#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import runpy
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import jwt
import psycopg
from app.auth.access_token import (
    AccessTokenClaims,
    AccessTokenError,
    AccessTokenVerifier,
)
from app.auth.application_user import ApplicationUserResolver
from app.auth.scopes import (
    branch_authorization_scope,
    branch_scope_predicate,
    direct_report_authorization_scope,
    direct_report_scope_predicate,
    employee_self_authorization_scope,
    employee_self_scope_predicate,
)
from app.db.authorization_context import (
    AuthorizationBranchUnavailableError,
    AuthorizationTransactionFactory,
)
from app.db.seed import constants as c
from app.models import Base
from app.models.identity import AppRole
from app.repositories.scoped import (
    build_scoped_delete,
    build_scoped_lookup,
    build_scoped_update,
)
from app.schemas.mutations import (
    MutationFieldGuard,
    MutationFieldGuardConfigurationError,
)
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

BASE = runpy.run_path(str(Path(__file__).with_name("verify-phase-5e-rls.py")))
build_rows = BASE["build_rows"]
apply_rows = BASE["apply_rows"]
clean = BASE["clean"]
validate = BASE["validate"]
connect_as = BASE["connect_as"]
human_context = BASE["human_context"]
job_context = BASE["job_context"]
principal_for = BASE["principal_for"]

RAVI = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA = uuid.UUID("21000000-0000-4000-8000-000000000003")
OMAR = uuid.UUID("22000000-0000-4000-8000-000000000001")
LEILA = uuid.UUID("22000000-0000-4000-8000-000000000002")
CEDAR_EMPLOYEE = uuid.UUID("31000000-0000-4000-8000-000000000002")


@dataclass(slots=True)
class ControlContext:
    engine: Any
    runtime: psycopg.Connection[Any]

    def id(self, sql: str, parameters: dict[str, object]) -> uuid.UUID:
        with self.engine.connect() as connection:
            return connection.execute(text(sql), parameters).scalar_one()


def table(name: str) -> Any:
    return Base.metadata.tables[name]


def app_ids(ctx: ControlContext, statement: Any) -> list[uuid.UUID]:
    with ctx.engine.connect() as connection:
        return list(connection.execute(statement).scalars())


def app_branch_predicate(subject: str, branch_id: uuid.UUID, table_name: str) -> Any:
    target = table(table_name)
    principal = principal_for(subject)
    scope = (
        branch_authorization_scope(principal, verified_admin_branch_id=branch_id)
        if principal.role is AppRole.ADMIN
        else branch_authorization_scope(principal)
    )
    return branch_scope_predicate(target.c.company_id, target.c.branch_id, scope)


def app_self_predicate(subject: str, table_name: str) -> Any:
    target = table(table_name)
    scope = employee_self_authorization_scope(principal_for(subject))
    return employee_self_scope_predicate(
        target.c.company_id, target.c.branch_id, target.c.employee_id, scope
    )


def app_report_predicate(subject: str, employee_column: Any) -> Any:
    return direct_report_scope_predicate(
        employee_column, direct_report_authorization_scope(principal_for(subject))
    )


def assert_protected(field: str) -> None:
    try:
        MutationFieldGuard(allowed_input_fields=frozenset({field}))
    except MutationFieldGuardConfigurationError:
        return
    raise AssertionError(
        f"generic mutation unexpectedly accepted protected field {field}"
    )


def runtime_database_url() -> str:
    migration_url = urlsplit(os.environ["MIGRATION_DATABASE_URL"])
    return (
        "postgresql+psycopg://workloop_runtime:"
        f"{quote(os.environ['WORKLOOP_RUNTIME_PASSWORD'], safe='')}@"
        f"{migration_url.hostname}:{migration_url.port}{migration_url.path}"
    )


async def verify_live_admin_branch() -> None:
    engine = create_async_engine(runtime_database_url())
    principal = principal_for("hr.admin@horizon.test")
    claims = AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject="hr.admin@horizon.test",
        audience=("workloop-api",),
        expires_at=2_000_000_000,
        issued_at=1_999_999_000,
        not_before=None,
    )
    factory = AuthorizationTransactionFactory(
        engine=engine,
        setup_timeout_seconds=5,
        clock=lambda: datetime(2026, 9, 6, tzinfo=UTC),
    )
    try:
        async with factory.transaction(
            claims=claims,
            principal=principal,
            verified_admin_branch_id=c.BRANCH_DXB,
        ) as connection:
            rows = (
                await connection.execute(
                    text("SELECT company_id,branch_id FROM employees")
                )
            ).all()
            assert rows
            assert all(
                company_id == c.COMPANY_ID[c.HORIZON] and branch_id == c.BRANCH_DXB
                for company_id, branch_id in rows
            )
        try:
            async with factory.transaction(
                claims=claims,
                principal=principal,
                verified_admin_branch_id=c.BRANCH_SHJ,
            ):
                raise AssertionError("cross-tenant admin branch was accepted")
        except AuthorizationBranchUnavailableError:
            pass
        async with engine.connect() as connection, connection.begin():
            count = (
                await connection.execute(text("SELECT count(*) FROM employees"))
            ).scalar_one()
            assert count == 0
    finally:
        await engine.dispose()


def row_digest(ctx: ControlContext, table_name: str) -> tuple[int, str]:
    with ctx.engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    f"SELECT count(*),coalesce(md5(string_agg(to_jsonb(row_value)::text,',' "
                    f"ORDER BY row_value.id::text)),md5('')) FROM {table_name} AS row_value"
                )
            ).one()
        )


def deny_mutation(
    ctx: ControlContext,
    subject: str,
    sql: str,
    parameters: tuple[object, ...],
    affected_tables: tuple[str, ...],
    *,
    branch_id: uuid.UUID | None = None,
    overrides: dict[str, object | None] | None = None,
) -> None:
    before = {name: row_digest(ctx, name) for name in affected_tables}
    denied = False
    try:
        with human_context(
            ctx.runtime,
            subject,
            branch_id=branch_id,
            overrides=overrides,
        ) as cursor:
            cursor.execute(sql, parameters)
            denied = cursor.fetchone() is None
    except psycopg.Error:
        denied = True
    assert denied
    after = {name: row_digest(ctx, name) for name in affected_tables}
    assert after == before


def rls_empty(
    ctx: ControlContext,
    subject: str,
    sql: str,
    parameters: tuple[object, ...] = (),
    *,
    branch_id: uuid.UUID | None = None,
    overrides: dict[str, object | None] | None = None,
) -> None:
    with human_context(
        ctx.runtime, subject, branch_id=branch_id, overrides=overrides
    ) as cursor:
        cursor.execute(sql, parameters)
        assert cursor.fetchall() == []


def control_01_application(ctx: ControlContext) -> None:
    employees = table("employees")
    predicate = app_branch_predicate("hr.admin@horizon.test", c.BRANCH_DXB, "employees")
    lookup = build_scoped_lookup(employees, employees.c.id, CEDAR_EMPLOYEE, predicate)
    assert app_ids(ctx, lookup) == []
    guard = MutationFieldGuard(allowed_input_fields=frozenset({"phone"}))
    with ctx.engine.connect() as connection:
        transaction = connection.begin()
        assert (
            connection.execute(
                build_scoped_update(
                    employees,
                    employees.c.id,
                    (CEDAR_EMPLOYEE,),
                    predicate,
                    guard.prepare({"phone": "+971500000099"}),
                )
            ).rowcount
            == 0
        )
        assert (
            connection.execute(
                build_scoped_delete(
                    employees, employees.c.id, (CEDAR_EMPLOYEE,), predicate
                )
            ).rowcount
            == 0
        )
        transaction.rollback()
    asyncio.run(verify_live_admin_branch())


def control_01_rls(ctx: ControlContext) -> None:
    rls_empty(
        ctx,
        "hr.admin@horizon.test",
        "SELECT id FROM employees WHERE id=%s",
        (CEDAR_EMPLOYEE,),
        branch_id=c.BRANCH_DXB,
    )
    deny_mutation(
        ctx,
        "hr.admin@horizon.test",
        "UPDATE employees SET phone=phone WHERE id=%s RETURNING id",
        (CEDAR_EMPLOYEE,),
        ("employees",),
        branch_id=c.BRANCH_DXB,
    )
    deny_mutation(
        ctx,
        "hr.admin@horizon.test",
        "DELETE FROM employees WHERE id=%s RETURNING id",
        (CEDAR_EMPLOYEE,),
        ("employees",),
        branch_id=c.BRANCH_DXB,
    )


def control_02_application(ctx: ControlContext) -> None:
    for name in ("payroll_runs", "payroll_entries"):
        target = table(name)
        predicate = app_branch_predicate("hr.admin@horizon.test", c.BRANCH_DXB, name)
        statement = select(target.c.id).where(
            predicate, target.c.company_id == c.COMPANY_ID[c.CEDAR]
        )
        assert app_ids(ctx, statement) == []


def control_02_rls(ctx: ControlContext) -> None:
    for name in ("payroll_runs", "payroll_entries"):
        rls_empty(
            ctx,
            "hr.admin@horizon.test",
            f"SELECT id FROM {name} WHERE company_id=%s",
            (c.COMPANY_ID[c.CEDAR],),
            branch_id=c.BRANCH_DXB,
        )


def control_03_application(ctx: ControlContext) -> None:
    assert_protected("basic_salary")


def control_03_rls(ctx: ControlContext) -> None:
    run_id = ctx.id(
        "SELECT id FROM payroll_runs WHERE company_id=:company ORDER BY id LIMIT 1",
        {"company": c.COMPANY_ID[c.CEDAR]},
    )
    deny_mutation(
        ctx,
        "hr.admin@horizon.test",
        "SELECT public.replace_payroll_entries(%s,'[]'::jsonb)",
        (run_id,),
        ("payroll_entries",),
        branch_id=c.BRANCH_DXB,
    )


def control_04_application(ctx: ControlContext) -> None:
    assert_protected("outstanding_balance")


def control_04_rls(ctx: ControlContext) -> None:
    advance_id = ctx.id(
        "SELECT id FROM salary_advances WHERE company_id=:company ORDER BY id LIMIT 1",
        {"company": c.COMPANY_ID[c.CEDAR]},
    )
    run_id = ctx.id(
        "SELECT id FROM payroll_runs WHERE company_id=:company ORDER BY id LIMIT 1",
        {"company": c.COMPANY_ID[c.CEDAR]},
    )
    deny_mutation(
        ctx,
        "hr.admin@horizon.test",
        "SELECT public.record_advance_repayment(%s,%s,%s,1.00,DATE '2026-09-06')",
        (advance_id, run_id, uuid.uuid4()),
        ("salary_advances", "advance_repayments"),
        branch_id=c.BRANCH_DXB,
    )


def control_05_application(ctx: ControlContext) -> None:
    assert_protected("admin_approved_by_app_user_id")


def control_05_rls(ctx: ControlContext) -> None:
    swap_id = ctx.id(
        "SELECT id FROM shift_swap_requests WHERE company_id=:company ORDER BY id LIMIT 1",
        {"company": c.COMPANY_ID[c.CEDAR]},
    )
    deny_mutation(
        ctx,
        "hr.admin@horizon.test",
        "SELECT public.admin_execute_shift_swap(%s,%s)",
        (swap_id, principal_for("hr.admin@horizon.test").app_user_id),
        ("shift_swap_requests", "roster_assignments", "audit_events"),
        branch_id=c.BRANCH_DXB,
    )


def control_06_application(ctx: ControlContext) -> None:
    requests = table("leave_requests")
    request_id = ctx.id(
        "SELECT request.id FROM leave_requests AS request "
        "JOIN employees AS employee ON employee.id=request.employee_id "
        "WHERE employee.reporting_manager_id=:manager ORDER BY request.id LIMIT 1",
        {"manager": OMAR},
    )
    statement = select(requests.c.id).where(
        requests.c.id == request_id,
        app_report_predicate("aisha.manager@horizon.test", requests.c.employee_id),
    )
    assert app_ids(ctx, statement) == []


def control_06_rls(ctx: ControlContext) -> None:
    request_id = ctx.id(
        "SELECT request.id FROM leave_requests AS request "
        "JOIN employees AS employee ON employee.id=request.employee_id "
        "WHERE employee.reporting_manager_id=:manager ORDER BY request.id LIMIT 1",
        {"manager": OMAR},
    )
    deny_mutation(
        ctx,
        "aisha.manager@horizon.test",
        "UPDATE leave_requests SET status='ManagerApproved' WHERE id=%s RETURNING id",
        (request_id,),
        ("leave_requests",),
    )


def control_07_application(ctx: ControlContext) -> None:
    claims = table("expense_claims")
    statement = select(claims.c.id).where(
        claims.c.company_id == c.COMPANY_ID[c.CEDAR],
        app_report_predicate("aisha.manager@horizon.test", claims.c.employee_id),
    )
    assert app_ids(ctx, statement) == []


def control_07_rls(ctx: ControlContext) -> None:
    claim_id = ctx.id(
        "SELECT id FROM expense_claims WHERE company_id=:company ORDER BY id LIMIT 1",
        {"company": c.COMPANY_ID[c.CEDAR]},
    )
    deny_mutation(
        ctx,
        "aisha.manager@horizon.test",
        "UPDATE expense_claims SET amount=amount WHERE id=%s RETURNING id",
        (claim_id,),
        ("expense_claims",),
    )


def control_08_application(ctx: ControlContext) -> None:
    sections = table("appraisal_sections")
    appraisals = table("appraisals")
    source = sections.join(appraisals, appraisals.c.id == sections.c.appraisal_id)
    statement = (
        select(sections.c.id)
        .select_from(source)
        .where(
            appraisals.c.employee_id.in_((LEILA, CEDAR_EMPLOYEE)),
            app_report_predicate(
                "aisha.manager@horizon.test", appraisals.c.employee_id
            ),
        )
    )
    assert app_ids(ctx, statement) == []


def control_08_rls(ctx: ControlContext) -> None:
    for employee_id in (LEILA, CEDAR_EMPLOYEE):
        appraisal_id = ctx.id(
            "SELECT id FROM appraisals WHERE employee_id=:employee ORDER BY id LIMIT 1",
            {"employee": employee_id},
        )
        deny_mutation(
            ctx,
            "aisha.manager@horizon.test",
            "UPDATE appraisals SET status=status WHERE id=%s RETURNING id",
            (appraisal_id,),
            ("appraisals",),
        )
        deny_mutation(
            ctx,
            "aisha.manager@horizon.test",
            "INSERT INTO appraisal_sections(id,company_id,branch_id,appraisal_id,"
            "section_name,weight,sort_order) SELECT %s,company_id,branch_id,id,'Denied',1,99 "
            "FROM appraisals WHERE id=%s RETURNING id",
            (uuid.uuid4(), appraisal_id),
            ("appraisal_sections",),
        )


def control_09_application(ctx: ControlContext) -> None:
    for name in (
        "payslips",
        "attendance_records",
        "employee_documents",
        "salary_advances",
        "expense_claims",
        "appraisals",
    ):
        target = table(name)
        statement = select(target.c.id).where(
            target.c.employee_id == MARIA,
            app_self_predicate("ravi.employee@horizon.test", name),
        )
        assert app_ids(ctx, statement) == []


def control_09_rls(ctx: ControlContext) -> None:
    for name in (
        "payslips",
        "attendance_records",
        "employee_documents",
        "salary_advances",
        "expense_claims",
        "appraisals",
    ):
        rls_empty(
            ctx,
            "ravi.employee@horizon.test",
            f"SELECT id FROM {name} WHERE employee_id=%s",
            (MARIA,),
        )


def control_10_application(ctx: ControlContext) -> None:
    documents = table("employee_documents")
    statement = select(documents.c.storage_path).where(
        documents.c.employee_id == MARIA,
        app_self_predicate("ravi.employee@horizon.test", "employee_documents"),
    )
    assert app_ids(ctx, statement) == []


def control_11_application(ctx: ControlContext) -> None:
    claims = table("expense_claims")
    statement = select(claims.c.id).where(
        app_self_predicate("ravi.employee@horizon.test", "expense_claims"),
        claims.c.status == "draft",
        claims.c.employee_id == RAVI,
    )
    approved = ctx.id(
        "SELECT id FROM expense_claims WHERE employee_id=:employee AND status='approved' "
        "ORDER BY id LIMIT 1",
        {"employee": RAVI},
    )
    assert app_ids(ctx, statement.where(claims.c.id == approved)) == []


def control_11_rls(ctx: ControlContext) -> None:
    claim_id = ctx.id(
        "SELECT id FROM expense_claims WHERE employee_id=:employee AND status='approved' "
        "ORDER BY id LIMIT 1",
        {"employee": RAVI},
    )
    deny_mutation(
        ctx,
        "ravi.employee@horizon.test",
        "DELETE FROM expense_claims WHERE id=%s RETURNING id",
        (claim_id,),
        ("expense_claims",),
    )


def control_12_application(ctx: ControlContext) -> None:
    advances = table("salary_advances")
    scope = app_self_predicate("ravi.employee@horizon.test", "salary_advances")
    for status, employee_id in (("active", RAVI), ("settled", LEILA)):
        target_id = ctx.id(
            "SELECT id FROM salary_advances WHERE employee_id=:employee AND status=:status "
            "ORDER BY id LIMIT 1",
            {"employee": employee_id, "status": status},
        )
        statement = select(advances.c.id).where(
            scope,
            advances.c.status == "pending",
            advances.c.id == target_id,
        )
        assert app_ids(ctx, statement) == []


def control_12_rls(ctx: ControlContext) -> None:
    for status, employee_id in (("active", RAVI), ("settled", LEILA)):
        target_id = ctx.id(
            "SELECT id FROM salary_advances WHERE employee_id=:employee AND status=:status "
            "ORDER BY id LIMIT 1",
            {"employee": employee_id, "status": status},
        )
        deny_mutation(
            ctx,
            "ravi.employee@horizon.test",
            "UPDATE salary_advances SET status='cancelled',rejection_reason='x' "
            "WHERE id=%s RETURNING id",
            (target_id,),
            ("salary_advances",),
        )


def control_13_application(ctx: ControlContext) -> None:
    employees = table("employees")
    predicate = app_branch_predicate(
        "ravi.employee@horizon.test", c.BRANCH_DXB, "employees"
    )
    assert (
        app_ids(
            ctx,
            select(employees.c.id).where(predicate, employees.c.id == CEDAR_EMPLOYEE),
        )
        == []
    )


def control_13_rls(ctx: ControlContext) -> None:
    before = row_digest(ctx, "shift_swap_requests")
    rls_empty(
        ctx,
        "ravi.employee@horizon.test",
        "SELECT id FROM employees WHERE id=%s",
        (CEDAR_EMPLOYEE,),
    )
    assert row_digest(ctx, "shift_swap_requests") == before


def control_14_application(ctx: ControlContext) -> None:
    for name in (
        "employees",
        "payroll_runs",
        "roster_assignments",
        "shift_swap_requests",
        "incident_reports",
    ):
        target = table(name)
        predicate = app_branch_predicate("hr.admin@horizon.test", c.BRANCH_DXB, name)
        assert (
            app_ids(
                ctx,
                select(target.c.id).where(
                    predicate, target.c.branch_id == c.BRANCH_AUH
                ),
            )
            == []
        )


def control_14_rls(ctx: ControlContext) -> None:
    for name in (
        "employees",
        "payroll_runs",
        "roster_assignments",
        "shift_swap_requests",
        "incident_reports",
    ):
        rls_empty(
            ctx,
            "hr.admin@horizon.test",
            f"SELECT id FROM {name} WHERE branch_id=%s",
            (c.BRANCH_AUH,),
            branch_id=c.BRANCH_DXB,
        )


def control_15_application(ctx: ControlContext) -> None:
    for name in (
        "leave_requests",
        "expense_claims",
        "assets",
        "training_records",
        "appraisals",
        "departments",
        "attendance_records",
    ):
        target = table(name)
        predicate = app_branch_predicate("hr.admin@horizon.test", c.BRANCH_DXB, name)
        assert (
            app_ids(
                ctx,
                select(target.c.id).where(
                    predicate, target.c.branch_id == c.BRANCH_AUH
                ),
            )
            == []
        )


def control_15_rls(ctx: ControlContext) -> None:
    for name in (
        "leave_requests",
        "expense_claims",
        "assets",
        "training_records",
        "appraisals",
        "departments",
        "attendance_records",
    ):
        rls_empty(
            ctx,
            "hr.admin@horizon.test",
            f"SELECT id FROM {name} WHERE branch_id=%s",
            (c.BRANCH_AUH,),
            branch_id=c.BRANCH_DXB,
        )


async def resolve_leila(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        resolver = ApplicationUserResolver(
            engine=engine, issuer=c.SEED_ISSUER, timeout_seconds=5.0
        )
        principal = await resolver.resolve(
            issuer=c.SEED_ISSUER, subject="leila.employee@horizon.test"
        )
        assert principal.company_id == c.COMPANY_ID[c.HORIZON]
        assert principal.branch_id == c.BRANCH_AUH
        assert principal.employee_id == LEILA
        assert principal.role is AppRole.EMPLOYEE
    finally:
        await engine.dispose()


def control_16_application(ctx: ControlContext) -> None:
    asyncio.run(resolve_leila(runtime_database_url()))


def control_16_rls(ctx: ControlContext) -> None:
    with human_context(ctx.runtime, "leila.employee@horizon.test") as cursor:
        cursor.execute("SELECT id FROM employees WHERE id=%s", (LEILA,))
        assert cursor.fetchone() == (LEILA,)
    rls_empty(
        ctx,
        "leila.employee@horizon.test",
        "SELECT id FROM employees WHERE id=%s",
        (LEILA,),
        overrides={"workloop.company_id": c.COMPANY_ID[c.CEDAR]},
    )


async def reject_expired_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "phase5h-key", "alg": "RS256", "use": "sig"})

    def jwks(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": [public_jwk]}, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(jwks)) as client:
        verifier = AccessTokenVerifier(
            issuer="https://phase5h.invalid/realms/workloop",
            audience="workloop-api",
            jwks_url="https://phase5h.invalid/certs",
            http_client=client,
            total_timeout_seconds=1,
            cache_ttl_seconds=60,
            refresh_cooldown_seconds=1,
        )
        now = int(time.time())
        token = jwt.encode(
            {
                "iss": "https://phase5h.invalid/realms/workloop",
                "sub": "synthetic-expired-caller",
                "aud": "workloop-api",
                "exp": now - 1,
                "iat": now - 60,
                "typ": "Bearer",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "phase5h-key", "typ": "JWT"},
        )
        try:
            await verifier.verify(token)
        except AccessTokenError:
            return
    raise AssertionError("expired access token produced a new authorization")


def control_17_application(ctx: ControlContext) -> None:
    asyncio.run(reject_expired_token())


def control_18_application(ctx: ControlContext) -> None:
    documents = table("employee_documents")
    predicate = app_branch_predicate(
        "hr.admin@horizon.test", c.BRANCH_DXB, "employee_documents"
    )
    statement = select(documents.c.storage_path).where(
        predicate, documents.c.company_id == c.COMPANY_ID[c.CEDAR]
    )
    assert app_ids(ctx, statement) == []


def verify_forged_and_stale_manager_context(ctx: ControlContext) -> None:
    aisha = principal_for("aisha.manager@horizon.test")
    with ctx.engine.connect() as connection:
        request_id = connection.execute(
            text(
                "SELECT request.id FROM leave_requests AS request "
                "JOIN employees AS employee ON employee.id=request.employee_id "
                "WHERE employee.reporting_manager_id=:manager "
                "AND request.status='Approved' ORDER BY request.id LIMIT 1"
            ),
            {"manager": aisha.employee_id},
        ).scalar_one()
        expense_id, employee_id = connection.execute(
            text(
                "SELECT claim.id,claim.employee_id FROM expense_claims AS claim "
                "JOIN employees AS employee ON employee.id=claim.employee_id "
                "WHERE employee.reporting_manager_id=:manager "
                "AND claim.status='manager_approved' "
                "AND claim.manager_approved_by_app_user_id=:actor "
                "ORDER BY claim.id LIMIT 1"
            ),
            {"manager": aisha.employee_id, "actor": aisha.app_user_id},
        ).one()
    deny_mutation(
        ctx,
        "aisha.manager@horizon.test",
        "SELECT public.create_workflow_notification('leave_approved',%s)",
        (str(request_id),),
        ("notifications",),
        overrides={"workloop.employee_id": RAVI},
    )
    deny_mutation(
        ctx,
        "aisha.manager@horizon.test",
        "SELECT public.append_audit_event('expense_approved','expense_claim',%s,"
        "ARRAY['status']::text[],'Manager approval',"
        '\'{"transition":"submitted_to_manager_approved"}\'::jsonb)',
        (expense_id,),
        ("audit_events",),
        overrides={"workloop.employee_id": RAVI},
    )
    with ctx.engine.begin() as connection:
        old_manager = connection.execute(
            text("SELECT reporting_manager_id FROM employees WHERE id=:id"),
            {"id": employee_id},
        ).scalar_one()
        connection.execute(
            text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"),
            {"manager": RAVI, "id": employee_id},
        )
    try:
        deny_mutation(
            ctx,
            "aisha.manager@horizon.test",
            "SELECT public.append_audit_event('expense_approved','expense_claim',%s,"
            "ARRAY['status']::text[],'Stale manager approval',"
            '\'{"transition":"submitted_to_manager_approved"}\'::jsonb)',
            (expense_id,),
            ("audit_events",),
        )
    finally:
        with ctx.engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"),
                {"manager": old_manager, "id": employee_id},
            )


def expect_expiry_notification_denied(
    ctx: ControlContext,
    expiry: psycopg.Connection[Any],
    values: tuple[object, ...],
) -> None:
    before = row_digest(ctx, "notifications")
    try:
        with job_context(
            expiry, company_id=c.COMPANY_ID[c.HORIZON], branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "INSERT INTO notifications(company_id,branch_id,recipient_app_user_id,type,"
                "title,body,related_entity_type,related_entity_id) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s)",
                values,
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("invalid expiry notification was accepted")
    assert row_digest(ctx, "notifications") == before


def expect_expiry_audit_denied(
    ctx: ControlContext,
    expiry: psycopg.Connection[Any],
    source_id: uuid.UUID,
    metadata: str,
) -> None:
    before = row_digest(ctx, "audit_events")
    try:
        with job_context(
            expiry, company_id=c.COMPANY_ID[c.HORIZON], branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "INSERT INTO audit_events(company_id,branch_id,actor_kind,system_actor_key,"
                "action,entity_type,entity_id,changed_fields,reason,metadata) VALUES "
                "(%s,%s,'scheduled_job','expiry_processing','expiry_notification_created',"
                "'employee_document',%s,ARRAY['type','recipient_app_user_id']::text[],"
                "'Expiry notification created',%s::jsonb)",
                (c.COMPANY_ID[c.HORIZON], c.BRANCH_DXB, source_id, metadata),
            )
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("false expiry audit metadata was accepted")
    assert row_digest(ctx, "audit_events") == before


def verify_expiry_negative_paths(ctx: ControlContext) -> None:
    expiry = connect_as("workloop_expiry_processing")
    admin_id = principal_for("hr.admin@horizon.test").app_user_id
    ravi_id = principal_for("ravi.employee@horizon.test").app_user_id
    with ctx.engine.connect() as connection:
        source_id, source_date, employee_id = connection.execute(
            text(
                "SELECT document.id,document.expiry_date,document.employee_id "
                "FROM employee_documents AS document JOIN employees AS employee "
                "ON employee.id=document.employee_id "
                "WHERE document.company_id=:company AND document.branch_id=:branch "
                "AND document.status='verified' AND employee.active "
                "AND document.document_type NOT IN ('DHA Licence','DOH Licence','MOH Licence',"
                "'BLS Certificate','ACLS Certificate','PALS Certificate','NRP Certificate',"
                "'CME Certificate') AND document.expiry_date BETWEEN DATE '2026-09-06' "
                "AND DATE '2026-09-06' + 60 ORDER BY document.id LIMIT 1"
            ),
            {"company": c.COMPANY_ID[c.HORIZON], "branch": c.BRANCH_DXB},
        ).one()
    days = (source_date - date(2026, 9, 6)).days
    threshold = 14 if days <= 14 else 30 if days <= 30 else 60
    related_id = f"{source_id}:document:{threshold}"
    base = (
        c.COMPANY_ID[c.HORIZON],
        c.BRANCH_DXB,
        admin_id,
        "document_expiry",
        "Document expiring",
        "Review this expiry item.",
        "employee_document",
        related_id,
    )
    try:
        expect_expiry_notification_denied(ctx, expiry, (*base[:2], ravi_id, *base[3:]))
        expect_expiry_notification_denied(
            ctx, expiry, (*base[:4], "Forged title", *base[5:])
        )
        expect_expiry_notification_denied(
            ctx, expiry, (*base[:7], f"{source_id}:document:90")
        )
        for source_change in (
            {"status": "pending_verification"},
            {"expiry_date": date(2026, 9, 5)},
            {"expiry_date": date(2027, 1, 1)},
        ):
            with ctx.engine.begin() as connection:
                original = connection.execute(
                    text(
                        "SELECT status,expiry_date FROM employee_documents WHERE id=:id"
                    ),
                    {"id": source_id},
                ).one()
                connection.execute(
                    text(
                        "UPDATE employee_documents SET "
                        + ",".join(f"{key}=:{key}" for key in source_change)
                        + " WHERE id=:id"
                    ),
                    {"id": source_id, **source_change},
                )
            try:
                expect_expiry_notification_denied(ctx, expiry, base)
            finally:
                with ctx.engine.begin() as connection:
                    connection.execute(
                        text(
                            "UPDATE employee_documents SET status=:status,expiry_date=:expiry "
                            "WHERE id=:id"
                        ),
                        {
                            "status": original.status,
                            "expiry": original.expiry_date,
                            "id": source_id,
                        },
                    )
        with ctx.engine.begin() as connection:
            connection.execute(
                text("UPDATE employees SET active=false WHERE id=:id"),
                {"id": employee_id},
            )
        try:
            expect_expiry_notification_denied(ctx, expiry, base)
        finally:
            with ctx.engine.begin() as connection:
                connection.execute(
                    text("UPDATE employees SET active=true WHERE id=:id"),
                    {"id": employee_id},
                )
        with ctx.engine.begin() as connection:
            connection.execute(
                text("UPDATE app_users SET status='disabled' WHERE id=:id"),
                {"id": admin_id},
            )
        try:
            expect_expiry_notification_denied(ctx, expiry, base)
        finally:
            with ctx.engine.begin() as connection:
                connection.execute(
                    text("UPDATE app_users SET status='active' WHERE id=:id"),
                    {"id": admin_id},
                )
        with job_context(
            expiry, company_id=c.COMPANY_ID[c.HORIZON], branch_id=c.BRANCH_DXB
        ) as cursor:
            cursor.execute(
                "INSERT INTO notifications(company_id,branch_id,recipient_app_user_id,type,"
                "title,body,related_entity_type,related_entity_id) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s)",
                base,
            )
        wrong_date = date(2026, 9, 6).isoformat()
        expect_expiry_audit_denied(
            ctx,
            expiry,
            source_id,
            (
                '{"threshold_days":%d,"source_date":"%s","source_kind":"document",'
                '"recipient_app_user_id":"%s"}'
            )
            % (threshold, wrong_date, admin_id),
        )
        expect_expiry_audit_denied(
            ctx,
            expiry,
            source_id,
            (
                '{"threshold_days":%d,"source_date":"%s","source_kind":"document",'
                '"recipient_app_user_id":"%s"}'
            )
            % (threshold, source_date.isoformat(), ravi_id),
        )
    finally:
        with ctx.engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM audit_events WHERE entity_id=:source "
                    "AND action='expiry_notification_created'"
                ),
                {"source": source_id},
            )
            connection.execute(
                text("DELETE FROM notifications WHERE related_entity_id=:related"),
                {"related": related_id},
            )
        expiry.close()


def verify_audit_context_constraint_and_branches(ctx: ControlContext) -> None:
    with ctx.engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    "INSERT INTO audit_events(company_id,actor_kind,action,entity_type,entity_id,"
                    "changed_fields,reason,metadata) VALUES "
                    "(:company,'scheduled_job','invalid_actor','test',:id,ARRAY['x'],"
                    "'Invalid actor','{}'::jsonb)"
                ),
                {"company": c.COMPANY_ID[c.HORIZON], "id": uuid.uuid4()},
            )
        except IntegrityError:
            transaction.rollback()
        else:
            transaction.rollback()
            raise AssertionError("null system actor key satisfied the audit constraint")

    rls_empty(
        ctx,
        "hr.admin@horizon.test",
        "SELECT id FROM audit_events",
        branch_id=c.BRANCH_DXB,
        overrides={"workloop.business_date": "not-a-date"},
    )

    created_branch = uuid.uuid4()
    deleted_branch = uuid.uuid4()
    with ctx.engine.begin() as connection:
        for branch_id, name in (
            (created_branch, "Phase 5H created branch"),
            (deleted_branch, "Phase 5H deleted branch"),
        ):
            connection.execute(
                text(
                    "INSERT INTO branches(id,company_id,name) VALUES(:id,:company,:name)"
                ),
                {"id": branch_id, "company": c.COMPANY_ID[c.HORIZON], "name": name},
            )
    try:
        with human_context(ctx.runtime, "hr.admin@horizon.test") as cursor:
            cursor.execute(
                "SELECT public.append_audit_event('branch_created','branch',%s,"
                "ARRAY['id']::text[],'Branch created','{}'::jsonb)",
                (created_branch,),
            )
            assert cursor.fetchone()[0] is not None
        deny_mutation(
            ctx,
            "hr.admin@horizon.test",
            "SELECT public.append_audit_event('branch_created','branch',%s,"
            "ARRAY['id']::text[],'Wrong branch context','{}'::jsonb)",
            (created_branch,),
            ("audit_events",),
            branch_id=created_branch,
        )
        with human_context(
            ctx.runtime, "hr.admin@horizon.test", branch_id=deleted_branch
        ) as cursor:
            cursor.execute(
                "SELECT public.append_audit_event('branch_deleted','branch',%s,"
                "ARRAY['id']::text[],'Branch deleted','{}'::jsonb)",
                (deleted_branch,),
            )
            assert cursor.fetchone()[0] is not None
    finally:
        with ctx.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM audit_events WHERE entity_id IN (:created,:deleted)"),
                {"created": created_branch, "deleted": deleted_branch},
            )
            connection.execute(
                text("DELETE FROM branches WHERE id IN (:created,:deleted)"),
                {"created": created_branch, "deleted": deleted_branch},
            )


APPLICATION_CONTROLS = {
    1: control_01_application,
    2: control_02_application,
    3: control_03_application,
    4: control_04_application,
    5: control_05_application,
    6: control_06_application,
    7: control_07_application,
    8: control_08_application,
    9: control_09_application,
    10: control_10_application,
    11: control_11_application,
    12: control_12_application,
    13: control_13_application,
    14: control_14_application,
    15: control_15_application,
    16: control_16_application,
    17: control_17_application,
    18: control_18_application,
}

RLS_CONTROLS = {
    1: control_01_rls,
    2: control_02_rls,
    3: control_03_rls,
    4: control_04_rls,
    5: control_05_rls,
    6: control_06_rls,
    7: control_07_rls,
    8: control_08_rls,
    9: control_09_rls,
    11: control_11_rls,
    12: control_12_rls,
    13: control_13_rls,
    14: control_14_rls,
    15: control_15_rls,
    16: control_16_rls,
}


def main() -> None:
    database_url = os.environ["MIGRATION_DATABASE_URL"]
    engine = create_engine(database_url)
    runtime = connect_as("workloop_runtime")
    rows = build_rows()
    completed: list[str] = []
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
        for control_id, assertion in APPLICATION_CONTROLS.items():
            assertion(ControlContext(engine, runtime))
            completed.append(f"{control_id}A")
        for control_id, assertion in RLS_CONTROLS.items():
            assertion(ControlContext(engine, runtime))
            completed.append(f"{control_id}R")
        context = ControlContext(engine, runtime)
        verify_forged_and_stale_manager_context(context)
        verify_expiry_negative_paths(context)
        verify_audit_context_constraint_and_branches(context)
    finally:
        runtime.close()
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()
    print("Phase 5H focused controls passed: " + ",".join(completed))


if __name__ == "__main__":
    main()
