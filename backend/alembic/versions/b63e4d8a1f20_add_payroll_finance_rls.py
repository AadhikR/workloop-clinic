"""Add Phase 5F payroll and finance row security.

Revision ID: b63e4d8a1f20
Revises: f52e0a1b9c34
Created: 2026-09-06 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b63e4d8a1f20"
down_revision: str | Sequence[str] | None = "f52e0a1b9c34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RLS_TABLES: tuple[str, ...] = (
    "payroll_runs",
    "payroll_entries",
    "payslips",
    "payroll_approval_log",
    "nafis_reports",
    "salary_advances",
    "advance_repayments",
    "expense_claims",
    "compliance_overrides",
)

HUMAN_CONTEXT = """
current_user = 'workloop_runtime'
AND session_user = 'workloop_runtime'
AND public.workloop_actor_kind() = 'human'
AND public.workloop_actor_key() IS NULL
AND public.workloop_business_date() IS NOT NULL
AND EXISTS (
  SELECT 1
  FROM public.resolve_workloop_principal() AS principal
  WHERE principal.app_user_id = public.workloop_app_user_id()
    AND principal.account_status = 'active'
    AND principal.profile_app_user_id = principal.app_user_id
    AND principal.role = public.workloop_role()
    AND principal.profile_company_id = public.workloop_company_id()
    AND principal.company_id = principal.profile_company_id
    AND (
      (
        principal.role = 'admin'
        AND principal.profile_employee_id IS NULL
        AND principal.employee_id IS NULL
        AND principal.branch_id IS NULL
        AND public.workloop_employee_id() IS NULL
      )
      OR
      (
        principal.role IN ('manager', 'employee')
        AND principal.profile_employee_id = public.workloop_employee_id()
        AND principal.employee_id = principal.profile_employee_id
        AND principal.employee_company_id = principal.profile_company_id
        AND principal.employee_branch_id = public.workloop_branch_id()
        AND principal.employee_active
        AND principal.employment_status IN ('Active', 'Probation', 'On Leave')
        AND principal.branch_id = principal.employee_branch_id
        AND principal.branch_company_id = principal.profile_company_id
      )
    )
)
""".strip()


def _policy(
    name: str,
    table: str,
    command: str,
    *,
    using: str | None = None,
    check: str | None = None,
) -> None:
    clauses: list[str] = []
    if using is not None:
        clauses.append(f"USING ({using})")
    if check is not None:
        clauses.append(f"WITH CHECK ({check})")
    op.execute(
        f"CREATE POLICY {name} ON public.{table} FOR {command} "
        "TO workloop_runtime " + " ".join(clauses)
    )


def _admin_branch(table: str | None = None) -> str:
    prefix = f"{table}." if table else ""
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND {prefix}company_id = public.workloop_company_id()
AND {prefix}branch_id = public.workloop_branch_id()"""


def _self_scope(employee_column: str = "employee_id") -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND {employee_column} = public.workloop_employee_id()"""


def _direct_report_scope() -> str:
    return f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'manager'
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND EXISTS (
  SELECT 1
  FROM public.employees AS target_employee
  WHERE target_employee.id = employee_id
    AND target_employee.company_id = expense_claims.company_id
    AND target_employee.branch_id = expense_claims.branch_id
    AND target_employee.reporting_manager_id = public.workloop_employee_id()
)"""


def _create_policies() -> None:
    admin = _admin_branch()
    for command in ("SELECT", "INSERT", "UPDATE"):
        _policy(
            f"phase5f_nafis_reports_{command.lower()}_runtime",
            "nafis_reports",
            command,
            using=admin if command != "INSERT" else None,
            check=admin if command in {"INSERT", "UPDATE"} else None,
        )

    payroll_run_insert = f"""{admin}
AND status = 'draft'
AND approval_status = 'draft'
AND run_by_app_user_id = public.workloop_app_user_id()"""
    _policy("phase5f_payroll_runs_select_runtime", "payroll_runs", "SELECT", using=admin)
    _policy(
        "phase5f_payroll_runs_insert_runtime",
        "payroll_runs",
        "INSERT",
        check=payroll_run_insert,
    )
    _policy(
        "phase5f_payroll_runs_update_runtime",
        "payroll_runs",
        "UPDATE",
        using=admin,
        check=f"""{admin}
AND (
  approval_status <> 'approved'
  OR (
    approved_by_app_user_id IS DISTINCT FROM run_by_app_user_id
    AND approved_by_app_user_id IS DISTINCT FROM submitted_by_app_user_id
  )
)
AND (
  rejected_by_app_user_id IS NULL
  OR (
    rejected_by_app_user_id IS DISTINCT FROM run_by_app_user_id
    AND rejected_by_app_user_id IS DISTINCT FROM submitted_by_app_user_id
  )
)""",
    )
    payroll_delete = f"""{admin}
AND status = 'draft'
AND approval_status = 'draft'
AND NOT EXISTS (
  SELECT 1 FROM public.payroll_entries AS entry
  WHERE entry.payroll_run_id = payroll_runs.id
)
AND NOT EXISTS (
  SELECT 1 FROM public.payroll_approval_log AS approval
  WHERE approval.payroll_run_id = payroll_runs.id
)
AND NOT EXISTS (
  SELECT 1 FROM public.payslips AS payslip
  WHERE payslip.payroll_run_id = payroll_runs.id
)
AND NOT EXISTS (
  SELECT 1 FROM public.advance_repayments AS repayment
  WHERE repayment.payroll_run_id = payroll_runs.id
)
AND NOT EXISTS (
  SELECT 1 FROM public.expense_claims AS claim
  WHERE claim.payroll_run_id = payroll_runs.id
)"""
    _policy(
        "phase5f_payroll_runs_delete_runtime",
        "payroll_runs",
        "DELETE",
        using=payroll_delete,
    )

    _policy(
        "phase5f_payroll_entries_select_runtime",
        "payroll_entries",
        "SELECT",
        using=admin,
    )

    payslip_select = f"""{HUMAN_CONTEXT}
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND (
  public.workloop_role() = 'admin'
  OR (
    public.workloop_role() IN ('manager', 'employee')
    AND employee_id = public.workloop_employee_id()
  )
)"""
    _policy("phase5f_payslips_select_runtime", "payslips", "SELECT", using=payslip_select)
    _policy("phase5f_payslips_insert_runtime", "payslips", "INSERT", check=admin)

    approval_insert = f"""{admin}
AND performed_by_app_user_id = public.workloop_app_user_id()"""
    _policy(
        "phase5f_payroll_approval_log_select_runtime",
        "payroll_approval_log",
        "SELECT",
        using=admin,
    )
    _policy(
        "phase5f_payroll_approval_log_insert_runtime",
        "payroll_approval_log",
        "INSERT",
        check=approval_insert,
    )

    self_advance = _self_scope()
    advance_scope = f"({admin}) OR ({self_advance})"
    _policy(
        "phase5f_salary_advances_select_runtime",
        "salary_advances",
        "SELECT",
        using=advance_scope,
    )
    _policy(
        "phase5f_salary_advances_insert_runtime",
        "salary_advances",
        "INSERT",
        check=advance_scope,
    )
    advance_update = f"""({admin}) OR (
  {self_advance}
  AND status = 'pending'
)"""
    advance_update_check = f"""({admin}) OR (
  {self_advance}
  AND status = 'cancelled'
)"""
    _policy(
        "phase5f_salary_advances_update_runtime",
        "salary_advances",
        "UPDATE",
        using=advance_update,
        check=advance_update_check,
    )

    self_repayment = f"""{HUMAN_CONTEXT}
AND public.workloop_role() IN ('manager', 'employee')
AND company_id = public.workloop_company_id()
AND branch_id = public.workloop_branch_id()
AND EXISTS (
  SELECT 1
  FROM public.salary_advances AS advance
  WHERE advance.id = advance_id
    AND advance.company_id = advance_repayments.company_id
    AND advance.branch_id = advance_repayments.branch_id
    AND advance.employee_id = public.workloop_employee_id()
)"""
    repayment_scope = f"({admin}) OR ({self_repayment})"
    _policy(
        "phase5f_advance_repayments_select_runtime",
        "advance_repayments",
        "SELECT",
        using=repayment_scope,
    )

    self_expense = _self_scope()
    report_expense = _direct_report_scope()
    expense_select = f"({admin}) OR ({self_expense}) OR ({report_expense})"
    _policy(
        "phase5f_expense_claims_select_runtime",
        "expense_claims",
        "SELECT",
        using=expense_select,
    )
    _policy(
        "phase5f_expense_claims_insert_runtime",
        "expense_claims",
        "INSERT",
        check=self_expense,
    )
    expense_update = f"({admin}) OR ({report_expense})"
    _policy(
        "phase5f_expense_claims_update_runtime",
        "expense_claims",
        "UPDATE",
        using=expense_update,
        check=expense_update,
    )
    expense_delete = f"""(({admin}) OR ({self_expense}))
AND status IN ('pending', 'rejected', 'manager_rejected')"""
    _policy(
        "phase5f_expense_claims_delete_runtime",
        "expense_claims",
        "DELETE",
        using=expense_delete,
    )

    compliance_select = f"""{HUMAN_CONTEXT}
AND public.workloop_role() = 'admin'
AND company_id = public.workloop_company_id()
AND (
  (branch_id IS NULL AND public.workloop_branch_id() IS NULL)
  OR (
    branch_id IS NOT NULL
    AND branch_id = public.workloop_branch_id()
  )
)"""
    compliance_insert = f"""{compliance_select}
AND created_by_app_user_id = public.workloop_app_user_id()"""
    _policy(
        "phase5f_compliance_overrides_select_runtime",
        "compliance_overrides",
        "SELECT",
        using=compliance_select,
    )
    _policy(
        "phase5f_compliance_overrides_insert_runtime",
        "compliance_overrides",
        "INSERT",
        check=compliance_insert,
    )


def _admin_function_guard() -> str:
    return """
  IF session_user <> 'workloop_runtime'
     OR public.workloop_actor_kind() IS DISTINCT FROM 'human'
     OR public.workloop_actor_key() IS NOT NULL
     OR public.workloop_business_date() IS NULL
     OR public.workloop_app_user_id() IS NULL
     OR public.workloop_role() IS DISTINCT FROM 'admin'
     OR public.workloop_company_id() IS NULL
     OR public.workloop_branch_id() IS NULL
     OR public.workloop_employee_id() IS NOT NULL
     OR NOT EXISTS (
       SELECT 1
       FROM public.resolve_workloop_principal() AS principal
       WHERE principal.app_user_id = public.workloop_app_user_id()
         AND principal.account_status = 'active'
         AND principal.profile_app_user_id = principal.app_user_id
         AND principal.role = 'admin'
         AND principal.profile_company_id = public.workloop_company_id()
         AND principal.company_id = principal.profile_company_id
         AND principal.profile_employee_id IS NULL
         AND principal.employee_id IS NULL
         AND principal.branch_id IS NULL
     )
     OR NOT EXISTS (
       SELECT 1
       FROM public.branches AS selected_branch
       WHERE selected_branch.id = public.workloop_branch_id()
         AND selected_branch.company_id = public.workloop_company_id()
     ) THEN
    RAISE EXCEPTION 'workloop_admin_context_required';
  END IF;
"""


def _replace_payroll_entries_sql(*, hardened: bool) -> str:
    guard = _admin_function_guard() if hardened else ""
    search_path = "pg_catalog, public, pg_temp"
    scope = (
        """
  IF v_run.company_id <> public.workloop_company_id()
     OR v_run.branch_id <> public.workloop_branch_id() THEN
    RAISE EXCEPTION 'payroll_run_out_of_scope';
  END IF;
"""
        if hardened
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION public.replace_payroll_entries(
  p_payroll_run_id uuid, p_entries jsonb)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO {search_path}
AS $function$
DECLARE
  v_run          public.payroll_runs%ROWTYPE;
  v_entry        jsonb;
  v_key          text;
  v_emp          uuid;
  v_emp_ids      uuid[] := ARRAY[]::uuid[];
  v_scalar_keys  text[] := ARRAY[
    'basic_salary','housing_allowance','transport_allowance','allowance',
    'increment','bonus','other_pay','leave_deduction','variable_allowance'];
  v_allowed_keys text[] := ARRAY[
    'employee_id','basic_salary','housing_allowance','transport_allowance',
    'allowance','increment','bonus','other_pay','leave_deduction',
    'variable_allowance','additional_allowances','deductions','excluded',
    'wps_payment_status','wps_rejection_reason'];
  v_val          numeric;
BEGIN
{guard}
  IF p_entries IS NULL OR pg_catalog.jsonb_typeof(p_entries) <> 'array' THEN
    RAISE EXCEPTION 'replace_payroll_entries_requires_array';
  END IF;

  SELECT * INTO v_run FROM public.payroll_runs
  WHERE id = p_payroll_run_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'payroll_run_not_found';
  END IF;
{scope}
  IF v_run.status <> 'draft' OR v_run.approval_status <> 'draft' THEN
    RAISE EXCEPTION 'payroll_run_not_draft';
  END IF;

  FOR v_entry IN SELECT * FROM pg_catalog.jsonb_array_elements(p_entries)
  LOOP
    IF pg_catalog.jsonb_typeof(v_entry) <> 'object' THEN
      RAISE EXCEPTION 'payroll_entry_not_object';
    END IF;
    FOR v_key IN SELECT pg_catalog.jsonb_object_keys(v_entry)
    LOOP
      IF v_key <> ALL (v_allowed_keys) THEN
        RAISE EXCEPTION 'payroll_entry_unknown_key: %', v_key;
      END IF;
    END LOOP;
    IF v_entry->>'employee_id' IS NULL THEN
      RAISE EXCEPTION 'payroll_entry_missing_employee';
    END IF;
    v_emp := (v_entry->>'employee_id')::uuid;
    IF v_emp = ANY (v_emp_ids) THEN
      RAISE EXCEPTION 'payroll_entry_duplicate_employee: %', v_emp;
    END IF;
    v_emp_ids := pg_catalog.array_append(v_emp_ids, v_emp);

    FOREACH v_key IN ARRAY v_scalar_keys
    LOOP
      IF v_entry ? v_key AND pg_catalog.jsonb_typeof(v_entry->v_key) <> 'null' THEN
        IF pg_catalog.jsonb_typeof(v_entry->v_key) <> 'number' THEN
          RAISE EXCEPTION 'payroll_entry_scalar_not_number: %', v_key;
        END IF;
        v_val := (v_entry->>v_key)::numeric;
      ELSE
        v_val := 0;
      END IF;
      IF v_val = 'NaN'::numeric
         OR v_val = 'Infinity'::numeric
         OR v_val = '-Infinity'::numeric THEN
        RAISE EXCEPTION 'payroll_entry_scalar_not_finite: %', v_key;
      END IF;
      IF pg_catalog.scale(v_val) > 2 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_scale: %', v_key;
      END IF;
      IF pg_catalog.abs(v_val) > 9999999999.99 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_range: %', v_key;
      END IF;
      IF v_key <> 'variable_allowance' AND v_val < 0 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_negative: %', v_key;
      END IF;
    END LOOP;

    IF v_entry ? 'additional_allowances'
       AND pg_catalog.jsonb_typeof(v_entry->'additional_allowances') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_additional_allowances_not_array';
    END IF;
    IF v_entry ? 'deductions'
       AND pg_catalog.jsonb_typeof(v_entry->'deductions') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_deductions_not_array';
    END IF;
    IF v_entry ? 'excluded'
       AND pg_catalog.jsonb_typeof(v_entry->'excluded') NOT IN ('boolean', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_excluded_not_boolean';
    END IF;
  END LOOP;

  IF EXISTS (
    SELECT 1 FROM pg_catalog.unnest(v_emp_ids) AS candidate(id)
    WHERE NOT EXISTS (
      SELECT 1 FROM public.employees AS employee
      WHERE employee.id = candidate.id
        AND employee.company_id = v_run.company_id
        AND employee.branch_id = v_run.branch_id
    )
  ) THEN
    RAISE EXCEPTION 'payroll_entry_employee_out_of_scope';
  END IF;

  DELETE FROM public.payroll_entries WHERE payroll_run_id = p_payroll_run_id;
  INSERT INTO public.payroll_entries (
    payroll_run_id, company_id, branch_id, employee_id,
    basic_salary, housing_allowance, transport_allowance, allowance,
    increment, bonus, other_pay, leave_deduction, variable_allowance,
    additional_allowances, deductions, excluded,
    wps_payment_status, wps_rejection_reason)
  SELECT
    p_payroll_run_id, v_run.company_id, v_run.branch_id,
    (entry->>'employee_id')::uuid,
    COALESCE((entry->>'basic_salary')::numeric, 0),
    COALESCE((entry->>'housing_allowance')::numeric, 0),
    COALESCE((entry->>'transport_allowance')::numeric, 0),
    COALESCE((entry->>'allowance')::numeric, 0),
    COALESCE((entry->>'increment')::numeric, 0),
    COALESCE((entry->>'bonus')::numeric, 0),
    COALESCE((entry->>'other_pay')::numeric, 0),
    COALESCE((entry->>'leave_deduction')::numeric, 0),
    COALESCE((entry->>'variable_allowance')::numeric, 0),
    CASE WHEN pg_catalog.jsonb_typeof(entry->'additional_allowances') = 'array'
      THEN entry->'additional_allowances' ELSE '[]'::jsonb END,
    CASE WHEN pg_catalog.jsonb_typeof(entry->'deductions') = 'array'
      THEN entry->'deductions' ELSE '[]'::jsonb END,
    COALESCE((entry->>'excluded')::boolean, false),
    COALESCE(entry->>'wps_payment_status', 'pending'),
    COALESCE(entry->>'wps_rejection_reason', '')
  FROM pg_catalog.jsonb_array_elements(p_entries) AS entry;
END;
$function$;
"""


def _record_advance_repayment_sql(*, hardened: bool) -> str:
    guard = _admin_function_guard() if hardened else ""
    search_path = "pg_catalog, public, pg_temp"
    scope = (
        """
  IF v_advance.company_id <> public.workloop_company_id()
     OR v_advance.branch_id <> public.workloop_branch_id() THEN
    RAISE EXCEPTION 'advance_repayment_out_of_scope';
  END IF;
"""
        if hardened
        else ""
    )
    return f"""
CREATE OR REPLACE FUNCTION public.record_advance_repayment(
  p_advance_id uuid,
  p_payroll_run_id uuid,
  p_idempotency_key uuid,
  p_amount numeric,
  p_paid_date date DEFAULT CURRENT_DATE)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO {search_path}
AS $function$
DECLARE
  v_advance    public.salary_advances%ROWTYPE;
  v_existing   public.advance_repayments%ROWTYPE;
  v_run_co     uuid;
  v_run_br     uuid;
  v_amount     numeric;
  v_paid_date  date;
  v_new_bal    numeric;
  v_new_status text;
  v_repay_id   uuid;
BEGIN
{guard}
  IF p_advance_id IS NULL OR p_idempotency_key IS NULL THEN
    RAISE EXCEPTION 'advance_repayment_missing_key';
  END IF;
  v_paid_date := p_paid_date;
  IF v_paid_date IS NULL THEN
    RAISE EXCEPTION 'advance_repayment_missing_paid_date';
  END IF;
  v_amount := p_amount;
  IF v_amount IS NULL
     OR v_amount = 'NaN'::numeric
     OR v_amount = 'Infinity'::numeric
     OR v_amount = '-Infinity'::numeric THEN
    RAISE EXCEPTION 'advance_repayment_amount_not_finite';
  END IF;
  IF pg_catalog.scale(v_amount) > 2 THEN
    RAISE EXCEPTION 'advance_repayment_amount_scale';
  END IF;
  IF v_amount <= 0 OR v_amount > 9999999999.99 THEN
    RAISE EXCEPTION 'advance_repayment_amount_range';
  END IF;

  SELECT * INTO v_advance FROM public.salary_advances
  WHERE id = p_advance_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'advance_repayment_advance_not_found';
  END IF;
{scope}
  SELECT * INTO v_existing
  FROM public.advance_repayments
  WHERE advance_id = p_advance_id AND idempotency_key = p_idempotency_key;
  IF FOUND THEN
    IF v_existing.advance_id = p_advance_id
       AND v_existing.payroll_run_id IS NOT DISTINCT FROM p_payroll_run_id
       AND v_existing.amount = v_amount
       AND v_existing.paid_date = v_paid_date
       AND v_existing.company_id = v_advance.company_id
       AND v_existing.branch_id = v_advance.branch_id THEN
      RETURN pg_catalog.jsonb_build_object(
        'repaymentId', v_existing.id,
        'newBalance', v_advance.outstanding_balance,
        'newStatus', v_advance.status,
        'alreadyRecorded', true);
    END IF;
    RAISE EXCEPTION 'advance_repayment_idempotency_conflict';
  END IF;

  IF p_payroll_run_id IS NOT NULL THEN
    SELECT * INTO v_existing
    FROM public.advance_repayments
    WHERE advance_id = p_advance_id AND payroll_run_id = p_payroll_run_id;
    IF FOUND THEN
      RAISE EXCEPTION 'advance_repayment_payroll_conflict';
    END IF;
  END IF;
  IF v_advance.status <> 'active' OR v_advance.outstanding_balance <= 0 THEN
    RAISE EXCEPTION 'advance_repayment_not_active';
  END IF;

  IF p_payroll_run_id IS NOT NULL THEN
    SELECT company_id, branch_id INTO v_run_co, v_run_br
    FROM public.payroll_runs WHERE id = p_payroll_run_id;
    IF NOT FOUND
       OR v_run_co <> v_advance.company_id
       OR v_run_br <> v_advance.branch_id THEN
      RAISE EXCEPTION 'advance_repayment_payroll_scope';
    END IF;
  END IF;
  IF v_amount > v_advance.outstanding_balance THEN
    RAISE EXCEPTION 'advance_repayment_exceeds_outstanding';
  END IF;

  INSERT INTO public.advance_repayments (
    company_id, branch_id, advance_id, payroll_run_id,
    idempotency_key, amount, paid_date)
  VALUES (
    v_advance.company_id, v_advance.branch_id, p_advance_id, p_payroll_run_id,
    p_idempotency_key, v_amount, v_paid_date)
  RETURNING id INTO v_repay_id;

  UPDATE public.salary_advances
  SET outstanding_balance = outstanding_balance - v_amount,
      status = CASE WHEN outstanding_balance - v_amount <= 0 THEN 'settled' ELSE 'active' END
  WHERE id = p_advance_id
  RETURNING outstanding_balance, status INTO v_new_bal, v_new_status;

  RETURN pg_catalog.jsonb_build_object(
    'repaymentId', v_repay_id,
    'newBalance', v_new_bal,
    'newStatus', v_new_status,
    'alreadyRecorded', false);
END;
$function$;
"""


def _replace_functions(*, hardened: bool) -> None:
    op.execute(_replace_payroll_entries_sql(hardened=hardened))
    op.execute(_record_advance_repayment_sql(hardened=hardened))
    for signature in (
        "public.replace_payroll_entries(uuid, jsonb)",
        "public.record_advance_repayment(uuid, uuid, uuid, numeric, date)",
    ):
        op.execute(f"ALTER FUNCTION {signature} OWNER TO workloop_migration")
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO workloop_runtime")


def _grant_privileges() -> None:
    op.execute("GRANT INSERT, UPDATE, DELETE ON TABLE public.payroll_runs TO workloop_runtime")
    op.execute("GRANT INSERT, UPDATE ON TABLE public.salary_advances TO workloop_runtime")
    op.execute("GRANT DELETE ON TABLE public.expense_claims TO workloop_runtime")


def upgrade() -> None:
    _replace_functions(hardened=True)
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    _create_policies()
    _grant_privileges()


def downgrade() -> None:
    op.execute("REVOKE INSERT, UPDATE, DELETE ON TABLE public.payroll_runs FROM workloop_runtime")
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.salary_advances FROM workloop_runtime")
    op.execute("REVOKE DELETE ON TABLE public.expense_claims FROM workloop_runtime")

    for table in reversed(RLS_TABLES):
        for command in ("delete", "update", "insert", "select"):
            op.execute(f"DROP POLICY IF EXISTS phase5f_{table}_{command}_runtime ON public.{table}")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")

    _replace_functions(hardened=False)
