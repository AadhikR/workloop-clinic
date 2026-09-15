from __future__ import annotations

import uuid
from decimal import Decimal
from typing import cast

from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.leave_request import LeaveRequestRepository
from app.schemas.leave_attachment import LeaveAttachmentResponse
from app.schemas.leave_balance import LeaveRequestResponse
from app.schemas.leave_request import LeaveSubmissionRequest
from app.services.execution import ServiceExecutionError
from app.services.leave_attachment import ClaimedCleanup
from app.services.leave_balance import completed_service_months, leave_days, sick_tiers

ZERO = Decimal("0.00")
ACTIVE_EMPLOYMENT = {"Active", "Probation", "On Leave"}


def _required(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def type_fields_valid(code: str, request: LeaveSubmissionRequest) -> bool:
    values = {
        "relationship": request.relationship,
        "deceased_name": request.deceased_name,
        "date_of_death": request.date_of_death,
        "child_birth_date": request.child_birth_date,
        "child_name": request.child_name,
        "expected_due_date": request.expected_due_date,
        "institution_name": request.institution_name,
        "exam_dates": request.exam_dates,
    }
    allowed: set[str]
    if code == "BEREAVEMENT":
        allowed = {"relationship", "deceased_name", "date_of_death"}
        if request.relationship is None:
            return False
    elif code == "PATERNITY":
        allowed = {"child_birth_date", "child_name"}
        if request.child_birth_date is None:
            return False
    elif code == "MATERNITY":
        allowed = {"expected_due_date"}
        if request.expected_due_date is None:
            return False
    elif code == "STUDY":
        allowed = {"institution_name", "exam_dates"}
        if not _required(request.institution_name) or not _required(request.exam_dates):
            return False
    else:
        allowed = set()
    return all(
        name in allowed or value is None or (isinstance(value, str) and not value)
        for name, value in values.items()
    )


def _request_response(row: RowMapping) -> LeaveRequestResponse:
    attachment = None
    if row["attachment_id"] is not None:
        attachment = LeaveAttachmentResponse(
            id=row["attachment_id"],
            file_name=row["attachment_file_name"],
            content_type=row["attachment_content_type"],
            size_bytes=row["attachment_size_bytes"],
            sha256=row["attachment_sha256"],
            uploaded_at=row["attachment_uploaded_at"],
            expires_at=row["attachment_expires_at"],
        )
    values = {name: row[name] for name in LeaveRequestResponse.model_fields if name != "attachment"}
    values["attachment"] = attachment
    return LeaveRequestResponse.model_validate(values)


class LeaveRequestService:
    def __init__(
        self,
        connection: AsyncConnection,
        repository: LeaveRequestRepository | None = None,
    ) -> None:
        self.connection = connection
        self.repository = repository or LeaveRequestRepository(connection)

    @staticmethod
    def _branch(
        principal: AuthorizationPrincipal, selected_branch_id: uuid.UUID | None
    ) -> uuid.UUID:
        if principal.role is AppRole.ADMIN:
            if selected_branch_id is None or principal.employee_id is not None:
                raise ServiceExecutionError("operation_not_permitted")
            return selected_branch_id
        if (
            principal.role not in {AppRole.EMPLOYEE, AppRole.MANAGER}
            or principal.employee_id is None
            or principal.branch_id is None
            or selected_branch_id is not None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id

    async def submit(
        self,
        principal: AuthorizationPrincipal,
        request: LeaveSubmissionRequest,
        *,
        employee_id: uuid.UUID,
        selected_branch_id: uuid.UUID | None,
    ) -> LeaveRequestResponse:
        branch_id = self._branch(principal, selected_branch_id)
        if principal.role is not AppRole.ADMIN and principal.employee_id != employee_id:
            raise ServiceExecutionError("operation_not_permitted")
        business_date = await self.repository.business_date()
        if (
            request.start_date.year != business_date.year
            or request.end_date.year != business_date.year
        ):
            raise ServiceExecutionError("validation_failed")

        await self.repository.lock_employee_scope(principal.company_id, branch_id, employee_id)
        settings = await self.repository.lock_settings(principal.company_id, branch_id)
        employee = await self.repository.lock_employee(principal.company_id, branch_id, employee_id)
        leave_type = await self.repository.lock_type(
            principal.company_id, branch_id, request.leave_type_id
        )
        if settings is None or employee is None or leave_type is None:
            raise ServiceExecutionError("resource_not_found")
        if not employee["active"] or employee["employment_status"] not in ACTIVE_EMPLOYMENT:
            raise ServiceExecutionError("resource_not_found")
        if not leave_type["is_active"]:
            raise ServiceExecutionError("resource_not_found")

        substitute = None
        if request.substitute_employee_id is not None:
            if request.substitute_employee_id == employee_id:
                raise ServiceExecutionError("validation_failed")
            substitute = await self.repository.lock_substitute(
                principal.company_id, branch_id, request.substitute_employee_id
            )
            if (
                substitute is None
                or not substitute["active"]
                or substitute["employment_status"] not in ACTIVE_EMPLOYMENT
            ):
                raise ServiceExecutionError("resource_not_found")

        overlaps = await self.repository.lock_overlaps(
            principal.company_id,
            branch_id,
            employee_id,
            request.start_date,
            request.end_date,
        )
        if overlaps:
            raise ServiceExecutionError("state_conflict")
        balance = await self.repository.lock_balance(
            principal.company_id,
            branch_id,
            employee_id,
            request.leave_type_id,
            business_date.year,
        )
        if balance is None:
            raise ServiceExecutionError("resource_not_found")

        attachment = None
        if request.attachment_id is not None:
            attachment = await self.repository.lock_attachment(
                principal.company_id,
                branch_id,
                employee_id,
                request.attachment_id,
                principal.app_user_id,
            )
            if attachment is None:
                raise ServiceExecutionError("resource_not_found")
        if leave_type["requires_attachment"] and attachment is None:
            raise ServiceExecutionError("validation_failed")
        if leave_type["requires_reason"] and not request.reason:
            raise ServiceExecutionError("validation_failed")
        if not type_fields_valid(cast(str, leave_type["code"]), request):
            raise ServiceExecutionError("validation_failed")
        if request.date_of_death is not None and request.date_of_death > request.start_date:
            raise ServiceExecutionError("validation_failed")
        if request.child_birth_date is not None and request.child_birth_date > request.start_date:
            raise ServiceExecutionError("validation_failed")
        if (
            leave_type["gender_restriction"] is not None
            and employee["gender"] != leave_type["gender_restriction"]
        ):
            raise ServiceExecutionError("validation_failed")
        service_months = completed_service_months(employee["employment_start_date"], business_date)
        if service_months < leave_type["min_service_months"]:
            raise ServiceExecutionError("validation_failed")
        if employee["employment_status"] == "Probation" and not leave_type["probation_eligible"]:
            raise ServiceExecutionError("validation_failed")
        if leave_type["once_per_career"] and balance["hajj_taken"]:
            raise ServiceExecutionError("validation_failed")

        holidays = await self.repository.holidays(
            principal.company_id, branch_id, business_date.year
        )
        try:
            days = leave_days(
                request.start_date,
                request.end_date,
                day_count_type=leave_type["day_count_type"],
                weekend_definition=settings["weekend_definition"],
                holidays=holidays,
                half_day=request.is_half_day,
            )
        except ValueError:
            raise ServiceExecutionError("validation_failed") from None
        if days <= ZERO:
            raise ServiceExecutionError("validation_failed")

        deducts = not leave_type["is_unlimited"] and not leave_type["not_deducted_from_annual"]
        if deducts and days > balance["remaining_days"]:
            raise ServiceExecutionError("validation_failed")
        warnings: list[str] = []
        notice_days = (request.start_date - business_date).days
        if notice_days < leave_type["min_notice_days"]:
            warnings.append(
                f"This request gives {notice_days} days notice; the leave type requires "
                f"{leave_type['min_notice_days']}."
            )
        if leave_type["code"] == "SICK" and employee["employment_status"] == "Probation":
            warnings.append("Sick leave during probation is unpaid.")

        request_id = await self.repository.insert_request(
            {
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "leave_type_id": request.leave_type_id,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "is_half_day": request.is_half_day,
                "half_day_period": request.half_day_period,
                "days_requested": days,
                "status": "Pending",
                "reason": request.reason,
                "relationship": request.relationship or "",
                "deceased_name": request.deceased_name or "",
                "date_of_death": request.date_of_death,
                "child_birth_date": request.child_birth_date,
                "child_name": request.child_name or "",
                "expected_due_date": request.expected_due_date,
                "institution_name": request.institution_name or "",
                "exam_dates": request.exam_dates or "",
                "substitute_employee_id": request.substitute_employee_id,
                "approval_level_required": 1 if settings["approval_chain"] == "1-level" else 2,
                "warnings": warnings,
            }
        )
        if request.attachment_id is not None:
            await self.repository.bind_attachment(request.attachment_id, request_id)

        pending = Decimal(balance["pending_days"])
        used = Decimal(balance["used_days"])
        remaining = Decimal(balance["remaining_days"])
        if deducts:
            pending += days
            remaining -= days
            await self.repository.update_balance(
                balance["id"], {"pending_days": pending, "remaining_days": remaining}
            )
        await self.repository.insert_domain_audit(
            company_id=principal.company_id,
            branch_id=branch_id,
            request_id=request_id,
            actor_id=principal.app_user_id,
            action="submitted",
            reason="Leave request submitted",
            old_status="",
            new_status="Pending",
        )
        submission_mode = "administrator" if principal.role is AppRole.ADMIN else "self"
        await append_audit_event(
            self.connection,
            action="leave_request_submitted",
            entity_type="leave_request",
            entity_id=request_id,
            changed_fields=["id", "status", "days_requested", "approval_level_required"],
            reason="Leave request submitted",
            metadata={"transition": "created_to_pending", "submission_mode": submission_mode},
        )

        if leave_type["auto_approve"]:
            await self.repository.auto_approve(request_id, principal.app_user_id)
            if deducts:
                pending -= days
                used += days
                values: dict[str, Decimal | bool] = {
                    "pending_days": pending,
                    "used_days": used,
                    "remaining_days": remaining,
                }
                if leave_type["code"] == "SICK":
                    full, half, unpaid = sick_tiers(
                        used, probation=employee["employment_status"] == "Probation"
                    )
                    values.update(
                        sick_full_pay_used=full,
                        sick_half_pay_used=half,
                        sick_unpaid_used=unpaid,
                    )
                if leave_type["once_per_career"]:
                    values["hajj_taken"] = True
                await self.repository.update_balance(balance["id"], values)
            await self.repository.insert_domain_audit(
                company_id=principal.company_id,
                branch_id=branch_id,
                request_id=request_id,
                actor_id=principal.app_user_id,
                action="auto_approved",
                reason="Leave request auto-approved by leave type policy",
                old_status="Pending",
                new_status="Approved",
            )
            await append_audit_event(
                self.connection,
                action="leave_request_auto_approved",
                entity_type="leave_request",
                entity_id=request_id,
                changed_fields=[
                    "status",
                    "approved_by_app_user_id",
                    "approved_at",
                    "approval_comment",
                ],
                reason="Leave request auto-approved by leave type policy",
                metadata={
                    "transition": "pending_to_approved",
                    "decision_source": "leave_type_policy",
                },
            )

        row = await self.repository.get_request(principal.company_id, branch_id, request_id)
        if row is None:
            raise RuntimeError("submitted leave request is not visible")
        return _request_response(row)

    async def cancel(
        self,
        principal: AuthorizationPrincipal,
        request_id: uuid.UUID,
        *,
        selected_branch_id: uuid.UUID | None,
    ) -> LeaveRequestResponse:
        response, _claimed = await self.cancel_with_cleanup(
            principal, request_id, selected_branch_id=selected_branch_id
        )
        return response

    async def cancel_with_cleanup(
        self,
        principal: AuthorizationPrincipal,
        request_id: uuid.UUID,
        *,
        selected_branch_id: uuid.UUID | None,
    ) -> tuple[LeaveRequestResponse, ClaimedCleanup | None]:
        branch_id = self._branch(principal, selected_branch_id)
        preliminary = await self.repository.get_request(principal.company_id, branch_id, request_id)
        if preliminary is None:
            raise ServiceExecutionError("resource_not_found")
        employee_id = cast(uuid.UUID, preliminary["employee_id"])
        if principal.role is not AppRole.ADMIN and principal.employee_id != employee_id:
            raise ServiceExecutionError("resource_not_found")
        await self.repository.lock_employee_scope(principal.company_id, branch_id, employee_id)
        request = await self.repository.lock_request(principal.company_id, branch_id, request_id)
        if request is None:
            raise ServiceExecutionError("resource_not_found")
        business_date = await self.repository.business_date()
        expected = "Approved" if principal.role is AppRole.ADMIN else "Pending"
        if request["status"] != expected:
            raise ServiceExecutionError("state_conflict")
        if expected == "Approved" and request["start_date"] <= business_date:
            raise ServiceExecutionError("state_conflict")

        leave_type = await self.repository.lock_type(
            principal.company_id, branch_id, request["leave_type_id"]
        )
        balance = await self.repository.lock_balance(
            principal.company_id,
            branch_id,
            employee_id,
            request["leave_type_id"],
            business_date.year,
        )
        if leave_type is None or balance is None:
            raise ServiceExecutionError("resource_not_found")
        days = Decimal(request["days_requested"])
        deducts = not leave_type["is_unlimited"] and not leave_type["not_deducted_from_annual"]
        if deducts:
            values: dict[str, Decimal | bool] = {}
            if expected == "Pending":
                pending = Decimal(balance["pending_days"]) - days
                if pending < ZERO:
                    raise RuntimeError("pending leave balance would become negative")
                values["pending_days"] = pending
            else:
                used = Decimal(balance["used_days"]) - days
                if used < ZERO:
                    raise RuntimeError("used leave balance would become negative")
                values["used_days"] = used
                if leave_type["code"] == "SICK":
                    remaining_sick = await self.repository.approved_days_except(
                        principal.company_id,
                        branch_id,
                        employee_id,
                        request["leave_type_id"],
                        business_date.year,
                        request_id,
                    )
                    full, half, unpaid = sick_tiers(remaining_sick)
                    values.update(
                        sick_full_pay_used=full,
                        sick_half_pay_used=half,
                        sick_unpaid_used=unpaid,
                    )
                if leave_type["once_per_career"]:
                    other_used = await self.repository.approved_days_except(
                        principal.company_id,
                        branch_id,
                        employee_id,
                        request["leave_type_id"],
                        business_date.year,
                        request_id,
                    )
                    values["hajj_taken"] = other_used > ZERO
            values["remaining_days"] = Decimal(balance["remaining_days"]) + days
            await self.repository.update_balance(balance["id"], values)

        claimed = await self.repository.request_attachment_cleanup(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            request_id=request_id,
            actor_id=principal.app_user_id,
        )
        if claimed is not None:
            await append_audit_event(
                self.connection,
                action="leave_attachment_cleanup_requested",
                entity_type="leave_attachment",
                entity_id=claimed.attachment_id,
                changed_fields=["status"],
                reason="Leave attachment cleanup requested",
                metadata={
                    "storage_operation_id": str(claimed.operation_id),
                    "trigger": "request_cancelled",
                },
            )
        await self.repository.cancel_request(request_id, expected)
        await self.repository.insert_domain_audit(
            company_id=principal.company_id,
            branch_id=branch_id,
            request_id=request_id,
            actor_id=principal.app_user_id,
            action="cancelled",
            reason="Leave request cancelled",
            old_status=expected,
            new_status="Cancelled",
        )
        transition = "approved_to_cancelled" if expected == "Approved" else "pending_to_cancelled"
        await append_audit_event(
            self.connection,
            action="leave_request_cancelled",
            entity_type="leave_request",
            entity_id=request_id,
            changed_fields=["status"],
            reason="Leave request cancelled",
            metadata={"transition": transition},
        )
        row = await self.repository.get_request(principal.company_id, branch_id, request_id)
        if row is None:
            raise RuntimeError("cancelled leave request is not visible")
        return _request_response(row), claimed

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
        if row is None or (
            principal.role is not AppRole.ADMIN and row["employee_id"] != principal.employee_id
        ):
            raise ServiceExecutionError("resource_not_found")
