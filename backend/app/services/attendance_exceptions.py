from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.schemas.attendance_calculation import AttendanceCalculationRequest
from app.schemas.attendance_exceptions import (
    AbsenceResolutionRequest,
    AttendanceAuditResponse,
    AttendanceExceptionRecordResponse,
    OvertimeApprovalRequest,
    RegularisationDecisionRequest,
    RegularisationResponse,
    RegularisationSubmitRequest,
)
from app.services.attendance_records import AttendanceRecordService
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class RegularisationListQuery:
    employee_id: uuid.UUID | None
    status: Literal["Pending", "Approved", "Rejected"] | None
    from_date: date | None
    to_date: date | None
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class AttendanceAuditListQuery:
    employee_id: uuid.UUID | None
    action: str | None
    from_date: date | None
    to_date: date | None
    limit: int
    cursor: str | None


class AttendanceExceptionRepository(Protocol):
    connection: AsyncConnection

    async def business_date(self) -> date: ...
    async def submit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: RegularisationSubmitRequest,
    ) -> RegularisationResponse: ...
    async def personal(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        query: RegularisationListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RegularisationResponse]: ...
    async def queue(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        query: RegularisationListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[RegularisationResponse]: ...
    async def decide(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        request_id: uuid.UUID,
        action: str,
        request: RegularisationDecisionRequest,
    ) -> RegularisationResponse: ...
    async def resolve_absence(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        record_id: uuid.UUID,
        request: AbsenceResolutionRequest,
    ) -> tuple[uuid.UUID, date, str, int]: ...
    async def approve_overtime(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        actor_id: uuid.UUID,
        record_id: uuid.UUID,
        request: OvertimeApprovalRequest,
    ) -> AttendanceExceptionRecordResponse: ...
    async def audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        query: AttendanceAuditListQuery,
        after_id: uuid.UUID | None,
        limit: int,
    ) -> list[AttendanceAuditResponse]: ...
    async def regularisation_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, request_id: uuid.UUID
    ) -> bool: ...
    async def audit_position(
        self, company_id: uuid.UUID, branch_id: uuid.UUID, audit_id: uuid.UUID
    ) -> bool: ...
    async def prepare_approval(
        self, request_id: uuid.UUID, expected_version: int
    ) -> tuple[uuid.UUID, date, str, int]: ...
    async def approval_audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        actor_id: uuid.UUID,
    ) -> None: ...
    async def approved_request(self, request_id: uuid.UUID) -> RegularisationResponse: ...
    async def record(self, record_id: uuid.UUID) -> AttendanceExceptionRecordResponse: ...
    async def resolution_audit(
        self,
        company_id: uuid.UUID,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        attendance_date: date,
        actor_id: uuid.UUID,
        reason: str,
        resolution_type: str,
    ) -> None: ...
    async def regularisation_exists(self, request_id: uuid.UUID) -> bool: ...
    async def attendance_record_exists(self, record_id: uuid.UUID) -> bool: ...


class AttendanceExceptionService:
    def __init__(
        self,
        repository: AttendanceExceptionRepository,
        cursor_codec: EmployeeCursorCodec | None = None,
    ) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    @staticmethod
    def _employee(principal: AuthorizationPrincipal) -> tuple[uuid.UUID, uuid.UUID]:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        return principal.branch_id, principal.employee_id

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role.value != "admin":
            raise ServiceExecutionError("operation_not_permitted")

    async def submit(
        self, principal: AuthorizationPrincipal, request: RegularisationSubmitRequest
    ) -> RegularisationResponse:
        branch_id, employee_id = self._employee(principal)
        today = await self.repository.business_date()
        if request.attendance_date > today:
            raise ServiceExecutionError("validation_failed")
        return await self.repository.submit(principal.company_id, branch_id, employee_id, request)

    def _decode_cursor(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        cursor: str | None,
    ) -> uuid.UUID | None:
        if cursor is None:
            return None
        try:
            if self.cursor_codec is None:
                raise ValueError
            result = self.cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=cursor,
            )
            if result is None:
                raise ValueError
            return result
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None

    def _next_cursor(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        last_id: uuid.UUID,
    ) -> str:
        if self.cursor_codec is None:
            raise ServiceExecutionError("invalid_cursor")
        return self.cursor_codec.encode(
            principal=principal,
            branch_id=branch_id,
            operation_id=operation_id,
            query=query,
            last_id=last_id,
        )

    async def personal(
        self, principal: AuthorizationPrincipal, query: RegularisationListQuery
    ) -> tuple[list[RegularisationResponse], str | None]:
        branch_id, employee_id = self._employee(principal)
        operation_id = "list_personal_attendance_regularisations"
        after_id = self._decode_cursor(principal, branch_id, operation_id, query, query.cursor)
        if after_id is not None and not await self.repository.regularisation_position(
            principal.company_id, branch_id, after_id
        ):
            raise ServiceExecutionError("invalid_cursor")
        rows = await self.repository.personal(
            principal.company_id,
            branch_id,
            employee_id,
            query,
            after_id,
            query.limit + 1,
        )
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, operation_id, query, visible[-1].id)
            if len(rows) > query.limit and visible
            else None
        )
        return visible, cursor

    async def queue(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: RegularisationListQuery,
    ) -> tuple[list[RegularisationResponse], str | None]:
        self._admin(principal)
        operation_id = "list_attendance_regularisations"
        after_id = self._decode_cursor(principal, branch_id, operation_id, query, query.cursor)
        if after_id is not None and not await self.repository.regularisation_position(
            principal.company_id, branch_id, after_id
        ):
            raise ServiceExecutionError("invalid_cursor")
        rows = await self.repository.queue(
            principal.company_id, branch_id, query, after_id, query.limit + 1
        )
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, operation_id, query, visible[-1].id)
            if len(rows) > query.limit and visible
            else None
        )
        return visible, cursor

    async def decide(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request_id: uuid.UUID,
        action: str,
        request: RegularisationDecisionRequest,
    ) -> RegularisationResponse:
        self._admin(principal)
        if action == "reject" and request.rejection_reason is None:
            raise ServiceExecutionError("validation_failed")
        if action == "approve" and request.rejection_reason is not None:
            raise ServiceExecutionError("validation_failed")
        if action == "approve":
            employee_id, attendance_date, digest, version = await self.repository.prepare_approval(
                request_id, request.expected_version
            )
            calculated = await AttendanceRecordService(
                self.repository.connection, None
            ).calculate_one(
                principal,
                branch_id,
                AttendanceCalculationRequest.model_validate(
                    {
                        "employeeId": str(employee_id),
                        "attendanceDate": attendance_date.isoformat(),
                        "expectedSourceDigest": digest,
                        "expectedCalculationVersion": version,
                    }
                ),
            )
            approved = await self.repository.approved_request(request_id)
            if (
                calculated.clock_in_time != approved.correct_clock_in
                or calculated.clock_out_time != approved.correct_clock_out
                or any(
                    flag in calculated.evidence_flags
                    for flag in (
                        "ambiguous_events",
                        "missing_clock_out",
                        "missing_split_interval",
                        "negative_interval",
                        "unmatched_clock_out",
                    )
                )
            ):
                raise ServiceExecutionError("state_conflict")
            await self.repository.approval_audit(
                principal.company_id,
                branch_id,
                employee_id,
                attendance_date,
                principal.app_user_id,
            )
            return approved
        return await self.repository.decide(
            principal.company_id, branch_id, principal.app_user_id, request_id, action, request
        )

    async def resolve_absence(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        request: AbsenceResolutionRequest,
    ) -> AttendanceExceptionRecordResponse:
        self._admin(principal)
        employee_id, attendance_date, digest, version = await self.repository.resolve_absence(
            principal.company_id, branch_id, principal.app_user_id, record_id, request
        )
        calculated = await AttendanceRecordService(self.repository.connection, None).calculate_one(
            principal,
            branch_id,
            AttendanceCalculationRequest.model_validate(
                {
                    "employeeId": str(employee_id),
                    "attendanceDate": attendance_date.isoformat(),
                    "expectedSourceDigest": digest,
                    "expectedCalculationVersion": version,
                }
            ),
        )
        expected_status = {
            "LEAVE_LINKED": "ON_LEAVE",
            "UNAUTHORISED": "UNEXPLAINED_ABSENCE",
            "WFH": "PRESENT_REMOTE",
        }[request.resolution_type]
        if calculated.status != expected_status:
            raise ServiceExecutionError("state_conflict")
        await self.repository.resolution_audit(
            principal.company_id,
            branch_id,
            calculated.employee_id,
            calculated.date,
            principal.app_user_id,
            request.reason,
            request.resolution_type,
        )
        return await self.repository.record(record_id)

    async def approve_overtime(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        record_id: uuid.UUID,
        request: OvertimeApprovalRequest,
    ) -> AttendanceExceptionRecordResponse:
        self._admin(principal)
        return await self.repository.approve_overtime(
            principal.company_id, branch_id, principal.app_user_id, record_id, request
        )

    async def audit(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: AttendanceAuditListQuery,
    ) -> tuple[list[AttendanceAuditResponse], str | None]:
        self._admin(principal)
        operation_id = "list_attendance_audit"
        after_id = self._decode_cursor(principal, branch_id, operation_id, query, query.cursor)
        if after_id is not None and not await self.repository.audit_position(
            principal.company_id, branch_id, after_id
        ):
            raise ServiceExecutionError("invalid_cursor")
        rows = await self.repository.audit(
            principal.company_id, branch_id, query, after_id, query.limit + 1
        )
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, operation_id, query, visible[-1].id)
            if len(rows) > query.limit and visible
            else None
        )
        return visible, cursor

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        if resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        if kind == "regularisation_request":
            if not await self.repository.regularisation_exists(resource_id):
                raise ServiceExecutionError("resource_not_found")
            return
        if kind == "attendance_record":
            self._admin(principal)
            if not await self.repository.attendance_record_exists(resource_id):
                raise ServiceExecutionError("resource_not_found")
            return
        raise ServiceExecutionError("resource_not_found")
