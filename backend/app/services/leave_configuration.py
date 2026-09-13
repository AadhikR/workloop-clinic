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
    LeaveTypeRequest,
    LeaveTypeResponse,
    PublicHolidayRequest,
    PublicHolidayResponse,
    SeedHolidaysRequest,
)
from app.services.execution import ServiceExecutionError


@dataclass(frozen=True, slots=True)
class LeaveConfigurationService:
    connection: AsyncConnection

    @property
    def repository(self) -> LeaveConfigurationRepository:
        return LeaveConfigurationRepository(self.connection)

    def _admin(self, principal: AuthorizationPrincipal) -> None:
        if principal.role is not AppRole.ADMIN:
            raise ServiceExecutionError("operation_not_permitted")

    def _branch(self, principal: AuthorizationPrincipal, branch_id: uuid.UUID) -> None:
        if principal.role is not AppRole.ADMIN and principal.branch_id != branch_id:
            raise ServiceExecutionError("resource_not_found")

    async def get_settings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> LeaveSettingsResponse:
        self._admin(principal)
        try:
            return LeaveSettingsResponse.model_validate(
                await self.repository.get_settings(principal.company_id, branch_id)
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None

    async def update_settings(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: LeaveSettingsRequest
    ) -> LeaveSettingsResponse:
        self._admin(principal)
        try:
            row = await self.repository.upsert_settings(
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
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, *, active_only: bool
    ) -> list[LeaveTypeResponse]:
        self._branch(principal, branch_id)
        rows = await self.repository.list_types(
            principal.company_id, branch_id, active_only=active_only
        )
        return [LeaveTypeResponse.model_validate(row) for row in rows]

    async def create_type(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: LeaveTypeRequest
    ) -> LeaveTypeResponse:
        self._admin(principal)
        try:
            row = await self.repository.create_type(
                company_id=principal.company_id,
                branch_id=branch_id,
                values=body.model_dump(exclude={"expected_updated_at"}, by_alias=False),
            )
            return LeaveTypeResponse.model_validate(row)
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def update_type(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        type_id: uuid.UUID,
        body: LeaveTypeRequest,
    ) -> LeaveTypeResponse:
        self._admin(principal)
        try:
            row = await self.repository.update_type(
                company_id=principal.company_id,
                branch_id=branch_id,
                type_id=type_id,
                expected=body.expected_updated_at,
                values=body.model_dump(exclude={"expected_updated_at"}, by_alias=False),
            )
            return LeaveTypeResponse.model_validate(row)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("state_conflict") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def seed_types(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID
    ) -> list[LeaveTypeResponse]:
        self._admin(principal)
        defaults = [
            {
                "code": "ANNUAL",
                "name": "Annual Leave",
                "is_paid": True,
                "min_notice_days": 14,
                "annual_entitlement_days": "30.00",
                "accrual_type": "monthly",
                "carry_forward_allowed": True,
                "carry_forward_max_days": 15,
                "sort_order": 0,
                "probation_eligible": False,
            },
            {
                "code": "SICK",
                "name": "Sick Leave",
                "is_paid": True,
                "requires_attachment": True,
                "requires_reason": True,
                "annual_entitlement_days": "90.00",
                "sort_order": 1,
            },
            {
                "code": "MATERNITY",
                "name": "Maternity Leave",
                "is_paid": True,
                "requires_attachment": True,
                "annual_entitlement_days": "60.00",
                "gender_restriction": "Female",
                "min_service_months": 12,
                "sort_order": 2,
            },
            {
                "code": "PATERNITY",
                "name": "Parental Leave",
                "is_paid": True,
                "annual_entitlement_days": "5.00",
                "day_count_type": "working",
                "gender_restriction": "Male",
                "sort_order": 3,
            },
            {
                "code": "BEREAVEMENT",
                "name": "Bereavement Leave",
                "is_paid": True,
                "requires_reason": True,
                "annual_entitlement_days": "5.00",
                "day_count_type": "working",
                "not_deducted_from_annual": True,
                "sort_order": 4,
            },
            {
                "code": "STUDY",
                "name": "Study Leave",
                "is_paid": True,
                "requires_attachment": True,
                "requires_reason": True,
                "annual_entitlement_days": "10.00",
                "day_count_type": "working",
                "probation_eligible": False,
                "sort_order": 5,
            },
            {
                "code": "HAJJ",
                "name": "Hajj Leave",
                "is_paid": False,
                "annual_entitlement_days": "30.00",
                "accrual_type": "once_per_career",
                "once_per_career": True,
                "min_notice_days": 30,
                "sort_order": 6,
            },
            {
                "code": "UNPAID",
                "name": "Unpaid Leave",
                "is_paid": False,
                "is_unlimited": True,
                "requires_reason": True,
                "accrual_type": "none",
                "affects_payroll": True,
                "sort_order": 7,
            },
        ]
        normalized = [{**item, "color": item.get("color", "#6b7280")} for item in defaults]
        rows = await self.repository.seed_types(
            company_id=principal.company_id, branch_id=branch_id, defaults=normalized
        )
        return [LeaveTypeResponse.model_validate(row) for row in rows]

    async def list_holidays(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, year: int | None
    ) -> list[PublicHolidayResponse]:
        self._branch(principal, branch_id)
        rows = await self.repository.list_holidays(principal.company_id, branch_id, year)
        return [PublicHolidayResponse.model_validate(row) for row in rows]

    async def create_holiday(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: PublicHolidayRequest
    ) -> PublicHolidayResponse:
        self._admin(principal)
        try:
            row = await self.repository.create_holiday(
                company_id=principal.company_id,
                branch_id=branch_id,
                values=body.model_dump(exclude={"expected_created_at"}, by_alias=False),
            )
            return PublicHolidayResponse.model_validate(row)
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def update_holiday(
        self,
        principal: AuthorizationPrincipal,
        branch_id: uuid.UUID,
        holiday_id: uuid.UUID,
        body: PublicHolidayRequest,
    ) -> PublicHolidayResponse:
        self._admin(principal)
        try:
            row = await self.repository.update_holiday(
                company_id=principal.company_id,
                branch_id=branch_id,
                holiday_id=holiday_id,
                values=body.model_dump(exclude={"expected_created_at"}, by_alias=False),
            )
            return PublicHolidayResponse.model_validate(row)
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("operation_not_permitted") from None
        except IntegrityError:
            raise ServiceExecutionError("branch_conflict") from None

    async def delete_holiday(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, holiday_id: uuid.UUID
    ) -> None:
        self._admin(principal)
        try:
            await self.repository.delete_holiday(
                company_id=principal.company_id, branch_id=branch_id, holiday_id=holiday_id
            )
        except ResourceNotFoundError:
            raise ServiceExecutionError("resource_not_found") from None
        except ValueError:
            raise ServiceExecutionError("operation_not_permitted") from None

    async def seed_holidays(
        self, principal: AuthorizationPrincipal, branch_id: uuid.UUID, body: SeedHolidaysRequest
    ) -> list[PublicHolidayResponse]:
        self._admin(principal)
        if any(item.date.year != body.year for item in body.holidays):
            raise ServiceExecutionError("operation_not_permitted")
        rows = await self.repository.seed_holidays(
            company_id=principal.company_id,
            branch_id=branch_id,
            holidays=[
                item.model_dump(exclude={"expected_created_at"}, by_alias=False)
                for item in body.holidays
            ],
        )
        return [PublicHolidayResponse.model_validate(row) for row in rows]
