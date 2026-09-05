"""Harden retained PostgreSQL function search paths.

Revision ID: b1e5f7a9d03c
Revises: a0d4e6f8c92b
Created: 2026-09-05 00:00:00.000000

Place PostgreSQL's catalog first and the caller's temporary schema last. This
prevents a runtime session from shadowing public tables inside a retained
security-definer function.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b1e5f7a9d03c"
down_revision: str | Sequence[str] | None = "a0d4e6f8c92b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION_SIGNATURES: tuple[str, ...] = (
    "set_updated_at()",
    "replace_payroll_entries(uuid, jsonb)",
    "record_advance_repayment(uuid, uuid, uuid, numeric, date)",
    "admin_execute_shift_swap(uuid, uuid)",
)


def upgrade() -> None:
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"ALTER FUNCTION {signature} SET search_path TO pg_catalog, public, pg_temp")


def downgrade() -> None:
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"ALTER FUNCTION {signature} SET search_path TO public")
