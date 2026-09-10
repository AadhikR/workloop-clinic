from __future__ import annotations

import base64
import binascii
import hashlib
import json
import secrets
import unicodedata
import uuid
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.organization import OrganizationRepository
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.organization import (
    BranchAdminResponse,
    BranchCreateRequest,
    BranchSafeResponse,
    BranchUpdateRequest,
    CompanyAdminResponse,
    CompanyUpdateRequest,
    SafeEmployerResponse,
)
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class BranchListQuery:
    limit: int
    search: str | None
    sort: tuple[tuple[str, bool], ...]
    cursor: str | None


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= 100:
        raise ValueError("invalid search")
    return normalized


def _cursor_context(query: BranchListQuery) -> str:
    context = {
        "search": query.search,
        "sort": [[field, descending] for field, descending in query.sort],
    }
    encoded = json.dumps(context, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(encoded).digest()).decode("ascii").rstrip("=")


class BranchCursorCodec:
    def __init__(
        self,
        key: bytes,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if len(key) != 32:
            raise ValueError("cursor key must contain 32 bytes")
        self._cipher = AESGCM(key)
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_base64url(cls, value: str) -> BranchCursorCodec:
        try:
            key = base64.b64decode(
                value + "=" * (-len(value) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (ValueError, binascii.Error):
            raise ValueError("invalid cursor key") from None
        return cls(key)

    def encode(
        self,
        principal: AuthorizationPrincipal,
        query: BranchListQuery,
        row: RowMapping,
    ) -> str:
        payload = {
            "appUserId": str(principal.app_user_id),
            "branchId": None if principal.branch_id is None else str(principal.branch_id),
            "companyId": str(principal.company_id),
            "context": _cursor_context(query),
            "expiresAt": int((self._clock() + timedelta(minutes=15)).timestamp()),
            "lastId": str(row["id"]),
            "operationId": "list_branches",
            "role": principal.role.value,
            "version": 1,
        }
        plaintext = zlib.compress(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
            level=9,
        )
        nonce = secrets.token_bytes(12)
        encrypted = self._cipher.encrypt(nonce, plaintext, b"workloop:list_branches:v1")
        cursor = base64.urlsafe_b64encode(b"\x01" + nonce + encrypted).decode("ascii").rstrip("=")
        if len(cursor) > 512:
            raise RuntimeError("cursor exceeds the contract limit")
        return cursor

    def decode(
        self,
        principal: AuthorizationPrincipal,
        query: BranchListQuery,
    ) -> uuid.UUID | None:
        if query.cursor is None:
            return None
        try:
            raw = base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4),
                altchars=b"-_",
                validate=True,
            )
            if len(raw) < 30 or raw[0] != 1:
                raise ValueError("invalid cursor")
            plaintext = self._cipher.decrypt(raw[1:13], raw[13:], b"workloop:list_branches:v1")
            value = cast(dict[str, Any], json.loads(zlib.decompress(plaintext).decode("utf-8")))
        except (
            InvalidTag,
            UnicodeError,
            ValueError,
            binascii.Error,
            json.JSONDecodeError,
            zlib.error,
        ):
            raise ValueError("invalid cursor") from None
        if set(value) != {
            "appUserId",
            "branchId",
            "companyId",
            "context",
            "expiresAt",
            "lastId",
            "operationId",
            "role",
            "version",
        }:
            raise ValueError("invalid cursor")
        expected_branch = None if principal.branch_id is None else str(principal.branch_id)
        expires_at = value.get("expiresAt")
        last_id = value.get("lastId")
        if (
            value.get("version") != 1
            or value.get("operationId") != "list_branches"
            or value.get("role") != principal.role.value
            or value.get("appUserId") != str(principal.app_user_id)
            or value.get("companyId") != str(principal.company_id)
            or value.get("branchId") != expected_branch
            or value.get("context") != _cursor_context(query)
            or not isinstance(expires_at, int)
            or isinstance(expires_at, bool)
            or expires_at <= int(self._clock().timestamp())
            or not isinstance(last_id, str)
        ):
            raise ValueError("invalid cursor")
        try:
            return uuid.UUID(last_id)
        except ValueError:
            raise ValueError("invalid cursor") from None


def _work_location(value: object) -> Literal["mainland", "free_zone"]:
    if value == "Mainland":
        return "mainland"
    if value == "Free Zone":
        return "free_zone"
    raise RuntimeError("invalid stored work location")


def _company(row: RowMapping) -> CompanyAdminResponse:
    return CompanyAdminResponse(
        id=row["id"],
        name=row["name"],
        sector=row["sector"],
        nafis_quota_percent=f"{row['nafis_quota_percent']:.2f}",
        enable_nafis=row["enable_nafis"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _safe_branch(row: RowMapping) -> BranchSafeResponse:
    return BranchSafeResponse(
        id=row["id"],
        name=row["name"],
        address=row["address"],
        contact_email=row["contact_email"],
        work_location_type=_work_location(row["work_location_type"]),
        free_zone_name=row["free_zone_name"],
        logo_url=row["logo_url"],
    )


def _admin_branch(row: RowMapping) -> BranchAdminResponse:
    return BranchAdminResponse(
        id=row["id"],
        name=row["name"],
        mol_employer_id=row["mol_employer_id"],
        default_bank_routing_code=row["default_bank_routing_code"],
        address=row["address"],
        contact_email=row["contact_email"],
        default_salary_day=row["default_salary_day"],
        work_location_type=_work_location(row["work_location_type"]),
        free_zone_name=row["free_zone_name"],
        logo_url=row["logo_url"],
        enable_staffing_rules=row["enable_staffing_rules"],
        enable_biometric_import=row["enable_biometric_import"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class OrganizationService:
    def __init__(self, connection: AsyncConnection, cursor_codec: BranchCursorCodec) -> None:
        self._repository = OrganizationRepository(connection)
        self._cursor_codec = cursor_codec

    async def get_company(self, principal: AuthorizationPrincipal) -> CompanyAdminResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            return _company(await self._repository.fetch_company(principal.company_id))
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_company(
        self, principal: AuthorizationPrincipal, request: CompanyUpdateRequest
    ) -> CompanyAdminResponse:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.update_company(
                company_id=principal.company_id,
                expected_updated_at=request.expected_updated_at,
                changes=request.changes(),
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        return _company(row)

    async def get_employer(self, principal: AuthorizationPrincipal) -> SafeEmployerResponse:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.branch_id is None
            or principal.employee_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.fetch_employer(principal.company_id, principal.branch_id)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        return SafeEmployerResponse(
            company_name=row["company_name"],
            branch_name=row["branch_name"],
            branch_contact_email=row["branch_contact_email"],
            branch_address=row["branch_address"],
            work_location_type=_work_location(row["work_location_type"]),
            free_zone_name=row["free_zone_name"],
            logo_url=row["logo_url"],
        )

    async def list_branches(
        self, principal: AuthorizationPrincipal, query: BranchListQuery
    ) -> tuple[list[BranchAdminResponse | BranchSafeResponse], str | None]:
        if principal.role not in {AppRole.ADMIN, AppRole.MANAGER, AppRole.EMPLOYEE}:
            raise ServiceExecutionError("operation_not_permitted")
        if principal.role is not AppRole.ADMIN and principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            after_id = self._cursor_codec.decode(principal, query)
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None
        after = None
        if after_id is not None:
            try:
                after = await self._repository.fetch_branch_position(
                    company_id=principal.company_id,
                    branch_id=None if principal.role is AppRole.ADMIN else principal.branch_id,
                    cursor_branch_id=after_id,
                    sort=query.sort,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_branches(
            company_id=principal.company_id,
            branch_id=None if principal.role is AppRole.ADMIN else principal.branch_id,
            admin_projection=principal.role is AppRole.ADMIN,
            search=query.search,
            sort=query.sort,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible_rows = rows[: query.limit]
        if principal.role is AppRole.ADMIN:
            items: list[BranchAdminResponse | BranchSafeResponse] = [
                _admin_branch(row) for row in visible_rows
            ]
        else:
            items = [_safe_branch(row) for row in visible_rows]
        next_cursor = (
            self._cursor_codec.encode(principal, query, visible_rows[-1]) if has_more else None
        )
        return items, next_cursor

    async def get_branch(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> BranchAdminResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            return _admin_branch(
                await self._repository.fetch_branch(principal.company_id, branch_id)
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def create_branch(
        self, principal: AuthorizationPrincipal, request: BranchCreateRequest
    ) -> BranchAdminResponse:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.create_branch(
                company_id=principal.company_id,
                values=request.values(),
            )
            await self._repository.append_branch_audit("branch_created", row["id"])
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None
        return _admin_branch(row)

    async def authorize_branch_replay(
        self, principal: AuthorizationPrincipal, kind: str, resource_id: uuid.UUID | None
    ) -> None:
        if (
            principal.role is not AppRole.ADMIN
            or principal.branch_id is not None
            or kind != "branch"
            or resource_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            await self._repository.fetch_branch(principal.company_id, resource_id)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_branch(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: BranchUpdateRequest,
    ) -> BranchAdminResponse:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.update_branch(
                company_id=principal.company_id,
                branch_id=branch_id,
                expected_updated_at=request.expected_updated_at,
                changes=request.changes(),
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None
        return _admin_branch(row)

    async def delete_branch(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> None:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            await self._repository.delete_branch(
                company_id=principal.company_id,
                branch_id=branch_id,
                expected_updated_at=expected_updated_at,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None
