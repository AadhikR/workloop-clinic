-- Feature 13: Offboarding Workflow & Clearance
-- Run in Supabase Dashboard → SQL Editor → New Query.

-- ── Clearance checklist header (one per terminated employee) ─────────────────
CREATE TABLE IF NOT EXISTS offboarding_checklists (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES auth.users(id),
  employee_id              UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  status                   TEXT NOT NULL DEFAULT 'in_progress',     -- 'in_progress' | 'completed'
  visa_cancellation_status TEXT NOT NULL DEFAULT 'not_started',     -- 'not_started' | 'initiated' | 'submitted_gdrfa' | 'cancelled'
  visa_cancellation_date   DATE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at             TIMESTAMPTZ,
  UNIQUE (user_id, employee_id)
);

ALTER TABLE offboarding_checklists ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE offboarding_checklists TO authenticated;
GRANT ALL ON TABLE offboarding_checklists TO service_role;

CREATE POLICY offboarding_checklists_admin
  ON offboarding_checklists FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ── Individual clearance tasks ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS offboarding_tasks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checklist_id UUID NOT NULL REFERENCES offboarding_checklists(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES auth.users(id),
  task_name    TEXT NOT NULL,
  completed    BOOLEAN NOT NULL DEFAULT false,
  completed_at TIMESTAMPTZ,
  completed_by TEXT NOT NULL DEFAULT '',
  notes        TEXT NOT NULL DEFAULT '',
  sort_order   INT  NOT NULL DEFAULT 0,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE offboarding_tasks ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE offboarding_tasks TO authenticated;
GRANT ALL ON TABLE offboarding_tasks TO service_role;

CREATE POLICY offboarding_tasks_admin
  ON offboarding_tasks FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ── Reusable task templates (admin-configurable default task list) ───────────
CREATE TABLE IF NOT EXISTS offboarding_task_templates (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id),
  task_name     TEXT NOT NULL,
  default_order INT  NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE offboarding_task_templates ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE offboarding_task_templates TO authenticated;
GRANT ALL ON TABLE offboarding_task_templates TO service_role;

CREATE POLICY offboarding_task_templates_admin
  ON offboarding_task_templates FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
