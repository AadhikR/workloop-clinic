"""Restrict direct runtime writes to function-protected workflow tables.

Revision ID: c2f6a8b0e14d
Revises: b1e5f7a9d03c
Created: 2026-09-05 00:00:00.000000

The retained functions enforce payroll replacement, advance repayment, and
shift-swap rules. Direct writes to their source and result tables would bypass
those checks. Keep those tables readable by the runtime role and route every
mutation through a reviewed function until a later phase adds a narrower API
operation and matching grant.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2f6a8b0e14d"
down_revision: str | Sequence[str] | None = "b1e5f7a9d03c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROTECTED_TABLES: tuple[str, ...] = (
    "payroll_runs",
    "payroll_entries",
    "salary_advances",
    "roster_assignments",
    "shift_swap_requests",
)


def upgrade() -> None:
    for table in PROTECTED_TABLES:
        op.execute(f"REVOKE INSERT, UPDATE ON TABLE {table} FROM workloop_runtime")


def downgrade() -> None:
    for table in PROTECTED_TABLES:
        op.execute(f"GRANT INSERT, UPDATE ON TABLE {table} TO workloop_runtime")
