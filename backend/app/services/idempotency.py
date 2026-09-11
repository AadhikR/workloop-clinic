from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from app.auth.application_user import AuthorizationPrincipal
from app.http.idempotency_fingerprint import FINGERPRINT_VERSION
from app.repositories.idempotency import IdempotencyRepository
from app.services.execution import ServiceExecutionError

IdempotencyStatus = Literal["in_progress", "completed", "not_found"]


@dataclass(frozen=True, slots=True)
class IdempotencyCommand:
    key: uuid.UUID
    operation_id: str
    method: str
    route_parameters: dict[str, object]
    fingerprint: str
    branch_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class IdempotentResponse:
    status: int
    body: dict[str, object] | None
    location: str | None
    resource_kind: str
    resource_id: uuid.UUID | None
    replayed: bool = False


ReplayAuthorizer = Callable[[str, uuid.UUID | None], Awaitable[None]]
Mutation = Callable[[], Awaitable[IdempotentResponse]]


def advisory_lock_key(app_user_id: uuid.UUID, idempotency_key: uuid.UUID) -> int:
    material = b"\x00".join(
        (
            b"wlp-idem-lock-v1",
            str(app_user_id).encode("ascii"),
            str(idempotency_key).encode("ascii"),
        )
    )
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big", signed=True)


class IdempotencyCoordinator:
    def __init__(
        self,
        repository: IdempotencyRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self,
        *,
        principal: AuthorizationPrincipal,
        command: IdempotencyCommand,
        authorize_replay: ReplayAuthorizer,
        mutation: Mutation,
    ) -> IdempotentResponse:
        if not await self._repository.try_lock(
            advisory_lock_key(principal.app_user_id, command.key)
        ):
            raise ServiceExecutionError("idempotency_in_progress")

        await self._repository.cleanup_expired()

        existing = await self._repository.fetch(principal.app_user_id, command.key)
        if existing is not None:
            scope_matches = (
                existing["company_id"] == principal.company_id
                and existing["branch_id"] == command.branch_id
                and existing["operation_id"] == command.operation_id
                and existing["http_method"] == command.method
                and cast(dict[str, object], existing["route_parameters"])
                == command.route_parameters
            )
            if not scope_matches or existing["request_fingerprint"] != command.fingerprint:
                raise ServiceExecutionError("idempotency_conflict")
            if existing["fingerprint_version"] != FINGERPRINT_VERSION:
                raise RuntimeError("unsupported retained fingerprint version")
            await authorize_replay(
                cast(str, existing["replay_resource_kind"]),
                cast(uuid.UUID | None, existing["replay_resource_id"]),
            )
            return IdempotentResponse(
                status=cast(int, existing["response_status"]),
                body=cast(dict[str, object] | None, existing["response_body"]),
                location=cast(str | None, existing["response_location"]),
                resource_kind=cast(str, existing["replay_resource_kind"]),
                resource_id=cast(uuid.UUID | None, existing["replay_resource_id"]),
                replayed=True,
            )

        await self._repository.reserve(
            app_user_id=principal.app_user_id,
            key=command.key,
            company_id=principal.company_id,
            branch_id=command.branch_id,
            operation_id=command.operation_id,
            method=command.method,
            route_parameters=command.route_parameters,
            fingerprint_version=FINGERPRINT_VERSION,
            fingerprint=command.fingerprint,
        )
        response = await mutation()
        completed_at = self._clock()
        await self._repository.complete(
            app_user_id=principal.app_user_id,
            key=command.key,
            replay_resource_kind=response.resource_kind,
            replay_resource_id=response.resource_id,
            response_status=response.status,
            response_body=response.body,
            response_location=response.location,
            completed_at=completed_at,
            retain_until=completed_at + timedelta(days=7),
        )
        return response

    async def status(
        self, *, principal: AuthorizationPrincipal, key: uuid.UUID
    ) -> IdempotencyStatus:
        if not await self._repository.try_lock(advisory_lock_key(principal.app_user_id, key)):
            return "in_progress"
        await self._repository.cleanup_expired()
        record = await self._repository.fetch(principal.app_user_id, key)
        return "completed" if record is not None else "not_found"


@dataclass(frozen=True, slots=True)
class RecoveryKey:
    key_id: str
    key: bytes
    accept_until: datetime | None = None


class RecoveryNamespaces:
    def __init__(
        self,
        current: RecoveryKey,
        previous: Sequence[RecoveryKey] = (),
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._current = current
        self._previous = tuple(previous)
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _namespace(key: RecoveryKey, app_user_id: uuid.UUID) -> str:
        material = b"wlp-idem-recovery-v1\x00" + str(app_user_id).encode("ascii")
        digest = hmac.new(key.key, material, hashlib.sha256).digest()[:16]
        encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"rn1.{key.key_id}.{encoded}"

    def for_user(self, app_user_id: uuid.UUID) -> tuple[str, list[str]]:
        current = self._namespace(self._current, app_user_id)
        now = self._clock()
        accepted = [current]
        accepted.extend(
            self._namespace(key, app_user_id)
            for key in self._previous
            if key.accept_until is not None and key.accept_until > now
        )
        return current, accepted
