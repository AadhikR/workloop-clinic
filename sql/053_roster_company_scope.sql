-- 053_roster_company_scope.sql
-- Roster / swap tables gain a company_id column so the multi-company admin
-- shell can scope queries the same way it already does for employees and
-- payroll (see CLAUDE.md — Multi-company section).
--
-- Backward-compatible: rows created before this migration have company_id
-- NULL; storage layer uses the project-standard
--   .or('company_id.eq.X,company_id.is.null')
-- filter so legacy rows still show up under the primary company.
--
-- Idempotent — safe to re-run in the Supabase SQL Editor.

ALTER TABLE roster_assignments
  ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);

ALTER TABLE shift_swap_requests
  ADD COLUMN IF NOT EXISTS company_id UUID REFERENCES companies(id);

-- Backfill from the employees table where possible.
UPDATE roster_assignments AS r
   SET company_id = e.company_id
  FROM employees AS e
 WHERE r.employee_id = e.id
   AND r.company_id IS NULL
   AND e.company_id IS NOT NULL;

UPDATE shift_swap_requests AS s
   SET company_id = e.company_id
  FROM employees AS e
 WHERE s.requester_employee_id = e.id
   AND s.company_id IS NULL
   AND e.company_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_roster_assignments_company_id
  ON roster_assignments(company_id);

CREATE INDEX IF NOT EXISTS idx_shift_swap_requests_company_id
  ON shift_swap_requests(company_id);

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
