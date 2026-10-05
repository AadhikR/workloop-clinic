"""Exercise staff training authority and own manager payslip delivery on a disposable database."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

from alembic import command as alembic_command
from alembic.config import Config
from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.core.config import Settings
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.development_api import (
    cancel_training_record,
    complete_self_training_record,
    complete_training_record,
    start_training_record,
)
from app.main import create_app
from app.rendered_output_api import (
    download_completed_request_letter_pdf,
    download_self_payslip_pdf,
)
from app.schemas.development import (
    TrainingCompleteRequest,
    TrainingSelfCompleteRequest,
    TrainingStaffCreateRequest,
    VersionRequest,
)
from app.services.development import DevelopmentService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from starlette.requests import Request

BRANCH = seed.BRANCH_DXB
MANAGER_PAYSLIP = uuid.UUID("e5000000-0000-4000-8000-000000000201")
MANAGER_LETTER = uuid.UUID("e5000000-0000-4000-8000-000000000202")
MANAGER_CUSTOM = uuid.UUID("e5000000-0000-4000-8000-000000000203")
SUBJECTS = (
    "ravi.employee@horizon.test",
    "aisha.manager@horizon.test",
    "hr.admin@horizon.test",
)


def url(user: str, variable: str) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=os.environ[variable],
        host=os.environ.get("WORKLOOP_POSTGRES_HOST", "postgres"),
        database="workloop",
    )


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=seed.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


async def denied(operation: Awaitable[Any], *codes: str) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code in codes, error.code
        return
    except HTTPException as error:
        assert error.detail["code"] in codes, error.detail
        return
    raise AssertionError("a denied operation succeeded")


async def database_denied(operation: Awaitable[Any], sqlstate: str) -> None:
    try:
        await operation
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) == sqlstate
        return
    raise AssertionError("a protected database write succeeded")


async def main() -> None:
    if os.environ.get("RESTORATION_E_DISPOSABLE") != "true":
        raise RuntimeError("explicit disposable database confirmation required")
    migration = create_engine(url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD"))
    runtime = create_async_engine(url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD"))
    control = create_async_engine(
        url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    with migration.begin() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "e2c4f6a8b0d3"
        )
        connection.execute(
            text("DELETE FROM idempotency_records WHERE company_id=:company"),
            {"company": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text("DELETE FROM audit_events WHERE company_id=:company"),
            {"company": seed.COMPANY_ID[seed.HORIZON]},
        )
        connection.execute(
            text("DELETE FROM training_records WHERE training_title=:title"),
            {"title": "Part E synthetic personal training"},
        )
        connection.execute(
            text("DELETE FROM payslips WHERE id=:id"), {"id": MANAGER_PAYSLIP}
        )
        connection.execute(
            text("DELETE FROM letter_requests WHERE id IN (:letter,:custom)"),
            {"letter": MANAGER_LETTER, "custom": MANAGER_CUSTOM},
        )
        clean(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        security = connection.execute(
            text(
                "SELECT r.rolname,p.prosecdef,p.proconfig,"
                "has_function_privilege('workloop_runtime',p.oid,'EXECUTE'),"
                "EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl,"
                "acldefault('f',p.proowner))) acl WHERE acl.grantee=0 "
                "AND acl.privilege_type='EXECUTE') "
                "FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner "
                "WHERE p.proname='transition_training_record'"
            )
        ).one()
        assert security[0] == "workloop_migration" and security[1]
        assert "search_path=pg_catalog, public, pg_temp" in security[2]
        assert security[3] and not security[4]
    resolver = ApplicationUserResolver(
        engine=runtime, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    principals = [
        await resolver.resolve(issuer=seed.SEED_ISSUER, subject=value)
        for value in SUBJECTS
    ]
    employee, manager, admin = principals
    assert employee.employee_id and manager.employee_id
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    app = create_app()
    app.state.settings = Settings()
    app.state.authorized_service_executor = executor

    def request(key: uuid.UUID | None = None) -> Request:
        return Request(
            {
                "type": "http",
                "app": app,
                "headers": []
                if key is None
                else [
                    (b"idempotency-key", str(key).encode()),
                ],
                "query_string": b"",
                "state": {"correlation_id": str(uuid.uuid4())},
            }
        )

    async def run(
        index: int, operation: Callable[[AsyncConnection], Awaitable[Any]]
    ) -> Any:
        return await executor.execute(
            claims=claims(SUBJECTS[index]),
            principal=principals[index],
            selected_admin_branch_id=BRANCH if index == 2 else None,
            operation=operation,
        )

    def service(connection: AsyncConnection) -> DevelopmentService:
        return DevelopmentService(
            connection, scanner_definition="synthetic-v1", object_key_hmac_key=b"E" * 32
        )

    async def create(index: int = 0) -> Any:
        return await run(
            index,
            lambda connection: service(connection).create_training(
                principals[index],
                BRANCH,
                TrainingStaffCreateRequest.model_validate(
                    {
                        "trainingTitle": "Part E synthetic personal training",
                        "trainingType": "external",
                        "provider": "Synthetic centre",
                        "startDate": "2026-08-20",
                        "endDate": None,
                        "durationHours": "2.00",
                        "notes": "Synthetic evidence",
                    }
                ),
                scope="self",
            ),
        )

    async def command(
        function: Any,
        item: Any,
        body: Any,
        index: int = 0,
        key: uuid.UUID | None = None,
    ) -> Any:
        return await function(
            item.id,
            request(key or uuid.uuid4()),
            body,
            claims(SUBJECTS[index]),
            principals[index],
            str(BRANCH) if index == 2 else None,
        )

    def version(item: Any) -> VersionRequest:
        return VersionRequest(expected_updated_at=item.updated_at)

    def result(item: Any, **extra: Any) -> TrainingSelfCompleteRequest:
        return TrainingSelfCompleteRequest.model_validate(
            {
                "endDate": "2026-08-21",
                "durationHours": "2.00",
                "score": "92%",
                "passed": True,
                "expectedUpdatedAt": item.updated_at,
                **extra,
            }
        )

    def snapshot(item: Any) -> tuple[Any, ...]:
        with migration.connect() as connection:
            return tuple(
                connection.execute(
                    text(
                        "SELECT status,result_verified,is_cme,passed,score,updated_at "
                        "FROM training_records WHERE id=:id"
                    ),
                    {"id": item.id},
                ).one()
            )

    created = await create()
    async with runtime.begin() as connection:
        assert (
            await connection.scalar(
                text("SELECT transition_training_record(:id,:version,'start')"),
                {"id": created.id, "version": created.updated_at},
            )
            == "operation_not_permitted"
        )
    await denied(
        start_training_record(
            created.id,
            request(uuid.uuid4()),
            version(created),
            claims(SUBJECTS[0]),
            employee,
            str(BRANCH),
        ),
        "operation_not_permitted",
    )
    await denied(
        command(complete_self_training_record, created, result(created), index=1),
        "operation_not_permitted",
    )
    await denied(
        command(complete_self_training_record, created, result(created), index=2),
        "operation_not_permitted",
    )
    with migration.connect() as connection:
        controls = connection.execute(
            text("SELECT id,updated_at FROM training_records WHERE branch_id<>:branch"),
            {"branch": BRANCH},
        ).all()
    assert len(controls) >= 2
    for record_id, updated_at in controls:
        record = SimpleNamespace(id=record_id, updated_at=updated_at)
        await denied(
            command(start_training_record, record, version(record)),
            "resource_not_found",
        )
    baseline = await run(
        0, lambda connection: service(connection).self_cme(employee, BRANCH, 2026)
    )
    start_key = uuid.uuid4()
    started = await command(
        start_training_record, created, version(created), key=start_key
    )
    replay = await command(
        start_training_record, created, version(created), key=start_key
    )
    assert (
        json.loads(started.body) == json.loads(replay.body)
        and replay.headers["idempotency-replayed"] == "true"
    )
    await denied(
        command(start_training_record, created, version(created)), "state_conflict"
    )
    started_item = await run(
        0,
        lambda connection: service(connection).get_training(
            employee,
            BRANCH,
            created.id,
            scope="self",
        ),
    )
    await denied(
        command(
            complete_self_training_record,
            started_item,
            result(started_item, endDate="2099-01-01"),
        ),
        "validation_failed",
    )
    await denied(
        command(
            complete_self_training_record,
            started_item,
            result(started_item, endDate="2026-08-19"),
        ),
        "validation_failed",
    )
    frozen = snapshot(created)

    async def forge(connection: AsyncConnection) -> None:
        await connection.execute(
            text(
                "UPDATE training_records SET is_cme=true,passed=true,score='trusted' WHERE id=:id"
            ),
            {"id": created.id},
        )

    await database_denied(run(0, forge), "42501")
    assert snapshot(created) == frozen
    complete_key = uuid.uuid4()
    completed = await command(
        complete_self_training_record,
        started_item,
        result(started_item),
        key=complete_key,
    )
    assert json.loads(completed.body)["data"]["resultVerified"] is False
    try:
        alembic_command.downgrade(Config("/app/alembic.ini"), "f1a3c5e7b9d2")
    except DBAPIError as error:
        assert getattr(error.orig, "sqlstate", None) == "P0001"
        assert "personal_training_results_require_preservation" in str(error.orig)
    else:
        raise AssertionError("downgrade discarded an unverified personal result")
    with migration.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "e2c4f6a8b0d3"
        )
    assert snapshot(created)[1:5] == (False, False, True, "92%")
    after = await run(
        0, lambda connection: service(connection).self_cme(employee, BRANCH, 2026)
    )
    assert baseline.achieved_hours == after.achieved_hours
    replay = await command(
        complete_self_training_record,
        started_item,
        result(started_item),
        key=complete_key,
    )
    assert (
        json.loads(replay.body) == json.loads(completed.body)
        and replay.headers["idempotency-replayed"] == "true"
    )
    await denied(
        command(cancel_training_record, started_item, version(started_item)),
        "state_conflict",
    )

    unverified = await run(
        1,
        lambda connection: service(connection).get_training(
            manager,
            BRANCH,
            created.id,
            scope="direct_report",
        ),
    )
    trusted_body = TrainingCompleteRequest.model_validate(
        {
            **result(unverified).model_dump(mode="json", by_alias=True),
            "isCme": True,
        }
    )
    await command(complete_training_record, unverified, trusted_body, index=1)
    verified = await run(
        0, lambda connection: service(connection).self_cme(employee, BRANCH, 2026)
    )
    assert verified.achieved_hours == baseline.achieved_hours + 2
    assert snapshot(created)[1:3] == (True, True)
    own_manager = await create(1)
    own_trusted = TrainingCompleteRequest.model_validate(
        {**result(own_manager).model_dump(mode="json", by_alias=True), "isCme": True}
    )
    await denied(
        command(complete_training_record, own_manager, own_trusted, index=1),
        "operation_not_permitted",
        "resource_not_found",
    )
    await command(
        complete_self_training_record, own_manager, result(own_manager), index=1
    )
    assert snapshot(own_manager)[1:3] == (False, False)
    with migration.begin() as connection:
        connection.execute(
            text("UPDATE employees SET active=false WHERE id=:id"),
            {"id": employee.employee_id},
        )
    await denied(
        command(start_training_record, created, version(created), key=start_key),
        "application_account_unavailable",
    )
    with migration.begin() as connection:
        connection.execute(
            text("UPDATE employees SET active=true WHERE id=:id"),
            {"id": employee.employee_id},
        )

    cancelled = await create()
    await command(cancel_training_record, cancelled, version(cancelled))
    assert snapshot(cancelled)[0] == "cancelled"
    await denied(
        command(complete_self_training_record, cancelled, result(cancelled)),
        "state_conflict",
    )

    report_record = await create()
    manager_key = uuid.uuid4()
    await command(
        start_training_record, report_record, version(report_record), 1, manager_key
    )
    with migration.begin() as connection:
        connection.execute(
            text("UPDATE employees SET reporting_manager_id=NULL WHERE id=:id"),
            {"id": employee.employee_id},
        )
    await denied(
        command(
            start_training_record, report_record, version(report_record), 1, manager_key
        ),
        "resource_not_found",
        "operation_not_permitted",
    )
    with migration.begin() as connection:
        connection.execute(
            text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"),
            {"id": employee.employee_id, "manager": manager.employee_id},
        )
    concurrent = await create()
    async with control.connect() as connection:
        transaction = await connection.begin()
        await connection.execute(
            text("UPDATE employees SET reporting_manager_id=NULL WHERE id=:id"),
            {"id": employee.employee_id},
        )
        pending = asyncio.create_task(
            command(start_training_record, concurrent, version(concurrent), 1)
        )
        await asyncio.sleep(0.15)
        assert not pending.done()
        await transaction.commit()
        await denied(pending, "resource_not_found", "operation_not_permitted")
    assert snapshot(concurrent)[0] == "planned"
    with migration.begin() as connection:
        connection.execute(
            text("UPDATE employees SET reporting_manager_id=:manager WHERE id=:id"),
            {"id": employee.employee_id, "manager": manager.employee_id},
        )

    rollback = await create()
    before = snapshot(rollback)
    with migration.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION restoration_e_audit_failure() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER restoration_e_audit_failure BEFORE INSERT "
                "ON audit_events FOR EACH ROW EXECUTE FUNCTION restoration_e_audit_failure()"
            )
        )
    try:
        await database_denied(
            command(start_training_record, rollback, version(rollback)),
            "P0001",
        )
        assert snapshot(rollback) == before
    finally:
        with migration.begin() as connection:
            connection.execute(
                text("DROP TRIGGER restoration_e_audit_failure ON audit_events")
            )
            connection.execute(text("DROP FUNCTION restoration_e_audit_failure()"))

    with migration.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO payslips(id,company_id,branch_id,payroll_run_id,employee_id,"
                "period,payment_date,gross_pay,net_pay,data_snapshot,issued_at) "
                "SELECT :id,company_id,branch_id,payroll_run_id,:employee,period,"
                "payment_date,gross_pay,net_pay,jsonb_build_object("
                "'employeeName','Synthetic manager','earnings',jsonb_build_array("
                "jsonb_build_object('label','Basic salary','amount',gross_pay::text)),"
                "'deductions','[]'::jsonb,'totalDeductions','0.00',"
                "'wpsBasicPay',gross_pay::text,'wpsVariablePay','0.00'),issued_at FROM payslips "
                "WHERE branch_id=:branch ORDER BY id LIMIT 1"
            ),
            {"id": MANAGER_PAYSLIP, "employee": manager.employee_id, "branch": BRANCH},
        )
        own_payslip = MANAGER_PAYSLIP
        foreign_payslip = connection.scalar(
            text("SELECT id FROM payslips WHERE id<>:id LIMIT 1"),
            {"id": own_payslip},
        )
    assert own_payslip and foreign_payslip
    pdf = await download_self_payslip_pdf(
        own_payslip, request(), claims(SUBJECTS[1]), manager
    )
    assert (
        bytes(pdf.body).startswith(b"%PDF-")
        and pdf.headers["cache-control"] == "no-store"
    )
    await denied(
        download_self_payslip_pdf(
            foreign_payslip, request(), claims(SUBJECTS[1]), manager
        ),
        "resource_not_found",
    )
    with migration.begin() as connection:
        for record_id, kind in ((MANAGER_LETTER, "letter"), (MANAGER_CUSTOM, "custom")):
            connection.execute(
                text(
                    "INSERT INTO letter_requests(id,company_id,branch_id,employee_id,"
                    "request_kind,letter_type,purpose,status,employee_name_snapshot,"
                    "branch_name_snapshot,actioned_by_app_user_id,actioned_at,completed_at) "
                    "VALUES(:id,:company,:branch,:employee,:kind,'employment_confirmation',"
                    "'Synthetic housing application','completed','Synthetic manager',"
                    "'Synthetic clinic',:actor,now(),now())"
                ),
                {
                    "id": record_id,
                    "company": manager.company_id,
                    "branch": BRANCH,
                    "employee": manager.employee_id,
                    "kind": kind,
                    "actor": admin.app_user_id,
                },
            )
    letter_pdf = await download_completed_request_letter_pdf(
        MANAGER_LETTER, request(), claims(SUBJECTS[1]), manager
    )
    assert bytes(letter_pdf.body).startswith(b"%PDF-")
    await denied(
        download_completed_request_letter_pdf(
            MANAGER_CUSTOM, request(), claims(SUBJECTS[1]), manager
        ),
        "operation_not_permitted",
    )
    await denied(
        download_completed_request_letter_pdf(
            MANAGER_LETTER, request(), claims(SUBJECTS[0]), employee
        ),
        "resource_not_found",
    )
    with migration.begin() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM audit_events WHERE action='payslip_pdf_exported' "
                    "AND actor_app_user_id=:id"
                ),
                {"id": manager.app_user_id},
            )
            == 1
        )
        connection.execute(
            text("DELETE FROM idempotency_records WHERE company_id=:company"),
            {"company": employee.company_id},
        )
        connection.execute(
            text("DELETE FROM audit_events WHERE company_id=:company"),
            {"company": employee.company_id},
        )
        connection.execute(
            text("DELETE FROM training_records WHERE training_title=:title"),
            {"title": "Part E synthetic personal training"},
        )
        connection.execute(
            text("DELETE FROM payslips WHERE id=:id"), {"id": MANAGER_PAYSLIP}
        )
        connection.execute(
            text("DELETE FROM letter_requests WHERE id IN (:letter,:custom)"),
            {"letter": MANAGER_LETTER, "custom": MANAGER_CUSTOM},
        )
        clean(connection, rows)
        prior_audit = connection.scalar(
            text(
                "SELECT pg_get_functiondef(oid) FROM pg_proc "
                "WHERE proname='_append_phase12_output_audit_restoration_e_prior'"
            )
        )
        assert isinstance(prior_audit, str)
    alembic_command.downgrade(Config("/app/alembic.ini"), "f1a3c5e7b9d2")
    with migration.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "f1a3c5e7b9d2"
        )
        assert not connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='training_records' "
                "AND column_name='result_verified')"
            )
        )
        assert not connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_proc WHERE proname IN "
                "('transition_training_record','guard_training_personal_authority',"
                "'_append_phase12_output_audit_restoration_e_prior'))"
            )
        )
        assert not connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='restoration_e_manager_payslips')"
            )
        )
        restored = connection.execute(
            text(
                "SELECT pg_get_functiondef(oid),"
                "has_function_privilege('workloop_runtime',oid,'EXECUTE'),"
                "EXISTS (SELECT 1 FROM aclexplode(coalesce(proacl,acldefault('f',proowner))) "
                "acl WHERE acl.grantee=0 AND acl.privilege_type='EXECUTE') "
                "FROM pg_proc WHERE proname='append_phase12_output_audit'"
            )
        ).one()
        assert restored[0] == prior_audit.replace(
            "_append_phase12_output_audit_restoration_e_prior",
            "append_phase12_output_audit",
        )
        assert restored[1] and not restored[2]
    alembic_command.upgrade(Config("/app/alembic.ini"), "head")
    await runtime.dispose()
    await control.dispose()
    migration.dispose()
    print(
        "Part E training provenance, replay, reassignment, rollback, and manager payslip boundaries passed."
    )


if __name__ == "__main__":
    asyncio.run(main())
