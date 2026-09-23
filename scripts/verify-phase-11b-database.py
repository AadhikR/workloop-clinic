#!/usr/bin/env python3
"""Exercise the Phase 11B scan queue with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.leave_attachment import AttachmentSubmissionRequest
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.leave_attachment import LeaveAttachmentService, ValidatedUpload
from app.storage.base import StorageError
from app.storage.malware import SYNTHETIC_MALWARE_MARKER, SyntheticMalwareScanner
from app.storage.reconciler import set_reconciler_context
from app.storage.scanner_worker import (
    claim_scan,
    manual_requeue,
    process_scan,
    run_maintenance,
    run_once,
)
from app.storage.synthetic import SyntheticObjectStorage

BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
RAVI = "ravi.employee@horizon.test"


class FailingStorage(SyntheticObjectStorage):
    async def get_object(self, *, key: str) -> object:
        del key
        raise StorageError


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
            "c3e5a7b9d1f6"
        )
        role = connection.execute(
            text(
                "SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname='workloop_file_scanner'"
            )
        ).one()
        assert role == (True, False, False, False, False, False, False)
        assert (
            connection.execute(
                text(
                    "SELECT relrowsecurity AND relforcerowsecurity FROM pg_catalog.pg_class "
                    "WHERE oid='public.file_security_scans'::regclass"
                )
            ).scalar_one()
            is True
        )
        scanner_tables = set(
            connection.execute(
                text(
                    "SELECT table_name,privilege_type FROM information_schema.role_table_grants "
                    "WHERE grantee='workloop_file_scanner'"
                )
            ).all()
        )
        assert scanner_tables == {("file_security_scans", "SELECT")}
        assert (
            connection.execute(
                text(
                    "SELECT has_table_privilege('workloop_file_scanner',"
                    "'public.audit_events','SELECT,INSERT,UPDATE,DELETE')"
                )
            ).scalar_one()
            is False
        )
        assert (
            connection.execute(
                text(
                    "SELECT has_column_privilege('workloop_runtime',"
                    "'public.file_security_scans','object_key','SELECT')"
                )
            ).scalar_one()
            is False
        )
        assert (
            connection.execute(
                text(
                    "SELECT has_function_privilege('workloop_file_scanner',"
                    "'public.append_file_security_audit(uuid,text,text)','EXECUTE')"
                )
            ).scalar_one()
            is True
        )
        assert (
            connection.execute(
                text(
                    "SELECT has_function_privilege('workloop_runtime',"
                    "'public.file_security_scan_allows_download"
                    "(uuid,text,uuid,text,text,bigint,text,text)','EXECUTE')"
                )
            ).scalar_one()
            is True
        )

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    scanner_engine = create_async_engine(
        database_url("workloop_file_scanner", "WORKLOOP_FILE_SCANNER_PASSWORD")
    )
    reconciler_engine = create_async_engine(
        database_url("workloop_storage_reconciler", "WORKLOOP_STORAGE_RECONCILER_PASSWORD")
    )
    resolver = ApplicationUserResolver(
        engine=runtime_engine, issuer=seed.SEED_ISSUER, timeout_seconds=5
    )
    executor = AuthorizedServiceExecutor(
        AuthorizationTransactionFactory(engine=runtime_engine, setup_timeout_seconds=5),
        deadline_seconds=15,
    )
    principal = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=RAVI)

    async def run(operation: object) -> object:
        async def invoke(connection: AsyncConnection) -> object:
            service = LeaveAttachmentService(
                connection,
                object_key_hmac_key=b"8" * 32,
                scanner_definition="synthetic-v1",
            )
            return await operation(service)  # type: ignore[operator]

        return await executor.execute(
            claims=claims(RAVI),
            principal=principal,
            selected_admin_branch_id=None,
            operation=invoke,
        )

    submission = await run(
        lambda service: service.create_submission(
            principal, BRANCH_ID, AttachmentSubmissionRequest()
        )
    )
    file_body = b"%PDF-1.7\nPhase 11B synthetic attachment\n%%EOF"
    digest = hashlib.sha256(file_body).hexdigest()
    upload = ValidatedUpload(
        body=file_body,
        file_name="phase-11b-proof.pdf",
        content_type="application/pdf",
        sha256=digest,
        submission_token=submission.submission_token,  # type: ignore[attr-defined]
    )
    claimed = await run(
        lambda service: service.claim_upload(
            principal,
            BRANCH_ID,
            submission.id,
            upload,  # type: ignore[attr-defined]
        )
    )
    storage_root = Path(os.environ.get("PHASE11B_STORAGE_PATH", "/tmp/phase11b-objects"))
    storage = SyntheticObjectStorage(
        root=storage_root,
        signing_key=b"9" * 32,
        base_url="http://127.0.0.1:28000",
    )
    await storage.put_object(
        key=claimed.object_key,  # type: ignore[attr-defined]
        body=file_body,
        content_type=upload.content_type,
        sha256=digest,
    )
    attachment = await run(lambda service: service.complete_upload(principal, claimed, upload))
    await expect_code(
        "service_unavailable",
        run(
            lambda service: service.load_for_download(
                principal,
                BRANCH_ID,
                attachment.id,  # type: ignore[attr-defined]
            )
        ),
    )

    scanner = SyntheticMalwareScanner(signing_key=b"s" * 32)
    assert await run_once(scanner_engine, storage, scanner) is True
    released = await run(
        lambda service: service.load_for_download(
            principal,
            BRANCH_ID,
            attachment.id,  # type: ignore[attr-defined]
        )
    )
    assert released["sha256"] == digest  # type: ignore[index]
    with migration_engine.begin() as connection:
        connection.execute(
            text("UPDATE public.leave_attachments SET sha256=:sha256 WHERE id=:id"),
            {"id": attachment.id, "sha256": "f" * 64},  # type: ignore[attr-defined]
        )
    await expect_code(
        "service_unavailable",
        run(
            lambda service: service.load_for_download(
                principal,
                BRANCH_ID,
                attachment.id,  # type: ignore[attr-defined]
            )
        ),
    )
    with migration_engine.begin() as connection:
        connection.execute(
            text("UPDATE public.leave_attachments SET sha256=:sha256 WHERE id=:id"),
            {"id": attachment.id, "sha256": digest},  # type: ignore[attr-defined]
        )

    company_id = principal.company_id
    employee_id = principal.employee_id
    assert employee_id is not None
    creator_id = principal.app_user_id
    created_scan_ids: list[uuid.UUID] = []

    def insert_scan(
        *,
        object_key: str,
        entity_id: uuid.UUID,
        status: str = "pending",
        attempt_count: int = 0,
        age: str = "1 day",
    ) -> uuid.UUID:
        scan_id = uuid.uuid4()
        created_scan_ids.append(scan_id)
        with migration_engine.begin() as connection:
            if status == "pending":
                state_columns = ""
                state_values = ""
            elif status == "failed":
                state_columns = ",status,attempt_count,last_error_code,next_attempt_at"
                state_values = ",'failed',:attempt_count,'provider_error',statement_timestamp()"
            elif status == "claimed":
                state_columns = ",status,attempt_count,claimed_at,lease_expires_at"
                state_values = (
                    ",'claimed',8,statement_timestamp()-interval '16 minutes',"
                    "statement_timestamp()-interval '1 minute'"
                )
            else:
                raise ValueError("unsupported verifier state")
            connection.execute(
                text(
                    "INSERT INTO public.file_security_scans("
                    "id,company_id,branch_id,employee_id,created_by_app_user_id,entity_type,"
                    "entity_id,object_key,content_type,size_bytes,sha256,scanner_definition,"
                    f"created_at,updated_at{state_columns}) VALUES("
                    ":id,:company_id,:branch_id,:employee_id,:creator,'employee_document',"
                    ":entity_id,:object_key,'application/pdf',:size_bytes,:sha256,'synthetic-v1',"
                    "statement_timestamp()-CAST(:age AS interval),statement_timestamp()"
                    f"{state_values})"
                ),
                {
                    "id": scan_id,
                    "company_id": company_id,
                    "branch_id": BRANCH_ID,
                    "employee_id": employee_id,
                    "creator": creator_id,
                    "entity_id": entity_id,
                    "object_key": object_key,
                    "size_bytes": len(file_body),
                    "sha256": digest,
                    "attempt_count": attempt_count,
                    "age": age,
                },
            )
        return scan_id

    infected_id = uuid.uuid4()
    infected_key = f"employee-documents/v1/scope/{infected_id.hex}"
    infected_body = b"%PDF-1.7\n" + SYNTHETIC_MALWARE_MARKER + b"\n%%EOF"
    infected_digest = hashlib.sha256(infected_body).hexdigest()
    infected_scan_id = uuid.uuid4()
    created_scan_ids.append(infected_scan_id)
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.file_security_scans("
                "id,company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,"
                "object_key,content_type,size_bytes,sha256,scanner_definition) VALUES("
                ":id,:company_id,:branch_id,:employee_id,:creator,'employee_document',:entity_id,"
                ":object_key,'application/pdf',:size_bytes,:sha256,'synthetic-v1')"
            ),
            {
                "id": infected_scan_id,
                "company_id": company_id,
                "branch_id": BRANCH_ID,
                "employee_id": employee_id,
                "creator": creator_id,
                "entity_id": infected_id,
                "object_key": infected_key,
                "size_bytes": len(infected_body),
                "sha256": infected_digest,
            },
        )
    await storage.put_object(
        key=infected_key,
        body=infected_body,
        content_type="application/pdf",
        sha256=infected_digest,
    )
    assert await run_once(scanner_engine, storage, scanner) is True
    with migration_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM public.file_security_scans WHERE id=:id"),
                {"id": infected_scan_id},
            ).scalar_one()
            == "infected"
        )

    race_id = uuid.uuid4()
    race_scan_id = insert_scan(
        object_key=f"employee-documents/v1/race/{race_id.hex}", entity_id=race_id
    )
    first, second = await asyncio.gather(claim_scan(scanner_engine), claim_scan(scanner_engine))
    claimed_race = first or second
    assert claimed_race is not None and claimed_race.id == race_scan_id
    assert (first is None) != (second is None)
    await process_scan(
        scanner_engine,
        FailingStorage(
            root=storage_root,
            signing_key=b"9" * 32,
            base_url="http://127.0.0.1:28000",
        ),
        scanner,
        claimed_race,
    )
    assert await manual_requeue(
        scanner_engine,
        scan_id=race_scan_id,
        company_id=company_id,
        branch_id=BRANCH_ID,
    )
    requeued = await claim_scan(scanner_engine)
    assert requeued is not None and requeued.id == race_scan_id
    await process_scan(scanner_engine, FailingStorage(
        root=storage_root,
        signing_key=b"9" * 32,
        base_url="http://127.0.0.1:28000",
    ), scanner, requeued)
    with migration_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT count(*) FROM public.audit_events "
                "WHERE action='storage_manual_requeue' AND entity_id=:entity_id"
            ),
            {"entity_id": race_id},
        ).scalar_one() == 1

    delays = (
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
        timedelta(hours=72),
    )
    failing = FailingStorage(
        root=storage_root,
        signing_key=b"9" * 32,
        base_url="http://127.0.0.1:28000",
    )
    for expected_attempt in range(2, 9):
        entity_id = uuid.uuid4()
        scan_id = insert_scan(
            object_key=f"employee-documents/v1/retry/{entity_id.hex}",
            entity_id=entity_id,
            status="failed",
            attempt_count=expected_attempt - 1,
        )
        claimed_retry = await claim_scan(scanner_engine)
        assert claimed_retry is not None and claimed_retry.id == scan_id
        await process_scan(scanner_engine, failing, scanner, claimed_retry)
        with migration_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status,attempt_count,next_attempt_at,updated_at "
                    "FROM public.file_security_scans WHERE id=:id"
                ),
                {"id": scan_id},
            ).one()
            assert row.status == "failed" and row.attempt_count == expected_attempt
            assert (row.next_attempt_at is None) is (expected_attempt == 8)
            if expected_attempt < 8:
                assert row.next_attempt_at - row.updated_at == delays[expected_attempt - 1]

    lease_id = uuid.uuid4()
    terminal_scan_id = insert_scan(
        object_key=f"employee-documents/v1/lease/{lease_id.hex}",
        entity_id=lease_id,
        status="claimed",
    )
    await run_maintenance(scanner_engine)
    recovery_events = [uuid.uuid4() for _ in range(3)]
    manifest_digest = "sha256:" + "a" * 64
    async with reconciler_engine.begin() as connection:
        await set_reconciler_context(
            connection,
            company_id=company_id,
            branch_id=BRANCH_ID,
        )
        for event_id, action, digest_value in (
            (recovery_events[0], "storage_backup_completed", manifest_digest),
            (recovery_events[1], "storage_restore_verified", manifest_digest),
            (recovery_events[2], "storage_credential_rotated", ""),
        ):
            await connection.execute(
                text(
                    "SELECT public.append_storage_recovery_audit"
                    "(:company_id,:branch_id,:action,:event_id,:manifest_digest)"
                ),
                {
                    "company_id": company_id,
                    "branch_id": BRANCH_ID,
                    "action": action,
                    "event_id": event_id,
                    "manifest_digest": digest_value,
                },
            )
    with migration_engine.connect() as connection:
        assert connection.execute(
            text("SELECT status,last_error_code FROM public.file_security_scans WHERE id=:id"),
            {"id": terminal_scan_id},
        ).one() == ("failed", "retry_exhausted")
        unsafe_audits = connection.execute(
            text(
                "SELECT count(*) FROM public.audit_events "
                "WHERE system_actor_key='file_security_scan' AND "
                "(metadata ? 'object_key' OR metadata ? 'filename' OR metadata ? 'sha256' "
                "OR metadata ? 'employee_id')"
            )
        ).scalar_one()
        assert unsafe_audits == 0
        recovery_audits = connection.execute(
            text(
                "SELECT action,metadata FROM public.audit_events "
                "WHERE entity_type='storage_recovery' ORDER BY action"
            )
        ).all()
        assert len(recovery_audits) == 3
        assert {row.action for row in recovery_audits} == {
            "storage_backup_completed",
            "storage_restore_verified",
            "storage_credential_rotated",
        }
        assert all(
            set(row.metadata) == {"operation_id", "manifest_digest"}
            for row in recovery_audits
        )

    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM public.audit_events WHERE system_actor_key='file_security_scan'")
        )
        connection.execute(
            text("DELETE FROM public.audit_events WHERE entity_type='storage_recovery'")
        )
        connection.execute(
            text("DELETE FROM public.audit_events WHERE entity_id=:id"),
            {"id": attachment.id},  # type: ignore[attr-defined]
        )
        connection.execute(
            text("DELETE FROM public.storage_operations WHERE entity_id=:id"),
            {"id": attachment.id},  # type: ignore[attr-defined]
        )
        connection.execute(
            text("DELETE FROM public.leave_attachments WHERE id=:id"),
            {"id": attachment.id},  # type: ignore[attr-defined]
        )
        connection.execute(text("DELETE FROM public.file_security_scans"))
    await storage.delete_object(key=claimed.object_key)  # type: ignore[attr-defined]
    await storage.delete_object(key=infected_key)
    await storage.close()
    await scanner_engine.dispose()
    await reconciler_engine.dispose()
    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, seed_rows)
    migration_engine.dispose()
    print("Phase 11B file-security database and worker checks passed")


if __name__ == "__main__":
    asyncio.run(main())
