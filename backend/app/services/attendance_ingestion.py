from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.db.audit import append_audit_event
from app.models.identity import AppRole
from app.repositories.attendance_ingestion import AttendanceIngestionRepository
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.attendance_ingestion import (
    BiometricImportRequest,
    BiometricImportResponse,
    BiometricMappingRequest,
    BiometricMappingResponse,
    ClockEventResponse,
    ImportRowOutcome,
    ManualClockEventRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError

_DUBAI = ZoneInfo("Asia/Dubai")
_ELIGIBLE = {"Active", "Probation", "On Leave"}


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _event(row: object) -> ClockEventResponse:
    return ClockEventResponse.model_validate(row)


@dataclass(frozen=True, slots=True)
class EventListQuery:
    limit: int
    employee_id: uuid.UUID | None
    start: datetime | None
    end: datetime | None
    cursor: str | None


@dataclass(frozen=True, slots=True)
class MappingListQuery:
    limit: int
    cursor: str | None


class AttendanceIngestionService:
    def __init__(
        self, connection: AsyncConnection, cursor_codec: EmployeeCursorCodec | None = None
    ) -> None:
        self.connection = connection
        self.repository = AttendanceIngestionRepository(connection)
        self.cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    async def list_events(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: EventListQuery,
        operation_id: str = "list_clock_events",
    ) -> tuple[list[ClockEventResponse], str | None]:
        self._admin(principal)
        return await self._events_page(principal, branch_id, query, operation_id)

    async def self_events(
        self,
        principal: AuthorizationPrincipal,
        query: EventListQuery,
    ) -> tuple[list[ClockEventResponse], str | None]:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        scoped_query = EventListQuery(
            limit=query.limit,
            employee_id=principal.employee_id,
            start=query.start,
            end=query.end,
            cursor=query.cursor,
        )
        return await self._events_page(
            principal, principal.branch_id, scoped_query, "list_self_clock_events"
        )

    async def _events_page(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: EventListQuery,
        operation_id: str,
    ) -> tuple[list[ClockEventResponse], str | None]:
        try:
            after_id = (
                None
                if self.cursor_codec is None
                else self.cursor_codec.decode(
                    principal=principal,
                    branch_id=branch_id,
                    operation_id=operation_id,
                    query=query,
                    cursor=query.cursor,
                )
            )
            if query.cursor is not None and self.cursor_codec is None:
                raise ValueError
            after = (
                None
                if after_id is None
                else await self.repository.event_position(principal.company_id, branch_id, after_id)
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = list(
            await self.repository.events(
                principal.company_id,
                branch_id,
                query.employee_id,
                query.start,
                query.end,
                after,
                query.limit + 1,
            )
        )
        page_rows = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and page_rows:
            if self.cursor_codec is None:
                raise RuntimeError("cursor codec is unavailable")
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=page_rows[-1]["id"],
            )
        return [_event(row) for row in page_rows], next_cursor

    async def manual(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: ManualClockEventRequest,
    ) -> ClockEventResponse:
        self._admin(principal)
        try:
            employee = await self.repository.employee(
                principal.company_id, branch_id, request.employee_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not employee["active"] or employee["employment_status"] not in _ELIGIBLE:
            raise ServiceExecutionError("resource_not_found")
        business_date = await self.repository.business_date()
        local = request.event_time.astimezone(_DUBAI).date()
        if local < business_date - timedelta(days=31) or local > business_date + timedelta(days=1):
            raise ServiceExecutionError("validation_failed")
        if await self.repository.minute_duplicate(
            principal.company_id,
            branch_id,
            request.employee_id,
            request.event_type,
            "MANUAL",
            request.event_time.astimezone(UTC),
        ):
            raise ServiceExecutionError("clock_event_conflict")
        row = await self.repository.create_manual(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            {
                "employee_id": request.employee_id,
                "event_type": request.event_type,
                "event_time": request.event_time.astimezone(UTC),
                "notes": request.note,
            },
        )
        if row is None:
            raise ServiceExecutionError("clock_event_conflict")
        await append_audit_event(
            self.connection,
            action="attendance_manual_event_created",
            entity_type="clock_event",
            entity_id=row["id"],
            changed_fields=["employee_id", "event_type", "event_time", "method", "notes"],
            reason=request.note,
        )
        return _event(row)

    async def mappings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, query: MappingListQuery
    ) -> tuple[list[BiometricMappingResponse], str | None]:
        self._admin(principal)
        try:
            after_id = (
                None
                if self.cursor_codec is None
                else self.cursor_codec.decode(
                    principal=principal,
                    branch_id=branch_id,
                    operation_id="list_biometric_mappings",
                    query=query,
                    cursor=query.cursor,
                )
            )
            if query.cursor is not None and self.cursor_codec is None:
                raise ValueError
            after = (
                None
                if after_id is None
                else await self.repository.mapping_position(
                    principal.company_id, branch_id, after_id
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = list(
            await self.repository.mappings(principal.company_id, branch_id, after, query.limit + 1)
        )
        page_rows = rows[: query.limit]
        next_cursor = None
        if len(rows) > query.limit and page_rows:
            if self.cursor_codec is None:
                raise RuntimeError("cursor codec is unavailable")
            next_cursor = self.cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_biometric_mappings",
                query=query,
                last_id=page_rows[-1]["id"],
            )
        return [BiometricMappingResponse.model_validate(row) for row in page_rows], next_cursor

    async def replace_mapping(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        badge_no: str,
        request: BiometricMappingRequest,
    ) -> BiometricMappingResponse:
        self._admin(principal)
        badge = badge_no.strip()
        if not badge or len(badge) > 120:
            raise ServiceExecutionError("validation_failed")
        try:
            employee = await self.repository.employee(
                principal.company_id, branch_id, request.employee_id, lock=True
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not employee["active"] or employee["employment_status"] not in _ELIGIBLE:
            raise ServiceExecutionError("resource_not_found")
        row = await self.repository.replace_mapping(
            principal.company_id, branch_id, badge, request.employee_id, request.device_name
        )
        await append_audit_event(
            self.connection,
            action="biometric_mapping_replaced",
            entity_type="biometric_mapping",
            entity_id=row["id"],
            changed_fields=["badge_no", "employee_id", "device_name"],
            reason="Biometric mapping replaced",
        )
        return BiometricMappingResponse.model_validate(row)

    async def delete_mapping(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, badge_no: str
    ) -> None:
        self._admin(principal)
        row = await self.repository.mapping(principal.company_id, branch_id, badge_no, lock=True)
        if row is None:
            raise ServiceExecutionError("resource_not_found")
        await append_audit_event(
            self.connection,
            action="biometric_mapping_deleted",
            entity_type="biometric_mapping",
            entity_id=row["id"],
            changed_fields=["badge_no", "employee_id", "device_name"],
            reason="Biometric mapping deleted",
        )
        await self.repository.delete_mapping(principal.company_id, branch_id, badge_no)

    async def import_candidates(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: BiometricImportRequest,
    ) -> BiometricImportResponse:
        self._admin(principal)
        normalized = request.model_dump(mode="json", by_alias=True)
        fingerprint = _digest(normalized)
        await self.repository.lock_batch_fingerprint(
            f"{principal.company_id}:{branch_id}:{fingerprint}"
        )
        existing = await self.repository.batch_by_fingerprint(
            principal.company_id, branch_id, fingerprint
        )
        if existing is not None:
            saved = [
                ImportRowOutcome.model_validate(row)
                for row in await self.repository.batch_outcomes(
                    principal.company_id, branch_id, existing["id"]
                )
            ]
            return BiometricImportResponse(
                id=existing["id"],
                accepted_count=sum(item.outcome == "accepted" for item in saved),
                duplicate_count=sum(item.outcome == "duplicate" for item in saved),
                rejected_count=sum(item.outcome in {"invalid", "unknown_badge"} for item in saved),
                outcomes=saved,
            )
        batch = await self.repository.create_batch(
            principal.company_id,
            branch_id,
            principal.app_user_id,
            fingerprint,
            len(request.candidates),
            request.source_bytes,
        )
        business_date = await self.repository.business_date()
        outcomes: list[ImportRowOutcome] = []
        accepted = duplicates = rejected = 0
        ordered = sorted(
            enumerate(request.candidates, 1),
            key=lambda item: (
                item[1].event_time.astimezone(UTC),
                item[1].badge_no,
                item[1].event_type,
                item[0],
            ),
        )
        for row_number, candidate in ordered:
            event_type = candidate.event_type
            instant = candidate.event_time.astimezone(UTC)
            local = instant.astimezone(_DUBAI).date()
            if local < business_date - timedelta(days=31) or local > business_date + timedelta(
                days=1
            ):
                outcome = ImportRowOutcome(
                    row_number=row_number,
                    outcome="invalid",
                    reason_code="invalid_timestamp",
                    clock_event_id=None,
                )
            else:
                employee_id = await self.repository.badge_employee(
                    principal.company_id, branch_id, candidate.badge_no
                )
                if employee_id is None:
                    outcome = ImportRowOutcome(
                        row_number=row_number,
                        outcome="unknown_badge",
                        reason_code="unknown_badge",
                        clock_event_id=None,
                    )
                else:
                    fingerprint = _digest(
                        [
                            str(principal.company_id),
                            str(branch_id),
                            candidate.badge_no,
                            event_type,
                            instant.isoformat(timespec="milliseconds"),
                            candidate.device_name,
                        ]
                    )
                    if await self.repository.duplicate(
                        principal.company_id,
                        branch_id,
                        fingerprint,
                        employee_id,
                        event_type,
                        instant,
                    ):
                        outcome = ImportRowOutcome(
                            row_number=row_number,
                            outcome="duplicate",
                            reason_code="duplicate",
                            clock_event_id=None,
                        )
                    else:
                        event_id = await self.repository.biometric_event(
                            principal.company_id,
                            branch_id,
                            batch["id"],
                            row_number,
                            employee_id,
                            event_type,
                            instant,
                            candidate.badge_no,
                            candidate.device_name,
                            fingerprint,
                        )
                        outcome = (
                            ImportRowOutcome(
                                row_number=row_number,
                                outcome="accepted",
                                reason_code=None,
                                clock_event_id=event_id,
                            )
                            if event_id is not None
                            else ImportRowOutcome(
                                row_number=row_number,
                                outcome="duplicate",
                                reason_code="duplicate",
                                clock_event_id=None,
                            )
                        )
            await self.repository.outcome(
                principal.company_id,
                branch_id,
                batch["id"],
                outcome.row_number,
                outcome.outcome,
                outcome.reason_code,
                outcome.clock_event_id,
            )
            outcomes.append(outcome)
            accepted += outcome.outcome == "accepted"
            duplicates += outcome.outcome == "duplicate"
            rejected += outcome.outcome in {"invalid", "unknown_badge"}
        await append_audit_event(
            self.connection,
            action="attendance_biometric_batch_imported",
            entity_type="attendance_import_batch",
            entity_id=batch["id"],
            changed_fields=["row_count", "byte_count"],
            reason="Biometric attendance imported",
        )
        return BiometricImportResponse(
            id=batch["id"],
            accepted_count=accepted,
            duplicate_count=duplicates,
            rejected_count=rejected,
            outcomes=sorted(outcomes, key=lambda item: item.row_number),
        )

    async def authorize_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._admin(principal)
        if kind == "tenant" and resource_id is None:
            return
        if resource_id is None or not await self.repository.resource_exists(
            principal.company_id, branch_id, kind, resource_id
        ):
            raise ServiceExecutionError("resource_not_found")
