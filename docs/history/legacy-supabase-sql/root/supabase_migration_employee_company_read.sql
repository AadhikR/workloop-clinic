-- ============================================================
-- Workloop — Allow employees to read their own company record
-- Run in Supabase SQL Editor after the employee auth mapping migration.
-- ============================================================

-- Employees can read the company they belong to (via user_profiles.company_user_id).
CREATE POLICY "employees: read own company"
  ON public.companies FOR SELECT
  USING (
    user_id = (
      SELECT company_user_id
      FROM user_profiles
      WHERE user_id = auth.uid()
    )
  );
