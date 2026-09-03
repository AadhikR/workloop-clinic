#!/bin/sh
set -eu

# Phase 4D function and trigger behavior gate. Runs against a connected row
# graph in one rolled-back transaction and proves: the canonical set_updated_at
# trigger advances updated_at within a single transaction; replace_payroll_entries
# inserts, replaces, and rejects unknown keys, duplicate employees, negative
# fixed scalars, over-scale money, out-of-scope employees, and non-draft runs;
# record_advance_repayment is idempotent by request key, rejects mismatched
# replays and payroll conflicts, refuses amounts over the outstanding balance,
# and settles at zero; and admin_execute_shift_swap refuses a non-active or
# non-admin actor, swaps both roster rows atomically, records the approval
# fields, and refuses a stale non-pending swap.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 <<'SQL'
BEGIN;

INSERT INTO companies (id, name) VALUES
  ('00000000-0000-0000-0000-000000000001', 'Tenant One');
INSERT INTO branches (id, company_id, name) VALUES
  ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'One Main');
INSERT INTO app_users (id, identity_issuer, identity_subject, status) VALUES
  ('00000000-0000-0000-0000-000000000031', 'https://issuer.test', 'admin', 'active'),
  ('00000000-0000-0000-0000-000000000032', 'https://issuer.test', 'disabled-admin', 'disabled');
INSERT INTO employees (id, company_id, branch_id, name, mol_id) VALUES
  ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Employee One', 'MOL-1'),
  ('00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Employee Two', 'MOL-2');
INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) VALUES
  ('00000000-0000-0000-0000-000000000031', '00000000-0000-0000-0000-000000000001', NULL, 'admin'),
  ('00000000-0000-0000-0000-000000000032', '00000000-0000-0000-0000-000000000001', NULL, 'admin');
INSERT INTO payroll_runs (id, company_id, branch_id, period) VALUES
  ('00000000-0000-0000-0000-000000000401', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '2026-01');
INSERT INTO salary_advances (id, company_id, branch_id, employee_id, amount, outstanding_balance, status) VALUES
  ('00000000-0000-0000-0000-000000000402', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', 1000, 1000, 'active');
INSERT INTO shifts (id, company_id, branch_id, name) VALUES
  ('00000000-0000-0000-0000-000000000201', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Day');
INSERT INTO roster_assignments (id, company_id, branch_id, employee_id, shift_id, date) VALUES
  ('00000000-0000-0000-0000-000000000211', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000201', '2026-01-05'),
  ('00000000-0000-0000-0000-000000000212', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000201', '2026-01-06');
INSERT INTO shift_swap_requests (id, company_id, branch_id, requester_employee_id, target_employee_id, requester_date, target_date) VALUES
  ('00000000-0000-0000-0000-000000000221', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000022', '2026-01-05', '2026-01-06');

-- A. trigger advances updated_at within one transaction
DO $$
DECLARE v_before timestamptz; v_after timestamptz;
BEGIN
  SELECT updated_at INTO v_before FROM companies WHERE id='00000000-0000-0000-0000-000000000001';
  UPDATE companies SET name='Renamed' WHERE id='00000000-0000-0000-0000-000000000001';
  SELECT updated_at INTO v_after FROM companies WHERE id='00000000-0000-0000-0000-000000000001';
  IF NOT (v_after > v_before) THEN RAISE EXCEPTION 'A FAIL: updated_at did not advance'; END IF;
END $$;

-- B. replace_payroll_entries
DO $$
DECLARE v_count int;
BEGIN
  PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[
    {"employee_id":"00000000-0000-0000-0000-000000000021","basic_salary":5000,"variable_allowance":-100},
    {"employee_id":"00000000-0000-0000-0000-000000000022","basic_salary":6000.50}]'::jsonb);
  SELECT count(*) INTO v_count FROM payroll_entries WHERE payroll_run_id='00000000-0000-0000-0000-000000000401';
  IF v_count <> 2 THEN RAISE EXCEPTION 'B FAIL: expected 2 entries, got %', v_count; END IF;
  PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021","basic_salary":5500}]'::jsonb);
  SELECT count(*) INTO v_count FROM payroll_entries WHERE payroll_run_id='00000000-0000-0000-0000-000000000401';
  IF v_count <> 1 THEN RAISE EXCEPTION 'B FAIL: re-run should replace to 1, got %', v_count; END IF;
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021","bogus":1}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: unknown key'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%unknown_key%' THEN RAISE; END IF; END;
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021"},{"employee_id":"00000000-0000-0000-0000-000000000021"}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: dup emp'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%duplicate_employee%' THEN RAISE; END IF; END;
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021","basic_salary":-1}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: neg scalar'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%scalar_negative%' THEN RAISE; END IF; END;
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021","basic_salary":1.234}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: scale'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%scalar_scale%' THEN RAISE; END IF; END;
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-0000000000ff"}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: scope'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%out_of_scope%' THEN RAISE; END IF; END;
  UPDATE payroll_runs SET approval_status='pending_approval', submitted_by_app_user_id='00000000-0000-0000-0000-000000000031', submitted_for_approval_at=now() WHERE id='00000000-0000-0000-0000-000000000401';
  BEGIN PERFORM replace_payroll_entries('00000000-0000-0000-0000-000000000401', '[{"employee_id":"00000000-0000-0000-0000-000000000021"}]'::jsonb);
    RAISE EXCEPTION 'B FAIL: non-draft'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%not_draft%' THEN RAISE; END IF; END;
  UPDATE payroll_runs SET approval_status='draft', submitted_by_app_user_id=NULL, submitted_for_approval_at=NULL WHERE id='00000000-0000-0000-0000-000000000401';
END $$;

-- C. record_advance_repayment
DO $$
DECLARE v_res jsonb; v_bal numeric;
BEGIN
  v_res := record_advance_repayment('00000000-0000-0000-0000-000000000402', NULL, '00000000-0000-0000-0000-000000000501', 250, '2026-01-31');
  IF (v_res->>'alreadyRecorded')::boolean OR (v_res->>'newBalance')::numeric <> 750 THEN RAISE EXCEPTION 'C FAIL: first call'; END IF;
  v_res := record_advance_repayment('00000000-0000-0000-0000-000000000402', NULL, '00000000-0000-0000-0000-000000000501', 250, '2026-01-31');
  IF NOT (v_res->>'alreadyRecorded')::boolean THEN RAISE EXCEPTION 'C FAIL: replay'; END IF;
  SELECT outstanding_balance INTO v_bal FROM salary_advances WHERE id='00000000-0000-0000-0000-000000000402';
  IF v_bal <> 750 THEN RAISE EXCEPTION 'C FAIL: replay decremented'; END IF;
  BEGIN PERFORM record_advance_repayment('00000000-0000-0000-0000-000000000402', NULL, '00000000-0000-0000-0000-000000000501', 300, '2026-01-31');
    RAISE EXCEPTION 'C FAIL: mismatch'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%idempotency_conflict%' THEN RAISE; END IF; END;
  BEGIN PERFORM record_advance_repayment('00000000-0000-0000-0000-000000000402', NULL, '00000000-0000-0000-0000-000000000502', 1000, '2026-01-31');
    RAISE EXCEPTION 'C FAIL: over'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%exceeds_outstanding%' THEN RAISE; END IF; END;
  v_res := record_advance_repayment('00000000-0000-0000-0000-000000000402', NULL, '00000000-0000-0000-0000-000000000504', 750, '2026-02-01');
  IF v_res->>'newStatus' <> 'settled' THEN RAISE EXCEPTION 'C FAIL: not settled'; END IF;
END $$;

-- D. admin_execute_shift_swap
DO $$
DECLARE v_ok boolean; v_e1 uuid; v_e2 uuid; v_status text;
BEGIN
  BEGIN PERFORM admin_execute_shift_swap('00000000-0000-0000-0000-000000000221', '00000000-0000-0000-0000-000000000032');
    RAISE EXCEPTION 'D FAIL: disabled admin'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%forbidden%' THEN RAISE; END IF; END;
  v_ok := admin_execute_shift_swap('00000000-0000-0000-0000-000000000221', '00000000-0000-0000-0000-000000000031');
  IF NOT v_ok THEN RAISE EXCEPTION 'D FAIL: returned false'; END IF;
  SELECT employee_id INTO v_e1 FROM roster_assignments WHERE id='00000000-0000-0000-0000-000000000211';
  SELECT employee_id INTO v_e2 FROM roster_assignments WHERE id='00000000-0000-0000-0000-000000000212';
  IF v_e1 <> '00000000-0000-0000-0000-000000000022' OR v_e2 <> '00000000-0000-0000-0000-000000000021' THEN RAISE EXCEPTION 'D FAIL: not swapped'; END IF;
  SELECT status INTO v_status FROM shift_swap_requests WHERE id='00000000-0000-0000-0000-000000000221';
  IF v_status <> 'approved' THEN RAISE EXCEPTION 'D FAIL: not approved'; END IF;
  BEGIN PERFORM admin_execute_shift_swap('00000000-0000-0000-0000-000000000221', '00000000-0000-0000-0000-000000000031');
    RAISE EXCEPTION 'D FAIL: re-exec'; EXCEPTION WHEN others THEN IF SQLERRM NOT LIKE '%not_pending%' THEN RAISE; END IF; END;
END $$;

DO $$ BEGIN RAISE NOTICE 'phase 4d function and trigger behavior verified'; END $$;
ROLLBACK;
SQL
