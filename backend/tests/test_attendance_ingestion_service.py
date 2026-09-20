from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.schemas.attendance_ingestion import (
    BiometricCandidate,
    BiometricImportRequest,
    BiometricMappingRequest,
    ManualClockEventRequest,
)
from app.services.attendance_ingestion import AttendanceIngestionService, EventListQuery
from app.services.execution import ServiceExecutionError

COMPANY_ID = uuid.UUID("10000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
ADMIN_ID = uuid.UUID("30000000-0000-4000-8000-000000000001")
EMPLOYEE_ID = uuid.UUID("40000000-0000-4000-8000-000000000001")
EVENT_ID = uuid.UUID("50000000-0000-4000-8000-000000000001")
BATCH_ID = uuid.UUID("60000000-0000-4000-8000-000000000001")
MAPPING_ID = uuid.UUID("70000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 8, 27, 8, tzinfo=UTC)


def principal(
    role: AppRole = AppRole.ADMIN,
    *,
    employee_id: uuid.UUID | None = None,
    branch_id: uuid.UUID | None = None,
) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=ADMIN_ID,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=employee_id,
        branch_id=branch_id,
    )


class FakeRepository:
    def __init__(self) -> None:
        self.employee_row: dict[str, object] = {
            "id": EMPLOYEE_ID,
            "active": True,
            "employment_status": "Active",
        }
        self.badges: dict[str, uuid.UUID] = {"A-1": EMPLOYEE_ID}
        self.duplicates: set[str] = set()
        self.manual_duplicate = False
        self.created_events: list[dict[str, object]] = []
        self.outcomes: list[tuple[int, str, str | None, uuid.UUID | None]] = []
        self.mapping_row: dict[str, object] = {
            "id": MAPPING_ID,
            "badge_no": "A-1",
            "employee_id": EMPLOYEE_ID,
            "device_name": "Front door",
            "created_at": NOW,
        }

    async def business_date(self) -> date:
        return date(2026, 8, 27)

    async def employee(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        return self.employee_row

    async def create_manual(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        _actor_id: uuid.UUID,
        values: dict[str, object],
    ) -> dict[str, object]:
        return {
            "id": EVENT_ID,
            **values,
            "method": "MANUAL",
            "created_at": NOW,
        }

    async def minute_duplicate(self, *_args: object) -> bool:
        return self.manual_duplicate

    async def events(self, *_args: object) -> list[dict[str, object]]:
        return [
            {
                "id": EVENT_ID,
                "employee_id": EMPLOYEE_ID,
                "event_type": "CLOCK_IN",
                "event_time": NOW,
                "method": "MANUAL",
                "notes": "Reception correction",
                "created_at": NOW,
            }
        ]

    async def mappings(self, *_args: object) -> list[dict[str, object]]:
        return [self.mapping_row]

    async def mapping(self, *_args: object, **_kwargs: object) -> dict[str, object] | None:
        return self.mapping_row

    async def replace_mapping(self, *_args: object) -> dict[str, object]:
        return self.mapping_row

    async def delete_mapping(self, *_args: object) -> None:
        self.mapping_row = {}

    async def create_batch(self, *_args: object) -> dict[str, object]:
        return {"id": BATCH_ID}

    async def lock_batch_fingerprint(self, *_args: object) -> None:
        return None

    async def batch_by_fingerprint(self, *_args: object) -> None:
        return None

    async def badge_employee(self, *_args: object) -> uuid.UUID | None:
        return self.badges.get(cast(str, _args[-1]))

    async def duplicate(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        fingerprint: str,
        _employee_id: uuid.UUID,
        _event_type: str,
        _event_time: datetime,
    ) -> bool:
        return fingerprint in self.duplicates

    async def biometric_event(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        _batch_id: uuid.UUID,
        row_number: int,
        employee_id: uuid.UUID,
        event_type: str,
        event_time: datetime,
        badge_no: str,
        device_name: str,
        fingerprint: str,
    ) -> uuid.UUID:
        self.created_events.append(
            {
                "row_number": row_number,
                "employee_id": employee_id,
                "event_type": event_type,
                "event_time": event_time,
                "badge_no": badge_no,
                "device_name": device_name,
                "fingerprint": fingerprint,
            }
        )
        return uuid.UUID(int=EVENT_ID.int + row_number)

    async def outcome(
        self,
        _company_id: uuid.UUID,
        _branch_id: uuid.UUID,
        _batch_id: uuid.UUID,
        row_number: int,
        outcome: str,
        reason: str | None,
        event_id: uuid.UUID | None,
    ) -> None:
        self.outcomes.append((row_number, outcome, reason, event_id))


def service(repository: FakeRepository) -> AttendanceIngestionService:
    value = AttendanceIngestionService(cast(Any, object()))
    value.repository = cast(Any, repository)
    return value


def manual_request(event_time: str, note: str = "Reception correction") -> ManualClockEventRequest:
    return ManualClockEventRequest.model_validate(
        {
            "employeeId": str(EMPLOYEE_ID),
            "eventType": "CLOCK_IN",
            "eventTime": event_time,
            "note": note,
        }
    )


def mapping_request() -> BiometricMappingRequest:
    return BiometricMappingRequest.model_validate(
        {"employeeId": str(EMPLOYEE_ID), "deviceName": "Front door"}
    )


def candidate(badge_no: str, event_type: str, event_time: str) -> BiometricCandidate:
    return BiometricCandidate.model_validate(
        {
            "badgeNo": badge_no,
            "eventType": event_type,
            "eventTime": event_time,
            "deviceName": "Front door",
        }
    )


@pytest.fixture(autouse=True)
def audit_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    async def append(*_args: object, **_kwargs: object) -> uuid.UUID:
        return uuid.uuid4()

    monkeypatch.setattr("app.services.attendance_ingestion.append_audit_event", append)


@pytest.mark.asyncio
async def test_manual_event_uses_trusted_actor_and_utc_instant() -> None:
    repository = FakeRepository()
    item = await service(repository).manual(
        principal(),
        BRANCH_ID,
        manual_request("2026-08-27T12:00:00+04:00"),
    )
    assert item.id == EVENT_ID
    assert item.method == "MANUAL"
    assert item.event_time == NOW


@pytest.mark.asyncio
async def test_manual_event_rejects_out_of_window_and_ineligible_employee() -> None:
    repository = FakeRepository()
    ingestion = service(repository)
    request = manual_request("2026-06-01T12:00:00+04:00", "Old correction")
    with pytest.raises(ServiceExecutionError, match="validation_failed"):
        await ingestion.manual(principal(), BRANCH_ID, request)
    repository.employee_row["active"] = False
    request.event_time = NOW
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await ingestion.manual(principal(), BRANCH_ID, request)
    repository.employee_row["active"] = True
    repository.manual_duplicate = True
    with pytest.raises(ServiceExecutionError, match="clock_event_conflict"):
        await ingestion.manual(principal(), BRANCH_ID, manual_request("2026-08-27T12:00:20+04:00"))


@pytest.mark.asyncio
async def test_employee_projection_is_for_self_only() -> None:
    repository = FakeRepository()
    staff = principal(AppRole.EMPLOYEE, employee_id=EMPLOYEE_ID, branch_id=BRANCH_ID)
    items, cursor = await service(repository).self_events(
        staff, EventListQuery(50, None, None, None, None)
    )
    assert [item.employee_id for item in items] == [EMPLOYEE_ID]
    assert cursor is None
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await service(repository).self_events(
            principal(AppRole.EMPLOYEE), EventListQuery(50, None, None, None, None)
        )


@pytest.mark.asyncio
async def test_mapping_replace_and_delete_require_admin() -> None:
    repository = FakeRepository()
    ingestion = service(repository)
    request = mapping_request()
    item = await ingestion.replace_mapping(principal(), BRANCH_ID, " A-1 ", request)
    assert item.badge_no == "A-1"
    await ingestion.delete_mapping(principal(), BRANCH_ID, "A-1")
    assert repository.mapping_row == {}
    with pytest.raises(ServiceExecutionError, match="operation_not_permitted"):
        await ingestion.replace_mapping(
            principal(AppRole.EMPLOYEE, employee_id=EMPLOYEE_ID, branch_id=BRANCH_ID),
            BRANCH_ID,
            "A-1",
            request,
        )


@pytest.mark.asyncio
async def test_import_orders_rows_and_retains_partial_outcomes() -> None:
    repository = FakeRepository()
    request = BiometricImportRequest.model_validate(
        {
            "sourceBytes": 240,
            "candidates": [
                candidate("UNKNOWN", "CLOCK_OUT", "2026-08-27T17:00:00+04:00"),
                candidate("A-1", "CLOCK_IN", "2026-08-27T08:00:00+04:00"),
            ],
        }
    )
    result = await service(repository).import_candidates(principal(), BRANCH_ID, request)
    assert result.accepted_count == 1
    assert result.rejected_count == 1
    assert [event["row_number"] for event in repository.created_events] == [2]
    assert [outcome.outcome for outcome in result.outcomes] == ["unknown_badge", "accepted"]
    assert len(cast(str, repository.created_events[0]["fingerprint"])) == 64


def test_import_schema_rejects_naive_instants_formulas_and_oversized_batches() -> None:
    with pytest.raises(ValidationError):
        candidate("=A1", "CLOCK_IN", "2026-08-27T08:00:00")
    with pytest.raises(ValidationError):
        BiometricImportRequest.model_validate({"sourceBytes": 2_097_153, "candidates": []})
