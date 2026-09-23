"""Add Phase 11C employee records and benefits authority.

Revision ID: e9a1b3d5f7c2
Revises: d8f0a2c4e6b1
Created: 2026-09-22 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9a1b3d5f7c2"
down_revision: str | Sequence[str] | None = "d8f0a2c4e6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIOR_REPLAY_KINDS = (
    "'branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot',"
    "'attendance_settings','shift','shift_assignment','clock_event','biometric_mapping',"
    "'attendance_import_batch','attendance_record','regularisation_request',"
    "'attendance_period','roster_assignment','roster_publication_version','shift_swap_request'"
)
PHASE11C_REPLAY_KINDS = PRIOR_REPLAY_KINDS + (
    ",'employee_document','insurance_policy','employee_insurance',"
    "'insurance_dependant','employee_contract'"
)

SELF_DOCUMENT_SCOPE = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_role() IN ('manager','employee')
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
AND employee_id=public.workloop_employee_id()
""".strip()

ADMIN_DOCUMENT_SCOPE = """
current_user='workloop_runtime' AND session_user='workloop_runtime'
AND public.workloop_actor_kind()='human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND public.workloop_role()='admin' AND public.workloop_employee_id() IS NULL
AND company_id=public.workloop_company_id()
AND branch_id=public.workloop_branch_id()
""".strip()


def _add_document_contract() -> None:
    op.alter_column("employee_documents", "file_name", existing_type=sa.Text(), nullable=True)
    op.alter_column("employee_documents", "file_size", existing_type=sa.Integer(), nullable=True)
    op.alter_column("employee_documents", "storage_path", existing_type=sa.Text(), nullable=True)
    for column in (
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=True),
        sa.Column("file_security_scan_id", sa.UUID(), nullable=True),
        sa.Column("created_by_app_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.Column("cleanup_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upload_claimed_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("employee_documents", column)
    op.create_foreign_key(
        "fk_employee_documents_file_security_scan_scope",
        "employee_documents",
        "file_security_scans",
        ["file_security_scan_id", "company_id", "branch_id"],
        ["id", "company_id", "branch_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_employee_documents_created_by_scope",
        "employee_documents",
        "user_profiles",
        ["created_by_app_user_id", "company_id"],
        ["app_user_id", "company_id"],
        ondelete="RESTRICT",
    )
    op.execute("""
ALTER TABLE public.employee_documents ADD CONSTRAINT ck_employee_documents_phase11c_metadata
CHECK (
  (file_name IS NULL AND file_size IS NULL AND storage_path IS NULL
   AND content_type IS NULL AND sha256 IS NULL AND file_security_scan_id IS NULL)
  OR
  (octet_length(file_name) BETWEEN 1 AND 180 AND file_size BETWEEN 1 AND 10485760
   AND octet_length(storage_path) BETWEEN 1 AND 1024
   AND content_type IN ('application/pdf','image/png','image/jpeg')
   AND sha256~'^[0-9a-f]{64}$' AND file_security_scan_id IS NOT NULL)
) NOT VALID;
""")
    op.create_check_constraint(
        "phase11c_lengths",
        "employee_documents",
        "octet_length(btrim(document_number)) BETWEEN 1 AND 120 "
        "AND octet_length(notes)<=1000 "
        "AND (status<>'rejected' OR octet_length(btrim(rejection_reason)) BETWEEN 1 AND 500)",
    )
    op.execute("""
CREATE TRIGGER trg_employee_documents_set_updated_at
BEFORE UPDATE ON public.employee_documents
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
""")


def _add_optimistic_lock_fields() -> None:
    for table in ("insurance_policies", "employee_insurance", "insurance_dependants"):
        op.add_column(
            table,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("statement_timestamp()"),
            ),
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_set_updated_at BEFORE UPDATE ON public.{table} "
            "FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
        )
    op.create_check_constraint(
        "phase11c_lengths",
        "insurance_policies",
        "octet_length(btrim(insurer_name)) BETWEEN 1 AND 180 "
        "AND octet_length(btrim(policy_number)) BETWEEN 1 AND 120 "
        "AND octet_length(btrim(tier_name)) BETWEEN 1 AND 120 "
        "AND octet_length(broker_name)<=180 AND octet_length(broker_contact)<=500 "
        "AND octet_length(notes)<=1000 AND annual_premium<=9999999999.99",
    )
    op.create_check_constraint(
        "phase11c_lengths",
        "employee_insurance",
        "octet_length(btrim(member_id)) BETWEEN 1 AND 120 "
        "AND octet_length(card_number)<=120 AND octet_length(btrim(tier_name)) BETWEEN 1 AND 120",
    )
    op.create_check_constraint(
        "phase11c_lengths",
        "insurance_dependants",
        "octet_length(btrim(name)) BETWEEN 1 AND 180 "
        "AND octet_length(btrim(relationship)) BETWEEN 1 AND 120 "
        "AND octet_length(card_number)<=120",
    )


def _replace_document_policies() -> None:
    op.execute("DROP POLICY phase5g_employee_documents_delete_runtime ON public.employee_documents")
    op.execute(f"""
CREATE POLICY phase11c_employee_documents_delete_runtime ON public.employee_documents
FOR DELETE TO workloop_runtime USING (
  (({ADMIN_DOCUMENT_SCOPE}) OR ({SELF_DOCUMENT_SCOPE}))
  AND status IN ('pending_verification','rejected'));
CREATE POLICY phase11c_employee_documents_self_cleanup_runtime ON public.employee_documents
FOR UPDATE TO workloop_runtime USING (
  ({SELF_DOCUMENT_SCOPE}) AND status IN ('pending_verification','rejected')
  AND cleanup_requested_at IS NULL)
WITH CHECK (
  ({SELF_DOCUMENT_SCOPE}) AND status IN ('pending_verification','rejected')
  AND cleanup_requested_at IS NOT NULL);
CREATE POLICY phase11c_employee_documents_self_upload_runtime ON public.employee_documents
FOR UPDATE TO workloop_runtime USING (
  ({SELF_DOCUMENT_SCOPE}) AND status='pending_verification'
  AND file_security_scan_id IS NULL
  AND cleanup_requested_at IS NULL)
WITH CHECK (
  ({SELF_DOCUMENT_SCOPE}) AND status='pending_verification'
  AND upload_claimed_at IS NOT NULL
  AND cleanup_requested_at IS NULL);
GRANT UPDATE(content_type,sha256,file_security_scan_id,created_by_app_user_id,
  cleanup_requested_at,upload_claimed_at,updated_at,file_name,file_size,storage_path)
ON public.employee_documents TO workloop_runtime;
""")


def _extend_audit_authority() -> None:
    op.execute("""
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
RENAME TO _append_audit_event_phase11c_prior;
REVOKE ALL ON FUNCTION public._append_audit_event_phase11c_prior(text,text,uuid,text[],text,jsonb)
FROM PUBLIC,workloop_runtime;
""")
    op.execute(r"""
CREATE FUNCTION public.append_audit_event(
  p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],
  p_reason text,p_metadata jsonb
) RETURNS uuid
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp
AS $function$
DECLARE event_id uuid;
BEGIN
  IF p_action NOT IN (
    'employee_document_uploaded','employee_document_verified','employee_document_rejected',
    'employee_document_cleanup_requested',
    'insurance_policy_created','insurance_policy_updated','insurance_policy_deleted',
    'insurance_coverage_replaced','insurance_dependant_created',
    'insurance_dependant_updated','insurance_dependant_deleted',
    'employment_contract_recorded') THEN
    RETURN public._append_audit_event_phase11c_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user<>'workloop_runtime' OR public.workloop_actor_kind()<>'human'
     OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL OR p_reason IS NULL OR btrim(p_reason)=''
     OR jsonb_typeof(COALESCE(p_metadata,'{}'::jsonb))<>'object'
     OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
       WHERE key NOT IN ('transition','operation_id','action'))
     OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() caller
       WHERE caller.app_user_id=public.workloop_app_user_id()
         AND caller.account_status='active'
         AND caller.profile_company_id=public.workloop_company_id()
         AND caller.role=public.workloop_role()) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action LIKE 'employee_document_%' THEN
    IF p_entity_type<>'employee_document' OR NOT EXISTS (
      SELECT 1 FROM public.employee_documents source WHERE source.id=p_entity_id
        AND source.company_id=public.workloop_company_id()
        AND source.branch_id=public.workloop_branch_id()
        AND (public.workloop_role()='admin' OR
             source.employee_id=public.workloop_employee_id())) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action LIKE 'insurance_%' THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
    IF p_action IN ('insurance_policy_created','insurance_policy_updated',
                    'insurance_policy_deleted') THEN
      IF p_entity_type<>'insurance_policy' OR NOT EXISTS (
        SELECT 1 FROM public.insurance_policies source WHERE source.id=p_entity_id
          AND source.company_id=public.workloop_company_id()
          AND source.branch_id=public.workloop_branch_id()) THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action='insurance_coverage_replaced' THEN
      IF p_entity_type<>'employee_insurance' OR NOT EXISTS (
        SELECT 1 FROM public.employee_insurance source WHERE source.id=p_entity_id
          AND source.company_id=public.workloop_company_id()
          AND source.branch_id=public.workloop_branch_id()) THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSIF p_action IN ('insurance_dependant_created','insurance_dependant_updated',
                       'insurance_dependant_deleted') THEN
      IF p_entity_type<>'insurance_dependant' OR NOT EXISTS (
        SELECT 1 FROM public.insurance_dependants source WHERE source.id=p_entity_id
          AND source.company_id=public.workloop_company_id()
          AND source.branch_id=public.workloop_branch_id()) THEN
        RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
      END IF;
    ELSE
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='employment_contract_recorded' THEN
    IF p_entity_type<>'employee_contract' OR public.workloop_role()<>'admin'
       OR public.workloop_employee_id() IS NOT NULL OR NOT EXISTS (
         SELECT 1 FROM public.employee_contracts source WHERE source.id=p_entity_id
           AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  END IF;
  INSERT INTO public.audit_events(
    company_id,branch_id,actor_kind,actor_app_user_id,system_actor_key,
    initiated_by_app_user_id,action,entity_type,entity_id,changed_fields,reason,metadata)
  VALUES(public.workloop_company_id(),public.workloop_branch_id(),'human',
    public.workloop_app_user_id(),NULL,NULL,p_action,p_entity_type,p_entity_id,
    p_changed_fields,p_reason,COALESCE(p_metadata,'{}'::jsonb))
  RETURNING id INTO event_id;
  RETURN event_id;
END
$function$;
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
OWNER TO workloop_migration;
REVOKE ALL ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
TO workloop_runtime;
""")


def _extend_idempotency() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11C_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def upgrade() -> None:
    _add_document_contract()
    _add_optimistic_lock_fields()
    _replace_document_policies()
    _extend_audit_authority()
    _extend_idempotency()


def downgrade() -> None:
    op.execute("""
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.employee_documents WHERE content_type IS NOT NULL)
     OR EXISTS (SELECT 1 FROM public.idempotency_records
       WHERE replay_resource_kind IN ('employee_document','insurance_policy',
         'employee_insurance','insurance_dependant','employee_contract'))
  THEN RAISE EXCEPTION 'phase11c_data_requires_preservation'; END IF;
END $$;
""")
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PRIOR_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
    op.execute("DROP FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)")
    op.execute("""
ALTER FUNCTION public._append_audit_event_phase11c_prior(text,text,uuid,text[],text,jsonb)
RENAME TO append_audit_event;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
TO workloop_runtime;
""")
    op.execute(
        "DROP POLICY phase11c_employee_documents_delete_runtime ON public.employee_documents"
    )
    op.execute(
        "DROP POLICY phase11c_employee_documents_self_cleanup_runtime ON public.employee_documents"
    )
    op.execute(
        "DROP POLICY phase11c_employee_documents_self_upload_runtime ON public.employee_documents"
    )
    op.execute(f"""
CREATE POLICY phase5g_employee_documents_delete_runtime ON public.employee_documents
FOR DELETE TO workloop_runtime USING (
  ({ADMIN_DOCUMENT_SCOPE}) AND status IN ('pending_verification','rejected'));
""")
    for table in ("insurance_dependants", "employee_insurance", "insurance_policies"):
        op.execute(f"DROP TRIGGER trg_{table}_set_updated_at ON public.{table}")
        op.drop_constraint("phase11c_lengths", table, type_="check")
        op.drop_column(table, "updated_at")
    op.execute("DROP TRIGGER trg_employee_documents_set_updated_at ON public.employee_documents")
    op.drop_constraint("phase11c_lengths", "employee_documents", type_="check")
    op.drop_constraint(
        op.f("ck_employee_documents_phase11c_metadata"), "employee_documents", type_="check"
    )
    op.drop_constraint(
        "fk_employee_documents_created_by_scope", "employee_documents", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_employee_documents_file_security_scan_scope",
        "employee_documents",
        type_="foreignkey",
    )
    for column in (
        "upload_claimed_at",
        "cleanup_requested_at",
        "updated_at",
        "created_by_app_user_id",
        "file_security_scan_id",
        "sha256",
        "content_type",
    ):
        op.drop_column("employee_documents", column)
    op.execute("""
UPDATE public.employee_documents
SET file_name=COALESCE(file_name,'legacy-unavailable.pdf'),
    file_size=COALESCE(file_size,0),storage_path=COALESCE(storage_path,'');
""")
    op.alter_column("employee_documents", "storage_path", existing_type=sa.Text(), nullable=False)
    op.alter_column("employee_documents", "file_size", existing_type=sa.Integer(), nullable=False)
    op.alter_column("employee_documents", "file_name", existing_type=sa.Text(), nullable=False)
