from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AccountStatus, AppRole
from app.services.execution import ServiceExecutionError
from app.services.notifications import NotificationListQuery, NotificationService

COMPANY_ID = uuid.UUID("b2000000-0000-4000-8000-000000000001")
BRANCH_ID = uuid.UUID("b2000000-0000-4000-8000-000000000002")
APP_USER_ID = uuid.UUID("b2000000-0000-4000-8000-000000000003")
NOTIFICATION_IDS = [uuid.UUID(int=index) for index in range(1, 4)]
NOW = datetime(2026, 9, 24, 8, tzinfo=UTC)
PRECISE_NOW = datetime(2026, 9, 24, 8, 0, 0, 123456, tzinfo=UTC)


def principal(role: AppRole) -> AuthorizationPrincipal:
    staff = role is not AppRole.ADMIN
    return AuthorizationPrincipal(
        app_user_id=APP_USER_ID,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=COMPANY_ID,
        employee_id=uuid.uuid4() if staff else None,
        branch_id=BRANCH_ID if staff else None,
    )


def row(index: int, read_at: datetime | None = None) -> dict[str, object]:
    return {
        "id": NOTIFICATION_IDS[index],
        "type": "leave_approved",
        "title": "Leave approved",
        "body": "Your leave request was approved.",
        "related_entity_type": "leave_request",
        "related_entity_id": str(uuid.UUID(int=100 + index)),
        "read_at": read_at,
        "created_at": NOW,
    }


class Cursor:
    def __init__(self, decoded: uuid.UUID | None = None) -> None:
        self.decoded = decoded
        self.encoded: uuid.UUID | None = None

    def decode(self, **_values: object) -> uuid.UUID | None:
        return self.decoded

    def encode(self, **values: object) -> str:
        self.encoded = values["last_id"]  # type: ignore[assignment]
        return "opaque-cursor"


class Repository:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []
        self.read_row: dict[str, object] | None = None

    async def list(self, **values: object) -> list[dict[str, object]]:
        self.calls.append(values)
        return self.rows

    async def snapshot(self, **values: object) -> dict[str, object]:
        self.calls.append(values)
        return {
            "as_of": NOW,
            "newest_created_at": NOW,
            "newest_read_at": None,
            "total": len(self.rows),
            "unread": len(self.rows),
        }

    async def read_one(self, **values: object) -> dict[str, object] | None:
        self.calls.append(values)
        return self.read_row

    async def read_all(self, **values: object) -> tuple[int, datetime]:
        self.calls.append(values)
        return 2, NOW


@pytest.mark.asyncio
async def test_list_has_exact_shape_cursor_order_and_role_partition() -> None:
    repository = Repository([row(0), row(1), row(2)])
    cursor = Cursor()
    service = NotificationService(repository, cursor)  # type: ignore[arg-type]

    response = await service.list(
        principal(AppRole.ADMIN), BRANCH_ID, NotificationListQuery(limit=2, cursor=None)
    )

    assert [item.id for item in response.items] == NOTIFICATION_IDS[:2]
    assert response.next_cursor == "opaque-cursor"
    assert response.as_of == NOW
    assert response.source_version.startswith("sha256:")
    assert cursor.encoded == NOTIFICATION_IDS[1]
    assert repository.calls[0]["include_tenant"] is True
    assert repository.calls[0]["limit"] == 3

    staff_repository = Repository([])
    staff_service = NotificationService(staff_repository, Cursor())  # type: ignore[arg-type]
    await staff_service.unread_count(principal(AppRole.MANAGER), BRANCH_ID)
    assert staff_repository.calls[0]["include_tenant"] is False


@pytest.mark.asyncio
async def test_invalid_or_stale_cursor_fails_closed() -> None:
    repository = Repository([])
    service = NotificationService(repository, Cursor(NOTIFICATION_IDS[0]))  # type: ignore[arg-type]
    with pytest.raises(ServiceExecutionError, match="invalid_cursor"):
        await service.list(
            principal(AppRole.EMPLOYEE),
            BRANCH_ID,
            NotificationListQuery(limit=30, cursor="opaque"),
        )


@pytest.mark.asyncio
async def test_read_one_is_scoped_and_read_all_reports_consistent_zero() -> None:
    repository = Repository([])
    repository.read_row = row(0, NOW)
    service = NotificationService(repository, Cursor())  # type: ignore[arg-type]
    actor = principal(AppRole.EMPLOYEE)

    updated = await service.read_one(actor, BRANCH_ID, NOTIFICATION_IDS[0])
    assert updated.read_at == NOW
    assert repository.calls[0]["recipient_id"] == APP_USER_ID

    all_read = await service.read_all(actor, BRANCH_ID)
    assert all_read.changed_count == 2
    assert all_read.unread_count == 0
    assert all_read.as_of == NOW

    repository.read_row = None
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await service.read_one(actor, BRANCH_ID, NOTIFICATION_IDS[1])


@pytest.mark.asyncio
async def test_replay_authorization_rejects_changed_partition() -> None:
    service = NotificationService(Repository([]), Cursor())  # type: ignore[arg-type]
    actor = principal(AppRole.EMPLOYEE)
    await service.authorize_replay(actor, BRANCH_ID, "notification_inbox", None)
    with pytest.raises(ServiceExecutionError, match="resource_not_found"):
        await service.authorize_replay(actor, uuid.uuid4(), "notification_inbox", None)


@pytest.mark.asyncio
async def test_notification_timestamps_serialize_to_contract_milliseconds() -> None:
    repository = Repository([row(0, PRECISE_NOW)])
    service = NotificationService(repository, Cursor())  # type: ignore[arg-type]
    response = await service.list(
        principal(AppRole.EMPLOYEE), BRANCH_ID, NotificationListQuery(limit=30, cursor=None)
    )
    response.as_of = PRECISE_NOW

    payload = response.model_dump(mode="json", by_alias=True)

    assert payload["asOf"] == "2026-09-24T08:00:00.123Z"
    assert payload["items"][0]["readAt"] == "2026-09-24T08:00:00.123Z"
