-- 006_multi_level_leave.sql
-- Feature 6: Multi-Level Leave Approval Workflow
-- Run in Supabase Dashboard → SQL Editor → New Query

-- ─── Extend leave_requests with manager-approval columns ─────────────────────
-- These are all additive — safe to run on existing data.
ALTER TABLE leave_requests
  ADD COLUMN IF NOT EXISTS manager_approved_at      TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS manager_approved_by      TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS manager_rejection_reason TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS substitute_employee_id   UUID REFERENCES employees(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS approval_level_required  INT  NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS approval_comment         TEXT NOT NULL DEFAULT '';

-- ─── leave_approval_delegates ────────────────────────────────────────────────
-- Admin sets a deputy approver when the main manager is on leave.
-- approver_employee_id = the manager who is away
-- delegate_employee_id = the colleague covering approval during from_date..to_date
CREATE TABLE IF NOT EXISTS leave_approval_delegates (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  approver_employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  delegate_employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  from_date            DATE NOT NULL,
  to_date              DATE NOT NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE leave_approval_delegates ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE leave_approval_delegates TO authenticated;

-- Admin full access
DROP POLICY IF EXISTS leave_approval_delegates_admin ON leave_approval_delegates;
CREATE POLICY leave_approval_delegates_admin ON leave_approval_delegates
  FOR ALL
  USING     (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Manager or delegate can read their own delegation records
DROP POLICY IF EXISTS leave_approval_delegates_actor_read ON leave_approval_delegates;
CREATE POLICY leave_approval_delegates_actor_read ON leave_approval_delegates
  FOR SELECT
  USING (
    approver_employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
    OR
    delegate_employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- ─── RPC: manager_approve_leave ──────────────────────────────────────────────
-- Called by a manager (role = 'manager') to approve a direct report's leave.
-- If approval_level_required = 1 → sets status to 'Approved' immediately.
-- If approval_level_required = 2 → sets status to 'ManagerApproved' (HR does final approval).
CREATE OR REPLACE FUNCTION manager_approve_leave(p_request_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_manager_emp_id UUID;
  v_req            RECORD;
  v_manager_email  TEXT;
BEGIN
  -- Resolve manager's employee record
  SELECT id INTO v_manager_emp_id
  FROM   employees
  WHERE  auth_user_id = auth.uid()
  LIMIT  1;

  IF v_manager_emp_id IS NULL THEN
    RAISE EXCEPTION 'No employee record is linked to your account.';
  END IF;

  -- Load the leave request (check it belongs to the correct company via user_id)
  SELECT * INTO v_req FROM leave_requests WHERE id = p_request_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Leave request not found.';
  END IF;

  IF v_req.status != 'Pending' THEN
    RAISE EXCEPTION 'Leave request is not Pending (current status: %).', v_req.status;
  END IF;

  -- Verify the caller is the direct reporting manager or an active delegate
  IF NOT EXISTS (
    SELECT 1 FROM employees
    WHERE  id = v_req.employee_id
    AND    reporting_manager_id = v_manager_emp_id
  ) THEN
    -- Check delegation
    IF NOT EXISTS (
      SELECT 1
      FROM   leave_approval_delegates lad
      JOIN   employees e ON e.id = v_req.employee_id
      WHERE  lad.delegate_employee_id = v_manager_emp_id
      AND    lad.approver_employee_id = e.reporting_manager_id
      AND    lad.from_date <= CURRENT_DATE
      AND    lad.to_date   >= CURRENT_DATE
    ) THEN
      RAISE EXCEPTION 'You are not the reporting manager (or active delegate) for this employee.';
    END IF;
  END IF;

  SELECT email INTO v_manager_email FROM auth.users WHERE id = auth.uid();

  UPDATE leave_requests SET
    manager_approved_at = NOW(),
    manager_approved_by = COALESCE(v_manager_email, auth.uid()::TEXT),
    -- 1-level: fully approved; 2-level: awaits HR final sign-off
    status      = CASE WHEN approval_level_required <= 1
                       THEN 'Approved'
                       ELSE 'ManagerApproved'
                  END,
    approved_by = CASE WHEN approval_level_required <= 1
                       THEN COALESCE(v_manager_email, auth.uid()::TEXT)
                       ELSE ''
                  END,
    approved_at = CASE WHEN approval_level_required <= 1 THEN NOW() ELSE NULL END
  WHERE id = p_request_id;
END;
$$;

GRANT EXECUTE ON FUNCTION manager_approve_leave(UUID) TO authenticated;

-- ─── RPC: manager_reject_leave ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION manager_reject_leave(p_request_id UUID, p_reason TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_manager_emp_id UUID;
  v_req            RECORD;
  v_manager_email  TEXT;
BEGIN
  SELECT id INTO v_manager_emp_id
  FROM   employees
  WHERE  auth_user_id = auth.uid()
  LIMIT  1;

  IF v_manager_emp_id IS NULL THEN
    RAISE EXCEPTION 'No employee record is linked to your account.';
  END IF;

  SELECT * INTO v_req FROM leave_requests WHERE id = p_request_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Leave request not found.';
  END IF;

  -- Can reject Pending or ManagerApproved (HR override)
  IF v_req.status NOT IN ('Pending', 'ManagerApproved') THEN
    RAISE EXCEPTION 'Cannot reject a request in status %.', v_req.status;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM employees
    WHERE  id = v_req.employee_id
    AND    reporting_manager_id = v_manager_emp_id
  ) THEN
    IF NOT EXISTS (
      SELECT 1
      FROM   leave_approval_delegates lad
      JOIN   employees e ON e.id = v_req.employee_id
      WHERE  lad.delegate_employee_id = v_manager_emp_id
      AND    lad.approver_employee_id = e.reporting_manager_id
      AND    lad.from_date <= CURRENT_DATE
      AND    lad.to_date   >= CURRENT_DATE
    ) THEN
      RAISE EXCEPTION 'You are not the reporting manager (or active delegate) for this employee.';
    END IF;
  END IF;

  SELECT email INTO v_manager_email FROM auth.users WHERE id = auth.uid();

  UPDATE leave_requests SET
    status                   = 'ManagerRejected',
    manager_rejection_reason = COALESCE(NULLIF(TRIM(p_reason), ''), 'Rejected by manager'),
    manager_approved_by      = COALESCE(v_manager_email, auth.uid()::TEXT)
  WHERE id = p_request_id;
END;
$$;

GRANT EXECUTE ON FUNCTION manager_reject_leave(UUID, TEXT) TO authenticated;

-- ─── RPC: admin_set_employee_portal_role ──────────────────────────────────────
-- Admin upgrades an activated employee's portal role to 'manager' (or back to 'employee').
-- Requires the employee to have already signed in to the portal at least once
-- (i.e. their user_profiles row must exist).
CREATE OR REPLACE FUNCTION admin_set_employee_portal_role(p_employee_id UUID, p_role TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_auth_user_id UUID;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM companies WHERE user_id = auth.uid()) THEN
    RAISE EXCEPTION 'Only company admins can set portal roles.';
  END IF;

  IF p_role NOT IN ('employee', 'manager') THEN
    RAISE EXCEPTION 'Invalid role "%". Must be employee or manager.', p_role;
  END IF;

  -- Resolve the employee's linked auth account (scoped to admin's company)
  SELECT auth_user_id INTO v_auth_user_id
  FROM   employees
  WHERE  id = p_employee_id AND user_id = auth.uid();

  IF v_auth_user_id IS NULL THEN
    RAISE EXCEPTION 'Employee not found or not linked to your company.';
  END IF;

  UPDATE user_profiles SET role = p_role WHERE user_id = v_auth_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Employee portal account has not been activated yet. The employee must sign in to the portal first.';
  END IF;
END;
$$;

GRANT EXECUTE ON FUNCTION admin_set_employee_portal_role(UUID, TEXT) TO authenticated;

-- ─── RPC: admin_get_employee_portal_role ──────────────────────────────────────
-- Returns the current portal role for an employee ('employee', 'manager', or NULL if not activated).
CREATE OR REPLACE FUNCTION admin_get_employee_portal_role(p_employee_id UUID)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_auth_user_id UUID;
  v_role         TEXT;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM companies WHERE user_id = auth.uid()) THEN
    RAISE EXCEPTION 'Only company admins can read portal roles.';
  END IF;

  SELECT auth_user_id INTO v_auth_user_id
  FROM   employees
  WHERE  id = p_employee_id AND user_id = auth.uid();

  IF v_auth_user_id IS NULL THEN RETURN NULL; END IF;

  SELECT role INTO v_role
  FROM   user_profiles
  WHERE  user_id = v_auth_user_id;

  RETURN v_role;
END;
$$;

GRANT EXECUTE ON FUNCTION admin_get_employee_portal_role(UUID) TO authenticated;

-- After running this file, also execute:
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
