#!/usr/bin/env python3
"""Exercise Phase 11C records and benefits boundaries with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from datetime import date
from decimal import Decimal

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.employee_document import EmployeeDocumentSubmissionRequest
from app.schemas.employment_contract import (
    ContractCommandRequest,
    ContractExpectedSnapshot,
)
from app.schemas.insurance import CoverageReplaceRequest, InsurancePolicyCreateRequest
from app.services.employee_documents import (
    EmployeeDocumentListQuery,
    EmployeeDocumentService,
)
from app.services.employees import EmployeeCursorCodec
from app.services.employment_contracts import (
    EmploymentContractListQuery,
    EmploymentContractService,
)
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.insurance import InsurancePolicyListQuery, InsuranceService
from app.services.leave_attachment import ValidatedUpload
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ADMIN = "hr.admin@horizon.test"
RAVI = "ravi.employee@horizon.test"
AISHA = "aisha.manager@horizon.test"
BRANCH_ID = uuid.UUID("20000000-0000-4000-8000-000000000001")
CURSOR_CODEC = EmployeeCursorCodec(b"phase11c-pagination-key-material")


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
        assert connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one() == ("b2d4f6a8c0e5")
        columns = set(
            connection.execute(
                text(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name IN "
                    "('employee_documents','insurance_policies','employee_insurance',"
                    "'insurance_dependants') AND column_name IN "
                    "('content_type','sha256','file_security_scan_id',"
                    "'created_by_app_user_id','updated_at')"
                )
            ).all()
        )
        assert columns == {
            ("employee_documents", "content_type"),
            ("employee_documents", "sha256"),
            ("employee_documents", "file_security_scan_id"),
            ("employee_documents", "created_by_app_user_id"),
            ("employee_documents", "updated_at"),
            ("insurance_policies", "updated_at"),
            ("employee_insurance", "updated_at"),
            ("insurance_dependants", "updated_at"),
        }
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM pg_catalog.pg_trigger WHERE NOT tgisinternal "
                    "AND tgname IN ('trg_employee_documents_set_updated_at',"
                    "'trg_insurance_policies_set_updated_at',"
                    "'trg_employee_insurance_set_updated_at',"
                    "'trg_insurance_dependants_set_updated_at')"
                )
            ).scalar_one()
            == 4
        )
        delete_policy = connection.execute(
            text(
                "SELECT qual FROM pg_catalog.pg_policies WHERE schemaname='public' "
                "AND tablename='employee_documents' "
                "AND policyname='phase11c_employee_documents_delete_runtime'"
            )
        ).scalar_one()
        assert "workloop_employee_id" in delete_policy
        assert "pending_verification" in delete_policy and "rejected" in delete_policy
        assert (
            connection.execute(
                text(
                    "SELECT has_table_privilege('workloop_runtime',"
                    "'public.employee_contracts','UPDATE,DELETE')"
                )
            ).scalar_one()
            is False
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
    ravi = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=RAVI)
    aisha = await resolver.resolve(issuer=seed.SEED_ISSUER, subject=AISHA)

    async def run(
        principal: object, subject: str, selected: uuid.UUID | None, operation: object
    ):
        return await executor.execute(
            claims=claims(subject),
            principal=principal,  # type: ignore[arg-type]
            selected_admin_branch_id=selected,
            operation=operation,  # type: ignore[arg-type]
        )

    self_submission = await run(
        ravi,
        RAVI,
        None,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).create_submission(
            ravi,
            BRANCH_ID,
            EmployeeDocumentSubmissionRequest.model_validate(
                {
                    "documentType": "Passport",
                    "documentNumber": "SYNTH-11C-SELF",
                    "expiryDate": "2027-09-23",
                    "notes": "Synthetic Phase 11C proof",
                }
            ),
        ),
    )
    body = b"%PDF-1.7\nPhase 11C synthetic employee document\n%%EOF"
    upload = ValidatedUpload(
        body=body,
        file_name="phase-11c-self.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(body).hexdigest(),
        submission_token=self_submission.submission_token,
    )
    claimed = await run(
        ravi,
        RAVI,
        None,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).claim_upload(ravi, BRANCH_ID, self_submission.id, upload),
    )
    self_document = await run(
        ravi,
        RAVI,
        None,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).complete_upload(ravi, claimed, upload),
    )
    assert self_document.status == "pending_verification"
    assert set(self_document.model_dump(by_alias=False)) == {
        "id",
        "employee_id",
        "document_type",
        "status",
        "rejection_reason",
        "file_name",
        "size_bytes",
        "content_type",
        "expiry_date",
        "notes",
        "reviewer_name",
        "uploaded_at",
        "reviewed_at",
        "updated_at",
    }
    await expect_code(
        "service_unavailable",
        run(
            ravi,
            RAVI,
            None,
            lambda connection: EmployeeDocumentService(
                connection,
                object_key_hmac_key=b"c" * 32,
                scanner_definition="synthetic-v1",
            ).load_for_download(ravi, BRANCH_ID, self_document.id),
        ),
    )
    rejected_document = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).decide(
            admin,
            BRANCH_ID,
            self_document.id,
            self_document.updated_at,
            verify=False,
            reason="Image is unreadable",
        ),
    )
    assert rejected_document.status == "rejected"
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: EmployeeDocumentService(
                connection,
                object_key_hmac_key=b"c" * 32,
                scanner_definition="synthetic-v1",
            ).decide(
                admin,
                BRANCH_ID,
                self_document.id,
                self_document.updated_at,
                verify=False,
                reason="Different reason",
            ),
        ),
    )

    with migration_engine.begin() as connection:
        employee_id = connection.execute(
            text("SELECT id FROM employees WHERE emp_no='H-DXB-002'")
        ).scalar_one()

    admin_submission = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).create_submission(
            admin,
            BRANCH_ID,
            EmployeeDocumentSubmissionRequest.model_validate(
                {
                    "employeeId": str(employee_id),
                    "documentType": "Passport",
                    "documentNumber": "SYNTH-11C-ADMIN",
                    "expiryDate": None,
                    "notes": "",
                }
            ),
        ),
    )
    admin_body = b"%PDF-1.7\nPhase 11C synthetic administrator document\n%%EOF"
    admin_upload = ValidatedUpload(
        body=admin_body,
        file_name="phase-11c-admin.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(admin_body).hexdigest(),
        submission_token=admin_submission.submission_token,
    )
    admin_claimed = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).claim_upload(admin, BRANCH_ID, admin_submission.id, admin_upload),
    )
    admin_document = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection, object_key_hmac_key=b"c" * 32, scanner_definition="synthetic-v1"
        ).complete_upload(admin, admin_claimed, admin_upload),
    )
    assert admin_document.status == "verified"
    await expect_code(
        "service_unavailable",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: EmployeeDocumentService(
                connection,
                object_key_hmac_key=b"c" * 32,
                scanner_definition="synthetic-v1",
            ).load_for_download(admin, BRANCH_ID, admin_document.id),
        ),
    )

    first_document_page, document_cursor = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection,
            object_key_hmac_key=b"c" * 32,
            scanner_definition="synthetic-v1",
            cursor_codec=CURSOR_CODEC,
        ).list(
            admin,
            BRANCH_ID,
            EmployeeDocumentListQuery(
                employee_id=employee_id,
                status=None,
                document_type=None,
                limit=1,
                cursor=None,
            ),
            operation_id="list_employee_documents",
        ),
    )
    assert len(first_document_page) == 1 and document_cursor is not None
    second_document_page, _ = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmployeeDocumentService(
            connection,
            object_key_hmac_key=b"c" * 32,
            scanner_definition="synthetic-v1",
            cursor_codec=CURSOR_CODEC,
        ).list(
            admin,
            BRANCH_ID,
            EmployeeDocumentListQuery(
                employee_id=employee_id,
                status=None,
                document_type=None,
                limit=1,
                cursor=document_cursor,
            ),
            operation_id="list_employee_documents",
        ),
    )
    assert len(second_document_page) == 1
    assert second_document_page[0].id != first_document_page[0].id
    await expect_code(
        "operation_not_permitted",
        run(
            aisha,
            AISHA,
            None,
            lambda connection: EmployeeDocumentService(
                connection,
                object_key_hmac_key=b"c" * 32,
                scanner_definition="synthetic-v1",
                cursor_codec=CURSOR_CODEC,
            ).list(
                aisha,
                BRANCH_ID,
                EmployeeDocumentListQuery(
                    employee_id=employee_id,
                    status=None,
                    document_type=None,
                    limit=50,
                    cursor=None,
                ),
                operation_id="list_self_employee_documents",
            ),
        ),
    )
    await expect_code(
        "operation_not_permitted",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: EmployeeDocumentService(
                connection,
                object_key_hmac_key=b"c" * 32,
                scanner_definition="synthetic-v1",
            ).claim_cleanup(
                admin,
                BRANCH_ID,
                admin_document.id,
                admin_document.updated_at,
            ),
        ),
    )

    policy = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: InsuranceService(connection).create_policy(
            admin,
            BRANCH_ID,
            InsurancePolicyCreateRequest.model_validate(
                {
                    "insurerName": "Phase 11C Synthetic Insurer",
                    "policyNumber": "SYNTH-11C-POLICY",
                    "tierName": "Synthetic Gold",
                    "annualPremium": "1234.50",
                    "renewalDate": "2027-09-23",
                    "brokerName": "",
                    "brokerContact": "",
                    "notes": "Synthetic Phase 11C proof",
                }
            ),
        ),
    )
    assert policy.annual_premium == Decimal("1234.50")
    first_policy_page, policy_cursor = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: InsuranceService(connection).list_policies(
            admin,
            BRANCH_ID,
            InsurancePolicyListQuery(
                renewal_from=None,
                renewal_to=None,
                search=None,
                limit=1,
                cursor=None,
            ),
            CURSOR_CODEC,
        ),
    )
    assert len(first_policy_page) == 1 and policy_cursor is not None
    second_policy_page, _ = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: InsuranceService(connection).list_policies(
            admin,
            BRANCH_ID,
            InsurancePolicyListQuery(
                renewal_from=None,
                renewal_to=None,
                search=None,
                limit=1,
                cursor=policy_cursor,
            ),
            CURSOR_CODEC,
        ),
    )
    assert len(second_policy_page) == 1
    assert second_policy_page[0].id != first_policy_page[0].id

    async def current_coverage_updated_at(connection: AsyncConnection):
        result = await connection.execute(
            text(
                "SELECT updated_at FROM employee_insurance "
                "WHERE branch_id=:branch_id AND employee_id=:employee_id"
            ),
            {"branch_id": BRANCH_ID, "employee_id": employee_id},
        )
        return result.scalar_one_or_none()

    expected_coverage_updated_at = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        current_coverage_updated_at,
    )
    coverage = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: InsuranceService(connection).replace_coverage(
            admin,
            BRANCH_ID,
            employee_id,
            CoverageReplaceRequest.model_validate(
                {
                    "policyId": str(policy.id),
                    "memberId": "SYNTH-11C-MEMBER",
                    "cardNumber": "SYNTH-SECRET-CARD",
                    "effectiveDate": "2026-09-23",
                    "expiryDate": "2027-09-23",
                    "tierName": "Synthetic Gold",
                    "expectedUpdatedAt": expected_coverage_updated_at,
                }
            ),
        ),
    )
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: InsuranceService(connection).replace_coverage(
                admin,
                BRANCH_ID,
                employee_id,
                CoverageReplaceRequest.model_validate(
                    {
                        "policyId": str(policy.id),
                        "memberId": "SYNTH-11C-CHANGED",
                        "cardNumber": "",
                        "effectiveDate": "2026-09-23",
                        "expiryDate": None,
                        "tierName": "Synthetic Gold",
                        "expectedUpdatedAt": expected_coverage_updated_at,
                    }
                ),
            ),
        ),
    )
    assert coverage.employee_id == employee_id
    self_projection = await run(
        ravi,
        RAVI,
        None,
        lambda connection: InsuranceService(connection).self_coverage(ravi),
    )
    assert set(self_projection.model_dump(by_alias=False)) == {
        "policy_id",
        "insurer_name",
        "tier_name",
        "effective_date",
        "expiry_date",
    }

    async def load_contract_snapshot(connection: AsyncConnection):
        current = (
            await connection.execute(
                text(
                    "SELECT contract_type,contract_end_date,updated_at FROM employees "
                    "WHERE id=:id"
                ),
                {"id": employee_id},
            )
        ).one()
        latest_id = (
            await connection.execute(
                text(
                    "SELECT id FROM employee_contracts WHERE employee_id=:id "
                    "ORDER BY created_at DESC,id DESC LIMIT 1"
                ),
                {"id": employee_id},
            )
        ).scalar_one_or_none()
        return (
            current.contract_type,
            ContractExpectedSnapshot(
                employee_updated_at=current.updated_at,
                current_contract_type=current.contract_type,
                current_contract_end_date=current.contract_end_date,
                latest_contract_event_id=latest_id,
            ),
        )

    current_contract_type, expected_contract = await run(
        admin, ADMIN, BRANCH_ID, load_contract_snapshot
    )

    async def attempt_renewal(end_date: date):
        request = ContractCommandRequest(
            contract_type=current_contract_type,
            start_date=date(2027, 1, 1),
            end_date=end_date if current_contract_type == "Limited" else None,
            notes="Synthetic Phase 11C renewal",
            expected=expected_contract,
        )
        return await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: EmploymentContractService(connection).record(
                admin, BRANCH_ID, employee_id, "renewed", request
            ),
        )

    renewal_results = await asyncio.gather(
        attempt_renewal(date(2027, 12, 31)),
        attempt_renewal(date(2028, 12, 31)),
        return_exceptions=True,
    )
    successful_contracts = [
        result for result in renewal_results if not isinstance(result, BaseException)
    ]
    failed_contracts = [
        result
        for result in renewal_results
        if isinstance(result, ServiceExecutionError)
    ]
    assert len(successful_contracts) == 1
    assert len(failed_contracts) == 1 and failed_contracts[0].code == "state_conflict"
    contract = successful_contracts[0]
    assert contract.action == "renewed"
    first_contract_page, contract_cursor = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmploymentContractService(connection).list(
            admin,
            BRANCH_ID,
            EmploymentContractListQuery(employee_id=employee_id, limit=1, cursor=None),
            CURSOR_CODEC,
        ),
    )
    assert len(first_contract_page) == 1 and contract_cursor is not None
    second_contract_page, _ = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: EmploymentContractService(connection).list(
            admin,
            BRANCH_ID,
            EmploymentContractListQuery(
                employee_id=employee_id,
                limit=1,
                cursor=contract_cursor,
            ),
            CURSOR_CODEC,
        ),
    )
    assert len(second_contract_page) == 1
    assert second_contract_page[0].id != first_contract_page[0].id
    with migration_engine.begin() as connection:
        unchanged_prior = connection.execute(
            text(
                "SELECT count(*) FROM employee_contracts WHERE employee_id=:employee_id "
                "AND id<>:id"
            ),
            {"employee_id": employee_id, "id": contract.id},
        ).scalar_one()
        assert unchanged_prior >= 1
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE action IN "
                    "('employee_document_uploaded','employee_document_rejected',"
                    "'insurance_policy_created',"
                    "'insurance_coverage_replaced','employment_contract_recorded')"
                )
            ).scalar_one()
            >= 6
        )

    await runtime_engine.dispose()
    with migration_engine.begin() as connection:
        document_ids = [self_document.id, admin_document.id]
        connection.execute(
            text(
                "DELETE FROM storage_operations WHERE entity_type='employee_document' "
                "AND entity_id=ANY(:ids)"
            ),
            {"ids": document_ids},
        )
        connection.execute(
            text("DELETE FROM employee_documents WHERE id=ANY(:ids)"),
            {"ids": document_ids},
        )
        connection.execute(
            text(
                "DELETE FROM file_security_scans WHERE entity_type='employee_document' "
                "AND entity_id=ANY(:ids)"
            ),
            {"ids": document_ids},
        )
        connection.execute(
            text("DELETE FROM employee_insurance WHERE id=:id"), {"id": coverage.id}
        )
        connection.execute(
            text("DELETE FROM insurance_policies WHERE id=:id"), {"id": policy.id}
        )
        connection.execute(
            text(
                "DELETE FROM employee_job_history WHERE employee_id=:employee_id "
                "AND reason='Employment contract renewed'"
            ),
            {"employee_id": employee_id},
        )
        connection.execute(
            text("DELETE FROM employee_contracts WHERE id=:id"), {"id": contract.id}
        )
        connection.execute(
            text(
                "DELETE FROM audit_events WHERE action IN "
                "('employee_document_uploaded','employee_document_rejected',"
                "'insurance_policy_created',"
                "'insurance_coverage_replaced','employment_contract_recorded')"
            )
        )
        clean(connection, seed_rows)
    migration_engine.dispose()
    print("Phase 11C records and benefits database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
