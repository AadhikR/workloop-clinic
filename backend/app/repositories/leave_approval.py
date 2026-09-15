from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import asc, delete, func, insert, or_, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Employee, UserProfile
from app.models.leave import (
    LeaveApprovalDelegate,
    LeaveAttachment,
    LeaveBalance,
    LeaveRequest,
    LeaveSettings,
    LeaveType,
)
from app.repositories.leave_request import REQUEST_COLUMNS


class LeaveApprovalRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def list_staff_queue(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_employee_id: uuid.UUID,
        *,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        criteria = [
            LeaveRequest.company_id == company_id,
            LeaveRequest.branch_id == branch_id,
            LeaveRequest.status == "Pending",
            LeaveRequest.employee_id != actor_employee_id,
            func.public.leave_decision_visibility(LeaveRequest.employee_id).is_not(None),
        ]
        if after_id is not None:
            criteria.append(LeaveRequest.id > after_id)
        return list(
            (
                await self.connection.execute(
                    self._queue_select()
                    .where(*criteria)
                    .order_by(asc(LeaveRequest.id))
                    .limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )

    async def list_admin_queue(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        *,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RowMapping]:
        criteria = [
            LeaveRequest.company_id == company_id,
            LeaveRequest.branch_id == branch_id,
            or_(
                (LeaveRequest.status == "Pending") & (LeaveRequest.approval_level_required == 1),
                LeaveRequest.status == "ManagerApproved",
            ),
        ]
        if after_id is not None:
            criteria.append(LeaveRequest.id > after_id)
        return list(
            (
                await self.connection.execute(
                    self._queue_select()
                    .where(*criteria)
                    .order_by(asc(LeaveRequest.id))
                    .limit(limit + 1)
                )
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _queue_select():
        return (
            select(
                *REQUEST_COLUMNS,
                func.public.leave_queue_employee(LeaveRequest.employee_id).label(
                    "employee_projection"
                ),
                func.public.leave_decision_visibility(LeaveRequest.employee_id).label(
                    "visible_because"
                ),
                *(
                    column.label(f"type_{column.name}")
                    for column in LeaveType.__table__.c
                    if column.name != "company_id"
                ),
                LeaveBalance.employee_id.label("balance_employee_id"),
                LeaveBalance.leave_type_id.label("balance_leave_type_id"),
                LeaveBalance.leave_year.label("balance_leave_year"),
                LeaveBalance.entitled_days.label("balance_entitled_days"),
                LeaveBalance.accrued_days.label("balance_accrued_days"),
                LeaveBalance.used_days.label("balance_used_days"),
                LeaveBalance.pending_days.label("balance_pending_days"),
                LeaveBalance.carried_forward.label("balance_carried_forward"),
                LeaveBalance.remaining_days.label("balance_remaining_days"),
                LeaveBalance.sick_full_pay_used.label("balance_sick_full_pay_used"),
                LeaveBalance.sick_half_pay_used.label("balance_sick_half_pay_used"),
                LeaveBalance.sick_unpaid_used.label("balance_sick_unpaid_used"),
                LeaveAttachment.id.label("attachment_id"),
                LeaveAttachment.file_name.label("attachment_file_name"),
                LeaveAttachment.content_type.label("attachment_content_type"),
                LeaveAttachment.size_bytes.label("attachment_size_bytes"),
                LeaveAttachment.sha256.label("attachment_sha256"),
                LeaveAttachment.uploaded_at.label("attachment_uploaded_at"),
                LeaveAttachment.expires_at.label("attachment_expires_at"),
            )
            .join(
                LeaveType,
                (LeaveType.id == LeaveRequest.leave_type_id)
                & (LeaveType.company_id == LeaveRequest.company_id)
                & (LeaveType.branch_id == LeaveRequest.branch_id),
            )
            .outerjoin(
                LeaveBalance,
                (LeaveBalance.employee_id == LeaveRequest.employee_id)
                & (LeaveBalance.leave_type_id == LeaveRequest.leave_type_id)
                & (LeaveBalance.leave_year == func.extract("year", LeaveRequest.start_date)),
            )
            .outerjoin(
                LeaveAttachment,
                (LeaveAttachment.leave_request_id == LeaveRequest.id)
                & (LeaveAttachment.status == "attached"),
            )
        )

    async def lock_request(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveRequest.__table__.c)
                    .where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.id == request_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_staff_authority(self, target_employee_id: uuid.UUID) -> str | None:
        value = await self.connection.scalar(
            text("SELECT public.lock_leave_decision_authority(:target_employee_id)"),
            {"target_employee_id": target_employee_id},
        )
        return None if value is None else str(value)

    async def queue_employee(self, target_employee_id: uuid.UUID) -> dict[str, Any] | None:
        value = await self.connection.scalar(
            text("SELECT public.leave_queue_employee(:target_employee_id)"),
            {"target_employee_id": target_employee_id},
        )
        return None if value is None else dict(value)

    async def decision_employee_status(self, target_employee_id: uuid.UUID) -> str | None:
        value = await self.connection.scalar(
            text("SELECT public.leave_decision_employee_status(:target_employee_id)"),
            {"target_employee_id": target_employee_id},
        )
        return None if value is None else str(value)

    async def lock_admin_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(Employee.id, Employee.active, Employee.employment_status)
                    .where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.id == employee_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_type(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, type_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveType.__table__.c)
                    .where(
                        LeaveType.company_id == company_id,
                        LeaveType.branch_id == branch_id,
                        LeaveType.id == type_id,
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_settings(self, company_id: uuid.UUID, branch_id: uuid.UUID) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveSettings.__table__.c)
                    .where(
                        LeaveSettings.company_id == company_id,
                        LeaveSettings.branch_id == branch_id,
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_attachment(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(LeaveAttachment.id, LeaveAttachment.status)
                    .where(
                        LeaveAttachment.company_id == company_id,
                        LeaveAttachment.branch_id == branch_id,
                        LeaveAttachment.leave_request_id == request_id,
                    )
                    .with_for_update(read=True)
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_balance(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        year: int,
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveBalance.__table__.c)
                    .where(
                        LeaveBalance.company_id == company_id,
                        LeaveBalance.branch_id == branch_id,
                        LeaveBalance.employee_id == employee_id,
                        LeaveBalance.leave_type_id == leave_type_id,
                        LeaveBalance.leave_year == year,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def owner_app_user_id(
        self, company_id: uuid.UUID, employee_id: uuid.UUID
    ) -> uuid.UUID | None:
        return await self.connection.scalar(
            select(UserProfile.app_user_id).where(
                UserProfile.company_id == company_id,
                UserProfile.employee_id == employee_id,
            )
        )

    async def update_balance(
        self, balance_id: uuid.UUID, values: dict[str, Decimal | bool]
    ) -> None:
        result = await self.connection.execute(
            update(LeaveBalance)
            .where(LeaveBalance.id == balance_id)
            .values(**values, updated_at=func.statement_timestamp())
        )
        if result.rowcount != 1:
            raise RuntimeError("leave decision lost its balance lock")

    async def update_request(
        self,
        request_id: uuid.UUID,
        expected_status: str,
        values: dict[str, Any],
    ) -> None:
        result = await self.connection.execute(
            update(LeaveRequest)
            .where(LeaveRequest.id == request_id, LeaveRequest.status == expected_status)
            .values(**values, updated_at=func.statement_timestamp())
        )
        if result.rowcount != 1:
            raise RuntimeError("leave decision lost its request lock")

    async def insert_domain_audit(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        reason: str,
        old_status: str,
        new_status: str,
    ) -> None:
        await self.connection.execute(
            text(
                "SELECT public.append_leave_domain_decision_audit("
                ":request_id,:action,:reason,:old_status,:new_status)"
            ),
            {
                "request_id": request_id,
                "action": action,
                "reason": reason,
                "old_status": old_status,
                "new_status": new_status,
            },
        )

    async def get_request(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(
                        *REQUEST_COLUMNS,
                        LeaveRequest.approved_by_app_user_id,
                        LeaveRequest.manager_approved_by_app_user_id,
                        LeaveAttachment.id.label("attachment_id"),
                        LeaveAttachment.file_name.label("attachment_file_name"),
                        LeaveAttachment.content_type.label("attachment_content_type"),
                        LeaveAttachment.size_bytes.label("attachment_size_bytes"),
                        LeaveAttachment.sha256.label("attachment_sha256"),
                        LeaveAttachment.uploaded_at.label("attachment_uploaded_at"),
                        LeaveAttachment.expires_at.label("attachment_expires_at"),
                    )
                    .outerjoin(
                        LeaveAttachment,
                        (LeaveAttachment.leave_request_id == LeaveRequest.id)
                        & (LeaveAttachment.status == "attached"),
                    )
                    .where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.id == request_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )

    async def list_delegations(
        self, company_id: uuid.UUID, branch_id: uuid.UUID
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    select(*LeaveApprovalDelegate.__table__.c)
                    .where(
                        LeaveApprovalDelegate.company_id == company_id,
                        LeaveApprovalDelegate.branch_id == branch_id,
                    )
                    .order_by(asc(LeaveApprovalDelegate.from_date), asc(LeaveApprovalDelegate.id))
                )
            )
            .mappings()
            .all()
        )

    async def lock_delegation_people(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        approver_id: uuid.UUID,
        delegate_id: uuid.UUID,
    ) -> tuple[RowMapping | None, RowMapping | None]:
        rows = list(
            (
                await self.connection.execute(
                    select(Employee.id, Employee.active, Employee.employment_status)
                    .where(
                        Employee.company_id == company_id,
                        Employee.branch_id == branch_id,
                        Employee.id.in_(sorted((approver_id, delegate_id), key=str)),
                    )
                    .order_by(asc(Employee.id))
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )
        by_id = {row["id"]: row for row in rows}
        return by_id.get(approver_id), by_id.get(delegate_id)

    async def lock_delegations(self) -> None:
        await self.connection.exec_driver_sql(
            "LOCK TABLE public.leave_approval_delegates IN SHARE ROW EXCLUSIVE MODE"
        )

    async def overlapping_delegation_exists(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        approver_id: uuid.UUID,
        from_date: date,
        to_date: date,
        *,
        exclude_id: uuid.UUID | None,
    ) -> bool:
        criteria = [
            LeaveApprovalDelegate.company_id == company_id,
            LeaveApprovalDelegate.branch_id == branch_id,
            LeaveApprovalDelegate.approver_employee_id == approver_id,
            LeaveApprovalDelegate.from_date <= to_date,
            LeaveApprovalDelegate.to_date >= from_date,
        ]
        if exclude_id is not None:
            criteria.append(LeaveApprovalDelegate.id != exclude_id)
        return (
            await self.connection.scalar(select(LeaveApprovalDelegate.id).where(*criteria).limit(1))
        ) is not None

    async def approver_is_manager(self, company_id: uuid.UUID, employee_id: uuid.UUID) -> bool:
        value = await self.connection.scalar(
            select(UserProfile.app_user_id).where(
                UserProfile.company_id == company_id,
                UserProfile.employee_id == employee_id,
                UserProfile.role == "manager",
            )
        )
        return value is not None

    async def create_delegation(self, values: dict[str, Any]) -> RowMapping:
        delegation_id = uuid.uuid4()
        row = (
            (
                await self.connection.execute(
                    insert(LeaveApprovalDelegate)
                    .values(id=delegation_id, **values)
                    .returning(*LeaveApprovalDelegate.__table__.c)
                )
            )
            .mappings()
            .one()
        )
        return row

    async def lock_delegation(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, delegation_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveApprovalDelegate.__table__.c)
                    .where(
                        LeaveApprovalDelegate.company_id == company_id,
                        LeaveApprovalDelegate.branch_id == branch_id,
                        LeaveApprovalDelegate.id == delegation_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def update_delegation(self, delegation_id: uuid.UUID, values: dict[str, Any]) -> None:
        result = await self.connection.execute(
            update(LeaveApprovalDelegate)
            .where(LeaveApprovalDelegate.id == delegation_id)
            .values(**values, updated_at=func.statement_timestamp())
        )
        if result.rowcount != 1:
            raise RuntimeError("delegation update lost its lock")

    async def delete_delegation(self, delegation_id: uuid.UUID) -> None:
        result = await self.connection.execute(
            delete(LeaveApprovalDelegate).where(LeaveApprovalDelegate.id == delegation_id)
        )
        if result.rowcount != 1:
            raise RuntimeError("delegation delete lost its lock")

    async def list_audit_projection(self, request_id: uuid.UUID) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    text(
                        "SELECT id,leave_request_id,action,reason,old_status,new_status,created_at "
                        "FROM public.read_leave_audit_projection(:request_id)"
                    ),
                    {"request_id": request_id},
                )
            )
            .mappings()
            .all()
        )
