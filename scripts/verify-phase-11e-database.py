#!/usr/bin/env python3
"""Exercise the Phase 11E appraisal and clinical incident boundary."""

from __future__ import annotations

import asyncio
import os
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.appraisals import (
    AppraisalCalibrationRequest,
    AppraisalCycleCreateRequest,
    AppraisalReviewRequest,
    AppraisalSectionRatingRequest,
)
from app.schemas.incidents import (
    IncidentCorrectiveActionRequest,
    IncidentCreateRequest,
    IncidentInvestigationRequest,
)
from app.services.appraisals import AppraisalService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.incidents import IncidentListQuery, IncidentService

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


async def expect_code(code: str, operation: object) -> None:
    try:
        await operation  # type: ignore[misc]
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
            "d6f8a0c2e4b7"
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

    cycle = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).create_cycle(
            admin,
            BRANCH_ID,
            AppraisalCycleCreateRequest.model_validate(
                {
                    "name": "Phase 11E synthetic cycle",
                    "reviewFrom": "2026-01-01",
                    "reviewTo": "2026-12-31",
                }
            ),
        ),
    )
    cycle = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).activate_cycle(
            admin, BRANCH_ID, cycle.id, cycle.updated_at
        ),
    )

    async def generate():
        return await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AppraisalService(connection).generate(
                admin, BRANCH_ID, cycle.id, cycle.updated_at
            ),
        )

    generated = await asyncio.gather(generate(), generate())
    assert sum(item.created_count for item in generated) == generated[0].appraisal_count
    assert generated[0].section_count == generated[0].appraisal_count * 5
    with migration_engine.connect() as connection:
        duplicates = connection.execute(
            text(
                "SELECT count(*) FROM (SELECT appraisal_id,section_name,count(*) "
                "FROM appraisal_sections GROUP BY appraisal_id,section_name "
                "HAVING count(*)>1) duplicate"
            )
        ).scalar_one()
        assert duplicates == 0

    reports = await run(
        manager,
        MANAGER,
        None,
        lambda connection: AppraisalService(connection).list_appraisals(
            manager, BRANCH_ID, scope="direct_report", limit=100
        ),
    )
    appraisal = next(
        item
        for item in reports
        if item.employee_id == employee.employee_id and item.cycle_id == cycle.id
    )
    ratings = ["4.0", "4.0", "3.0", "3.0", "5.0"]
    stale_review_version = appraisal.updated_at
    for index, (section, rating) in enumerate(zip(appraisal.sections, ratings, strict=True)):
        if index == 4:
            stale_review_version = appraisal.updated_at
        appraisal = await run(
            manager,
            MANAGER,
            None,
            lambda connection, section=section, rating=rating, appraisal=appraisal: (
                AppraisalService(connection).rate_section(
                    manager,
                    BRANCH_ID,
                    appraisal.id,
                    section.id,
                    AppraisalSectionRatingRequest.model_validate(
                        {
                            "rating": rating,
                            "comments": "Synthetic rating",
                            "expectedUpdatedAt": appraisal.updated_at,
                        }
                    ),
                )
            ),
        )
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AppraisalService(connection).review(
                admin,
                BRANCH_ID,
                appraisal.id,
                AppraisalReviewRequest.model_validate(
                    {
                        "reviewerComments": "Stale review",
                        "developmentPlan": "Synthetic plan",
                        "expectedUpdatedAt": stale_review_version,
                    }
                ),
            ),
        ),
    )
    appraisal = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).review(
            admin,
            BRANCH_ID,
            appraisal.id,
            AppraisalReviewRequest.model_validate(
                {
                    "reviewerComments": "Synthetic review",
                    "developmentPlan": "Synthetic plan",
                    "expectedUpdatedAt": appraisal.updated_at,
                }
            ),
        ),
    )
    assert appraisal.overall_rating == Decimal("3.8")
    appraisal = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).calibrate(
            admin,
            BRANCH_ID,
            appraisal.id,
            AppraisalCalibrationRequest.model_validate(
                {"finalRating": "4.0", "expectedUpdatedAt": appraisal.updated_at}
            ),
        ),
    )
    assert appraisal.status == "calibrated" and appraisal.overall_rating == Decimal("4.0")

    current_cycle = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).get_cycle(admin, BRANCH_ID, cycle.id),
    )
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AppraisalService(connection).close_cycle(
                admin, BRANCH_ID, cycle.id, current_cycle.updated_at
            ),
        ),
    )
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE appraisals SET status='reviewed',overall_rating=3.0,"
                "reviewed_by_app_user_id=:actor,reviewed_at=statement_timestamp() "
                "WHERE cycle_id=:cycle_id AND status='pending'"
            ),
            {"actor": admin.app_user_id, "cycle_id": cycle.id},
        )
    closed = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AppraisalService(connection).close_cycle(
            admin, BRANCH_ID, cycle.id, current_cycle.updated_at
        ),
    )
    assert closed.status == "closed" and closed.closed_by_app_user_id == admin.app_user_id

    incident_request = IncidentCreateRequest.model_validate(
        {
            "incidentDate": date(2026, 9, 23),
            "incidentType": "medication_error",
            "severity": "critical",
            "description": "SENSITIVE-PHASE11E-DESCRIPTION",
            "location": "SENSITIVE-PHASE11E-LOCATION",
            "department": "Synthetic clinical department",
            "reportedById": employee.employee_id,
            "involvedEmpId": employee.employee_id,
            "immediateAction": "SENSITIVE-PHASE11E-ACTION",
            "notes": "SENSITIVE-PHASE11E-NOTES",
        }
    )
    incident = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: IncidentService(connection).create(admin, BRANCH_ID, incident_request),
    )
    listed = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: IncidentService(connection).list(
            admin,
            BRANCH_ID,
            IncidentListQuery(None, None, "medication_error", "critical", "open", 50),
        ),
    )
    assert listed[0].id == incident.id
    with migration_engine.connect() as connection:
        other_branch_employee = connection.execute(
            text(
                "SELECT id FROM employees WHERE company_id=:company_id "
                "AND branch_id<>:branch_id ORDER BY id LIMIT 1"
            ),
            {"company_id": admin.company_id, "branch_id": BRANCH_ID},
        ).scalar_one()
    wrong_branch = incident_request.model_copy(update={"reported_by_id": other_branch_employee})
    await expect_code(
        "resource_not_found",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: IncidentService(connection).create(admin, BRANCH_ID, wrong_branch),
        ),
    )
    incident = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: IncidentService(connection).investigate(
            admin,
            BRANCH_ID,
            incident.id,
            IncidentInvestigationRequest.model_validate(
                {
                    "rootCause": "SENSITIVE-PHASE11E-ROOT",
                    "expectedUpdatedAt": incident.updated_at,
                }
            ),
        ),
    )
    incident = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: IncidentService(connection).corrective_action(
            admin,
            BRANCH_ID,
            incident.id,
            IncidentCorrectiveActionRequest.model_validate(
                {
                    "correctiveAction": "SENSITIVE-PHASE11E-CORRECTION",
                    "expectedUpdatedAt": incident.updated_at,
                }
            ),
        ),
    )
    incident = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: IncidentService(connection).close(
            admin, BRANCH_ID, incident.id, incident.updated_at
        ),
    )
    assert incident.status == "closed" and incident.closed_by_app_user_id == admin.app_user_id

    with migration_engine.connect() as connection:
        incident_events = connection.execute(
            text(
                "SELECT metadata::text FROM audit_events WHERE entity_id=:id "
                "AND action LIKE 'incident_%' ORDER BY occurred_at,id"
            ),
            {"id": incident.id},
        ).scalars()
        metadata = " ".join(incident_events)
        assert "medication_error" in metadata and "critical" in metadata
        for secret in (
            "SENSITIVE-PHASE11E-DESCRIPTION",
            "SENSITIVE-PHASE11E-LOCATION",
            "SENSITIVE-PHASE11E-ACTION",
            "SENSITIVE-PHASE11E-NOTES",
            "SENSITIVE-PHASE11E-ROOT",
            "SENSITIVE-PHASE11E-CORRECTION",
            str(employee.employee_id),
        ):
            assert secret not in metadata

    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM audit_events WHERE company_id=:company_id"),
            {"company_id": admin.company_id},
        )
        connection.execute(
            text(
                "DELETE FROM appraisal_sections WHERE appraisal_id IN "
                "(SELECT id FROM appraisals WHERE cycle_id=:cycle_id)"
            ),
            {"cycle_id": cycle.id},
        )
        connection.execute(
            text("DELETE FROM appraisals WHERE cycle_id=:cycle_id"),
            {"cycle_id": cycle.id},
        )
        connection.execute(
            text("DELETE FROM appraisal_cycles WHERE id=:cycle_id"),
            {"cycle_id": cycle.id},
        )
        connection.execute(
            text("DELETE FROM incident_reports WHERE id=:incident_id"),
            {"incident_id": incident.id},
        )
        clean(connection, seed_rows)

    await runtime_engine.dispose()
    migration_engine.dispose()
    print("Phase 11E appraisal and clinical incident database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
