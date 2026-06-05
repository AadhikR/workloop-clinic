-- Feature 17: Payroll Approval (Maker-Checker)
-- Run in Supabase Dashboard → SQL Editor → New Query.

-- ── Add approval columns to payroll_runs ──────────────────────────────────────
-- approval_status flow:
--   'draft' → 'pending_approval' → 'approved'
--   then handleSubmitPayroll sets payroll_runs.status = 'generated' (irreversible).
-- On rejection: approval_status returns to 'draft'; rejection_reason is retained.

ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS approval_status             TEXT        NOT NULL DEFAULT 'draft';
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS submitted_for_approval_at   TIMESTAMPTZ;
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS submitted_by                TEXT        NOT NULL DEFAULT '';
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS approved_by                 TEXT        NOT NULL DEFAULT '';
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS approved_at                 TIMESTAMPTZ;
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS rejection_reason            TEXT        NOT NULL DEFAULT '';
ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS rejected_at                 TIMESTAMPTZ;

-- ── Audit log for approval actions ────────────────────────────────────────────
-- action values: 'submitted' | 'approved' | 'rejected' | 'recalled'

CREATE TABLE IF NOT EXISTS payroll_approval_log (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES auth.users(id),
  payroll_run_id UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE,
  action         TEXT NOT NULL,
  performed_by   TEXT NOT NULL DEFAULT '',
  notes          TEXT NOT NULL DEFAULT '',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE payroll_approval_log ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE payroll_approval_log TO authenticated;
GRANT ALL ON TABLE payroll_approval_log TO service_role;

CREATE POLICY payroll_approval_log_admin
  ON payroll_approval_log FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
