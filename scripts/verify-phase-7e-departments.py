#!/usr/bin/env python3
"""Verify Phase 7E departments and staffing rules with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import date
from typing import Any

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as c
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.people import Department
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.departments import (
    DepartmentCreateRequest,
    DepartmentDeleteRequest,
    DepartmentSnapshot,
    DepartmentUpdateRequest,
    StaffingRuleCreateRequest,
    StaffingRuleDeleteRequest,
    StaffingRuleSnapshot,
    StaffingRuleUpdateRequest,
)
from app.services.departments import (
    DepartmentListQuery,
    DepartmentService,
    StaffingRuleListQuery,
)
from app.services.employees import EmployeeCursorCodec
from app.services.execution import (
    AuthorizedServiceExecutor,
    ServiceExecutionError,
)
from app.services.idempotency import (
    IdempotencyCommand,
    IdempotencyCoordinator,
    IdempotentResponse,
)
from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

EXPECTED_HEAD = "7d4a9c2e6b10"
ADMIN_SUBJECT = "hr.admin@horizon.test"
MANAGER_SUBJECT = "aisha.manager@horizon.test"
FOREIGN_DEPARTMENT_ID = uuid.UUID("7e000000-0000-4000-8000-000000000001")
RENAME_KEY = uuid.UUID("7e000000-0000-4000-8000-000000000002")
CURSOR_CODEC = EmployeeCursorCodec(b"phase-7e-verifier-cursor-key-000")


def claims(subject: str) -> AccessTokenClaims:
    return AccessTokenClaims(
        issuer=c.SEED_ISSUER,
        subject=subject,
        audience=("workloop-api",),
        expires_at=1,
        issued_at=1,
        not_before=None,
    )


def row_values(table: str, **matches: object) -> dict[str, object]:
    candidates = [
        row.values
        for row in build_rows()
        if row.table == table
        and all(row.values.get(name) == value for name, value in matches.items())
    ]
    if len(candidates) != 1:
        raise AssertionError(f"expected one synthetic {table} row")
    return candidates[0]


def department_query(**changes: object) -> DepartmentListQuery:
    values: dict[str, object] = {
        "limit": 50,
        "search": None,
        "parent_id": None,
        "head_employee_id": None,
        "sort": (("sortOrder", False), ("name", False)),
        "cursor": None,
    }
    values.update(changes)
    return DepartmentListQuery(**values)  # pyright: ignore[reportArgumentType]


def staffing_query(**changes: object) -> StaffingRuleListQuery:
    values: dict[str, object] = {
        "limit": 50,
        "department": None,
        "shift_category": None,
        "effective_on": None,
        "sort": (("department", False), ("shiftCategory", False)),
        "cursor": None,
    }
    values.update(changes)
    return StaffingRuleListQuery(**values)  # pyright: ignore[reportArgumentType]


def snapshot(item: Any) -> DepartmentSnapshot:
    return DepartmentSnapshot.model_validate(
        {
            "name": item.name,
            "parentId": item.parent_id,
            "headEmployeeId": item.head_employee_id,
            "color": item.color,
            "description": item.description,
            "sortOrder": item.sort_order,
        }
    )


def rule_snapshot(item: Any) -> StaffingRuleSnapshot:
    return StaffingRuleSnapshot.model_validate(
        {
            "department": item.department,
            "shiftCategory": item.shift_category,
            "minStaff": item.min_staff,
            "effectiveFrom": item.effective_from,
            "effectiveTo": item.effective_to,
        }
    )


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
        engine=runtime_engine, issuer=c.SEED_ISSUER, timeout_seconds=2
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=2),
        deadline_seconds=5,
    )
    admin = await resolver.resolve(issuer=c.SEED_ISSUER, subject=ADMIN_SUBJECT)
    manager = await resolver.resolve(issuer=c.SEED_ISSUER, subject=MANAGER_SUBJECT)

    async def run_admin(operation: Any) -> Any:
        async def execute(connection: AsyncConnection) -> Any:
            return await operation(
                DepartmentService(connection, CURSOR_CODEC), connection
            )

        return await executor.execute(
            claims=claims(ADMIN_SUBJECT),
            principal=admin,
            operation=execute,
            selected_admin_branch_id=c.BRANCH_DXB,
        )

    created_ids: list[uuid.UUID] = []
    rule_ids: list[uuid.UUID] = []
    try:
        departments, cursor = await run_admin(
            lambda service, _connection: service.list_departments(
                admin, c.BRANCH_DXB, department_query(limit=2)
            )
        )
        assert len(departments) == 2 and cursor is not None
        names = [item.name for item in departments]
        while cursor is not None:
            page, cursor = await run_admin(
                lambda service, _connection, active_cursor=cursor: (
                    service.list_departments(
                        admin,
                        c.BRANCH_DXB,
                        department_query(limit=2, cursor=active_cursor),
                    )
                )
            )
            names.extend(item.name for item in page)
        assert len(names) == 6 and len(set(names)) == 6

        wildcard, _ = await run_admin(
            lambda service, _connection: service.list_departments(
                admin, c.BRANCH_DXB, department_query(search="%")
            )
        )
        assert wildcard == []
        await expect_code(
            "operation_not_permitted",
            run_admin(
                lambda service, _connection: service.list_departments(
                    manager, c.BRANCH_DXB, department_query()
                )
            ),
        )

        async def manager_rows(connection: AsyncConnection) -> int:
            result = await connection.execute(select(Department.id))
            return len(result.all())

        assert (
            await executor.execute(
                claims=claims(MANAGER_SUBJECT),
                principal=manager,
                operation=manager_rows,
            )
            == 0
        )

        await expect_code(
            "resource_not_found",
            run_admin(
                lambda service, _connection: service.create_department(
                    admin,
                    c.BRANCH_DXB,
                    DepartmentCreateRequest(
                        name="Cross branch", parentId=FOREIGN_DEPARTMENT_ID
                    ),
                )
            ),
        )

        root = await run_admin(
            lambda service, _connection: service.create_department(
                admin,
                c.BRANCH_DXB,
                DepartmentCreateRequest(name="Phase 7E Root", sortOrder=50),
            )
        )
        created_ids.append(root.id)
        child = await run_admin(
            lambda service, _connection: service.create_department(
                admin,
                c.BRANCH_DXB,
                DepartmentCreateRequest(
                    name="Phase 7E Child", parentId=root.id, sortOrder=51
                ),
            )
        )
        created_ids.append(child.id)
        await expect_code(
            "department_conflict",
            run_admin(
                lambda service, _connection: service.update_department(
                    admin,
                    c.BRANCH_DXB,
                    root.id,
                    DepartmentUpdateRequest(expected=snapshot(root), parentId=child.id),
                )
            ),
        )
        await expect_code(
            "department_conflict",
            run_admin(
                lambda service, _connection: service.delete_department(
                    admin,
                    c.BRANCH_DXB,
                    root.id,
                    DepartmentDeleteRequest(expected=snapshot(root)),
                )
            ),
        )
        await run_admin(
            lambda service, _connection: service.delete_department(
                admin,
                c.BRANCH_DXB,
                child.id,
                DepartmentDeleteRequest(expected=snapshot(child)),
            )
        )
        created_ids.remove(child.id)

        all_departments, _ = await run_admin(
            lambda service, _connection: service.list_departments(
                admin, c.BRANCH_DXB, department_query()
            )
        )
        nursing = next(item for item in all_departments if item.name == "Nursing")
        rename = DepartmentUpdateRequest(
            expected=snapshot(nursing), name="Nursing Care"
        )
        mutation_calls = 0

        async def rename_operation(
            service: DepartmentService, connection: AsyncConnection
        ) -> IdempotentResponse:
            command = IdempotencyCommand(
                key=RENAME_KEY,
                operation_id="update_department",
                method="PATCH",
                route_parameters={"departmentId": str(nursing.id)},
                fingerprint="7" * 64,
                branch_id=c.BRANCH_DXB,
            )

            async def mutate() -> IdempotentResponse:
                nonlocal mutation_calls
                mutation_calls += 1
                item = await service.update_department(
                    admin, c.BRANCH_DXB, nursing.id, rename
                )
                return IdempotentResponse(
                    status=200,
                    body={"data": item.model_dump(mode="json", by_alias=True)},
                    location=None,
                    resource_kind="department",
                    resource_id=item.id,
                )

            return await IdempotencyCoordinator(
                IdempotencyRepository(connection)
            ).execute(
                principal=admin,
                command=command,
                authorize_replay=lambda kind, resource_id: (
                    service.authorize_department_replay(
                        admin, c.BRANCH_DXB, kind, resource_id
                    )
                ),
                mutation=mutate,
            )

        first = await run_admin(rename_operation)
        replay = await run_admin(rename_operation)
        assert first.body == replay.body and replay.replayed and mutation_calls == 1

        with engine.connect() as connection:
            employee_count = connection.execute(
                text(
                    "SELECT count(*) FROM employees WHERE branch_id=:branch_id "
                    "AND department='Nursing Care'"
                ),
                {"branch_id": c.BRANCH_DXB},
            ).scalar_one()
            staffing_count = connection.execute(
                text(
                    "SELECT count(*) FROM department_staffing_rules WHERE branch_id=:branch_id "
                    "AND department='Nursing Care'"
                ),
                {"branch_id": c.BRANCH_DXB},
            ).scalar_one()
            history_count = connection.execute(
                text(
                    "SELECT count(*) FROM employee_job_history WHERE branch_id=:branch_id "
                    "AND old_value='Nursing' AND new_value='Nursing Care'"
                ),
                {"branch_id": c.BRANCH_DXB},
            ).scalar_one()
        assert employee_count == history_count and employee_count > 0
        assert staffing_count == 2

        created_rule = await run_admin(
            lambda service, _connection: service.create_staffing_rule(
                admin,
                c.BRANCH_DXB,
                StaffingRuleCreateRequest(
                    department="Phase 7E Root",
                    shiftCategory="flexible",
                    minStaff=0,
                    effectiveFrom=date(2026, 9, 11),
                    effectiveTo=date(2026, 9, 30),
                ),
            )
        )
        rule_ids.append(created_rule.id)
        await expect_code(
            "staffing_rule_conflict",
            run_admin(
                lambda service, _connection: service.create_staffing_rule(
                    admin,
                    c.BRANCH_DXB,
                    StaffingRuleCreateRequest(
                        department="Phase 7E Root",
                        shiftCategory="flexible",
                        minStaff=9,
                    ),
                )
            ),
        )
        updated_rule = await run_admin(
            lambda service, _connection: service.update_staffing_rule(
                admin,
                c.BRANCH_DXB,
                created_rule.id,
                StaffingRuleUpdateRequest(
                    expected=rule_snapshot(created_rule), minStaff=3
                ),
            )
        )
        assert updated_rule.min_staff == 3
        await run_admin(
            lambda service, _connection: service.delete_staffing_rule(
                admin,
                c.BRANCH_DXB,
                updated_rule.id,
                StaffingRuleDeleteRequest(expected=rule_snapshot(updated_rule)),
            )
        )
        rule_ids.remove(updated_rule.id)
        await run_admin(
            lambda service, _connection: service.delete_department(
                admin,
                c.BRANCH_DXB,
                root.id,
                DepartmentDeleteRequest(expected=snapshot(root)),
            )
        )
        created_ids.remove(root.id)

        rules, _ = await run_admin(
            lambda service, _connection: service.list_staffing_rules(
                admin,
                c.BRANCH_DXB,
                staffing_query(effective_on=date(2026, 9, 11)),
            )
        )
        assert rules and all(
            item.effective_from is None or item.effective_from <= date(2026, 9, 11)
            for item in rules
        )
        return {
            "departmentCount": len(names),
            "employeeRenameCount": employee_count,
            "historyRenameCount": history_count,
            "renameReplay": replay.replayed,
            "staffingRenameCount": staffing_count,
        }
    finally:
        await runtime_engine.dispose()
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM idempotency_records WHERE idempotency_key=:key"),
                {"key": RENAME_KEY},
            )
            connection.execute(
                text(
                    "DELETE FROM employee_job_history WHERE branch_id=:branch_id "
                    "AND old_value='Nursing' AND new_value='Nursing Care'"
                ),
                {"branch_id": c.BRANCH_DXB},
            )
            for rule_id in rule_ids:
                connection.execute(
                    text("DELETE FROM department_staffing_rules WHERE id=:id"),
                    {"id": rule_id},
                )
            for department_id in reversed(created_ids):
                connection.execute(
                    text("DELETE FROM departments WHERE id=:id"), {"id": department_id}
                )


def main() -> None:
    engine = create_engine(os.environ["MIGRATION_DATABASE_URL"])
    rows = build_rows()
    try:
        with engine.begin() as connection:
            apply_rows(connection, rows)
            validate(connection, rows)
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == EXPECTED_HEAD
            )
            connection.execute(
                text(
                    "INSERT INTO departments(id,company_id,branch_id,name,sort_order) "
                    "VALUES (:id,:company_id,:branch_id,'Foreign Phase 7E',99)"
                ),
                {
                    "id": FOREIGN_DEPARTMENT_ID,
                    "company_id": c.COMPANY_ID[c.HORIZON],
                    "branch_id": c.BRANCH_AUH,
                },
            )
        evidence = asyncio.run(verify_services(engine))
        evidence["alembicHead"] = EXPECTED_HEAD
        evidence["syntheticState"] = hashlib.sha256(
            json.dumps(evidence, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        print(json.dumps(evidence, separators=(",", ":"), sort_keys=True))
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM departments WHERE id=:id"),
                {"id": FOREIGN_DEPARTMENT_ID},
            )
            clean(connection, rows)
        engine.dispose()


if __name__ == "__main__":
    main()
