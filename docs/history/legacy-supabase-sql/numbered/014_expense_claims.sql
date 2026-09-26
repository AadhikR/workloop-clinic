-- Feature 14: Expense Claims & Reimbursements
-- Run in Supabase Dashboard → SQL Editor → New Query.

-- ── Expense claims table ─────────────────────────────────────────────────────
-- Categories: travel | meals | accommodation | office_supplies | medical |
--             phone_internet | training | other
-- Status:     pending → approved → paid  (or pending → rejected)

CREATE TABLE IF NOT EXISTS expense_claims (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id),
  employee_id      UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  category         TEXT NOT NULL DEFAULT 'other',
  amount           DECIMAL(12,2) NOT NULL CHECK (amount > 0),
  expense_date     DATE NOT NULL,
  description      TEXT NOT NULL DEFAULT '',
  receipt_url      TEXT NOT NULL DEFAULT '',
  status           TEXT NOT NULL DEFAULT 'pending',       -- 'pending'|'approved'|'rejected'|'paid'
  rejection_reason TEXT NOT NULL DEFAULT '',
  payroll_run_id   UUID REFERENCES payroll_runs(id) ON DELETE SET NULL,
  approved_by      TEXT NOT NULL DEFAULT '',
  approved_at      TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE expense_claims ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE expense_claims TO authenticated;
GRANT ALL ON TABLE expense_claims TO service_role;

-- Admin: full access to their company's claims
CREATE POLICY expense_claims_admin
  ON expense_claims FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employees: read their own claims (submitted via RPC → user_id = admin's uid)
CREATE POLICY expense_claims_employee_read
  ON expense_claims FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ── SECURITY DEFINER RPC — employee submits their own expense claim ───────────
-- Resolves the employee from auth.uid() → employees.auth_user_id,
-- then inserts with the admin's user_id so the admin's RLS policy can read it.
CREATE OR REPLACE FUNCTION employee_submit_expense(
  p_category     TEXT,
  p_amount       DECIMAL,
  p_expense_date DATE,
  p_description  TEXT,
  p_receipt_url  TEXT DEFAULT ''
) RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_emp_id   UUID;
  v_admin_id UUID;
  v_claim_id UUID;
BEGIN
  -- Find the linked employee and their admin's user_id
  SELECT id, user_id
    INTO v_emp_id, v_admin_id
    FROM employees
   WHERE auth_user_id = auth.uid()
   LIMIT 1;

  IF v_emp_id IS NULL THEN
    RAISE EXCEPTION 'Employee account not linked. Please register on the employee portal first.';
  END IF;

  IF p_amount IS NULL OR p_amount <= 0 THEN
    RAISE EXCEPTION 'Amount must be greater than zero.';
  END IF;

  IF p_expense_date IS NULL THEN
    RAISE EXCEPTION 'Expense date is required.';
  END IF;

  INSERT INTO expense_claims
    (user_id, employee_id, category, amount, expense_date, description, receipt_url, status)
  VALUES
    (v_admin_id, v_emp_id, p_category, p_amount, p_expense_date, COALESCE(p_description, ''), COALESCE(p_receipt_url, ''), 'pending')
  RETURNING id INTO v_claim_id;

  RETURN v_claim_id;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_submit_expense(TEXT, DECIMAL, DATE, TEXT, TEXT) TO authenticated;

-- ── Notes on the expense-receipts Storage bucket ─────────────────────────────
-- Create a private bucket named "expense-receipts" in Supabase Dashboard →
-- Storage, then add this Storage policy so admins can access their own files:
--
--   Policy name : expense_receipts_admin
--   Allowed op  : SELECT, INSERT, UPDATE, DELETE
--   Target roles: authenticated
--   USING       : (storage.foldername(name))[1] = auth.uid()::text
--
-- Files are stored at: {admin_user_id}/{employee_id}/{timestamp}_{filename}
-- (mirroring the employee-documents bucket layout)
