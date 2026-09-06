"""Add safe readers for the approved transaction context.

Revision ID: e418c0d7a6b3
Revises: d307b9c1f25e
Created: 2026-09-06 00:00:00.000000

The readers expose only the ten fixed ``workloop.*`` settings approved in
Phase 5A. Invalid text becomes SQL NULL. The functions run with invoker rights,
have a pinned search path, and are callable only by the migration owner and
``workloop_runtime``.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e418c0d7a6b3"
down_revision: str | Sequence[str] | None = "d307b9c1f25e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEXT_READERS: tuple[tuple[str, str], ...] = (
    ("workloop_identity_issuer", "workloop.identity_issuer"),
    ("workloop_identity_subject", "workloop.identity_subject"),
)
UUID_READERS: tuple[tuple[str, str], ...] = (
    ("workloop_app_user_id", "workloop.app_user_id"),
    ("workloop_company_id", "workloop.company_id"),
    ("workloop_employee_id", "workloop.employee_id"),
    ("workloop_branch_id", "workloop.branch_id"),
)
ALLOWLIST_READERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("workloop_role", "workloop.role", ("admin", "manager", "employee")),
    ("workloop_actor_kind", "workloop.actor_kind", ("human", "scheduled_job")),
    (
        "workloop_actor_key",
        "workloop.actor_key",
        ("expiry_processing", "storage_reconciliation"),
    ),
)
DATE_READERS: tuple[tuple[str, str], ...] = (("workloop_business_date", "workloop.business_date"),)
FUNCTION_NAMES: tuple[str, ...] = tuple(
    name for name, *_ in (*TEXT_READERS, *UUID_READERS, *ALLOWLIST_READERS, *DATE_READERS)
)

assert len(FUNCTION_NAMES) == 10
assert len(set(FUNCTION_NAMES)) == 10


def _create_text_reader(name: str, setting: str) -> None:
    op.execute(
        f"""
CREATE FUNCTION public.{name}()
RETURNS text
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog, pg_temp
AS $function$
  SELECT CASE
    WHEN pg_catalog.length(value) BETWEEN 1 AND 255
     AND pg_catalog.btrim(value) <> ''
    THEN value
    ELSE NULL
  END
  FROM (VALUES (pg_catalog.current_setting('{setting}', true))) AS setting(value)
$function$
"""
    )


def _create_uuid_reader(name: str, setting: str) -> None:
    op.execute(
        f"""
CREATE FUNCTION public.{name}()
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog, pg_temp
AS $function$
  SELECT CASE
    WHEN pg_catalog.pg_input_is_valid(value, 'uuid') THEN value::uuid
    ELSE NULL
  END
  FROM (VALUES (pg_catalog.current_setting('{setting}', true))) AS setting(value)
$function$
"""
    )


def _create_allowlist_reader(name: str, setting: str, allowed_values: tuple[str, ...]) -> None:
    sql_values = ", ".join(f"'{value}'" for value in allowed_values)
    op.execute(
        f"""
CREATE FUNCTION public.{name}()
RETURNS text
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog, pg_temp
AS $function$
  SELECT CASE WHEN value IN ({sql_values}) THEN value ELSE NULL END
  FROM (VALUES (pg_catalog.current_setting('{setting}', true))) AS setting(value)
$function$
"""
    )


def _create_date_reader(name: str, setting: str) -> None:
    op.execute(
        f"""
CREATE FUNCTION public.{name}()
RETURNS date
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog, pg_temp
AS $function$
  SELECT CASE
    WHEN pg_catalog.pg_input_is_valid(value, 'date') THEN value::date
    ELSE NULL
  END
  FROM (VALUES (pg_catalog.current_setting('{setting}', true))) AS setting(value)
$function$
"""
    )


def upgrade() -> None:
    for name, setting in TEXT_READERS:
        _create_text_reader(name, setting)
    for name, setting in UUID_READERS:
        _create_uuid_reader(name, setting)
    for name, setting, allowed_values in ALLOWLIST_READERS:
        _create_allowlist_reader(name, setting, allowed_values)
    for name, setting in DATE_READERS:
        _create_date_reader(name, setting)

    for name in FUNCTION_NAMES:
        signature = f"public.{name}()"
        op.execute(f"ALTER FUNCTION {signature} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO workloop_runtime")


def downgrade() -> None:
    for name in reversed(FUNCTION_NAMES):
        op.execute(f"DROP FUNCTION public.{name}()")
