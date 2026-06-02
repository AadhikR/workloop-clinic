-- 005_salary_advances.sql
-- Feature 5: Salary Advance & Loan Management
-- Run in Supabase Dashboard → SQL Editor → New Query

-- ─── salary_advances ─────────────────────────────────────────────────────────
-- Tracks advance/loan disbursements per employee.
-- Admin-created advances start as 'active'.
-- Employee-requested advances start as 'pending' (awaiting admin approval).
CREATE TABLE IF NOT EXISTS salary_advances (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  amount              DECIMAL(12,2) NOT NULL CHECK (amount > 0),
  disbursed_date      DATE,
  reason              TEXT NOT NULL DEFAULT '',
  repayment_months    INT  NOT NULL DEFAULT 1 CHECK (repayment_months > 0),
  monthly_deduction   DECIMAL(12,2) NOT NULL DEFAULT 0 CHECK (monthly_deduction >= 0),
  outstanding_balance DECIMAL(12,2) NOT NULL DEFAULT 0 CHECK (outstanding_balance >= 0),
  status              TEXT NOT NULL DEFAULT 'active'
                      CHECK (status IN ('pending','active','settled','cancelled')),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE salary_advances ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE salary_advances TO authenticated;

-- Admin: full access to advances in their company
DROP POLICY IF EXISTS salary_advances_admin ON salary_advances;
CREATE POLICY salary_advances_admin ON salary_advances
  FOR ALL
  USING     (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employee self-service: can read their own advance records
DROP POLICY IF EXISTS salary_advances_employee_read ON salary_advances;
CREATE POLICY salary_advances_employee_read ON salary_advances
  FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ─── advance_repayments ───────────────────────────────────────────────────────
-- One row per monthly deduction applied in a payroll run.
CREATE TABLE IF NOT EXISTS advance_repayments (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  advance_id     UUID NOT NULL REFERENCES salary_advances(id) ON DELETE CASCADE,
  payroll_run_id UUID REFERENCES payroll_runs(id) ON DELETE SET NULL,
  amount         DECIMAL(12,2) NOT NULL CHECK (amount > 0),
  paid_date      DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE advance_repayments ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE advance_repayments TO authenticated;

-- RLS via join to parent advance (admin inherits access)
DROP POLICY IF EXISTS advance_repayments_admin ON advance_repayments;
CREATE POLICY advance_repayments_admin ON advance_repayments
  FOR ALL
  USING (
    advance_id IN (
      SELECT id FROM salary_advances WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    advance_id IN (
      SELECT id FROM salary_advances WHERE user_id = auth.uid()
    )
  );

-- Employee can read their own repayment history
DROP POLICY IF EXISTS advance_repayments_employee_read ON advance_repayments;
CREATE POLICY advance_repayments_employee_read ON advance_repayments
  FOR SELECT
  USING (
    advance_id IN (
      SELECT sa.id
      FROM   salary_advances sa
      JOIN   employees       e  ON e.id = sa.employee_id
      WHERE  e.auth_user_id = auth.uid()
    )
  );

-- ─── RPC: employee_request_advance ───────────────────────────────────────────
-- Employees call this to submit an advance request.
-- The advance is created with status = 'pending'; admin must approve it.
CREATE OR REPLACE FUNCTION employee_request_advance(
  p_amount DECIMAL,
  p_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_employee_id UUID;
  v_user_id     UUID;
  v_advance_id  UUID;
BEGIN
  -- Resolve the employee linked to this auth user
  SELECT id, user_id
  INTO   v_employee_id, v_user_id
  FROM   employees
  WHERE  auth_user_id = auth.uid()
  LIMIT  1;

  IF v_employee_id IS NULL THEN
    RAISE EXCEPTION 'No linked employee found for this account. Please contact HR.';
  END IF;

  IF p_amount IS NULL OR p_amount <= 0 THEN
    RAISE EXCEPTION 'Advance amount must be greater than zero.';
  END IF;

  INSERT INTO salary_advances (
    user_id,
    employee_id,
    amount,
    reason,
    repayment_months,
    monthly_deduction,
    outstanding_balance,
    status
  ) VALUES (
    v_user_id,
    v_employee_id,
    p_amount,
    COALESCE(NULLIF(TRIM(p_reason), ''), 'No reason provided'),
    1,         -- default: 1 month repayment (admin can adjust on approval)
    p_amount,  -- will be recalculated when admin sets repayment_months
    p_amount,
    'pending'
  )
  RETURNING id INTO v_advance_id;

  RETURN v_advance_id;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_request_advance(DECIMAL, TEXT) TO authenticated;

-- After running this file, also execute:
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
