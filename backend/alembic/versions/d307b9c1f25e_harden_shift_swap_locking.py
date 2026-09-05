"""Revalidate roster assignments after shift-swap locks are acquired.

Revision ID: d307b9c1f25e
Revises: c2f6a8b0e14d
Created: 2026-09-05 00:00:00.000000

A concurrent transaction can change a roster row after the function finds its
identifier but before the function acquires the row lock. Capture each locked
row and verify its employee, date, company, and branch before applying a swap.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d307b9c1f25e"
down_revision: str | Sequence[str] | None = "c2f6a8b0e14d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HARDENED_TWO_WAY = r"""
    SELECT id INTO v_tgt_id
    FROM public.roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date = v_swap.target_date
      AND company_id = v_swap.company_id
      AND branch_id = v_swap.branch_id;
    IF v_tgt_id IS NULL THEN
      RAISE EXCEPTION 'shift_swap_target_unassigned';
    END IF;

    -- Lock in stable UUID order and retain the current locked row versions.
    IF v_req_id < v_tgt_id THEN
      SELECT * INTO v_req_row FROM public.roster_assignments
        WHERE id = v_req_id FOR UPDATE;
      SELECT * INTO v_tgt_row FROM public.roster_assignments
        WHERE id = v_tgt_id FOR UPDATE;
    ELSE
      SELECT * INTO v_tgt_row FROM public.roster_assignments
        WHERE id = v_tgt_id FOR UPDATE;
      SELECT * INTO v_req_row FROM public.roster_assignments
        WHERE id = v_req_id FOR UPDATE;
    END IF;

    IF v_req_row.id IS NULL
       OR v_req_row.employee_id IS DISTINCT FROM v_swap.requester_employee_id
       OR v_req_row.date IS DISTINCT FROM v_swap.requester_date
       OR v_req_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_req_row.branch_id IS DISTINCT FROM v_swap.branch_id
       OR v_tgt_row.id IS NULL
       OR v_tgt_row.employee_id IS DISTINCT FROM v_swap.target_employee_id
       OR v_tgt_row.date IS DISTINCT FROM v_swap.target_date
       OR v_tgt_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_tgt_row.branch_id IS DISTINCT FROM v_swap.branch_id THEN
      RAISE EXCEPTION 'shift_swap_roster_changed';
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
        AND (
          (employee_id = v_swap.target_employee_id
             AND date = v_swap.requester_date AND id <> v_req_id)
          OR (employee_id = v_swap.requester_employee_id
             AND date = v_swap.target_date AND id <> v_tgt_id))
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
    UPDATE public.roster_assignments SET employee_id = v_swap.requester_employee_id
      WHERE id = v_tgt_id;
"""

PREVIOUS_TWO_WAY = r"""
    SELECT id INTO v_tgt_id
    FROM public.roster_assignments
    WHERE employee_id = v_swap.target_employee_id
      AND date = v_swap.target_date
      AND company_id = v_swap.company_id
      AND branch_id = v_swap.branch_id;
    IF v_tgt_id IS NULL THEN
      RAISE EXCEPTION 'shift_swap_target_unassigned';
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
        AND (
          (employee_id = v_swap.target_employee_id
             AND date = v_swap.requester_date AND id <> v_req_id)
          OR (employee_id = v_swap.requester_employee_id
             AND date = v_swap.target_date AND id <> v_tgt_id))
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    IF v_req_id < v_tgt_id THEN
      v_first := v_req_id; v_second := v_tgt_id;
    ELSE
      v_first := v_tgt_id; v_second := v_req_id;
    END IF;
    PERFORM 1 FROM public.roster_assignments WHERE id = v_first FOR UPDATE;
    PERFORM 1 FROM public.roster_assignments WHERE id = v_second FOR UPDATE;

    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
    UPDATE public.roster_assignments SET employee_id = v_swap.requester_employee_id
      WHERE id = v_tgt_id;
"""

HARDENED_ONE_WAY = r"""
    SELECT * INTO v_req_row FROM public.roster_assignments
      WHERE id = v_req_id FOR UPDATE;
    IF v_req_row.id IS NULL
       OR v_req_row.employee_id IS DISTINCT FROM v_swap.requester_employee_id
       OR v_req_row.date IS DISTINCT FROM v_swap.requester_date
       OR v_req_row.company_id IS DISTINCT FROM v_swap.company_id
       OR v_req_row.branch_id IS DISTINCT FROM v_swap.branch_id THEN
      RAISE EXCEPTION 'shift_swap_roster_changed';
    END IF;

    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE employee_id = v_swap.target_employee_id
        AND date = v_swap.requester_date
        AND company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
"""

PREVIOUS_ONE_WAY = r"""
    IF EXISTS (
      SELECT 1 FROM public.roster_assignments
      WHERE employee_id = v_swap.target_employee_id
        AND date = v_swap.requester_date
        AND company_id = v_swap.company_id
        AND branch_id = v_swap.branch_id
    ) THEN
      RAISE EXCEPTION 'shift_swap_destination_conflict';
    END IF;

    PERFORM 1 FROM public.roster_assignments WHERE id = v_req_id FOR UPDATE;
    UPDATE public.roster_assignments SET employee_id = v_swap.target_employee_id
      WHERE id = v_req_id;
"""


def _function_sql(*, hardened: bool) -> str:
    row_variables = (
        """
  v_req_row public.roster_assignments%ROWTYPE;
  v_tgt_row public.roster_assignments%ROWTYPE;"""
        if hardened
        else """
  v_first   uuid;
  v_second  uuid;"""
    )
    two_way = HARDENED_TWO_WAY if hardened else PREVIOUS_TWO_WAY
    one_way = HARDENED_ONE_WAY if hardened else PREVIOUS_ONE_WAY
    return rf"""
CREATE OR REPLACE FUNCTION public.admin_execute_shift_swap(
  p_swap_id uuid, p_actor_app_user_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public, pg_temp
AS $$
DECLARE
  v_swap    public.shift_swap_requests%ROWTYPE;
  v_req_id  uuid;
  v_tgt_id  uuid;{row_variables}
BEGIN
  SELECT * INTO v_swap FROM public.shift_swap_requests
    WHERE id = p_swap_id FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'shift_swap_not_found';
  END IF;
  IF v_swap.status <> 'pending' THEN
    RAISE EXCEPTION 'shift_swap_not_pending';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM public.user_profiles up
    JOIN public.app_users au ON au.id = up.app_user_id
    WHERE up.app_user_id = p_actor_app_user_id
      AND up.company_id = v_swap.company_id
      AND up.role = 'admin'
      AND au.status = 'active'
  ) THEN
    RAISE EXCEPTION 'shift_swap_forbidden';
  END IF;

  IF v_swap.requester_employee_id = v_swap.target_employee_id THEN
    RAISE EXCEPTION 'shift_swap_same_employee';
  END IF;

  SELECT id INTO v_req_id
  FROM public.roster_assignments
  WHERE employee_id = v_swap.requester_employee_id
    AND date = v_swap.requester_date
    AND company_id = v_swap.company_id
    AND branch_id = v_swap.branch_id;
  IF v_req_id IS NULL THEN
    RAISE EXCEPTION 'shift_swap_requester_unassigned';
  END IF;

  IF v_swap.target_date IS NOT NULL THEN
    IF v_swap.requester_date = v_swap.target_date THEN
      RAISE EXCEPTION 'shift_swap_same_day';
    END IF;
{two_way}
  ELSE
{one_way}
  END IF;

  UPDATE public.shift_swap_requests
  SET status = 'approved',
      admin_approved_at = now(),
      admin_approved_by_app_user_id = p_actor_app_user_id,
      rejection_reason = ''
  WHERE id = p_swap_id;

  RETURN true;
END;
$$;
"""


def upgrade() -> None:
    op.execute(_function_sql(hardened=True))
    op.execute("REVOKE EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) FROM PUBLIC")


def downgrade() -> None:
    op.execute(_function_sql(hardened=False))
    op.execute("REVOKE EXECUTE ON FUNCTION public.admin_execute_shift_swap(uuid, uuid) FROM PUBLIC")
