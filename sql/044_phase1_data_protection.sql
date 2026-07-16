-- 044_phase1_data_protection.sql
-- Phase 1: Data protection fixes — duplicate payroll prevention, atomic payroll save,
-- atomic advance repayment, restricted employee self-update.

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1.1  DUPLICATE PAYROLL PREVENTION
-- Prevents two payroll runs for the same period+company by the same admin.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Dry-run check: run this SELECT first to see if existing data would violate the constraint.
-- SELECT user_id, company_id, period, COUNT(*)
-- FROM payroll_runs
-- GROUP BY user_id, company_id, period
-- HAVING COUNT(*) > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_payroll_runs_period
  ON payroll_runs (user_id, COALESCE(company_id, '00000000-0000-0000-0000-000000000000'::uuid), period);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1.2  ATOMIC PAYROLL SAVE (entries replacement)
-- Wraps DELETE + INSERT in a single transaction so a failure mid-way doesn't
-- leave the payroll with zero entries.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION replace_payroll_entries(
  p_payroll_run_id UUID,
  p_entries JSONB
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  -- Delete existing entries
  DELETE FROM payroll_entries WHERE payroll_run_id = p_payroll_run_id;

  -- Insert new entries from the JSONB array
  INSERT INTO payroll_entries (
    payroll_run_id, user_id, employee_id,
    basic_salary, housing_allowance, transport_allowance,
    allowance, increment, bonus, other_pay, du_cost,
    variable_allowance, additional_allowances, deductions,
    excluded, wps_payment_status, wps_rejection_reason
  )
  SELECT
    p_payroll_run_id,
    (entry->>'user_id')::UUID,
    (entry->>'employee_id')::UUID,
    COALESCE((entry->>'basic_salary')::NUMERIC, 0),
    COALESCE((entry->>'housing_allowance')::NUMERIC, 0),
    COALESCE((entry->>'transport_allowance')::NUMERIC, 0),
    COALESCE((entry->>'allowance')::NUMERIC, 0),
    COALESCE((entry->>'increment')::NUMERIC, 0),
    COALESCE((entry->>'bonus')::NUMERIC, 0),
    COALESCE((entry->>'other_pay')::NUMERIC, 0),
    COALESCE((entry->>'du_cost')::NUMERIC, 0),
    COALESCE((entry->>'variable_allowance')::NUMERIC, 0),
    COALESCE((entry->'additional_allowances')::JSONB, '[]'::JSONB),
    COALESCE((entry->'deductions')::JSONB, '[]'::JSONB),
    COALESCE((entry->>'excluded')::BOOLEAN, false),
    COALESCE(entry->>'wps_payment_status', 'pending'),
    COALESCE(entry->>'wps_rejection_reason', '')
  FROM jsonb_array_elements(p_entries) AS entry;
END;
$$;

GRANT EXECUTE ON FUNCTION replace_payroll_entries(UUID, JSONB) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1.3  ATOMIC ADVANCE REPAYMENT
-- Inserts repayment row + decrements outstanding_balance in one transaction.
-- Auto-sets status to 'settled' when balance hits zero.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION record_advance_repayment(
  p_advance_id UUID,
  p_payroll_run_id UUID,
  p_amount NUMERIC,
  p_paid_date DATE DEFAULT CURRENT_DATE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_new_balance NUMERIC;
  v_new_status TEXT;
  v_repayment_id UUID;
BEGIN
  -- Insert the repayment record
  INSERT INTO advance_repayments (advance_id, payroll_run_id, amount, paid_date)
  VALUES (p_advance_id, p_payroll_run_id, p_amount, p_paid_date)
  RETURNING id INTO v_repayment_id;

  -- Atomically update the parent advance balance
  UPDATE salary_advances
  SET outstanding_balance = GREATEST(0, outstanding_balance - p_amount),
      status = CASE
        WHEN GREATEST(0, outstanding_balance - p_amount) <= 0 THEN 'settled'
        ELSE 'active'
      END
  WHERE id = p_advance_id
  RETURNING outstanding_balance, status INTO v_new_balance, v_new_status;

  RETURN jsonb_build_object(
    'repaymentId', v_repayment_id,
    'newBalance', v_new_balance,
    'newStatus', v_new_status
  );
END;
$$;

GRANT EXECUTE ON FUNCTION record_advance_repayment(UUID, UUID, NUMERIC, DATE) TO authenticated;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 1.4  RESTRICTED EMPLOYEE SELF-UPDATE
-- Replace the broad UPDATE policy with a SECURITY DEFINER function that only
-- allows employees to update their contact columns.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Drop the old broad policy
DROP POLICY IF EXISTS "employees_self_update_contact" ON employees;

CREATE OR REPLACE FUNCTION employee_update_contact(
  p_phone TEXT DEFAULT NULL,
  p_personal_email TEXT DEFAULT NULL,
  p_emergency_contact_name TEXT DEFAULT NULL,
  p_emergency_contact_phone TEXT DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  UPDATE employees
  SET phone                  = COALESCE(p_phone, phone),
      personal_email         = COALESCE(p_personal_email, personal_email),
      emergency_contact_name  = COALESCE(p_emergency_contact_name, emergency_contact_name),
      emergency_contact_phone = COALESCE(p_emergency_contact_phone, emergency_contact_phone)
  WHERE auth_user_id = auth.uid();

  IF NOT FOUND THEN
    RAISE EXCEPTION 'No employee record linked to current user';
  END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_update_contact(TEXT, TEXT, TEXT, TEXT) TO authenticated;
