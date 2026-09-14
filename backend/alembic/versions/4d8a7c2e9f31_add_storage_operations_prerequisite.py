"""Add the shared storage operation prerequisite.

Revision ID: 4d8a7c2e9f31
Revises: 8f6b2d1a4c70
Created: 2026-09-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4d8a7c2e9f31"
down_revision: str | Sequence[str] | None = "8f6b2d1a4c70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HUMAN_CONTEXT = """
current_user='workloop_runtime'
AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
""".strip()


def upgrade() -> None:
    op.create_table(
        "storage_operations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=True),
        sa.Column("created_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_error_code", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("operation IN ('upload','delete')", name="operation"),
        sa.CheckConstraint(
            "status IN ('pending','claimed','succeeded','failed','reconciled')",
            name="status",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 8", name="attempt_count"),
        sa.CheckConstraint(
            "entity_type ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="entity_type",
        ),
        sa.CheckConstraint(
            "octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%'",
            name="object_key",
        ),
        sa.CheckConstraint(
            "(status='pending' AND attempt_count=0 AND last_error_code='' "
            "AND next_attempt_at IS NULL AND claimed_at IS NULL "
            "AND lease_expires_at IS NULL AND completed_at IS NULL) OR "
            "(status='claimed' AND attempt_count BETWEEN 1 AND 8 AND claimed_at IS NOT NULL "
            "AND lease_expires_at=claimed_at+interval '15 minutes' AND next_attempt_at IS NULL "
            "AND completed_at IS NULL AND last_error_code='') OR "
            "(status='failed' AND attempt_count BETWEEN 1 AND 8 AND completed_at IS NULL "
            "AND claimed_at IS NULL AND lease_expires_at IS NULL AND last_error_code<>' ' "
            "AND last_error_code<>'' AND ((attempt_count<8 AND next_attempt_at IS NOT NULL) "
            "OR (attempt_count=8 AND next_attempt_at IS NULL))) OR "
            "(status IN ('succeeded','reconciled') AND attempt_count BETWEEN 1 AND 8 "
            "AND completed_at IS NOT NULL AND claimed_at IS NULL AND lease_expires_at IS NULL "
            "AND next_attempt_at IS NULL AND last_error_code='')",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "last_error_code='' OR last_error_code ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="last_error_code",
        ),
        sa.CheckConstraint(
            "updated_at>=created_at AND (next_attempt_at IS NULL OR next_attempt_at>=created_at) "
            "AND (claimed_at IS NULL OR claimed_at>=created_at) "
            "AND (lease_expires_at IS NULL OR lease_expires_at>=created_at) "
            "AND (completed_at IS NULL OR completed_at>=created_at)",
            name="timestamps",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["branch_id", "company_id"],
            ["branches.id", "branches.company_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id", "company_id", "branch_id"],
            ["employees.id", "employees.company_id", "employees.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_app_user_id", "company_id"],
            ["user_profiles.app_user_id", "user_profiles.company_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_storage_operations"),
    )
    op.create_index(
        "ix_storage_operations_claim",
        "storage_operations",
        ["status", "next_attempt_at", "lease_expires_at", "created_at", "id"],
    )
    op.create_index(
        "ix_storage_operations_purge",
        "storage_operations",
        ["completed_at", "id"],
        postgresql_where=sa.text("status IN ('succeeded','reconciled')"),
    )
    op.execute("ALTER TABLE public.storage_operations OWNER TO workloop_migration")
    op.execute(r"""
CREATE FUNCTION public._storage_operation_transition_phase8d()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
BEGIN
  IF session_user='workloop_runtime' THEN
    IF NOT (
      (OLD.status='pending' AND OLD.attempt_count=0
       AND NEW.status='claimed' AND NEW.attempt_count=1
       AND NEW.claimed_at=statement_timestamp()
       AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
      OR
      (OLD.status='claimed' AND OLD.attempt_count=1
       AND NEW.attempt_count=1
       AND ((NEW.status='succeeded' AND NEW.completed_at=statement_timestamp())
         OR (NEW.status='failed' AND NEW.last_error_code='provider_error'
             AND NEW.next_attempt_at=statement_timestamp()+interval '1 minute')))
    ) THEN
      RAISE EXCEPTION 'storage operation transition denied' USING ERRCODE='42501';
    END IF;
  ELSIF session_user='workloop_storage_reconciler' THEN
    IF NOT (
      (OLD.status='pending' AND OLD.attempt_count=0
       AND NEW.status='claimed' AND NEW.attempt_count=1
       AND NEW.claimed_at=statement_timestamp()
       AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
      OR
      (OLD.status='failed' AND OLD.attempt_count BETWEEN 1 AND 7
       AND OLD.next_attempt_at<=statement_timestamp()
       AND NEW.status='claimed' AND NEW.attempt_count=OLD.attempt_count+1
       AND NEW.claimed_at=statement_timestamp()
       AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
      OR
      (OLD.status='claimed' AND OLD.attempt_count BETWEEN 1 AND 7
       AND OLD.lease_expires_at<=statement_timestamp()
       AND NEW.status='claimed' AND NEW.attempt_count=OLD.attempt_count+1
       AND NEW.claimed_at=statement_timestamp()
       AND NEW.lease_expires_at=NEW.claimed_at+interval '15 minutes')
      OR
      (OLD.status='claimed' AND NEW.attempt_count=OLD.attempt_count
       AND NEW.status IN ('succeeded','reconciled')
       AND NEW.completed_at=statement_timestamp())
      OR
      (OLD.status='claimed' AND OLD.attempt_count BETWEEN 1 AND 7
       AND NEW.status='failed' AND NEW.attempt_count=OLD.attempt_count
       AND NEW.last_error_code='provider_error'
       AND NEW.next_attempt_at=statement_timestamp()+CASE OLD.attempt_count
         WHEN 1 THEN interval '1 minute' WHEN 2 THEN interval '5 minutes'
         WHEN 3 THEN interval '15 minutes' WHEN 4 THEN interval '1 hour'
         WHEN 5 THEN interval '6 hours' WHEN 6 THEN interval '24 hours'
         WHEN 7 THEN interval '72 hours' END)
      OR
      (OLD.status='claimed' AND OLD.attempt_count=8 AND NEW.attempt_count=8
       AND NEW.status='failed' AND NEW.next_attempt_at IS NULL
       AND ((NEW.last_error_code='provider_error')
         OR (OLD.lease_expires_at<=statement_timestamp()
             AND NEW.last_error_code='retry_exhausted')))
    ) THEN
      RAISE EXCEPTION 'storage operation transition denied' USING ERRCODE='42501';
    END IF;
  ELSE
    RAISE EXCEPTION 'storage operation transition denied' USING ERRCODE='42501';
  END IF;
  IF NEW.id<>OLD.id OR NEW.company_id<>OLD.company_id OR NEW.branch_id<>OLD.branch_id
    OR NEW.employee_id IS DISTINCT FROM OLD.employee_id
    OR NEW.created_by_app_user_id<>OLD.created_by_app_user_id
    OR NEW.entity_type<>OLD.entity_type OR NEW.entity_id<>OLD.entity_id
    OR NEW.operation<>OLD.operation OR NEW.object_key<>OLD.object_key
    OR NEW.created_at<>OLD.created_at THEN
    RAISE EXCEPTION 'storage operation identity is immutable' USING ERRCODE='42501';
  END IF;
  RETURN NEW;
END
$function$
""")
    op.execute(
        "ALTER FUNCTION public._storage_operation_transition_phase8d() OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public._storage_operation_transition_phase8d() FROM PUBLIC")
    op.execute(
        "CREATE TRIGGER storage_operation_transition_phase8d "
        "BEFORE UPDATE ON public.storage_operations FOR EACH ROW "
        "EXECUTE FUNCTION public._storage_operation_transition_phase8d()"
    )
    op.execute("ALTER TABLE public.storage_operations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.storage_operations FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.storage_operations FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.storage_operations FROM workloop_runtime")
    op.execute("REVOKE ALL ON TABLE public.storage_operations FROM workloop_storage_reconciler")
    op.execute(
        "GRANT INSERT(company_id,branch_id,employee_id,created_by_app_user_id,entity_type,"
        "entity_id,operation,object_key) ON public.storage_operations TO workloop_runtime"
    )
    op.execute(
        "GRANT SELECT(id,company_id,branch_id,status,created_by_app_user_id) "
        "ON public.storage_operations TO workloop_runtime"
    )
    op.execute(
        "GRANT UPDATE(status,attempt_count,last_error_code,next_attempt_at,claimed_at,"
        "lease_expires_at,completed_at,updated_at) ON public.storage_operations "
        "TO workloop_runtime"
    )
    op.execute("GRANT SELECT ON public.storage_operations TO workloop_storage_reconciler")
    op.execute(
        "GRANT UPDATE(status,attempt_count,last_error_code,next_attempt_at,claimed_at,"
        "lease_expires_at,completed_at,updated_at) ON public.storage_operations "
        "TO workloop_storage_reconciler"
    )
    op.execute("GRANT DELETE ON public.storage_operations TO workloop_storage_reconciler")
    op.execute("GRANT USAGE ON SCHEMA public TO workloop_storage_reconciler")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.workloop_actor_kind(),"
        "public.workloop_actor_key() TO workloop_storage_reconciler"
    )
    runtime_scope = f"""{HUMAN_CONTEXT}
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND created_by_app_user_id=public.workloop_app_user_id()"""
    op.execute(
        "CREATE POLICY storage_operations_runtime_select ON public.storage_operations "
        f"FOR SELECT TO workloop_runtime USING ({runtime_scope})"
    )
    op.execute(
        "CREATE POLICY storage_operations_migration_all ON public.storage_operations "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY storage_operations_runtime_insert ON public.storage_operations "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({runtime_scope} "
        "AND status='pending' AND attempt_count=0 AND last_error_code='' "
        "AND next_attempt_at IS NULL AND claimed_at IS NULL AND lease_expires_at IS NULL "
        "AND completed_at IS NULL)"
    )
    op.execute(
        "CREATE POLICY storage_operations_runtime_update ON public.storage_operations "
        f"FOR UPDATE TO workloop_runtime USING ({runtime_scope}) WITH CHECK ({runtime_scope})"
    )
    reconciler = (
        "current_user='workloop_storage_reconciler' "
        "AND session_user='workloop_storage_reconciler' "
        "AND public.workloop_actor_kind()='scheduled_job' "
        "AND public.workloop_actor_key()='storage_reconciliation'"
    )
    op.execute(
        "CREATE POLICY storage_operations_reconciler_select ON public.storage_operations "
        f"FOR SELECT TO workloop_storage_reconciler USING ({reconciler})"
    )
    op.execute(
        "CREATE POLICY storage_operations_reconciler_update ON public.storage_operations "
        f"FOR UPDATE TO workloop_storage_reconciler USING ({reconciler}) "
        f"WITH CHECK ({reconciler})"
    )
    op.execute(
        "CREATE POLICY storage_operations_reconciler_delete ON public.storage_operations "
        f"FOR DELETE TO workloop_storage_reconciler USING ({reconciler} "
        "AND status IN ('succeeded','reconciled') "
        "AND completed_at < statement_timestamp()-interval '90 days')"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.workloop_actor_kind(),"
        "public.workloop_actor_key() FROM workloop_storage_reconciler"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM workloop_storage_reconciler")
    op.drop_table("storage_operations")
    op.execute("DROP FUNCTION public._storage_operation_transition_phase8d()")
