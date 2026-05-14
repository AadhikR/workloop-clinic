-- ─── payslips table ─────────────────────────────────────────────────────────
-- Immutable snapshot created when admin downloads the SIF (finalises payroll).
-- Employees read their own via RLS; admin reads all under their company.

CREATE TABLE IF NOT EXISTS payslips (
  id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         UUID        NOT NULL REFERENCES auth.users(id),
  payroll_run_id  UUID        NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
  employee_id     UUID        NOT NULL REFERENCES employees(id)    ON DELETE CASCADE,
  period          TEXT        NOT NULL,          -- 'YYYY-MM'
  payment_date    DATE,
  gross_pay       NUMERIC(12,2) NOT NULL DEFAULT 0,
  net_pay         NUMERIC(12,2) NOT NULL DEFAULT 0,
  data_snapshot   JSONB       NOT NULL DEFAULT '{}',   -- full entry at time of finalisation
  issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (payroll_run_id, employee_id)
);

ALTER TABLE payslips ENABLE ROW LEVEL SECURITY;

-- Admin: read all payslips belonging to their company
CREATE POLICY "payslips: admin read own"
  ON payslips FOR SELECT
  USING (user_id = auth.uid());

-- Employee: read only their own payslip(s)
CREATE POLICY "payslips: employee read own"
  ON payslips FOR SELECT
  USING (
    employee_id = (
      SELECT id FROM employees WHERE auth_user_id = auth.uid() LIMIT 1
    )
  );

-- Admin: insert (createPayslipRecords runs as the admin user)
CREATE POLICY "payslips: admin insert"
  ON payslips FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- Admin: update to allow re-finalisation (upsert on conflict)
CREATE POLICY "payslips: admin update"
  ON payslips FOR UPDATE
  USING (user_id = auth.uid());
