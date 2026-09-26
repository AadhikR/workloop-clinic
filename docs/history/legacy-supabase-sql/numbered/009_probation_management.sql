-- 009_probation_management.sql: Probation Period Management (Feature 11)
-- Run in Supabase SQL Editor

-- probation_extended: true when the admin has extended the probation at least once.
-- Used to flag the employee in the UI and log the extension event in job history.
ALTER TABLE employees
  ADD COLUMN IF NOT EXISTS probation_extended BOOLEAN NOT NULL DEFAULT false;

-- Keep service role in sync for the test suite
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
