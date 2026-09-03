#!/bin/sh
set -eu

# Phase 4D grant-boundary gate. Proves workloop_runtime holds exactly the
# least-privilege matrix the grant revision declares and nothing more: the
# four identity tables stay read-only, the SELECT-only and append-only classes
# withhold the writes they should, operational tables allow only
# SELECT/INSERT/UPDATE, no table anywhere allows DELETE or TRUNCATE, the three
# retained business functions are executable while the trigger helper is not,
# and a live runtime session is refused an ungranted write. Everything runs in
# one transaction and rolls back.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 \
  --command "
BEGIN;
DO \$\$
DECLARE
  r text;
  identity_tables text[] := ARRAY['companies','employees','app_users','user_profiles'];
  select_only text[] := ARRAY['advance_repayments'];
  append_only text[] := ARRAY['employee_job_history','payslips','payroll_approval_log',
    'compliance_overrides','leave_audit_log','clock_events','attendance_audit_log',
    'employee_contracts'];
  operational text[] := ARRAY['branches','departments','department_staffing_rules',
    'payroll_runs','payroll_entries','nafis_reports','salary_advances','expense_claims',
    'leave_settings','leave_types','public_holidays','leave_requests','leave_balances',
    'leave_approval_delegates','attendance_settings','shifts','shift_assignments',
    'attendance_records','attendance_periods','regularisation_requests','roster_assignments',
    'shift_swap_requests','biometric_mappings','employee_documents','insurance_policies',
    'employee_insurance','insurance_dependants','notifications','offboarding_checklists',
    'offboarding_tasks','offboarding_task_templates','assets','asset_assignments',
    'training_records','certifications','appraisal_cycles','appraisals','appraisal_sections',
    'cme_requirements','incident_reports','letter_requests'];
  all_business text[];
BEGIN
  all_business := select_only || append_only || operational;
  IF array_length(all_business, 1) <> 50 THEN
    RAISE EXCEPTION 'expected 50 business tables in matrix, got %', array_length(all_business, 1);
  END IF;

  -- Identity tables: SELECT only, no writes.
  FOREACH r IN ARRAY identity_tables LOOP
    IF NOT has_table_privilege('workloop_runtime', r, 'SELECT') THEN
      RAISE EXCEPTION '% : identity SELECT missing', r; END IF;
    IF has_table_privilege('workloop_runtime', r, 'INSERT')
       OR has_table_privilege('workloop_runtime', r, 'UPDATE')
       OR has_table_privilege('workloop_runtime', r, 'DELETE') THEN
      RAISE EXCEPTION '% : identity table unexpectedly writable', r; END IF;
  END LOOP;

  -- SELECT-only business tables.
  FOREACH r IN ARRAY select_only LOOP
    IF NOT has_table_privilege('workloop_runtime', r, 'SELECT') THEN
      RAISE EXCEPTION '% : SELECT missing', r; END IF;
    IF has_table_privilege('workloop_runtime', r, 'INSERT')
       OR has_table_privilege('workloop_runtime', r, 'UPDATE')
       OR has_table_privilege('workloop_runtime', r, 'DELETE') THEN
      RAISE EXCEPTION '% : SELECT-only table unexpectedly writable', r; END IF;
  END LOOP;

  -- Append-only: SELECT + INSERT, never UPDATE or DELETE.
  FOREACH r IN ARRAY append_only LOOP
    IF NOT has_table_privilege('workloop_runtime', r, 'SELECT')
       OR NOT has_table_privilege('workloop_runtime', r, 'INSERT') THEN
      RAISE EXCEPTION '% : append-only SELECT/INSERT missing', r; END IF;
    IF has_table_privilege('workloop_runtime', r, 'UPDATE')
       OR has_table_privilege('workloop_runtime', r, 'DELETE') THEN
      RAISE EXCEPTION '% : append-only table unexpectedly mutable', r; END IF;
  END LOOP;

  -- Operational: SELECT + INSERT + UPDATE, never DELETE.
  FOREACH r IN ARRAY operational LOOP
    IF NOT has_table_privilege('workloop_runtime', r, 'SELECT')
       OR NOT has_table_privilege('workloop_runtime', r, 'INSERT')
       OR NOT has_table_privilege('workloop_runtime', r, 'UPDATE') THEN
      RAISE EXCEPTION '% : operational SELECT/INSERT/UPDATE missing', r; END IF;
    IF has_table_privilege('workloop_runtime', r, 'DELETE') THEN
      RAISE EXCEPTION '% : operational table unexpectedly deletable', r; END IF;
  END LOOP;

  -- No business table grants DELETE or TRUNCATE.
  FOREACH r IN ARRAY all_business LOOP
    IF has_table_privilege('workloop_runtime', r, 'DELETE')
       OR has_table_privilege('workloop_runtime', r, 'TRUNCATE') THEN
      RAISE EXCEPTION '% : unexpected DELETE/TRUNCATE grant', r; END IF;
  END LOOP;

  -- Function execute grants.
  IF NOT has_function_privilege('workloop_runtime', 'replace_payroll_entries(uuid, jsonb)', 'EXECUTE')
     OR NOT has_function_privilege('workloop_runtime', 'record_advance_repayment(uuid, uuid, uuid, numeric, date)', 'EXECUTE')
     OR NOT has_function_privilege('workloop_runtime', 'admin_execute_shift_swap(uuid, uuid)', 'EXECUTE') THEN
    RAISE EXCEPTION 'business function execute grant missing';
  END IF;
  IF has_function_privilege('workloop_runtime', 'set_updated_at()', 'EXECUTE') THEN
    RAISE EXCEPTION 'set_updated_at unexpectedly executable by runtime';
  END IF;

  RAISE NOTICE 'grant matrix matches least-privilege declaration';
END
\$\$;

-- Live enforcement: a runtime session may read a granted table but is refused
-- an ungranted DELETE and an ungranted identity INSERT.
SET ROLE workloop_runtime;
DO \$\$
BEGIN
  PERFORM count(*) FROM leave_requests;   -- granted SELECT, must succeed
  BEGIN
    DELETE FROM departments;
    RAISE EXCEPTION 'runtime unexpectedly deleted from departments';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
  BEGIN
    INSERT INTO companies (id, name) VALUES (gen_random_uuid(), 'x');
    RAISE EXCEPTION 'runtime unexpectedly inserted into companies';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
  RAISE NOTICE 'runtime session enforcement holds';
END
\$\$;
RESET ROLE;
ROLLBACK;
"
