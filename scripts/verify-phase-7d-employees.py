#!/usr/bin/env python3
"""Verify Phase 7D employee reads against the synthetic database."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import (
    ApplicationUserResolver,
    ApplicationUserUnavailableError,
)
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.services.employees import (
    DirectReportQuery,
    EmployeeCursorCodec,
    EmployeeListQuery,
    EmployeeService,
    JobHistoryQuery,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_HEAD = "8f6b2d1a4c70"
ADMIN_SUBJECT = "hr.admin@horizon.test"
MANAGER_SUBJECT = "aisha.manager@horizon.test"
EMPLOYEE_SUBJECT = "ravi.employee@horizon.test"
EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
OTHER_BRANCH_EMPLOYEE_ID = uuid.UUID("22000000-0000-4000-8000-000000000002")
MANAGER_ID = uuid.UUID("21000000-0000-4000-8000-000000000001")
HISTORY_IDS = (
    uuid.UUID("7d000000-0000-4000-8000-000000000001"),
    uuid.UUID("7d000000-0000-4000-8000-000000000002"),
)
UNLINKED_USER_ID = uuid.UUID("7d000000-0000-4000-8000-000000000003")
UNLINKED_SUBJECT = "phase7d.unlinked@horizon.test"
CURSOR_CODEC = EmployeeCursorCodec(b"phase-7d-verifier-cursor-key-000")


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def list_query(**changes: object) -> EmployeeListQuery:
    values: dict[str, object] = {
        "limit": 50,
        "search": None,
        "employment_status": None,
        "department": None,
        "active": None,
        "reporting_manager_id": None,
        "sort": (("name", False),),
        "cursor": None,
    }
    values.update(changes)
    return EmployeeListQuery(**values)  # pyright: ignore[reportArgumentType]


async def expect_code(code: str, operation: Any) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


async def verify_services(engine: Engine) -> dict[str, object]:
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
        engine=runtime_engine,
        issuer=c.SEED_ISSUER,
        timeout_seconds=2,
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=5,
    )
    admin = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
    manager = await resolver.resolve(issuer=c.SEED_ISSUER, subject=MANAGER_SUBJECT)
    employee = await resolver.resolve(issuer=c.SEED_ISSUER, subject=EMPLOYEE_SUBJECT)

    async def run_admin(branch_id: uuid.UUID, operation: Any) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            return await operation(EmployeeService(connection, CURSOR_CODEC))

        return await executor.execute(
            claims=claims(ADMIN_SUBJECT),
            principal=admin,
            operation=execute,
            selected_admin_branch_id=branch_id,
        )

    async def run_staff(active: Any, subject: str, operation: Any) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            return await operation(EmployeeService(connection, CURSOR_CODEC))

        return await executor.execute(
            claims=claims(subject), principal=active, operation=execute
        )

    async def read_manager(connection: AsyncConnection) -> dict[str, object] | None:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT id, name, job_title "
                        "FROM public.current_employee_reporting_manager()"
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else dict(row)

    try:
        first_query = list_query(limit=2, sort=(("employmentStartDate", False),))
        first, cursor = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_employees(admin, c.BRANCH_DXB, first_query),
        )
        assert cursor is not None and len(first) == 2
        all_items = list(first)
        while cursor is not None:
            page_query = list_query(
                limit=2,
                sort=(("employmentStartDate", False),),
                cursor=cursor,
            )
            page, cursor = await run_admin(
                c.BRANCH_DXB,
                lambda service, query=page_query: service.list_employees(
                    admin, c.BRANCH_DXB, query
                ),
            )
            all_items.extend(page)
        assert len(all_items) == 6
        assert len({item.id for item in all_items}) == 6
        assert all_items[-1].employment_start_date is None

        descending, _ = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_employees(
                admin,
                c.BRANCH_DXB,
                list_query(sort=(("employmentStartDate", True),)),
            ),
        )
        assert descending[-1].employment_start_date is None
        literal_wildcard, _ = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_employees(
                admin, c.BRANCH_DXB, list_query(search="%")
            ),
        )
        assert literal_wildcard == []
        no_manager, _ = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_employees(
                admin, c.BRANCH_DXB, list_query(reporting_manager_id="null")
            ),
        )
        assert [item.id for item in no_manager] == [MANAGER_ID]

        detail = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.get_employee(admin, c.BRANCH_DXB, EMPLOYEE_ID),
        )
        assert detail.id == EMPLOYEE_ID
        assert detail.basic_salary == "12000.00"
        assert set(detail.model_dump(by_alias=True)) == {
            "id",
            "empNo",
            "name",
            "photoUrl",
            "workEmail",
            "jobTitle",
            "department",
            "reportingManagerId",
            "employmentStartDate",
            "probationEndDate",
            "employmentStatus",
            "active",
            "basicSalary",
            "housingAllowance",
            "transportAllowance",
            "otherAllowances",
            "bankName",
            "updatedAt",
            "molId",
            "bankRoutingCode",
            "iban",
            "allowance",
            "personalEmail",
            "phone",
            "dateOfBirth",
            "gender",
            "maritalStatus",
            "homeCountryAddress",
            "emergencyContactName",
            "emergencyContactRelationship",
            "emergencyContactPhone",
            "probationExtended",
            "terminationDate",
            "terminationReason",
            "otherAllowancesLabel",
            "bankAccountHolder",
            "nationality",
            "visaType",
            "visaNumber",
            "visaExpiry",
            "passportNumber",
            "passportExpiry",
            "emiratesId",
            "emiratesIdExpiry",
            "labourCardNumber",
            "labourCardExpiry",
            "sponsoringEntity",
            "workLocationType",
            "freeZoneName",
            "nafisRegistrationNo",
            "licenceAuthority",
            "licenceNumber",
            "licenceExpiry",
            "createdAt",
        }
        await expect_code(
            "resource_not_found",
            run_admin(
                c.BRANCH_DXB,
                lambda service: service.get_employee(
                    admin, c.BRANCH_DXB, OTHER_BRANCH_EMPLOYEE_ID
                ),
            ),
        )
        await expect_code(
            "resource_not_found",
            run_admin(
                c.BRANCH_SHJ,
                lambda service: service.list_employees(
                    admin, c.BRANCH_SHJ, list_query()
                ),
            ),
        )

        self_projection = await run_staff(
            employee, EMPLOYEE_SUBJECT, lambda service: service.get_self(employee)
        )
        assert self_projection.id == EMPLOYEE_ID
        assert self_projection.iban == detail.iban
        assert self_projection.reporting_manager is not None
        assert self_projection.reporting_manager.id == MANAGER_ID
        assert "updatedAt" in self_projection.model_dump(by_alias=True)
        assert not {"active", "reportingManagerId", "createdAt"} & set(
            self_projection.model_dump(by_alias=True)
        )
        employee_manager = await executor.execute(
            claims=claims(EMPLOYEE_SUBJECT),
            principal=employee,
            operation=read_manager,
        )
        assert employee_manager == {
            "id": MANAGER_ID,
            "name": self_projection.reporting_manager.name,
            "job_title": self_projection.reporting_manager.job_title,
        }
        admin_manager = await executor.execute(
            claims=claims(ADMIN_SUBJECT),
            principal=admin,
            operation=read_manager,
            selected_admin_branch_id=c.BRANCH_DXB,
        )
        assert admin_manager is None

        async with runtime_engine.connect() as connection:
            without_context = (
                await connection.execute(
                    text(
                        "SELECT count(*) FROM public.current_employee_reporting_manager()"
                    )
                )
            ).scalar_one()
        assert without_context == 0

        reports, _ = await run_staff(
            manager,
            MANAGER_SUBJECT,
            lambda service: service.list_direct_reports(
                manager,
                DirectReportQuery(
                    limit=50,
                    search=None,
                    employment_status=None,
                    sort=(("name", False),),
                    cursor=None,
                ),
            ),
        )
        assert {report.id for report in reports} == {
            uuid.UUID("21000000-0000-4000-8000-000000000002"),
            uuid.UUID("21000000-0000-4000-8000-000000000003"),
            uuid.UUID("21000000-0000-4000-8000-000000000004"),
            uuid.UUID("21000000-0000-4000-8000-000000000005"),
        }
        assert all(
            not {"basicSalary", "workEmail", "phone", "emiratesId"}
            & set(report.model_dump(by_alias=True))
            for report in reports
        )
        await expect_code(
            "operation_not_permitted",
            run_staff(
                employee,
                EMPLOYEE_SUBJECT,
                lambda service: service.list_direct_reports(
                    employee,
                    DirectReportQuery(
                        limit=50,
                        search=None,
                        employment_status=None,
                        sort=(("name", False),),
                        cursor=None,
                    ),
                ),
            ),
        )

        history_query = JobHistoryQuery(
            limit=50,
            employee_id=EMPLOYEE_ID,
            change_type=None,
            changed_from=None,
            changed_to=None,
            descending=True,
            cursor=None,
        )
        history, _ = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_job_history(
                admin, c.BRANCH_DXB, history_query
            ),
        )
        assert [item.id for item in history] == list(reversed(HISTORY_IDS))
        one_history, _ = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_job_history(
                admin, c.BRANCH_DXB, history_query, path_employee_id=EMPLOYEE_ID
            ),
        )
        assert one_history == history

        bound_query = list_query(limit=1)
        bound_page, bound_cursor = await run_admin(
            c.BRANCH_DXB,
            lambda service: service.list_employees(admin, c.BRANCH_DXB, bound_query),
        )
        assert len(bound_page) == 1
        if bound_cursor is not None:
            await expect_code(
                "invalid_cursor",
                run_admin(
                    c.BRANCH_DXB,
                    lambda service: service.list_employees(
                        admin,
                        c.BRANCH_DXB,
                        list_query(limit=1, search="Maria", cursor=bound_cursor),
                    ),
                ),
            )

        return {
            "adminBranchEmployees": len(all_items),
            "directReports": len(reports),
            "jobHistoryRows": len(history),
            "nullableDateOrdering": "nulls-last-both-directions",
            "reportingManagerReader": "employee-context-only",
        }
    finally:
        await runtime_engine.dispose()


async def verify_ineligible_accounts(engine: Engine) -> None:
    async_engine = create_async_engine(
        URL.create(
            "postgresql+psycopg",
            username="workloop_runtime",
            password=os.environ["WORKLOOP_RUNTIME_PASSWORD"],
            host="postgres",
            database="workloop",
        )
    )
    resolver = ApplicationUserResolver(
        engine=async_engine, issuer=c.SEED_ISSUER, timeout_seconds=2
    )

    async def denied(subject: str = EMPLOYEE_SUBJECT) -> None:
        try:
            await resolver.resolve(issuer=c.SEED_ISSUER, subject=subject)
        except ApplicationUserUnavailableError:
            return
        raise AssertionError("ineligible account resolved")

    employee_profile = next(
        row.values
        for row in build_rows()
        if row.table == "user_profiles" and row.values.get("employee_id") == EMPLOYEE_ID
    )
    employee_user = cast(uuid.UUID, employee_profile["app_user_id"])
    checks = [
        (
            "UPDATE employees SET active=false WHERE id=:id",
            "UPDATE employees SET active=true WHERE id=:id",
            {"id": EMPLOYEE_ID},
        ),
        (
            "UPDATE employees SET employment_status='Terminated' WHERE id=:id",
            "UPDATE employees SET employment_status='Active' WHERE id=:id",
            {"id": EMPLOYEE_ID},
        ),
        (
            "UPDATE app_users SET status='disabled' WHERE id=:id",
            "UPDATE app_users SET status='active' WHERE id=:id",
            {"id": employee_user},
        ),
    ]
    try:
        for statement, restore, values in checks:
            with engine.begin() as connection:
                connection.execute(text(statement), values)
            await denied()
            with engine.begin() as connection:
                connection.execute(text(restore), values)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO app_users "
                    "(id, identity_issuer, identity_subject, status) "
                    "VALUES (:id, :issuer, :subject, 'active')"
                ),
                {
                    "id": UNLINKED_USER_ID,
                    "issuer": c.SEED_ISSUER,
                    "subject": UNLINKED_SUBJECT,
                },
            )
        await denied(UNLINKED_SUBJECT)
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM app_users WHERE id = :id"),
                {"id": UNLINKED_USER_ID},
            )
        await async_engine.dispose()


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            head = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert head == EXPECTED_HEAD
            function = (
                connection.execute(
                    text(
                        "SELECT p.prosecdef, p.provolatile, p.proconfig, "
                        "pg_get_function_result(p.oid) AS result_type, "
                        "pg_get_functiondef(p.oid) AS definition, "
                        "pg_get_userbyid(p.proowner) AS owner_name, "
                        "has_function_privilege('workloop_runtime', p.oid, 'EXECUTE') "
                        "AS runtime_execute, "
                        "has_function_privilege('workloop_expiry_processing', p.oid, 'EXECUTE') "
                        "AS job_execute, "
                        "NOT EXISTS ("
                        "SELECT 1 FROM aclexplode(p.proacl) AS acl "
                        "WHERE acl.grantee = 0 AND acl.privilege_type = 'EXECUTE'"
                        ") AS public_revoked "
                        "FROM pg_proc AS p "
                        "JOIN pg_namespace AS n ON n.oid = p.pronamespace "
                        "WHERE n.nspname = 'public' "
                        "AND p.proname = 'current_employee_reporting_manager' "
                        "AND p.pronargs = 0"
                    )
                )
                .mappings()
                .one()
            )
            assert function["prosecdef"] is True
            assert function["provolatile"] == "s"
            assert function["proconfig"] == ["search_path=pg_catalog, public, pg_temp"]
            assert (
                function["result_type"] == "TABLE(id uuid, name text, job_title text)"
            )
            assert function["owner_name"] == "workloop_migration"
            assert function["runtime_execute"] is True
            assert function["job_execute"] is False
            assert function["public_revoked"] is True
            definition = function["definition"].lower()
            for required in (
                "security definer",
                "session_user",
                "resolve_workloop_principal",
                "workloop_business_date",
                "workloop_employee_id",
                "workloop_branch_id",
            ):
                assert required in definition
            migration_rows = connection.execute(
                text("SELECT count(*) FROM public.current_employee_reporting_manager()")
            ).scalar_one()
            assert migration_rows == 0
            for index, history_id in enumerate(HISTORY_IDS):
                connection.execute(
                    text(
                        "INSERT INTO employee_job_history "
                        "(id,company_id,branch_id,employee_id,changed_at,change_type,old_value,"
                        "new_value,reason) VALUES "
                        "(:id,:company_id,:branch_id,:employee_id,:changed_at,'title_change',"
                        ":old_value,:new_value,'Synthetic Phase 7D proof')"
                    ),
                    {
                        "id": history_id,
                        "company_id": c.COMPANY_ID[c.HORIZON],
                        "branch_id": c.BRANCH_DXB,
                        "employee_id": EMPLOYEE_ID,
                        "changed_at": datetime(2026, 9, 10, 8, index, tzinfo=UTC),
                        "old_value": f"Role {index}",
                        "new_value": f"Role {index + 1}",
                    },
                )
        evidence = asyncio.run(verify_services(engine))
        asyncio.run(verify_ineligible_accounts(engine))
        evidence["alembicHead"] = EXPECTED_HEAD
        digest = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        evidence["syntheticState"] = digest
        print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM employee_job_history WHERE id IN (:first_id, :second_id)"
                ),
                {"first_id": HISTORY_IDS[0], "second_id": HISTORY_IDS[1]},
            )
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
