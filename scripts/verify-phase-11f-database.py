#!/usr/bin/env python3
"""Exercise the Phase 11F letter and custom request boundary."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.letter_requests import LetterRequestCreateRequest
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.letter_requests import LetterRequestListQuery, LetterRequestService

ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
EMPLOYEE = "ravi.employee@horizon.test"
BRANCH_ID = seed.BRANCH_DXB


def database_url(user: str, password_name: str) -> URL:
    password = os.environ.get(password_name)
    if not password:
        raise RuntimeError(f"{password_name} is required")
    return URL.create(
        "postgresql+psycopg",
        username=user,
        password=password,
        host=os.environ.get("WORKLOOP_POSTGRES_HOST", "postgres"),
        port=5432,
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


async def expect_code(code: str, operation: Awaitable[object]) -> None:
    try:
        await operation
    except ServiceExecutionError as error:
        assert error.code == code
        return
    raise AssertionError(f"expected {code}")


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    seed_rows = build_rows()
    with migration_engine.begin() as connection:
        apply_rows(connection, seed_rows)
        validate(connection, seed_rows)
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "c3e5a7b9d1f6"
        )

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    admin = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=ADMIN)
    manager = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=MANAGER)
    employee = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=EMPLOYEE)
    assert manager.employee_id is not None and employee.employee_id is not None

    async def run(principal: object, subject: str, selected: object, operation: object):
        return await executor.execute(
            claims=claims(subject),
            principal=principal,  # type: ignore[arg-type]
            selected_admin_branch_id=selected,  # type: ignore[arg-type]
            operation=operation,  # type: ignore[arg-type]
        )

    salary_request = await run(
        employee,
        EMPLOYEE,
        None,
        lambda connection: LetterRequestService(connection).submit(
            employee,
            LetterRequestCreateRequest.model_validate(
                {
                    "requestKind": "letter",
                    "letterType": "salary_certificate_bank",
                    "purpose": "Emirates NBD",
                }
            ),
        ),
    )
    assert salary_request.status == "pending"
    assert not hasattr(salary_request, "basic_salary")

    custom_request = await run(
        manager,
        MANAGER,
        None,
        lambda connection: LetterRequestService(connection).submit(
            manager,
            LetterRequestCreateRequest.model_validate(
                {"requestKind": "custom", "subject": "ABC", "details": "12345"}
            ),
        ),
    )
    assert custom_request.letter_type == "ABC" and custom_request.purpose == "12345"

    own = await run(
        employee,
        EMPLOYEE,
        None,
        lambda connection: LetterRequestService(connection).list_self(
            employee, status="pending", kind="letter", limit=50
        ),
    )
    assert [item.id for item in own if item.id == salary_request.id] == [salary_request.id]
    queue = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: LetterRequestService(connection).list_admin(
            admin,
            BRANCH_ID,
            LetterRequestListQuery("pending", "letter", employee.employee_id, 50),
        ),
    )
    assert [item.id for item in queue if item.id == salary_request.id] == [salary_request.id]
    await expect_code(
        "resource_not_found",
        run(
            admin,
            ADMIN,
            seed.BRANCH_AUH,
            lambda connection: LetterRequestService(connection).get(
                admin, seed.BRANCH_AUH, salary_request.id
            ),
        ),
    )

    async def complete():
        public_requested_at = salary_request.requested_at.replace(
            microsecond=salary_request.requested_at.microsecond // 1000 * 1000
        )
        return await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: LetterRequestService(connection).complete(
                admin, BRANCH_ID, salary_request.id, public_requested_at
            ),
        )

    async def reject():
        public_requested_at = salary_request.requested_at.replace(
            microsecond=salary_request.requested_at.microsecond // 1000 * 1000
        )
        return await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: LetterRequestService(connection).reject(
                admin,
                BRANCH_ID,
                salary_request.id,
                public_requested_at,
                "Synthetic rejection",
            ),
        )

    decisions = await asyncio.gather(complete(), reject(), return_exceptions=True)
    successes = [item for item in decisions if not isinstance(item, BaseException)]
    failures = [item for item in decisions if isinstance(item, ServiceExecutionError)]
    assert len(successes) == 1 and len(failures) == 1
    assert failures[0].code == "state_conflict"
    decided = successes[0]

    if decided.status == "rejected":
        second = await run(
            employee,
            EMPLOYEE,
            None,
            lambda connection: LetterRequestService(connection).submit(
                employee,
                LetterRequestCreateRequest.model_validate(
                    {
                        "requestKind": "letter",
                        "letterType": "salary_certificate_bank",
                        "purpose": "Emirates NBD",
                    }
                ),
            ),
        )
        decided = await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: LetterRequestService(connection).complete(
                admin,
                BRANCH_ID,
                second.id,
                second.requested_at.replace(
                    microsecond=second.requested_at.microsecond // 1000 * 1000
                ),
            ),
        )

    source = await run(
        employee,
        EMPLOYEE,
        None,
        lambda connection: LetterRequestService(connection).print_source(
            employee, BRANCH_ID, decided.id
        ),
    )
    assert source.employee_name == decided.employee_name
    assert source.basic_salary is not None and source.allowance is not None
    original_source = source.model_dump()
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE employees SET name='Changed after request',basic_salary=999999.99 "
                "WHERE id=:id"
            ),
            {"id": employee.employee_id},
        )
    source_after_change = await run(
        employee,
        EMPLOYEE,
        None,
        lambda connection: LetterRequestService(connection).print_source(
            employee, BRANCH_ID, decided.id
        ),
    )
    assert source_after_change.model_dump() == original_source

    with migration_engine.connect() as connection:
        metadata = " ".join(
            connection.execute(
                text(
                    "SELECT metadata::text FROM audit_events "
                    "WHERE entity_id IN (:salary_id,:custom_id) ORDER BY occurred_at,id"
                ),
                {"salary_id": salary_request.id, "custom_id": custom_request.id},
            ).scalars()
        )
        assert "salary_certificate_bank" in metadata and "custom" in metadata
        for secret in ("Emirates NBD", "12345", "Synthetic clinician", "999999.99"):
            assert secret not in metadata

    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM audit_events WHERE company_id=:company_id"),
            {"company_id": admin.company_id},
        )
        connection.execute(
            text("DELETE FROM idempotency_records WHERE company_id=:company_id"),
            {"company_id": admin.company_id},
        )
        connection.execute(
            text("DELETE FROM letter_requests WHERE id IN (:salary_id,:custom_id,:decided_id)"),
            {
                "salary_id": salary_request.id,
                "custom_id": custom_request.id,
                "decided_id": decided.id,
            },
        )
        clean(connection, seed_rows)

    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 11F letter and custom request database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
