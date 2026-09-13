from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.auth.application_user import AuthorizationPrincipal
from app.models.identity import AppRole
from app.repositories.leave_configuration import LeaveConfigurationRepository
from app.repositories.scoped import ResourceNotFoundError
from app.schemas.leave_configuration import (
    LeaveSettingsRequest,
    LeaveSettingsResponse,
    LeaveTypeCreateRequest,
    LeaveTypeResponse,
    LeaveTypeUpdateRequest,
    PublicHolidayCreateRequest,
    PublicHolidayResponse,
    PublicHolidaySnapshot,
    PublicHolidayUpdateRequest,
    SeedHolidaysRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class LeaveTypeListQuery:
    limit: int
    cursor: str | None


@dataclass(frozen=True, slots=True)
class HolidayListQuery:
    limit: int
    year: int | None
    cursor: str | None


DEFAULT_LEAVE_TYPES: tuple[dict[str, object], ...] = (
    {
        "code": "ANNUAL",
        "name": "Annual Leave",
        "color": "#1a56db",
        "is_paid": True,
        "min_notice_days": 14,
        "annual_entitlement_days": "30.00",
        "accrual_type": "monthly",
        "carry_forward_allowed": True,
        "carry_forward_max_days": 15,
        "sort_order": 0,
        "probation_eligible": False,
        "law_reference": "Art. 29 - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "SICK",
        "name": "Sick Leave",
        "color": "#c27803",
        "is_paid": True,
        "requires_attachment": True,
        "requires_reason": True,
        "annual_entitlement_days": "90.00",
        "sort_order": 1,
        "law_reference": "Art. 31 - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "MATERNITY",
        "name": "Maternity Leave",
        "color": "#e879f9",
        "is_paid": True,
        "requires_attachment": True,
        "min_notice_days": 30,
        "annual_entitlement_days": "60.00",
        "gender_restriction": "Female",
        "min_service_months": 12,
        "sort_order": 2,
        "law_reference": "Art. 30 - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "PATERNITY",
        "name": "Parental Leave",
        "color": "#0891b2",
        "is_paid": True,
        "annual_entitlement_days": "5.00",
        "day_count_type": "working",
        "gender_restriction": "Male",
        "sort_order": 3,
        "law_reference": "Art. 32 - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "BEREAVEMENT",
        "name": "Bereavement Leave",
        "color": "#6b7280",
        "is_paid": True,
        "requires_reason": True,
        "annual_entitlement_days": "5.00",
        "day_count_type": "working",
        "not_deducted_from_annual": True,
        "sort_order": 4,
        "law_reference": "UAE Cabinet Resolution No. 1 of 2022",
    },
    {
        "code": "STUDY",
        "name": "Study Leave",
        "color": "#7c3aed",
        "is_paid": True,
        "requires_attachment": True,
        "requires_reason": True,
        "min_notice_days": 7,
        "annual_entitlement_days": "10.00",
        "day_count_type": "working",
        "probation_eligible": False,
        "sort_order": 5,
        "law_reference": "Art. 36 - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "HAJJ",
        "name": "Hajj Leave",
        "color": "#16a34a",
        "is_paid": False,
        "annual_entitlement_days": "30.00",
        "accrual_type": "once_per_career",
        "once_per_career": True,
        "min_service_months": 24,
        "min_notice_days": 30,
        "probation_eligible": False,
        "sort_order": 6,
        "law_reference": "Art. 29 Hajj - Federal Decree-Law No. 33 of 2021",
    },
    {
        "code": "UNPAID",
        "name": "Unpaid Leave",
        "color": "#9ca3af",
        "is_paid": False,
        "is_unlimited": True,
        "requires_reason": True,
        "min_notice_days": 7,
        "annual_entitlement_days": "0.00",
        "accrual_type": "none",
        "affects_payroll": True,
        "sort_order": 7,
        "law_reference": "Employer discretion - Federal Decree-Law No. 33 of 2021",
    },
)


class LeaveConfigurationService:
    def __init__(
        self,
        connection: AsyncConnection,
        cursor_codec: EmployeeCursorCodec,
        repository: LeaveConfigurationRepository | None = None,
    ) -> None:
        self._repository = repository or LeaveConfigurationRepository(connection)
        self._cursor_codec = cursor_codec

    @staticmethod
    def _admin(principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN or principal.branch_id is not None:
            raise ServiceExecutionError("operation_not_permitted")

    @staticmethod
    def _branch(principal: AuthorizationPrincipal, branch_id: uuid.UUID) -> None:
        if principal.role is not AppRole.ADMIN and principal.branch_id != branch_id:
            raise ServiceExecutionError("resource_not_found")

    async def get_settings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> LeaveSettingsResponse:
        self._admin(principal)
        try:
            return LeaveSettingsResponse.model_validate(
                await self._repository.get_settings(principal.company_id, branch_id)
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_settings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: LeaveSettingsRequest
    ) -> LeaveSettingsResponse:
        self._admin(principal)
        try:
            row = await self._repository.upsert_settings(
                company_id=principal.company_id,
                branch_id=branch_id,
                expected=body.expected_updated_at,
                values=body.model_dump(exclude={"expected_updated_at"}, by_alias=False),
            )
            return LeaveSettingsResponse.model_validate(row)
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def list_types(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: LeaveTypeListQuery,
        *,
        active_only: bool,
    ) -> tuple[list[LeaveTypeResponse], str | None]:
        self._branch(principal, branch_id)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_leave_types",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_type_position(
                    principal.company_id,
                    branch_id,
                    after_id,
                    active_only=active_only,
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.list_types(
            principal.company_id,
            branch_id,
            active_only=active_only,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_leave_types",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [LeaveTypeResponse.model_validate(row) for row in visible], next_cursor

    async def create_type(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        body: LeaveTypeCreateRequest,
    ) -> LeaveTypeResponse:
        self._admin(principal)
        try:
            row = await self._repository.create_type(
                company_id=principal.company_id,
                branch_id=branch_id,
                values=body.model_dump(by_alias=False),
            )
            return LeaveTypeResponse.model_validate(row)
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def update_type(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        type_id: uuid.UUID,
        body: LeaveTypeUpdateRequest,
    ) -> LeaveTypeResponse:
        self._admin(principal)
        try:
            row = await self._repository.update_type(
                company_id=principal.company_id,
                branch_id=branch_id,
                type_id=type_id,
                expected=body.expected_updated_at,
                values=body.model_dump(
                    exclude={"expected_updated_at"}, exclude_unset=True, by_alias=False
                ),
            )
            return LeaveTypeResponse.model_validate(row)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError as error:
            code = "state_conflict" if str(error) == "state conflict" else "branch_conflict"
            raise ServiceExecutionError(code) from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def seed_types(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> list[LeaveTypeResponse]:
        self._admin(principal)
        rows = await self._repository.seed_types(
            company_id=principal.company_id,
            branch_id=branch_id,
            defaults=DEFAULT_LEAVE_TYPES,
        )
        return [LeaveTypeResponse.model_validate(row) for row in rows]

    async def list_holidays(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        query: HolidayListQuery,
    ) -> tuple[list[PublicHolidayResponse], str | None]:
        self._admin(principal)
        try:
            after_id = self._cursor_codec.decode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_public_holidays",
                query=query,
                cursor=query.cursor,
            )
            after = (
                None
                if after_id is None
                else await self._repository.fetch_holiday_position(
                    principal.company_id, branch_id, after_id, query.year
                )
            )
        except (ValueError, ResourceNotFoundError):
            raise ServiceExecutionError("invalid_cursor") from None
        rows = await self._repository.list_holidays(
            principal.company_id,
            branch_id,
            query.year,
            after=after,
            limit=query.limit,
        )
        has_more = len(rows) > query.limit
        visible = rows[: query.limit]
        next_cursor = None
        if has_more:
            next_cursor = self._cursor_codec.encode(
                principal=principal,
                branch_id=branch_id,
                operation_id="list_public_holidays",
                query=query,
                last_id=visible[-1]["id"],
            )
        return [PublicHolidayResponse.model_validate(row) for row in visible], next_cursor

    async def create_holiday(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        body: PublicHolidayCreateRequest,
    ) -> PublicHolidayResponse:
        self._admin(principal)
        try:
            row = await self._repository.create_holiday(
                company_id=principal.company_id,
                branch_id=branch_id,
                values=body.model_dump(by_alias=False),
            )
            return PublicHolidayResponse.model_validate(row)
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def update_holiday(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        body: PublicHolidayUpdateRequest,
    ) -> PublicHolidayResponse:
        self._admin(principal)
        try:
            row = await self._repository.update_holiday(
                company_id=principal.company_id,
                branch_id=branch_id,
                holiday_id=holiday_id,
                expected=body.expected.model_dump(by_alias=False),
                values=body.model_dump(exclude={"expected"}, exclude_unset=True, by_alias=False),
            )
            return PublicHolidayResponse.model_validate(row)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError as error:
            code = "state_conflict" if str(error) == "state conflict" else "operation_not_permitted"
            raise ServiceExecutionError(code) from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def delete_holiday(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        expected: PublicHolidaySnapshot,
    ) -> None:
        self._admin(principal)
        try:
            await self._repository.delete_holiday(
                company_id=principal.company_id,
                branch_id=branch_id,
                holiday_id=holiday_id,
                expected=expected.model_dump(by_alias=False),
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError as error:
            code = "state_conflict" if str(error) == "state conflict" else "operation_not_permitted"
            raise ServiceExecutionError(code) from None

    async def seed_holidays(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: SeedHolidaysRequest
    ) -> list[PublicHolidayResponse]:
        self._admin(principal)
        if any(item.date.year != body.year for item in body.holidays):
            raise ServiceExecutionError("operation_not_permitted")
        try:
            rows = await self._repository.seed_holidays(
                company_id=principal.company_id,
                branch_id=branch_id,
                holidays=[item.model_dump(by_alias=False) for item in body.holidays],
            )
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None
        return [PublicHolidayResponse.model_validate(row) for row in rows]
