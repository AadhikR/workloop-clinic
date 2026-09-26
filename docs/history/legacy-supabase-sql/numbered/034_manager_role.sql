-- Migration 034: Allow 'manager' role in user_profiles
-- Feature 6 (Multi-Level Leave Approval) introduced ManagerShell and the 'manager'
-- portal role, but the user_profiles_role_check constraint was never updated to
-- include 'manager'. This caused admin_set_employee_portal_role RPC to silently fail
-- and prevented manager sessions from being created in E2E tests.
--
-- Also updates admin_set_employee_portal_role RPC to accept 'manager'.

-- 1. Drop and recreate the role check constraint
ALTER TABLE user_profiles
  DROP CONSTRAINT IF EXISTS user_profiles_role_check;

ALTER TABLE user_profiles
  ADD CONSTRAINT user_profiles_role_check
  CHECK (role IN ('admin', 'employee', 'manager'));

-- 2. Grant service_role access (required for test suite)
GRANT ALL ON TABLE user_profiles TO service_role;

-- 3. Update the admin_set_employee_portal_role RPC to accept 'manager' role
--    (replace existing RPC that only had 'employee' in its validation)
CREATE OR REPLACE FUNCTION admin_set_employee_portal_role(
  p_employee_id UUID,
  p_role TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_auth_user_id UUID;
BEGIN
  IF p_role NOT IN ('employee', 'manager') THEN
    RAISE EXCEPTION 'Invalid role: must be ''employee'' or ''manager''';
  END IF;

  SELECT auth_user_id INTO v_auth_user_id
  FROM employees
  WHERE id = p_employee_id;

  IF v_auth_user_id IS NULL THEN
    RAISE EXCEPTION 'Employee has not activated their portal yet';
  END IF;

  UPDATE user_profiles
  SET role = p_role
  WHERE user_id = v_auth_user_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'user_profiles row not found for this employee';
  END IF;
END;
$$;
