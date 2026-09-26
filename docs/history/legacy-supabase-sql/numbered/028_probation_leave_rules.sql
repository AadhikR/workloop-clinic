-- Feature 2.3: Probation-Aware Leave Rules
-- Adds a per-leave-type flag that HR can toggle to control
-- which leave types employees on probation are allowed to apply for.

ALTER TABLE leave_types ADD COLUMN IF NOT EXISTS probation_eligible BOOLEAN DEFAULT true;

-- UAE Law sensible defaults for pre-existing seeded rows:
--   ANNUAL: not available during probation (Art. 29 requires 6 months service)
--   HAJJ:   not available (requires 2 years service, Art. 29)
--   STUDY:  not available (requires proof of enrollment, unusual during probation)
--   All others remain true (SICK is available but processed unpaid per Art. 31)
UPDATE leave_types SET probation_eligible = false WHERE code IN ('ANNUAL', 'HAJJ', 'STUDY');

-- Keep service_role in sync for tests
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
