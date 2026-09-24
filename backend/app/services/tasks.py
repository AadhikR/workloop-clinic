from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import secrets
import uuid
import zlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, Protocol, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.schemas.tasks import TaskCategory, TaskItem, TaskListResponse, TaskNavigation, TaskUrgency
from app.services.execution import ServiceExecutionError

logger = logging.getLogger(__name__)

UrgencyRule = Literal["action", "info", "urgent", "warning", "expiry"]

URGENCY_RANK: dict[TaskUrgency, int] = {
    "action": 0,
    "expired": 1,
    "urgent": 2,
    "warning": 3,
    "info": 4,
}


@dataclass(frozen=True, slots=True)
class TaskCategorySpec:
    code: str
    label: str
    roles: frozenset[AppRole]
    entity: str
    navigation: str
    urgency_rule: UrgencyRule
    order: int
    id_prefix: str


def _roles(*roles: AppRole) -> frozenset[AppRole]:
    return frozenset(roles)


TASK_CATEGORY_REGISTRY: tuple[TaskCategorySpec, ...] = (
    TaskCategorySpec(
        "leaveApprovals",
        "Leave requests",
        _roles(AppRole.ADMIN, AppRole.MANAGER),
        "leaveRequest",
        "leaveApprovals",
        "action",
        10,
        "leaveApproval",
    ),
    TaskCategorySpec(
        "expenseApprovals",
        "Expense claims",
        _roles(AppRole.ADMIN, AppRole.MANAGER),
        "expenseClaim",
        "expenses",
        "action",
        20,
        "expenseApproval",
    ),
    TaskCategorySpec(
        "advanceApprovals",
        "Salary advances",
        _roles(AppRole.ADMIN),
        "salaryAdvance",
        "advances",
        "action",
        30,
        "advanceApproval",
    ),
    TaskCategorySpec(
        "letterRequests",
        "Letter requests",
        _roles(AppRole.ADMIN),
        "letterRequest",
        "letterRequests",
        "action",
        40,
        "letterRequest",
    ),
    TaskCategorySpec(
        "documentVerification",
        "Document verification",
        _roles(AppRole.ADMIN),
        "employeeDocument",
        "recordsBenefits",
        "action",
        50,
        "documentVerification",
    ),
    TaskCategorySpec(
        "certificationReview",
        "Certification review",
        _roles(AppRole.ADMIN),
        "certification",
        "developmentAssets",
        "action",
        60,
        "certificationReview",
    ),
    TaskCategorySpec(
        "regularisationRequests",
        "Regularisation requests",
        _roles(AppRole.ADMIN),
        "regularisationRequest",
        "attendanceExceptions",
        "action",
        70,
        "regularisation",
    ),
    TaskCategorySpec(
        "shiftSwapRequests",
        "Shift swap requests",
        _roles(AppRole.ADMIN),
        "shiftSwapRequest",
        "shiftSwaps",
        "action",
        80,
        "shiftSwap",
    ),
    TaskCategorySpec(
        "payrollApproval",
        "Payroll approval",
        _roles(AppRole.ADMIN),
        "payrollRun",
        "payroll",
        "action",
        90,
        "payrollApproval",
    ),
    TaskCategorySpec(
        "documentExpiry",
        "Document expiry",
        _roles(AppRole.ADMIN, AppRole.EMPLOYEE),
        "employee",
        "recordsBenefits",
        "expiry",
        100,
        "documentExpiry",
    ),
    TaskCategorySpec(
        "certificationExpiry",
        "Certification expiry",
        _roles(AppRole.ADMIN, AppRole.EMPLOYEE),
        "certification",
        "developmentAssets",
        "expiry",
        110,
        "certificationExpiry",
    ),
    TaskCategorySpec(
        "probationEnding",
        "Probation ending",
        _roles(AppRole.ADMIN),
        "employee",
        "employees",
        "warning",
        120,
        "probationEnding",
    ),
    TaskCategorySpec(
        "contractExpiry",
        "Contract expiry",
        _roles(AppRole.ADMIN),
        "employmentContract",
        "recordsBenefits",
        "expiry",
        130,
        "contractExpiry",
    ),
    TaskCategorySpec(
        "offboardingInProgress",
        "Offboarding in progress",
        _roles(AppRole.ADMIN),
        "offboardingChecklist",
        "offboarding",
        "warning",
        140,
        "offboarding",
    ),
    TaskCategorySpec(
        "appraisalCalibration",
        "Appraisals awaiting calibration",
        _roles(AppRole.ADMIN),
        "appraisal",
        "appraisals",
        "action",
        150,
        "appraisalCalibration",
    ),
    TaskCategorySpec(
        "teamAppraisals",
        "Team appraisals",
        _roles(AppRole.MANAGER),
        "appraisal",
        "appraisals",
        "action",
        160,
        "teamAppraisal",
    ),
    TaskCategorySpec(
        "teamCertificationExpiry",
        "Team certification expiry",
        _roles(AppRole.MANAGER),
        "certification",
        "developmentAssets",
        "expiry",
        170,
        "teamCertificationExpiry",
    ),
    TaskCategorySpec(
        "rejectedCertifications",
        "Rejected certifications",
        _roles(AppRole.EMPLOYEE),
        "certification",
        "developmentAssets",
        "urgent",
        180,
        "rejectedCertification",
    ),
    TaskCategorySpec(
        "rejectedDocuments",
        "Rejected documents",
        _roles(AppRole.EMPLOYEE),
        "employeeDocument",
        "recordsBenefits",
        "urgent",
        190,
        "rejectedDocument",
    ),
    TaskCategorySpec(
        "missingClockOuts",
        "Missing clock-out",
        _roles(AppRole.EMPLOYEE),
        "attendanceRecord",
        "personalAttendance",
        "urgent",
        200,
        "missingClockOut",
    ),
    TaskCategorySpec(
        "pendingLeave",
        "Pending leave",
        _roles(AppRole.EMPLOYEE),
        "leaveRequest",
        "leave",
        "info",
        210,
        "pendingLeave",
    ),
    TaskCategorySpec(
        "pendingAdvances",
        "Pending advances",
        _roles(AppRole.EMPLOYEE),
        "salaryAdvance",
        "advances",
        "info",
        220,
        "pendingAdvance",
    ),
    TaskCategorySpec(
        "pendingExpenses",
        "Pending expenses",
        _roles(AppRole.EMPLOYEE),
        "expenseClaim",
        "expenses",
        "info",
        230,
        "pendingExpense",
    ),
    TaskCategorySpec(
        "pendingLetters",
        "Pending letters",
        _roles(AppRole.EMPLOYEE),
        "letterRequest",
        "letterRequests",
        "info",
        240,
        "pendingLetter",
    ),
)


@dataclass(frozen=True, slots=True)
class TaskListQuery:
    category: str | None
    urgency: TaskUrgency | None
    limit: int
    cursor: str | None


class TaskRepository(Protocol):
    async def snapshot(self) -> dict[str, object]: ...

    async def read_category(
        self,
        *,
        code: str,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        business_date: date,
    ) -> list[dict[str, object]]: ...


class TaskCursor(Protocol):
    def encode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TaskListQuery,
        last_id: str,
    ) -> str: ...

    def decode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TaskListQuery,
    ) -> str | None: ...


class TaskCursorCodec:
    def __init__(self, key: bytes, *, clock: Any | None = None) -> None:
        if len(key) != 32:
            raise ValueError("cursor key must contain 32 bytes")
        self._cipher = AESGCM(key)
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_base64url(cls, value: str) -> TaskCursorCodec:
        try:
            key = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("invalid cursor key") from None
        return cls(key)

    @staticmethod
    def _context(query: TaskListQuery) -> dict[str, object]:
        return {"category": query.category, "limit": query.limit, "urgency": query.urgency}

    def encode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TaskListQuery,
        last_id: str,
    ) -> str:
        payload = {
            "appUserId": str(principal.app_user_id),
            "branchId": str(branch_id),
            "companyId": str(principal.company_id),
            "context": self._context(query),
            "expiresAt": int((self._clock() + timedelta(minutes=15)).timestamp()),
            "lastId": last_id,
            "operationId": "list_tasks",
            "role": principal.role.value,
            "version": 1,
        }
        plaintext = zlib.compress(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(), level=9
        )
        nonce = secrets.token_bytes(12)
        encrypted = self._cipher.encrypt(nonce, plaintext, b"workloop:list_tasks:v1")
        cursor = base64.urlsafe_b64encode(b"\x01" + nonce + encrypted).decode().rstrip("=")
        if len(cursor) > 512:
            raise RuntimeError("cursor exceeds the contract limit")
        return cursor

    def decode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TaskListQuery,
    ) -> str | None:
        if query.cursor is None:
            return None
        try:
            raw = base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
            if len(raw) < 30 or raw[0] != 1:
                raise ValueError("invalid cursor")
            value = cast(
                dict[str, Any],
                json.loads(
                    zlib.decompress(
                        self._cipher.decrypt(raw[1:13], raw[13:], b"workloop:list_tasks:v1")
                    ).decode()
                ),
            )
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
        if (
            value.get("version") != 1
            or value.get("operationId") != "list_tasks"
            or value.get("role") != principal.role.value
            or value.get("appUserId") != str(principal.app_user_id)
            or value.get("companyId") != str(principal.company_id)
            or value.get("branchId") != str(branch_id)
            or value.get("context") != self._context(query)
            or not isinstance(value.get("expiresAt"), int)
            or cast(int, value["expiresAt"]) <= int(self._clock().timestamp())
            or not isinstance(value.get("lastId"), str)
        ):
            raise ValueError("invalid cursor")
        return cast(str, value["lastId"])


def _urgency(rule: UrgencyRule, due_date: date | None, business_date: date) -> TaskUrgency:
    if rule != "expiry":
        return cast(TaskUrgency, rule)
    if due_date is None or due_date <= business_date:
        return "expired"
    remaining = (due_date - business_date).days
    if remaining <= 14:
        return "urgent"
    if remaining <= 30:
        return "warning"
    return "info"


def _task_item(spec: TaskCategorySpec, row: dict[str, object], business_date: date) -> TaskItem:
    entity_id = cast(uuid.UUID, row["entity_id"])
    suffix = str(row.get("task_key") or "")
    task_id = f"{spec.id_prefix}:{entity_id}" + (f":{suffix}" if suffix else "")
    due_date = cast(date | None, row.get("due_date"))
    return TaskItem(
        id=task_id,
        entity=spec.entity,
        entity_id=entity_id,
        title=str(row["title"]),
        subtitle=str(row["subtitle"]),
        urgency=_urgency(spec.urgency_rule, due_date, business_date),
        due_date=due_date,
        created_at=cast(datetime | None, row.get("created_at")),
        navigation=TaskNavigation(screen=spec.navigation),
    )


def _sort_key(item: TaskItem, order: int) -> tuple[object, ...]:
    return (
        order,
        URGENCY_RANK[item.urgency],
        item.due_date is None,
        item.due_date or date.max,
        item.created_at is None,
        item.created_at or datetime.max.replace(tzinfo=UTC),
        item.id,
    )


class TaskService:
    def __init__(self, repository: TaskRepository, cursor_codec: TaskCursor) -> None:
        self.repository = repository
        self.cursor_codec = cursor_codec

    async def list(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: TaskListQuery,
    ) -> TaskListResponse:
        specs = [spec for spec in TASK_CATEGORY_REGISTRY if principal.role in spec.roles]
        if query.category is not None:
            specs = [spec for spec in specs if spec.code == query.category]
            if not specs:
                raise ServiceExecutionError("validation_failed")
        try:
            anchor = self.cursor_codec.decode(principal=principal, branch_id=branch_id, query=query)
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None

        snapshot = await self.repository.snapshot()
        as_of = cast(datetime, snapshot["as_of"])
        business_date = cast(date, snapshot["business_date"])
        items_by_code: dict[str, list[TaskItem]] = {}
        failed: set[str] = set()
        for spec in specs:
            try:
                rows = await self.repository.read_category(
                    code=spec.code,
                    principal=principal,
                    branch_id=branch_id,
                    business_date=business_date,
                )
            except Exception:
                logger.warning(
                    "task_source_failed",
                    extra={"error_code": "task_source_unavailable", "task_category": spec.code},
                )
                failed.add(spec.code)
                items_by_code[spec.code] = []
                continue
            items = [_task_item(spec, row, business_date) for row in rows]
            if query.urgency is not None:
                items = [item for item in items if item.urgency == query.urgency]
            items_by_code[spec.code] = sorted(items, key=lambda item: _sort_key(item, spec.order))

        ordered = [item for spec in specs for item in items_by_code[spec.code]]
        start = 0
        if anchor is not None:
            try:
                start = next(index for index, item in enumerate(ordered) if item.id == anchor) + 1
            except StopIteration:
                raise ServiceExecutionError("invalid_cursor") from None
        page = ordered[start : start + query.limit]
        visible_ids = {item.id for item in page}
        next_cursor = None
        if start + query.limit < len(ordered):
            next_cursor = self.cursor_codec.encode(
                principal=principal, branch_id=branch_id, query=query, last_id=page[-1].id
            )

        categories: list[TaskCategory] = []
        version_rows: list[object] = []
        for spec in specs:
            all_items = items_by_code[spec.code]
            visible = [item for item in all_items if item.id in visible_ids]
            status = "failed" if spec.code in failed else ("ok" if all_items else "empty")
            categories.append(
                TaskCategory(
                    code=spec.code,
                    label=spec.label,
                    status=status,
                    count=len(all_items),
                    items=visible,
                    error_code="task_source_unavailable" if status == "failed" else None,
                )
            )
            version_rows.append(
                [spec.code, status, [item.model_dump(mode="json") for item in all_items]]
            )
        version = hashlib.sha256(
            json.dumps(version_rows, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        return TaskListResponse(
            categories=categories,
            next_cursor=next_cursor,
            as_of=as_of,
            source_version=f"sha256:{version}",
            source_unavailable=bool(failed),
        )
