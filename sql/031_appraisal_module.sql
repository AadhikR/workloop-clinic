-- 031_appraisal_module.sql
-- Feature 6.1 — Employee Evaluation & Appraisal Module
-- Clinic-specific: default sections reflect clinical competency domains

-- ── Appraisal Cycles ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appraisal_cycles (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,                          -- e.g. "H1 2025", "Annual 2025"
  review_from  DATE NOT NULL,
  review_to    DATE NOT NULL,
  status       TEXT NOT NULL DEFAULT 'draft'           -- draft | active | closed
                CHECK (status IN ('draft','active','closed')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE appraisal_cycles ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE appraisal_cycles TO authenticated;

DROP POLICY IF EXISTS "appraisal_cycles_admin" ON appraisal_cycles;
CREATE POLICY "appraisal_cycles_admin"
  ON appraisal_cycles FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ── Appraisals ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appraisals (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  cycle_id            UUID NOT NULL REFERENCES appraisal_cycles(id) ON DELETE CASCADE,
  employee_id         UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  overall_rating      DECIMAL(3,1),                    -- computed avg of sections (1.0–5.0)
  self_rating         DECIMAL(3,1),                    -- employee's own overall rating
  status              TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','self_reviewed','reviewed','calibrated')),
  reviewer_comments   TEXT,
  development_plan    TEXT,
  reviewed_at         TIMESTAMPTZ,
  reviewed_by         TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (cycle_id, employee_id)
);

ALTER TABLE appraisals ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE appraisals TO authenticated;

DROP POLICY IF EXISTS "appraisals_admin" ON appraisals;
CREATE POLICY "appraisals_admin"
  ON appraisals FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employee self-read: see their own appraisals
DROP POLICY IF EXISTS "appraisals_employee_read" ON appraisals;
CREATE POLICY "appraisals_employee_read"
  ON appraisals FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ── Appraisal Sections ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appraisal_sections (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appraisal_id   UUID NOT NULL REFERENCES appraisals(id) ON DELETE CASCADE,
  section_name   TEXT NOT NULL,                        -- e.g. "Clinical Competency"
  weight         DECIMAL(4,2) NOT NULL DEFAULT 1.0,    -- relative weight for avg
  rating         DECIMAL(3,1),                         -- admin rating (1.0–5.0)
  self_rating    DECIMAL(3,1),                         -- employee rating
  comments       TEXT,
  sort_order     INT NOT NULL DEFAULT 0
);

ALTER TABLE appraisal_sections ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE appraisal_sections TO authenticated;

DROP POLICY IF EXISTS "appraisal_sections_admin" ON appraisal_sections;
CREATE POLICY "appraisal_sections_admin"
  ON appraisal_sections FOR ALL
  USING (
    appraisal_id IN (
      SELECT id FROM appraisals WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    appraisal_id IN (
      SELECT id FROM appraisals WHERE user_id = auth.uid()
    )
  );

-- Employee self-read: see their own section scores
DROP POLICY IF EXISTS "appraisal_sections_employee_read" ON appraisal_sections;
CREATE POLICY "appraisal_sections_employee_read"
  ON appraisal_sections FOR SELECT
  USING (
    appraisal_id IN (
      SELECT a.id FROM appraisals a
      JOIN employees e ON e.id = a.employee_id
      WHERE e.auth_user_id = auth.uid()
    )
  );

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
