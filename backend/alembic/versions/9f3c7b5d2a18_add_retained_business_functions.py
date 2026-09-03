"""Add the three retained PostgreSQL business functions.

Revision ID: 9f3c7b5d2a18
Revises: 8e2b6a4c1f07
Created: 2026-09-03 00:00:00.000000

Phase 4D, part 2 of 3. Implements the three business functions the approved
Phase 4A catalogue keeps in PostgreSQL, to their exact target signatures and
behavior: ``replace_payroll_entries``, ``record_advance_repayment``, and
``admin_execute_shift_swap``. Each is SECURITY DEFINER with a pinned
``search_path`` and has its default PUBLIC execute privilege revoked; the
execute grant to ``workloop_runtime`` is added in the grant revision that
follows. None of them read a Supabase-era session identity or role helper: the
caller's identity arrives as an explicit ``app_users`` argument and every
ownership column derives from locked rows, not from a session role. No grant or
business table is added here.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9f3c7b5d2a18"
down_revision: str | Sequence[str] | None = "8e2b6a4c1f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REPLACE_PAYROLL_ENTRIES = r"""
CREATE FUNCTION replace_payroll_entries(p_payroll_run_id uuid, p_entries jsonb)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public
AS $$
DECLARE
  v_run          payroll_runs%ROWTYPE;
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
  IF p_entries IS NULL OR jsonb_typeof(p_entries) <> 'array' THEN
    RAISE EXCEPTION 'replace_payroll_entries_requires_array';
  END IF;

  SELECT * INTO v_run FROM payroll_runs WHERE id = p_payroll_run_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'payroll_run_not_found';
  END IF;
  IF v_run.status <> 'draft' OR v_run.approval_status <> 'draft' THEN
    RAISE EXCEPTION 'payroll_run_not_draft';
  END IF;

  FOR v_entry IN SELECT * FROM jsonb_array_elements(p_entries)
  LOOP
    IF jsonb_typeof(v_entry) <> 'object' THEN
      RAISE EXCEPTION 'payroll_entry_not_object';
    END IF;

    -- Reject any key outside the exact allowed set.
    FOR v_key IN SELECT jsonb_object_keys(v_entry)
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
    v_emp_ids := array_append(v_emp_ids, v_emp);

    -- Validate every scalar money value: finite, scale <= 2, |v| <= 10 digits,
    -- and non-negative for every fixed scalar except variable_allowance.
    FOREACH v_key IN ARRAY v_scalar_keys
    LOOP
      IF v_entry ? v_key AND jsonb_typeof(v_entry->v_key) <> 'null' THEN
        IF jsonb_typeof(v_entry->v_key) <> 'number' THEN
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
      IF scale(v_val) > 2 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_scale: %', v_key;
      END IF;
      IF abs(v_val) > 9999999999.99 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_range: %', v_key;
      END IF;
      IF v_key <> 'variable_allowance' AND v_val < 0 THEN
        RAISE EXCEPTION 'payroll_entry_scalar_negative: %', v_key;
      END IF;
    END LOOP;

    -- The JSON adjustment arrays are validated field by field in FastAPI; here
    -- only their JSON type is enforced when present.
    IF v_entry ? 'additional_allowances'
       AND jsonb_typeof(v_entry->'additional_allowances') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_additional_allowances_not_array';
    END IF;
    IF v_entry ? 'deductions'
       AND jsonb_typeof(v_entry->'deductions') NOT IN ('array', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_deductions_not_array';
    END IF;
    IF v_entry ? 'excluded'
       AND jsonb_typeof(v_entry->'excluded') NOT IN ('boolean', 'null') THEN
      RAISE EXCEPTION 'payroll_entry_excluded_not_boolean';
    END IF;
  END LOOP;

  -- Every employee must belong to the run's own company and branch scope.
  IF EXISTS (
    SELECT 1 FROM unnest(v_emp_ids) AS candidate(id)
    WHERE NOT EXISTS (
      SELECT 1 FROM employees e
      WHERE e.id = candidate.id
        AND e.company_id = v_run.company_id
        AND e.branch_id = v_run.branch_id
    )
  ) THEN
    RAISE EXCEPTION 'payroll_entry_employee_out_of_scope';
  END IF;

  -- Delete and replace only this draft run's entries, in one transaction.
  DELETE FROM payroll_entries WHERE payroll_run_id = p_payroll_run_id;

  INSERT INTO payroll_entries (
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
    CASE WHEN jsonb_typeof(entry->'additional_allowances') = 'array'
      THEN entry->'additional_allowances' ELSE '[]'::jsonb END,
    CASE WHEN jsonb_typeof(entry->'deductions') = 'array'
      THEN entry->'deductions' ELSE '[]'::jsonb END,
    COALESCE((entry->>'excluded')::boolean, false),
    COALESCE(entry->>'wps_payment_status', 'pending'),
    COALESCE(entry->>'wps_rejection_reason', '')
  FROM jsonb_array_elements(p_entries) AS entry;
END;
$$;
"""


RECORD_ADVANCE_REPAYMENT = r"""
CREATE FUNCTION record_advance_repayment(
  p_advance_id uuid,
  p_payroll_run_id uuid,
  p_idempotency_key uuid,
  p_amount numeric,
  p_paid_date date DEFAULT current_date)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public
AS $$
DECLARE
  v_advance    salary_advances%ROWTYPE;
  v_existing   advance_repayments%ROWTYPE;
  v_run_co     uuid;
  v_run_br     uuid;
  v_amount     numeric;
  v_paid_date  date;
  v_new_bal    numeric;
  v_new_status text;
  v_repay_id   uuid;
BEGIN
  IF p_advance_id IS NULL OR p_idempotency_key IS NULL THEN
    RAISE EXCEPTION 'advance_repayment_missing_key';
  END IF;

  v_paid_date := p_paid_date;
  IF v_paid_date IS NULL THEN
    RAISE EXCEPTION 'advance_repayment_missing_paid_date';
  END IF;

  -- Normalize amount without rounding; the argument carries no typmod, so the
  -- scale and range are enforced here, not by the parameter type.
  v_amount := p_amount;
  IF v_amount IS NULL
     OR v_amount = 'NaN'::numeric
     OR v_amount = 'Infinity'::numeric
     OR v_amount = '-Infinity'::numeric THEN
    RAISE EXCEPTION 'advance_repayment_amount_not_finite';
  END IF;
  IF scale(v_amount) > 2 THEN
    RAISE EXCEPTION 'advance_repayment_amount_scale';
  END IF;
  IF v_amount <= 0 OR v_amount > 9999999999.99 THEN
    RAISE EXCEPTION 'advance_repayment_amount_range';
  END IF;

  SELECT * INTO v_advance FROM salary_advances WHERE id = p_advance_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'advance_repayment_advance_not_found';
  END IF;

  -- Replay check by request key, before any state or balance check.
  SELECT * INTO v_existing
  FROM advance_repayments
  WHERE advance_id = p_advance_id AND idempotency_key = p_idempotency_key;
  IF FOUND THEN
    IF v_existing.advance_id = p_advance_id
       AND v_existing.payroll_run_id IS NOT DISTINCT FROM p_payroll_run_id
       AND v_existing.amount = v_amount
       AND v_existing.paid_date = v_paid_date
       AND v_existing.company_id = v_advance.company_id
       AND v_existing.branch_id = v_advance.branch_id THEN
      RETURN jsonb_build_object(
        'repaymentId', v_existing.id,
        'newBalance', v_advance.outstanding_balance,
        'newStatus', v_advance.status,
        'alreadyRecorded', true);
    END IF;
    RAISE EXCEPTION 'advance_repayment_idempotency_conflict';
  END IF;

  -- No key row: if a run was supplied, a row for that run under any other key
  -- or a different normalized request is a conflict.
  IF p_payroll_run_id IS NOT NULL THEN
    SELECT * INTO v_existing
    FROM advance_repayments
    WHERE advance_id = p_advance_id AND payroll_run_id = p_payroll_run_id;
    IF FOUND THEN
      RAISE EXCEPTION 'advance_repayment_payroll_conflict';
    END IF;
  END IF;

  -- Both replay checks passed. Require an active advance with a positive balance.
  IF v_advance.status <> 'active' OR v_advance.outstanding_balance <= 0 THEN
    RAISE EXCEPTION 'advance_repayment_not_active';
  END IF;

  -- An optional run must share the locked advance's company and branch.
  IF p_payroll_run_id IS NOT NULL THEN
    SELECT company_id, branch_id INTO v_run_co, v_run_br
    FROM payroll_runs WHERE id = p_payroll_run_id;
    IF NOT FOUND
       OR v_run_co <> v_advance.company_id
       OR v_run_br <> v_advance.branch_id THEN
      RAISE EXCEPTION 'advance_repayment_payroll_scope';
    END IF;
  END IF;

  IF v_amount > v_advance.outstanding_balance THEN
    RAISE EXCEPTION 'advance_repayment_exceeds_outstanding';
  END IF;

  INSERT INTO advance_repayments (
    company_id, branch_id, advance_id, payroll_run_id,
    idempotency_key, amount, paid_date)
  VALUES (
    v_advance.company_id, v_advance.branch_id, p_advance_id, p_payroll_run_id,
    p_idempotency_key, v_amount, v_paid_date)
  RETURNING id INTO v_repay_id;

  UPDATE salary_advances
  SET outstanding_balance = outstanding_balance - v_amount,
      status = CASE WHEN outstanding_balance - v_amount <= 0 THEN 'settled' ELSE 'active' END
  WHERE id = p_advance_id
  RETURNING outstanding_balance, status INTO v_new_bal, v_new_status;

  RETURN jsonb_build_object(
    'repaymentId', v_repay_id,
    'newBalance', v_new_bal,
    'newStatus', v_new_status,
    'alreadyRecorded', false);
END;
$$;
"""


ADMIN_EXECUTE_SHIFT_SWAP = r"""
CREATE FUNCTION admin_execute_shift_swap(p_swap_id uuid, p_actor_app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO public
AS $$
DECLARE
  v_swap    shift_swap_requests%ROWTYPE;
  v_req_id  uuid;
  v_tgt_id  uuid;
  v_first   uuid;
  v_second  uuid;
BEGIN
  SELECT * INTO v_swap FROM shift_swap_requests WHERE id = p_swap_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'shift_swap_not_found';
  END IF;
  IF v_swap.status <> 'pending' THEN
    RAISE EXCEPTION 'shift_swap_not_pending';
  END IF;

  -- The actor must be an active admin of the swap's own company.
  IF NOT EXISTS (
    SELECT 1
    FROM user_profiles up
    JOIN app_users au ON au.id = up.app_user_id
    WHERE up.app_user_id = p_actor_app_user_id
      AND up.company_id = v_swap.company_id
      AND up.role = 'admin'
      AND au.status = 'active'
  ) THEN
    RAISE EXCEPTION 'shift_swap_forbidden';
  END IF;

  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN
    RAISE EXCEPTION 'shift_swap_same_employee';
  END IF;

  SELECT id INTO v_req_id
  FROM roster_assignments
  WHERE employee_id = v_swap.requester_employee_id
    AND date = v_swap.requester_date
    AND company_id = v_swap.company_id
    AND branch_id = v_swap.branch_id;
  IF v_req_id IS NULL THEN
    RAISE EXCEPTION 'shift_swap_requester_unassigned';
  END IF;

  IF v_swap.target_date IS NOT NULL THEN
    IF v_swap.requester_date = v_swap.target_date THEN
      RAISE EXCEPTION 'shift_swap_same_day';
    END IF;

    SELECT id INTO v_tgt_id
    FROM roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date = v_swap.target_date
      AND company_id = v_swap.company_id
      AND branch_id = v_swap.branch_id;
    IF v_tgt_id IS NULL THEN
      RAISE EXCEPTION 'shift_swap_target_unassigned';
    END IF;

    IF EXISTS (
      SELECT 1 FROM roster_assignments
      WHERE company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
        AND (
          (employee_id = v_swap.target_employee_id
             AND date = v_swap.requester_date AND id <> v_req_id)
          OR (employee_id = v_swap.requester_employee_id
             AND date = v_swap.target_date AND id <> v_tgt_id))
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    -- Lock both roster rows in ascending id order to avoid deadlocks between
    -- concurrent executions that touch overlapping roster rows.
    IF v_req_id < v_tgt_id THEN
      v_first := v_req_id; v_second := v_tgt_id;
    ELSE
      v_first := v_tgt_id; v_second := v_req_id;
    END IF;
    PERFORM 1 FROM roster_assignments WHERE id = v_first FOR UPDATE;
    PERFORM 1 FROM roster_assignments WHERE id = v_second FOR UPDATE;

    UPDATE roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
    UPDATE roster_assignments SET employee_id = v_swap.requester_employee_id
      WHERE id = v_tgt_id;
  ELSE
    IF EXISTS (
      SELECT 1 FROM roster_assignments
      WHERE employee_id = v_swap.target_employee_id
        AND date = v_swap.requester_date
        AND company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    PERFORM 1 FROM roster_assignments WHERE id = v_req_id FOR UPDATE;
    UPDATE roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
  END IF;

  UPDATE shift_swap_requests
  SET status = 'approved',
      admin_approved_at = now(),
      admin_approved_by_app_user_id = p_actor_app_user_id,
      rejection_reason = ''
  WHERE id = p_swap_id;

  RETURN true;
END;
$$;
"""


FUNCTION_SIGNATURES: tuple[str, ...] = (
    "replace_payroll_entries(uuid, jsonb)",
    "record_advance_repayment(uuid, uuid, uuid, numeric, date)",
    "admin_execute_shift_swap(uuid, uuid)",
)


def upgrade() -> None:
    op.execute(REPLACE_PAYROLL_ENTRIES)
    op.execute(RECORD_ADVANCE_REPAYMENT)
    op.execute(ADMIN_EXECUTE_SHIFT_SWAP)
    # Each function is internal and callable only through the reviewed runtime
    # grant added in the next revision. Remove the default PUBLIC execute grant.
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"REVOKE EXECUTE ON FUNCTION {signature} FROM PUBLIC")


def downgrade() -> None:
    for signature in FUNCTION_SIGNATURES:
        op.execute(f"DROP FUNCTION {signature}")
