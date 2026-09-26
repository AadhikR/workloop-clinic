-- Feature 2.2: Biometric / Punching Machine Integration
-- Badge-to-employee mappings for CSV imports from ZKTeco, Suprema, and generic devices.

CREATE TABLE IF NOT EXISTS biometric_mappings (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  badge_no    TEXT NOT NULL,
  employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  device_name TEXT DEFAULT 'Default',
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, badge_no)
);

ALTER TABLE biometric_mappings ENABLE ROW LEVEL SECURITY;
GRANT ALL ON TABLE biometric_mappings TO authenticated;

DROP POLICY IF EXISTS "biometric_mappings_admin" ON biometric_mappings;
CREATE POLICY "biometric_mappings_admin" ON biometric_mappings
  FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
