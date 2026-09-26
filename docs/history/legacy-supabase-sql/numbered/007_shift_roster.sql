-- 007_shift_roster.sql: Shift Scheduling & Roster (Feature 8)
-- Run in Supabase SQL Editor

-- ── 1. Add color column to existing shifts table ───────────────────────────────
ALTER TABLE shifts ADD COLUMN IF NOT EXISTS color TEXT DEFAULT '#6366f1';

-- ── 2. Roster assignments: one shift per employee per calendar day ─────────────
CREATE TABLE IF NOT EXISTS roster_assignments (
  id          UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID        NOT NULL REFERENCES auth.users(id)  ON DELETE CASCADE,
  employee_id UUID        NOT NULL REFERENCES employees(id)   ON DELETE CASCADE,
  shift_id    UUID        NOT NULL REFERENCES shifts(id)      ON DELETE CASCADE,
  date        DATE        NOT NULL,
  published   BOOLEAN     NOT NULL DEFAULT false,
  notes       TEXT        NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  -- One shift per employee per day
  UNIQUE (employee_id, date)
);

ALTER TABLE roster_assignments ENABLE ROW LEVEL SECURITY;

-- Admin: full access (owns the company's data)
CREATE POLICY "roster_assignments_admin_all"
  ON roster_assignments FOR ALL
  USING (user_id = auth.uid());

-- Employee: read their own published assignments
CREATE POLICY "roster_assignments_employee_read"
  ON roster_assignments FOR SELECT
  USING (
    published = true
    AND EXISTS (
      SELECT 1 FROM employees e
      WHERE e.id = roster_assignments.employee_id
        AND e.auth_user_id = auth.uid()
    )
  );

-- ── 3. Shift swap requests ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shift_swap_requests (
  id                    UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id               UUID        NOT NULL REFERENCES auth.users(id)  ON DELETE CASCADE,
  requester_employee_id UUID        NOT NULL REFERENCES employees(id)   ON DELETE CASCADE,
  target_employee_id    UUID        NOT NULL REFERENCES employees(id)   ON DELETE CASCADE,
  requester_date        DATE        NOT NULL,
  target_date           DATE,
  reason                TEXT        NOT NULL DEFAULT '',
  status                TEXT        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','approved','rejected','cancelled')),
  admin_approved_at     TIMESTAMPTZ,
  admin_approved_by     TEXT        NOT NULL DEFAULT '',
  rejection_reason      TEXT        NOT NULL DEFAULT '',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE shift_swap_requests ENABLE ROW LEVEL SECURITY;

-- Admin: full access
CREATE POLICY "shift_swap_requests_admin_all"
  ON shift_swap_requests FOR ALL
  USING (user_id = auth.uid());

-- Employee: read swap requests they are involved in (as requester or target)
CREATE POLICY "shift_swap_requests_employee_read"
  ON shift_swap_requests FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM employees e
      WHERE e.auth_user_id = auth.uid()
        AND e.id IN (requester_employee_id, target_employee_id)
    )
  );

-- ── 4. RPC: employee reads own published roster for a date range ───────────────
CREATE OR REPLACE FUNCTION employee_get_my_roster(
  p_date_from DATE,
  p_date_to   DATE
)
RETURNS TABLE (
  id             UUID,
  shift_id       UUID,
  date           DATE,
  published      BOOLEAN,
  notes          TEXT,
  shift_name     TEXT,
  shift_color    TEXT,
  start_time     TEXT,
  end_time       TEXT,
  expected_hours NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_employee_id UUID;
BEGIN
  SELECT e.id INTO v_employee_id
  FROM employees e
  WHERE e.auth_user_id = auth.uid()
  LIMIT 1;

  IF v_employee_id IS NULL THEN RETURN; END IF;

  RETURN QUERY
  SELECT
    ra.id,
    ra.shift_id,
    ra.date,
    ra.published,
    ra.notes,
    s.name          AS shift_name,
    COALESCE(s.color, '#6366f1') AS shift_color,
    s.start_time,
    s.end_time,
    s.expected_hours
  FROM roster_assignments ra
  JOIN shifts s ON s.id = ra.shift_id
  WHERE ra.employee_id = v_employee_id
    AND ra.date BETWEEN p_date_from AND p_date_to
    AND ra.published = true
  ORDER BY ra.date;
END;
$$;

-- ── 5. RPC: employee gets a list of colleagues (for swap requests) ─────────────
CREATE OR REPLACE FUNCTION employee_get_colleagues()
RETURNS TABLE (id UUID, name TEXT, job_title TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_admin_user_id UUID;
  v_employee_id   UUID;
BEGIN
  SELECT e.id, e.user_id
  INTO v_employee_id, v_admin_user_id
  FROM employees e
  WHERE e.auth_user_id = auth.uid()
  LIMIT 1;

  IF v_employee_id IS NULL THEN RETURN; END IF;

  RETURN QUERY
  SELECT e.id, e.name, e.job_title
  FROM employees e
  WHERE e.user_id = v_admin_user_id
    AND e.id != v_employee_id
    AND LOWER(COALESCE(e.employment_status, 'active')) != 'terminated'
  ORDER BY e.name;
END;
$$;

-- ── 6. RPC: employee submits a shift swap request ─────────────────────────────
CREATE OR REPLACE FUNCTION employee_request_shift_swap(
  p_target_employee_id UUID,
  p_requester_date     DATE,
  p_target_date        DATE    DEFAULT NULL,
  p_reason             TEXT    DEFAULT ''
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_employee_id   UUID;
  v_admin_user_id UUID;
BEGIN
  SELECT e.id, e.user_id
  INTO v_employee_id, v_admin_user_id
  FROM employees e
  WHERE e.auth_user_id = auth.uid()
  LIMIT 1;

  IF v_employee_id IS NULL THEN
    RETURN json_build_object('success', false, 'error', 'Employee record not found');
  END IF;

  INSERT INTO shift_swap_requests (
    user_id, requester_employee_id, target_employee_id,
    requester_date, target_date, reason, status
  ) VALUES (
    v_admin_user_id,
    v_employee_id,
    p_target_employee_id,
    p_requester_date,
    p_target_date,
    p_reason,
    'pending'
  );

  RETURN json_build_object('success', true);
END;
$$;
