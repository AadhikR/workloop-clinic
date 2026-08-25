-- 051_employee_request_actions.sql
-- Reliable employee-side withdrawal/deletion for pending requests.
-- Idempotent: safe to run repeatedly in Supabase SQL Editor.

-- The migration-049 version returned TABLE(id, status, rejection_reason).
-- Those output variable names conflicted with the unqualified columns in its
-- UPDATE ... RETURNING clause on PostgreSQL. Return a simple boolean instead.
DROP FUNCTION IF EXISTS employee_cancel_advance(UUID);

CREATE OR REPLACE FUNCTION employee_cancel_advance(p_advance_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_rows INTEGER := 0;
BEGIN
  UPDATE salary_advances AS advance
     SET status = 'cancelled',
         rejection_reason = COALESCE(NULLIF(advance.rejection_reason, ''), 'Withdrawn by employee')
   WHERE advance.id = p_advance_id
     AND advance.status = 'pending'
     AND advance.employee_id IN (
       SELECT employee.id
       FROM employees AS employee
       WHERE employee.auth_user_id = auth.uid()
     );

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  IF v_rows = 0 THEN
    RAISE EXCEPTION 'Request not found, already actioned, or not owned by this employee.';
  END IF;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION employee_cancel_advance(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION employee_cancel_advance(UUID) TO authenticated;

-- Employees may permanently remove only their own claims that have not entered
-- an approval/payment workflow, or claims that were rejected. Manager-approved,
-- HR-approved, and paid claims are retained as payroll/audit records.
CREATE OR REPLACE FUNCTION employee_delete_expense(p_expense_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_rows INTEGER := 0;
BEGIN
  DELETE FROM expense_claims AS claim
   WHERE claim.id = p_expense_id
     AND claim.status IN ('pending', 'rejected', 'manager_rejected')
     AND claim.employee_id IN (
       SELECT employee.id
       FROM employees AS employee
       WHERE employee.auth_user_id = auth.uid()
     );

  GET DIAGNOSTICS v_rows = ROW_COUNT;
  IF v_rows = 0 THEN
    RAISE EXCEPTION 'Claim not found, already actioned, or not owned by this employee.';
  END IF;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION employee_delete_expense(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION employee_delete_expense(UUID) TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;