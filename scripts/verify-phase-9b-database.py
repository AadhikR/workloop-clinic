#!/usr/bin/env python3
"""Exercise Phase 9B expense and receipt boundaries through the runtime role."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import date, timedelta

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.http.idempotency_fingerprint import request_fingerprint
from app.http.schemas import DataResponse
from app.repositories.idempotency import IdempotencyRepository
from app.schemas.expense import ExpenseCreateRequest, ExpenseDecisionRequest
from app.schemas.expense_receipt import ReceiptSubmissionRequest
from app.services.employees import EmployeeCursorCodec
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.expense_receipt import ClaimedReceiptCleanup, ExpenseReceiptService
from app.services.expenses import ExpenseListQuery, ExpenseService
from app.services.idempotency import IdempotencyCommand, IdempotencyCoordinator, IdempotentResponse
from app.services.leave_attachment import ValidatedUpload
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

COMPANY_ID = seed.COMPANY_ID[seed.HORIZON]
BRANCH_ID = seed.BRANCH_DXB
OTHER_BRANCH_ID = seed.BRANCH_AUH
ADMIN = "hr.admin@horizon.test"
MANAGER = "aisha.manager@horizon.test"
RAVI = "ravi.employee@horizon.test"
MARIA = "maria.employee@horizon.test"
RAVI_ID = uuid.UUID("21000000-0000-4000-8000-000000000002")
MARIA_ID = uuid.UUID("21000000-0000-4000-8000-000000000003")
CREATE_KEYS = [uuid.UUID(f"9b000000-0000-4000-8000-{value:012d}") for value in range(101, 105)]
DECISION_KEY = uuid.UUID("9b000000-0000-4000-8000-000000000201")
OBJECT_KEY_HMAC = b"9" * 32


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
        assert error.code == code, error.code
        return
    raise AssertionError(f"expected {code}")


async def main() -> None:
    migration_engine = create_engine(
        database_url("workloop_migration", "WORKLOOP_MIGRATION_PASSWORD")
    )
    rows = build_rows()
    with migration_engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "a1c3e5f7b902"
        )
        apply_rows(connection, rows)
        validate(connection, rows)
        business_date = connection.scalar(
            text("SELECT timezone('Asia/Dubai',statement_timestamp())::date")
        )
        assert isinstance(business_date, date)

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
        for subject in (ADMIN, MANAGER, RAVI, MARIA)
    }
    codec = EmployeeCursorCodec(b"9" * 32)

    async def run_expense(
        subject: str, callback: object, *, branch_id: uuid.UUID | None = None
    ) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            return await callback(ExpenseService(connection, codec), principal)  # type: ignore[operator]

        selected = branch_id if subject == ADMIN else None
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    async def run_receipt(
        subject: str, callback: object, *, branch_id: uuid.UUID | None = None
    ) -> object:
        principal = principals[subject]

        async def invoke(connection: AsyncConnection) -> object:
            service = ExpenseReceiptService(connection, object_key_hmac_key=OBJECT_KEY_HMAC)
            return await callback(service, principal)  # type: ignore[operator]

        selected = branch_id if subject == ADMIN else None
        return await executor.execute(
            claims=claims(subject),
            principal=principal,
            selected_admin_branch_id=selected,
            operation=invoke,
        )

    async def idempotent_create(key: uuid.UUID, body: ExpenseCreateRequest) -> IdempotentResponse:
        principal = principals[RAVI]
        operation_id = "create_self_expense"
        body_values = body.model_dump(mode="json", by_alias=True)
        command = IdempotencyCommand(
            key=key,
            operation_id=operation_id,
            method="POST",
            route_parameters={},
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method="POST",
                route_parameters={},
                effective_query_parameters={},
                body=body_values,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = ExpenseService(connection, codec)

            async def mutate() -> IdempotentResponse:
                result = await service.create(principal, body)
                return IdempotentResponse(
                    status=201,
                    body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                    location=f"/api/v1/expenses/self/{result.id}",
                    resource_kind="expense_claim",
                    resource_id=result.id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutate,
            )

        return await executor.execute(claims=claims(RAVI), principal=principal, operation=invoke)

    async def idempotent_admin_approve(
        claim_id: uuid.UUID, body: ExpenseDecisionRequest
    ) -> IdempotentResponse:
        principal = principals[ADMIN]
        operation_id = "admin_approve_expense"
        route_parameters: dict[str, object] = {"claimId": str(claim_id)}
        body_values = body.model_dump(mode="json", by_alias=True)
        command = IdempotencyCommand(
            key=DECISION_KEY,
            operation_id=operation_id,
            method="POST",
            route_parameters=route_parameters,
            fingerprint=request_fingerprint(
                operation_id=operation_id,
                method="POST",
                route_parameters=route_parameters,
                effective_query_parameters={},
                body=body_values,
            ),
            branch_id=BRANCH_ID,
        )

        async def invoke(connection: AsyncConnection) -> IdempotentResponse:
            service = ExpenseService(connection, codec)

            async def mutate() -> IdempotentResponse:
                result = await service.decide(
                    principal, BRANCH_ID, claim_id, body, stage="admin", approve=True
                )
                return IdempotentResponse(
                    status=200,
                    body=DataResponse(data=result).model_dump(mode="json", by_alias=True),
                    location=None,
                    resource_kind="expense_claim",
                    resource_id=claim_id,
                )

            return await IdempotencyCoordinator(IdempotencyRepository(connection)).execute(
                principal=principal,
                command=command,
                authorize_replay=lambda kind, resource_id: service.authorize_replay(
                    principal, BRANCH_ID, kind, resource_id
                ),
                mutation=mutate,
            )

        return await executor.execute(
            claims=claims(ADMIN),
            principal=principal,
            selected_admin_branch_id=BRANCH_ID,
            operation=invoke,
        )

    submission = await run_receipt(
        RAVI,
        lambda service, principal: service.create_submission(
            principal, BRANCH_ID, ReceiptSubmissionRequest()
        ),
    )
    pdf = b"%PDF-1.7\nPhase 9B synthetic receipt\n%%EOF"
    upload = ValidatedUpload(
        body=pdf,
        file_name="phase-9b.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(pdf).hexdigest(),
        submission_token=submission.submission_token,  # type: ignore[union-attr]
    )
    claimed_upload = await run_receipt(
        RAVI,
        lambda service, principal: service.claim_upload(
            principal,
            BRANCH_ID,
            submission.id,
            upload,  # type: ignore[union-attr]
        ),
    )
    receipt = await run_receipt(
        RAVI,
        lambda service, principal: service.complete_upload(principal, claimed_upload, upload),
    )
    assert receipt.expires_at is not None  # type: ignore[union-attr]
    assert str(submission.id) not in claimed_upload.object_key  # type: ignore[union-attr]
    assert RAVI_ID.hex not in claimed_upload.object_key  # type: ignore[union-attr]

    receipt_body = ExpenseCreateRequest(
        category="Travel",
        amount="350.00",
        expense_date=business_date,
        description="Phase 9B receipt claim",
        receipt_id=submission.id,  # type: ignore[union-attr]
    )
    created = await idempotent_create(CREATE_KEYS[0], receipt_body)
    replayed = await idempotent_create(CREATE_KEYS[0], receipt_body)
    assert created.body is not None and replayed.replayed and replayed.body == created.body
    receipt_claim_id = uuid.UUID(created.body["data"]["id"])  # type: ignore[index]
    await expect_code(
        "idempotency_conflict",
        idempotent_create(
            CREATE_KEYS[0],
            receipt_body.model_copy(update={"description": "Changed replay payload"}),
        ),
    )

    self_items, _ = await run_expense(
        RAVI, lambda service, principal: service.list_self(principal, ExpenseListQuery(limit=100))
    )
    assert receipt_claim_id in {item.id for item in self_items}  # type: ignore[union-attr]
    maria_items, _ = await run_expense(
        MARIA, lambda service, principal: service.list_self(principal, ExpenseListQuery(limit=100))
    )
    assert receipt_claim_id not in {item.id for item in maria_items}  # type: ignore[union-attr]

    manager_items, _ = await run_expense(
        MANAGER,
        lambda service, principal: service.list_queue(
            principal, BRANCH_ID, ExpenseListQuery(limit=100), admin=False
        ),
    )
    receipt_claim = next(item for item in manager_items if item.id == receipt_claim_id)  # type: ignore[union-attr]
    assert receipt_claim.has_receipt and receipt_claim.can_decide
    await expect_code(
        "stale_financial_state",
        run_expense(
            MANAGER,
            lambda service, principal: service.decide(
                principal,
                BRANCH_ID,
                receipt_claim_id,
                ExpenseDecisionRequest(
                    expected_updated_at=receipt_claim.updated_at - timedelta(seconds=1)
                ),
                stage="manager",
                approve=True,
            ),
        ),
    )

    with migration_engine.begin() as connection:
        connection.execute(
            text("UPDATE public.employees SET reporting_manager_id=NULL WHERE id=:id"),
            {"id": RAVI_ID},
        )
    changed_queue, _ = await run_expense(
        MANAGER,
        lambda service, principal: service.list_queue(
            principal, BRANCH_ID, ExpenseListQuery(limit=100), admin=False
        ),
    )
    assert receipt_claim_id not in {item.id for item in changed_queue}  # type: ignore[union-attr]
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE public.employees SET reporting_manager_id="
                "'21000000-0000-4000-8000-000000000001'::uuid WHERE id=:id"
            ),
            {"id": RAVI_ID},
        )

    manager_receipt = await run_receipt(
        MANAGER,
        lambda service, principal: service.load_for_download(
            principal,
            BRANCH_ID,
            submission.id,  # type: ignore[union-attr]
        ),
    )
    assert manager_receipt["expense_claim_id"] == receipt_claim_id  # type: ignore[index]
    await expect_code(
        "resource_not_found",
        run_receipt(
            MARIA,
            lambda service, principal: service.load_for_download(
                principal,
                BRANCH_ID,
                submission.id,  # type: ignore[union-attr]
            ),
        ),
    )

    approved_by_manager = await run_expense(
        MANAGER,
        lambda service, principal: service.decide(
            principal,
            BRANCH_ID,
            receipt_claim_id,
            ExpenseDecisionRequest(expected_updated_at=receipt_claim.updated_at),
            stage="manager",
            approve=True,
        ),
    )
    final_body = ExpenseDecisionRequest(expected_updated_at=approved_by_manager.updated_at)  # type: ignore[union-attr]
    approved = await idempotent_admin_approve(receipt_claim_id, final_body)
    replayed_approval = await idempotent_admin_approve(receipt_claim_id, final_body)
    assert approved.body is not None and replayed_approval.replayed
    assert approved.body == replayed_approval.body
    await expect_code(
        "idempotency_conflict",
        idempotent_admin_approve(
            receipt_claim_id, final_body.model_copy(update={"reason": "Changed payload"})
        ),
    )

    wrong_branch, _ = await run_expense(
        ADMIN,
        lambda service, principal: service.list_queue(
            principal, OTHER_BRANCH_ID, ExpenseListQuery(limit=100), admin=True
        ),
        branch_id=OTHER_BRANCH_ID,
    )
    assert receipt_claim_id not in {item.id for item in wrong_branch}  # type: ignore[union-attr]

    async def create_plain(key: uuid.UUID, description: str) -> tuple[uuid.UUID, object]:
        outcome = await idempotent_create(
            key,
            ExpenseCreateRequest(
                category="Meals",
                amount="25.00",
                expense_date=business_date,
                description=description,
            ),
        )
        assert outcome.body is not None
        claim_id = uuid.UUID(outcome.body["data"]["id"])  # type: ignore[index]
        item = next(
            item
            for item in (
                await run_expense(
                    RAVI,
                    lambda service, principal: service.list_self(
                        principal, ExpenseListQuery(limit=100)
                    ),
                )
            )[0]
            if item.id == claim_id
        )
        return claim_id, item

    concurrent_id, concurrent_item = await create_plain(
        CREATE_KEYS[1], "Concurrent expense decision"
    )
    concurrent = await asyncio.gather(
        run_expense(
            MANAGER,
            lambda service, principal: service.decide(
                principal,
                BRANCH_ID,
                concurrent_id,
                ExpenseDecisionRequest(
                    expected_updated_at=concurrent_item.updated_at,  # type: ignore[attr-defined]
                    reason="Concurrent manager rejection",
                ),
                stage="manager",
                approve=False,
            ),
        ),
        run_expense(
            ADMIN,
            lambda service, principal: service.decide(
                principal,
                BRANCH_ID,
                concurrent_id,
                ExpenseDecisionRequest(expected_updated_at=concurrent_item.updated_at),  # type: ignore[attr-defined]
                stage="admin",
                approve=True,
            ),
            branch_id=BRANCH_ID,
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(item, BaseException) for item in concurrent) == 1
    failure = next(item for item in concurrent if isinstance(item, BaseException))
    assert isinstance(failure, ServiceExecutionError)
    assert failure.code in {"stale_financial_state", "resource_not_found"}

    delete_submission = await run_receipt(
        RAVI,
        lambda service, principal: service.create_submission(
            principal, BRANCH_ID, ReceiptSubmissionRequest()
        ),
    )
    delete_upload = ValidatedUpload(
        body=pdf,
        file_name="delete-me.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(pdf).hexdigest(),
        submission_token=delete_submission.submission_token,  # type: ignore[union-attr]
    )
    delete_claimed_upload = await run_receipt(
        RAVI,
        lambda service, principal: service.claim_upload(
            principal,
            BRANCH_ID,
            delete_submission.id,
            delete_upload,  # type: ignore[union-attr]
        ),
    )
    await run_receipt(
        RAVI,
        lambda service, principal: service.complete_upload(
            principal, delete_claimed_upload, delete_upload
        ),
    )
    delete_outcome = await idempotent_create(
        CREATE_KEYS[2],
        ExpenseCreateRequest(
            category="Travel",
            amount="10.00",
            expense_date=business_date,
            description="Delete with receipt cleanup",
            receipt_id=delete_submission.id,  # type: ignore[union-attr]
        ),
    )
    assert delete_outcome.body is not None
    delete_claim_id = uuid.UUID(delete_outcome.body["data"]["id"])  # type: ignore[index]
    delete_item = next(
        item
        for item in (
            await run_expense(
                RAVI,
                lambda service, principal: service.list_self(
                    principal, ExpenseListQuery(limit=100)
                ),
            )
        )[0]
        if item.id == delete_claim_id
    )
    cleanup = await run_expense(
        RAVI,
        lambda service, principal: service.delete(
            principal,
            BRANCH_ID,
            delete_claim_id,
            delete_item.updated_at,
            admin=False,
        ),
    )
    assert cleanup is not None
    await run_receipt(
        RAVI,
        lambda service, principal: service.complete_cleanup(
            ClaimedReceiptCleanup(
                cleanup.receipt_id,
                cleanup.operation_id,
                cleanup.object_key,  # type: ignore[union-attr]
            )
        ),
    )

    expiry_submission = await run_receipt(
        RAVI,
        lambda service, principal: service.create_submission(
            principal, BRANCH_ID, ReceiptSubmissionRequest()
        ),
    )
    expiry_upload = ValidatedUpload(
        body=pdf,
        file_name="expire-me.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(pdf).hexdigest(),
        submission_token=expiry_submission.submission_token,  # type: ignore[union-attr]
    )
    expiry_claimed_upload = await run_receipt(
        RAVI,
        lambda service, principal: service.claim_upload(
            principal,
            BRANCH_ID,
            expiry_submission.id,
            expiry_upload,  # type: ignore[union-attr]
        ),
    )
    await run_receipt(
        RAVI,
        lambda service, principal: service.complete_upload(
            principal, expiry_claimed_upload, expiry_upload
        ),
    )
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE public.expense_receipts SET created_at=created_at-interval '26 hours',"
                "uploaded_at=uploaded_at-interval '26 hours',"
                "expires_at=expires_at-interval '26 hours' "
                "WHERE id=:id"
            ),
            {"id": expiry_submission.id},  # type: ignore[union-attr]
        )
    expiry_cleanup = await run_receipt(
        RAVI,
        lambda service, principal: service.request_cleanup(
            principal,
            BRANCH_ID,
            expiry_submission.id,
            "staged_expired",  # type: ignore[union-attr]
        ),
    )
    await run_receipt(
        RAVI,
        lambda service, principal: service.complete_cleanup(expiry_cleanup),
    )

    generated_claim_ids = [receipt_claim_id, concurrent_id, delete_claim_id]
    receipt_ids = [submission.id, delete_submission.id, expiry_submission.id]  # type: ignore[union-attr]
    with migration_engine.begin() as connection:
        actions = set(
            connection.execute(
                text(
                    "SELECT action FROM public.audit_events "
                    "WHERE entity_id=ANY(:claim_ids) OR entity_id=ANY(:receipt_ids)"
                ),
                {"claim_ids": generated_claim_ids, "receipt_ids": receipt_ids},
            ).scalars()
        )
        assert {
            "expense_approved",
            "expense_receipt_uploaded",
            "expense_receipt_cleanup_requested",
        } <= actions
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM public.storage_operations "
                    "WHERE entity_type='expense_receipt' AND entity_id=ANY(:ids) "
                    "AND status='succeeded'"
                ),
                {"ids": receipt_ids},
            )
            == 5
        )
        connection.execute(
            text(
                "DELETE FROM public.audit_events "
                "WHERE entity_id=ANY(:claim_ids) OR entity_id=ANY(:receipt_ids)"
            ),
            {"claim_ids": generated_claim_ids, "receipt_ids": receipt_ids},
        )
        connection.execute(
            text("DELETE FROM public.idempotency_records WHERE idempotency_key=ANY(:keys)"),
            {"keys": [*CREATE_KEYS, DECISION_KEY]},
        )
        connection.execute(
            text("DELETE FROM public.storage_operations WHERE entity_id=ANY(:ids)"),
            {"ids": receipt_ids},
        )
        connection.execute(
            text("DELETE FROM public.expense_receipts WHERE id=ANY(:ids)"),
            {"ids": receipt_ids},
        )
        connection.execute(
            text("DELETE FROM public.expense_claims WHERE id=ANY(:ids)"),
            {"ids": generated_claim_ids},
        )
    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        clean(connection, rows)
    migration_engine.dispose()
    print("Phase 9B expense database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
