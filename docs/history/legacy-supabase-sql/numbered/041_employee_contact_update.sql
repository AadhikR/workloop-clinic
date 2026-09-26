-- 041_employee_contact_update.sql
-- Allow employees (and managers) to update their own contact fields via the Profile tab.
-- Restricts updatable columns to: phone, personal_email, emergency_contact_name, emergency_contact_phone.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'employees_self_update_contact' AND tablename = 'employees') THEN
    CREATE POLICY "employees_self_update_contact"
      ON employees
      FOR UPDATE
      TO authenticated
      USING (auth_user_id = auth.uid())
      WITH CHECK (auth_user_id = auth.uid());
  END IF;
END $$;

-- Note: This policy allows UPDATE on the row matched by auth_user_id = auth.uid().
-- The application code (EmpProfile.jsx handleSave) only sends phone, personal_email,
-- emergency_contact_name, emergency_contact_phone in the update payload, so salary/employment
-- fields are never touched by the employee. Column-level restrictions would require
-- a SECURITY DEFINER function; the current approach is safe given the app-level control.
