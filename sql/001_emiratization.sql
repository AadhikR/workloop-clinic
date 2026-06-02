-- ============================================================
-- Migration 001: Emiratization / Nafis Compliance Tracking
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Add sector and Nafis quota columns to companies
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS sector TEXT NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS nafis_quota_percent DECIMAL(5,2) NOT NULL DEFAULT 2.00;

-- 2. Add Nafis registration number to employees
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS nafis_registration_no TEXT NOT NULL DEFAULT '';

-- 3. Create the nafis_reports table
CREATE TABLE IF NOT EXISTS nafis_reports (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  period           TEXT NOT NULL,           -- 'YYYY-MM'
  total_headcount  INTEGER NOT NULL DEFAULT 0,
  emirati_count    INTEGER NOT NULL DEFAULT 0,
  ratio_percent    DECIMAL(5,2) NOT NULL DEFAULT 0,
  required_percent DECIMAL(5,2) NOT NULL DEFAULT 0,
  compliant        BOOLEAN NOT NULL DEFAULT false,
  snapshot         JSONB,                   -- list of UAE national employees at generation time
  generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, period)                 -- one report per company per month (upsert-safe)
);

-- 4. Enable Row Level Security
ALTER TABLE nafis_reports ENABLE ROW LEVEL SECURITY;

-- 5. Grant access to authenticated role
GRANT ALL ON TABLE nafis_reports TO authenticated;

-- 6. RLS policy: each admin sees only their own reports
CREATE POLICY "nafis_reports_owner"
  ON nafis_reports
  FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
