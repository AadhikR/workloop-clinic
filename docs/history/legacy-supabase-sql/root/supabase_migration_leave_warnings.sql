-- ============================================================
-- Workloop — Store employee-side validation warnings on leave requests
-- Run in Supabase SQL Editor.
-- ============================================================

ALTER TABLE leave_requests
  ADD COLUMN IF NOT EXISTS warnings JSONB NOT NULL DEFAULT '[]';

-- Re-create the submit RPC with the new p_warnings parameter
CREATE OR REPLACE FUNCTION employee_submit_leave_request(
  p_leave_type_id   UUID,
  p_leave_type_code TEXT,
  p_start_date      DATE,
  p_end_date        DATE,
  p_is_half_day     BOOLEAN  DEFAULT FALSE,
  p_half_day_period TEXT     DEFAULT NULL,
  p_days_requested  NUMERIC  DEFAULT 0,
  p_reason          TEXT     DEFAULT '',
  p_attachment_url  TEXT     DEFAULT '',
  p_warnings        JSONB    DEFAULT '[]'
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_emp employees%ROWTYPE;
  v_id  UUID;
BEGIN
  SELECT * INTO v_emp FROM employees WHERE auth_user_id = auth.uid() LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'error', 'not_linked');
  END IF;

  INSERT INTO leave_requests (
    user_id, employee_id, leave_type_id, leave_type_code,
    start_date, end_date, is_half_day, half_day_period,
    days_requested, status, reason, attachment_url, submitted_at,
    warnings
  ) VALUES (
    v_emp.user_id, v_emp.id, p_leave_type_id, p_leave_type_code,
    p_start_date, p_end_date, p_is_half_day, p_half_day_period,
    p_days_requested, 'Pending', p_reason, p_attachment_url, NOW(),
    p_warnings
  ) RETURNING id INTO v_id;

  INSERT INTO leave_audit_log (
    user_id, leave_request_id, employee_id,
    action, actor, reason, old_status, new_status
  ) VALUES (
    v_emp.user_id, v_id, v_emp.id,
    'Submitted', auth.email(), '', '', 'Pending'
  );

  RETURN json_build_object('success', true, 'id', v_id);
END;
$$;
