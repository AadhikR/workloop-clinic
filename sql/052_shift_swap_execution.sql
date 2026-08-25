-- 052_shift_swap_execution.sql
-- Atomic execution of an approved shift swap.
--
-- Motivation: prior to this migration, updateShiftSwapRequest() flipped the
-- request status to 'approved' without touching the underlying
-- roster_assignments rows. Managers thought they had actioned the swap; the
-- roster (and downstream attendance / payroll) still showed the original
-- pairing. This RPC performs the two-row swap in one transaction with the
-- proper pre-flight checks and returns TRUE on success.
--
-- Semantics of the swap ("date × shift keeps its slot, the person changes"):
--   Before: (requester, requester_date) works shift A
--           (target,    target_date)    works shift B
--   After:  (target,    requester_date) works shift A
--           (requester, target_date)    works shift B
--
-- One-way coverage (target_date IS NULL): the requester's shift on
-- requester_date transfers to the target; requester ends up unassigned that
-- day.
--
-- Idempotent: safe to re-run in the Supabase SQL Editor.

DROP FUNCTION IF EXISTS admin_execute_shift_swap(UUID);

CREATE OR REPLACE FUNCTION admin_execute_shift_swap(p_swap_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_swap        shift_swap_requests%ROWTYPE;
  v_req_row_id  UUID;
  v_tgt_row_id  UUID;
  v_conflict    INT;
BEGIN
  -- Load and lock the swap; only the admin that owns the row may execute it.
  SELECT * INTO v_swap
  FROM shift_swap_requests
  WHERE id      = p_swap_id
    AND user_id = auth.uid()
  FOR UPDATE;

  IF v_swap.id IS NULL THEN
    RAISE EXCEPTION 'Swap request not found or not owned by this admin.';
  END IF;
  IF v_swap.status <> 'pending' THEN
    RAISE EXCEPTION 'Only pending swap requests can be approved (current: %).', v_swap.status;
  END IF;
  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN
    RAISE EXCEPTION 'A swap request cannot pair an employee with themselves.';
  END IF;

  -- The requester's original assignment must exist — that row is what gets
  -- reassigned to the target employee.
  SELECT id INTO v_req_row_id
  FROM roster_assignments
  WHERE employee_id = v_swap.requester_employee_id
    AND date        = v_swap.requester_date
  FOR UPDATE;

  IF v_req_row_id IS NULL THEN
    RAISE EXCEPTION 'Requester has no roster assignment on %.', v_swap.requester_date;
  END IF;

  IF v_swap.target_date IS NOT NULL THEN
    -- Two-way swap.
    IF v_swap.requester_date = v_swap.target_date THEN
      -- Same-day swap conflicts with UNIQUE(employee_id, date) during the
      -- intermediate step of a two-statement update. We keep this constraint
      -- explicit until the callers actually need same-day pairings.
      RAISE EXCEPTION 'Same-day swaps are not supported yet.';
    END IF;

    SELECT id INTO v_tgt_row_id
    FROM roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date        = v_swap.target_date
    FOR UPDATE;

    IF v_tgt_row_id IS NULL THEN
      RAISE EXCEPTION 'Target has no roster assignment on %.', v_swap.target_date;
    END IF;

    -- Double-book guard: neither employee may already own the other's slot.
    SELECT COUNT(*) INTO v_conflict
    FROM roster_assignments
    WHERE (employee_id = v_swap.target_employee_id    AND date = v_swap.requester_date AND id <> v_req_row_id)
       OR (employee_id = v_swap.requester_employee_id AND date = v_swap.target_date    AND id <> v_tgt_row_id);
    IF v_conflict > 0 THEN
      RAISE EXCEPTION 'Swap would double-book one of the employees on the swap dates.';
    END IF;

    -- Two independent UPDATEs — order doesn't matter because the pre-check
    -- above proves neither destination is already occupied.
    UPDATE roster_assignments
       SET employee_id = v_swap.target_employee_id
     WHERE id = v_req_row_id;

    UPDATE roster_assignments
       SET employee_id = v_swap.requester_employee_id
     WHERE id = v_tgt_row_id;
  ELSE
    -- One-way coverage: hand the requester's shift to the target.
    SELECT COUNT(*) INTO v_conflict
    FROM roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date        = v_swap.requester_date;
    IF v_conflict > 0 THEN
      RAISE EXCEPTION 'Target is already scheduled on %.', v_swap.requester_date;
    END IF;

    UPDATE roster_assignments
       SET employee_id = v_swap.target_employee_id
     WHERE id = v_req_row_id;
  END IF;

  UPDATE shift_swap_requests
     SET status            = 'approved',
         admin_approved_at = NOW(),
         admin_approved_by = COALESCE(
           (SELECT email FROM auth.users WHERE id = auth.uid()),
           ''
         ),
         rejection_reason  = ''
   WHERE id = p_swap_id;

  RETURN TRUE;
END;
$$;

REVOKE ALL ON FUNCTION admin_execute_shift_swap(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION admin_execute_shift_swap(UUID) TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
