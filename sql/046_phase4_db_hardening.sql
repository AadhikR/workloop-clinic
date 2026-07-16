-- 046_phase4_db_hardening.sql
-- Phase 4: Database hardening — indexes, CHECK constraints, optimistic locking.

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4.1  INDEXES ON HIGH-TRAFFIC COLUMNS
-- These columns are used in WHERE/JOIN clauses by RLS policies, storage
-- functions, and portal queries. Without indexes, every query does a seq scan.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Employees (most queried table)
CREATE INDEX IF NOT EXISTS idx_employees_user_id       ON employees(user_id);
CREATE INDEX IF NOT EXISTS idx_employees_auth_user_id  ON employees(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_employees_active        ON employees(active);
CREATE INDEX IF NOT EXISTS idx_employees_reporting_mgr ON employees(reporting_manager_id);

-- Notifications (polled every 60s by every logged-in user)
CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_id   ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read_at   ON notifications(read_at) WHERE read_at IS NULL;

-- Attendance (queried by date range frequently)
CREATE INDEX IF NOT EXISTS idx_attendance_employee_date ON attendance_records(employee_id, date);
CREATE INDEX IF NOT EXISTS idx_clock_events_employee    ON clock_events(employee_id);
CREATE INDEX IF NOT EXISTS idx_clock_events_time        ON clock_events(event_time);

-- Leave requests (filtered by status in queues)
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status   ON leave_requests(status);

-- Payroll entries (joined to runs on every payroll load)
CREATE INDEX IF NOT EXISTS idx_payroll_entries_run_id ON payroll_entries(payroll_run_id);

-- Salary advances (filtered by employee and status)
CREATE INDEX IF NOT EXISTS idx_advances_employee ON salary_advances(employee_id);
CREATE INDEX IF NOT EXISTS idx_advances_status   ON salary_advances(status);

-- Expense claims (filtered by employee and status)
CREATE INDEX IF NOT EXISTS idx_expenses_employee ON expense_claims(employee_id);

-- Documents (queried per employee)
CREATE INDEX IF NOT EXISTS idx_documents_employee ON employee_documents(employee_id);

-- Training records and certifications
CREATE INDEX IF NOT EXISTS idx_training_employee ON training_records(employee_id);
CREATE INDEX IF NOT EXISTS idx_certs_employee    ON certifications(employee_id);

-- Appraisals
CREATE INDEX IF NOT EXISTS idx_appraisals_cycle    ON appraisals(cycle_id);
CREATE INDEX IF NOT EXISTS idx_appraisals_employee ON appraisals(employee_id);

-- Roster assignments
CREATE INDEX IF NOT EXISTS idx_roster_employee ON roster_assignments(employee_id);
CREATE INDEX IF NOT EXISTS idx_roster_date     ON roster_assignments(date);

-- Letter requests
CREATE INDEX IF NOT EXISTS idx_letters_employee ON letter_requests(employee_id);

-- Contracts
CREATE INDEX IF NOT EXISTS idx_contracts_employee ON employee_contracts(employee_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4.2  CHECK CONSTRAINTS ON FINANCIAL FIELDS
-- Prevent invalid data at the DB level — negative salaries, negative balances.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Dry-run: check for existing violations before applying.
-- SELECT id, name, basic_salary FROM employees WHERE basic_salary < 0;
-- SELECT id, amount, outstanding_balance FROM salary_advances WHERE amount < 0 OR outstanding_balance < 0;

ALTER TABLE employees
  ADD CONSTRAINT chk_employees_basic_salary
    CHECK (basic_salary >= 0) NOT VALID;

ALTER TABLE employees
  ADD CONSTRAINT chk_employees_housing_allowance
    CHECK (housing_allowance >= 0) NOT VALID;

ALTER TABLE employees
  ADD CONSTRAINT chk_employees_transport_allowance
    CHECK (transport_allowance >= 0) NOT VALID;

ALTER TABLE salary_advances
  ADD CONSTRAINT chk_advances_amount
    CHECK (amount > 0) NOT VALID;

ALTER TABLE salary_advances
  ADD CONSTRAINT chk_advances_outstanding
    CHECK (outstanding_balance >= 0) NOT VALID;

ALTER TABLE payroll_entries
  ADD CONSTRAINT chk_entries_basic_salary
    CHECK (basic_salary >= 0) NOT VALID;

ALTER TABLE expense_claims
  ADD CONSTRAINT chk_expenses_amount
    CHECK (amount >= 0) NOT VALID;

-- ═══════════════════════════════════════════════════════════════════════════════
-- 4.3  OPTIMISTIC LOCKING — updated_at COLUMNS
-- Adds updated_at with auto-update trigger to key tables. Client code can
-- include updated_at in WHERE clauses to detect concurrent edits.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Shared trigger function
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- Add updated_at column + trigger to each table
DO $$ BEGIN
  -- employees
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'employees' AND column_name = 'updated_at') THEN
    ALTER TABLE employees ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
  -- payroll_runs
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'payroll_runs' AND column_name = 'updated_at') THEN
    ALTER TABLE payroll_runs ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
  -- salary_advances
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'salary_advances' AND column_name = 'updated_at') THEN
    ALTER TABLE salary_advances ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
  -- leave_requests
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'leave_requests' AND column_name = 'updated_at') THEN
    ALTER TABLE leave_requests ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
  -- attendance_records
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'attendance_records' AND column_name = 'updated_at') THEN
    ALTER TABLE attendance_records ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
  -- expense_claims
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'expense_claims' AND column_name = 'updated_at') THEN
    ALTER TABLE expense_claims ADD COLUMN updated_at TIMESTAMPTZ DEFAULT NOW();
  END IF;
END $$;

-- Create triggers (DROP first to make idempotent)
DROP TRIGGER IF EXISTS trg_employees_updated_at ON employees;
CREATE TRIGGER trg_employees_updated_at BEFORE UPDATE ON employees FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_payroll_runs_updated_at ON payroll_runs;
CREATE TRIGGER trg_payroll_runs_updated_at BEFORE UPDATE ON payroll_runs FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_advances_updated_at ON salary_advances;
CREATE TRIGGER trg_advances_updated_at BEFORE UPDATE ON salary_advances FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_leave_requests_updated_at ON leave_requests;
CREATE TRIGGER trg_leave_requests_updated_at BEFORE UPDATE ON leave_requests FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_attendance_updated_at ON attendance_records;
CREATE TRIGGER trg_attendance_updated_at BEFORE UPDATE ON attendance_records FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_expenses_updated_at ON expense_claims;
CREATE TRIGGER trg_expenses_updated_at BEFORE UPDATE ON expense_claims FOR EACH ROW EXECUTE FUNCTION set_updated_at();
