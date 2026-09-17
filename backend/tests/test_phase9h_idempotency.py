from typing import cast

from sqlalchemy import CheckConstraint, Table

from app.models.idempotency import IdempotencyRecord


def test_phase9_replay_resources_are_allowed_by_model_metadata() -> None:
    table = cast(Table, IdempotencyRecord.__table__)
    replay_constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and str(constraint.name).endswith("replay_resource")
    )
    expression = str(replay_constraint.sqltext)
    for resource_kind in (
        "expense_claim",
        "salary_advance",
        "payroll_run",
        "compliance_override",
        "nafis_snapshot",
    ):
        assert f"'{resource_kind}'" in expression
