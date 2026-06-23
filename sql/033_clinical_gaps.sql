-- 033_clinical_gaps.sql
-- Fills spec gaps from features 4.1, 7.1, 7.2
-- Idempotent: safe to re-run (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS)

-- ── 7.1  Professional Licence fields on employees ─────────────────────────────
-- Stored separately from document uploads so payroll can read them without a join.
ALTER TABLE employees ADD COLUMN IF NOT EXISTS licence_authority TEXT    NOT NULL DEFAULT 'None';
ALTER TABLE employees ADD COLUMN IF NOT EXISTS licence_number    TEXT    NOT NULL DEFAULT '';
ALTER TABLE employees ADD COLUMN IF NOT EXISTS licence_expiry    DATE;

-- ── 7.1  Compliance override audit log ───────────────────────────────────────
-- Written when HR overrides an expired-licence block on SIF generation.
CREATE TABLE IF NOT EXISTS compliance_overrides (
  id            UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id       UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  override_type TEXT        NOT NULL,          -- 'payroll_sif' | 'roster_publish'
  employee_ids  JSONB,                         -- array of employee UUIDs affected
  reason        TEXT        NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE compliance_overrides ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE compliance_overrides TO authenticated;
DROP POLICY IF EXISTS "compliance_overrides_admin" ON compliance_overrides;
CREATE POLICY "compliance_overrides_admin" ON compliance_overrides
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ── 7.2  Department-level minimum-staffing rules ──────────────────────────────
-- Keyed by (user_id, department name, shift_category) — per-shift-category target.
-- Replaces the per-shift-template min_staff that was added in migration 032.
CREATE TABLE IF NOT EXISTS department_staffing_rules (
  id             UUID  NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id        UUID  NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  department     TEXT  NOT NULL,
  shift_category TEXT  NOT NULL CHECK (shift_category IN ('morning','afternoon','night')),
  min_staff      INT   NOT NULL DEFAULT 1,
  effective_from DATE,
  effective_to   DATE,
  UNIQUE (user_id, department, shift_category)
);
ALTER TABLE department_staffing_rules ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE department_staffing_rules TO authenticated;
DROP POLICY IF EXISTS "dept_staffing_admin" ON department_staffing_rules;
CREATE POLICY "dept_staffing_admin" ON department_staffing_rules
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- ── 6.1  Manager portal access to appraisals for direct reports ──────────────
-- Managers can read appraisals/sections/cycles for employees they manage.
-- Manager can also update section ratings (scoring workflow).

DROP POLICY IF EXISTS "appraisals_manager_read"           ON appraisals;
DROP POLICY IF EXISTS "appraisal_sections_manager_read"   ON appraisal_sections;
DROP POLICY IF EXISTS "appraisal_sections_manager_update" ON appraisal_sections;
DROP POLICY IF EXISTS "appraisal_cycles_manager_read"     ON appraisal_cycles;

CREATE POLICY "appraisals_manager_read" ON appraisals
  FOR SELECT USING (
    employee_id IN (
      SELECT e.id FROM employees e
      WHERE e.reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

CREATE POLICY "appraisal_sections_manager_read" ON appraisal_sections
  FOR SELECT USING (
    appraisal_id IN (
      SELECT a.id FROM appraisals a
      JOIN employees e ON e.id = a.employee_id
      WHERE e.reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

CREATE POLICY "appraisal_sections_manager_update" ON appraisal_sections
  FOR UPDATE USING (
    appraisal_id IN (
      SELECT a.id FROM appraisals a
      JOIN employees e ON e.id = a.employee_id
      WHERE e.reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

CREATE POLICY "appraisal_cycles_manager_read" ON appraisal_cycles
  FOR SELECT USING (
    id IN (
      SELECT DISTINCT a.cycle_id FROM appraisals a
      JOIN employees e ON e.id = a.employee_id
      WHERE e.reporting_manager_id IN (
        SELECT id FROM employees WHERE auth_user_id = auth.uid()
      )
    )
  );

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
