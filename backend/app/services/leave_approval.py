from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import func
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.leave_approval import LeaveApprovalRepository
from app.schemas.leave_approval import (
    LeaveApprovalDelegateCreate,
    LeaveApprovalDelegateResponse,
    LeaveApprovalDelegateUpdate,
    LeaveAuditEntryResponse,
    LeaveDecisionRequest,
    LeaveQueueItemResponse,
    QueueEmployeeResponse,
)
from app.schemas.leave_attachment import LeaveAttachmentResponse
from app.schemas.leave_balance import LeaveBalanceResponse, LeaveRequestResponse
from app.schemas.leave_configuration import LeaveTypeResponse
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError
from app.services.leave_balance import sick_tiers

ZERO = Decimal("0.00")
ELIGIBLE_EMPLOYMENT = {"Active", "Probation", "On Leave"}


def same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


@dataclass(frozen=True, slots=True)
class ApprovalQueueQuery:
    limit: int
    cursor: str | None


def _request_response(row: RowMapping) -> LeaveRequestResponse:
    attachment_values = {
        "id": row["attachment_id"],
        "file_name": row["attachment_file_name"],
        "content_type": row["attachment_content_type"],
        "size_bytes": row["attachment_size_bytes"],
        "sha256": row["attachment_sha256"],
        "uploaded_at": row["attachment_uploaded_at"],
        "expires_at": row["attachment_expires_at"],
    }
    values = {name: row[name] for name in LeaveRequestResponse.model_fields if name != "attachment"}
    values["attachment"] = (
        None
        if attachment_values["id"] is None
        else LeaveAttachmentResponse.model_validate(attachment_values)
    )
    return LeaveRequestResponse.model_validate(values)


def _queue_item(row: RowMapping, *, admin: bool) -> LeaveQueueItemResponse:
    employee = dict(row["employee_projection"])
    type_values = {name: row[f"type_{name}"] for name in LeaveTypeResponse.model_fields}
    balance = None
    if row["balance_employee_id"] is not None:
        balance = LeaveBalanceResponse.model_validate(
            {name: row[f"balance_{name}"] for name in LeaveBalanceResponse.model_fields}
        )
    visibility = "administrator" if admin else row["visible_because"]
    return LeaveQueueItemResponse(
        request=_request_response(row),
        employee=QueueEmployeeResponse.model_validate(employee),
        leave_type=LeaveTypeResponse.model_validate(type_values),
        balance=balance,
        can_decide=True,
        visible_because=cast(
            Literal["directReport", "activeDelegation", "administrator"], visibility
        ),
    )


def _delegation_response(row: RowMapping) -> LeaveApprovalDelegateResponse:
    return LeaveApprovalDelegateResponse.model_validate(
        {name: row[name] for name in LeaveApprovalDelegateResponse.model_fields}
    )


class LeaveApprovalService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        repository: LeaveApprovalRepository | None = None,
    ) -> None:
        self.connection = connection
        self.repository = repository or LeaveApprovalRepository(connection)
        self.cursor_codec = cursor_codec

    @staticmethod
    def _staff(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id, principal.employee_id

    @staticmethod
    def _admin(principal: AuthorizationPrincipal, branch_id: uuid.UUID) -> None:
        if (
            principal.role is not AppRole.ADMIN
            or principal.employee_id is not None
            or principal.branch_id is not None
        ):
            raise ServiceExecutionError("operation_not_permitted")

    async def list_staff_queue(
        self, principal: AuthorizationPrincipal, query: ApprovalQueueQuery
    ) -> tuple[list[LeaveQueueItemResponse], str | None]:
        branch_id, employee_id = self._staff(principal)
        return await self._list_queue(
            principal,
            branch_id,
            query,
            admin=False,
            actor_employee_id=employee_id,
            operation_id="get_leave_approver_queue",
        )

    async def list_admin_queue(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ApprovalQueueQuery,
    ) -> tuple[list[LeaveQueueItemResponse], str | None]:
        self._admin(principal, branch_id)
        return await self._list_queue(
            principal,
            branch_id,
            query,
            admin=True,
            actor_employee_id=None,
            operation_id="get_admin_leave_approval_queue",
        )

    async def _list_queue(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: ApprovalQueueQuery,
        *,
        admin: bool,
        actor_employee_id: uuid.UUID | None,
        operation_id: str,
    ) -> tuple[list[LeaveQueueItemResponse], str | None]:
        try:
            after_id = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=query.cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        rows = (
            await self.repository.list_admin_queue(
                principal.company_id, branch_id, after_id=after_id, limit=query.limit
            )
            if admin
            else await self.repository.list_staff_queue(
                principal.company_id,
                branch_id,
                cast(uuid.UUID, actor_employee_id),
                after_id=after_id,
                limit=query.limit,
            )
        )
        if after_id is not None and not rows:
            raise ServiceExecutionError("invalid_cursor")
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=visible[-1]["id"],
            )
        return [_queue_item(row, admin=admin) for row in visible], next_cursor

    async def decide_staff(
        self,
        principal: AuthorizationPrincipal,
        request_id: uuid.UUID,
        body: LeaveDecisionRequest,
    ) -> LeaveRequestResponse:
        branch_id, employee_id = self._staff(principal)
        return await self._decide(
            principal,
            branch_id,
            request_id,
            body,
            admin=False,
            actor_employee_id=employee_id,
        )

    async def decide_admin(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        body: LeaveDecisionRequest,
    ) -> LeaveRequestResponse:
        self._admin(principal, branch_id)
        return await self._decide(
            principal,
            branch_id,
            request_id,
            body,
            admin=True,
            actor_employee_id=None,
        )

    async def _decide(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        body: LeaveDecisionRequest,
        *,
        admin: bool,
        actor_employee_id: uuid.UUID | None,
    ) -> LeaveRequestResponse:
        request = await self.repository.lock_request(principal.company_id, branch_id, request_id)
        if request is None:
            raise ServiceExecutionError("resource_not_found")
        if not same_version(request["updated_at"], body.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        employee_id = cast(uuid.UUID, request["employee_id"])
        visibility = "administrator"
        employee_status: str | None = None
        if admin:
            employee = await self.repository.lock_admin_employee(
                principal.company_id, branch_id, employee_id
            )
            if (
                employee is None
                or not employee["active"]
                or employee["employment_status"] not in ELIGIBLE_EMPLOYMENT
            ):
                raise ServiceExecutionError("resource_not_found")
            employee_status = str(employee["employment_status"])
        else:
            if employee_id == actor_employee_id:
                raise ServiceExecutionError("operation_not_permitted")
            visibility = await self.repository.lock_staff_authority(employee_id) or ""
            if visibility not in {"directReport", "activeDelegation"}:
                raise ServiceExecutionError("resource_not_found")
            employee = await self.repository.queue_employee(employee_id)
            if employee is None:
                raise ServiceExecutionError("resource_not_found")
            employee_status = await self.repository.decision_employee_status(employee_id)
            if employee_status is None:
                raise ServiceExecutionError("resource_not_found")
        leave_type = await self.repository.lock_type(
            principal.company_id, branch_id, request["leave_type_id"]
        )
        settings = await self.repository.lock_settings(principal.company_id, branch_id)
        attachment = await self.repository.lock_attachment(
            principal.company_id, branch_id, request_id
        )
        business_date = await self.repository.business_date()
        balance = await self.repository.lock_balance(
            principal.company_id,
            branch_id,
            employee_id,
            request["leave_type_id"],
            business_date.year,
        )
        if leave_type is None or settings is None or balance is None:
            raise ServiceExecutionError("resource_not_found")
        if not leave_type["is_active"]:
            raise ServiceExecutionError("state_conflict")
        if leave_type["requires_attachment"] and (
            attachment is None or attachment["status"] != "attached"
        ):
            raise ServiceExecutionError("state_conflict")
        old_status = str(request["status"])
        level = int(request["approval_level_required"])
        if admin:
            if not ((old_status == "Pending" and level == 1) or old_status == "ManagerApproved"):
                raise ServiceExecutionError("state_conflict")
            if old_status == "Pending" and not body.reason:
                raise ServiceExecutionError("validation_failed")
            if request["manager_approved_by_app_user_id"] == principal.app_user_id:
                raise ServiceExecutionError("operation_not_permitted")
            new_status = "Approved" if body.decision == "approve" else "Rejected"
        else:
            if old_status != "Pending":
                raise ServiceExecutionError("state_conflict")
            new_status = (
                "ManagerRejected"
                if body.decision == "reject"
                else "Approved"
                if level == 1
                else "ManagerApproved"
            )

        deducts = not leave_type["is_unlimited"] and not leave_type["not_deducted_from_annual"]
        if deducts and new_status in {"Approved", "Rejected", "ManagerRejected"}:
            days = Decimal(request["days_requested"])
            pending = Decimal(balance["pending_days"]) - days
            if pending < ZERO:
                raise RuntimeError("pending leave balance would become negative")
            values: dict[str, Decimal | bool] = {"pending_days": pending}
            if new_status == "Approved":
                used = Decimal(balance["used_days"]) + days
                values["used_days"] = used
                if leave_type["code"] == "SICK":
                    full, half, unpaid = sick_tiers(used, probation=employee_status == "Probation")
                    values.update(
                        sick_full_pay_used=full,
                        sick_half_pay_used=half,
                        sick_unpaid_used=unpaid,
                    )
                if leave_type["once_per_career"]:
                    values["hajj_taken"] = True
            else:
                values["remaining_days"] = Decimal(balance["remaining_days"]) + days
            await self.repository.update_balance(balance["id"], values)

        reason = body.reason
        request_values: dict[str, object] = {}
        if new_status in {"ManagerApproved", "ManagerRejected"}:
            request_values.update(
                manager_approved_by_app_user_id=principal.app_user_id,
                manager_approved_at=func.statement_timestamp(),
            )
            if new_status == "ManagerRejected":
                request_values["manager_rejection_reason"] = reason
            else:
                request_values["approval_comment"] = reason
        else:
            request_values.update(
                approved_by_app_user_id=principal.app_user_id,
                approved_at=func.statement_timestamp(),
            )
            if new_status == "Rejected":
                request_values["rejection_reason"] = reason
            else:
                request_values["approval_comment"] = reason
        request_values["status"] = new_status
        await self.repository.update_request(request_id, old_status, request_values)

        action = {
            "ManagerApproved": "manager_approved",
            "ManagerRejected": "manager_rejected",
            "Approved": "approved",
            "Rejected": "rejected",
        }[new_status]
        audit_reason = reason or f"Leave request {action.replace('_', ' ')}"
        await self.repository.insert_domain_audit(
            company_id=principal.company_id,
            branch_id=branch_id,
            request_id=request_id,
            actor_id=principal.app_user_id,
            action=action,
            reason=audit_reason,
            old_status=old_status,
            new_status=new_status,
        )
        protected_action = f"leave_request_{action}"
        await append_audit_event(
            self.connection,
            action=protected_action,
            entity_type="leave_request",
            entity_id=request_id,
            changed_fields=["status", "balance"],
            reason=audit_reason,
            metadata={
                "transition": f"{old_status}_to_{new_status}",
                "decision_source": visibility,
            },
        )
        row = await self.repository.get_request(principal.company_id, branch_id, request_id)
        if row is None:
            raise RuntimeError("decided leave request is not visible")
        return _request_response(row)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if kind != "leave_request" or resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        row = await self.repository.get_request(principal.company_id, branch_id, resource_id)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        actor_fields = {
            row.get("approved_by_app_user_id"),
            row.get("manager_approved_by_app_user_id"),
        }
        if principal.role is not AppRole.ADMIN and principal.app_user_id not in actor_fields:
            raise ServiceExecutionError("resource_not_found")

    async def list_delegations(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> list[LeaveApprovalDelegateResponse]:
        self._admin(principal, branch_id)
        rows = await self.repository.list_delegations(principal.company_id, branch_id)
        return [_delegation_response(row) for row in rows]

    async def create_delegation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        body: LeaveApprovalDelegateCreate,
    ) -> LeaveApprovalDelegateResponse:
        self._admin(principal, branch_id)
        business_date = await self.repository.business_date()
        if body.from_date < business_date:
            raise ServiceExecutionError("validation_failed")
        await self.repository.lock_delegations()
        await self._validate_delegation_people(principal, branch_id, body, exclude_id=None)
        row = await self.repository.create_delegation(
            {
                "company_id": principal.company_id,
                "branch_id": branch_id,
                **body.model_dump(by_alias=False),
            }
        )
        await append_audit_event(
            self.connection,
            action="leave_delegation_created",
            entity_type="leave_approval_delegate",
            entity_id=row["id"],
            changed_fields=["id", "approver_employee_id", "delegate_employee_id", "dates"],
            reason="Leave approval delegation created",
            metadata={},
        )
        return _delegation_response(row)

    async def update_delegation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        delegation_id: uuid.UUID,
        body: LeaveApprovalDelegateUpdate,
    ) -> LeaveApprovalDelegateResponse:
        self._admin(principal, branch_id)
        await self.repository.lock_delegations()
        row = await self.repository.lock_delegation(principal.company_id, branch_id, delegation_id)
        business_date = await self.repository.business_date()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if row["from_date"] <= business_date or body.from_date <= business_date:
            raise ServiceExecutionError("state_conflict")
        if not same_version(row["updated_at"], body.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        await self._validate_delegation_people(principal, branch_id, body, exclude_id=delegation_id)
        values = body.model_dump(exclude={"expected_updated_at"}, by_alias=False)
        await self.repository.update_delegation(delegation_id, values)
        updated = await self.repository.lock_delegation(
            principal.company_id, branch_id, delegation_id
        )
        if updated is None:
            raise RuntimeError("updated delegation is not visible")
        await append_audit_event(
            self.connection,
            action="leave_delegation_updated",
            entity_type="leave_approval_delegate",
            entity_id=delegation_id,
            changed_fields=["approver_employee_id", "delegate_employee_id", "dates"],
            reason="Leave approval delegation updated",
            metadata={},
        )
        return _delegation_response(updated)

    async def delete_delegation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        delegation_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> None:
        self._admin(principal, branch_id)
        await self.repository.lock_delegations()
        row = await self.repository.lock_delegation(principal.company_id, branch_id, delegation_id)
        business_date = await self.repository.business_date()
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if row["from_date"] <= business_date or not same_version(
            row["updated_at"], expected_updated_at
        ):
            raise ServiceExecutionError("state_conflict")
        await append_audit_event(
            self.connection,
            action="leave_delegation_deleted",
            entity_type="leave_approval_delegate",
            entity_id=delegation_id,
            changed_fields=["id"],
            reason="Leave approval delegation deleted",
            metadata={
                "approver_employee_id": str(row["approver_employee_id"]),
                "delegate_employee_id": str(row["delegate_employee_id"]),
            },
        )
        await self.repository.delete_delegation(delegation_id)

    async def _validate_delegation_people(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        body: LeaveApprovalDelegateCreate,
        *,
        exclude_id: uuid.UUID | None,
    ) -> None:
        approver, delegate = await self.repository.lock_delegation_people(
            principal.company_id,
            branch_id,
            body.approver_employee_id,
            body.delegate_employee_id,
        )
        if (
            approver is None
            or delegate is None
            or not approver["active"]
            or not delegate["active"]
            or approver["employment_status"] not in ELIGIBLE_EMPLOYMENT
            or delegate["employment_status"] not in ELIGIBLE_EMPLOYMENT
            or not await self.repository.approver_is_manager(
                principal.company_id, body.approver_employee_id
            )
        ):
            raise ServiceExecutionError("resource_not_found")
        if await self.repository.overlapping_delegation_exists(
            principal.company_id,
            branch_id,
            body.approver_employee_id,
            body.from_date,
            body.to_date,
            exclude_id=exclude_id,
        ):
            raise ServiceExecutionError("state_conflict")

    async def list_audit(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
    ) -> list[LeaveAuditEntryResponse]:
        if principal.role is AppRole.ADMIN:
            self._admin(principal, branch_id)
        else:
            staff_branch, _ = self._staff(principal)
            if branch_id != staff_branch:
                raise ServiceExecutionError("resource_not_found")
        rows = await self.repository.list_audit_projection(request_id)
        if not rows:
            raise ServiceExecutionError("resource_not_found")
        return [LeaveAuditEntryResponse.model_validate(row) for row in rows]
