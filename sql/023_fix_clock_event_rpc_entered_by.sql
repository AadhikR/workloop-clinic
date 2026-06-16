-- ============================================================
-- Migration 023: Fix employee_record_clock_event RPC type error
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- The RPC inserts `auth.uid()::TEXT` into clock_events.entered_by, which is
-- a UUID column. Postgres rejects this with:
--   column "entered_by" is of type uuid but expression is of type text
-- Every employee clock-in/out therefore fails this RPC and silently falls
-- back to a direct insert from the client (recordClockEvent in
-- attendanceStorage.js). Fix by removing the ::TEXT cast.

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
    RETURN json_build_object('success', false, 'error', 'Employee record not found');
  END IF;

  INSERT INTO clock_events (
    user_id, employee_id, event_type, event_time, method, entered_by, notes
  ) VALUES (
    v_emp.user_id, v_emp.id, p_event_type, v_now, 'EMPLOYEE_APP', auth.uid(), p_notes
  ) RETURNING id INTO v_id;

  RETURN json_build_object('success', true, 'id', v_id, 'event_time', v_now);
END;
$$;
