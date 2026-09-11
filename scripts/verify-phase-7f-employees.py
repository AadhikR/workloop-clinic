#!/usr/bin/env python3
"""Verify Phase 7F employee administration with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.employees import (
    EmployeeCreateRequest,
    EmployeeImportRequest,
    EmployeeUpdateRequest,
)
from app.services.employees import EmployeeCursorCodec, EmployeeService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse

EXPECTED_HEAD = "7d4a9c2e6b10"
COMPOSE_PROJECT = "workloop-phase7f-final"
POSTGRES_PORT = 25432
API_PORT = 28000
KEYCLOAK_PORT = 28080
KEYCLOAK_MANAGEMENT_PORT = 29000
TEMPORARY_POSTGRES_VOLUME = "workloop-phase7f-final_postgres_data"
ADMIN_SUBJECT = "hr.admin@horizon.test"
MANAGER_SUBJECT = "aisha.manager@horizon.test"
CREATE_EMPLOYEE_ID = uuid.UUID("7f000000-0000-4000-8000-000000000001")
CREATE_KEY = uuid.UUID("7f000000-0000-4000-8000-000000000002")
IMPORT_EMPLOYEE_IDS = (
    uuid.UUID("7f000000-0000-4000-8000-000000000003"),
    uuid.UUID("7f000000-0000-4000-8000-000000000004"),
)
IMPORT_KEY = uuid.UUID("7f000000-0000-4000-8000-000000000005")
ROLLBACK_EMPLOYEE_ID = uuid.UUID("7f000000-0000-4000-8000-000000000006")
CONFLICT_EMPLOYEE_ID = uuid.UUID("7f000000-0000-4000-8000-000000000007")
FOREIGN_BRANCH_EMPLOYEE_ID = uuid.UUID("22000000-0000-4000-8000-000000000001")
FOREIGN_TENANT_EMPLOYEE_ID = uuid.UUID("31000000-0000-4000-8000-000000000001")
TERMINATED_EMPLOYEE_ID = uuid.UUID("21000000-0000-4000-8000-000000000006")
CURSOR_CODEC = EmployeeCursorCodec(b"phase-7f-verifier-cursor-key-000")


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def id_factory(values: Iterator[uuid.UUID]) -> Callable[[], uuid.UUID]:
    return lambda: next(values)


async def expect_code(code: str, operation: Any) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


def import_body() -> EmployeeImportRequest:
    return EmployeeImportRequest.model_validate(
        {
            "rows": [
                {
                    "rowNumber": 2,
                    "empNo": "7F-I-1",
                    "name": "Phase 7F Import One",
                    "molId": "10003048635713",
                    "bankName": "Synthetic Bank",
                    "bankRoutingCode": "123456789",
                    "iban": "AE000000000000000000001",
                    "basicSalary": "5000.00",
                    "allowance": "250.00",
                },
                {
                    "rowNumber": 3,
                    "empNo": "7F-I-2",
                    "name": "Phase 7F Import Two",
                    "molId": "10003048635714",
                    "bankName": "Synthetic Bank",
                    "bankRoutingCode": "",
                    "iban": "",
                    "basicSalary": "0.00",
                    "allowance": "0.00",
                },
            ]
        }
    )


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
        engine=runtime_engine, issuer=c.SEED_ISSUER, timeout_seconds=2
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=10,
    )
    admin = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
    manager = await resolver.resolve(issuer=c.SEED_ISSUER, subject=MANAGER_SUBJECT)
    assert manager.employee_id is not None
    created_ids: list[uuid.UUID] = []

    async def run(
        principal: AuthorizationPrincipal,
        operation: Callable[[EmployeeService, AsyncConnection], Any],
        *,
        ids: Iterator[uuid.UUID] | None = None,
    ) -> Any:
        active_ids = ids if ids is not None else iter(())

        async def execute(connection: AsyncConnection) -> Any:
            service = EmployeeService(connection, CURSOR_CODEC, id_factory=id_factory(active_ids))
            return await operation(service, connection)

        return await executor.execute(
            claims=claims(ADMIN_SUBJECT if principal is admin else MANAGER_SUBJECT),
            principal=principal,
            operation=execute,
            selected_admin_branch_id=c.BRANCH_DXB if principal is admin else None,
        )

    create = EmployeeCreateRequest.model_validate(
        {
            "empNo": "7F-C-1",
            "name": " Phase 7F Created ",
            "molId": "10003048635712",
            "workEmail": " PHASE7F@EXAMPLE.TEST ",
            "jobTitle": "Nurse",
            "department": "Nursing",
            "reportingManagerId": str(manager.employee_id),
            "employmentStatus": "probation",
            "basicSalary": "7000.00",
        }
    )
    create_calls = 0

    async def create_operation(
        service: EmployeeService, connection: AsyncConnection
    ) -> IdempotentResponse:
        command = IdempotencyCommand(
            key=CREATE_KEY,
            operation_id="create_employee",
            method="POST",
            route_parameters={},
            fingerprint="7" * 64,
            branch_id=c.BRANCH_DXB,
        )

        async def mutate() -> IdempotentResponse:
            nonlocal create_calls
            create_calls += 1
            item = await service.create_employee(admin, c.BRANCH_DXB, create)
            return IdempotentResponse(
                status=201,
                body={"data": item.model_dump(mode="json", by_alias=True)},
                location=f"/api/v1/employees/{item.id}",
                resource_kind="employee",
                resource_id=item.id,
            )

        return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
            principal=admin,
            command=command,
            authorize_replay=lambda kind, resource_id: service.authorize_employee_replay(
                admin, c.BRANCH_DXB, kind, resource_id
            ),
            mutation=mutate,
        )

    try:
        first = await run(admin, create_operation, ids=iter((CREATE_EMPLOYEE_ID,)))
        created_ids.append(CREATE_EMPLOYEE_ID)
        replay = await run(admin, create_operation, ids=iter((CREATE_EMPLOYEE_ID,)))
        assert replay.replayed and replay.body == first.body and create_calls == 1

        with engine.connect() as connection:
            created = connection.execute(
                text(
                    "SELECT id,company_id,branch_id,name,work_email,department,"
                    "reporting_manager_id,employment_status FROM employees WHERE id=:id"
                ),
                {"id": CREATE_EMPLOYEE_ID},
            ).mappings().one()
            assert dict(created) == {
                "id": CREATE_EMPLOYEE_ID,
                "company_id": c.COMPANY_ID[c.HORIZON],
                "branch_id": c.BRANCH_DXB,
                "name": "Phase 7F Created",
                "work_email": "phase7f@example.test",
                "department": "Nursing",
                "reporting_manager_id": manager.employee_id,
                "employment_status": "Probation",
            }
            audit_count = connection.execute(
                text("SELECT count(*) FROM audit_events WHERE entity_id=:id"),
                {"id": CREATE_EMPLOYEE_ID},
            ).scalar_one()
            assert audit_count == 0

        updated = await run(
            admin,
            lambda service, _connection: service.update_employee(
                admin,
                c.BRANCH_DXB,
                CREATE_EMPLOYEE_ID,
                EmployeeUpdateRequest.model_validate(
                    {
                        "expectedUpdatedAt": first.body["data"]["updatedAt"],
                        "name": "Phase 7F Edited",
                        "personalEmail": "edited@example.test",
                    }
                ),
            ),
        )
        assert updated.name == "Phase 7F Edited"
        await expect_code(
            "state_conflict",
            run(
                admin,
                lambda service, _connection: service.update_employee(
                    admin,
                    c.BRANCH_DXB,
                    CREATE_EMPLOYEE_ID,
                    EmployeeUpdateRequest.model_validate(
                        {
                            "expectedUpdatedAt": first.body["data"]["updatedAt"],
                            "name": "Stale edit",
                        }
                    ),
                ),
            ),
        )
        await expect_code(
            "resource_not_found",
            run(
                admin,
                lambda service, _connection: service.create_employee(
                    admin,
                    c.BRANCH_DXB,
                    EmployeeCreateRequest(
                        name="Missing department",
                        molId="10003048635711",
                        department="Not a department",
                    ),
                ),
                ids=iter((uuid.UUID("7f000000-0000-4000-8000-000000000010"),)),
            ),
        )
        await expect_code(
            "employee_conflict",
            run(
                admin,
                lambda service, _connection: service.create_employee(
                    admin,
                    c.BRANCH_DXB,
                    EmployeeCreateRequest(
                        name="Duplicate work email",
                        molId="10003048635710",
                        workEmail=" PHASE7F@example.test ",
                        department="Nursing",
                    ),
                ),
                ids=iter((CONFLICT_EMPLOYEE_ID,)),
            ),
        )
        await expect_code(
            "resource_not_found",
            run(
                admin,
                lambda service, _connection: service.create_employee(
                    admin,
                    c.BRANCH_DXB,
                    EmployeeCreateRequest(
                        name="Foreign branch manager",
                        molId="10003048635709",
                        department="Nursing",
                        reportingManagerId=FOREIGN_BRANCH_EMPLOYEE_ID,
                    ),
                ),
            ),
        )
        await expect_code(
            "employee_conflict",
            run(
                admin,
                lambda service, _connection: service.create_employee(
                    admin,
                    c.BRANCH_DXB,
                    EmployeeCreateRequest(
                        name="Ineligible manager",
                        molId="10003048635708",
                        department="Nursing",
                        reportingManagerId=TERMINATED_EMPLOYEE_ID,
                    ),
                ),
            ),
        )
        for inaccessible_id in (FOREIGN_BRANCH_EMPLOYEE_ID, FOREIGN_TENANT_EMPLOYEE_ID):
            await expect_code(
                "resource_not_found",
                run(
                    admin,
                    lambda service, _connection, target=inaccessible_id: service.update_employee(
                        admin,
                        c.BRANCH_DXB,
                        target,
                        EmployeeUpdateRequest.model_validate(
                            {
                                "expectedUpdatedAt": "2026-09-11T00:00:00.000Z",
                                "name": "Scope violation",
                            }
                        ),
                    ),
                ),
            )
        await expect_code(
            "operation_not_permitted",
            run(
                manager,
                lambda service, _connection: service.create_employee(
                    manager, c.BRANCH_DXB, create
                ),
                ids=iter((uuid.UUID("7f000000-0000-4000-8000-000000000011"),)),
            ),
        )

        import_calls = 0
        imported = import_body()

        async def import_operation(
            service: EmployeeService, connection: AsyncConnection
        ) -> IdempotentResponse:
            command = IdempotencyCommand(
                key=IMPORT_KEY,
                operation_id="create_employee_import",
                method="POST",
                route_parameters={},
                fingerprint="f" * 64,
                branch_id=c.BRANCH_DXB,
            )

            async def mutate() -> IdempotentResponse:
                nonlocal import_calls
                import_calls += 1
                result = await service.import_employees(admin, c.BRANCH_DXB, imported)
                return IdempotentResponse(
                    status=201,
                    body={"data": result.model_dump(mode="json", by_alias=True)},
                    location=None,
                    resource_kind="tenant",
                    resource_id=None,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=admin,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_import_replay(
                    admin, c.BRANCH_DXB, kind, resource_id
                ),
                mutation=mutate,
            )

        import_first = await run(admin, import_operation, ids=iter(IMPORT_EMPLOYEE_IDS))
        created_ids.extend(IMPORT_EMPLOYEE_IDS)
        import_replay = await run(admin, import_operation, ids=iter(IMPORT_EMPLOYEE_IDS))
        assert import_replay.replayed and import_replay.body == import_first.body
        assert import_calls == 1

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT count(*) FROM employees WHERE id=ANY(:ids)"),
                {"ids": list(IMPORT_EMPLOYEE_IDS)},
            ).scalar_one() == 2
            assert connection.execute(
                text("SELECT count(*) FROM audit_events WHERE entity_id=ANY(:ids)"),
                {"ids": list(IMPORT_EMPLOYEE_IDS)},
            ).scalar_one() == 0

        await expect_code(
            "employee_conflict",
            run(
                admin,
                lambda service, _connection: service.import_employees(
                    admin, c.BRANCH_DXB, imported
                ),
                ids=iter((ROLLBACK_EMPLOYEE_ID, manager.employee_id)),
            ),
        )
        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT count(*) FROM employees WHERE id=:id"),
                {"id": ROLLBACK_EMPLOYEE_ID},
            ).scalar_one() == 0
            assert connection.execute(
                text("SELECT count(*) FROM employees WHERE id=:id"),
                {"id": CONFLICT_EMPLOYEE_ID},
            ).scalar_one() == 0

        return {
            "ordinaryMutationAuditRows": audit_count,
            "createReplay": replay.replayed,
            "importCount": 2,
            "importReplay": import_replay.replayed,
            "rollbackCount": 0,
            "scopeFailuresRejected": True,
            "workEmailConflictRejected": True,
            "staleWriteRejected": True,
        }
    finally:
        await runtime_engine.dispose()
        with engine.begin() as connection:
            all_ids = [*created_ids, ROLLBACK_EMPLOYEE_ID, CONFLICT_EMPLOYEE_ID]
            connection.execute(
                text("DELETE FROM idempotency_records WHERE idempotency_key=ANY(:keys)"),
                {"keys": [CREATE_KEY, IMPORT_KEY]},
            )
            connection.execute(
                text("DELETE FROM audit_events WHERE entity_id=ANY(:ids)"),
                {"ids": all_ids},
            )
            connection.execute(
                text("DELETE FROM employees WHERE id=ANY(:ids)"),
                {"ids": all_ids},
            )


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == EXPECTED_HEAD
        evidence = asyncio.run(verify_services(engine))
        evidence.update(
            {
                "alembicHead": EXPECTED_HEAD,
                "apiPort": API_PORT,
                "composeProject": COMPOSE_PROJECT,
                "keycloakManagementPort": KEYCLOAK_MANAGEMENT_PORT,
                "keycloakPort": KEYCLOAK_PORT,
                "postgresPort": POSTGRES_PORT,
                "temporaryPostgresVolume": TEMPORARY_POSTGRES_VOLUME,
            }
        )
        evidence["syntheticState"] = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        with engine.begin() as connection:
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
