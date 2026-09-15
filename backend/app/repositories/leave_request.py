from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import asc, func, insert, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.identity import Employee
from app.models.leave import (
    LeaveAttachment,
    LeaveAuditLog,
    LeaveBalance,
    LeaveRequest,
    LeaveSettings,
    LeaveType,
    PublicHoliday,
)
from app.models.storage import StorageOperation
from app.services.leave_attachment import ClaimedCleanup

REQUEST_COLUMNS = (
    LeaveRequest.id,
    LeaveRequest.branch_id,
    LeaveRequest.employee_id,
    LeaveRequest.leave_type_id,
    LeaveRequest.start_date,
    LeaveRequest.end_date,
    LeaveRequest.is_half_day,
    LeaveRequest.half_day_period,
    LeaveRequest.days_requested,
    LeaveRequest.status,
    LeaveRequest.reason,
    LeaveRequest.rejection_reason,
    LeaveRequest.manager_rejection_reason,
    LeaveRequest.relationship,
    LeaveRequest.deceased_name,
    LeaveRequest.date_of_death,
    LeaveRequest.child_birth_date,
    LeaveRequest.child_name,
    LeaveRequest.expected_due_date,
    LeaveRequest.institution_name,
    LeaveRequest.exam_dates,
    LeaveRequest.substitute_employee_id,
    LeaveRequest.approval_level_required,
    LeaveRequest.approval_comment,
    LeaveRequest.warnings,
    LeaveRequest.submitted_at,
    LeaveRequest.created_at,
    LeaveRequest.updated_at,
)


def employee_lock_key(company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID) -> int:
    material = b"\x00".join(
        (
            b"wlp-leave-submission-lock-v1",
            str(company_id).encode("ascii"),
            str(branch_id).encode("ascii"),
            str(employee_id).encode("ascii"),
        )
    )
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big", signed=True)


class LeaveRequestRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def lock_employee_scope(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> None:
        await self.connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": employee_lock_key(company_id, branch_id, employee_id)},
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

    async def lock_employee(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(
                        Employee.id,
                        Employee.active,
                        Employee.employment_status,
                        Employee.employment_start_date,
                        Employee.gender,
                    )
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
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_substitute(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, employee_id: uuid.UUID
    ) -> RowMapping | None:
        return await self.lock_employee(company_id, branch_id, employee_id)

    async def lock_overlaps(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> list[RowMapping]:
        return list(
            (
                await self.connection.execute(
                    select(
                        LeaveRequest.id,
                        LeaveRequest.start_date,
                        LeaveRequest.end_date,
                        LeaveRequest.status,
                    )
                    .where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.employee_id == employee_id,
                        LeaveRequest.status.in_(("Pending", "ManagerApproved", "Approved")),
                        LeaveRequest.start_date <= end_date,
                        LeaveRequest.end_date >= start_date,
                    )
                    .order_by(asc(LeaveRequest.id))
                    .with_for_update()
                )
            )
            .mappings()
            .all()
        )

    async def lock_balance(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        leave_year: int,
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
                        LeaveBalance.leave_year == leave_year,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def lock_attachment(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attachment_id: uuid.UUID,
        creator_id: uuid.UUID,
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(LeaveAttachment)
                    .where(
                        LeaveAttachment.id == attachment_id,
                        LeaveAttachment.company_id == company_id,
                        LeaveAttachment.branch_id == branch_id,
                        LeaveAttachment.employee_id == employee_id,
                        LeaveAttachment.created_by_app_user_id == creator_id,
                        LeaveAttachment.status == "staged",
                        LeaveAttachment.leave_request_id.is_(None),
                        LeaveAttachment.expires_at > func.statement_timestamp(),
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def holidays(self, company_id: uuid.UUID, branch_id: uuid.UUID, year: int) -> list[date]:
        return list(
            (
                await self.connection.execute(
                    select(PublicHoliday.date).where(
                        PublicHoliday.company_id == company_id,
                        PublicHoliday.branch_id == branch_id,
                        PublicHoliday.year == year,
                    )
                )
            ).scalars()
        )

    async def insert_request(self, values: dict[str, Any]) -> uuid.UUID:
        request_id = uuid.uuid4()
        await self.connection.execute(insert(LeaveRequest).values(id=request_id, **values))
        return request_id

    async def bind_attachment(self, attachment_id: uuid.UUID, request_id: uuid.UUID) -> None:
        result = await self.connection.execute(
            update(LeaveAttachment)
            .where(
                LeaveAttachment.id == attachment_id,
                LeaveAttachment.status == "staged",
                LeaveAttachment.leave_request_id.is_(None),
            )
            .values(
                leave_request_id=request_id,
                status="attached",
                attached_at=func.statement_timestamp(),
                expires_at=None,
                updated_at=func.statement_timestamp(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("attachment binding lost its lock")

    async def update_balance(
        self, balance_id: uuid.UUID, values: dict[str, Decimal | bool]
    ) -> None:
        result = await self.connection.execute(
            update(LeaveBalance)
            .where(LeaveBalance.id == balance_id)
            .values(**values, updated_at=func.statement_timestamp())
        )
        if result.rowcount != 1:
            raise RuntimeError("balance update lost its lock")

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
            insert(LeaveAuditLog)
            .inline()
            .values(
                company_id=company_id,
                branch_id=branch_id,
                leave_request_id=request_id,
                actor_app_user_id=actor_id,
                action=action,
                reason=reason,
                old_status=old_status,
                new_status=new_status,
                created_at=func.statement_timestamp(),
            )
        )

    async def auto_approve(self, request_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        result = await self.connection.execute(
            update(LeaveRequest)
            .where(LeaveRequest.id == request_id, LeaveRequest.status == "Pending")
            .values(
                status="Approved",
                approved_by_app_user_id=actor_id,
                approved_at=func.statement_timestamp(),
                approval_comment="Auto-approved by leave type policy",
                updated_at=func.statement_timestamp(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("automatic approval lost its request lock")

    async def lock_request(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(*LeaveRequest.__table__.c)
                    .where(
                        LeaveRequest.id == request_id,
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )

    async def cancel_request(self, request_id: uuid.UUID, expected_status: str) -> None:
        result = await self.connection.execute(
            update(LeaveRequest)
            .where(LeaveRequest.id == request_id, LeaveRequest.status == expected_status)
            .values(status="Cancelled", updated_at=func.statement_timestamp())
        )
        if result.rowcount != 1:
            raise RuntimeError("cancellation lost its request lock")

    async def request_attachment_cleanup(
        self,
        *,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request_id: uuid.UUID,
        actor_id: uuid.UUID,
    ) -> ClaimedCleanup | None:
        row = (
            await self.connection.execute(
                select(LeaveAttachment.id, LeaveAttachment.object_key)
                .where(
                    LeaveAttachment.company_id == company_id,
                    LeaveAttachment.branch_id == branch_id,
                    LeaveAttachment.employee_id == employee_id,
                    LeaveAttachment.leave_request_id == request_id,
                    LeaveAttachment.status == "attached",
                )
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            return None
        operation_id = (
            await self.connection.execute(
                insert(StorageOperation)
                .values(
                    company_id=company_id,
                    branch_id=branch_id,
                    employee_id=employee_id,
                    created_by_app_user_id=actor_id,
                    entity_type="leave_attachment",
                    entity_id=row.id,
                    operation="delete",
                    object_key=row.object_key,
                )
                .returning(StorageOperation.id)
            )
        ).scalar_one()
        await self.connection.execute(
            update(StorageOperation)
            .where(StorageOperation.id == operation_id, StorageOperation.status == "pending")
            .values(
                status="claimed",
                attempt_count=1,
                claimed_at=func.statement_timestamp(),
                lease_expires_at=func.statement_timestamp() + text("interval '15 minutes'"),
                updated_at=func.statement_timestamp(),
            )
        )
        await self.connection.execute(
            update(LeaveAttachment)
            .where(LeaveAttachment.id == row.id)
            .values(
                status="cleanup_pending",
                cleanup_requested_at=func.statement_timestamp(),
                expires_at=None,
                updated_at=func.statement_timestamp(),
            )
        )
        return ClaimedCleanup(row.id, operation_id, row.object_key)

    async def approved_days_except(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        leave_type_id: uuid.UUID,
        leave_year: int,
        excluded_request_id: uuid.UUID,
    ) -> Decimal:
        value = await self.connection.scalar(
            select(func.coalesce(func.sum(LeaveRequest.days_requested), 0)).where(
                LeaveRequest.company_id == company_id,
                LeaveRequest.branch_id == branch_id,
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.leave_type_id == leave_type_id,
                LeaveRequest.status == "Approved",
                LeaveRequest.id != excluded_request_id,
                LeaveRequest.start_date >= date(leave_year, 1, 1),
                LeaveRequest.end_date <= date(leave_year, 12, 31),
            )
        )
        if value is None:
            raise RuntimeError("approved leave sum returned no value")
        return Decimal(value)

    async def get_request(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> RowMapping | None:
        return (
            (
                await self.connection.execute(
                    select(
                        *REQUEST_COLUMNS,
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
                        LeaveRequest.id == request_id,
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
