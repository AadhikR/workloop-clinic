-- ============================================================
-- Workloop — Table-level grants for authenticated users
-- Postgres checks grants BEFORE RLS policies. Tables created via
-- SQL editor need explicit grants or subqueries in RLS policies fail.
-- Run this in Supabase SQL Editor.
-- ============================================================

-- Tables created in supabase_migration_employee_auth_mapping.sql
GRANT SELECT, INSERT, UPDATE        ON user_profiles        TO authenticated;

-- Tables created in supabase_migration_payslips.sql
GRANT SELECT, INSERT, UPDATE        ON payslips             TO authenticated;

-- ── Fix the companies employee-read policy ─────────────────────────────────
-- The original policy subqueried user_profiles, which caused "permission denied"
-- when admins updated their company. Rewrite it to use the employees table instead.

DROP POLICY IF EXISTS "employees: read own company" ON public.companies;

CREATE POLICY "employees: read own company"
  ON public.companies FOR SELECT
  USING (
    user_id IN (
      SELECT user_id FROM employees WHERE auth_user_id = auth.uid()
    )
  );
