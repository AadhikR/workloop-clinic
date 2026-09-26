-- ============================================================
-- Migration 021: Multi-Company / Branch Support
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Add branch_name to companies
--    Each company row can now represent a distinct branch/entity.
--    branch_name is the short label shown in the switcher (e.g. "Dubai HQ").
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS branch_name TEXT NOT NULL DEFAULT '';

-- 2. Drop the unique constraint on user_id so one admin can own multiple company rows.
--    Supabase names this constraint 'companies_user_id_key' by default.
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_user_id_key;
ALTER TABLE companies DROP CONSTRAINT IF EXISTS companies_user_id_unique;

-- 3. Add company_id FK to employees
--    Each employee belongs to a specific branch.
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL;

-- 4. Add company_id FK to payroll_runs
ALTER TABLE payroll_runs
  ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id) ON DELETE SET NULL;

-- 5. Back-fill existing employees to their admin's first (only) company
UPDATE employees e
SET company_id = (
  SELECT c.id FROM companies c
  WHERE c.user_id = e.user_id
  ORDER BY c.created_at ASC
  LIMIT 1
)
WHERE e.company_id IS NULL;

-- 6. Back-fill existing payroll_runs similarly
UPDATE payroll_runs pr
SET company_id = (
  SELECT c.id FROM companies c
  WHERE c.user_id = pr.user_id
  ORDER BY c.created_at ASC
  LIMIT 1
)
WHERE pr.company_id IS NULL;

-- 7. Performance indexes
CREATE INDEX IF NOT EXISTS idx_employees_company_id    ON employees(company_id);
CREATE INDEX IF NOT EXISTS idx_payroll_runs_company_id ON payroll_runs(company_id);

-- 8. Keep service role in sync
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
