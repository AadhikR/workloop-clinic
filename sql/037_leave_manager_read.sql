-- 037_leave_manager_read.sql
-- Adds RLS policies so managers can read their direct reports' leave data.
-- Required for ManagerLeaveQueue to show pending leave requests.
--
-- Direct reports = employees whose reporting_manager_id matches an employee
-- record with auth_user_id = auth.uid() (the signed-in manager).

-- ── leave_requests: manager can SELECT direct reports' requests ──────────────
CREATE POLICY leave_requests_manager_read ON leave_requests
  FOR SELECT USING (
    employee_id IN (
      SELECT id FROM employees
      WHERE reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

-- ── leave_balances: manager can SELECT direct reports' balances ──────────────
CREATE POLICY leave_balances_manager_read ON leave_balances
  FOR SELECT USING (
    employee_id IN (
      SELECT id FROM employees
      WHERE reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

-- ── leave_types: employee/manager can read active leave types ────────────────
-- Without this, getLeaveTypes() returns [] for non-admin users,
-- and EmpLeave falls back to hardcoded DEFAULT_LEAVE_TYPES.
CREATE POLICY leave_types_authenticated_read ON leave_types
  FOR SELECT USING (true);
