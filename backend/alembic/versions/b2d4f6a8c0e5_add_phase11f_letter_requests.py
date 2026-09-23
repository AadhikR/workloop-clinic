"""Add Phase 11F letter and custom request authority.

Revision ID: b2d4f6a8c0e5
Revises: a1c3e5f7b9d4
Created: 2026-09-23 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2d4f6a8c0e5"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PHASE11E_REPLAY_KINDS = (
    "'branch','employee','department','user_profile','leave_request','expense_claim',"
    "'salary_advance','payroll_run','compliance_override','nafis_snapshot',"
    "'attendance_settings','shift','shift_assignment','clock_event','biometric_mapping',"
    "'attendance_import_batch','attendance_record','regularisation_request',"
    "'attendance_period','roster_assignment','roster_publication_version','shift_swap_request',"
    "'employee_document','insurance_policy','employee_insurance','insurance_dependant',"
    "'employee_contract','asset','asset_assignment','training_record','certification',"
    "'cme_requirement','appraisal_cycle','appraisal','incident_report'"
)
PHASE11F_REPLAY_KINDS = PHASE11E_REPLAY_KINDS + ",'letter_request'"


def _add_contract_columns() -> None:
    op.add_column(
        "letter_requests",
        sa.Column(
            "employee_name_snapshot",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.add_column(
        "letter_requests",
        sa.Column("job_title_snapshot", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "letter_requests",
        sa.Column("department_snapshot", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "letter_requests", sa.Column("employment_start_date_snapshot", sa.Date(), nullable=True)
    )
    op.add_column(
        "letter_requests",
        sa.Column("branch_name_snapshot", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "letter_requests", sa.Column("basic_salary_snapshot", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "letter_requests", sa.Column("allowance_snapshot", sa.Numeric(12, 2), nullable=True)
    )
    op.add_column(
        "letter_requests",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
    )
    op.execute(
        """
UPDATE public.letter_requests request SET
 employee_name_snapshot=employee.name,
 job_title_snapshot=employee.job_title,
 department_snapshot=employee.department,
 employment_start_date_snapshot=employee.employment_start_date,
 branch_name_snapshot=branch.name,
 basic_salary_snapshot=CASE WHEN request.request_kind='letter' AND request.letter_type IN
  ('salary_certificate_bank','salary_certificate_embassy','salary_transfer_letter')
  THEN employee.basic_salary ELSE NULL END,
 allowance_snapshot=CASE WHEN request.request_kind='letter' AND request.letter_type IN
  ('salary_certificate_bank','salary_certificate_embassy','salary_transfer_letter')
  THEN employee.allowance ELSE NULL END
FROM public.employees employee
JOIN public.branches branch ON branch.id=employee.branch_id
 AND branch.company_id=employee.company_id
WHERE employee.id=request.employee_id AND employee.company_id=request.company_id
 AND employee.branch_id=request.branch_id
"""
    )
    op.execute(
        "CREATE TRIGGER trg_letter_requests_set_updated_at BEFORE UPDATE ON "
        "public.letter_requests FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )
    op.create_check_constraint(
        "phase11f_letter_fields",
        "letter_requests",
        "request_kind <> 'letter' OR (letter_type IN "
        "('salary_certificate_bank','salary_certificate_embassy','noc',"
        "'salary_transfer_letter','employment_confirmation') "
        "AND octet_length(purpose)<=500 AND (letter_type='employment_confirmation' "
        "OR octet_length(purpose)>=5))",
    )
    op.create_check_constraint(
        "phase11f_basic_salary",
        "letter_requests",
        "basic_salary_snapshot IS NULL OR basic_salary_snapshot>=0",
    )
    op.create_check_constraint(
        "phase11f_allowance",
        "letter_requests",
        "allowance_snapshot IS NULL OR allowance_snapshot>=0",
    )
    op.create_check_constraint(
        "phase11f_salary_snapshot",
        "letter_requests",
        "((request_kind='letter' AND letter_type IN "
        "('salary_certificate_bank','salary_certificate_embassy','salary_transfer_letter') "
        "AND basic_salary_snapshot IS NOT NULL AND allowance_snapshot IS NOT NULL) "
        "OR (basic_salary_snapshot IS NULL AND allowance_snapshot IS NULL))",
    )
    op.create_check_constraint(
        "phase11f_decided_snapshot",
        "letter_requests",
        "status='pending' OR (btrim(employee_name_snapshot)<>'' "
        "AND btrim(branch_name_snapshot)<>'')",
    )


def _extend_audit_authority() -> None:
    op.execute(
        """
ALTER FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
RENAME TO _append_audit_event_phase11f_prior;
REVOKE ALL ON FUNCTION public._append_audit_event_phase11f_prior(text,text,uuid,text[],text,jsonb)
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
DECLARE
  event_id uuid;
  source_employee uuid;
  source_status text;
  source_actor uuid;
  source_kind text;
  source_letter_type text;
  required_fields text[];
BEGIN
  IF p_action NOT IN ('letter_submitted','letter_completed','letter_rejected') THEN
    RETURN public._append_audit_event_phase11f_prior(
      p_action,p_entity_type,p_entity_id,p_changed_fields,p_reason,p_metadata);
  END IF;
  IF session_user<>'workloop_runtime' OR public.workloop_actor_kind()<>'human'
     OR public.workloop_actor_key() IS NOT NULL OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL OR p_reason IS NULL OR btrim(p_reason)=''
     OR p_entity_type<>'letter_request'
     OR jsonb_typeof(COALESCE(p_metadata,'{}'::jsonb))<>'object'
     OR EXISTS (SELECT 1 FROM jsonb_object_keys(COALESCE(p_metadata,'{}'::jsonb)) key
       WHERE key NOT IN ('transition','request_kind','letter_type'))
     OR NOT EXISTS (SELECT 1 FROM public.resolve_workloop_principal() caller
       WHERE caller.app_user_id=public.workloop_app_user_id()
         AND caller.account_status='active'
         AND caller.profile_company_id=public.workloop_company_id()
         AND caller.role=public.workloop_role()) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  SELECT employee_id,status,actioned_by_app_user_id,request_kind,letter_type
  INTO source_employee,source_status,source_actor,source_kind,source_letter_type
  FROM public.letter_requests
  WHERE id=p_entity_id AND company_id=public.workloop_company_id()
    AND branch_id=public.workloop_branch_id();
  IF NOT FOUND
     OR p_metadata->>'request_kind' IS DISTINCT FROM source_kind
     OR (source_kind='letter' AND p_metadata->>'letter_type' IS DISTINCT FROM source_letter_type)
     OR (source_kind='custom' AND p_metadata->'letter_type'<>'null'::jsonb) THEN
    RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
  END IF;
  IF p_action='letter_submitted' THEN
    required_fields := ARRAY['request_kind','letter_type','purpose','status',
      'employee_name_snapshot','job_title_snapshot','department_snapshot',
      'employment_start_date_snapshot','branch_name_snapshot','basic_salary_snapshot',
      'allowance_snapshot'];
    IF public.workloop_role() NOT IN ('employee','manager')
       OR public.workloop_employee_id() IS DISTINCT FROM source_employee
       OR source_status<>'pending' OR p_metadata ? 'transition'
       OR NOT (p_changed_fields @> required_fields AND p_changed_fields <@ required_fields)
       THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
    END IF;
  ELSE
    required_fields := CASE WHEN p_action='letter_completed'
      THEN ARRAY['status','actioned_at','actioned_by_app_user_id','completed_at']::text[]
      ELSE ARRAY['status','actioned_at','actioned_by_app_user_id','rejection_reason']::text[] END;
    IF public.workloop_role()<>'admin' OR public.workloop_employee_id() IS NOT NULL
       OR source_actor IS DISTINCT FROM public.workloop_app_user_id()
       OR source_status IS DISTINCT FROM
         (CASE WHEN p_action='letter_completed' THEN 'completed' ELSE 'rejected' END)
       OR p_metadata->>'transition' IS DISTINCT FROM
         (CASE WHEN p_action='letter_completed' THEN 'pending_to_completed'
               ELSE 'pending_to_rejected' END)
       OR NOT (p_changed_fields @> required_fields AND p_changed_fields <@ required_fields)
       THEN RAISE EXCEPTION 'audit event denied' USING ERRCODE='42501';
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
        f"(replay_resource_kind IN ({PHASE11F_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
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
  IF EXISTS (SELECT 1 FROM public.idempotency_records
       WHERE replay_resource_kind='letter_request')
     OR EXISTS (SELECT 1 FROM public.audit_events
       WHERE action IN ('letter_submitted','letter_completed','letter_rejected'))
  THEN RAISE EXCEPTION 'phase11f_data_requires_preservation'; END IF;
END $$;
"""
    )
    op.drop_constraint("replay_resource", "idempotency_records", type_="check")
    op.create_check_constraint(
        "replay_resource",
        "idempotency_records",
        f"(replay_resource_kind IN ({PHASE11E_REPLAY_KINDS}) AND replay_resource_id IS NOT NULL) "
        "OR (replay_resource_kind='tenant' AND replay_resource_id IS NULL) "
        "OR replay_resource_kind IS NULL",
    )
    op.execute("DROP FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)")
    op.execute(
        """
ALTER FUNCTION public._append_audit_event_phase11f_prior(text,text,uuid,text[],text,jsonb)
RENAME TO append_audit_event;
GRANT EXECUTE ON FUNCTION public.append_audit_event(text,text,uuid,text[],text,jsonb)
TO workloop_runtime;
"""
    )
    op.drop_constraint("phase11f_decided_snapshot", "letter_requests", type_="check")
    op.drop_constraint("phase11f_salary_snapshot", "letter_requests", type_="check")
    op.drop_constraint("phase11f_allowance", "letter_requests", type_="check")
    op.drop_constraint("phase11f_basic_salary", "letter_requests", type_="check")
    op.drop_constraint("phase11f_letter_fields", "letter_requests", type_="check")
    op.execute("DROP TRIGGER trg_letter_requests_set_updated_at ON public.letter_requests")
    for column in (
        "updated_at",
        "allowance_snapshot",
        "basic_salary_snapshot",
        "branch_name_snapshot",
        "employment_start_date_snapshot",
        "department_snapshot",
        "job_title_snapshot",
        "employee_name_snapshot",
    ):
        op.drop_column("letter_requests", column)
