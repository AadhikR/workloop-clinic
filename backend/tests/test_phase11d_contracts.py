import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.assets import AssetCreateRequest, AssetResponse
from app.schemas.development import (
    CertificationResponse,
    CmeSummaryResponse,
    TrainingAdminCreateRequest,
    TrainingResponse,
)
from app.services.leave_attachment import parse_direct_upload

ID = UUID("12345678-1234-4234-8234-123456789abc")
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_phase11d_routes_are_registered_once() -> None:
    operations: list[str] = []
    for path_item in create_app().openapi()["paths"].values():
        for raw_operation in path_item.values():
            if isinstance(raw_operation, dict):
                operation = cast(dict[str, object], raw_operation)
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str):
                    operations.append(operation_id)
    expected = {
        "list_assets",
        "list_self_assets",
        "create_asset",
        "update_asset",
        "change_asset_status",
        "assign_asset",
        "return_asset",
        "delete_asset",
        "list_training_records",
        "create_training_record",
        "list_self_training_records",
        "create_self_training_record",
        "list_direct_report_training_records",
        "create_direct_report_training_record",
        "update_training_record",
        "complete_training_record",
        "delete_training_record",
        "list_certifications",
        "create_certification",
        "list_self_certifications",
        "create_self_certification",
        "list_direct_report_certifications",
        "create_direct_report_certification",
        "verify_certification",
        "reject_certification",
        "delete_certification",
        "upload_training_evidence",
        "download_training_evidence",
        "delete_training_evidence",
        "upload_certification_evidence",
        "download_certification_evidence",
        "delete_certification_evidence",
        "read_cme_requirement",
        "save_cme_requirement",
        "delete_cme_requirement",
        "read_self_cme",
    }
    assert expected <= set(operations)
    assert all(operations.count(operation) == 1 for operation in expected)


def test_asset_code_and_money_are_canonical() -> None:
    request = AssetCreateRequest.model_validate(
        {
            "name": "Synthetic laptop",
            "assetCode": " lap-001 ",
            "category": "Laptop",
            "purchaseCost": "1250.75",
        }
    )
    assert request.asset_code == "LAP-001"
    assert request.purchase_cost == Decimal("1250.75")
    for invalid in (1250.75, "1250", "1250.7", "10000000000.00"):
        with pytest.raises(ValidationError):
            AssetCreateRequest.model_validate(
                {
                    "name": "Synthetic laptop",
                    "assetCode": "LAP-001",
                    "purchaseCost": invalid,
                }
            )


def test_direct_evidence_upload_derives_digest_on_the_server() -> None:
    file_body = b"%PDF-1.7\nPhase 11D browser upload\n%%EOF"
    boundary = "phase11d-boundary"
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="certificate.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + file_body
        + f"\r\n--{boundary}--\r\n".encode()
    )
    upload = parse_direct_upload(f"multipart/form-data; boundary={boundary}", body)
    assert upload.file_name == "certificate.pdf"
    assert upload.content_type == "application/pdf"
    assert upload.sha256 == hashlib.sha256(file_body).hexdigest()


def test_training_decimals_and_dates_are_strict() -> None:
    values = {
        "employeeId": str(ID),
        "trainingTitle": "Synthetic course",
        "trainingType": "external",
        "provider": "Synthetic provider",
        "startDate": "2026-10-01",
        "endDate": "2026-10-02",
        "durationHours": "12.50",
        "cost": "0.00",
        "isCme": True,
        "notes": "",
    }
    request = TrainingAdminCreateRequest.model_validate(values)
    assert request.duration_hours == Decimal("12.50")
    assert request.cost == Decimal("0.00")
    with pytest.raises(ValidationError):
        TrainingAdminCreateRequest.model_validate({**values, "durationHours": "12.5"})
    with pytest.raises(ValidationError):
        TrainingAdminCreateRequest.model_validate(
            {**values, "startDate": "2026-10-03", "endDate": "2026-10-02"}
        )


def test_cme_summary_rounds_once_and_never_returns_negative_gap() -> None:
    response = CmeSummaryResponse(
        year=2026,
        target_hours=Decimal("25.0"),
        achieved_hours=Decimal("20.8"),
        gap_hours=Decimal("4.2"),
    ).model_dump(mode="json", by_alias=True)
    assert response == {
        "year": 2026,
        "targetHours": "25.0",
        "achievedHours": "20.8",
        "gapHours": "4.2",
    }


def test_phase11d_responses_hide_storage_and_scan_internals() -> None:
    asset = AssetResponse(
        id=ID,
        name="Synthetic laptop",
        asset_code="LAP-001",
        category="Laptop",
        brand="",
        model="",
        serial_number="",
        purchase_date=None,
        purchase_cost=Decimal("1250.75"),
        status="available",
        notes="",
        created_at=NOW,
        updated_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    training = TrainingResponse(
        id=ID,
        employee_id=ID,
        training_title="Synthetic course",
        training_type="external",
        provider="Synthetic provider",
        start_date=date(2026, 10, 1),
        end_date=None,
        duration_hours=Decimal("12.50"),
        cost=Decimal("0.00"),
        status="planned",
        score="",
        passed=None,
        notes="",
        is_cme=False,
        has_evidence=False,
        file_name=None,
        content_type=None,
        created_at=NOW,
        updated_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    certification = CertificationResponse(
        id=ID,
        employee_id=ID,
        certification_name="Synthetic licence",
        issuing_body="Synthetic authority",
        certificate_no="",
        issued_date=None,
        expiry_date=None,
        notes="",
        status="pending_review",
        has_evidence=False,
        file_name=None,
        content_type=None,
        reviewed_at=None,
        created_at=NOW,
        updated_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    for response in (asset, training, certification):
        assert "storagePath" not in response
        assert "sha256" not in response
        assert "fileSecurityScanId" not in response
