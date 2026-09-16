"""Add Phase 9B expense receipt metadata and protected audit actions.

Revision ID: f9b2c4d6e8a1
Revises: e8f4c7b2a610
Created: 2026-09-16 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9b2c4d6e8a1"
down_revision: str | Sequence[str] | None = "e8f4c7b2a610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_SIGNATURE = "public.append_audit_event(text,text,uuid,text[],text,jsonb)"
PRIOR_SIGNATURE = "public._append_audit_event_phase9b_prior(text,text,uuid,text[],text,jsonb)"

HUMAN_CONTEXT = """
session_user='workloop_runtime'
AND public.workloop_actor_kind()='human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_app_user_id() IS NOT NULL
AND public.workloop_company_id() IS NOT NULL
AND public.workloop_branch_id() IS NOT NULL
""".strip()


def _create_table() -> None:
    metadata_complete = (
        "file_name IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL "
        "AND sha256 IS NOT NULL AND object_key IS NOT NULL"
    )
    metadata_empty = (
        "file_name IS NULL AND content_type IS NULL AND size_bytes IS NULL "
        "AND sha256 IS NULL AND object_key IS NULL"
    )
    op.create_unique_constraint(
        "uq_expense_claims_id_company_id_branch_id",
        "expense_claims",
        ["id", "company_id", "branch_id"],
    )
    op.create_table(
        "expense_receipts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("branch_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("expense_claim_id", sa.UUID(), nullable=True),
        sa.Column("created_by_app_user_id", sa.UUID(), nullable=False),
        sa.Column("submission_token_digest", sa.LargeBinary(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("object_key", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleanup_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "octet_length(submission_token_digest)=32", name="submission_token_digest"
        ),
        sa.CheckConstraint(
            "status IN ('pending','uploading','staged','attached','cleanup_pending','removed')",
            name="status",
        ),
        sa.CheckConstraint(
            f"(({metadata_empty}) OR ({metadata_complete}))", name="metadata_completeness"
        ),
        sa.CheckConstraint(
            "file_name IS NULL OR octet_length(file_name) BETWEEN 1 AND 180", name="file_name"
        ),
        sa.CheckConstraint(
            "content_type IS NULL OR content_type IN ('application/pdf','image/png','image/jpeg')",
            name="content_type",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes BETWEEN 1 AND 10485760", name="size_bytes"
        ),
        sa.CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="sha256"),
        sa.CheckConstraint(
            "object_key IS NULL OR (octet_length(object_key) BETWEEN 1 AND 1024 "
            "AND object_key !~ '[[:cntrl:]\\\\]' AND left(object_key,1)<>'/' "
            "AND object_key NOT LIKE '%//%' AND ('/'||object_key||'/') NOT LIKE '%/./%' "
            "AND ('/'||object_key||'/') NOT LIKE '%/../%')",
            name="object_key",
        ),
        sa.CheckConstraint(
            f"(status='pending' AND {metadata_empty} AND token_consumed_at IS NULL "
            "AND expires_at=created_at+interval '15 minutes' AND uploaded_at IS NULL "
            "AND attached_at IS NULL AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='uploading' AND {metadata_empty} AND token_consumed_at IS NOT NULL "
            "AND expires_at IS NOT NULL AND uploaded_at IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='staged' AND {metadata_complete} AND token_consumed_at IS NOT NULL "
            "AND uploaded_at IS NOT NULL AND expires_at=uploaded_at+interval '24 hours' "
            "AND expense_claim_id IS NULL AND attached_at IS NULL "
            "AND cleanup_requested_at IS NULL AND removed_at IS NULL) OR "
            f"(status='attached' AND {metadata_complete} AND token_consumed_at IS NOT NULL "
            "AND uploaded_at IS NOT NULL AND expires_at IS NULL AND expense_claim_id IS NOT NULL "
            "AND attached_at IS NOT NULL AND cleanup_requested_at IS NULL "
            "AND removed_at IS NULL) OR "
            f"(status='cleanup_pending' AND {metadata_complete} "
            "AND cleanup_requested_at IS NOT NULL AND removed_at IS NULL) OR "
            f"(status='removed' AND {metadata_complete} AND removed_at IS NOT NULL)",
            name="lifecycle",
        ),
        sa.CheckConstraint(
            "updated_at>=created_at AND (expires_at IS NULL OR expires_at>=created_at) "
            "AND (token_consumed_at IS NULL OR token_consumed_at>=created_at) "
            "AND (uploaded_at IS NULL OR uploaded_at>=created_at) "
            "AND (attached_at IS NULL OR attached_at>=created_at) "
            "AND (cleanup_requested_at IS NULL OR cleanup_requested_at>=created_at) "
            "AND (removed_at IS NULL OR removed_at>=created_at)",
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
        sa.ForeignKeyConstraint(
            ["expense_claim_id", "company_id", "branch_id"],
            ["expense_claims.id", "expense_claims.company_id", "expense_claims.branch_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_receipts"),
        sa.UniqueConstraint("expense_claim_id", name="uq_expense_receipts_expense_claim_id"),
        sa.UniqueConstraint(
            "submission_token_digest", name="uq_expense_receipts_submission_token_digest"
        ),
    )
    op.create_index(
        "ix_expense_receipts_employee_scope",
        "expense_receipts",
        ["company_id", "branch_id", "employee_id"],
    )
    op.create_index(
        "ix_expense_receipts_staged_expiry",
        "expense_receipts",
        ["expires_at", "id"],
        postgresql_where=sa.text("status='staged'"),
    )
    op.execute("ALTER TABLE public.expense_receipts OWNER TO workloop_migration")


def _rls_and_grants() -> None:
    op.execute("ALTER TABLE public.expense_receipts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.expense_receipts FORCE ROW LEVEL SECURITY")
    op.execute("REVOKE ALL ON TABLE public.expense_receipts FROM PUBLIC")
    op.execute("REVOKE ALL ON TABLE public.expense_receipts FROM workloop_runtime")
    op.execute("GRANT SELECT ON public.expense_receipts TO workloop_runtime")
    op.execute(
        "GRANT INSERT(id,company_id,branch_id,employee_id,expense_claim_id,"
        "created_by_app_user_id,submission_token_digest,expires_at) "
        "ON public.expense_receipts TO workloop_runtime"
    )
    op.execute(
        "GRANT UPDATE(expense_claim_id,file_name,content_type,size_bytes,sha256,object_key,status,"
        "expires_at,token_consumed_at,uploaded_at,attached_at,cleanup_requested_at,removed_at,"
        "updated_at) ON public.expense_receipts TO workloop_runtime"
    )
    owner = "employee_id=public.workloop_employee_id()"
    administrator = "public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL"
    manager = """
public.workloop_role()='manager' AND expense_claim_id IS NOT NULL
AND employee_id<>public.workloop_employee_id()
AND EXISTS (
  SELECT 1 FROM public.employees AS employee
  WHERE employee.id=expense_receipts.employee_id
    AND employee.company_id=expense_receipts.company_id
    AND employee.branch_id=expense_receipts.branch_id
    AND employee.reporting_manager_id=public.workloop_employee_id()
    AND employee.active AND employee.employment_status IN ('Active','Probation','On Leave')
)
""".strip()
    scope = (
        f"{HUMAN_CONTEXT} AND company_id=public.workloop_company_id() "
        "AND branch_id=public.workloop_branch_id()"
    )
    insertable = (
        f"{scope} AND (({owner} AND created_by_app_user_id=public.workloop_app_user_id()) "
        f"OR ({administrator}))"
    )
    mutable = f"{scope} AND (({owner}) OR ({administrator}))"
    op.execute(
        "CREATE POLICY expense_receipts_migration_all ON public.expense_receipts "
        "FOR ALL TO workloop_migration USING (true) WITH CHECK (true)"
    )
    op.execute(
        "CREATE POLICY expense_receipts_runtime_select ON public.expense_receipts "
        f"FOR SELECT TO workloop_runtime USING ({scope} "
        f"AND (({owner}) OR ({administrator}) OR ({manager})))"
    )
    op.execute(
        "CREATE POLICY expense_receipts_runtime_insert ON public.expense_receipts "
        f"FOR INSERT TO workloop_runtime WITH CHECK ({insertable} AND status='pending')"
    )
    op.execute(
        "CREATE POLICY expense_receipts_runtime_update ON public.expense_receipts "
        f"FOR UPDATE TO workloop_runtime USING ({mutable}) WITH CHECK ({mutable})"
    )


def _allow_expense_replay() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request','expense_claim') "
        "AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def _authority_function() -> None:
    op.execute(
        f"""
CREATE FUNCTION public.lock_expense_claim(p_claim_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  claim public.expense_claims%ROWTYPE;
BEGIN
  IF NOT ({HUMAN_CONTEXT}) THEN RETURN false; END IF;
  SELECT expense.* INTO claim
  FROM public.expense_claims AS expense
  WHERE expense.id=p_claim_id
    AND expense.company_id=public.workloop_company_id()
    AND expense.branch_id=public.workloop_branch_id()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  IF public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL THEN
    RETURN true;
  END IF;
  IF public.workloop_role() IN ('manager','employee')
    AND claim.employee_id=public.workloop_employee_id() THEN RETURN true; END IF;
  RETURN public.workloop_role()='manager'
    AND public.workloop_employee_id() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.employees AS employee
      WHERE employee.id=claim.employee_id
        AND employee.company_id=claim.company_id
        AND employee.branch_id=claim.branch_id
        AND employee.reporting_manager_id=public.workloop_employee_id()
        AND employee.active
        AND employee.employment_status IN ('Active','Probation','On Leave')
    );
END
$function$
"""
    )
    op.execute(
        f"""
CREATE FUNCTION public.lock_expense_direct_report(p_target_employee_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE
  target public.employees%ROWTYPE;
  actor_id uuid;
BEGIN
  IF NOT ({HUMAN_CONTEXT}) OR public.workloop_role()<>'manager'
    OR public.workloop_employee_id() IS NULL THEN RETURN false; END IF;
  SELECT employee.* INTO target
  FROM public.employees AS employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id()
  FOR UPDATE;
  IF NOT FOUND OR target.id=public.workloop_employee_id()
    OR target.reporting_manager_id IS DISTINCT FROM public.workloop_employee_id()
    OR NOT target.active
    OR target.employment_status NOT IN ('Active','Probation','On Leave') THEN
    RETURN false;
  END IF;
  SELECT employee.id INTO actor_id
  FROM public.employees AS employee
  WHERE employee.id=public.workloop_employee_id()
    AND employee.company_id=target.company_id
    AND employee.branch_id=target.branch_id
    AND employee.active
    AND employee.employment_status IN ('Active','Probation','On Leave')
  FOR UPDATE;
  RETURN FOUND;
END
$function$
"""
    )
    for function in ("lock_expense_claim(uuid)", "lock_expense_direct_report(uuid)"):
        op.execute(f"ALTER FUNCTION public.{function} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION public.{function} TO workloop_runtime")


def _wrap_audit() -> None:
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(
        "ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) "
        "RENAME TO _append_audit_event_phase9b_prior"
    )
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON FUNCTION {PRIOR_SIGNATURE} FROM workloop_runtime")
    op.execute(
        f"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $function$
DECLARE event_id uuid;
BEGIN
  IF p_action NOT IN ('expense_receipt_uploaded','expense_receipt_cleanup_requested') THEN
    RETURN public._append_audit_event_phase9b_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF NOT ({HUMAN_CONTEXT}) OR p_entity_type<>'expense_receipt'
    OR jsonb_typeof(p_metadata) IS DISTINCT FROM 'object' THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='expense_receipt_uploaded' THEN
    IF p_changed_fields IS DISTINCT FROM
      ARRAY['file_name','content_type','size_bytes','sha256','status']::text[]
      OR p_reason<>'Expense receipt uploaded'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>1
      OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'storage_operation_id','uuid')
      OR NOT EXISTS (
        SELECT 1 FROM public.expense_receipts AS receipt
        JOIN public.storage_operations AS operation
          ON operation.id=(p_metadata->>'storage_operation_id')::uuid
         AND operation.entity_type='expense_receipt' AND operation.entity_id=receipt.id
         AND operation.company_id=receipt.company_id AND operation.branch_id=receipt.branch_id
        WHERE receipt.id=p_entity_id
          AND receipt.company_id=public.workloop_company_id()
          AND receipt.branch_id=public.workloop_branch_id()
          AND receipt.created_by_app_user_id=public.workloop_app_user_id()
          AND receipt.status IN ('staged','attached')
          AND operation.operation='upload' AND operation.status='succeeded') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    IF p_changed_fields IS DISTINCT FROM ARRAY['status']::text[]
      OR p_reason<>'Expense receipt cleanup requested'
      OR (SELECT count(*) FROM jsonb_object_keys(p_metadata))<>2
      OR p_metadata->>'trigger' NOT IN
        ('failed_submission','claim_deleted','staged_expired','missing_object')
      OR NOT pg_catalog.pg_input_is_valid(p_metadata->>'storage_operation_id','uuid')
      OR NOT EXISTS (
        SELECT 1 FROM public.expense_receipts AS receipt
        JOIN public.storage_operations AS operation
          ON operation.id=(p_metadata->>'storage_operation_id')::uuid
         AND operation.entity_type='expense_receipt' AND operation.entity_id=receipt.id
         AND operation.company_id=receipt.company_id AND operation.branch_id=receipt.branch_id
        WHERE receipt.id=p_entity_id
          AND receipt.company_id=public.workloop_company_id()
          AND receipt.branch_id=public.workloop_branch_id()
          AND receipt.status='cleanup_pending' AND operation.operation='delete') THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,p_metadata)
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$
"""
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")


def upgrade() -> None:
    _create_table()
    _rls_and_grants()
    _allow_expense_replay()
    _authority_function()
    _wrap_audit()


def downgrade() -> None:
    op.execute(
        """
DO $block$
BEGIN
  IF EXISTS (SELECT 1 FROM public.expense_receipts)
    OR EXISTS (
      SELECT 1 FROM public.idempotency_records WHERE replay_resource_kind='expense_claim'
    ) THEN
    RAISE EXCEPTION 'cannot downgrade Phase 9B while expense receipt or replay rows exist';
  END IF;
END
$block$
"""
    )
    op.execute(f"REVOKE EXECUTE ON FUNCTION {AUDIT_SIGNATURE} FROM workloop_runtime")
    op.execute(f"DROP FUNCTION {AUDIT_SIGNATURE}")
    op.execute(
        "ALTER FUNCTION public._append_audit_event_phase9b_prior"
        "(text,text,uuid,text[],text,jsonb) RENAME TO append_audit_event"
    )
    op.execute(f"ALTER FUNCTION {AUDIT_SIGNATURE} OWNER TO workloop_migration")
    op.execute(f"REVOKE ALL ON FUNCTION {AUDIT_SIGNATURE} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {AUDIT_SIGNATURE} TO workloop_runtime")
    op.execute("DROP FUNCTION public.lock_expense_direct_report(uuid)")
    op.execute("DROP FUNCTION public.lock_expense_claim(uuid)")
    op.drop_table("expense_receipts")
    op.drop_constraint(
        "uq_expense_claims_id_company_id_branch_id", "expense_claims", type_="unique"
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        "(replay_resource_kind IN "
        "('branch','employee','department','user_profile','leave_request') "
        "AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind = 'tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
