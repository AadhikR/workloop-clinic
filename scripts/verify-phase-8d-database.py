#!/usr/bin/env python3
"""Exercise the Phase 8D attachment transaction boundary with synthetic data."""

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
from app.auth.application_user import ApplicationUserResolver, AuthorizationPrincipal
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.models.identity import AppRole
from app.schemas.leave_attachment import AttachmentSubmissionRequest
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.leave_attachment import LeaveAttachmentService, ValidatedUpload
from app.storage.base import StorageError, StorageNotFoundError
from app.storage.reconciler import (
    claim_operation,
    complete_operation,
    run_maintenance,
    run_once,
)
from app.storage.synthetic import SyntheticObjectStorage

BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
REQUEST_ID = uuid.UUID("7a2fde23-dc8c-560c-937c-4ef631aff6b2")
RAVI = "ravi.employee@horizon.test"
AISHA = "aisha.manager@horizon.test"
ADMIN = "hr.admin@horizon.test"
MARIA = "maria.employee@horizon.test"
FATIMA = "fatima.employee@horizon.test"
OMAR = "omar.manager@horizon.test"
AHMED = "ahmed.employee@cedar.test"


class FailingStorage(SyntheticObjectStorage):
    async def head_object(self, *, key: str) -> object:
        del key
        raise StorageError

    async def delete_object(self, *, key: str) -> None:
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
    with migration_engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "a6c8e0f2b4d7"
        )
        role = connection.execute(
            text(
                "SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls FROM pg_catalog.pg_roles "
                "WHERE rolname='workloop_storage_reconciler'"
            )
        ).one()
        assert role == (True, False, False, False, False, False, False)
        assert connection.execute(
            text(
                "SELECT count(*) FROM pg_catalog.pg_class "
                "WHERE oid IN ('public.storage_operations'::regclass,"
                "'public.leave_attachments'::regclass) AND relrowsecurity AND relforcerowsecurity"
            )
        ).scalar_one() == 2
        reconciler_tables = set(
            connection.execute(
                text(
                    "SELECT table_name,privilege_type FROM information_schema.role_table_grants "
                    "WHERE grantee='workloop_storage_reconciler'"
                )
            ).all()
        )
        assert reconciler_tables == {
            ("storage_operations", "DELETE"),
            ("storage_operations", "SELECT"),
        }
        reconciler_update_columns = set(
            connection.execute(
                text(
                    "SELECT column_name FROM information_schema.role_column_grants "
                    "WHERE grantee='workloop_storage_reconciler' "
                    "AND table_name='storage_operations' AND privilege_type='UPDATE'"
                )
            ).scalars()
        )
        assert reconciler_update_columns == {
            "status",
            "attempt_count",
            "last_error_code",
            "next_attempt_at",
            "claimed_at",
            "lease_expires_at",
            "completed_at",
            "updated_at",
        }
        assert connection.execute(
            text(
                "SELECT has_function_privilege('workloop_storage_reconciler',"
                "'public.append_audit_event(text,text,uuid,text[],text,jsonb)','EXECUTE')"
            )
        ).scalar_one() is False
        assert connection.execute(
            text(
                "SELECT has_table_privilege('workloop_runtime',"
                "'public.leave_attachments','DELETE')"
            )
        ).scalar_one() is False
        stale_ids = list(
            connection.execute(
                text("SELECT id FROM public.leave_attachments WHERE leave_request_id=:id"),
                {"id": REQUEST_ID},
            ).scalars()
        )
        for stale_id in stale_ids:
            connection.execute(
                text("DELETE FROM public.audit_events WHERE entity_id=:id"), {"id": stale_id}
            )
            connection.execute(
                text("DELETE FROM public.storage_operations WHERE entity_id=:id"),
                {"id": stale_id},
            )
            connection.execute(
                text("DELETE FROM public.leave_attachments WHERE id=:id"), {"id": stale_id}
            )
        connection.execute(
            text(
                "DELETE FROM public.leave_approval_delegates "
                "WHERE id='8d000000-0000-4000-8000-000000000010'"
            )
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
    principals = {
        subject: await resolver.resolve(issuer=seed.SEED_ISSUER, subject=subject)
        for subject in (RAVI, AISHA, ADMIN, MARIA, FATIMA, OMAR, AHMED)
    }

    async def run(
        subject: str,
        operation: object,
        *,
        admin_branch: uuid.UUID | None = None,
    ) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            service = LeaveAttachmentService(connection, object_key_hmac_key=b"8" * 32)
            return await operation(service, principal)  # type: ignore[operator]

        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=admin_branch,
            operation=invoke,
        )

    submission = await run(
        RAVI,
        lambda service, principal: service.create_submission(
            principal,
            BRANCH_ID,
            AttachmentSubmissionRequest(requestId=REQUEST_ID),
        ),
    )
    file_body = b"%PDF-1.7\nPhase 8D synthetic attachment\n%%EOF"
    digest = hashlib.sha256(file_body).hexdigest()
    upload = ValidatedUpload(
        body=file_body,
        file_name="phase-8d-proof.pdf",
        content_type="application/pdf",
        sha256=digest,
        submission_token=submission.submission_token,  # type: ignore[attr-defined]
    )
    claimed = await run(
        RAVI,
        lambda service, principal: service.claim_upload(
            principal, BRANCH_ID, submission.id, upload  # type: ignore[attr-defined]
        ),
    )
    storage_root = Path(os.environ.get("PHASE8D_STORAGE_PATH", "/tmp/phase8d-objects"))
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
    attachment = await run(
        RAVI,
        lambda service, principal: service.complete_upload(principal, claimed, upload),
    )
    assert attachment.id == submission.id  # type: ignore[attr-defined]

    for subject, admin_branch in ((RAVI, None), (AISHA, None), (ADMIN, BRANCH_ID)):
        row = await run(
            subject,
            lambda service, principal: service.load_for_download(
                principal, BRANCH_ID, attachment.id  # type: ignore[attr-defined]
            ),
            admin_branch=admin_branch,
        )
        assert row["sha256"] == digest  # type: ignore[index]

    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.leave_approval_delegates("
                "id,company_id,branch_id,approver_employee_id,delegate_employee_id,"
                "from_date,to_date) VALUES("
                "'8d000000-0000-4000-8000-000000000010',"
                "'c89c5c2d-e755-5508-b182-707ac19fbe9c',:branch_id,"
                "'21000000-0000-4000-8000-000000000001',"
                "'21000000-0000-4000-8000-000000000005',current_date-1,current_date+1)"
            ),
            {"branch_id": BRANCH_ID},
        )
    delegated = await run(
        FATIMA,
        lambda service, principal: service.load_for_download(
            principal, BRANCH_ID, attachment.id  # type: ignore[attr-defined]
        ),
    )
    assert delegated["sha256"] == digest  # type: ignore[index]
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE public.leave_approval_delegates SET from_date=current_date-3,"
                "to_date=current_date-2 "
                "WHERE id='8d000000-0000-4000-8000-000000000010'"
            )
        )
    for subject in (FATIMA, MARIA, OMAR, AHMED):
        await expect_code(
            "resource_not_found",
            run(
                subject,
                lambda service, principal: service.load_for_download(
                    principal, BRANCH_ID, attachment.id  # type: ignore[attr-defined]
                ),
            ),
        )

    await expect_code(
        "resource_not_found",
        run(
            MARIA,
            lambda service, principal: service.load_for_download(
                principal, BRANCH_ID, attachment.id  # type: ignore[attr-defined]
            ),
        ),
    )
    await expect_code(
        "attachment_submission_unavailable",
        run(
            RAVI,
            lambda service, principal: service.claim_upload(
                principal, BRANCH_ID, submission.id, upload  # type: ignore[attr-defined]
            ),
        ),
    )
    signed = await storage.create_download_url(
        key=claimed.object_key,  # type: ignore[attr-defined]
        expires_in_seconds=300,
        download_name=attachment.file_name,  # type: ignore[attr-defined]
        content_type=attachment.content_type,  # type: ignore[attr-defined]
    )
    stored, _name = await storage.resolve_download(signed.url.rsplit("/", 1)[1])
    assert stored.body == file_body

    cleanup = await run(
        RAVI,
        lambda service, principal: service.request_cleanup(
            principal, BRANCH_ID, attachment.id, "missing_object"  # type: ignore[attr-defined]
        ),
    )
    await storage.delete_object(key=cleanup.object_key)  # type: ignore[attr-defined]
    await run(
        RAVI,
        lambda service, _principal: service.complete_cleanup(cleanup),
    )

    with migration_engine.begin() as connection:
        event = connection.execute(
            text(
                "SELECT count(*) FROM public.audit_events "
                "WHERE action='leave_attachment_uploaded' AND entity_id=:id"
            ),
            {"id": attachment.id},  # type: ignore[attr-defined]
        ).scalar_one()
        assert event == 1
        cleanup_event = connection.execute(
            text(
                "SELECT count(*) FROM public.audit_events "
                "WHERE action='leave_attachment_cleanup_requested' AND entity_id=:id"
            ),
            {"id": attachment.id},  # type: ignore[attr-defined]
        ).scalar_one()
        assert cleanup_event == 1
        assert connection.execute(
            text("SELECT status FROM public.leave_attachments WHERE id=:id"),
            {"id": attachment.id},  # type: ignore[attr-defined]
        ).scalar_one() == "removed"
        legacy_url = connection.execute(
            text("SELECT attachment_url FROM public.leave_requests WHERE id=:id"),
            {"id": REQUEST_ID},
        ).scalar_one()
        assert legacy_url == ""
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
        connection.execute(
            text(
                "DELETE FROM public.leave_approval_delegates "
                "WHERE id='8d000000-0000-4000-8000-000000000010'"
            )
        )

    reconciler_engine = create_async_engine(
        database_url(
            "workloop_storage_reconciler", "WORKLOOP_STORAGE_RECONCILER_PASSWORD"
        )
    )
    creator_id = principals[RAVI].app_user_id
    company_id = principals[RAVI].company_id
    employee_id = principals[RAVI].employee_id
    assert employee_id is not None

    def insert_operation(operation_id: uuid.UUID, operation: str, object_key: str) -> None:
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO public.storage_operations("
                    "id,company_id,branch_id,employee_id,created_by_app_user_id,entity_type,"
                    "entity_id,operation,object_key) VALUES("
                    ":id,:company_id,:branch_id,:employee_id,:creator,'leave_attachment',"
                    ":entity_id,:operation,:object_key)"
                ),
                {
                    "id": operation_id,
                    "company_id": company_id,
                    "branch_id": BRANCH_ID,
                    "employee_id": employee_id,
                    "creator": creator_id,
                    "entity_id": uuid.uuid4(),
                    "operation": operation,
                    "object_key": object_key,
                },
            )

    orphan_id = uuid.uuid4()
    orphan_key = f"leave-attachments/v1/reconcile/{orphan_id.hex}"
    insert_operation(orphan_id, "upload", orphan_key)
    await storage.put_object(
        key=orphan_key,
        body=file_body,
        content_type="application/pdf",
        sha256=digest,
    )
    assert await run_once(reconciler_engine, storage) is True
    with migration_engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM public.storage_operations WHERE id=:id"),
            {"id": orphan_id},
        ).scalar_one() == "reconciled"
    try:
        await storage.head_object(key=orphan_key)
    except StorageNotFoundError:
        pass
    else:
        raise AssertionError("orphan upload object was not removed")

    race_id = uuid.uuid4()
    insert_operation(race_id, "delete", f"leave-attachments/v1/race/{race_id.hex}")
    first, second = await asyncio.gather(
        claim_operation(reconciler_engine), claim_operation(reconciler_engine)
    )
    claimed_race = first or second
    assert claimed_race is not None and (first is None) != (second is None)
    await complete_operation(reconciler_engine, claimed_race, status="reconciled", error_code="")

    failing = FailingStorage(
        root=storage_root,
        signing_key=b"9" * 32,
        base_url="http://127.0.0.1:28000",
    )
    retry_ids: list[uuid.UUID] = []
    delays = (
        timedelta(minutes=1),
        timedelta(minutes=5),
        timedelta(minutes=15),
        timedelta(hours=1),
        timedelta(hours=6),
        timedelta(hours=24),
        timedelta(hours=72),
    )
    for expected_attempt in range(1, 9):
        retry_id = uuid.uuid4()
        retry_ids.append(retry_id)
        if expected_attempt == 1:
            insert_operation(
                retry_id, "delete", f"leave-attachments/v1/retry/{retry_id.hex}"
            )
        else:
            with migration_engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO public.storage_operations("
                        "id,company_id,branch_id,employee_id,created_by_app_user_id,"
                        "entity_type,entity_id,operation,object_key,status,attempt_count,"
                        "last_error_code,next_attempt_at,created_at,updated_at) VALUES("
                        ":id,:company_id,:branch_id,:employee_id,:creator,'leave_attachment',"
                        ":entity_id,'delete',:object_key,'failed',:attempt_count,"
                        "'provider_error',statement_timestamp(),"
                        "statement_timestamp()-interval '1 day',statement_timestamp())"
                    ),
                    {
                        "id": retry_id,
                        "company_id": company_id,
                        "branch_id": BRANCH_ID,
                        "employee_id": employee_id,
                        "creator": creator_id,
                        "entity_id": uuid.uuid4(),
                        "object_key": f"leave-attachments/v1/retry/{retry_id.hex}",
                        "attempt_count": expected_attempt - 1,
                    },
                )
        assert await run_once(reconciler_engine, failing) is True
        with migration_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status,attempt_count,next_attempt_at,updated_at "
                    "FROM public.storage_operations WHERE id=:id"
                ),
                {"id": retry_id},
            ).one()
            assert row.status == "failed" and row.attempt_count == expected_attempt
            assert (row.next_attempt_at is None) is (expected_attempt == 8)
            if expected_attempt < 8:
                assert row.next_attempt_at - row.updated_at == delays[expected_attempt - 1]

    purge_id = uuid.uuid4()
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO public.storage_operations("
                "id,company_id,branch_id,employee_id,created_by_app_user_id,entity_type,"
                "entity_id,operation,object_key,status,attempt_count,completed_at,created_at,"
                "updated_at) VALUES(:id,:company_id,:branch_id,:employee_id,:creator,"
                "'leave_attachment',:entity_id,'delete',:object_key,'reconciled',1,"
                "statement_timestamp()-interval '91 days',statement_timestamp()-interval '100 days',"
                "statement_timestamp()-interval '91 days')"
            ),
            {
                "id": purge_id,
                "company_id": company_id,
                "branch_id": BRANCH_ID,
                "employee_id": employee_id,
                "creator": creator_id,
                "entity_id": uuid.uuid4(),
                "object_key": f"leave-attachments/v1/purge/{purge_id.hex}",
            },
        )
    await run_maintenance(reconciler_engine)
    with migration_engine.begin() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM public.storage_operations WHERE id=:id"),
            {"id": purge_id},
        ).scalar_one() == 0
        connection.execute(
            text("DELETE FROM public.storage_operations WHERE id=ANY(:ids)"),
            {"ids": [orphan_id, race_id, *retry_ids]},
        )
    await reconciler_engine.dispose()
    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, seed_rows)
    migration_engine.dispose()
    print("Phase 8D attachment database and storage checks passed")


if __name__ == "__main__":
    asyncio.run(main())
