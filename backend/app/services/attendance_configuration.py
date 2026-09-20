from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.attendance_configuration import AttendanceConfigurationRepository
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.attendance_configuration import (
    AttendanceSettingsResponse,
    AttendanceSettingsUpdateRequest,
    ShiftAssignmentCreateRequest,
    ShiftAssignmentResponse,
    ShiftCreateRequest,
    ShiftResponse,
    ShiftUpdateRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class ShiftListQuery:
    limit: int
    active: bool | None
    shift_type: str | None
    shift_category: str | None
    search: str | None
    cursor: str | None


@dataclass(frozen=True, slots=True)
class AssignmentListQuery:
    limit: int
    employee_id: uuid.UUID
    effective_on: date | None
    cursor: str | None


def _settings(row: RowMapping) -> AttendanceSettingsResponse:
    values = dict(row)
    secret = str(values.pop("biometric_api_key"))
    values["biometric_api_key_configured"] = bool(secret)
    return AttendanceSettingsResponse.model_validate(values)


def _shift(row: RowMapping) -> ShiftResponse:
    return ShiftResponse.model_validate(row)


def _assignment(row: RowMapping) -> ShiftAssignmentResponse:
    return ShiftAssignmentResponse.model_validate(row)


def _same_instant(left: datetime, right: datetime) -> bool:
    normalized_left = left.astimezone(UTC).replace(microsecond=left.microsecond // 1000 * 1000)
    normalized_right = right.astimezone(UTC).replace(microsecond=right.microsecond // 1000 * 1000)
    return normalized_left == normalized_right


class AttendanceConfigurationService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        repository: AttendanceConfigurationRepository | None = None,
    ) -> None:
        self._connection = connection
        self._repository = repository or AttendanceConfigurationRepository(connection)
        self._cursor_codec = cursor_codec

    @staticmethod
    def _require_admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def get_settings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> AttendanceSettingsResponse:
        self._require_admin(principal)
        try:
            return _settings(await self._repository.fetch_settings(principal.company_id, branch_id))
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_settings(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: AttendanceSettingsUpdateRequest,
    ) -> AttendanceSettingsResponse:
        self._require_admin(principal)
        try:
            current = await self._repository.fetch_settings(
                principal.company_id, branch_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not _same_instant(current["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        secret_supplied = "biometric_api_key" in request.model_fields_set
        secret = request.biometric_api_key if secret_supplied else current["biometric_api_key"]
        if request.biometric_api_enabled and not secret:
            raise ServiceExecutionError("attendance_configuration_conflict")
        values = request.model_dump(
            exclude={"expected_updated_at", "biometric_api_key"},
            by_alias=False,
        )
        if secret_supplied:
            values["biometric_api_key"] = secret or ""
        changed = [
            field
            for field, value in values.items()
            if field != "biometric_api_key" and current[field] != value
        ]
        if secret_supplied and bool(current["biometric_api_key"]) != bool(secret):
            changed.append("biometric_api_key_configured")
        updated = await self._repository.update_settings(principal.company_id, branch_id, values)
        await append_audit_event(
            self._connection,
            action="attendance_settings_changed",
            entity_type="attendance_settings",
            entity_id=cast(uuid.UUID, current["id"]),
            changed_fields=sorted(changed),
            reason="Attendance settings updated",
            metadata={},
        )
        return _settings(updated)

    async def list_shifts(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, query: ShiftListQuery
    ) -> tuple[list[ShiftResponse], str | None]:
        self._require_admin(principal)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_shifts",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_shift_position(
                    principal.company_id, branch_id, after_id
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = list(
            await self._repository.fetch_shifts(
                company_id=principal.company_id,
                branch_id=branch_id,
                active=query.active,
                shift_type=query.shift_type,
                shift_category=query.shift_category,
                search=query.search,
                after=after,
                limit=query.limit,
            )
        )
        has_more = len(rows) > query.limit
        page_rows = rows[: query.limit]
        cursor = None
        if has_more and page_rows:
            cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_shifts",
                query=query,
                last_id=page_rows[-1]["id"],
            )
        return [_shift(row) for row in page_rows], cursor

    async def create_shift(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, request: ShiftCreateRequest
    ) -> ShiftResponse:
        self._require_admin(principal)
        try:
            row = await self._repository.create_shift(
                principal.company_id,
                branch_id,
                request.model_dump(by_alias=False),
            )
        except IntegrityError:
            raise ServiceExecutionError("shift_conflict") from None
        await append_audit_event(
            self._connection,
            action="shift_created",
            entity_type="shift",
            entity_id=row["id"],
            changed_fields=sorted(request.model_dump(by_alias=False)),
            reason="Shift created",
            metadata={},
        )
        return _shift(row)

    async def update_shift(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        shift_id: uuid.UUID,
        request: ShiftUpdateRequest,
    ) -> ShiftResponse:
        self._require_admin(principal)
        try:
            current = await self._repository.fetch_shift(
                principal.company_id, branch_id, shift_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not _same_instant(current["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        if await self._repository.shift_has_any_reference(
            principal.company_id, branch_id, shift_id
        ):
            raise ServiceExecutionError("retained_shift")
        changed_fields = request.model_fields_set - {"expected_updated_at"}
        changes = {field: getattr(request, field) for field in changed_fields}
        final = {field: current[field] for field in ShiftCreateRequest.model_fields}
        final.update(changes)
        try:
            validated = ShiftCreateRequest.model_validate(final, by_name=True)
            row = await self._repository.update_shift(
                principal.company_id,
                branch_id,
                shift_id,
                validated.model_dump(by_alias=False),
            )
        except IntegrityError:
            raise ServiceExecutionError("shift_conflict") from None
        await append_audit_event(
            self._connection,
            action="shift_changed",
            entity_type="shift",
            entity_id=shift_id,
            changed_fields=sorted(changed_fields),
            reason="Shift updated",
            metadata={},
        )
        return _shift(row)

    async def deactivate_shift(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        shift_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> ShiftResponse:
        self._require_admin(principal)
        try:
            current = await self._repository.fetch_shift(
                principal.company_id, branch_id, shift_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not _same_instant(current["updated_at"], expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        business_date = await self._repository.business_date()
        if await self._repository.shift_has_current_or_future_assignment(
            principal.company_id, branch_id, shift_id, business_date
        ):
            raise ServiceExecutionError("retained_shift")
        row = await self._repository.update_shift(
            principal.company_id, branch_id, shift_id, {"is_active": False}
        )
        await append_audit_event(
            self._connection,
            action="shift_deactivated",
            entity_type="shift",
            entity_id=shift_id,
            changed_fields=["is_active"],
            reason="Shift deactivated",
            metadata={},
        )
        return _shift(row)

    async def list_assignments(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, query: AssignmentListQuery
    ) -> tuple[list[ShiftAssignmentResponse], str | None]:
        self._require_admin(principal)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_shift_assignments",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_assignment_position(
                    principal.company_id,
                    branch_id,
                    query.employee_id,
                    after_id,
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = list(
            await self._repository.fetch_assignments(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=query.employee_id,
                effective_on=query.effective_on,
                after=after,
                limit=query.limit,
            )
        )
        has_more = len(rows) > query.limit
        page_rows = rows[: query.limit]
        cursor = (
            None
            if not has_more or not page_rows
            else self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_shift_assignments",
                query=query,
                last_id=page_rows[-1]["id"],
            )
        )
        return [_assignment(row) for row in page_rows], cursor

    async def assign_shift(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: ShiftAssignmentCreateRequest,
    ) -> ShiftAssignmentResponse:
        self._require_admin(principal)
        business_date = await self._repository.business_date()
        if request.effective_from < business_date:
            raise ServiceExecutionError("shift_assignment_conflict")
        try:
            employee = await self._repository.fetch_employee_for_assignment(
                principal.company_id, branch_id, request.employee_id
            )
            shift = await self._repository.fetch_shift(
                principal.company_id, branch_id, request.shift_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if (
            not employee["active"]
            or employee["employment_status"] not in {"Active", "Probation", "On Leave"}
            or not shift["is_active"]
        ):
            raise ServiceExecutionError("shift_assignment_conflict")
        rows = list(
            await self._repository.lock_assignments(
                principal.company_id, branch_id, request.employee_id
            )
        )
        current = next(
            (
                row
                for row in rows
                if row["effective_from"] <= request.effective_from
                and (row["effective_to"] is None or row["effective_to"] >= request.effective_from)
            ),
            None,
        )
        version_matches = (
            current is None
            and request.expected_current_assignment_id is None
            and request.expected_current_assignment_updated_at is None
        ) or (
            current is not None
            and request.expected_current_assignment_id == current["id"]
            and request.expected_current_assignment_updated_at is not None
            and _same_instant(
                current["updated_at"],
                request.expected_current_assignment_updated_at,
            )
        )
        if not version_matches or (
            current is not None and current["effective_from"] == request.effective_from
        ):
            raise ServiceExecutionError("state_conflict")
        next_row = min(
            (row for row in rows if row["effective_from"] > request.effective_from),
            key=lambda row: row["effective_from"],
            default=None,
        )
        effective_to = None if next_row is None else next_row["effective_from"] - timedelta(days=1)
        if current is not None:
            await self._repository.close_assignment(
                current["id"], request.effective_from - timedelta(days=1)
            )
        try:
            row = await self._repository.create_assignment(
                principal.company_id,
                branch_id,
                request.employee_id,
                request.shift_id,
                request.effective_from,
                effective_to,
            )
        except IntegrityError:
            raise ServiceExecutionError("shift_assignment_conflict") from None
        await append_audit_event(
            self._connection,
            action="shift_assigned",
            entity_type="shift_assignment",
            entity_id=row["id"],
            changed_fields=["employee_id", "shift_id", "effective_from", "effective_to"],
            reason="Shift assigned",
            metadata={
                "employee_id": str(request.employee_id),
                "shift_id": str(request.shift_id),
                "effective_from": request.effective_from.isoformat(),
                "effective_to": None if effective_to is None else effective_to.isoformat(),
            },
        )
        return _assignment(row)

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._require_admin(principal)
        if resource_id is None:
            raise ServiceExecutionError("resource_not_found")
        try:
            if kind == "attendance_settings":
                row = await self._repository.fetch_settings(principal.company_id, branch_id)
                if row["id"] != resource_id:
                    raise ResourceNotFoundError
            elif kind == "shift":
                await self._repository.fetch_shift(principal.company_id, branch_id, resource_id)
            elif kind == "shift_assignment":
                await self._repository.fetch_assignment(
                    principal.company_id, branch_id, resource_id
                )
            else:
                raise ResourceNotFoundError
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
