-- ============================================================
-- Migration 003: Medical Insurance Tracking
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================
-- Dubai Law No. 11 of 2013 (Dubai) / Abu Dhabi Circular 23/2014 mandates
-- employer-provided health insurance for all employees in the UAE.
-- ============================================================

-- 1. Insurance policies (company-level plan records)
CREATE TABLE IF NOT EXISTS insurance_policies (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  insurer_name   TEXT NOT NULL DEFAULT '',   -- e.g. Daman, AXA Gulf, Oman Insurance
  policy_number  TEXT NOT NULL DEFAULT '',   -- group certificate / policy number
  tier_name      TEXT NOT NULL DEFAULT '',   -- e.g. Gold, Silver, Enhanced Basic
  annual_premium DECIMAL(12,2) NOT NULL DEFAULT 0,
  renewal_date   DATE,                       -- dashboard alert fires 60d before this
  broker_name    TEXT NOT NULL DEFAULT '',
  broker_contact TEXT NOT NULL DEFAULT '',   -- phone or email
  notes          TEXT NOT NULL DEFAULT '',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE insurance_policies ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE insurance_policies TO authenticated;
CREATE POLICY "insurance_policies_admin"
  ON insurance_policies
  FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- 2. Per-employee insurance coverage assignment (one record per employee)
CREATE TABLE IF NOT EXISTS employee_insurance (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id    UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  policy_id      UUID REFERENCES insurance_policies(id) ON DELETE SET NULL,
  member_id      TEXT NOT NULL DEFAULT '',   -- insurer-assigned member ID
  card_number    TEXT NOT NULL DEFAULT '',   -- physical card number
  effective_date DATE,
  expiry_date    DATE,                       -- dashboard alert fires 60d before this
  tier_name      TEXT NOT NULL DEFAULT '',   -- override tier if different from policy default
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, employee_id)              -- one coverage record per employee
);
ALTER TABLE employee_insurance ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE employee_insurance TO authenticated;
CREATE POLICY "employee_insurance_admin"
  ON employee_insurance
  FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
-- Employees can read their own insurance record via employee self-service
CREATE POLICY "employee_insurance_self"
  ON employee_insurance
  FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- 3. Insurance dependants (family members covered under employee's policy)
CREATE TABLE IF NOT EXISTS insurance_dependants (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id   UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  name          TEXT NOT NULL DEFAULT '',
  relationship  TEXT NOT NULL DEFAULT '',   -- Spouse, Child, Parent, Sibling, Other
  date_of_birth DATE,
  card_number   TEXT NOT NULL DEFAULT '',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE insurance_dependants ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE insurance_dependants TO authenticated;
CREATE POLICY "insurance_dependants_admin"
  ON insurance_dependants
  FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ============================================================
-- After running this migration also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- to keep the Playwright test suite's service role in sync.
-- ============================================================
