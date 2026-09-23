from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection
from starlette.requests import Request

from app.auth.access_token import AccessTokenClaims
from app.auth.application_user import AuthorizationPrincipal
from app.main import create_app
from app.models.identity import AccountStatus, AppRole
from app.phase11c_support import idempotent_mutation
from app.schemas.employee_document import (
    EmployeeDocumentResponse,
    EmployeeDocumentSubmissionRequest,
)
from app.schemas.employment_contract import ContractCommandRequest
from app.schemas.insurance import CoverageReplaceRequest, InsurancePolicyCreateRequest
from app.services.execution import ServiceExecutionError
from app.services.idempotency import IdempotentResponse

ID = UUID("12345678-1234-4234-8234-123456789abc")
NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_phase11c_routes_are_registered_once() -> None:
    operations: list[str] = []
    for path_item in create_app().openapi()["paths"].values():
        for raw_operation in path_item.values():
            if isinstance(raw_operation, dict):
                operation = cast(dict[str, object], raw_operation)
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str):
                    operations.append(operation_id)
    expected = {
        "list_employee_documents",
        "list_self_employee_documents",
        "create_employee_document_submission",
        "upload_employee_document",
        "verify_employee_document",
        "reject_employee_document",
        "download_employee_document",
        "delete_employee_document",
        "list_insurance_policies",
        "create_insurance_policy",
        "update_insurance_policy",
        "delete_insurance_policy",
        "replace_employee_coverage",
        "list_insurance_dependants",
        "create_insurance_dependant",
        "update_insurance_dependant",
        "delete_insurance_dependant",
        "read_self_insurance",
        "list_employee_contracts",
        "record_new_contract",
        "renew_employee_contract",
        "convert_employee_contract",
        "record_contract_not_renewed",
    }
    assert expected <= set(operations)
    assert all(operations.count(operation) == 1 for operation in expected)


def test_document_submission_rejects_unknown_type_and_unknown_field() -> None:
    valid = {
        "employeeId": str(ID),
        "documentType": "Passport",
        "documentNumber": "SYNTH-001",
        "expiryDate": "2027-09-23",
        "notes": "Synthetic fixture",
    }
    assert EmployeeDocumentSubmissionRequest.model_validate(valid).document_number == "SYNTH-001"
    with pytest.raises(ValidationError):
        EmployeeDocumentSubmissionRequest.model_validate({**valid, "documentType": "Secret"})
    with pytest.raises(ValidationError):
        EmployeeDocumentSubmissionRequest.model_validate({**valid, "objectKey": "leak"})


def test_document_response_has_no_sensitive_storage_fields() -> None:
    response = EmployeeDocumentResponse(
        id=ID,
        employee_id=ID,
        document_type="Passport",
        status="pending_verification",
        rejection_reason=None,
        file_name="passport.pdf",
        size_bytes=100,
        content_type="application/pdf",
        expiry_date=date(2027, 9, 23),
        notes="",
        reviewer_name=None,
        uploaded_at=NOW,
        reviewed_at=None,
        updated_at=NOW,
    ).model_dump(mode="json", by_alias=True)
    assert set(response) == {
        "id",
        "employeeId",
        "documentType",
        "status",
        "rejectionReason",
        "fileName",
        "sizeBytes",
        "contentType",
        "expiryDate",
        "notes",
        "reviewerName",
        "uploadedAt",
        "reviewedAt",
        "updatedAt",
    }


def test_insurance_money_and_dates_are_exact() -> None:
    values = {
        "insurerName": "Synthetic Insurer",
        "policyNumber": "SYNTH-POLICY",
        "tierName": "Gold",
        "annualPremium": "1000.00",
        "renewalDate": None,
        "brokerName": "",
        "brokerContact": "",
        "notes": "",
    }
    policy = InsurancePolicyCreateRequest.model_validate(values)
    assert policy.annual_premium == Decimal("1000.00")
    for invalid in (1000, "1000", "1000.0", "1,000.00", "10000000000.00"):
        with pytest.raises(ValidationError):
            InsurancePolicyCreateRequest.model_validate({**values, "annualPremium": invalid})
    with pytest.raises(ValidationError):
        CoverageReplaceRequest.model_validate(
            {
                "policyId": str(ID),
                "memberId": "SYNTH-MEMBER",
                "cardNumber": "",
                "effectiveDate": "2026-09-23",
                "expiryDate": "2026-09-22",
                "tierName": "Gold",
                "expectedUpdatedAt": None,
            }
        )


def test_contract_date_and_type_rules() -> None:
    expected = {
        "employeeUpdatedAt": NOW.isoformat().replace("+00:00", "Z"),
        "currentContractType": "Limited",
        "currentContractEndDate": "2026-12-31",
        "latestContractEventId": str(ID),
    }
    limited = ContractCommandRequest.model_validate(
        {
            "contractType": "Limited",
            "startDate": "2027-01-01",
            "endDate": "2027-12-31",
            "notes": "",
            "expected": expected,
        }
    )
    assert limited.end_date == date(2027, 12, 31)
    with pytest.raises(ValidationError):
        ContractCommandRequest.model_validate(
            {
                "contractType": "Unlimited",
                "startDate": "2027-01-01",
                "endDate": "2027-12-31",
                "notes": "",
                "expected": expected,
            }
        )


class _ImmediateExecutor:
    async def execute(self, **values: object) -> object:
        operation = cast(Callable[[AsyncConnection], Awaitable[object]], values["operation"])
        return await operation(cast(AsyncConnection, object()))


class _ConflictingCoordinator:
    async def execute(self, **_values: object) -> NoReturn:
        raise ServiceExecutionError("idempotency_conflict")


@pytest.mark.asyncio
async def test_phase11c_preserves_contract_idempotency_conflict_code() -> None:
    def coordinator_factory(_connection: AsyncConnection) -> _ConflictingCoordinator:
        return _ConflictingCoordinator()

    application = SimpleNamespace(
        state=SimpleNamespace(
            authorized_service_executor=_ImmediateExecutor(),
            idempotency_coordinator_factory=coordinator_factory,
        )
    )
    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/test",
            "raw_path": b"/api/v1/test",
            "query_string": b"",
            "headers": [(b"idempotency-key", b"7e000000-0000-4000-8000-000000000001")],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
            "app": application,
        }
    )
    principal = AuthorizationPrincipal(
        app_user_id=ID,
        account_status=AccountStatus.ACTIVE,
        role=AppRole.ADMIN,
        company_id=ID,
        employee_id=None,
        branch_id=None,
    )

    async def authorize(
        _connection: AsyncConnection, _kind: str, _resource_id: UUID | None
    ) -> None:
        return None

    async def mutate(_connection: AsyncConnection) -> IdempotentResponse:
        raise AssertionError("mutation must not run on an idempotency conflict")

    with pytest.raises(ServiceExecutionError) as caught:
        await idempotent_mutation(
            request=request,
            claims=AccessTokenClaims(
                issuer="https://synthetic.test",
                subject="phase11c",
                audience=("workloop-api",),
                expires_at=1,
                issued_at=1,
                not_before=None,
            ),
            principal=principal,
            branch_id=ID,
            selected_admin_branch_id=ID,
            operation_id="phase11c_test",
            method="POST",
            route_parameters={},
            body={"value": "changed"},
            resource_authorizer=authorize,
            mutation=mutate,
        )
    assert caught.value.code == "idempotency_conflict"
