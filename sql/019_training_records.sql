-- 019_training_records.sql
-- Feature 19: Training & Certification Records
--
-- Two new tables:
--   training_records  — training/course history per employee
--   certifications    — professional cert registry with expiry tracking
--
-- RLS: admin full-access (user_id = auth.uid())
--       employee self-read (employee_id via employees.auth_user_id)
-- No RPC needed — admin manages all records; employees only read.

-- ── Training Records ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS training_records (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id     UUID        NOT NULL REFERENCES employees(id)  ON DELETE CASCADE,
  training_title  TEXT        NOT NULL DEFAULT '',
  training_type   TEXT        NOT NULL DEFAULT 'external',  -- internal | external | online | conference
  provider        TEXT        NOT NULL DEFAULT '',
  start_date      DATE,
  end_date        DATE,
  duration_hours  DECIMAL(6,2),
  cost            DECIMAL(12,2) NOT NULL DEFAULT 0,
  status          TEXT        NOT NULL DEFAULT 'planned',   -- planned | in_progress | completed | cancelled
  score           TEXT        NOT NULL DEFAULT '',
  passed          BOOLEAN,
  certificate_url TEXT        NOT NULL DEFAULT '',
  notes           TEXT        NOT NULL DEFAULT '',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE training_records ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE training_records TO authenticated;

-- Admin: full CRUD scoped to their company records
CREATE POLICY "training_records_admin"
  ON training_records FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employees: read their own records only
CREATE POLICY "training_records_employee_read"
  ON training_records FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ── Certifications ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS certifications (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id         UUID        NOT NULL REFERENCES employees(id)  ON DELETE CASCADE,
  certification_name  TEXT        NOT NULL DEFAULT '',
  issuing_body        TEXT        NOT NULL DEFAULT '',
  certificate_no      TEXT        NOT NULL DEFAULT '',
  issued_date         DATE,
  expiry_date         DATE,       -- NULL = no expiry / lifetime certification
  certificate_url     TEXT        NOT NULL DEFAULT '',
  notes               TEXT        NOT NULL DEFAULT '',
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE certifications ENABLE ROW LEVEL SECURITY;

GRANT ALL ON TABLE certifications TO authenticated;

-- Admin: full CRUD scoped to their company records
CREATE POLICY "certifications_admin"
  ON certifications FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employees: read their own certifications only
CREATE POLICY "certifications_employee_read"
  ON certifications FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- After running this file, also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
--   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
