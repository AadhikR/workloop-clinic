-- Feature 3.2: Multi-Level Expense Approvals
-- Adds manager pre-approval step to expense claims:
--   pending → manager_approved → approved → paid
--            → manager_rejected (manager rejects)
--            → rejected (HR/admin rejects at any point)

-- 1. New columns on expense_claims
ALTER TABLE expense_claims
  ADD COLUMN IF NOT EXISTS manager_approved_at       TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS manager_approved_by       TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS manager_rejection_reason  TEXT NOT NULL DEFAULT '';

-- 2. RPC: manager reads all expense claims for their direct reports
DROP FUNCTION IF EXISTS manager_get_expense_queue();
CREATE OR REPLACE FUNCTION manager_get_expense_queue()
RETURNS SETOF expense_claims
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE v_mgr_emp_id UUID;
BEGIN
  SELECT id INTO v_mgr_emp_id
  FROM employees WHERE auth_user_id = auth.uid() AND active = true LIMIT 1;
  IF v_mgr_emp_id IS NULL THEN RETURN; END IF;
  RETURN QUERY
    SELECT ec.* FROM expense_claims ec
    JOIN employees e ON e.id = ec.employee_id
    WHERE e.reporting_manager_id = v_mgr_emp_id
    ORDER BY ec.created_at DESC;
END;
$$;
GRANT EXECUTE ON FUNCTION manager_get_expense_queue() TO authenticated;

-- 3. RPC: manager approves a direct report's pending expense
DROP FUNCTION IF EXISTS manager_approve_expense(UUID);
CREATE OR REPLACE FUNCTION manager_approve_expense(p_expense_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  v_mgr_emp_id UUID;
  v_rows       INT := 0;
BEGIN
  SELECT id INTO v_mgr_emp_id
  FROM employees WHERE auth_user_id = auth.uid() AND active = true LIMIT 1;
  IF v_mgr_emp_id IS NULL THEN RETURN FALSE; END IF;

  UPDATE expense_claims
  SET status              = 'manager_approved',
      manager_approved_at = NOW(),
      manager_approved_by = auth.email()
  WHERE id = p_expense_id
    AND status = 'pending'
    AND employee_id IN (
      SELECT id FROM employees WHERE reporting_manager_id = v_mgr_emp_id
    );
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RETURN v_rows > 0;
END;
$$;
GRANT EXECUTE ON FUNCTION manager_approve_expense(UUID) TO authenticated;

-- 4. RPC: manager rejects a direct report's expense (pending or manager_approved)
DROP FUNCTION IF EXISTS manager_reject_expense(UUID, TEXT);
CREATE OR REPLACE FUNCTION manager_reject_expense(p_expense_id UUID, p_reason TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  v_mgr_emp_id UUID;
  v_rows       INT := 0;
BEGIN
  SELECT id INTO v_mgr_emp_id
  FROM employees WHERE auth_user_id = auth.uid() AND active = true LIMIT 1;
  IF v_mgr_emp_id IS NULL THEN RETURN FALSE; END IF;

  UPDATE expense_claims
  SET status                   = 'manager_rejected',
      manager_rejection_reason = COALESCE(p_reason, ''),
      manager_approved_by      = auth.email()
  WHERE id = p_expense_id
    AND status IN ('pending', 'manager_approved')
    AND employee_id IN (
      SELECT id FROM employees WHERE reporting_manager_id = v_mgr_emp_id
    );
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  RETURN v_rows > 0;
END;
$$;
GRANT EXECUTE ON FUNCTION manager_reject_expense(UUID, TEXT) TO authenticated;

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
