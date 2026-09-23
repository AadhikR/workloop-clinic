"""Add Phase 11E appraisal and clinical incident authority.

Revision ID: a1c3e5f7b9d4
Revises: f0b2c4d6e8a3
Created: 2026-09-23 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c3e5f7b9d4"
down_revision: str | Sequence[str] | None = "f0b2c4d6e8a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE11D_REPLAY_KINDS = (
    "'branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot',"
    "'attendance_settings','shift','shift_assignment','clock_event','biometric_mapping',"
    "'attendance_import_batch','attendance_record','regularisation_request',"
    "'attendance_period','roster_assignment','roster_publication_version','shift_swap_request',"
    "'employee_document','insurance_policy','employee_insurance','insurance_dependant',"
    "'employee_contract','asset','asset_assignment','training_record','certification',"
    "'cme_requirement'"
)
PHASE11E_REPLAY_KINDS = PHASE11D_REPLAY_KINDS + ",'appraisal_cycle','appraisal','incident_report'"


def _add_contract_columns() -> None:
    for table in ("appraisal_cycles", "appraisal_sections"):
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
    op.add_column(
        "appraisals",
        sa.Column(
            "template_version", sa.Text(), nullable=False, server_default=sa.text("'clinic-v1'")
        ),
    )
    op.create_check_constraint(
        "phase11e_template_version",
        "appraisals",
        "template_version ~ '^[a-z][a-z0-9-]{0,31}$'",
    )
    op.create_check_constraint(
        "phase11e_lengths",
        "appraisal_cycles",
        "octet_length(btrim(name)) BETWEEN 1 AND 180",
    )
    op.create_check_constraint(
        "phase11e_lengths",
        "appraisals",
        "octet_length(COALESCE(reviewer_comments,''))<=10000 "
        "AND octet_length(COALESCE(development_plan,''))<=10000",
    )
    op.create_check_constraint(
        "phase11e_lengths",
        "appraisal_sections",
        "octet_length(COALESCE(comments,''))<=10000",
    )
    op.create_check_constraint(
        "phase11e_lengths",
        "incident_reports",
        "octet_length(description) BETWEEN 1 AND 10000 "
        "AND octet_length(location)<=180 AND octet_length(department)<=180 "
        "AND octet_length(immediate_action)<=10000 AND octet_length(root_cause)<=10000 "
        "AND octet_length(corrective_action)<=10000 AND octet_length(notes)<=10000",
    )
    op.create_check_constraint(
        "phase11e_workflow",
        "incident_reports",
        "status<>'investigating' OR btrim(root_cause)<>''",
    )
    op.create_check_constraint(
        "phase11e_closed_evidence",
        "incident_reports",
        "status<>'closed' OR (btrim(root_cause)<>'' AND btrim(corrective_action)<>'')",
    )


def _extend_audit_authority() -> None:
    op.execute(
        """
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
RENAME TO _append_audit_event_phase11e_prior;
REVOKE ALL ON FUNCTION public._append_audit_event_phase11e_prior(text,text,uuid,text[],text,jsonb)
FROM PUBLIC,workloop_runtime;
"""
    )
    op.execute(
        r"""
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
    'appraisal_cycle_created','appraisal_cycle_updated','appraisal_cycle_activated',
    'appraisal_cycle_generated','appraisal_cycle_closed','appraisal_cycle_deleted',
    'appraisal_section_rated','appraisal_reviewed','appraisal_calibrated',
    'incident_created','incident_updated','incident_investigated',
    'incident_corrective_action_recorded','incident_closed') THEN
    RETURN public._append_audit_event_phase11e_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user<>'workloop_runtime' OR public.workloop_actor_kind()<>'human'
     OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL OR p_reason IS NULL OR btrim(p_reason)=''
     OR jsonb_typeof(COALESCE(p_metadata,'{}'::jsonb))<>'object'
     OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() caller
       WHERE caller.app_user_id=public.workloop_app_user_id()
         AND caller.account_status='active'
         AND caller.profile_company_id=public.workloop_company_id()
         AND caller.role=public.workloop_role()) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action LIKE 'appraisal_cycle_%' THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
       OR p_entity_type<>'appraisal_cycle'
       OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
         WHERE key NOT IN ('transition','created_count'))
       OR NOT EXISTS (SELECT 1 FROM public.appraisal_cycles source
         WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action='appraisal_section_rated' THEN
    IF public.workloop_role()<>'manager' OR p_entity_type<>'appraisal'
       OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
         WHERE key<>'section_id')
       OR NOT EXISTS (
         SELECT 1 FROM public.appraisals source
         JOIN public.employees employee ON employee.id=source.employee_id
          AND employee.company_id=source.company_id AND employee.branch_id=source.branch_id
         WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id()
           AND source.employee_id<>public.workloop_employee_id()
           AND employee.reporting_manager_id=public.workloop_employee_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action IN ('appraisal_reviewed','appraisal_calibrated') THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
       OR p_entity_type<>'appraisal'
       OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
         WHERE key<>'transition')
       OR NOT EXISTS (SELECT 1 FROM public.appraisals source
         WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
           AND source.branch_id=public.workloop_branch_id()) THEN
      RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSIF p_action LIKE 'incident_%' THEN
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
       OR p_entity_type<>'incident_report'
       OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
         WHERE key NOT IN ('incident_type','severity','from_status','to_status'))
       OR NOT EXISTS (SELECT 1 FROM public.incident_reports source
         WHERE source.id=p_entity_id AND source.company_id=public.workloop_company_id()
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
"""
    )


def _extend_idempotency() -> None:
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11E_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )


def upgrade() -> None:
    _add_contract_columns()
    _extend_audit_authority()
    _extend_idempotency()


def downgrade() -> None:
    op.execute(
        """
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM public.appraisals)
     OR EXISTS (SELECT 1 FROM public.incident_reports)
     OR EXISTS (SELECT 1 FROM public.idempotency_records
       WHERE replay_resource_kind IN ('appraisal_cycle','appraisal','incident_report'))
     OR EXISTS (SELECT 1 FROM public.audit_events WHERE action IN (
       'appraisal_cycle_created','appraisal_cycle_updated','appraisal_cycle_activated',
       'appraisal_cycle_generated','appraisal_cycle_closed','appraisal_cycle_deleted',
       'appraisal_section_rated','appraisal_reviewed','appraisal_calibrated',
       'incident_created','incident_updated','incident_investigated',
       'incident_corrective_action_recorded','incident_closed'))
  THEN RAISE EXCEPTION 'phase11e_data_requires_preservation'; END IF;
END $$;
"""
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11D_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
    op.execute("DROP FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)")
    op.execute(
        """
ALTER FUNCTION public._append_audit_event_phase11e_prior(text,text,uuid,text[],text,jsonb)
RENAME TO append_audit_event;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
TO workloop_runtime;
"""
    )
    op.drop_constraint("phase11e_closed_evidence", "incident_reports", type_="check")
    op.drop_constraint("phase11e_workflow", "incident_reports", type_="check")
    op.drop_constraint("phase11e_lengths", "incident_reports", type_="check")
    op.drop_constraint("phase11e_lengths", "appraisal_sections", type_="check")
    op.drop_constraint("phase11e_lengths", "appraisals", type_="check")
    op.drop_constraint("phase11e_lengths", "appraisal_cycles", type_="check")
    op.drop_constraint("phase11e_template_version", "appraisals", type_="check")
    op.drop_column("appraisals", "template_version")
    for table in ("appraisal_sections", "appraisal_cycles"):
        op.execute(f"DROP TRIGGER trg_{table}_set_updated_at ON public.{table}")
        op.drop_column(table, "updated_at")
