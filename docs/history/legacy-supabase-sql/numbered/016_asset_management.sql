-- Feature 16: Asset Management
-- Run in Supabase Dashboard → SQL Editor → New Query.
-- Note: 015 (GPS Attendance) was skipped; numbering jumps to 016.

-- ── Asset master table ────────────────────────────────────────────────────────
-- category: laptop | phone | tablet | vehicle | furniture | equipment | other
-- status:   available | assigned | under_repair | retired | lost

CREATE TABLE IF NOT EXISTS assets (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES auth.users(id),
  name          TEXT NOT NULL,
  asset_code    TEXT NOT NULL DEFAULT '',
  category      TEXT NOT NULL DEFAULT 'other',
  brand         TEXT NOT NULL DEFAULT '',
  model         TEXT NOT NULL DEFAULT '',
  serial_number TEXT NOT NULL DEFAULT '',
  purchase_date DATE,
  purchase_cost DECIMAL(12,2),
  status        TEXT NOT NULL DEFAULT 'available',
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE assets TO authenticated;
GRANT ALL ON TABLE assets TO service_role;

-- Admin: full CRUD on their company's assets
CREATE POLICY assets_admin
  ON assets FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- ── Assignment history table ──────────────────────────────────────────────────
-- One insert per assignment event; never updated (use return_date to close out).
-- return_date IS NULL → currently assigned.
-- condition values: 'new' | 'good' | 'fair' | 'poor'

CREATE TABLE IF NOT EXISTS asset_assignments (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES auth.users(id),
  asset_id              UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
  employee_id           UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  assigned_date         DATE NOT NULL DEFAULT CURRENT_DATE,
  return_date           DATE,
  condition_at_handover TEXT NOT NULL DEFAULT 'good',
  condition_at_return   TEXT,
  notes                 TEXT NOT NULL DEFAULT '',
  assigned_by           TEXT NOT NULL DEFAULT '',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE asset_assignments ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE asset_assignments TO authenticated;
GRANT ALL ON TABLE asset_assignments TO service_role;

-- Admin: full CRUD
CREATE POLICY asset_assignments_admin
  ON asset_assignments FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- Employees: read their own assignment records (current + historical)
CREATE POLICY asset_assignments_employee_read
  ON asset_assignments FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- ── Employee read policy on assets ───────────────────────────────────────────
-- Must come AFTER asset_assignments is created (references it in the subquery).
-- Employees can read assets that have ever been assigned to them.
CREATE POLICY assets_employee_read
  ON assets FOR SELECT
  USING (
    id IN (
      SELECT asset_id FROM asset_assignments
       WHERE employee_id IN (
         SELECT id FROM employees WHERE auth_user_id = auth.uid()
       )
    )
  );
