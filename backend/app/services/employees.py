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
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.employees import EmployeeRepository, EmployeeSort
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.employees import (
    DirectReportResponse,
    EmployeeAdminDetailResponse,
    EmployeeAdminListResponse,
    EmployeeArchiveRequest,
    EmployeeCreateRequest,
    EmployeeDepartmentChangeRequest,
    EmployeeImportRequest,
    EmployeeImportResponse,
    EmployeeImportResult,
    EmployeeJobHistoryResponse,
    EmployeeManagerChangeRequest,
    EmployeePortalRoleResponse,
    EmployeePortalRoleUpdateRequest,
    EmployeeProbationConfirmationRequest,
    EmployeeProbationExtensionRequest,
    EmployeeProbationTerminationRequest,
    EmployeeSalaryChangeRequest,
    EmployeeSelfContactRequest,
    EmployeeSelfResponse,
    EmployeeStatusChangeRequest,
    EmployeeTitleChangeRequest,
    EmployeeUpdateRequest,
    EmployeeWorkflowRequest,
    ReportingManagerResponse,
    ReportReassignment,
)
from app.schemas.mutations import (
    PROTECTED_FIELDS_BY_TABLE,
    GuardedMutationValues,
    MutationFieldGuard,
)
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class EmployeeListQuery:
    limit: int
    search: str | None
    employment_status: str | None
    department: str | None
    active: bool | None
    reporting_manager_id: uuid.UUID | Literal["null"] | None
    sort: EmployeeSort
    cursor: str | None


@dataclass(frozen=True, slots=True)
class DirectReportQuery:
    limit: int
    search: str | None
    employment_status: str | None
    sort: EmployeeSort
    cursor: str | None


@dataclass(frozen=True, slots=True)
class JobHistoryQuery:
    limit: int
    employee_id: uuid.UUID | None
    change_type: str | None
    changed_from: datetime | None
    changed_to: datetime | None
    descending: bool
    cursor: str | None


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= 100:
        raise ValueError("invalid search")
    return normalized


def normalize_filter_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(normalized) <= 200:
        raise ValueError("invalid filter")
    return normalized


def _query_context(query: object) -> str:
    values = asdict(query)  # pyright: ignore[reportArgumentType]
    values.pop("cursor", None)
    values.pop("limit", None)
    encoded = json.dumps(
        values,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(encoded).digest()).decode("ascii").rstrip("=")


class EmployeeCursorCodec:
    def __init__(self, key: bytes, *, clock: Callable[[], datetime] | None = None) -> None:
        if len(key) != 32:
            raise ValueError("cursor key must contain 32 bytes")
        self._cipher = AESGCM(key)
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def from_base64url(cls, value: str) -> EmployeeCursorCodec:
        try:
            key = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("invalid cursor key") from None
        return cls(key)

    def encode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        last_id: uuid.UUID,
    ) -> str:
        payload = {
            "appUserId": str(principal.app_user_id),
            "branchId": str(branch_id),
            "companyId": str(principal.company_id),
            "context": _query_context(query),
            "expiresAt": int((self._clock() + timedelta(minutes=15)).timestamp()),
            "lastId": str(last_id),
            "operationId": operation_id,
            "role": principal.role.value,
            "version": 1,
        }
        plaintext = zlib.compress(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"), level=9
        )
        nonce = secrets.token_bytes(12)
        associated_data = f"workloop:{operation_id}:v1".encode()
        encrypted = self._cipher.encrypt(nonce, plaintext, associated_data)
        cursor = base64.urlsafe_b64encode(b"\x01" + nonce + encrypted).decode("ascii").rstrip("=")
        if len(cursor) > 512:
            raise RuntimeError("cursor exceeds the contract limit")
        return cursor

    def decode(
        self,
        *,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        cursor: str | None,
    ) -> uuid.UUID | None:
        if cursor is None:
            return None
        associated_data = f"workloop:{operation_id}:v1".encode()
        try:
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            if len(raw) < 30 or raw[0] != 1:
                raise ValueError("invalid cursor")
            plaintext = self._cipher.decrypt(raw[1:13], raw[13:], associated_data)
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
        expires_at = value.get("expiresAt")
        last_id = value.get("lastId")
        if (
            value.get("version") != 1
            or value.get("operationId") != operation_id
            or value.get("role") != principal.role.value
            or value.get("appUserId") != str(principal.app_user_id)
            or value.get("companyId") != str(principal.company_id)
            or value.get("branchId") != str(branch_id)
            or value.get("context") != _query_context(query)
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


_EMPLOYMENT_STATUS = {
    "Active": "active",
    "Probation": "probation",
    "On Leave": "on_leave",
    "Terminated": "terminated",
}
_VISA_TYPE = {
    "": None,
    "Employment Visa": "employment_visa",
    "Investor Visa": "investor_visa",
    "Dependent Visa": "dependent_visa",
    "Tourist (Temp)": "tourist_temp",
    "Exempt": "exempt",
}
_GENDER = {"": None, "Male": "male", "Female": "female", "Other": "other"}
_MARITAL_STATUS = {
    "": None,
    "Single": "single",
    "Married": "married",
    "Divorced": "divorced",
    "Widowed": "widowed",
}
_WORK_LOCATION = {"Mainland": "mainland", "Free Zone": "free_zone"}

_EMPLOYEE_PROTECTED_FIELDS = PROTECTED_FIELDS_BY_TABLE["employees"]
_CREATE_INPUT_FIELDS = frozenset(EmployeeCreateRequest.model_fields)
_CREATE_GUARD = MutationFieldGuard(
    allowed_input_fields=_CREATE_INPUT_FIELDS,
    approved_protected_fields=_CREATE_INPUT_FIELDS & _EMPLOYEE_PROTECTED_FIELDS,
    server_derived_fields=frozenset({"id", "company_id", "branch_id", "active"}),
)
_UPDATE_INPUT_FIELDS = frozenset(EmployeeUpdateRequest.model_fields) - {"expected_updated_at"}
_UPDATE_GUARD = MutationFieldGuard(
    allowed_input_fields=_UPDATE_INPUT_FIELDS,
    approved_protected_fields=_UPDATE_INPUT_FIELDS & _EMPLOYEE_PROTECTED_FIELDS,
)
_IMPORT_INPUT_FIELDS = frozenset(
    {
        "emp_no",
        "name",
        "mol_id",
        "bank_name",
        "bank_routing_code",
        "iban",
        "basic_salary",
        "allowance",
    }
)
_IMPORT_GUARD = MutationFieldGuard(
    allowed_input_fields=_IMPORT_INPUT_FIELDS,
    approved_protected_fields=_IMPORT_INPUT_FIELDS & _EMPLOYEE_PROTECTED_FIELDS,
    server_derived_fields=frozenset({"id", "company_id", "branch_id", "active"}),
)
_TITLE_GUARD = MutationFieldGuard(allowed_input_fields=frozenset({"job_title"}))
_DEPARTMENT_GUARD = MutationFieldGuard(allowed_input_fields=frozenset({"department"}))
_SALARY_FIELDS = frozenset(
    {
        "basic_salary",
        "allowance",
        "housing_allowance",
        "transport_allowance",
        "other_allowances",
        "other_allowances_label",
    }
)
_SALARY_GUARD = MutationFieldGuard(
    allowed_input_fields=_SALARY_FIELDS,
    approved_protected_fields=_SALARY_FIELDS & _EMPLOYEE_PROTECTED_FIELDS,
)
_STATUS_FIELDS = frozenset(
    {"active", "employment_status", "termination_date", "termination_reason"}
)
_STATUS_GUARD = MutationFieldGuard(
    allowed_input_fields=_STATUS_FIELDS,
    approved_protected_fields=_STATUS_FIELDS & _EMPLOYEE_PROTECTED_FIELDS,
)
_MANAGER_GUARD = MutationFieldGuard(
    allowed_input_fields=frozenset({"reporting_manager_id"}),
    approved_protected_fields=frozenset({"reporting_manager_id"}),
)
_PROBATION_CONFIRM_GUARD = MutationFieldGuard(
    allowed_input_fields=frozenset({"employment_status", "probation_end_date"}),
    approved_protected_fields=frozenset({"employment_status"}),
)
_PROBATION_EXTENSION_GUARD = MutationFieldGuard(
    allowed_input_fields=frozenset({"probation_end_date", "probation_extended"})
)
_CONTACT_FIELDS = frozenset(
    {"phone", "personal_email", "emergency_contact_name", "emergency_contact_phone"}
)
_CONTACT_GUARD = MutationFieldGuard(allowed_input_fields=_CONTACT_FIELDS)


def database_employment_status(value: str | None) -> str | None:
    reverse = {api: stored for stored, api in _EMPLOYMENT_STATUS.items()}
    if value is None:
        return None
    try:
        return reverse[value]
    except KeyError:
        raise ValueError("invalid employment status") from None


def _mapped(mapping: dict[str, Any], value: object, name: str) -> Any:
    try:
        return mapping[cast(str, value)]
    except (KeyError, TypeError):
        raise RuntimeError(f"invalid stored {name}") from None


def _money(value: object) -> str:
    return f"{value:.2f}"


def _list_values(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"],
        "emp_no": row["emp_no"],
        "name": row["name"],
        "photo_url": row["photo_url"],
        "work_email": row["work_email"],
        "job_title": row["job_title"],
        "department": row["department"],
        "reporting_manager_id": row["reporting_manager_id"],
        "employment_start_date": row["employment_start_date"],
        "probation_end_date": row["probation_end_date"],
        "employment_status": _mapped(_EMPLOYMENT_STATUS, row["employment_status"], "status"),
        "active": row["active"],
        "basic_salary": _money(row["basic_salary"]),
        "housing_allowance": _money(row["housing_allowance"]),
        "transport_allowance": _money(row["transport_allowance"]),
        "other_allowances": _money(row["other_allowances"]),
        "bank_name": row["bank_name"],
        "updated_at": row["updated_at"],
    }


def _detail_values(row: RowMapping) -> dict[str, Any]:
    return {
        **_list_values(row),
        "mol_id": row["mol_id"],
        "bank_routing_code": row["bank_routing_code"],
        "iban": row["iban"],
        "allowance": _money(row["allowance"]),
        "personal_email": row["personal_email"],
        "phone": row["phone"],
        "date_of_birth": row["date_of_birth"],
        "gender": _mapped(_GENDER, row["gender"], "gender"),
        "marital_status": _mapped(_MARITAL_STATUS, row["marital_status"], "marital status"),
        "home_country_address": row["home_country_address"],
        "emergency_contact_name": row["emergency_contact_name"],
        "emergency_contact_relationship": row["emergency_contact_relationship"],
        "emergency_contact_phone": row["emergency_contact_phone"],
        "probation_extended": row["probation_extended"],
        "termination_date": row["termination_date"],
        "termination_reason": row["termination_reason"],
        "other_allowances_label": row["other_allowances_label"],
        "bank_account_holder": row["bank_account_holder"],
        "nationality": row["nationality"],
        "visa_type": _mapped(_VISA_TYPE, row["visa_type"], "visa type"),
        "visa_number": row["visa_number"],
        "visa_expiry": row["visa_expiry"],
        "passport_number": row["passport_number"],
        "passport_expiry": row["passport_expiry"],
        "emirates_id": row["emirates_id"],
        "emirates_id_expiry": row["emirates_id_expiry"],
        "labour_card_number": row["labour_card_number"],
        "labour_card_expiry": row["labour_card_expiry"],
        "sponsoring_entity": row["sponsoring_entity"],
        "work_location_type": _mapped(_WORK_LOCATION, row["work_location_type"], "work location"),
        "free_zone_name": row["free_zone_name"],
        "nafis_registration_no": row["nafis_registration_no"],
        "licence_authority": row["licence_authority"],
        "licence_number": row["licence_number"],
        "licence_expiry": row["licence_expiry"],
        "created_at": row["created_at"],
    }


def _direct_report(row: RowMapping) -> DirectReportResponse:
    return DirectReportResponse(
        id=row["id"],
        emp_no=row["emp_no"],
        name=row["name"],
        photo_url=row["photo_url"],
        job_title=row["job_title"],
        department=row["department"],
        employment_start_date=row["employment_start_date"],
        probation_end_date=row["probation_end_date"],
        employment_status=_mapped(_EMPLOYMENT_STATUS, row["employment_status"], "status"),
    )


def _same_version(actual: datetime, expected: datetime) -> bool:
    def milliseconds(value: datetime) -> datetime:
        utc_value = value.astimezone(UTC)
        return utc_value.replace(microsecond=utc_value.microsecond // 1000 * 1000)

    return milliseconds(actual) == milliseconds(expected)


def _salary_snapshot(row: RowMapping | EmployeeSalaryChangeRequest) -> str:
    names = {
        "basicSalary": "basic_salary",
        "allowance": "allowance",
        "housingAllowance": "housing_allowance",
        "transportAllowance": "transport_allowance",
        "otherAllowances": "other_allowances",
    }
    values = {
        output: f"{(row[source] if isinstance(row, RowMapping) else getattr(row, source)):.2f}"
        for output, source in names.items()
    }
    values["otherAllowancesLabel"] = (
        row["other_allowances_label"] if isinstance(row, RowMapping) else row.other_allowances_label
    )
    return json.dumps(values, separators=(",", ":"), sort_keys=True)


class EmployeeService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        *,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._repository = EmployeeRepository(connection)
        self._cursor_codec = cursor_codec
        self._id_factory = id_factory

    def _decode(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        cursor: str | None,
    ) -> uuid.UUID | None:
        try:
            return self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                cursor=cursor,
            )
        except ValueError:
            raise ServiceExecutionError("invalid_cursor") from None

    def _next_cursor(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        operation_id: str,
        query: object,
        rows: list[RowMapping],
    ) -> str | None:
        return (
            self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id=operation_id,
                query=query,
                last_id=rows[-1]["id"],
            )
            if rows
            else None
        )

    async def list_employees(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: EmployeeListQuery,
    ) -> tuple[list[EmployeeAdminListResponse], str | None]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        cursor_id = self._decode(principal, branch_id, "list_employees", query, query.cursor)
        after = None
        if cursor_id is not None:
            try:
                after = await self._repository.fetch_employee_position(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    cursor_id=cursor_id,
                    search=query.search,
                    employment_status=query.employment_status,
                    department=query.department,
                    active=query.active,
                    reporting_manager_id=query.reporting_manager_id,
                    sort=query.sort,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_employees(
            company_id=principal.company_id,
            branch_id=branch_id,
            search=query.search,
            employment_status=query.employment_status,
            department=query.department,
            active=query.active,
            reporting_manager_id=query.reporting_manager_id,
            sort=query.sort,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, "list_employees", query, visible)
            if has_more
            else None
        )
        return [EmployeeAdminListResponse(**_list_values(row)) for row in visible], cursor

    async def get_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> EmployeeAdminDetailResponse:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.fetch_employee(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=employee_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        return EmployeeAdminDetailResponse(**_detail_values(row))

    @staticmethod
    def _require_admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    async def _validate_manager(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        manager_id: uuid.UUID | None,
    ) -> None:
        if manager_id is None:
            return
        try:
            eligible = await self._repository.manager_is_eligible(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=manager_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not eligible:
            raise ServiceExecutionError("employee_conflict")

    async def create_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: EmployeeCreateRequest,
    ) -> EmployeeAdminDetailResponse:
        self._require_admin(principal)
        try:
            await self._repository.lock_department(
                company_id=principal.company_id,
                branch_id=branch_id,
                name=request.department,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        await self._validate_manager(principal, branch_id, request.reporting_manager_id)
        values = _CREATE_GUARD.prepare(
            request.values(),
            derived_values={
                "id": self._id_factory(),
                "company_id": principal.company_id,
                "branch_id": branch_id,
                "active": True,
            },
        )
        try:
            row = await self._repository.create_employee(values)
        except IntegrityError:
            raise ServiceExecutionError("employee_conflict") from None
        return EmployeeAdminDetailResponse(**_detail_values(row))

    async def authorize_employee_replay(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._require_admin(principal)
        if kind != "employee" or resource_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            await self._repository.assert_employee_exists(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=resource_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeUpdateRequest,
    ) -> EmployeeAdminDetailResponse:
        self._require_admin(principal)
        values = _UPDATE_GUARD.prepare(request.changes())
        try:
            row = await self._repository.update_employee(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=employee_id,
                expected_updated_at=request.expected_updated_at,
                values=values,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        except IntegrityError:
            raise ServiceExecutionError("employee_conflict") from None
        return EmployeeAdminDetailResponse(**_detail_values(row))

    async def import_employees(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        request: EmployeeImportRequest,
    ) -> EmployeeImportResponse:
        self._require_admin(principal)
        results: list[EmployeeImportResult] = []
        try:
            for item in request.rows:
                employee_id = self._id_factory()
                values = _IMPORT_GUARD.prepare(
                    item.values(),
                    derived_values={
                        "id": employee_id,
                        "company_id": principal.company_id,
                        "branch_id": branch_id,
                        "active": True,
                    },
                )
                created_id = await self._repository.create_imported_employee(values)
                results.append(
                    EmployeeImportResult(row_number=item.row_number, employee_id=created_id)
                )
        except IntegrityError:
            raise ServiceExecutionError("employee_conflict") from None
        return EmployeeImportResponse(created_count=len(results), rows=results)

    async def authorize_import_replay(
        self,
        principal: AuthorizationPrincipal,
        _branch_id: uuid.UUID,
        kind: str,
        resource_id: uuid.UUID | None,
    ) -> None:
        self._require_admin(principal)
        if kind != "tenant" or resource_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    async def get_self(self, principal: AuthorizationPrincipal) -> EmployeeSelfResponse:
        if (
            principal.role not in {AppRole.MANAGER, AppRole.EMPLOYEE}
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row, manager = await self._repository.fetch_self(
                company_id=principal.company_id,
                branch_id=principal.branch_id,
                employee_id=principal.employee_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        values = _detail_values(row)
        for field in ("reporting_manager_id", "active", "created_at"):
            values.pop(field)
        values["reporting_manager"] = (
            None
            if manager is None
            else ReportingManagerResponse(
                id=manager["id"],
                name=manager["name"],
                job_title=manager["job_title"],
            )
        )
        return EmployeeSelfResponse(**values)

    async def list_direct_reports(
        self, principal: AuthorizationPrincipal, query: DirectReportQuery
    ) -> tuple[list[DirectReportResponse], str | None]:
        if (
            principal.role is not AppRole.MANAGER
            or principal.employee_id is None
            or principal.branch_id is None
        ):
            raise ServiceExecutionError("operation_not_permitted")
        branch_id = principal.branch_id
        cursor_id = self._decode(principal, branch_id, "list_direct_reports", query, query.cursor)
        after = None
        if cursor_id is not None:
            try:
                after = await self._repository.fetch_direct_report_position(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    manager_id=principal.employee_id,
                    cursor_id=cursor_id,
                    search=query.search,
                    employment_status=query.employment_status,
                    sort=query.sort,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_direct_reports(
            company_id=principal.company_id,
            branch_id=branch_id,
            manager_id=principal.employee_id,
            search=query.search,
            employment_status=query.employment_status,
            sort=query.sort,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, "list_direct_reports", query, visible)
            if has_more
            else None
        )
        return [_direct_report(row) for row in visible], cursor

    async def list_job_history(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: JobHistoryQuery,
        *,
        path_employee_id: uuid.UUID | None = None,
    ) -> tuple[list[EmployeeJobHistoryResponse], str | None]:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")
        employee_id = path_employee_id if path_employee_id is not None else query.employee_id
        if path_employee_id is not None:
            try:
                await self._repository.assert_employee_exists(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    employee_id=path_employee_id,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("resource_not_found") from None
        operation_id = (
            "list_employee_job_history" if path_employee_id is not None else "list_job_history"
        )
        cursor_id = self._decode(principal, branch_id, operation_id, query, query.cursor)
        after = None
        if cursor_id is not None:
            try:
                after = await self._repository.fetch_job_history_position(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    cursor_id=cursor_id,
                    employee_id=employee_id,
                    change_type=query.change_type,
                    changed_from=query.changed_from,
                    changed_to=query.changed_to,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.fetch_job_history(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            change_type=query.change_type,
            changed_from=query.changed_from,
            changed_to=query.changed_to,
            descending=query.descending,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        cursor = (
            self._next_cursor(principal, branch_id, operation_id, query, visible)
            if has_more
            else None
        )
        items = [
            EmployeeJobHistoryResponse(
                id=row["id"],
                employee_id=row["employee_id"],
                changed_at=row["changed_at"],
                changed_by_app_user_id=row["changed_by_app_user_id"],
                change_type=row["change_type"],
                old_value=row["old_value"],
                new_value=row["new_value"],
                reason=row["reason"],
            )
            for row in visible
        ]
        return items, cursor

    async def _locked_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        expected_updated_at: datetime,
    ) -> RowMapping:
        self._require_admin(principal)
        try:
            row = await self._repository.lock_employee(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=employee_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not _same_version(row["updated_at"], expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        return row

    async def _history_change(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeWorkflowRequest,
        *,
        change_type: str,
        old_value: str,
        new_value: str,
        values: GuardedMutationValues,
    ) -> EmployeeAdminDetailResponse:
        await self._repository.append_job_history(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            actor_id=principal.app_user_id,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            reason=request.reason,
        )
        row = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=values,
        )
        return EmployeeAdminDetailResponse(**_detail_values(row))

    async def change_title(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeTitleChangeRequest,
    ) -> EmployeeAdminDetailResponse:
        row = await self._locked_employee(
            principal, branch_id, employee_id, request.expected_updated_at
        )
        if row["job_title"] == request.job_title:
            raise ServiceExecutionError("employee_conflict")
        return await self._history_change(
            principal,
            branch_id,
            employee_id,
            request,
            change_type="title_change",
            old_value=row["job_title"],
            new_value=request.job_title,
            values=_TITLE_GUARD.prepare({"job_title": request.job_title}),
        )

    async def change_department(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeDepartmentChangeRequest,
    ) -> EmployeeAdminDetailResponse:
        row = await self._locked_employee(
            principal, branch_id, employee_id, request.expected_updated_at
        )
        if row["department"] == request.department:
            raise ServiceExecutionError("employee_conflict")
        try:
            await self._repository.lock_department(
                company_id=principal.company_id,
                branch_id=branch_id,
                name=request.department,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        return await self._history_change(
            principal,
            branch_id,
            employee_id,
            request,
            change_type="department_change",
            old_value=row["department"],
            new_value=request.department,
            values=_DEPARTMENT_GUARD.prepare({"department": request.department}),
        )

    async def change_salary(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeSalaryChangeRequest,
    ) -> EmployeeAdminDetailResponse:
        row = await self._locked_employee(
            principal, branch_id, employee_id, request.expected_updated_at
        )
        old_value = _salary_snapshot(row)
        new_value = _salary_snapshot(request)
        if old_value == new_value:
            raise ServiceExecutionError("employee_conflict")
        values = {name: getattr(request, name) for name in _SALARY_FIELDS}
        return await self._history_change(
            principal,
            branch_id,
            employee_id,
            request,
            change_type="salary_change",
            old_value=old_value,
            new_value=new_value,
            values=_SALARY_GUARD.prepare(values),
        )

    async def _apply_report_reassignments(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        manager_id: uuid.UUID,
        manager_expected_updated_at: datetime,
        reassignments: list[ReportReassignment],
    ) -> RowMapping:
        if len({item.employee_id for item in reassignments}) != len(reassignments):
            raise ServiceExecutionError("manager_reassignment_conflict")
        preliminary = await self._repository.fetch_report_ids(
            company_id=principal.company_id, branch_id=branch_id, manager_id=manager_id
        )
        ids = {
            manager_id,
            *preliminary,
            *(item.employee_id for item in reassignments),
            *(item.new_manager_id for item in reassignments),
        }
        await self._repository.acquire_relationship_locks(ids)
        locked = await self._repository.lock_employee_set(
            company_id=principal.company_id, branch_id=branch_id, employee_ids=ids
        )
        if set(locked) != ids or manager_id not in locked:
            raise ServiceExecutionError("resource_not_found")
        current_reports = await self._repository.fetch_report_ids(
            company_id=principal.company_id, branch_id=branch_id, manager_id=manager_id
        )
        if set(current_reports) != {item.employee_id for item in reassignments}:
            raise ServiceExecutionError("manager_reassignment_conflict")
        manager = locked[manager_id]
        if not _same_version(manager["updated_at"], manager_expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        for item in sorted(reassignments, key=lambda value: value.employee_id):
            report = locked[item.employee_id]
            replacement = locked[item.new_manager_id]
            if (
                report["reporting_manager_id"] != manager_id
                or not _same_version(report["updated_at"], item.expected_updated_at)
                or item.new_manager_id == manager_id
                or replacement["active"] is not True
                or replacement["employment_status"] not in {"Active", "Probation", "On Leave"}
                or await self._repository.would_create_manager_cycle(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    employee_id=item.employee_id,
                    new_manager_id=item.new_manager_id,
                )
            ):
                raise ServiceExecutionError("manager_reassignment_conflict")
        for item in sorted(reassignments, key=lambda value: value.employee_id):
            await self._repository.update_workflow_employee(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=item.employee_id,
                values=_MANAGER_GUARD.prepare({"reporting_manager_id": item.new_manager_id}),
            )
            await self._repository.append_employee_audit(
                action="employee_manager_changed",
                entity_type="employee",
                entity_id=item.employee_id,
                changed_fields=["reporting_manager_id"],
                reason="Reporting manager reassigned",
                metadata={
                    "previous_manager_id": str(manager_id),
                    "new_manager_id": str(item.new_manager_id),
                },
            )
        return manager

    async def change_manager(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeManagerChangeRequest,
    ) -> EmployeeAdminDetailResponse:
        self._require_admin(principal)
        ids = {employee_id}
        if request.reporting_manager_id is not None:
            ids.add(request.reporting_manager_id)
        await self._repository.acquire_relationship_locks(ids)
        locked = await self._repository.lock_employee_set(
            company_id=principal.company_id, branch_id=branch_id, employee_ids=ids
        )
        if employee_id not in locked:
            raise ServiceExecutionError("resource_not_found")
        row = locked[employee_id]
        if not _same_version(row["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        new_manager_id = request.reporting_manager_id
        old_manager_id = row["reporting_manager_id"]
        if old_manager_id == new_manager_id or new_manager_id == employee_id:
            raise ServiceExecutionError("manager_reassignment_conflict")
        if new_manager_id is not None:
            manager = locked.get(new_manager_id)
            if (
                manager is None
                or manager["active"] is not True
                or manager["employment_status"] not in {"Active", "Probation", "On Leave"}
                or await self._repository.would_create_manager_cycle(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    employee_id=employee_id,
                    new_manager_id=new_manager_id,
                )
            ):
                raise ServiceExecutionError("manager_reassignment_conflict")
        updated = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=_MANAGER_GUARD.prepare({"reporting_manager_id": new_manager_id}),
        )
        await self._repository.append_employee_audit(
            action="employee_manager_changed",
            entity_type="employee",
            entity_id=employee_id,
            changed_fields=["reporting_manager_id"],
            reason=request.reason,
            metadata={
                "previous_manager_id": None if old_manager_id is None else str(old_manager_id),
                "new_manager_id": None if new_manager_id is None else str(new_manager_id),
            },
        )
        return EmployeeAdminDetailResponse(**_detail_values(updated))

    async def change_status(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeStatusChangeRequest,
    ) -> EmployeeAdminDetailResponse:
        new_status = database_employment_status(request.employment_status)
        assert new_status is not None
        preliminary = await self._repository.fetch_report_ids(
            company_id=principal.company_id, branch_id=branch_id, manager_id=employee_id
        )
        if new_status == "Terminated" and preliminary:
            row = await self._apply_report_reassignments(
                principal,
                branch_id,
                employee_id,
                request.expected_updated_at,
                request.report_reassignments,
            )
        else:
            if request.report_reassignments:
                raise ServiceExecutionError("manager_reassignment_conflict")
            row = await self._locked_employee(
                principal, branch_id, employee_id, request.expected_updated_at
            )
        old_status = row["employment_status"]
        if old_status == "Terminated" or old_status == new_status:
            raise ServiceExecutionError("employment_transition_conflict")
        if old_status == "Probation" and new_status in {"Active", "Terminated"}:
            raise ServiceExecutionError("employment_transition_conflict")
        business_date = await self._repository.business_date()
        values = {
            "active": new_status != "Terminated",
            "employment_status": new_status,
            "termination_date": business_date if new_status == "Terminated" else None,
            "termination_reason": request.reason if new_status == "Terminated" else "",
        }
        await self._repository.append_job_history(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            actor_id=principal.app_user_id,
            change_type="status_change",
            old_value=old_status,
            new_value=new_status,
            reason=request.reason,
        )
        updated = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=_STATUS_GUARD.prepare(values),
        )
        return EmployeeAdminDetailResponse(**_detail_values(updated))

    async def confirm_probation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeProbationConfirmationRequest,
    ) -> EmployeeAdminDetailResponse:
        row = await self._locked_employee(
            principal, branch_id, employee_id, request.expected_updated_at
        )
        if row["employment_status"] != "Probation" or row["active"] is not True:
            raise ServiceExecutionError("employment_transition_conflict")
        await self._repository.append_job_history(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            actor_id=principal.app_user_id,
            change_type="status_change",
            old_value="Probation",
            new_value="Active",
            reason=request.reason,
        )
        updated = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=_PROBATION_CONFIRM_GUARD.prepare(
                {"employment_status": "Active", "probation_end_date": None}
            ),
        )
        await self._repository.append_employee_audit(
            action="employee_probation_confirmed",
            entity_type="employee",
            entity_id=employee_id,
            changed_fields=["employment_status", "probation_end_date"],
            reason=request.reason,
            metadata={"transition": "probation_to_active"},
        )
        return EmployeeAdminDetailResponse(**_detail_values(updated))

    async def extend_probation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeProbationExtensionRequest,
    ) -> EmployeeAdminDetailResponse:
        row = await self._locked_employee(
            principal, branch_id, employee_id, request.expected_updated_at
        )
        previous = row["probation_end_date"]
        if (
            row["employment_status"] != "Probation"
            or row["active"] is not True
            or previous is None
            or request.probation_end_date <= previous
        ):
            raise ServiceExecutionError("employment_transition_conflict")
        updated = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=_PROBATION_EXTENSION_GUARD.prepare(
                {"probation_end_date": request.probation_end_date, "probation_extended": True}
            ),
        )
        await self._repository.append_employee_audit(
            action="employee_probation_extended",
            entity_type="employee",
            entity_id=employee_id,
            changed_fields=["probation_end_date", "probation_extended"],
            reason=request.reason,
            metadata={
                "previous_probation_end_date": previous.isoformat(),
                "new_probation_end_date": request.probation_end_date.isoformat(),
            },
        )
        return EmployeeAdminDetailResponse(**_detail_values(updated))

    async def _terminate(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeProbationTerminationRequest | EmployeeArchiveRequest,
        *,
        probation: bool,
    ) -> EmployeeAdminDetailResponse:
        preliminary = await self._repository.fetch_report_ids(
            company_id=principal.company_id, branch_id=branch_id, manager_id=employee_id
        )
        if preliminary:
            row = await self._apply_report_reassignments(
                principal,
                branch_id,
                employee_id,
                request.expected_updated_at,
                request.report_reassignments,
            )
        else:
            if request.report_reassignments:
                raise ServiceExecutionError("manager_reassignment_conflict")
            row = await self._locked_employee(
                principal, branch_id, employee_id, request.expected_updated_at
            )
        allowed = {"Probation"} if probation else {"Active", "On Leave"}
        if row["employment_status"] not in allowed or row["active"] is not True:
            raise ServiceExecutionError("employment_transition_conflict")
        business_date = await self._repository.business_date()
        await self._repository.append_job_history(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            actor_id=principal.app_user_id,
            change_type="status_change",
            old_value=row["employment_status"],
            new_value="Terminated",
            reason=request.reason,
        )
        updated = await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            values=_STATUS_GUARD.prepare(
                {
                    "active": False,
                    "employment_status": "Terminated",
                    "termination_date": business_date,
                    "termination_reason": request.reason,
                }
            ),
        )
        action = "employee_probation_terminated" if probation else "employee_archived"
        transition = (
            "probation_to_terminated"
            if probation
            else f"{_EMPLOYMENT_STATUS[row['employment_status']]}_to_terminated"
        )
        await self._repository.append_employee_audit(
            action=action,
            entity_type="employee",
            entity_id=employee_id,
            changed_fields=[
                "active",
                "employment_status",
                "termination_date",
                "termination_reason",
            ],
            reason=request.reason,
            metadata={"transition": transition},
        )
        return EmployeeAdminDetailResponse(**_detail_values(updated))

    async def terminate_probation(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeProbationTerminationRequest,
    ) -> EmployeeAdminDetailResponse:
        return await self._terminate(principal, branch_id, employee_id, request, probation=True)

    async def archive_employee(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeeArchiveRequest,
    ) -> EmployeeAdminDetailResponse:
        return await self._terminate(principal, branch_id, employee_id, request, probation=False)

    async def update_self_contact(
        self, principal: AuthorizationPrincipal, request: EmployeeSelfContactRequest
    ) -> EmployeeSelfResponse:
        if principal.employee_id is None or principal.branch_id is None:
            raise ServiceExecutionError("operation_not_permitted")
        try:
            row = await self._repository.lock_employee(
                company_id=principal.company_id,
                branch_id=principal.branch_id,
                employee_id=principal.employee_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        if not _same_version(row["updated_at"], request.expected_updated_at):
            raise ServiceExecutionError("state_conflict")
        await self._repository.update_workflow_employee(
            company_id=principal.company_id,
            branch_id=principal.branch_id,
            employee_id=principal.employee_id,
            values=_CONTACT_GUARD.prepare(request.changes()),
        )
        return await self.get_self(principal)

    async def get_portal_role(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
    ) -> EmployeePortalRoleResponse:
        self._require_admin(principal)
        try:
            await self._repository.assert_employee_exists(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=employee_id,
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        profile = await self._repository.fetch_portal_role(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
        )
        if profile is None or profile["eligible"] is not True:
            return EmployeePortalRoleResponse(employee_id=employee_id, activated=False, role=None)
        return EmployeePortalRoleResponse(
            employee_id=employee_id, activated=True, role=profile["role"]
        )

    async def set_portal_role(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        employee_id: uuid.UUID,
        request: EmployeePortalRoleUpdateRequest,
    ) -> EmployeePortalRoleResponse:
        self._require_admin(principal)
        profile = await self._repository.fetch_portal_role(
            company_id=principal.company_id,
            branch_id=branch_id,
            employee_id=employee_id,
            lock=True,
        )
        if (
            profile is None
            or profile["eligible"] is not True
            or profile["app_user_id"] == principal.app_user_id
            or profile["role"] != request.expected_role
            or request.role == request.expected_role
        ):
            raise ServiceExecutionError("portal_role_conflict")
        if request.expected_role == "manager" and request.role == "employee":
            employee = await self._repository.fetch_employee(
                company_id=principal.company_id,
                branch_id=branch_id,
                employee_id=employee_id,
            )
            await self._apply_report_reassignments(
                principal,
                branch_id,
                employee_id,
                employee["updated_at"],
                request.report_reassignments,
            )
        elif request.report_reassignments:
            raise ServiceExecutionError("manager_reassignment_conflict")
        else:
            try:
                employee = await self._repository.lock_employee(
                    company_id=principal.company_id,
                    branch_id=branch_id,
                    employee_id=employee_id,
                )
            except ResourceNotFoundError:
                raise ServiceExecutionError("portal_role_conflict") from None
            if employee["active"] is not True or employee["employment_status"] not in {
                "Active",
                "Probation",
                "On Leave",
            }:
                raise ServiceExecutionError("portal_role_conflict")
        try:
            await self._repository.update_portal_role(
                app_user_id=profile["app_user_id"], employee_id=employee_id, role=request.role
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("portal_role_conflict") from None
        await self._repository.append_employee_audit(
            action="employee_portal_role_changed",
            entity_type="user_profile",
            entity_id=profile["app_user_id"],
            changed_fields=["role"],
            reason="Portal role changed",
            metadata={"transition": f"{request.expected_role}_to_{request.role}"},
        )
        return EmployeePortalRoleResponse(
            employee_id=employee_id, activated=True, role=request.role
        )
