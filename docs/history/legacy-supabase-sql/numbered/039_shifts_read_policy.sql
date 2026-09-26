-- 039_shifts_read_policy.sql: Allow all authenticated users to read shifts
-- Required for employee/manager roster view fallback (direct query on roster_assignments
-- with embedded shifts join). The RPC uses SECURITY DEFINER so it bypasses RLS, but
-- the fallback direct query needs this policy.

-- Ensure RLS is enabled (idempotent)
ALTER TABLE shifts ENABLE ROW LEVEL SECURITY;

-- Admin: full access
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'shifts_admin_all' AND tablename = 'shifts') THEN
    CREATE POLICY "shifts_admin_all" ON shifts FOR ALL
      USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
  END IF;
END $$;

-- All authenticated users can read shifts (shift templates are not sensitive)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'shifts_authenticated_read' AND tablename = 'shifts') THEN
    CREATE POLICY "shifts_authenticated_read" ON shifts FOR SELECT
      USING (auth.role() = 'authenticated');
  END IF;
END $$;

GRANT ALL ON TABLE shifts TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
