-- 040_training_manager_policies.sql
-- Allow managers to CRUD training records and certifications for their direct reports.
-- Also allow employees to INSERT their own training records (self-enrollment).
-- Uses get_manager_employee_id() from migration 035.

-- ── Manager policies: training_records ──────────────────────────────────────

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'training_records_manager_all' AND tablename = 'training_records') THEN
    CREATE POLICY "training_records_manager_all"
      ON training_records FOR ALL
      USING (
        employee_id IN (
          SELECT id FROM employees WHERE reporting_manager_id = get_manager_employee_id()
        )
      )
      WITH CHECK (
        employee_id IN (
          SELECT id FROM employees WHERE reporting_manager_id = get_manager_employee_id()
        )
      );
  END IF;
END $$;

-- ── Manager policies: certifications ────────────────────────────────────────

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'certifications_manager_all' AND tablename = 'certifications') THEN
    CREATE POLICY "certifications_manager_all"
      ON certifications FOR ALL
      USING (
        employee_id IN (
          SELECT id FROM employees WHERE reporting_manager_id = get_manager_employee_id()
        )
      )
      WITH CHECK (
        employee_id IN (
          SELECT id FROM employees WHERE reporting_manager_id = get_manager_employee_id()
        )
      );
  END IF;
END $$;

-- ── Employee self-insert: training_records (request training) ───────────────

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'training_records_employee_insert' AND tablename = 'training_records') THEN
    CREATE POLICY "training_records_employee_insert"
      ON training_records FOR INSERT
      WITH CHECK (
        employee_id IN (
          SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
      );
  END IF;
END $$;

-- ── Employee self-update: training_records (update own status/cert URL) ─────

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'training_records_employee_update' AND tablename = 'training_records') THEN
    CREATE POLICY "training_records_employee_update"
      ON training_records FOR UPDATE
      USING (
        employee_id IN (
          SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
      )
      WITH CHECK (
        employee_id IN (
          SELECT id FROM employees WHERE auth_user_id = auth.uid()
        )
      );
  END IF;
END $$;

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
