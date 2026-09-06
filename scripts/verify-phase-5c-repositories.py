import asyncio
import os
import uuid
from datetime import date
from typing import Any, cast

from sqlalchemy import ColumnElement, create_engine, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.application_user import AuthorizationPrincipal
from app.auth.scopes import (
    active_leave_delegate_authorization_scope,
    active_leave_delegate_scope_predicate,
    branch_authorization_scope,
    branch_scope_predicate,
    direct_report_authorization_scope,
    direct_report_scope_predicate,
    employee_self_authorization_scope,
    employee_self_scope_predicate,
    tenant_authorization_scope,
    tenant_scope_predicate,
)
from app.db.seed import constants as fixture_ids
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.identity import AccountStatus, AppRole, AppUser, Employee
from app.models.leave import LeaveApprovalDelegate, LeaveRequest
from app.repositories.scoped import (
    MutationConflictError,
    ResourceNotFoundError,
    ScopedRepository,
)
from app.schemas.mutations import MutationFieldGuard

HORIZON_MANAGER_ID = uuid.UUID("21000000-0000-4000-8000-000000000001")
HORIZON_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
HORIZON_DELEGATE_ID = uuid.UUID("21000000-0000-4000-8000-000000000005")
CEDAR_EMPLOYEE_ID = uuid.UUID("31000000-0000-4000-8000-000000000002")
HORIZON_MANAGER_APP_USER_ID = uuid.UUID("11000000-0000-4000-8000-000000000001")
HORIZON_EMPLOYEE_APP_USER_ID = uuid.UUID("11000000-0000-4000-8000-000000000002")
HORIZON_DELEGATE_APP_USER_ID = uuid.UUID("11000000-0000-4000-8000-000000000005")


def principal(
    *,
    app_user_id: uuid.UUID,
    role: AppRole,
    employee_id: uuid.UUID | None,
    branch_id: uuid.UUID | None,
) -> AuthorizationPrincipal:
    return AuthorizationPrincipal(
        app_user_id=app_user_id,
        account_status=AccountStatus.ACTIVE,
        role=role,
        company_id=fixture_ids.COMPANY_ID[fixture_ids.HORIZON],
        employee_id=employee_id,
        branch_id=branch_id,
    )


async def employee_ids(
    connection: AsyncConnection,
    predicate: ColumnElement[bool],
) -> set[uuid.UUID]:
    statement = select(Employee.__table__.c.id).where(predicate)
    return set((await connection.execute(statement)).scalars().all())


async def verify(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                admin = principal(
                    app_user_id=fixture_ids.ADMIN_APP_USER[fixture_ids.HORIZON],
                    role=AppRole.ADMIN,
                    employee_id=None,
                    branch_id=None,
                )
                manager = principal(
                    app_user_id=HORIZON_MANAGER_APP_USER_ID,
                    role=AppRole.MANAGER,
                    employee_id=HORIZON_MANAGER_ID,
                    branch_id=fixture_ids.BRANCH_DXB,
                )
                employee = principal(
                    app_user_id=HORIZON_EMPLOYEE_APP_USER_ID,
                    role=AppRole.EMPLOYEE,
                    employee_id=HORIZON_EMPLOYEE_ID,
                    branch_id=fixture_ids.BRANCH_DXB,
                )
                delegate = principal(
                    app_user_id=HORIZON_DELEGATE_APP_USER_ID,
                    role=AppRole.EMPLOYEE,
                    employee_id=HORIZON_DELEGATE_ID,
                    branch_id=fixture_ids.BRANCH_DXB,
                )

                tenant_scope = tenant_authorization_scope(admin)
                tenant_ids = await employee_ids(
                    connection,
                    tenant_scope_predicate(Employee.__table__.c.company_id, tenant_scope),
                )
                assert HORIZON_EMPLOYEE_ID in tenant_ids
                assert CEDAR_EMPLOYEE_ID not in tenant_ids

                branch_scope = branch_authorization_scope(
                    admin,
                    verified_admin_branch_id=fixture_ids.BRANCH_DXB,
                )
                branch_predicate = branch_scope_predicate(
                    Employee.__table__.c.company_id,
                    Employee.__table__.c.branch_id,
                    branch_scope,
                )
                branch_ids = await employee_ids(connection, branch_predicate)
                assert HORIZON_EMPLOYEE_ID in branch_ids
                assert uuid.UUID("22000000-0000-4000-8000-000000000002") not in branch_ids
                assert CEDAR_EMPLOYEE_ID not in branch_ids

                self_scope = employee_self_authorization_scope(employee)
                self_ids = await employee_ids(
                    connection,
                    employee_self_scope_predicate(
                        Employee.__table__.c.company_id,
                        Employee.__table__.c.branch_id,
                        Employee.__table__.c.id,
                        self_scope,
                    ),
                )
                assert self_ids == {HORIZON_EMPLOYEE_ID}

                manager_scope = direct_report_authorization_scope(manager)
                report_predicate = direct_report_scope_predicate(
                    Employee.__table__.c.id,
                    manager_scope,
                )
                report_ids = await employee_ids(connection, report_predicate)
                assert HORIZON_EMPLOYEE_ID in report_ids
                assert HORIZON_MANAGER_ID not in report_ids
                assert CEDAR_EMPLOYEE_ID not in report_ids

                delegate_scope = active_leave_delegate_authorization_scope(
                    delegate,
                    business_date=fixture_ids.TODAY,
                )
                delegated_request_ids = set(
                    (
                        await connection.execute(
                            select(LeaveRequest.__table__.c.employee_id).where(
                                active_leave_delegate_scope_predicate(
                                    LeaveRequest.__table__.c.employee_id,
                                    delegate_scope,
                                )
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert HORIZON_EMPLOYEE_ID in delegated_request_ids

                future_scope = active_leave_delegate_authorization_scope(
                    delegate,
                    business_date=date(2027, 1, 1),
                )
                future_requests = await connection.execute(
                    select(LeaveRequest.__table__.c.id).where(
                        active_leave_delegate_scope_predicate(
                            LeaveRequest.__table__.c.employee_id,
                            future_scope,
                        )
                    )
                )
                assert future_requests.scalars().all() == []

                active_delegation_id = fixture_ids.derive(
                    "leave_approval_delegates",
                    fixture_ids.HORIZON,
                    "dubai",
                    "H-DXB-001",
                    "active",
                )
                date_savepoint = await connection.begin_nested()
                try:
                    for from_date, to_date in (
                        (date(2027, 1, 1), date(2027, 1, 31)),
                        (date(2026, 6, 1), date(2026, 6, 30)),
                    ):
                        await connection.execute(
                            update(cast(Any, LeaveApprovalDelegate.__table__))
                            .where(LeaveApprovalDelegate.__table__.c.id == active_delegation_id)
                            .values(from_date=from_date, to_date=to_date)
                        )
                        inactive_requests = await connection.execute(
                            select(LeaveRequest.__table__.c.id).where(
                                active_leave_delegate_scope_predicate(
                                    LeaveRequest.__table__.c.employee_id,
                                    delegate_scope,
                                )
                            )
                        )
                        assert inactive_requests.scalars().all() == []
                finally:
                    await date_savepoint.rollback()

                manager_account_savepoint = await connection.begin_nested()
                try:
                    await connection.execute(
                        update(cast(Any, AppUser.__table__))
                        .where(AppUser.__table__.c.id == HORIZON_MANAGER_APP_USER_ID)
                        .values(status=AccountStatus.DISABLED)
                    )
                    assert await employee_ids(connection, report_predicate) == set()
                finally:
                    await manager_account_savepoint.rollback()

                delegate_account_savepoint = await connection.begin_nested()
                try:
                    await connection.execute(
                        update(cast(Any, AppUser.__table__))
                        .where(AppUser.__table__.c.id == HORIZON_DELEGATE_APP_USER_ID)
                        .values(status=AccountStatus.DISABLED)
                    )
                    disabled_delegate_requests = await connection.execute(
                        select(LeaveRequest.__table__.c.id).where(
                            active_leave_delegate_scope_predicate(
                                LeaveRequest.__table__.c.employee_id,
                                delegate_scope,
                            )
                        )
                    )
                    assert disabled_delegate_requests.scalars().all() == []
                finally:
                    await delegate_account_savepoint.rollback()

                repository = ScopedRepository(
                    connection=connection,
                    table=Employee.__table__,
                    id_column=Employee.__table__.c.id,
                    scope_predicate=branch_predicate,
                )
                for inaccessible_id in (uuid.uuid4(), CEDAR_EMPLOYEE_ID):
                    try:
                        await repository.fetch_one(inaccessible_id)
                    except ResourceNotFoundError:
                        pass
                    else:
                        raise AssertionError("an inaccessible employee lookup returned a row")

                original_phone = (
                    await connection.execute(
                        select(Employee.__table__.c.phone).where(
                            Employee.__table__.c.id == HORIZON_EMPLOYEE_ID
                        )
                    )
                ).scalar_one()
                contact_guard = MutationFieldGuard(allowed_input_fields=frozenset({"phone"}))
                try:
                    await repository.update_batch(
                        (HORIZON_EMPLOYEE_ID, CEDAR_EMPLOYEE_ID),
                        contact_guard.prepare({"phone": "+971500000099"}),
                    )
                except ResourceNotFoundError:
                    pass
                else:
                    raise AssertionError("a mixed-scope batch update did not fail")
                phone_after_denial = (
                    await connection.execute(
                        select(Employee.__table__.c.phone).where(
                            Employee.__table__.c.id == HORIZON_EMPLOYEE_ID
                        )
                    )
                ).scalar_one()
                assert phone_after_denial == original_phone

                try:
                    await repository.update_one(
                        HORIZON_EMPLOYEE_ID,
                        contact_guard.prepare({"phone": "+971500000099"}),
                        extra_predicates=(Employee.__table__.c.phone == "stale-value",),
                    )
                except MutationConflictError:
                    pass
                else:
                    raise AssertionError("a stale guarded update did not return a conflict")
                phone_after_conflict = (
                    await connection.execute(
                        select(Employee.__table__.c.phone).where(
                            Employee.__table__.c.id == HORIZON_EMPLOYEE_ID
                        )
                    )
                ).scalar_one()
                assert phone_after_conflict == original_phone

                await connection.execute(
                    update(cast(Any, Employee.__table__))
                    .where(Employee.__table__.c.id == HORIZON_EMPLOYEE_ID)
                    .values(reporting_manager_id=None)
                )
                assert HORIZON_EMPLOYEE_ID not in await employee_ids(
                    connection,
                    report_predicate,
                )
                stale_delegate_requests = await connection.execute(
                    select(LeaveRequest.__table__.c.id).where(
                        LeaveRequest.__table__.c.employee_id == HORIZON_EMPLOYEE_ID,
                        active_leave_delegate_scope_predicate(
                            LeaveRequest.__table__.c.employee_id,
                            delegate_scope,
                        ),
                    )
                )
                assert stale_delegate_requests.scalars().all() == []

            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


def main() -> None:
    database_url = os.environ.get("MIGRATION_DATABASE_URL")
    if not database_url:
        raise SystemExit("MIGRATION_DATABASE_URL is required")
    rows = build_rows()
    sync_engine = create_engine(database_url)
    try:
        with sync_engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
        try:
            asyncio.run(verify(database_url))
        finally:
            with sync_engine.begin() as connection:
                clean(connection, rows)
    finally:
        sync_engine.dispose()
    print("Phase 5C repository authorization checks passed and fixtures were removed.")


if __name__ == "__main__":
    main()
