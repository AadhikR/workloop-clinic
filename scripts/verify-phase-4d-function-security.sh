#!/bin/sh
set -eu

# Prove the retained functions keep the catalog first and the caller's
# temporary schema last. Each attack case shadows the first business table a
# definer function reads. The function must still report that the fixture does
# not exist in public.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 \
  --command "
BEGIN;
DO \$\$
DECLARE
  function_name text;
  function_config text[];
  mismatch_count integer;
BEGIN
  WITH expected(signature, security_definer) AS (
    VALUES
      ('set_updated_at()', false),
      ('replace_payroll_entries(uuid, jsonb)', true),
      ('record_advance_repayment(uuid, uuid, uuid, numeric, date)', true),
      ('admin_execute_shift_swap(uuid, uuid)', true)
  ), actual AS (
    SELECT p.proname || '(' || pg_catalog.oidvectortypes(p.proargtypes) || ')' AS signature,
           p.prosecdef AS security_definer
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.proname IN (
        'set_updated_at',
        'replace_payroll_entries',
        'record_advance_repayment',
        'admin_execute_shift_swap'
      )
  )
  SELECT count(*) INTO mismatch_count
  FROM (
    (SELECT * FROM expected EXCEPT SELECT * FROM actual)
    UNION ALL
    (SELECT * FROM actual EXCEPT SELECT * FROM expected)
  ) differences;

  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'retained public function set or SECURITY DEFINER state differs';
  END IF;

  FOREACH function_name IN ARRAY ARRAY[
    'set_updated_at',
    'replace_payroll_entries',
    'record_advance_repayment',
    'admin_execute_shift_swap'
  ] LOOP
    SELECT proconfig INTO function_config
    FROM pg_catalog.pg_proc
    WHERE oid = CASE function_name
      WHEN 'set_updated_at' THEN 'set_updated_at()'::regprocedure
      WHEN 'replace_payroll_entries' THEN
        'replace_payroll_entries(uuid,jsonb)'::regprocedure
      WHEN 'record_advance_repayment' THEN
        'record_advance_repayment(uuid,uuid,uuid,numeric,date)'::regprocedure
      ELSE 'admin_execute_shift_swap(uuid,uuid)'::regprocedure
    END;
    IF function_config <> ARRAY['search_path=pg_catalog, public, pg_temp'] THEN
      RAISE EXCEPTION '% has unsafe configuration: %', function_name, function_config;
    END IF;
    IF pg_catalog.pg_get_userbyid((
      SELECT proowner FROM pg_catalog.pg_proc
      WHERE oid = CASE function_name
        WHEN 'set_updated_at' THEN 'set_updated_at()'::regprocedure
        WHEN 'replace_payroll_entries' THEN
          'replace_payroll_entries(uuid,jsonb)'::regprocedure
        WHEN 'record_advance_repayment' THEN
          'record_advance_repayment(uuid,uuid,uuid,numeric,date)'::regprocedure
        ELSE 'admin_execute_shift_swap(uuid,uuid)'::regprocedure
      END
    )) <> 'workloop_migration' THEN
      RAISE EXCEPTION '% has the wrong owner', function_name;
    END IF;
  END LOOP;
END
\$\$;

SET ROLE workloop_runtime;
CREATE TEMP TABLE payroll_runs (
  id uuid, status text, approval_status text, company_id uuid, branch_id uuid
);
CREATE TEMP TABLE salary_advances (
  id uuid, company_id uuid, branch_id uuid, status text, outstanding_balance numeric
);
CREATE TEMP TABLE shift_swap_requests (
  id uuid, company_id uuid, branch_id uuid, requester_employee_id uuid,
  target_employee_id uuid, requester_date date, target_date date, status text
);
GRANT SELECT, UPDATE ON payroll_runs, salary_advances, shift_swap_requests
  TO workloop_migration;

INSERT INTO payroll_runs VALUES (
  '00000000-0000-0000-0000-000000000801', 'draft', 'draft',
  '00000000-0000-0000-0000-000000000802',
  '00000000-0000-0000-0000-000000000803'
);
INSERT INTO salary_advances VALUES (
  '00000000-0000-0000-0000-000000000804',
  '00000000-0000-0000-0000-000000000802',
  '00000000-0000-0000-0000-000000000803', 'active', 100
);
INSERT INTO shift_swap_requests VALUES (
  '00000000-0000-0000-0000-000000000805',
  '00000000-0000-0000-0000-000000000802',
  '00000000-0000-0000-0000-000000000803',
  '00000000-0000-0000-0000-000000000806',
  '00000000-0000-0000-0000-000000000807',
  '2026-09-05', '2026-09-06', 'pending'
);

DO \$\$
BEGIN
  BEGIN
    PERFORM replace_payroll_entries(
      '00000000-0000-0000-0000-000000000801', '[]'::jsonb
    );
    RAISE EXCEPTION 'replace_payroll_entries accepted a temporary shadow row';
  EXCEPTION WHEN others THEN
    IF SQLERRM NOT LIKE '%payroll_run_not_found%' THEN RAISE; END IF;
  END;

  BEGIN
    PERFORM record_advance_repayment(
      '00000000-0000-0000-0000-000000000804', NULL,
      '00000000-0000-0000-0000-000000000808', 10, '2026-09-05'
    );
    RAISE EXCEPTION 'record_advance_repayment accepted a temporary shadow row';
  EXCEPTION WHEN others THEN
    IF SQLERRM NOT LIKE '%advance_repayment_advance_not_found%' THEN RAISE; END IF;
  END;

  BEGIN
    PERFORM admin_execute_shift_swap(
      '00000000-0000-0000-0000-000000000805',
      '00000000-0000-0000-0000-000000000809'
    );
    RAISE EXCEPTION 'admin_execute_shift_swap accepted a temporary shadow row';
  EXCEPTION WHEN others THEN
    IF SQLERRM NOT LIKE '%shift_swap_not_found%' THEN RAISE; END IF;
  END;
END
\$\$;
RESET ROLE;
ROLLBACK;
"

echo "Phase 4D function search paths resist temporary-table shadowing."
