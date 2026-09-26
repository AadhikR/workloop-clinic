-- 048_incident_reports.sql
-- Phase 7.3: Clinical workplace incident reporting.
-- Tracks incidents (injuries, near-misses, medication errors, patient safety events, etc.)

CREATE TABLE IF NOT EXISTS incident_reports (
  id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id           UUID NOT NULL REFERENCES auth.users(id),
  company_id        UUID REFERENCES companies(id) ON DELETE SET NULL,

  incident_date     DATE NOT NULL,
  incident_time     TIME,
  location          TEXT DEFAULT '',
  department        TEXT DEFAULT '',

  incident_type     TEXT NOT NULL DEFAULT 'other',
  severity          TEXT NOT NULL DEFAULT 'low',
  description       TEXT NOT NULL DEFAULT '',

  reported_by_id    UUID REFERENCES employees(id) ON DELETE SET NULL,
  involved_emp_id   UUID REFERENCES employees(id) ON DELETE SET NULL,

  immediate_action  TEXT DEFAULT '',
  root_cause        TEXT DEFAULT '',
  corrective_action TEXT DEFAULT '',

  status            TEXT NOT NULL DEFAULT 'open',
  closed_date       DATE,
  closed_by         TEXT DEFAULT '',
  notes             TEXT DEFAULT '',

  created_at        TIMESTAMPTZ DEFAULT NOW(),
  updated_at        TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE incident_reports ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE incident_reports TO authenticated;

CREATE POLICY incident_reports_admin_all
  ON incident_reports FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS idx_incidents_date       ON incident_reports(incident_date);
CREATE INDEX IF NOT EXISTS idx_incidents_status     ON incident_reports(status);
CREATE INDEX IF NOT EXISTS idx_incidents_department ON incident_reports(department);
CREATE INDEX IF NOT EXISTS idx_incidents_severity   ON incident_reports(severity);

DROP TRIGGER IF EXISTS trg_incidents_updated_at ON incident_reports;
CREATE TRIGGER trg_incidents_updated_at
  BEFORE UPDATE ON incident_reports
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
