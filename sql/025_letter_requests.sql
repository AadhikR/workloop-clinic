-- ============================================================
-- Migration 025: Letter & Certificate Request System (Feature 1.3)
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Create letter_requests table
CREATE TABLE IF NOT EXISTS letter_requests (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  employee_id  UUID        NOT NULL REFERENCES employees(id)  ON DELETE CASCADE,
  letter_type  TEXT        NOT NULL,
  purpose      TEXT        NOT NULL DEFAULT '',
  status       TEXT        NOT NULL DEFAULT 'pending',   -- pending | completed | rejected
  notes        TEXT        NOT NULL DEFAULT '',
  rejection_reason TEXT    NOT NULL DEFAULT '',
  requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- 2. Enable RLS
ALTER TABLE letter_requests ENABLE ROW LEVEL SECURITY;

-- 3. Grant access
GRANT ALL ON TABLE letter_requests TO authenticated;

-- 4. Admin: full access to their company's requests
DROP POLICY IF EXISTS "letter_requests_admin" ON letter_requests;
CREATE POLICY "letter_requests_admin"
  ON letter_requests FOR ALL
  USING  (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- 5. Employee: read own requests
DROP POLICY IF EXISTS "letter_requests_employee_read" ON letter_requests;
CREATE POLICY "letter_requests_employee_read"
  ON letter_requests FOR SELECT
  USING (
    employee_id IN (
      SELECT id FROM employees WHERE auth_user_id = auth.uid()
    )
  );

-- 6. RPC: employee submits a letter request
CREATE OR REPLACE FUNCTION employee_request_letter(
  p_letter_type TEXT,
  p_purpose     TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_employee_id UUID;
  v_admin_uid   UUID;
  v_req_id      UUID;
BEGIN
  SELECT id, user_id
    INTO v_employee_id, v_admin_uid
    FROM employees
   WHERE auth_user_id = auth.uid()
     AND active = true
   LIMIT 1;

  IF v_employee_id IS NULL THEN
    RAISE EXCEPTION 'No active employee account linked to this user';
  END IF;

  INSERT INTO letter_requests (user_id, employee_id, letter_type, purpose)
  VALUES (v_admin_uid, v_employee_id, p_letter_type, COALESCE(p_purpose, ''))
  RETURNING id INTO v_req_id;

  RETURN v_req_id;
END;
$$;

GRANT EXECUTE ON FUNCTION employee_request_letter(TEXT, TEXT) TO authenticated;

-- ============================================================
-- After running, also run:
--   GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
-- ============================================================
