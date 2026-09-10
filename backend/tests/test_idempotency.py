import uuid
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.auth.application_user import AuthorizationPrincipal
from app.http.idempotency_fingerprint import ABSENT, request_fingerprint
from app.models.identity import AccountStatus, AppRole
from app.services.execution import ServiceExecutionError
from app.services.idempotency import (
    IdempotencyCommand,
    IdempotencyCoordinator,
    IdempotentResponse,
    RecoveryKey,
    RecoveryNamespaces,
)

APP_USER_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
COMPANY_ID = uuid.UUID("3afbf0a0-9642-4d44-9884-e9654983eb9b")
KEY = uuid.UUID("11111111-1111-4111-8111-111111111111")
BRANCH_ID = uuid.UUID("de0fb0c1-2d7a-438a-b19a-98e5bc3698c2")
NOW = datetime(2026, 9, 10, tzinfo=UTC)


def principal() -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=APP_USER_ID,
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=COMPANY_ID,
        employee_id=None,
        branch_id=None,
    )


def command(fingerprint: str = "a" * 64) -> IdempotencyCommand:
    return IdempotencyCommand(
        key=KEY,
        operation_id="create_branch",
        method="POST",
        route_parameters={},
        fingerprint=fingerprint,
    )


class MemoryRepository:
    def __init__(self) -> None:
        self.locked = True
        self.record: dict[str, object] | None = None
        self.completions = 0
        self.cleanups = 0

    async def try_lock(self, _lock_key: int) -> bool:
        return self.locked

    async def fetch(self, _app_user_id: uuid.UUID, _key: uuid.UUID) -> Any:
        return self.record

    async def cleanup_expired(self) -> None:
        self.cleanups += 1

    async def reserve(self, **values: object) -> None:
        self.record = {
            "app_user_id": values["app_user_id"],
            "idempotency_key": values["key"],
            "company_id": values["company_id"],
            "branch_id": values["branch_id"],
            "operation_id": values["operation_id"],
            "http_method": values["method"],
            "route_parameters": values["route_parameters"],
            "fingerprint_version": values["fingerprint_version"],
            "request_fingerprint": values["fingerprint"],
        }

    async def complete(self, **values: object) -> None:
        assert self.record is not None
        self.record.update(values)
        self.record["response_location"] = values["response_location"]
        self.completions += 1


@pytest.mark.asyncio
async def test_idempotency_first_commit_and_identical_replay() -> None:
    repository = MemoryRepository()
    coordinator = IdempotencyCoordinator(cast(Any, repository), clock=lambda: NOW)
    mutations = 0
    replay_authorizations = 0

    async def mutate() -> IdempotentResponse:
        nonlocal mutations
        mutations += 1
        return IdempotentResponse(
            status=201,
            body={"data": {"id": str(BRANCH_ID)}},
            location=f"/api/v1/branches/{BRANCH_ID}",
            resource_kind="branch",
            resource_id=BRANCH_ID,
        )

    async def authorize(kind: str, resource_id: uuid.UUID | None) -> None:
        nonlocal replay_authorizations
        replay_authorizations += 1
        assert (kind, resource_id) == ("branch", BRANCH_ID)

    first = await coordinator.execute(
        principal=principal(), command=command(), authorize_replay=authorize, mutation=mutate
    )
    replay = await coordinator.execute(
        principal=principal(), command=command(), authorize_replay=authorize, mutation=mutate
    )

    assert first.replayed is False
    assert replay.replayed is True
    assert replay.body == first.body
    assert replay.location == first.location
    assert mutations == repository.completions == replay_authorizations == 1
    assert repository.cleanups == 2


@pytest.mark.asyncio
async def test_idempotency_rejects_mismatch_and_reports_in_progress() -> None:
    repository = MemoryRepository()
    coordinator = IdempotencyCoordinator(cast(Any, repository), clock=lambda: NOW)

    async def mutate() -> IdempotentResponse:
        return IdempotentResponse(201, {}, None, "branch", BRANCH_ID)

    async def authorize(_kind: str, _resource_id: uuid.UUID | None) -> None:
        return None

    await coordinator.execute(
        principal=principal(), command=command(), authorize_replay=authorize, mutation=mutate
    )
    with pytest.raises(ServiceExecutionError, match="idempotency_conflict"):
        await coordinator.execute(
            principal=principal(),
            command=command("b" * 64),
            authorize_replay=authorize,
            mutation=mutate,
        )

    repository.locked = False
    with pytest.raises(ServiceExecutionError, match="idempotency_in_progress"):
        await coordinator.execute(
            principal=principal(), command=command(), authorize_replay=authorize, mutation=mutate
        )
    assert await coordinator.status(principal=principal(), key=KEY) == "in_progress"


def test_fingerprint_preserves_absent_null_and_normalizes_unicode() -> None:
    def fingerprint_body(body: dict[str, object]) -> str:
        return request_fingerprint(
            operation_id="create_branch",
            method="POST",
            route_parameters={},
            effective_query_parameters={},
            body=body,
        )

    absent = fingerprint_body({"name": "Du\u0301bai", "value": ABSENT})
    normalized = fingerprint_body({"name": "D\u00fabai", "value": ABSENT})
    explicit_null = fingerprint_body({"name": "D\u00fabai", "value": None})

    assert absent == normalized
    assert absent != explicit_null
    assert len(absent) == 64


def test_recovery_namespaces_are_user_bound_and_rotate_for_a_bounded_window() -> None:
    namespaces = RecoveryNamespaces(
        RecoveryKey("1234abcd", b"1" * 32),
        [RecoveryKey("8765dcba", b"2" * 32, NOW.replace(day=11))],
        clock=lambda: NOW,
    )
    current, accepted = namespaces.for_user(APP_USER_ID)

    assert current == accepted[0]
    assert len(accepted) == 2
    assert all(value.startswith("rn1.") and len(value) == 35 for value in accepted)
    assert namespaces.for_user(uuid.uuid4())[0] != current
