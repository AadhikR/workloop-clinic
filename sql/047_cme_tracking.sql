-- 047_cme_tracking.sql
-- Phase 7: CME (Continuing Medical Education) hour tracking.
-- Stores per-employee annual CME targets and logs hours from training_records.

-- ═══════════════════════════════════════════════════════════════════════════════
-- 7.2a  CME_REQUIREMENTS — annual hour targets per employee
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS cme_requirements (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES auth.users(id),
  employee_id     UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  year            INTEGER NOT NULL,
  required_hours  NUMERIC(6,1) NOT NULL DEFAULT 25,
  notes           TEXT DEFAULT '',
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (employee_id, year)
);

ALTER TABLE cme_requirements ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE cme_requirements TO authenticated;

CREATE POLICY cme_requirements_admin_all
  ON cme_requirements FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_cme_req_employee ON cme_requirements(employee_id);
CREATE INDEX IF NOT EXISTS idx_cme_req_year     ON cme_requirements(year);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_cme_requirements_updated_at ON cme_requirements;
CREATE TRIGGER trg_cme_requirements_updated_at
  BEFORE UPDATE ON cme_requirements
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════════
-- 7.2b  Add is_cme flag to training_records (marks a record as CME-eligible)
-- ═══════════════════════════════════════════════════════════════════════════════

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'training_records' AND column_name = 'is_cme'
  ) THEN
    ALTER TABLE training_records ADD COLUMN is_cme BOOLEAN DEFAULT false;
  END IF;
END $$;
