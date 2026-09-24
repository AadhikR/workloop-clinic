from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.db.engine import normalize_psycopg_url

CLINICAL_DOCUMENT_TYPES = frozenset(
    {
        "ACLS Certificate",
        "BLS Certificate",
        "CME Certificate",
        "DHA Licence",
        "DOH Licence",
        "MOH Licence",
        "NRP Certificate",
        "PALS Certificate",
    }
)


@dataclass(frozen=True, slots=True)
class ExpiryCandidate:
    source_id: uuid.UUID
    source_kind: str
    source_date: date
    entity_type: str
    notification_type: str
    title: str
    threshold: int


def _candidate(
    source_id: uuid.UUID,
    source_kind: str,
    source_date: date | None,
    business_date: date,
    thresholds: tuple[int, ...],
    entity_type: str,
    notification_type: str,
    title: str,
) -> ExpiryCandidate | None:
    if source_date is None:
        return None
    days = (source_date - business_date).days
    if days not in thresholds:
        return None
    return ExpiryCandidate(
        source_id=source_id,
        source_kind=source_kind,
        source_date=source_date,
        entity_type=entity_type,
        notification_type=notification_type,
        title=title,
        threshold=days,
    )


async def _set_context(
    connection: AsyncConnection,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    business_date: date,
) -> None:
    user = (await connection.execute(text("SELECT current_user"))).scalar_one()
    if user != "workloop_expiry_processing":
        raise RuntimeError("expiry command requires the workloop_expiry_processing login")
    await connection.execute(
        text(
            """
SELECT pg_catalog.set_config('workloop.company_id',:company,true),
       pg_catalog.set_config('workloop.branch_id',:branch,true),
       pg_catalog.set_config('workloop.actor_kind','scheduled_job',true),
       pg_catalog.set_config('workloop.actor_key','expiry_processing',true),
       pg_catalog.set_config('workloop.business_date',:business_date,true)
"""
        ),
        {
            "branch": "" if branch_id is None else str(branch_id),
            "business_date": business_date.isoformat(),
            "company": str(company_id),
        },
    )
    company_exists = await connection.scalar(
        text("SELECT EXISTS(SELECT 1 FROM public.companies WHERE id=:company)"),
        {"company": company_id},
    )
    if company_exists is not True:
        raise RuntimeError("company is outside the expiry login scope")
    if branch_id is not None:
        branch_exists = await connection.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM public.branches "
                "WHERE id=:branch AND company_id=:company)"
            ),
            {"branch": branch_id, "company": company_id},
        )
        if branch_exists is not True:
            raise RuntimeError("branch is outside the expiry login scope")


async def _lock_tuple(
    connection: AsyncConnection,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    business_date: date,
) -> None:
    await connection.execute(
        text(
            "SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended("
            ":company || ':' || :branch || ':' || :business_date,0))"
        ),
        {
            "branch": "tenant" if branch_id is None else str(branch_id),
            "business_date": business_date.isoformat(),
            "company": str(company_id),
        },
    )


async def _source_candidates(
    connection: AsyncConnection, business_date: date
) -> list[ExpiryCandidate]:
    candidates: list[ExpiryCandidate] = []
    employee_rows = (
        await connection.execute(
            text(
                """
SELECT id,employment_status,visa_expiry,passport_expiry,emirates_id_expiry,labour_card_expiry,
       probation_end_date,contract_type,contract_end_date,licence_authority,licence_expiry
FROM public.employees
WHERE active AND employment_status <> 'Terminated'
"""
            )
        )
    ).mappings()
    employee_specs = (
        ("visa", "visa_expiry", (60, 30, 14), "document_expiry", "Document expiring"),
        (
            "passport",
            "passport_expiry",
            (60, 30, 14),
            "document_expiry",
            "Document expiring",
        ),
        (
            "emirates_id",
            "emirates_id_expiry",
            (60, 30, 14),
            "document_expiry",
            "Document expiring",
        ),
        (
            "labour_card",
            "labour_card_expiry",
            (60, 30, 14),
            "document_expiry",
            "Document expiring",
        ),
    )
    for row in employee_rows:
        for source_kind, column, thresholds, notification_type, title in employee_specs:
            item = _candidate(
                row["id"],
                source_kind,
                row[column],
                business_date,
                thresholds,
                "employee",
                notification_type,
                title,
            )
            if item is not None:
                candidates.append(item)
        if row["contract_type"] == "Limited":
            item = _candidate(
                row["id"],
                "contract",
                row["contract_end_date"],
                business_date,
                (60, 30, 14, 7),
                "employee",
                "contract_expiry",
                "Contract expiring",
            )
            if item is not None:
                candidates.append(item)
        if row["employment_status"] == "Probation":
            item = _candidate(
                row["id"],
                "probation",
                row["probation_end_date"],
                business_date,
                (14, 7),
                "employee",
                "probation_ending",
                "Probation ending",
            )
            if item is not None:
                candidates.append(item)
        if row["licence_authority"] not in {None, "None"}:
            item = _candidate(
                row["id"],
                "licence",
                row["licence_expiry"],
                business_date,
                (60, 30, 14),
                "employee",
                "clinical_licence_expiry",
                "Clinical licence expiring",
            )
            if item is not None:
                candidates.append(item)

    document_rows = (
        await connection.execute(
            text(
                "SELECT id,document_type,expiry_date FROM public.employee_documents "
                "WHERE status='verified'"
            )
        )
    ).mappings()
    for row in document_rows:
        clinical = row["document_type"] in CLINICAL_DOCUMENT_TYPES
        item = _candidate(
            row["id"],
            "clinical" if clinical else "document",
            row["expiry_date"],
            business_date,
            (90, 30, 14) if clinical else (60, 30, 14),
            "employee_document",
            "clinical_credential_expiry" if clinical else "document_expiry",
            "Clinical credential expiring" if clinical else "Document expiring",
        )
        if item is not None:
            candidates.append(item)

    certification_rows = (
        await connection.execute(
            text("SELECT id,expiry_date FROM public.certifications WHERE status='verified'")
        )
    ).mappings()
    for row in certification_rows:
        item = _candidate(
            row["id"],
            "certification",
            row["expiry_date"],
            business_date,
            (60, 30, 14),
            "certification",
            "cert_expiry",
            "Certification expiring",
        )
        if item is not None:
            candidates.append(item)

    insurance_rows = (
        await connection.execute(text("SELECT id,expiry_date FROM public.employee_insurance"))
    ).mappings()
    for row in insurance_rows:
        item = _candidate(
            row["id"],
            "insurance",
            row["expiry_date"],
            business_date,
            (60, 30),
            "employee_insurance",
            "insurance_expiry",
            "Insurance expiring",
        )
        if item is not None:
            candidates.append(item)

    policy_rows = (
        await connection.execute(text("SELECT id,renewal_date FROM public.insurance_policies"))
    ).mappings()
    for row in policy_rows:
        item = _candidate(
            row["id"],
            "policy",
            row["renewal_date"],
            business_date,
            (60, 30),
            "insurance_policy",
            "policy_renewal",
            "Policy renewal due",
        )
        if item is not None:
            candidates.append(item)
    return candidates


async def _recipients(connection: AsyncConnection) -> list[uuid.UUID]:
    result = await connection.execute(
        text(
            """
SELECT profile.app_user_id
FROM public.user_profiles AS profile
JOIN public.app_users AS account ON account.id=profile.app_user_id
WHERE profile.role='admin' AND profile.employee_id IS NULL AND account.status='active'
ORDER BY profile.app_user_id
"""
        )
    )
    return list(result.scalars())


async def _insert(
    connection: AsyncConnection,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    recipient_id: uuid.UUID,
    item: ExpiryCandidate,
) -> bool:
    result = await connection.execute(
        text(
            """
INSERT INTO public.notifications(
 company_id,branch_id,created_by_app_user_id,recipient_app_user_id,type,title,body,
 related_entity_type,related_entity_id)
VALUES(:company,:branch,NULL,:recipient,:type,:title,'Review this expiry item.',
 :entity_type,:related_id)
ON CONFLICT(company_id,recipient_app_user_id,type,related_entity_type,related_entity_id)
DO NOTHING
"""
        ),
        {
            "branch": branch_id,
            "company": company_id,
            "entity_type": item.entity_type,
            "recipient": recipient_id,
            "related_id": f"{item.source_id}:{item.source_kind}:{item.threshold}",
            "title": item.title,
            "type": item.notification_type,
        },
    )
    if result.rowcount != 1:
        return False
    metadata = {
        "recipient_app_user_id": str(recipient_id),
        "source_date": item.source_date.isoformat(),
        "source_kind": item.source_kind,
        "threshold_days": item.threshold,
    }
    await connection.execute(
        text(
            """
INSERT INTO public.audit_events(
 company_id,branch_id,actor_kind,system_actor_key,action,entity_type,entity_id,
 changed_fields,reason,metadata)
VALUES(:company,:branch,'scheduled_job','expiry_processing','expiry_notification_created',
 :entity_type,:entity_id,ARRAY['type','recipient_app_user_id']::text[],
 'Expiry notification created',CAST(:metadata AS jsonb))
"""
        ),
        {
            "branch": branch_id,
            "company": company_id,
            "entity_id": item.source_id,
            "entity_type": item.entity_type,
            "metadata": json.dumps(metadata, separators=(",", ":"), sort_keys=True),
        },
    )
    return True


async def run_expiry(
    database_url: str,
    *,
    company_id: uuid.UUID,
    branch_id: uuid.UUID | None,
    business_date: date,
) -> int:
    engine = create_async_engine(normalize_psycopg_url(database_url), pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await _set_context(
                connection,
                company_id=company_id,
                branch_id=branch_id,
                business_date=business_date,
            )
            await _lock_tuple(
                connection,
                company_id=company_id,
                branch_id=branch_id,
                business_date=business_date,
            )
            recipients = await _recipients(connection)
            candidates = await _source_candidates(connection, business_date)
            inserted = 0
            for item in candidates:
                for recipient_id in recipients:
                    inserted += int(
                        await _insert(
                            connection,
                            company_id=company_id,
                            branch_id=branch_id,
                            recipient_id=recipient_id,
                            item=item,
                        )
                    )
            return inserted
    finally:
        await engine.dispose()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create due Workloop expiry notifications")
    parser.add_argument("--company-id", type=uuid.UUID, required=True)
    branch = parser.add_mutually_exclusive_group(required=True)
    branch.add_argument("--branch-id", type=uuid.UUID)
    branch.add_argument("--tenant-wide", action="store_true")
    parser.add_argument("--business-date", type=date.fromisoformat, required=True)
    return parser.parse_args()


def main() -> None:
    arguments = _arguments()
    database_url = os.environ.get("EXPIRY_DATABASE_URL")
    if not database_url:
        raise SystemExit("EXPIRY_DATABASE_URL is required")
    try:
        inserted = asyncio.run(
            run_expiry(
                database_url,
                company_id=arguments.company_id,
                branch_id=None if arguments.tenant_wide else arguments.branch_id,
                business_date=arguments.business_date,
            )
        )
    except Exception:
        print('{"error":"expiry_processing_failed"}', file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps({"inserted": inserted}, separators=(",", ":")))


if __name__ == "__main__":
    main()
