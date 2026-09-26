-- 049_feature_toggles.sql
-- Per-company feature toggles so small clinics can hide advanced modules
-- (Emiratization/Nafis panel, roster staffing-rule enforcement, biometric CSV
-- import) without losing the underlying data. All defaults are TRUE so
-- existing installs behave identically after running this migration.
--
-- Run in Supabase SQL Editor. Idempotent — safe to re-run.

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'companies' AND column_name = 'enable_nafis'
  ) THEN
    ALTER TABLE companies ADD COLUMN enable_nafis BOOLEAN NOT NULL DEFAULT true;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'companies' AND column_name = 'enable_staffing_rules'
  ) THEN
    ALTER TABLE companies ADD COLUMN enable_staffing_rules BOOLEAN NOT NULL DEFAULT true;
  END IF;
END $$;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'companies' AND column_name = 'enable_biometric_import'
  ) THEN
    ALTER TABLE companies ADD COLUMN enable_biometric_import BOOLEAN NOT NULL DEFAULT true;
  END IF;
END $$;

-- No new RLS policies needed — the columns inherit the existing companies
-- policy (user_id = auth.uid()).

-- ═══════════════════════════════════════════════════════════════════════════════
-- Employee-side advance cancellation (SECURITY DEFINER RPC).
--
-- Employees can withdraw their own PENDING advance requests. Once HR has
-- approved (status = 'active'), or the record has been settled/cancelled, the
-- RPC refuses. The employee is resolved by employees.auth_user_id = auth.uid()
-- so only the requesting employee can cancel their own row.
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION employee_cancel_advance(p_advance_id UUID)
RETURNS TABLE (
  id                    UUID,
  status                TEXT,
  rejection_reason      TEXT
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE
  v_emp_id UUID;
  v_status TEXT;
BEGIN
  -- Resolve calling employee
  SELECT e.id INTO v_emp_id
  FROM employees e
  WHERE e.auth_user_id = auth.uid()
  LIMIT 1;

  IF v_emp_id IS NULL THEN
    RAISE EXCEPTION 'No employee record linked to this account.';
  END IF;

  -- Fetch and confirm ownership + pending status
  SELECT sa.status INTO v_status
  FROM salary_advances sa
  WHERE sa.id = p_advance_id AND sa.employee_id = v_emp_id;

  IF v_status IS NULL THEN
    RAISE EXCEPTION 'Advance not found or not owned by this employee.';
  END IF;

  IF v_status <> 'pending' THEN
    RAISE EXCEPTION 'Only pending advances can be cancelled (current status: %).', v_status;
  END IF;

  RETURN QUERY
  UPDATE salary_advances
     SET status = 'cancelled',
         rejection_reason = COALESCE(rejection_reason, 'Cancelled by employee')
   WHERE id = p_advance_id
   RETURNING id, status, rejection_reason;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_cancel_advance(UUID) TO authenticated;

GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
