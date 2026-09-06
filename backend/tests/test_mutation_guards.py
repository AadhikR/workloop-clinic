import uuid
from collections.abc import MutableMapping
from typing import Any, cast

import pytest
from pydantic import ValidationError

from app.schemas.mutations import (
    COMPENSATION_FIELDS,
    IDENTITY_SCOPE_FIELDS,
    PROTECTED_MUTATION_FIELDS,
    WORKFLOW_STATE_FIELDS,
    GuardedMutationValues,
    MutationFieldGuard,
    MutationFieldGuardConfigurationError,
    ProtectedMutationError,
    StrictMutationModel,
)


class EmployeeContactPatch(StrictMutationModel):
    phone: str | None = None
    personal_email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


def test_strict_mutation_model_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        EmployeeContactPatch.model_validate(
            {
                "phone": "+971500000099",
                "basic_salary": "999999.00",
            }
        )


@pytest.mark.parametrize(
    "field_name",
    sorted(PROTECTED_MUTATION_FIELDS),
)
def test_generic_mutation_rejects_every_protected_field(field_name: str) -> None:
    guard = MutationFieldGuard(allowed_input_fields=frozenset({"phone"}))
    with pytest.raises(ProtectedMutationError):
        guard.prepare({"phone": "+971500000099", field_name: "caller-value"})


def test_guard_configuration_requires_exact_workflow_approval() -> None:
    protected_field = next(iter(WORKFLOW_STATE_FIELDS))
    with pytest.raises(MutationFieldGuardConfigurationError):
        MutationFieldGuard(allowed_input_fields=frozenset({protected_field}))


def test_named_workflow_can_allow_one_protected_field() -> None:
    guard = MutationFieldGuard(
        allowed_input_fields=frozenset({"status", "reason"}),
        approved_protected_fields=frozenset({"status"}),
        server_derived_fields=frozenset({"approved_by_app_user_id"}),
    )
    actor = uuid.uuid4()

    values = guard.prepare(
        {"status": "Approved", "reason": "Reviewed"},
        derived_values={"approved_by_app_user_id": actor},
    )

    assert dict(values) == {
        "status": "Approved",
        "reason": "Reviewed",
        "approved_by_app_user_id": actor,
    }


def test_body_branch_may_only_repeat_the_verified_branch() -> None:
    verified_branch = uuid.uuid4()
    guard = MutationFieldGuard(
        allowed_input_fields=frozenset({"name"}),
        server_derived_fields=frozenset({"company_id", "branch_id"}),
        matching_derived_input_fields=frozenset({"branch_id"}),
    )

    values = guard.prepare(
        {"name": "Synthetic record", "branch_id": verified_branch},
        derived_values={"company_id": uuid.uuid4(), "branch_id": verified_branch},
    )

    assert values["branch_id"] == verified_branch
    assert "company_id" in values


def test_body_branch_cannot_override_the_verified_branch() -> None:
    guard = MutationFieldGuard(
        allowed_input_fields=frozenset({"name"}),
        server_derived_fields=frozenset({"company_id", "branch_id"}),
        matching_derived_input_fields=frozenset({"branch_id"}),
    )
    with pytest.raises(ProtectedMutationError):
        guard.prepare(
            {"name": "Synthetic record", "branch_id": uuid.uuid4()},
            derived_values={"company_id": uuid.uuid4(), "branch_id": uuid.uuid4()},
        )


def test_guard_requires_every_server_derived_field() -> None:
    guard = MutationFieldGuard(
        allowed_input_fields=frozenset({"phone"}),
        server_derived_fields=frozenset({"company_id", "employee_id"}),
    )
    with pytest.raises(MutationFieldGuardConfigurationError):
        guard.prepare(
            {"phone": "+971500000099"},
            derived_values={"company_id": uuid.uuid4()},
        )


def test_guarded_values_are_immutable() -> None:
    values = MutationFieldGuard(allowed_input_fields=frozenset({"phone"})).prepare(
        {"phone": "+971500000099"}
    )

    with pytest.raises(TypeError):
        cast(MutableMapping[str, Any], values)["phone"] = "+971500000000"


def test_guarded_values_cannot_be_constructed_without_a_field_guard() -> None:
    with pytest.raises(MutationFieldGuardConfigurationError):
        GuardedMutationValues({"status": "Approved"}, guard_token=object())


def test_protected_catalogue_covers_required_field_classes() -> None:
    assert {"role", "company_id", "branch_id", "employee_id"} <= IDENTITY_SCOPE_FIELDS
    assert {"basic_salary", "iban", "bank_name"} <= COMPENSATION_FIELDS
    assert {"status", "approval_status", "payroll_run_id"} <= WORKFLOW_STATE_FIELDS
