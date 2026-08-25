-- 055: General/custom employee and manager requests
-- Extends the existing letter request queue so HR can receive and action
-- free-form requests without changing the established letter workflow.
-- Idempotent — safe to re-run.

ALTER TABLE letter_requests
  ADD COLUMN IF NOT EXISTS request_kind TEXT NOT NULL DEFAULT 'letter';

UPDATE letter_requests
   SET request_kind = 'letter'
 WHERE request_kind IS NULL OR request_kind NOT IN ('letter', 'custom');

ALTER TABLE letter_requests
  DROP CONSTRAINT IF EXISTS letter_requests_request_kind_check;

ALTER TABLE letter_requests
  ADD CONSTRAINT letter_requests_request_kind_check
  CHECK (request_kind IN ('letter', 'custom'));

CREATE OR REPLACE FUNCTION employee_request_custom(p_subject TEXT, p_details TEXT)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_employee_id UUID;
  v_admin_uid UUID;
  v_req_id UUID;
  v_subject TEXT := btrim(COALESCE(p_subject, ''));
  v_details TEXT := btrim(COALESCE(p_details, ''));
BEGIN
  IF char_length(v_subject) < 3 OR char_length(v_subject) > 120 THEN
    RAISE EXCEPTION 'Request subject must be between 3 and 120 characters';
  END IF;
  IF char_length(v_details) < 5 OR char_length(v_details) > 2000 THEN
    RAISE EXCEPTION 'Request details must be between 5 and 2000 characters';
  END IF;

  SELECT id, user_id INTO v_employee_id, v_admin_uid
    FROM employees
   WHERE auth_user_id = auth.uid() AND active = true
   LIMIT 1;

  IF v_employee_id IS NULL THEN
    RAISE EXCEPTION 'No active employee account linked to this user';
  END IF;

  INSERT INTO letter_requests (user_id, employee_id, request_kind, letter_type, purpose)
  VALUES (v_admin_uid, v_employee_id, 'custom', v_subject, v_details)
  RETURNING id INTO v_req_id;

  RETURN v_req_id;
END;
$$;

REVOKE ALL ON FUNCTION employee_request_custom(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION employee_request_custom(TEXT, TEXT) TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;