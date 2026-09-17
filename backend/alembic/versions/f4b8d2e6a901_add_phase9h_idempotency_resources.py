"""Allow every Phase 9 replay resource.

Revision ID: f4b8d2e6a901
Revises: e3a7c9d1f5b2
Created: 2026-09-17 23:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4b8d2e6a901"
down_revision: str | Sequence[str] | None = "e3a7c9d1f5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE_9H_REPLAY_RESOURCE = (
    "(replay_resource_kind IN "
    "('branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot') "
    "AND replay_resource_id IS NOT NULL) "
    "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
    "OR replay_resource_kind IS NULL"
)

PHASE_9G_REPLAY_RESOURCE = (
    "(replay_resource_kind IN "
    "('branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run') AND replay_resource_id IS NOT NULL) "
    "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
    "OR replay_resource_kind IS NULL"
)


def _replace_replay_resource_constraint(expression: str) -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        expression,
    )


def upgrade() -> None:
    _replace_replay_resource_constraint(PHASE_9H_REPLAY_RESOURCE)


def downgrade() -> None:
    _replace_replay_resource_constraint(PHASE_9G_REPLAY_RESOURCE)
