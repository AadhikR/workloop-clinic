from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models.attendance import (
    AttendanceAuditLog,
    AttendancePeriod,
    AttendanceRecord,
    AttendanceSettings,
    RegularisationRequest,
)
from app.models.identity import Employee
from app.models.leave import LeaveRequest
from app.schemas.attendance_exceptions import (
    AbsenceResolutionRequest,
    AttendanceAuditResponse,
    AttendanceExceptionRecordResponse,
    OvertimeApprovalRequest,
    RegularisationDecisionRequest,
    RegularisationResponse,
    RegularisationSubmitRequest,
)
from app.services.execution import ServiceExecutionError

if TYPE_CHECKING:
    from app.services.attendance_exceptions import (
        AttendanceAuditListQuery,
        RegularisationListQuery,
    )


def _request(row: RowMapping) -> RegularisationResponse:
    return RegularisationResponse(
        id=row["id"],
        employee_id=row["employee_id"],
        attendance_date=row["attendance_date"],
        correct_clock_in=row["correct_clock_in"],
        correct_clock_out=row["correct_clock_out"],
        reason=row["reason"],
        status=row["status"],
        rejection_reason=row["rejection_reason"] or None,
        submitted_at=row["submitted_at"],
        decided_at=row["approved_at"],
        version=row["version"],
    )


def _record(row: RowMapping) -> AttendanceExceptionRecordResponse:
    return AttendanceExceptionRecordResponse(
        id=row["id"],
        employee_id=row["employee_id"],
        date=row["date"],
        status=row["status"],
        resolution_type=row["resolution_type"] or None,
        absence_deduction=Decimal(row["absence_deduction"]),
        overtime_hours=Decimal(row["overtime_hours"]),
        overtime_type=row["overtime_type"],
        overtime_amount=Decimal(row["overtime_amount"]),
        overtime_approved=row["overtime_approved"],
        overtime_approved_at=row["overtime_approved_at"],
        overtime_approval_source_digest=row["overtime_approval_source_digest"],
        resolved_at=row["resolved_at"],
        resolution_source_digest=row["resolution_source_digest"],
        calculation_version=row["calculation_version"],
    )


class SqlAttendanceExceptionRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self.connection = connection

    async def business_date(self) -> date:
        return (
            await self.connection.exec_driver_sql("SELECT public.workloop_business_date()")
        ).scalar_one()

    async def submit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: RegularisationSubmitRequest,
    ) -> RegularisationResponse:
        settings = (
            (
                await self.connection.execute(
                    text(
                        "SELECT window_days, max_days FROM public.phase10e_regularisation_limits()"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            settings is None
            or (await self.business_date() - request.attendance_date).days > settings["window_days"]
        ):
            raise ServiceExecutionError("validation_failed")
        next_month = (request.attendance_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        existing = (
            await self.connection.execute(
                select(func.count())
                .select_from(RegularisationRequest)
                .where(
                    RegularisationRequest.company_id == company_id,
                    RegularisationRequest.branch_id == branch_id,
                    RegularisationRequest.employee_id == employee_id,
                    RegularisationRequest.attendance_date >= request.attendance_date.replace(day=1),
                    RegularisationRequest.attendance_date < next_month,
                )
            )
        ).scalar_one()
        if existing >= settings["max_days"]:
            raise ServiceExecutionError("state_conflict")
        duplicate = (
            await self.connection.execute(
                select(RegularisationRequest.id)
                .where(
                    RegularisationRequest.company_id == company_id,
                    RegularisationRequest.branch_id == branch_id,
                    RegularisationRequest.employee_id == employee_id,
                    RegularisationRequest.attendance_date == request.attendance_date,
                    RegularisationRequest.status == "Pending",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise ServiceExecutionError("state_conflict")
        try:
            row = (
                (
                    await self.connection.execute(
                        insert(RegularisationRequest)
                        .values(
                            company_id=company_id,
                            branch_id=branch_id,
                            employee_id=employee_id,
                            attendance_date=request.attendance_date,
                            correct_clock_in=request.correct_clock_in,
                            correct_clock_out=request.correct_clock_out,
                            reason=request.reason.strip(),
                        )
                        .returning(*RegularisationRequest.__table__.c)
                    )
                )
                .mappings()
                .one()
            )
        except IntegrityError:
            raise ServiceExecutionError("state_conflict") from None
        return _request(row)

    async def personal(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        query: RegularisationListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RegularisationResponse]:
        filters = [
            RegularisationRequest.company_id == company_id,
            RegularisationRequest.branch_id == branch_id,
            RegularisationRequest.employee_id == employee_id,
        ]
        if query.status is not None:
            filters.append(RegularisationRequest.status == query.status)
        if query.from_date is not None:
            filters.append(RegularisationRequest.attendance_date >= query.from_date)
        if query.to_date is not None:
            filters.append(RegularisationRequest.attendance_date <= query.to_date)
        if after_id is not None:
            filters.append(RegularisationRequest.id > after_id)
        rows = (
            await self.connection.execute(
                select(*RegularisationRequest.__table__.c)
                .where(*filters)
                .order_by(RegularisationRequest.id)
                .limit(limit)
            )
        ).mappings()
        return [_request(row) for row in rows]

    async def queue(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        query: RegularisationListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RegularisationResponse]:
        filters = [
            RegularisationRequest.company_id == company_id,
            RegularisationRequest.branch_id == branch_id,
        ]
        if query.employee_id is not None:
            filters.append(RegularisationRequest.employee_id == query.employee_id)
        if query.status is not None:
            filters.append(RegularisationRequest.status == query.status)
        if query.from_date is not None:
            filters.append(RegularisationRequest.attendance_date >= query.from_date)
        if query.to_date is not None:
            filters.append(RegularisationRequest.attendance_date <= query.to_date)
        if after_id is not None:
            filters.append(RegularisationRequest.id > after_id)
        rows = (
            await self.connection.execute(
                select(*RegularisationRequest.__table__.c)
                .where(*filters)
                .order_by(RegularisationRequest.id)
                .limit(limit)
            )
        ).mappings()
        return [_request(row) for row in rows]

    async def decide(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_id: uuid.UUID,
        action: str,
        request: RegularisationDecisionRequest,
    ) -> RegularisationResponse:
        row = (
            (
                await self.connection.execute(
                    select(*RegularisationRequest.__table__.c)
                    .where(
                        RegularisationRequest.id == request_id,
                        RegularisationRequest.company_id == company_id,
                        RegularisationRequest.branch_id == branch_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if row["status"] != "Pending" or row["version"] != request.expected_version:
            raise ServiceExecutionError("state_conflict")
        period = (
            await self.connection.execute(
                select(AttendancePeriod.status)
                .where(
                    AttendancePeriod.company_id == company_id,
                    AttendancePeriod.branch_id == branch_id,
                    AttendancePeriod.period == row["attendance_date"].strftime("%Y-%m"),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if period == "closed":
            raise ServiceExecutionError("state_conflict")
        values = {
            "status": "Rejected",
            "approved_by_app_user_id": actor_id,
            "approved_at": func.now(),
            "rejection_reason": request.rejection_reason,
            "version": row["version"] + 1,
        }
        saved = (
            (
                await self.connection.execute(
                    update(RegularisationRequest)
                    .where(
                        RegularisationRequest.id == request_id,
                        RegularisationRequest.version == request.expected_version,
                    )
                    .values(**values)
                    .returning(*RegularisationRequest.__table__.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if saved is None:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            company_id,
            branch_id,
            row["employee_id"],
            row["attendance_date"],
            actor_id,
            "REGULARISATION_REJECTED",
            row["reason"],
            "Pending",
            "Rejected",
        )
        return _request(saved)

    async def prepare_approval(
        self, request_id: uuid.UUID, expected_version: int
    ) -> tuple[uuid.UUID, date, str, int]:
        try:
            row = (
                (
                    await self.connection.execute(
                        text(
                            "SELECT employee_id, attendance_date, source_digest, "
                            "calculation_version "
                            "FROM public.phase10e_prepare_regularisation_approval("
                            ":request_id, :version)"
                        ),
                        {"request_id": request_id, "version": expected_version},
                    )
                )
                .mappings()
                .one_or_none()
            )
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) in {"23505", "40001", "42501"}:
                raise ServiceExecutionError("state_conflict") from None
            raise
        if row is None:
            raise ServiceExecutionError("state_conflict")
        return (
            row["employee_id"],
            row["attendance_date"],
            row["source_digest"],
            row["calculation_version"],
        )

    async def approval_audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        actor_id: uuid.UUID,
    ) -> None:
        await self._audit(
            company_id,
            branch_id,
            employee_id,
            attendance_date,
            actor_id,
            "REGULARISATION_APPROVED",
            "Approved attendance correction",
            "Pending",
            "Approved",
        )

    async def approved_request(self, request_id: uuid.UUID) -> RegularisationResponse:
        row = (
            (
                await self.connection.execute(
                    select(*RegularisationRequest.__table__.c).where(
                        RegularisationRequest.id == request_id
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("state_conflict")
        return _request(row)

    async def resolve_absence(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        record_id: uuid.UUID,
        request: AbsenceResolutionRequest,
    ) -> tuple[uuid.UUID, date, str, int]:
        row = await self._locked_record(
            company_id,
            branch_id,
            record_id,
            request.expected_calculation_version,
            allow_stale=True,
        )
        if row["status"] != "UNEXPLAINED_ABSENCE" or row["resolution_type"]:
            raise ServiceExecutionError("state_conflict")
        if request.resolution_type == "LEAVE_LINKED":
            leave = (
                await self.connection.execute(
                    select(LeaveRequest.id)
                    .where(
                        LeaveRequest.company_id == company_id,
                        LeaveRequest.branch_id == branch_id,
                        LeaveRequest.employee_id == row["employee_id"],
                        LeaveRequest.status == "Approved",
                        LeaveRequest.start_date <= row["date"],
                        LeaveRequest.end_date >= row["date"],
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if leave is None:
                raise ServiceExecutionError("state_conflict")
        if request.resolution_type == "WFH":
            enabled = (
                await self.connection.execute(
                    select(AttendanceSettings.wfh_enabled)
                    .where(
                        AttendanceSettings.company_id == company_id,
                        AttendanceSettings.branch_id == branch_id,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if enabled is not True:
                raise ServiceExecutionError("state_conflict")
        employee = (
            await self.connection.execute(
                select(Employee.id)
                .where(
                    Employee.id == row["employee_id"],
                    Employee.company_id == company_id,
                    Employee.branch_id == branch_id,
                    Employee.active.is_(True),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if employee is None:
            raise ServiceExecutionError("state_conflict")
        prepared = (
            (
                await self.connection.execute(
                    update(AttendanceRecord)
                    .where(
                        AttendanceRecord.id == record_id,
                        AttendanceRecord.calculation_version
                        == request.expected_calculation_version,
                    )
                    .values(
                        resolution_type=request.resolution_type,
                        resolved_by_app_user_id=actor_id,
                        resolved_at=func.now(),
                        resolution_source_digest=row["source_digest"],
                        resolution_notes=request.reason,
                    )
                    .returning(*AttendanceRecord.__table__.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if prepared is None:
            raise ServiceExecutionError("state_conflict")
        return (
            prepared["employee_id"],
            prepared["date"],
            prepared["source_digest"],
            prepared["calculation_version"],
        )

    async def approve_overtime(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        record_id: uuid.UUID,
        request: OvertimeApprovalRequest,
    ) -> AttendanceExceptionRecordResponse:
        row = await self._locked_record(
            company_id, branch_id, record_id, request.expected_calculation_version
        )
        if row["overtime_hours"] <= 0 or row["overtime_type"] is None or row["overtime_approved"]:
            raise ServiceExecutionError("state_conflict")
        saved = (
            (
                await self.connection.execute(
                    update(AttendanceRecord)
                    .where(
                        AttendanceRecord.id == record_id,
                        AttendanceRecord.calculation_version
                        == request.expected_calculation_version,
                    )
                    .values(overtime_approved=True, overtime_approved_by_app_user_id=actor_id)
                    .values(
                        overtime_approved_at=func.now(),
                        overtime_approval_source_digest=row["source_digest"],
                    )
                    .returning(*AttendanceRecord.__table__.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if saved is None:
            raise ServiceExecutionError("state_conflict")
        await self._audit(
            company_id,
            branch_id,
            row["employee_id"],
            row["date"],
            actor_id,
            "OVERTIME_APPROVED",
            "approved calculated overtime",
            "unapproved",
            "approved",
        )
        return _record(saved)

    async def record(self, record_id: uuid.UUID) -> AttendanceExceptionRecordResponse:
        row = (
            (
                await self.connection.execute(
                    select(*AttendanceRecord.__table__.c).where(AttendanceRecord.id == record_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("state_conflict")
        return _record(row)

    async def resolution_audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        actor_id: uuid.UUID,
        reason: str,
        resolution_type: str,
    ) -> None:
        await self._audit(
            company_id,
            branch_id,
            employee_id,
            attendance_date,
            actor_id,
            "ABSENCE_RESOLVED",
            reason,
            "UNEXPLAINED_ABSENCE",
            resolution_type,
        )

    async def _locked_record(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        expected: int,
        *,
        allow_stale: bool = False,
    ) -> RowMapping:
        row = (
            (
                await self.connection.execute(
                    select(*AttendanceRecord.__table__.c)
                    .where(
                        AttendanceRecord.id == record_id,
                        AttendanceRecord.company_id == company_id,
                        AttendanceRecord.branch_id == branch_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        if (
            row["period_closed"]
            or (row["source_stale"] and not allow_stale)
            or row["calculation_version"] != expected
        ):
            raise ServiceExecutionError("state_conflict")
        return row

    async def _audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        actor_id: uuid.UUID,
        action: str,
        reason: str,
        old_value: str,
        new_value: str,
    ) -> None:
        await self.connection.execute(
            insert(AttendanceAuditLog).values(
                company_id=company_id,
                branch_id=branch_id,
                employee_id=employee_id,
                attendance_date=attendance_date,
                actor_app_user_id=actor_id,
                action=action,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
            )
        )

    async def audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        query: AttendanceAuditListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[AttendanceAuditResponse]:
        filters = [
            AttendanceAuditLog.company_id == company_id,
            AttendanceAuditLog.branch_id == branch_id,
        ]
        if query.employee_id is not None:
            filters.append(AttendanceAuditLog.employee_id == query.employee_id)
        if query.action is not None:
            filters.append(AttendanceAuditLog.action == query.action)
        if query.from_date is not None:
            filters.append(AttendanceAuditLog.attendance_date >= query.from_date)
        if query.to_date is not None:
            filters.append(AttendanceAuditLog.attendance_date <= query.to_date)
        if after_id is not None:
            filters.append(AttendanceAuditLog.id > after_id)
        rows = (
            await self.connection.execute(
                select(
                    AttendanceAuditLog.id,
                    AttendanceAuditLog.employee_id,
                    AttendanceAuditLog.attendance_date,
                    AttendanceAuditLog.action,
                    AttendanceAuditLog.created_at,
                )
                .where(*filters)
                .order_by(AttendanceAuditLog.id)
                .limit(limit)
            )
        ).mappings()
        return [
            AttendanceAuditResponse(
                id=row["id"],
                employee_id=row["employee_id"],
                attendance_date=row["attendance_date"],
                action=row["action"],
                occurred_at=row["created_at"],
            )
            for row in rows
        ]

    async def regularisation_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> bool:
        return (
            await self.connection.execute(
                select(RegularisationRequest.id).where(
                    RegularisationRequest.id == request_id,
                    RegularisationRequest.company_id == company_id,
                    RegularisationRequest.branch_id == branch_id,
                )
            )
        ).scalar_one_or_none() is not None

    async def audit_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, audit_id: uuid.UUID
    ) -> bool:
        return (
            await self.connection.execute(
                select(AttendanceAuditLog.id).where(
                    AttendanceAuditLog.id == audit_id,
                    AttendanceAuditLog.company_id == company_id,
                    AttendanceAuditLog.branch_id == branch_id,
                )
            )
        ).scalar_one_or_none() is not None

    async def regularisation_exists(self, request_id: uuid.UUID) -> bool:
        return (
            await self.connection.execute(
                select(RegularisationRequest.id).where(RegularisationRequest.id == request_id)
            )
        ).scalar_one_or_none() is not None

    async def attendance_record_exists(self, record_id: uuid.UUID) -> bool:
        return (
            await self.connection.execute(
                select(AttendanceRecord.id).where(AttendanceRecord.id == record_id)
            )
        ).scalar_one_or_none() is not None
