-- ============================================================
-- Workloop — Employee Self-Service: RLS Policies + Write RPCs
-- Run this in the Supabase SQL editor AFTER the first migration.
-- ============================================================

-- Helper: returns the employee row for the signed-in auth user.
-- Used as a subquery in all employee RLS policies.
-- Pattern: (SELECT id FROM employees WHERE auth_user_id = auth.uid())

-- ── READ POLICIES ─────────────────────────────────────────────────────────────

-- leave_types: employees read types configured by their company
CREATE POLICY "employees: read leave types"
  ON leave_types FOR SELECT
  USING (
    user_id = (SELECT user_id FROM employees WHERE auth_user_id = auth.uid())
  );

-- public_holidays: employees read holidays for their company
CREATE POLICY "employees: read public holidays"
  ON public_holidays FOR SELECT
  USING (
    user_id = (SELECT user_id FROM employees WHERE auth_user_id = auth.uid())
  );

-- leave_settings: employees read settings for their company
CREATE POLICY "employees: read leave settings"
  ON leave_settings FOR SELECT
  USING (
    user_id = (SELECT user_id FROM employees WHERE auth_user_id = auth.uid())
  );

-- leave_requests: employee reads only their own
CREATE POLICY "employees: read own leave requests"
  ON leave_requests FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- leave_balances: employee reads only their own
CREATE POLICY "employees: read own leave balances"
  ON leave_balances FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- payroll_entries: employee reads only their own
CREATE POLICY "employees: read own payroll entries"
  ON payroll_entries FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- payroll_runs: employee reads runs that contain an entry for them
CREATE POLICY "employees: read payroll runs for own entries"
  ON payroll_runs FOR SELECT
  USING (
    id IN (
      SELECT payroll_run_id
      FROM payroll_entries
      WHERE employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
    )
  );

-- attendance_records: employee reads only their own
CREATE POLICY "employees: read own attendance records"
  ON attendance_records FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- clock_events: employee reads only their own
CREATE POLICY "employees: read own clock events"
  ON clock_events FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );

-- regularisation_requests: employee reads only their own
CREATE POLICY "employees: read own regularisation requests"
  ON regularisation_requests FOR SELECT
  USING (
    employee_id = (SELECT id FROM employees WHERE auth_user_id = auth.uid())
  );


-- ── WRITE RPCs (SECURITY DEFINER) ─────────────────────────────────────────────
--
-- Employee writes must set user_id = company_user_id (the admin's UID) so that
-- the admin's existing RLS policies can see the records.
-- SECURITY DEFINER lets the function bypass RLS to read the employees table
-- and write with the correct user_id.


-- 1. Submit a leave request
CREATE OR REPLACE FUNCTION employee_submit_leave_request(
  p_leave_type_id   UUID,
  p_leave_type_code TEXT,
  p_start_date      DATE,
  p_end_date        DATE,
  p_is_half_day     BOOLEAN  DEFAULT FALSE,
  p_half_day_period TEXT     DEFAULT NULL,
  p_days_requested  NUMERIC  DEFAULT 0,
  p_reason          TEXT     DEFAULT '',
  p_attachment_url  TEXT     DEFAULT ''
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
    days_requested, status, reason, attachment_url, submitted_at
  ) VALUES (
    v_emp.user_id, v_emp.id, p_leave_type_id, p_leave_type_code,
    p_start_date, p_end_date, p_is_half_day, p_half_day_period,
    p_days_requested, 'Pending', p_reason, p_attachment_url, NOW()
  ) RETURNING id INTO v_id;

  -- Immutable audit trail
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


-- 2. Cancel an employee's own pending leave request
CREATE OR REPLACE FUNCTION employee_cancel_leave_request(p_request_id UUID)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_emp  employees%ROWTYPE;
  v_req  leave_requests%ROWTYPE;
BEGIN
  SELECT * INTO v_emp FROM employees WHERE auth_user_id = auth.uid() LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'error', 'not_linked');
  END IF;

  SELECT * INTO v_req FROM leave_requests
  WHERE id = p_request_id AND employee_id = v_emp.id
  LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'error', 'not_found');
  END IF;
  IF v_req.status NOT IN ('Pending') THEN
    RETURN json_build_object('success', false, 'error', 'not_cancellable');
  END IF;

  UPDATE leave_requests SET status = 'Cancelled' WHERE id = p_request_id;

  INSERT INTO leave_audit_log (
    user_id, leave_request_id, employee_id,
    action, actor, reason, old_status, new_status
  ) VALUES (
    v_emp.user_id, p_request_id, v_emp.id,
    'Cancelled', auth.email(), 'Cancelled by employee', v_req.status, 'Cancelled'
  );

  RETURN json_build_object('success', true);
END;
$$;


-- 3. Record a clock-in or clock-out event
CREATE OR REPLACE FUNCTION employee_record_clock_event(
  p_event_type TEXT,       -- 'CLOCK_IN' or 'CLOCK_OUT'
  p_notes      TEXT DEFAULT ''
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_emp    employees%ROWTYPE;
  v_id     UUID;
  v_now    TIMESTAMPTZ := NOW();
BEGIN
  SELECT * INTO v_emp FROM employees WHERE auth_user_id = auth.uid() LIMIT 1;
  IF NOT FOUND THEN
    RETURN json_build_object('success', false, 'error', 'not_linked');
  END IF;

  IF p_event_type NOT IN ('CLOCK_IN', 'CLOCK_OUT') THEN
    RETURN json_build_object('success', false, 'error', 'invalid_event_type');
  END IF;

  INSERT INTO clock_events (
    user_id, employee_id, event_type, event_time, method, entered_by, notes
  ) VALUES (
    v_emp.user_id, v_emp.id, p_event_type, v_now, 'EMPLOYEE_APP', auth.uid()::TEXT, p_notes
  ) RETURNING id INTO v_id;

  RETURN json_build_object('success', true, 'id', v_id, 'event_time', v_now);
END;
$$;


-- 4. Submit an attendance regularisation request
CREATE OR REPLACE FUNCTION employee_submit_regularisation(
  p_attendance_date    DATE,
  p_correct_clock_in   TIMESTAMPTZ,
  p_correct_clock_out  TIMESTAMPTZ,
  p_reason             TEXT,
  p_original_clock_in  TIMESTAMPTZ DEFAULT NULL,
  p_original_clock_out TIMESTAMPTZ DEFAULT NULL
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

  INSERT INTO regularisation_requests (
    user_id, employee_id, attendance_date,
    correct_clock_in, correct_clock_out, reason,
    original_clock_in, original_clock_out, status
  ) VALUES (
    v_emp.user_id, v_emp.id, p_attendance_date,
    p_correct_clock_in, p_correct_clock_out, p_reason,
    p_original_clock_in, p_original_clock_out, 'Pending'
  ) RETURNING id INTO v_id;

  RETURN json_build_object('success', true, 'id', v_id);
END;
$$;
