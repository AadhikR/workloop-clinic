#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, select, text

ROOT = Path("/workspace") if Path("/workspace").is_dir() else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.seed.fixtures import build_rows  # noqa: E402
from app.db.seed.runner import apply_rows, clean as clean_seed, validate  # noqa: E402
from app.expiry_command import run_expiry  # noqa: E402

TEMP_EMPLOYEE_ID = uuid.UUID("01000000-0000-4000-8000-000000000012")
TEMP_CLINICAL_DOCUMENT_ID = uuid.UUID("02000000-0000-4000-8000-000000000012")


@dataclass(frozen=True, slots=True)
class Target:
    source_id: uuid.UUID
    source_kind: str
    source_date: date
    entity_type: str
    notification_type: str
    thresholds: tuple[int, ...]


def one(connection: object, sql: str, **values: object) -> object:
    return connection.execute(text(sql), values).mappings().one()


def target(
    row: object,
    *,
    source_kind: str,
    entity_type: str,
    notification_type: str,
    thresholds: tuple[int, ...],
    date_column: str,
) -> Target:
    return Target(
        source_id=row["id"],
        source_kind=source_kind,
        source_date=row[date_column],
        entity_type=entity_type,
        notification_type=notification_type,
        thresholds=thresholds,
    )


async def run_dates(
    expiry_url: str,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    targets: list[Target],
) -> None:
    dates = sorted(
        {
            item.source_date - timedelta(days=threshold)
            for item in targets
            for threshold in item.thresholds
        }
    )
    for business_date in dates:
        await run_expiry(
            expiry_url,
            company_id=company_id,
            branch_id=branch_id,
            business_date=business_date,
        )


def related_ids(targets: list[Target]) -> list[str]:
    return [
        f"{item.source_id}:{item.source_kind}:{threshold}"
        for item in targets
        for threshold in item.thresholds
    ]


def assert_targets(
    connection: object,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID,
    recipient_id: uuid.UUID,
    targets: list[Target],
) -> None:
    expected = related_ids(targets)
    rows = connection.execute(
        text(
            """
SELECT type,related_entity_type,related_entity_id,title,body,created_by_app_user_id
FROM public.notifications
WHERE company_id=:company AND branch_id=:branch AND recipient_app_user_id=:recipient
  AND related_entity_id=ANY(:related_ids)
ORDER BY related_entity_id
"""
        ),
        {
            "branch": branch_id,
            "company": company_id,
            "recipient": recipient_id,
            "related_ids": expected,
        },
    ).mappings()
    by_related = {row["related_entity_id"]: row for row in rows}
    assert set(by_related) == set(expected)
    for item in targets:
        for threshold in item.thresholds:
            row = by_related[f"{item.source_id}:{item.source_kind}:{threshold}"]
            assert row["type"] == item.notification_type
            assert row["related_entity_type"] == item.entity_type
            assert row["body"] == "Review this expiry item."
            assert row["created_by_app_user_id"] is None

    audit_count = connection.execute(
        text(
            """
SELECT count(*) FROM public.audit_events
WHERE company_id=:company AND branch_id=:branch
  AND action='expiry_notification_created'
  AND metadata->>'recipient_app_user_id'=:recipient
  AND entity_id=ANY(:source_ids)
"""
        ),
        {
            "branch": branch_id,
            "company": company_id,
            "recipient": str(recipient_id),
            "source_ids": list({item.source_id for item in targets}),
        },
    ).scalar_one()
    assert audit_count >= len(expected)


def cleanup(
    connection: object,
    *,
    company_id: uuid.UUID,
    targets: list[Target],
) -> None:
    source_ids = list({item.source_id for item in targets})
    connection.execute(
        text(
            """
DELETE FROM public.audit_events
WHERE company_id=:company AND action='expiry_notification_created'
  AND entity_id=ANY(:source_ids)
"""
        ),
        {
            "company": company_id,
            "source_ids": source_ids,
        },
    )
    connection.execute(
        text(
            """
DELETE FROM public.notifications
WHERE company_id=:company AND created_by_app_user_id IS NULL
  AND split_part(related_entity_id,':',1)=ANY(:source_ids)
"""
        ),
        {
            "company": company_id,
            "source_ids": [str(source_id) for source_id in source_ids],
        },
    )


async def verify() -> None:
    migration_url = os.environ["MIGRATION_DATABASE_URL"]
    expiry_url = os.environ["EXPIRY_DATABASE_URL"]
    engine = create_engine(migration_url)
    rows = build_rows()
    all_targets: list[Target] = []
    notification_ids_before: list[uuid.UUID] = []
    audit_ids_before: list[uuid.UUID] = []
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM alembic_version")).scalar_one() == 1
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "c3e5a7b9d1f6"
        )
        clean_seed(connection, rows)
        apply_rows(connection, rows)
        validate(connection, rows)
        for table, column, privilege in (
            ("notifications", "company_id", "SELECT"),
            ("notifications", "type", "INSERT"),
            ("audit_events", "action", "INSERT"),
        ):
            assert connection.execute(
                text(
                    "SELECT has_column_privilege('workloop_expiry_processing',"
                    ":table,:column,:privilege)"
                ),
                {
                    "column": column,
                    "privilege": privilege,
                    "table": f"public.{table}",
                },
            ).scalar_one()
        assert not connection.execute(
            text(
                "SELECT has_column_privilege('workloop_expiry_processing',"
                "'public.notifications','id','SELECT')"
            )
        ).scalar_one()

        scope = one(
            connection,
            """
SELECT company.id AS company_id,branch.id AS branch_id,profile.app_user_id AS recipient_id
FROM public.companies AS company
JOIN public.branches AS branch ON branch.company_id=company.id
JOIN public.user_profiles AS profile ON profile.company_id=company.id
JOIN public.app_users AS account ON account.id=profile.app_user_id
WHERE branch.id='20000000-0000-4000-8000-000000000001'::uuid
  AND profile.role='admin' AND profile.employee_id IS NULL AND account.status='active'
ORDER BY company.id,branch.id LIMIT 1
""",
        )
        company_id = scope["company_id"]
        branch_id = scope["branch_id"]
        recipient_id = scope["recipient_id"]

        standard_row = one(
            connection,
            "SELECT id,expiry_date FROM public.employee_documents "
            "WHERE company_id=:company AND branch_id=:branch AND status='verified' "
            "AND expiry_date IS NOT NULL ORDER BY id LIMIT 1",
            company=company_id,
            branch=branch_id,
        )
        clinical_source_row = one(
            connection,
            "SELECT id,document_type,expiry_date FROM public.employee_documents "
            "WHERE company_id=:company AND branch_id=:branch AND status='verified' "
            "AND expiry_date IS NOT NULL AND id<>:standard ORDER BY id LIMIT 1",
            company=company_id,
            branch=branch_id,
            standard=standard_row["id"],
        )
        standard = target(
            standard_row,
            source_kind="document",
            entity_type="employee_document",
            notification_type="document_expiry",
            thresholds=(60, 30, 14),
            date_column="expiry_date",
        )
        certification_row = one(
            connection,
            "SELECT id,expiry_date FROM public.certifications "
            "WHERE company_id=:company AND branch_id=:branch AND status='verified' "
            "AND expiry_date IS NOT NULL ORDER BY id LIMIT 1",
            company=company_id,
            branch=branch_id,
        )
        insurance_row = one(
            connection,
            "SELECT coverage.id,coverage.expiry_date FROM public.employee_insurance AS coverage "
            "JOIN public.employees AS employee ON employee.id=coverage.employee_id "
            "WHERE coverage.company_id=:company AND coverage.branch_id=:branch "
            "AND employee.active AND employee.employment_status<>'Terminated' "
            "ORDER BY coverage.id LIMIT 1",
            company=company_id,
            branch=branch_id,
        )
        policy_row = one(
            connection,
            "SELECT id,renewal_date FROM public.insurance_policies "
            "WHERE company_id=:company AND branch_id=:branch AND renewal_date IS NOT NULL "
            "ORDER BY id LIMIT 1",
            company=company_id,
            branch=branch_id,
        )
        certification = target(
            certification_row,
            source_kind="certification",
            entity_type="certification",
            notification_type="cert_expiry",
            thresholds=(60, 30, 14),
            date_column="expiry_date",
        )
        insurance = target(
            insurance_row,
            source_kind="insurance",
            entity_type="employee_insurance",
            notification_type="insurance_expiry",
            thresholds=(60, 30),
            date_column="expiry_date",
        )
        policy = target(
            policy_row,
            source_kind="policy",
            entity_type="insurance_policy",
            notification_type="policy_renewal",
            thresholds=(60, 30),
            date_column="renewal_date",
        )

        employee_specs = (
            ("passport", "passport_expiry", (60, 30, 14), "document_expiry"),
            ("contract", "contract_end_date", (60, 30, 14, 7), "contract_expiry"),
            ("licence", "licence_expiry", (60, 30, 14), "clinical_licence_expiry"),
        )
        employee_targets: list[Target] = []
        for kind, column, thresholds, notification_type in employee_specs:
            extra = ""
            if kind == "contract":
                extra = "AND contract_type='Limited'"
            elif kind == "licence":
                extra = "AND licence_authority IS NOT NULL AND licence_authority<>'None'"
            row = one(
                connection,
                f"SELECT id,{column} FROM public.employees "
                "WHERE company_id=:company AND branch_id=:branch AND active "
                f"AND employment_status<>'Terminated' AND {column} IS NOT NULL {extra} "
                "ORDER BY id LIMIT 1",
                company=company_id,
                branch=branch_id,
            )
            employee_targets.append(
                target(
                    row,
                    source_kind=kind,
                    entity_type="employee",
                    notification_type=notification_type,
                    thresholds=thresholds,
                    date_column=column,
                )
            )
        probation_row = one(
            connection,
            "SELECT id,probation_end_date FROM public.employees "
            "WHERE company_id=:company AND branch_id=:branch AND active "
            "AND employment_status='Probation' AND probation_end_date IS NOT NULL "
            "ORDER BY id LIMIT 1",
            company=company_id,
            branch=branch_id,
        )
        probation = target(
            probation_row,
            source_kind="probation",
            entity_type="employee",
            notification_type="probation_ending",
            thresholds=(14, 7),
            date_column="probation_end_date",
        )

        metadata = MetaData()
        employee_table = Table("employees", metadata, schema="public", autoload_with=connection)
        document_table = Table(
            "employee_documents", metadata, schema="public", autoload_with=connection
        )
        employee_values = dict(
            connection.execute(
                select(employee_table).where(
                    employee_table.c.id == uuid.UUID("21000000-0000-4000-8000-000000000005")
                )
            )
            .mappings()
            .one()
        )
        employee_values.update(
            id=TEMP_EMPLOYEE_ID,
            emp_no="P12B-EXPIRY",
            name="Phase 12B Expiry",
            personal_email="phase12b.expiry@synthetic.test",
            work_email="phase12b.expiry@synthetic.test",
            visa_expiry=date(2027, 1, 15),
            emirates_id_expiry=date(2027, 2, 15),
            labour_card_expiry=date(2027, 3, 15),
        )
        connection.execute(employee_table.insert().values(**employee_values))

        document_values = dict(
            connection.execute(
                select(document_table).where(document_table.c.id == clinical_source_row["id"])
            )
            .mappings()
            .one()
        )
        document_values.update(
            id=TEMP_CLINICAL_DOCUMENT_ID,
            document_type="BLS Certificate",
            document_number="P12B-CLINICAL",
        )
        connection.execute(document_table.insert().values(**document_values))

        identity_targets = [
            Target(
                source_id=TEMP_EMPLOYEE_ID,
                source_kind=kind,
                source_date=source_date,
                entity_type="employee",
                notification_type="document_expiry",
                thresholds=(60, 30, 14),
            )
            for kind, source_date in (
                ("visa", date(2027, 1, 15)),
                ("emirates_id", date(2027, 2, 15)),
                ("labour_card", date(2027, 3, 15)),
            )
        ]
        clinical = Target(
            source_id=TEMP_CLINICAL_DOCUMENT_ID,
            source_kind="clinical",
            source_date=clinical_source_row["expiry_date"],
            entity_type="employee_document",
            notification_type="clinical_credential_expiry",
            thresholds=(90, 30, 14),
        )
        nonclinical_targets = [
            standard,
            certification,
            insurance,
            policy,
            probation,
            *employee_targets,
            *identity_targets,
        ]
        all_targets = [*nonclinical_targets, clinical]
        cleanup(
            connection,
            company_id=company_id,
            targets=all_targets,
        )
        notification_ids_before = list(
            connection.scalars(
                text("SELECT id FROM public.notifications WHERE company_id=:company"),
                {"company": company_id},
            )
        )
        audit_ids_before = list(
            connection.scalars(
                text("SELECT id FROM public.audit_events WHERE company_id=:company"),
                {"company": company_id},
            )
        )

    try:
        await run_dates(expiry_url, company_id, branch_id, nonclinical_targets)
        with engine.begin() as connection:
            assert_targets(
                connection,
                company_id=company_id,
                branch_id=branch_id,
                recipient_id=recipient_id,
                targets=nonclinical_targets,
            )

        await run_dates(expiry_url, company_id, branch_id, [clinical])
        with engine.begin() as connection:
            assert_targets(
                connection,
                company_id=company_id,
                branch_id=branch_id,
                recipient_id=recipient_id,
                targets=all_targets,
            )

            concurrent = clinical
            threshold = concurrent.thresholds[0]
            related = f"{concurrent.source_id}:{concurrent.source_kind}:{threshold}"
            connection.execute(
                text(
                    "DELETE FROM public.audit_events WHERE company_id=:company "
                    "AND action='expiry_notification_created' AND entity_id=:source "
                    "AND metadata->>'threshold_days'=:threshold"
                ),
                {
                    "company": company_id,
                    "source": concurrent.source_id,
                    "threshold": str(threshold),
                },
            )
            connection.execute(
                text(
                    "DELETE FROM public.notifications WHERE company_id=:company "
                    "AND recipient_app_user_id=:recipient AND related_entity_id=:related"
                ),
                {"company": company_id, "recipient": recipient_id, "related": related},
            )

        concurrent_date = concurrent.source_date - timedelta(days=threshold)
        results = await asyncio.gather(
            run_expiry(
                expiry_url,
                company_id=company_id,
                branch_id=branch_id,
                business_date=concurrent_date,
            ),
            run_expiry(
                expiry_url,
                company_id=company_id,
                branch_id=branch_id,
                business_date=concurrent_date,
            ),
        )
        assert sum(results) == 1
        assert (
            await run_expiry(
                expiry_url,
                company_id=company_id,
                branch_id=branch_id,
                business_date=concurrent_date,
            )
            == 0
        )
        assert (
            await run_expiry(
                expiry_url,
                company_id=company_id,
                branch_id=None,
                business_date=concurrent_date,
            )
            == 0
        )

        try:
            await run_expiry(
                expiry_url,
                company_id=company_id,
                branch_id=uuid.uuid4(),
                business_date=concurrent_date,
            )
        except RuntimeError as error:
            assert "outside the expiry login scope" in str(error)
        else:
            raise AssertionError("wrong branch was accepted")
        try:
            await run_expiry(
                migration_url,
                company_id=company_id,
                branch_id=branch_id,
                business_date=concurrent_date,
            )
        except RuntimeError as error:
            assert "workloop_expiry_processing" in str(error)
        else:
            raise AssertionError("wrong database login was accepted")
    finally:
        with engine.begin() as connection:
            if all_targets:
                cleanup(
                    connection,
                    company_id=company_id,
                    targets=all_targets,
                )
            connection.execute(
                text(
                    "DELETE FROM public.audit_events WHERE company_id=:company "
                    "AND action='expiry_notification_created' AND NOT (id=ANY(:preserved))"
                ),
                {"company": company_id, "preserved": audit_ids_before},
            )
            connection.execute(
                text(
                    "DELETE FROM public.notifications WHERE company_id=:company "
                    "AND created_by_app_user_id IS NULL AND body='Review this expiry item.' "
                    "AND NOT (id=ANY(:preserved))"
                ),
                {"company": company_id, "preserved": notification_ids_before},
            )
            connection.execute(
                text("DELETE FROM public.employee_documents WHERE id=:id"),
                {"id": TEMP_CLINICAL_DOCUMENT_ID},
            )
            connection.execute(
                text("DELETE FROM public.employees WHERE id=:id"),
                {"id": TEMP_EMPLOYEE_ID},
            )
            connection.execute(
                text("DELETE FROM public.audit_events WHERE entity_id IN (:employee,:document)"),
                {"document": TEMP_CLINICAL_DOCUMENT_ID, "employee": TEMP_EMPLOYEE_ID},
            )
            clean_seed(connection, rows)
        engine.dispose()

    print("Phase 12B database verification passed")


if __name__ == "__main__":
    asyncio.run(verify())
