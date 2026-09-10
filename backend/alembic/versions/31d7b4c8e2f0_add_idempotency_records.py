"""Add the shared API idempotency record.

Revision ID: 31d7b4c8e2f0
Revises: 2c4d6e8f0a1b
Created: 2026-09-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "31d7b4c8e2f0"
down_revision: str | Sequence[str] | None = "2c4d6e8f0a1b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HUMAN_CONTEXT = """
current_user = 'workloop_runtime'
AND session_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND principal.role = public.workloop_role()
    AND (
      (principal.role = 'admin'
       AND principal.profile_employee_id IS NULL
       AND principal.employee_id IS NULL
       AND principal.branch_id IS NULL
       AND public.workloop_employee_id() IS NULL)
      OR
      (principal.role IN ('manager', 'employee')
       AND principal.profile_employee_id = public.workloop_employee_id()
       AND principal.employee_id = principal.profile_employee_id
       AND principal.employee_company_id = principal.profile_company_id
       AND principal.employee_branch_id = public.workloop_branch_id()
       AND principal.employee_active
       AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
       AND principal.branch_id = principal.employee_branch_id
       AND principal.branch_company_id = principal.profile_company_id)
    )
)
""".strip()


def _create_table() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("app_user_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=True),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("http_method", sa.Text(), nullable=False),
        sa.Column("route_parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint_version", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        sa.Column("replay_resource_kind", sa.Text(), nullable=True),
        sa.Column("replay_resource_id", sa.UUID(), nullable=True),
        sa.Column("response_status", sa.SmallInteger(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_location", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "substring(idempotency_key::text, 15, 1) = '4'",
            name=op.f("ck_idempotency_records_idempotency_key_uuid4"),
        ),
        sa.CheckConstraint(
            "operation_id ~ '^[a-z][a-z0-9_]{0,127}$'",
            name=op.f("ck_idempotency_records_operation_id"),
        ),
        sa.CheckConstraint(
            "http_method IN ('POST','PATCH','PUT','DELETE')",
            name=op.f("ck_idempotency_records_http_method"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(route_parameters) = 'object'",
            name=op.f("ck_idempotency_records_route_parameters"),
        ),
        sa.CheckConstraint(
            "fingerprint_version ~ '^wlp-idem-fp-v[1-9][0-9]{0,3}$'",
            name=op.f("ck_idempotency_records_fingerprint_version"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_idempotency_records_request_fingerprint"),
        ),
        sa.CheckConstraint(
            "replay_resource_kind IS NULL OR replay_resource_kind ~ '^[a-z][a-z0-9_]{0,63}$'",
            name=op.f("ck_idempotency_records_replay_resource_kind"),
        ),
        sa.CheckConstraint(
            "(completed_at IS NULL AND replay_resource_kind IS NULL AND replay_resource_id IS NULL "
            "AND response_status IS NULL AND response_body IS NULL AND response_location IS NULL "
            "AND retain_until IS NULL) OR "
            "(completed_at IS NOT NULL AND replay_resource_kind IS NOT NULL "
            "AND response_status BETWEEN 200 AND 299 AND retain_until IS NOT NULL "
            "AND ((response_status = 204 AND response_body IS NULL) "
            "OR (response_status <> 204 AND jsonb_typeof(response_body) = 'object')))",
            name=op.f("ck_idempotency_records_completion_state"),
        ),
        sa.CheckConstraint(
            "response_location IS NULL OR (response_status IN (201,202) "
            "AND octet_length(response_location) <= 2048 AND response_location LIKE '/%' "
            "AND response_location NOT LIKE '//%' AND position(chr(13) in response_location) = 0 "
            "AND position(chr(10) in response_location) = 0)",
            name=op.f("ck_idempotency_records_response_location"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name=op.f("ck_idempotency_records_completed_at"),
        ),
        sa.CheckConstraint(
            "retain_until IS NULL OR retain_until >= completed_at + interval '7 days'",
            name=op.f("ck_idempotency_records_retention_floor"),
        ),
        sa.CheckConstraint(
            "(replay_resource_kind IN ('branch','employee','department','user_profile') "
            "AND replay_resource_id IS NOT NULL) "
            "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
            "OR replay_resource_kind IS NULL",
            name=op.f("ck_idempotency_records_replay_resource"),
        ),
        sa.ForeignKeyConstraint(
            ["app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            name="fk_idempotency_records_actor_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name="fk_idempotency_records_company",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            name="fk_idempotency_records_branch",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "app_user_id", "idempotency_key", name=op.f("pk_idempotency_records")
        ),
    )
    op.create_index(
        "ix_idempotency_records_company_retention",
        "idempotency_records",
        ["company_id", "retain_until", "created_at"],
    )
    op.execute("ALTER TABLE public.idempotency_records OWNER TO workloop_migration")


def _create_lifecycle_triggers() -> None:
    op.execute(r"""
CREATE FUNCTION public._idempotency_reservation_only_phase7c()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF NEW.replay_resource_kind IS NOT NULL OR NEW.replay_resource_id IS NOT NULL
    OR NEW.response_status IS NOT NULL OR NEW.response_body IS NOT NULL
    OR NEW.response_location IS NOT NULL OR NEW.completed_at IS NOT NULL
    OR NEW.retain_until IS NOT NULL THEN
    RAISE EXCEPTION 'idempotency claim must begin reserved' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public._idempotency_reservation_only_phase7c() OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public._idempotency_reservation_only_phase7c() FROM PUBLIC")
    op.execute(r"""
CREATE FUNCTION public._idempotency_completed_before_commit_phase7c()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM public.idempotency_records AS record
    WHERE record.app_user_id = NEW.app_user_id
      AND record.idempotency_key = NEW.idempotency_key
      AND record.completed_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'idempotency claim must complete before commit' USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public._idempotency_completed_before_commit_phase7c() "
        "OWNER TO workloop_migration"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public._idempotency_completed_before_commit_phase7c() FROM PUBLIC"
    )
    op.execute("""
CREATE TRIGGER idempotency_reservation_only_phase7c
BEFORE INSERT ON public.idempotency_records
FOR EACH ROW EXECUTE FUNCTION public._idempotency_reservation_only_phase7c()
""")
    op.execute("""
CREATE CONSTRAINT TRIGGER idempotency_completed_before_commit_phase7c
AFTER INSERT OR UPDATE ON public.idempotency_records
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION public._idempotency_completed_before_commit_phase7c()
""")


def _create_rls_and_grants() -> None:
    own_record = f"""{HUMAN_CONTEXT}
AND app_user_id = public.workloop_app_user_id()
AND company_id = public.workloop_company_id()"""
    current_scope = f"""{own_record}
AND branch_id IS NOT DISTINCT FROM public.workloop_branch_id()"""
    op.execute("ALTER TABLE public.idempotency_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.idempotency_records FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY phase7c_idempotency_records_migration_all "
        "ON public.idempotency_records FOR ALL TO workloop_migration "
        "USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY phase7c_idempotency_records_select_runtime "
        "ON public.idempotency_records FOR SELECT TO workloop_runtime "
        f"USING ({own_record})"
    )
    op.execute(
        "CREATE POLICY phase7c_idempotency_records_insert_runtime "
        "ON public.idempotency_records FOR INSERT TO workloop_runtime "
        f"WITH CHECK ({current_scope} AND completed_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY phase7c_idempotency_records_update_runtime "
        "ON public.idempotency_records FOR UPDATE TO workloop_runtime "
        f"USING ({current_scope} AND completed_at IS NULL) "
        f"WITH CHECK ({current_scope} AND completed_at IS NOT NULL)"
    )
    cleanup = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND retain_until <= statement_timestamp()"""
    op.execute(
        "CREATE POLICY phase7c_idempotency_records_delete_runtime "
        "ON public.idempotency_records FOR DELETE TO workloop_runtime "
        f"USING ({cleanup})"
    )
    op.execute("REVOKE ALL ON TABLE public.idempotency_records FROM PUBLIC")
    op.execute("GRANT SELECT, INSERT ON TABLE public.idempotency_records TO workloop_runtime")
    op.execute(
        "GRANT UPDATE (replay_resource_kind, replay_resource_id, response_status, "
        "response_body, response_location, completed_at, retain_until) "
        "ON TABLE public.idempotency_records TO workloop_runtime"
    )


def _create_cleanup_function() -> None:
    op.execute(r"""
CREATE FUNCTION public.cleanup_expired_idempotency_records()
RETURNS integer
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE deleted_count integer;
BEGIN
  IF session_user <> 'workloop_runtime'
    OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
    OR public.workloop_actor_key() IS NOT NULL
    OR public.workloop_business_date() IS NULL
    OR public.workloop_app_user_id() IS NULL
    OR public.workloop_company_id() IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM public.resolve_workloop_principal() AS principal
      WHERE principal.app_user_id = public.workloop_app_user_id()
        AND principal.account_status = 'active'
        AND principal.profile_app_user_id = principal.app_user_id
        AND principal.profile_company_id = public.workloop_company_id()
        AND principal.company_id = principal.profile_company_id
        AND principal.role = public.workloop_role()
        AND (
          (principal.role = 'admin'
           AND principal.profile_employee_id IS NULL
           AND principal.employee_id IS NULL
           AND principal.branch_id IS NULL
           AND public.workloop_employee_id() IS NULL)
          OR
          (principal.role IN ('manager', 'employee')
           AND principal.profile_employee_id = public.workloop_employee_id()
           AND principal.employee_id = principal.profile_employee_id
           AND principal.employee_company_id = principal.profile_company_id
           AND principal.employee_branch_id = public.workloop_branch_id()
           AND principal.employee_active
           AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
           AND principal.branch_id = principal.employee_branch_id
           AND principal.branch_company_id = principal.profile_company_id)
        )
    ) THEN
    RAISE EXCEPTION 'idempotency cleanup denied' USING ERRCODE = '42501';
  END IF;

  WITH candidates AS (
    SELECT record.app_user_id, record.idempotency_key
    FROM public.idempotency_records AS record
    WHERE record.company_id = public.workloop_company_id()
      AND record.completed_at IS NOT NULL
      AND record.retain_until <= statement_timestamp()
    ORDER BY record.retain_until, record.created_at,
      record.app_user_id, record.idempotency_key
    LIMIT 100
    FOR UPDATE SKIP LOCKED
  ), deleted AS (
    DELETE FROM public.idempotency_records AS record
    USING candidates
    WHERE record.app_user_id = candidates.app_user_id
      AND record.idempotency_key = candidates.idempotency_key
      AND record.company_id = public.workloop_company_id()
      AND record.completed_at IS NOT NULL
      AND record.retain_until <= statement_timestamp()
    RETURNING 1
  )
  SELECT count(*)::integer INTO deleted_count FROM deleted;
  RETURN deleted_count;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public.cleanup_expired_idempotency_records() OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.cleanup_expired_idempotency_records() FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.cleanup_expired_idempotency_records() TO workloop_runtime"
    )


def upgrade() -> None:
    _create_table()
    _create_lifecycle_triggers()
    _create_rls_and_grants()
    _create_cleanup_function()


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.cleanup_expired_idempotency_records() "
        "FROM workloop_runtime"
    )
    op.execute("DROP FUNCTION public.cleanup_expired_idempotency_records()")
    op.execute("REVOKE ALL ON TABLE public.idempotency_records FROM workloop_runtime")
    for policy in (
        "phase7c_idempotency_records_delete_runtime",
        "phase7c_idempotency_records_update_runtime",
        "phase7c_idempotency_records_insert_runtime",
        "phase7c_idempotency_records_select_runtime",
        "phase7c_idempotency_records_migration_all",
    ):
        op.execute(f"DROP POLICY IF EXISTS {policy} ON public.idempotency_records")
    op.execute(
        "DROP TRIGGER idempotency_completed_before_commit_phase7c ON public.idempotency_records"
    )
    op.execute("DROP TRIGGER idempotency_reservation_only_phase7c ON public.idempotency_records")
    op.execute("DROP FUNCTION public._idempotency_completed_before_commit_phase7c()")
    op.execute("DROP FUNCTION public._idempotency_reservation_only_phase7c()")
    op.drop_index("ix_idempotency_records_company_retention", table_name="idempotency_records")
    op.drop_table("idempotency_records")
