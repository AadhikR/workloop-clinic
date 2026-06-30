-- 035_manager_employee_read.sql
-- Allow managers to read their direct reports' employee records.
-- IMPORTANT: A plain subquery on employees inside an employees RLS policy causes
-- infinite recursion. Fix: use a SECURITY DEFINER helper that bypasses RLS
-- for the inner lookup, breaking the recursion chain.

-- Lookup helper — runs as owner (SECURITY DEFINER), so it reads employees without
-- applying RLS. Safe because auth_user_id is globally unique per portal account.
CREATE OR REPLACE FUNCTION get_manager_employee_id()
RETURNS UUID
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT id FROM employees WHERE auth_user_id = auth.uid() LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION get_manager_employee_id() TO authenticated;

-- Policy: managers can SELECT their direct reports' employee rows
DROP POLICY IF EXISTS "employees_manager_read" ON employees;
CREATE POLICY "employees_manager_read" ON employees
  FOR SELECT USING (
    reporting_manager_id = get_manager_employee_id()
  );

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
