#!/usr/bin/env python3
"""Exercise Phase 11D asset and professional-development boundaries."""

from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import ApplicationUserResolver
from app.db.authorization_context import AuthorizationTransactionFactory
from app.db.seed import constants as seed
from app.db.seed.fixtures import build_rows
from app.db.seed.runner import apply_rows, clean, validate
from app.schemas.assets import (
    AssetAssignmentResponse,
    AssetAssignRequest,
    AssetCreateRequest,
    AssetReturnRequest,
    AssetUpdateRequest,
)
from app.schemas.development import (
    CertificationStaffCreateRequest,
    CmeRequirementRequest,
    TrainingCompleteRequest,
    TrainingStaffCreateRequest,
    TrainingUpdateRequest,
)
from app.services.assets import AssetService
from app.services.development import DevelopmentService
from app.services.execution import AuthorizedServiceExecutor, ServiceExecutionError
from app.services.leave_attachment import ValidatedUpload
from app.storage.scanner_worker import _record_result, claim_scan
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ADMIN = "hr.admin@horizon.test"
RAVI = "ravi.employee@horizon.test"
AISHA = "aisha.manager@horizon.test"
BRANCH_ID = seed.BRANCH_DXB
SCANNER_DEFINITION = "synthetic-v1"
OBJECT_KEY = b"d" * 32


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
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "b2d4f6a8c0e5"
        )
        columns = set(
            connection.execute(
                text(
                    "SELECT table_name,column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name IN "
                    "('assets','training_records','certifications') AND column_name IN "
                    "('updated_at','content_type','size_bytes','sha256',"
                    "'file_security_scan_id','created_by_app_user_id')"
                )
            ).all()
        )
        assert ("assets", "updated_at") in columns
        for table in ("training_records", "certifications"):
            assert {
                (table, "updated_at"),
                (table, "content_type"),
                (table, "size_bytes"),
                (table, "sha256"),
                (table, "file_security_scan_id"),
                (table, "created_by_app_user_id"),
            } <= columns

    runtime_engine = create_async_engine(
        database_url("workloop_runtime", "WORKLOOP_RUNTIME_PASSWORD")
    )
    scanner_engine = create_async_engine(
        database_url("workloop_file_scanner", "WORKLOOP_FILE_SCANNER_PASSWORD")
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
    assert ravi.employee_id is not None and aisha.employee_id is not None

    async def run(principal: object, subject: str, selected: object, operation: object):
        return await executor.execute(
            claims=claims(subject),
            principal=principal,  # type: ignore[arg-type]
            selected_admin_branch_id=selected,  # type: ignore[arg-type]
            operation=operation,  # type: ignore[arg-type]
        )

    asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).create(
            admin,
            BRANCH_ID,
            AssetCreateRequest.model_validate(
                {
                    "name": "Phase 11D tablet",
                    "assetCode": " phase-11d-asset ",
                    "category": "clinical",
                    "brand": "",
                    "model": "",
                    "serialNumber": "SYNTH-11D",
                    "purchaseDate": "2026-09-23",
                    "purchaseCost": "1234.50",
                    "notes": "Synthetic Phase 11D proof",
                }
            ),
        ),
    )
    assert asset.asset_code == "PHASE-11D-ASSET"
    assert asset.purchase_cost == Decimal("1234.50")
    updated_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).update(
            admin,
            BRANCH_ID,
            asset.id,
            AssetUpdateRequest.model_validate(
                {
                    "name": "Phase 11D clinical tablet",
                    "assetCode": asset.asset_code,
                    "category": asset.category,
                    "brand": asset.brand,
                    "model": asset.model,
                    "serialNumber": asset.serial_number,
                    "purchaseDate": asset.purchase_date,
                    "purchaseCost": str(asset.purchase_cost),
                    "notes": asset.notes,
                    "expectedUpdatedAt": asset.updated_at,
                }
            ),
        ),
    )
    assert updated_asset.name == "Phase 11D clinical tablet"
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AssetService(connection).update(
                admin,
                BRANCH_ID,
                asset.id,
                AssetUpdateRequest.model_validate(
                    {
                        "name": "Stale update",
                        "assetCode": asset.asset_code,
                        "category": asset.category,
                        "brand": asset.brand,
                        "model": asset.model,
                        "serialNumber": asset.serial_number,
                        "purchaseDate": asset.purchase_date,
                        "purchaseCost": str(asset.purchase_cost),
                        "notes": asset.notes,
                        "expectedUpdatedAt": asset.updated_at,
                    }
                ),
            ),
        ),
    )
    repair_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).transition(
            admin,
            BRANCH_ID,
            asset.id,
            "under_repair",
            updated_asset.updated_at,
        ),
    )
    asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).transition(
            admin,
            BRANCH_ID,
            asset.id,
            "available",
            repair_asset.updated_at,
        ),
    )
    assignment = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).assign(
            admin,
            BRANCH_ID,
            asset.id,
            AssetAssignRequest(
                employee_id=ravi.employee_id,
                condition_at_handover="new",
                notes="",
                expected_updated_at=asset.updated_at,
            ),
        ),
    )
    assert assignment.employee_id == ravi.employee_id and assignment.return_date is None
    self_assets = await run(
        ravi,
        RAVI,
        None,
        lambda connection: AssetService(connection).list_self(ravi, BRANCH_ID, 50),
    )
    assert any(item.id == assignment.id for item in self_assets)
    assigned_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).get(admin, BRANCH_ID, asset.id),
    )
    returned = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).return_asset(
            admin,
            BRANCH_ID,
            asset.id,
            AssetReturnRequest(
                condition_at_return="good",
                notes="",
                expected_updated_at=assigned_asset.updated_at,
            ),
        ),
    )
    assert returned.return_date is not None
    retained_history = await run(
        ravi,
        RAVI,
        None,
        lambda connection: AssetService(connection).list_self(ravi, BRANCH_ID, 50),
    )
    assert any(
        item.id == assignment.id and item.return_date is not None
        for item in retained_history
    )
    current_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).get(admin, BRANCH_ID, asset.id),
    )
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AssetService(connection).delete(
                admin, BRANCH_ID, asset.id, current_asset.updated_at
            ),
        ),
    )

    with migration_engine.connect() as connection:
        other_branch_employee_id = connection.execute(
            text(
                "SELECT id FROM employees WHERE company_id=:company_id "
                "AND branch_id=:branch_id AND active ORDER BY id LIMIT 1"
            ),
            {"company_id": admin.company_id, "branch_id": seed.BRANCH_AUH},
        ).scalar_one()
    cross_scope_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).create(
            admin,
            BRANCH_ID,
            AssetCreateRequest.model_validate(
                {"name": "Phase 11D scope asset", "assetCode": "PHASE-11D-SCOPE"}
            ),
        ),
    )
    await expect_code(
        "resource_not_found",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AssetService(connection).assign(
                admin,
                BRANCH_ID,
                cross_scope_asset.id,
                AssetAssignRequest(
                    employee_id=other_branch_employee_id,
                    condition_at_handover="new",
                    notes="",
                    expected_updated_at=cross_scope_asset.updated_at,
                ),
            ),
        ),
    )
    await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).delete(
            admin,
            BRANCH_ID,
            cross_scope_asset.id,
            cross_scope_asset.updated_at,
        ),
    )

    concurrent_asset = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).create(
            admin,
            BRANCH_ID,
            AssetCreateRequest.model_validate(
                {"name": "Phase 11D concurrent asset", "assetCode": "PHASE-11D-RACE"}
            ),
        ),
    )

    async def assign_concurrent(employee_id: object):
        return await run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: AssetService(connection).assign(
                admin,
                BRANCH_ID,
                concurrent_asset.id,
                AssetAssignRequest.model_validate(
                    {
                        "employeeId": employee_id,
                        "conditionAtHandover": "new",
                        "notes": "",
                        "expectedUpdatedAt": concurrent_asset.updated_at,
                    }
                ),
            ),
        )

    assignment_results = await asyncio.gather(
        assign_concurrent(ravi.employee_id),
        assign_concurrent(aisha.employee_id),
        return_exceptions=True,
    )
    concurrent_assignments = [
        result
        for result in assignment_results
        if isinstance(result, AssetAssignmentResponse)
    ]
    concurrent_errors = [
        result
        for result in assignment_results
        if isinstance(result, ServiceExecutionError)
    ]
    assert len(concurrent_assignments) == 1
    assert len(concurrent_errors) == 1 and concurrent_errors[0].code == "state_conflict"
    concurrent_current = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).get(
            admin, BRANCH_ID, concurrent_asset.id
        ),
    )
    concurrent_return = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: AssetService(connection).return_asset(
            admin,
            BRANCH_ID,
            concurrent_asset.id,
            AssetReturnRequest(
                condition_at_return="good",
                notes="",
                expected_updated_at=concurrent_current.updated_at,
            ),
        ),
    )
    assert concurrent_return.id == concurrent_assignments[0].id

    rolled_back_ids: list[object] = []

    async def force_asset_rollback(connection: AsyncConnection) -> object:
        rolled_back = await AssetService(connection).create(
            admin,
            BRANCH_ID,
            AssetCreateRequest.model_validate(
                {"name": "Phase 11D rollback asset", "assetCode": "PHASE-11D-ROLLBACK"}
            ),
        )
        rolled_back_ids.append(rolled_back.id)
        raise ServiceExecutionError("state_conflict")

    await expect_code(
        "state_conflict",
        run(admin, ADMIN, BRANCH_ID, force_asset_rollback),
    )
    with migration_engine.connect() as connection:
        assert (
            rolled_back_ids
            and connection.execute(
                text("SELECT count(*) FROM assets WHERE id=:id"),
                {"id": rolled_back_ids[0]},
            ).scalar_one()
            == 0
        )

    try:
        TrainingStaffCreateRequest.model_validate(
            {
                "trainingTitle": "Forbidden self cost",
                "trainingType": "external",
                "provider": "",
                "startDate": "2026-09-01",
                "endDate": None,
                "durationHours": None,
                "notes": "",
                "cost": "10.00",
                "isCme": True,
                "status": "completed",
            }
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("self training accepted administrator-only fields")

    training = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).create_training(
            ravi,
            BRANCH_ID,
            TrainingStaffCreateRequest.model_validate(
                {
                    "trainingTitle": "Phase 11D CME",
                    "trainingType": "external",
                    "provider": "Synthetic Provider",
                    "startDate": "2028-09-01",
                    "endDate": None,
                    "durationHours": None,
                    "notes": "",
                }
            ),
            scope="self",
        ),
    )
    assert training.status == "planned" and training.cost == Decimal("0.00")
    updated_training = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).update_training(
            ravi,
            BRANCH_ID,
            training.id,
            TrainingUpdateRequest.model_validate(
                {
                    "trainingTitle": "Phase 11D CME updated",
                    "trainingType": training.training_type,
                    "provider": training.provider,
                    "startDate": training.start_date,
                    "endDate": training.end_date,
                    "durationHours": training.duration_hours,
                    "cost": "0.00",
                    "notes": training.notes,
                    "isCme": False,
                    "expectedUpdatedAt": training.updated_at,
                }
            ),
            scope="staff",
        ),
    )
    assert updated_training.training_title == "Phase 11D CME updated"
    await expect_code(
        "operation_not_permitted",
        run(
            ravi,
            RAVI,
            None,
            lambda connection: DevelopmentService(
                connection, scanner_definition=SCANNER_DEFINITION
            ).update_training(
                ravi,
                BRANCH_ID,
                training.id,
                TrainingUpdateRequest.model_validate(
                    {
                        "trainingTitle": updated_training.training_title,
                        "trainingType": updated_training.training_type,
                        "provider": updated_training.provider,
                        "startDate": updated_training.start_date,
                        "endDate": updated_training.end_date,
                        "durationHours": updated_training.duration_hours,
                        "cost": "10.00",
                        "notes": updated_training.notes,
                        "isCme": False,
                        "expectedUpdatedAt": updated_training.updated_at,
                    }
                ),
                scope="staff",
            ),
        ),
    )
    training = updated_training
    completed = await run(
        aisha,
        AISHA,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).complete_training(
            aisha,
            BRANCH_ID,
            training.id,
            TrainingCompleteRequest.model_validate(
                {
                    "endDate": "2028-09-23",
                    "durationHours": "20.75",
                    "score": "passed",
                    "passed": True,
                    "isCme": True,
                    "expectedUpdatedAt": training.updated_at,
                }
            ),
            scope="direct_report",
        ),
    )
    assert completed.status == "completed" and completed.duration_hours == Decimal(
        "20.75"
    )
    await expect_code(
        "state_conflict",
        run(
            aisha,
            AISHA,
            None,
            lambda connection: DevelopmentService(
                connection, scanner_definition=SCANNER_DEFINITION
            ).complete_training(
                aisha,
                BRANCH_ID,
                training.id,
                TrainingCompleteRequest.model_validate(
                    {
                        "endDate": "2028-09-23",
                        "durationHours": "20.75",
                        "score": "passed",
                        "passed": True,
                        "isCme": True,
                        "expectedUpdatedAt": training.updated_at,
                    }
                ),
                scope="direct_report",
            ),
        ),
    )

    requirement = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).save_requirement(
            admin,
            BRANCH_ID,
            ravi.employee_id,
            2028,
            CmeRequirementRequest.model_validate(
                {"requiredHours": "25.0", "notes": "", "expectedUpdatedAt": None}
            ),
        ),
    )
    updated_requirement = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).save_requirement(
            admin,
            BRANCH_ID,
            ravi.employee_id,
            2028,
            CmeRequirementRequest.model_validate(
                {
                    "requiredHours": "25.0",
                    "notes": "Annual target",
                    "expectedUpdatedAt": requirement.updated_at,
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
            lambda connection: DevelopmentService(
                connection, scanner_definition=SCANNER_DEFINITION
            ).save_requirement(
                admin,
                BRANCH_ID,
                ravi.employee_id,
                2028,
                CmeRequirementRequest.model_validate(
                    {
                        "requiredHours": "30.0",
                        "notes": "Stale target",
                        "expectedUpdatedAt": requirement.updated_at,
                    }
                ),
            ),
        ),
    )
    requirement = updated_requirement
    summary = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).self_cme(ravi, BRANCH_ID, 2028),
    )
    assert requirement.required_hours == Decimal("25.0")
    assert summary.achieved_hours == Decimal("20.8") and summary.gap_hours == Decimal(
        "4.2"
    ), (summary.achieved_hours, summary.gap_hours)

    rejected_certification = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).create_certification(
            ravi,
            BRANCH_ID,
            CertificationStaffCreateRequest.model_validate(
                {
                    "certificationName": "Phase 11D rejected certificate",
                    "issuingBody": "Synthetic Authority",
                    "certificateNo": "SYNTH-11D-REJECT",
                    "issuedDate": "2026-09-01",
                    "expiryDate": "2027-09-01",
                    "notes": "",
                }
            ),
            scope="self",
        ),
    )
    rejected_certification = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).decide_certification(
            admin,
            BRANCH_ID,
            rejected_certification.id,
            rejected_certification.updated_at,
            verify=False,
            reason="Synthetic rejection",
        ),
    )
    assert rejected_certification.status == "rejected"
    await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).delete_certification(
            ravi,
            BRANCH_ID,
            rejected_certification.id,
            rejected_certification.updated_at,
            scope="staff",
        ),
    )

    certification = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).create_certification(
            ravi,
            BRANCH_ID,
            CertificationStaffCreateRequest.model_validate(
                {
                    "certificationName": "Phase 11D Certificate",
                    "issuingBody": "Synthetic Authority",
                    "certificateNo": "SYNTH-11D-CERT",
                    "issuedDate": "2026-09-01",
                    "expiryDate": "2027-09-01",
                    "notes": "",
                }
            ),
            scope="self",
        ),
    )
    body = b"%PDF-1.7\nPhase 11D certification evidence\n%%EOF"
    upload = ValidatedUpload(
        body=body,
        file_name="phase-11d-certificate.pdf",
        content_type="application/pdf",
        sha256=hashlib.sha256(body).hexdigest(),
        submission_token="direct",
    )
    claimed = await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection,
            scanner_definition=SCANNER_DEFINITION,
            object_key_hmac_key=OBJECT_KEY,
        ).claim_evidence_upload(
            ravi,
            BRANCH_ID,
            "certification_evidence",
            certification.id,
            upload,
            scope="staff",
        ),
    )
    await run(
        ravi,
        RAVI,
        None,
        lambda connection: DevelopmentService(
            connection,
            scanner_definition=SCANNER_DEFINITION,
            object_key_hmac_key=OBJECT_KEY,
        ).complete_evidence_upload(ravi, claimed, upload),
    )
    uploaded_certification = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).get_certification(admin, BRANCH_ID, certification.id, scope="admin"),
    )
    assert (
        uploaded_certification.status == "pending_review"
        and uploaded_certification.has_evidence
    )
    await expect_code(
        "service_unavailable",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: DevelopmentService(
                connection, scanner_definition=SCANNER_DEFINITION
            ).load_evidence_download(
                admin,
                BRANCH_ID,
                "certification_evidence",
                certification.id,
                scope="admin",
            ),
        ),
    )
    verified = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).decide_certification(
            admin,
            BRANCH_ID,
            certification.id,
            uploaded_certification.updated_at,
            verify=True,
            reason=None,
        ),
    )
    claimed_scan = await claim_scan(scanner_engine)
    assert (
        claimed_scan is not None
        and claimed_scan.entity_type == "certification_evidence"
    )
    await _record_result(
        scanner_engine,
        claimed_scan,
        status="clean",
        scanner_name="phase11d-test",
        result_signature="clean-proof",
        scanned_at=datetime.now(UTC),
    )
    released = await run(
        admin,
        ADMIN,
        BRANCH_ID,
        lambda connection: DevelopmentService(
            connection, scanner_definition=SCANNER_DEFINITION
        ).load_evidence_download(
            admin,
            BRANCH_ID,
            "certification_evidence",
            certification.id,
            scope="admin",
        ),
    )
    assert released["file_name"] == "phase-11d-certificate.pdf"
    assert verified.status == "verified"
    await expect_code(
        "state_conflict",
        run(
            admin,
            ADMIN,
            BRANCH_ID,
            lambda connection: DevelopmentService(
                connection, scanner_definition=SCANNER_DEFINITION
            ).claim_evidence_cleanup(
                admin,
                BRANCH_ID,
                "certification_evidence",
                certification.id,
                verified.updated_at,
                scope="admin",
            ),
        ),
    )

    with migration_engine.begin() as connection:
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE entity_id=ANY(:ids) "
                    "AND action IN ('asset_created','asset_assigned','asset_returned',"
                    "'training_enrolled','training_completed','cme_requirement_saved',"
                    "'certification_submitted','certification_evidence_uploaded',"
                    "'certification_verified')"
                ),
                {
                    "ids": [
                        asset.id,
                        assignment.id,
                        cross_scope_asset.id,
                        concurrent_asset.id,
                        concurrent_return.id,
                        training.id,
                        requirement.id,
                        rejected_certification.id,
                        certification.id,
                    ]
                },
            ).scalar_one()
            >= 9
        )

    await runtime_engine.dispose()
    await scanner_engine.dispose()
    with migration_engine.begin() as connection:
        connection.execute(
            text("DELETE FROM storage_operations WHERE entity_id=:id"),
            {"id": certification.id},
        )
        connection.execute(
            text("DELETE FROM certifications WHERE id=:id"),
            {"id": certification.id},
        )
        connection.execute(
            text("DELETE FROM file_security_scans WHERE entity_id=:id"),
            {"id": certification.id},
        )
        connection.execute(
            text("DELETE FROM cme_requirements WHERE id=:id"), {"id": requirement.id}
        )
        connection.execute(
            text("DELETE FROM training_records WHERE id=:id"), {"id": training.id}
        )
        connection.execute(
            text("DELETE FROM asset_assignments WHERE id=:id"), {"id": assignment.id}
        )
        connection.execute(
            text("DELETE FROM asset_assignments WHERE id=:id"),
            {"id": concurrent_return.id},
        )
        connection.execute(text("DELETE FROM assets WHERE id=:id"), {"id": asset.id})
        connection.execute(
            text("DELETE FROM assets WHERE id=:id"), {"id": concurrent_asset.id}
        )
        connection.execute(
            text("DELETE FROM audit_events WHERE entity_id=ANY(:ids)"),
            {
                "ids": [
                    asset.id,
                    assignment.id,
                    cross_scope_asset.id,
                    concurrent_asset.id,
                    concurrent_return.id,
                    training.id,
                    requirement.id,
                    rejected_certification.id,
                    certification.id,
                ]
            },
        )
        clean(connection, seed_rows)
    migration_engine.dispose()
    print("Phase 11D asset and professional-development database checks passed")


if __name__ == "__main__":
    asyncio.run(main())
