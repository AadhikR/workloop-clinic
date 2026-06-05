-- Feature 12: Contract Renewal Management
-- Creates employee_contracts history table for tracking all contract lifecycle events.
-- Run in Supabase Dashboard → SQL Editor → New Query.

CREATE TABLE IF NOT EXISTS employee_contracts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id),
  employee_id   UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  contract_type TEXT NOT NULL DEFAULT 'Limited',
  start_date    DATE,
  end_date      DATE,
  renewed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  renewed_by    TEXT NOT NULL DEFAULT '',
  action        TEXT NOT NULL DEFAULT 'new',   -- 'new' | 'renewed' | 'converted' | 'not_renewed'
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE employee_contracts ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE employee_contracts TO authenticated;

CREATE POLICY employee_contracts_admin
  ON employee_contracts FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Keep service_role in sync so the test suite can read/write this table.
GRANT ALL ON TABLE employee_contracts TO service_role;
