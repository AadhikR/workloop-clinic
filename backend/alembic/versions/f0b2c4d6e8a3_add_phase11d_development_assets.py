"""Add Phase 11D development and asset authority.

Revision ID: f0b2c4d6e8a3
Revises: e9a1b3d5f7c2
Created: 2026-09-23 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f0b2c4d6e8a3"
down_revision: str | Sequence[str] | None = "e9a1b3d5f7c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRIOR_REPLAY_KINDS = (
    "'branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot',"
    "'attendance_settings','shift','shift_assignment','clock_event','biometric_mapping',"
    "'attendance_import_batch','attendance_record','regularisation_request',"
    "'attendance_period','roster_assignment','roster_publication_version','shift_swap_request',"
    "'employee_document','insurance_policy','employee_insurance','insurance_dependant',"
    "'employee_contract'"
)
PHASE11D_REPLAY_KINDS = PRIOR_REPLAY_KINDS + (
    ",'asset','asset_assignment','training_record','certification','cme_requirement'"
)

HUMAN_CONTEXT = """
current_user = 'workloop_runtime' AND session_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human' AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
  SELECT 1 FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.role = public.workloop_role()
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND ((principal.role = 'admin' AND principal.profile_employee_id IS NULL
      AND principal.employee_id IS NULL AND principal.branch_id IS NULL
      AND public.workloop_employee_id() IS NULL)
    OR (principal.role IN ('manager','employee')
      AND principal.profile_employee_id = public.workloop_employee_id()
      AND principal.employee_id = principal.profile_employee_id
      AND principal.employee_company_id = principal.profile_company_id
      AND principal.employee_branch_id = public.workloop_branch_id()
      AND principal.employee_active
      AND principal.employment_status IN ('Active','Probation','On Leave')
      AND principal.branch_id = principal.employee_branch_id
      AND principal.branch_company_id = principal.profile_company_id))
)
""".strip()
DEFINER_HUMAN_CONTEXT = HUMAN_CONTEXT.replace("current_user = 'workloop_runtime' AND ", "", 1)

ADMIN_SCOPE = f"""
{HUMAN_CONTEXT} AND public.workloop_role()='admin'
AND public.workloop_employee_id() IS NULL
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
""".strip()

SELF_SCOPE = f"""
{HUMAN_CONTEXT} AND public.workloop_role() IN ('manager','employee')
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
AND employee_id=public.workloop_employee_id()
""".strip()

REPORT_SCOPE = f"""
{HUMAN_CONTEXT} AND public.workloop_role()='manager'
AND company_id=public.workloop_company_id() AND branch_id=public.workloop_branch_id()
AND EXISTS (SELECT 1 FROM public.employees target WHERE target.id=employee_id
  AND target.company_id=public.workloop_company_id()
  AND target.branch_id=public.workloop_branch_id()
  AND target.reporting_manager_id=public.workloop_employee_id())
""".strip()


def _add_columns_and_constraints() -> None:
    for table in ("assets", "training_records", "certifications"):
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
    for table in ("training_records", "certifications"):
        for column in (
            sa.Column("content_type", sa.Text(), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("sha256", sa.Text(), nullable=True),
            sa.Column("file_security_scan_id", sa.UUID(), nullable=True),
            sa.Column("created_by_app_user_id", sa.UUID(), nullable=True),
        ):
            op.add_column(table, column)
        op.create_foreign_key(
            f"fk_{table}_file_security_scan_scope",
            table,
            "file_security_scans",
            ["file_security_scan_id", "company_id", "branch_id"],
            ["id", "company_id", "branch_id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            f"fk_{table}_created_by_scope",
            table,
            "user_profiles",
            ["created_by_app_user_id", "company_id"],
            ["app_user_id", "company_id"],
            ondelete="RESTRICT",
        )
        op.create_check_constraint(
            "phase11d_metadata",
            table,
            "(file_name='' AND storage_path='' AND content_type IS NULL "
            "AND size_bytes IS NULL AND sha256 IS NULL AND file_security_scan_id IS NULL) "
            "OR (octet_length(file_name) BETWEEN 1 AND 180 "
            "AND octet_length(storage_path) BETWEEN 1 AND 1024 AND content_type IS NULL "
            "AND size_bytes IS NULL AND sha256 IS NULL AND file_security_scan_id IS NULL) "
            "OR (octet_length(file_name) BETWEEN 1 AND 180 "
            "AND octet_length(storage_path) BETWEEN 1 AND 1024 "
            "AND content_type IN ('application/pdf','image/png','image/jpeg') "
            "AND size_bytes BETWEEN 1 AND 10485760 "
            "AND sha256~'^[0-9a-f]{64}$' AND file_security_scan_id IS NOT NULL)",
        )
    op.create_check_constraint(
        "phase11d_lengths",
        "assets",
        "octet_length(btrim(name)) BETWEEN 1 AND 180 "
        "AND octet_length(asset_code)<=120 AND octet_length(category)<=120 "
        "AND octet_length(brand)<=120 AND octet_length(model)<=120 "
        "AND octet_length(serial_number)<=180 AND octet_length(notes)<=1000 "
        "AND (purchase_cost IS NULL OR purchase_cost<=9999999999.99)",
    )
    op.create_check_constraint(
        "phase11d_lengths",
        "training_records",
        "octet_length(btrim(training_title)) BETWEEN 1 AND 180 "
        "AND octet_length(btrim(training_type)) BETWEEN 1 AND 120 "
        "AND octet_length(provider)<=180 AND octet_length(score)<=120 "
        "AND octet_length(notes)<=1000 AND cost<=9999999999.99 "
        "AND (duration_hours IS NULL OR duration_hours<=9999.99)",
    )
    op.create_check_constraint(
        "phase11d_lengths",
        "certifications",
        "octet_length(btrim(certification_name)) BETWEEN 1 AND 180 "
        "AND octet_length(btrim(issuing_body)) BETWEEN 1 AND 180 "
        "AND octet_length(certificate_no)<=120 AND octet_length(notes)<=1000",
    )
    op.create_check_constraint(
        "phase11d_bounds",
        "cme_requirements",
        "year BETWEEN 1900 AND 9999 AND required_hours<=9999.9 AND octet_length(notes)<=1000",
    )


def _replace_policies() -> None:
    op.execute("DROP POLICY phase5g_assets_select_runtime ON public.assets")
    op.execute(f"""
CREATE POLICY phase11d_assets_select_runtime ON public.assets
FOR SELECT TO workloop_runtime USING (
  ({ADMIN_SCOPE}) OR (
    {HUMAN_CONTEXT} AND public.workloop_role() IN ('manager','employee')
    AND assets.company_id=public.workloop_company_id()
    AND assets.branch_id=public.workloop_branch_id()
    AND EXISTS (SELECT 1 FROM public.asset_assignments assignment
      WHERE assignment.asset_id=assets.id
        AND assignment.company_id=assets.company_id
        AND assignment.branch_id=assets.branch_id
        AND assignment.employee_id=public.workloop_employee_id())
  ));
""")
    op.execute("DROP POLICY phase5g_training_records_delete_runtime ON public.training_records")
    op.execute(f"""
CREATE POLICY phase11d_training_records_delete_runtime ON public.training_records
FOR DELETE TO workloop_runtime USING (
  (({ADMIN_SCOPE}) OR ({SELF_SCOPE}) OR ({REPORT_SCOPE})) AND status='planned');
""")
    op.execute("DROP POLICY phase5g_training_records_insert_runtime ON public.training_records")
    op.execute(f"""
CREATE POLICY phase11d_training_records_insert_runtime ON public.training_records
FOR INSERT TO workloop_runtime WITH CHECK (
  ({ADMIN_SCOPE})
  OR (({SELF_SCOPE}) AND status='planned' AND cost=0 AND score=''
    AND passed IS NULL AND NOT is_cme)
  OR (({REPORT_SCOPE}) AND employee_id<>public.workloop_employee_id() AND status='planned'));
""")
    op.execute("DROP POLICY phase5g_certifications_delete_runtime ON public.certifications")
    op.execute(f"""
CREATE POLICY phase11d_certifications_delete_runtime ON public.certifications
FOR DELETE TO workloop_runtime USING (
  (({ADMIN_SCOPE}) OR ({SELF_SCOPE}) OR ({REPORT_SCOPE}))
  AND status IN ('pending_review','rejected'));
""")
    op.execute("DROP POLICY phase5g_cme_requirements_select_runtime ON public.cme_requirements")
    op.execute(f"""
CREATE POLICY phase11d_cme_requirements_select_runtime ON public.cme_requirements
FOR SELECT TO workloop_runtime USING (({ADMIN_SCOPE}) OR ({SELF_SCOPE}));
""")


def _add_direct_report_lock() -> None:
    op.execute(f"""
CREATE FUNCTION public.lock_development_direct_report(p_target_employee_id uuid)
RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path TO pg_catalog,public,pg_temp
AS $function$
DECLARE target public.employees%ROWTYPE;
BEGIN
  IF NOT ({DEFINER_HUMAN_CONTEXT}) OR public.workloop_role()<>'manager'
    OR public.workloop_employee_id() IS NULL THEN RETURN false; END IF;
  SELECT employee.* INTO target FROM public.employees employee
  WHERE employee.id=p_target_employee_id
    AND employee.company_id=public.workloop_company_id()
    AND employee.branch_id=public.workloop_branch_id()
  FOR UPDATE;
  RETURN FOUND AND target.id<>public.workloop_employee_id()
    AND target.reporting_manager_id=public.workloop_employee_id()
    AND target.active
    AND target.employment_status IN ('Active','Probation','On Leave');
END
$function$;
""")
    op.execute(
        "ALTER FUNCTION public.lock_development_direct_report(uuid) OWNER TO workloop_migration"
    )
    op.execute("REVOKE ALL ON FUNCTION public.lock_development_direct_report(uuid) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.lock_development_direct_report(uuid) TO workloop_runtime"
    )


def _extend_audit_authority() -> None:
    op.execute("""
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
RENAME TO _append_audit_event_phase11d_prior;
REVOKE ALL ON FUNCTION public._append_audit_event_phase11d_prior(text,text,uuid,text[],text,jsonb)
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
    'asset_created','asset_updated','asset_status_changed','asset_assigned',
    'asset_returned','asset_deleted','training_enrolled','training_updated',
    'training_completed','training_deleted','training_evidence_uploaded',
    'training_cleanup_requested','certification_submitted','certification_verified',
    'certification_rejected','certification_deleted','certification_evidence_uploaded',
    'certification_cleanup_requested','cme_requirement_saved','cme_requirement_deleted') THEN
    RETURN public._append_audit_event_phase11d_prior(
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
  IF p_action LIKE 'asset_%' THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
       OR p_entity_type NOT IN ('asset','asset_assignment')
       OR (p_entity_type='asset' AND NOT EXISTS (
         SELECT 1 FROM public.assets source WHERE source.id=p_entity_id
           AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id()))
       OR (p_entity_type='asset_assignment' AND NOT EXISTS (
         SELECT 1 FROM public.asset_assignments source WHERE source.id=p_entity_id
           AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id())) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action LIKE 'training_%' THEN
    IF p_entity_type<>'training_record' OR NOT EXISTS (
      SELECT 1 FROM public.training_records source
      LEFT JOIN public.employees target ON target.id=source.employee_id
      WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
        AND source.branch_id=public.workloop_branch_id()
        AND (public.workloop_role()='admin'
          OR source.employee_id=public.workloop_employee_id()
          OR (public.workloop_role()='manager'
            AND target.reporting_manager_id=public.workloop_employee_id()))) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action LIKE 'certification_%' THEN
    IF p_entity_type<>'certification' OR NOT EXISTS (
      SELECT 1 FROM public.certifications source
      LEFT JOIN public.employees target ON target.id=source.employee_id
      WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
        AND source.branch_id=public.workloop_branch_id()
        AND (public.workloop_role()='admin'
          OR source.employee_id=public.workloop_employee_id()
          OR (public.workloop_role()='manager'
            AND target.reporting_manager_id=public.workloop_employee_id()))) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action LIKE 'cme_requirement_%' THEN
    IF p_entity_type<>'cme_requirement' OR public.workloop_role()<>'admin'
       OR public.workloop_employee_id() IS NOT NULL OR NOT EXISTS (
         SELECT 1 FROM public.cme_requirements source WHERE source.id=p_entity_id
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
        f"(replay_resource_kind IN ({PHASE11D_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def upgrade() -> None:
    _add_columns_and_constraints()
    _replace_policies()
    _add_direct_report_lock()
    _extend_audit_authority()
    _extend_idempotency()


def downgrade() -> None:
    op.execute("""
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.training_records WHERE content_type IS NOT NULL)
     OR EXISTS (SELECT 1 FROM public.certifications WHERE content_type IS NOT NULL)
     OR EXISTS (SELECT 1 FROM public.idempotency_records
       WHERE replay_resource_kind IN ('asset','asset_assignment','training_record',
         'certification','cme_requirement'))
  THEN RAISE EXCEPTION 'phase11d_data_requires_preservation'; END IF;
END $$;
""")
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.lock_development_direct_report(uuid) "
        "FROM workloop_runtime"
    )
    op.execute("DROP FUNCTION public.lock_development_direct_report(uuid)")
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
ALTER FUNCTION public._append_audit_event_phase11d_prior(text,text,uuid,text[],text,jsonb)
RENAME TO append_audit_event;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
TO workloop_runtime;
""")
    op.execute("DROP POLICY phase11d_cme_requirements_select_runtime ON public.cme_requirements")
    op.execute(f"""
CREATE POLICY phase5g_cme_requirements_select_runtime ON public.cme_requirements
FOR SELECT TO workloop_runtime USING ({ADMIN_SCOPE});
""")
    op.execute("DROP POLICY phase11d_certifications_delete_runtime ON public.certifications")
    op.execute(f"""
CREATE POLICY phase5g_certifications_delete_runtime ON public.certifications
FOR DELETE TO workloop_runtime USING (
  (({ADMIN_SCOPE}) OR (({REPORT_SCOPE}) AND employee_id<>public.workloop_employee_id()))
  AND status IN ('pending_review','rejected'));
""")
    op.execute("DROP POLICY phase11d_training_records_delete_runtime ON public.training_records")
    op.execute(f"""
CREATE POLICY phase5g_training_records_delete_runtime ON public.training_records
FOR DELETE TO workloop_runtime USING (
  (({ADMIN_SCOPE}) OR (({REPORT_SCOPE}) AND employee_id<>public.workloop_employee_id()))
  AND status='planned');
""")
    op.execute("DROP POLICY phase11d_training_records_insert_runtime ON public.training_records")
    op.execute(f"""
CREATE POLICY phase5g_training_records_insert_runtime ON public.training_records
FOR INSERT TO workloop_runtime WITH CHECK (
  ({ADMIN_SCOPE})
  OR (({SELF_SCOPE}) AND status='planned' AND cost=0 AND score IS NULL
    AND passed IS NULL AND NOT is_cme)
  OR (({REPORT_SCOPE}) AND employee_id<>public.workloop_employee_id() AND status='planned'));
""")
    op.execute("DROP POLICY phase11d_assets_select_runtime ON public.assets")
    op.execute(f"""
CREATE POLICY phase5g_assets_select_runtime ON public.assets
FOR SELECT TO workloop_runtime USING (
  ({ADMIN_SCOPE}) OR (
    {HUMAN_CONTEXT} AND public.workloop_role() IN ('manager','employee')
    AND assets.company_id=public.workloop_company_id()
    AND assets.branch_id=public.workloop_branch_id()
    AND EXISTS (SELECT 1 FROM public.asset_assignments assignment
      WHERE assignment.asset_id=assets.id AND assignment.company_id=assets.company_id
        AND assignment.branch_id=assets.branch_id
        AND assignment.employee_id=public.workloop_employee_id()
        AND assignment.return_date IS NULL)));
""")
    op.drop_constraint("phase11d_bounds", "cme_requirements", type_="check")
    for table in ("certifications", "training_records"):
        op.drop_constraint("phase11d_lengths", table, type_="check")
        op.drop_constraint("phase11d_metadata", table, type_="check")
        op.drop_constraint(f"fk_{table}_created_by_scope", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_file_security_scan_scope", table, type_="foreignkey")
        for column in (
            "created_by_app_user_id",
            "file_security_scan_id",
            "sha256",
            "size_bytes",
            "content_type",
        ):
            op.drop_column(table, column)
    op.drop_constraint("phase11d_lengths", "assets", type_="check")
    for table in ("certifications", "training_records", "assets"):
        op.execute(f"DROP TRIGGER trg_{table}_set_updated_at ON public.{table}")
        op.drop_column(table, "updated_at")
