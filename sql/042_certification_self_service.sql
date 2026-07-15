-- 042_certification_self_service.sql
-- Allow employees to submit certifications for HR/manager review.
-- Adds a status column (pending_review, verified, rejected) and employee insert/update policies.

-- 1. Add status column if it doesn't exist
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'certifications' AND column_name = 'status'
  ) THEN
    ALTER TABLE certifications ADD COLUMN status TEXT NOT NULL DEFAULT 'verified';
  END IF;
END $$;

-- 2. Employee can INSERT own certifications (self-submitted start as pending_review)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'certifications_employee_insert' AND tablename = 'certifications') THEN
    CREATE POLICY "certifications_employee_insert"
      ON certifications FOR INSERT TO authenticated
      WITH CHECK (
        employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
      );
  END IF;
END $$;

-- 3. Employee can UPDATE own certifications (edit before verified)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'certifications_employee_update' AND tablename = 'certifications') THEN
    CREATE POLICY "certifications_employee_update"
      ON certifications FOR UPDATE TO authenticated
      USING (
        employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
      )
      WITH CHECK (
        employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
      );
  END IF;
END $$;
