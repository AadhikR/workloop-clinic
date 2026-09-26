-- Feature 2.1: Clinical Duty Rota — Department-Scoped, Multi-Shift
-- Adds short code + category to shifts, and hour-tracking columns to roster_assignments.

-- ── shifts: add code and shift_category ──────────────────────────────────────
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS code TEXT;
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS shift_category TEXT DEFAULT 'morning';

-- ── roster_assignments: add hour tracking ────────────────────────────────────
ALTER TABLE roster_assignments ADD COLUMN IF NOT EXISTS planned_hours DECIMAL(4,2);
ALTER TABLE roster_assignments ADD COLUMN IF NOT EXISTS actual_hours  DECIMAL(4,2);
ALTER TABLE roster_assignments ADD COLUMN IF NOT EXISTS co_hours      DECIMAL(4,2) DEFAULT 0;

-- Back-fill planned_hours from the linked shift template's expected_hours
UPDATE roster_assignments ra
SET    planned_hours = s.expected_hours
FROM   shifts s
WHERE  ra.shift_id = s.id
  AND  ra.planned_hours IS NULL;

-- ── Grant (idempotent) ────────────────────────────────────────────────────────
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
