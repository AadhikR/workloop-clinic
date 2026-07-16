-- 045_core_rls_baseline.sql
-- Baseline RLS policies for core tables that were created outside numbered migrations.
-- This documents the expected state and ensures new environments match production.
-- All statements are idempotent (IF NOT EXISTS / DO $$ guards).

-- ═══════════════════════════════════════════════════════════════════════════════
-- COMPANIES
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'companies_owner_all' AND tablename = 'companies') THEN
    CREATE POLICY "companies_owner_all"
      ON companies FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- USER_PROFILES
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'user_profiles_owner_all' AND tablename = 'user_profiles') THEN
    CREATE POLICY "user_profiles_owner_all"
      ON user_profiles FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- EMPLOYEES
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE employees ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'employees_owner_all' AND tablename = 'employees') THEN
    CREATE POLICY "employees_owner_all"
      ON employees FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- Employee self-read (portal)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'employees_self_read' AND tablename = 'employees') THEN
    CREATE POLICY "employees_self_read"
      ON employees FOR SELECT TO authenticated
      USING (auth_user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAYROLL_RUNS
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE payroll_runs ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'payroll_runs_owner_all' AND tablename = 'payroll_runs') THEN
    CREATE POLICY "payroll_runs_owner_all"
      ON payroll_runs FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAYROLL_ENTRIES
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE payroll_entries ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'payroll_entries_owner_all' AND tablename = 'payroll_entries') THEN
    CREATE POLICY "payroll_entries_owner_all"
      ON payroll_entries FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAYSLIPS
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE payslips ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'payslips_owner_all' AND tablename = 'payslips') THEN
    CREATE POLICY "payslips_owner_all"
      ON payslips FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- Employee payslip self-read
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'payslips_employee_read' AND tablename = 'payslips') THEN
    CREATE POLICY "payslips_employee_read"
      ON payslips FOR SELECT TO authenticated
      USING (
        employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
      );
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- ATTENDANCE_RECORDS
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE attendance_records ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'attendance_records_owner_all' AND tablename = 'attendance_records') THEN
    CREATE POLICY "attendance_records_owner_all"
      ON attendance_records FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- Employee attendance self-read
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'attendance_records_employee_read' AND tablename = 'attendance_records') THEN
    CREATE POLICY "attendance_records_employee_read"
      ON attendance_records FOR SELECT TO authenticated
      USING (
        employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())
      );
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- CLOCK_EVENTS
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE clock_events ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'clock_events_owner_all' AND tablename = 'clock_events') THEN
    CREATE POLICY "clock_events_owner_all"
      ON clock_events FOR ALL TO authenticated
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- GRANTS (ensure authenticated role has access)
-- ═══════════════════════════════════════════════════════════════════════════════

GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
