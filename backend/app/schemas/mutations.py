from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict

IDENTITY_SCOPE_FIELDS = frozenset(
    {
        "role",
        "company_id",
        "branch_id",
        "employee_id",
        "app_user_id",
        "reporting_manager_id",
    }
)
COMPENSATION_FIELDS = frozenset(
    {
        "basic_salary",
        "allowance",
        "housing_allowance",
        "transport_allowance",
        "other_allowances",
        "other_allowances_label",
        "bank_name",
        "bank_routing_code",
        "bank_account_holder",
        "iban",
        "mol_id",
    }
)
WORKFLOW_STATE_FIELDS = frozenset(
    {
        "status",
        "approval_status",
        "approved_at",
        "approved_by_app_user_id",
        "manager_approved_at",
        "manager_approved_by_app_user_id",
        "manager_rejection_reason",
        "rejection_reason",
        "reviewed_at",
        "reviewed_by_app_user_id",
        "completed_at",
        "paid_at",
        "payroll_run_id",
        "wps_status",
        "outstanding_balance",
        "monthly_deduction",
        "settled_at",
    }
)
AUDIT_FIELDS = frozenset(
    {
        "actor_app_user_id",
        "actor_kind",
        "audit_event_id",
        "created_at",
        "updated_at",
    }
)
PROTECTED_MUTATION_FIELDS = (
    IDENTITY_SCOPE_FIELDS | COMPENSATION_FIELDS | WORKFLOW_STATE_FIELDS | AUDIT_FIELDS
)


class ProtectedMutationError(ValueError):
    pass


class MutationFieldGuardConfigurationError(ValueError):
    pass


_MUTATION_GUARD_TOKEN = object()


class GuardedMutationValues(Mapping[str, Any]):
    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any], *, guard_token: object) -> None:
        if guard_token is not _MUTATION_GUARD_TOKEN:
            raise MutationFieldGuardConfigurationError(
                "mutation values must come from a configured field guard"
            )
        self._values = MappingProxyType(dict(values))

    def __getitem__(self, key: str) -> Any:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class StrictMutationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _empty_field_set() -> frozenset[str]:
    return frozenset()


@dataclass(frozen=True, slots=True)
class MutationFieldGuard:
    allowed_input_fields: frozenset[str]
    approved_protected_fields: frozenset[str] = field(default_factory=_empty_field_set)
    server_derived_fields: frozenset[str] = field(default_factory=_empty_field_set)
    matching_derived_input_fields: frozenset[str] = field(default_factory=_empty_field_set)

    def __post_init__(self) -> None:
        approved_without_allowlist = self.approved_protected_fields - self.allowed_input_fields
        unapproved_protected = (
            self.allowed_input_fields & PROTECTED_MUTATION_FIELDS
        ) - self.approved_protected_fields
        matching_without_derived = self.matching_derived_input_fields - self.server_derived_fields
        if approved_without_allowlist:
            raise MutationFieldGuardConfigurationError(
                "approved protected fields must also be allowlisted"
            )
        if unapproved_protected:
            raise MutationFieldGuardConfigurationError(
                "protected input fields require an exact workflow approval"
            )
        if matching_without_derived:
            raise MutationFieldGuardConfigurationError(
                "matching input fields must be server-derived"
            )

    def prepare(
        self,
        payload: BaseModel | Mapping[str, Any],
        *,
        derived_values: Mapping[str, Any] | None = None,
    ) -> GuardedMutationValues:
        if derived_values is None:
            derived_values = {}
        raw_values = (
            payload.model_dump(exclude_unset=True)
            if isinstance(payload, BaseModel)
            else dict(payload)
        )
        supplied_fields = frozenset(raw_values)
        allowed_supplied_fields = self.allowed_input_fields | self.matching_derived_input_fields
        if supplied_fields - allowed_supplied_fields:
            raise ProtectedMutationError("the mutation contains a field this action cannot write")
        if frozenset(derived_values) != self.server_derived_fields:
            raise MutationFieldGuardConfigurationError(
                "the mutation did not provide its exact server-derived fields"
            )
        for name in self.matching_derived_input_fields & supplied_fields:
            if raw_values[name] != derived_values[name]:
                raise ProtectedMutationError("the mutation conflicts with its authorized scope")
            raw_values.pop(name)
        raw_values.update(derived_values)
        return GuardedMutationValues(raw_values, guard_token=_MUTATION_GUARD_TOKEN)
