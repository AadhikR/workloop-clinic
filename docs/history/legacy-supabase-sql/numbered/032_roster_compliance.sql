-- 032_roster_compliance.sql
-- Feature 7.2 — Shift Minimum Staffing Compliance
-- Adds min_staff per shift template; roster warnings when below minimum

ALTER TABLE shifts ADD COLUMN IF NOT EXISTS min_staff INT NOT NULL DEFAULT 1;

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
