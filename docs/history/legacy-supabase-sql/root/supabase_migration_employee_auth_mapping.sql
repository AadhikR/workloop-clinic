-- ============================================================
-- Workloop — Employee ↔ Auth User Mapping
-- Run this in the Supabase SQL editor (Dashboard → SQL Editor)
-- ============================================================

-- 1. Add auth_user_id to employees
--    Nullable so existing rows are unaffected.
--    Unique so one Supabase account links to exactly one employee.
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS auth_user_id UUID UNIQUE REFERENCES auth.users(id);


-- 2. Create user_profiles table
--    One row per Supabase auth user.
--    role:            'admin' (HR) or 'employee'
--    company_user_id: the admin's auth.uid() that owns the company data
--    employee_id:     FK to employees (null for admin users)
CREATE TABLE IF NOT EXISTS user_profiles (
  user_id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role            TEXT NOT NULL DEFAULT 'admin'
                    CHECK (role IN ('admin', 'employee')),
  company_user_id UUID NOT NULL,
  employee_id     UUID REFERENCES employees(id) ON DELETE SET NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Users can read and write only their own profile row
CREATE POLICY "user_profiles: read own"
  ON user_profiles FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "user_profiles: insert own"
  ON user_profiles FOR INSERT
  WITH CHECK (user_id = auth.uid());


-- 3. New RLS policy on employees
--    Allows a linked employee to read their own record.
--    The existing admin policy (user_id = auth.uid()) is unchanged.
CREATE POLICY "employees: read own via auth_user_id"
  ON employees FOR SELECT
  USING (auth_user_id = auth.uid());


-- 4. SECURITY DEFINER function: link_employee_account()
--    Called by the frontend on the employee's first login.
--    Matches auth.email() against employees.work_email,
--    writes auth_user_id back to the employee row,
--    and inserts the user_profiles row.
--    SECURITY DEFINER means it runs as the DB owner and bypasses RLS.
CREATE OR REPLACE FUNCTION link_employee_account()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_uid   UUID := auth.uid();
  v_email TEXT := auth.email();
  v_emp   employees%ROWTYPE;
BEGIN

  -- Already linked? Return existing mapping.
  SELECT * INTO v_emp
  FROM employees
  WHERE auth_user_id = v_uid
  LIMIT 1;

  IF FOUND THEN
    RETURN json_build_object(
      'success',         true,
      'already_linked',  true,
      'employee_id',     v_emp.id,
      'company_user_id', v_emp.user_id,
      'employee_name',   v_emp.name
    );
  END IF;

  -- Find an unlinked employee whose work_email matches the signed-in user's email.
  SELECT * INTO v_emp
  FROM employees
  WHERE work_email = v_email
    AND auth_user_id IS NULL
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN json_build_object(
      'success', false,
      'error',   'no_match'
    );
  END IF;

  -- Write the link onto the employee row.
  UPDATE employees
  SET auth_user_id = v_uid
  WHERE id = v_emp.id;

  -- Insert (or repair) the profile row.
  INSERT INTO user_profiles (user_id, role, company_user_id, employee_id)
  VALUES (v_uid, 'employee', v_emp.user_id, v_emp.id)
  ON CONFLICT (user_id) DO UPDATE
    SET role            = 'employee',
        company_user_id = v_emp.user_id,
        employee_id     = v_emp.id;

  RETURN json_build_object(
    'success',         true,
    'already_linked',  false,
    'employee_id',     v_emp.id,
    'company_user_id', v_emp.user_id,
    'employee_name',   v_emp.name
  );

END;
$$;
