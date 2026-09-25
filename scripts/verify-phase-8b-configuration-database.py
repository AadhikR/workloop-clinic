#!/usr/bin/env python3
"""Verify Phase 8B configuration transactions with synthetic PostgreSQL data."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.leave import LeaveSettings, LeaveType, PublicHoliday
from app.schemas.leave_configuration import (
    LeaveSettingsRequest,
    LeaveTypeUpdateRequest,
    PublicHolidayCreateRequest,
    PublicHolidaySnapshot,
    PublicHolidayUpdateRequest,
    SeedHolidaysRequest,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.leave_configuration import (
    HolidayListQuery,
    LeaveConfigurationService,
    LeaveTypeListQuery,
)
from sqlalchemy import Engine, create_engine, delete, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_HEAD = "e8a1c3f5b7d9"
ADMIN_SUBJECT = "hr.admin@horizon.test"
STAFF_SUBJECT = "ravi.employee@horizon.test"
CURSOR_CODEC = EmployeeCursorCodec(b"8" * 32)


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


async def expect_code(code: str, operation: Awaitable[object]) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


async def verify_services() -> None:
    runtime_engine = create_async_engine(
        URL.create(
            "postgresql+psycopg",
            username="workloop_runtime",
            password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
            host="postgres",
            database="workloop",
        )
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=c.SEED_ISSUER, timeout_seconds=2
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=10,
    )

    async def run(
        subject: str,
        principal: AuthorizationPrincipal,
        operation: Callable[[LeaveConfigurationService], Awaitable[Any]],
        branch_id: uuid.UUID | None,
    ) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            return await operation(LeaveConfigurationService(connection, CURSOR_CODEC))

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            operation=execute,
            selected_admin_branch_id=branch_id,
        )

    try:
        admin = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
        staff = await resolver.resolve(issuer=c.SEED_ISSUER, subject=STAFF_SUBJECT)

        async def read_settings(service: LeaveConfigurationService) -> object:
            return await service.get_settings(admin, c.BRANCH_DXB)

        settings = await run(ADMIN_SUBJECT, admin, read_settings, c.BRANCH_DXB)
        settings_values = settings.model_dump(by_alias=True, mode="json")
        update_values = {
            "expectedUpdatedAt": settings_values["updatedAt"],
            "leaveYearType": settings_values["leaveYearType"],
            "weekendDefinition": settings_values["weekendDefinition"],
            "carryForwardEnabled": settings_values["carryForwardEnabled"],
            "carryForwardMaxDays": 16,
            "approvalChain": settings_values["approvalChain"],
            "ramadanActive": settings_values["ramadanActive"],
            "ramadanStart": settings_values["ramadanStart"],
            "ramadanEnd": settings_values["ramadanEnd"],
        }
        update_request = LeaveSettingsRequest.model_validate(update_values)

        async def update_settings(service: LeaveConfigurationService) -> object:
            return await service.update_settings(admin, c.BRANCH_DXB, update_request)

        updated_settings = await run(
            ADMIN_SUBJECT, admin, update_settings, c.BRANCH_DXB
        )
        assert updated_settings.carry_forward_max_days == 16
        assert updated_settings.updated_at > settings.updated_at
        await expect_code(
            "state_conflict", run(ADMIN_SUBJECT, admin, update_settings, c.BRANCH_DXB)
        )

        list_query = LeaveTypeListQuery(limit=100, cursor=None)

        async def list_admin_types(service: LeaveConfigurationService) -> object:
            return await service.list_types(
                admin, c.BRANCH_DXB, list_query, active_only=False
            )

        types_before, _ = await run(
            ADMIN_SUBJECT, admin, list_admin_types, c.BRANCH_DXB
        )
        by_code = {item.code: item for item in types_before}
        annual = by_code["ANNUAL"]
        unsafe = LeaveTypeUpdateRequest.model_validate(
            {
                "expectedUpdatedAt": annual.model_dump(by_alias=True, mode="json")[
                    "updatedAt"
                ],
                "isActive": False,
            }
        )

        async def deactivate_annual(service: LeaveConfigurationService) -> object:
            return await service.update_type(admin, c.BRANCH_DXB, annual.id, unsafe)

        await expect_code(
            "branch_conflict",
            run(ADMIN_SUBJECT, admin, deactivate_annual, c.BRANCH_DXB),
        )
        types_after_failure, _ = await run(
            ADMIN_SUBJECT, admin, list_admin_types, c.BRANCH_DXB
        )
        assert next(
            item for item in types_after_failure if item.id == annual.id
        ).is_active

        custom = by_code["CUSTOM_COMPASSIONATE"]
        custom_update = LeaveTypeUpdateRequest.model_validate(
            {
                "expectedUpdatedAt": custom.model_dump(by_alias=True, mode="json")[
                    "updatedAt"
                ],
                "name": "Phase 8B Compassionate Leave",
            }
        )

        async def update_custom_type(service: LeaveConfigurationService) -> object:
            return await service.update_type(
                admin, c.BRANCH_DXB, custom.id, custom_update
            )

        updated_custom = await run(
            ADMIN_SUBJECT, admin, update_custom_type, c.BRANCH_DXB
        )
        assert updated_custom.updated_at > custom.updated_at
        await expect_code(
            "state_conflict",
            run(ADMIN_SUBJECT, admin, update_custom_type, c.BRANCH_DXB),
        )

        async def seed_types(service: LeaveConfigurationService) -> object:
            return await service.seed_types(admin, c.BRANCH_DXB)

        first_seed = await run(ADMIN_SUBJECT, admin, seed_types, c.BRANCH_DXB)
        second_seed = await run(ADMIN_SUBJECT, admin, seed_types, c.BRANCH_DXB)
        assert [item.id for item in first_seed] == [item.id for item in second_seed]

        async def list_staff_types(service: LeaveConfigurationService) -> object:
            return await service.list_types(
                staff, c.BRANCH_DXB, list_query, active_only=True
            )

        staff_types, _ = await run(STAFF_SUBJECT, staff, list_staff_types, None)
        assert staff_types and all(item.is_active for item in staff_types)
        await expect_code(
            "resource_not_found",
            run(
                STAFF_SUBJECT,
                staff,
                lambda service: service.list_types(
                    staff, c.BRANCH_AUH, list_query, active_only=True
                ),
                None,
            ),
        )
        await expect_code(
            "operation_not_permitted",
            run(
                STAFF_SUBJECT,
                staff,
                lambda service: service.list_holidays(
                    staff,
                    c.BRANCH_DXB,
                    HolidayListQuery(limit=50, year=2027, cursor=None),
                ),
                None,
            ),
        )
        await expect_code(
            "resource_not_found",
            run(ADMIN_SUBJECT, admin, read_settings, c.BRANCH_SHJ),
        )

        seed_request = SeedHolidaysRequest.model_validate(
            {
                "year": 2027,
                "holidays": [
                    {
                        "date": "2027-01-01",
                        "name": "Phase 8B New Year",
                        "type": "federal",
                    }
                ],
            }
        )

        async def seed_holidays(service: LeaveConfigurationService) -> object:
            return await service.seed_holidays(admin, c.BRANCH_DXB, seed_request)

        first_holidays = await run(ADMIN_SUBJECT, admin, seed_holidays, c.BRANCH_DXB)
        second_holidays = await run(ADMIN_SUBJECT, admin, seed_holidays, c.BRANCH_DXB)
        assert [item.id for item in first_holidays] == [
            item.id for item in second_holidays
        ]
        holiday = next(
            item for item in first_holidays if item.name == "Phase 8B New Year"
        )
        holiday_values = holiday.model_dump(by_alias=True, mode="json")
        holiday_snapshot = PublicHolidaySnapshot.model_validate(
            {
                "date": holiday_values["date"],
                "name": holiday_values["name"],
                "type": holiday_values["type"],
            }
        )
        holiday_update = PublicHolidayUpdateRequest.model_validate(
            {
                "expected": holiday_snapshot.model_dump(by_alias=True, mode="json"),
                "name": "Phase 8B New Year Day",
            }
        )

        async def update_holiday(service: LeaveConfigurationService) -> object:
            return await service.update_holiday(
                admin, c.BRANCH_DXB, holiday.id, holiday_update
            )

        updated_holiday = await run(ADMIN_SUBJECT, admin, update_holiday, c.BRANCH_DXB)
        assert updated_holiday.name == "Phase 8B New Year Day"
        await expect_code(
            "state_conflict", run(ADMIN_SUBJECT, admin, update_holiday, c.BRANCH_DXB)
        )

        used_holiday_request = PublicHolidayCreateRequest.model_validate(
            {
                "date": "2026-10-01",
                "name": "Phase 8B Used Holiday",
                "type": "company",
            }
        )

        async def create_used_holiday(service: LeaveConfigurationService) -> object:
            return await service.create_holiday(
                admin, c.BRANCH_DXB, used_holiday_request
            )

        used_holiday = await run(
            ADMIN_SUBJECT, admin, create_used_holiday, c.BRANCH_DXB
        )
        used_values = used_holiday.model_dump(by_alias=True, mode="json")
        used_snapshot = PublicHolidaySnapshot.model_validate(
            {
                "date": used_values["date"],
                "name": used_values["name"],
                "type": used_values["type"],
            }
        )
        used_update = PublicHolidayUpdateRequest.model_validate(
            {
                "expected": used_snapshot.model_dump(by_alias=True, mode="json"),
                "name": "Phase 8B Changed Holiday",
            }
        )
        await expect_code(
            "operation_not_permitted",
            run(
                ADMIN_SUBJECT,
                admin,
                lambda service: service.update_holiday(
                    admin, c.BRANCH_DXB, used_holiday.id, used_update
                ),
                c.BRANCH_DXB,
            ),
        )

        past_request = PublicHolidayCreateRequest.model_validate(
            {
                "date": "2025-01-01",
                "name": "Phase 8B Past Holiday",
                "type": "federal",
            }
        )

        async def create_past_holiday(service: LeaveConfigurationService) -> object:
            return await service.create_holiday(admin, c.BRANCH_DXB, past_request)

        past_holiday = await run(
            ADMIN_SUBJECT, admin, create_past_holiday, c.BRANCH_DXB
        )
        past_values = past_holiday.model_dump(by_alias=True, mode="json")
        past_snapshot = PublicHolidaySnapshot.model_validate(
            {
                "date": past_values["date"],
                "name": past_values["name"],
                "type": past_values["type"],
            }
        )
        await expect_code(
            "operation_not_permitted",
            run(
                ADMIN_SUBJECT,
                admin,
                lambda service: service.delete_holiday(
                    admin, c.BRANCH_DXB, past_holiday.id, past_snapshot
                ),
                c.BRANCH_DXB,
            ),
        )
        await expect_code(
            "operation_not_permitted",
            run(
                ADMIN_SUBJECT,
                admin,
                lambda service: service.delete_holiday(
                    admin, c.BRANCH_DXB, used_holiday.id, used_snapshot
                ),
                c.BRANCH_DXB,
            ),
        )
    finally:
        await runtime_engine.dispose()


def cleanup_extra_rows(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            delete(PublicHoliday).where(PublicHoliday.name.like("Phase 8B%"))
        )


def verify_guard_lock_conflict(engine: Engine) -> None:
    with engine.connect() as guard, engine.connect() as writer:
        guard_transaction = guard.begin()
        writer_transaction = writer.begin()
        try:
            guard.exec_driver_sql(
                "LOCK TABLE public.leave_requests, public.attendance_records "
                "IN SHARE ROW EXCLUSIVE MODE"
            )
            writer.exec_driver_sql("SET LOCAL lock_timeout = '100ms'")
            try:
                writer.exec_driver_sql(
                    "LOCK TABLE public.leave_requests, public.attendance_records "
                    "IN ROW EXCLUSIVE MODE"
                )
            except DBAPIError as error:
                assert getattr(error.orig, "sqlstate", None) == "55P03"
            else:
                raise AssertionError(
                    "configuration guard lock allowed a concurrent writer"
                )
        finally:
            writer_transaction.rollback()
            guard_transaction.rollback()


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            assert connection.execute(select(LeaveSettings.id)).first() is not None
            assert connection.execute(select(LeaveType.id)).first() is not None
            assert connection.execute(select(PublicHoliday.id)).first() is not None
            assert (
                connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
                == EXPECTED_HEAD
            )
        verify_guard_lock_conflict(engine)
        asyncio.run(verify_services())
        print("Phase 8B configuration database check passed")
    finally:
        cleanup_extra_rows(engine)
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
