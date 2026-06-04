-- 008_wps_tracking.sql: WPS Payment Confirmation & Reconciliation (Feature 9)
-- Run in Supabase SQL Editor

-- ── 1. Add WPS tracking columns to payroll_runs ───────────────────────────────
--   wps_status: workflow state for the WPS submission
--     'draft'             → SIF not yet downloaded (initial state)
--     'sif_generated'     → SIF file has been downloaded by admin
--     'submitted'         → Admin has submitted the file to the bank
--     'confirmed'         → Bank confirmed successful payment
--     'partial_rejection' → Bank confirmed but some employee payments rejected
--     'failed'            → Bank rejected the entire payment
--
ALTER TABLE payroll_runs
  ADD COLUMN IF NOT EXISTS wps_status        TEXT        NOT NULL DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS wps_submitted_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS wps_confirmed_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS wps_reference_no  TEXT        NOT NULL DEFAULT '';

-- ── 2. Add per-employee WPS payment status to payroll_entries ─────────────────
--   wps_payment_status: 'pending' | 'paid' | 'rejected'
--
ALTER TABLE payroll_entries
  ADD COLUMN IF NOT EXISTS wps_payment_status    TEXT NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS wps_rejection_reason  TEXT NOT NULL DEFAULT '';

-- ── 3. Keep service role in sync for test suite ───────────────────────────────
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
