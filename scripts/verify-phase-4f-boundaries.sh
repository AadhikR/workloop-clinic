#!/bin/sh
set -eu

# Phase 4F live-database boundary gate. Run after an empty database reaches
# Alembic head. It checks the target server, migration ownership, runtime role,
# absence of Supabase database objects, and no row security outside the
# tables approved through Phase 5G.

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
DO \$\$
DECLARE
  mismatch_count integer;
  database_owner text;
BEGIN
  IF current_setting('server_version_num')::integer <> 170011 THEN
    RAISE EXCEPTION 'expected PostgreSQL 17.11, found %', version();
  END IF;

  SELECT pg_catalog.pg_get_userbyid(datdba) INTO database_owner
  FROM pg_catalog.pg_database WHERE datname = current_database();
  IF database_owner <> 'workloop_migration' THEN
    RAISE EXCEPTION 'workloop database owner is %, not workloop_migration', database_owner;
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_roles
  WHERE rolname IN (
    'anon', 'authenticated', 'service_role', 'supabase_admin',
    'supabase_auth_admin', 'supabase_storage_admin', 'authenticator', 'dashboard_user'
  );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'fresh cluster contains a Supabase role';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_namespace
  WHERE nspname IN ('auth', 'storage');
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'migrated database contains an auth or storage schema';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_roles
  WHERE rolname IN ('workloop_migration', 'workloop_runtime')
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'a Workloop database role has an elevated role attribute';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_auth_members memberships
  JOIN pg_catalog.pg_roles member_role ON member_role.oid = memberships.member
  JOIN pg_catalog.pg_roles granted_role ON granted_role.oid = memberships.roleid
  WHERE member_role.rolname IN ('workloop_migration', 'workloop_runtime')
     OR granted_role.rolname IN ('workloop_migration', 'workloop_runtime');
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'a Workloop database role has an unexpected role membership';
  END IF;

  IF has_schema_privilege('workloop_runtime', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'workloop_runtime can create objects in public';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_class objects
  JOIN pg_catalog.pg_namespace schemas ON schemas.oid = objects.relnamespace
  WHERE schemas.nspname = 'public'
    AND objects.relkind IN ('r', 'p', 'S', 'v', 'm')
    AND pg_catalog.pg_get_userbyid(objects.relowner) <> 'workloop_migration';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'a public relation is not owned by workloop_migration';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_type types
  JOIN pg_catalog.pg_namespace schemas ON schemas.oid = types.typnamespace
  WHERE schemas.nspname = 'public'
    AND types.typtype = 'e'
    AND pg_catalog.pg_get_userbyid(types.typowner) <> 'workloop_migration';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'a public enum is not owned by workloop_migration';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_class tables
  JOIN pg_catalog.pg_namespace schemas ON schemas.oid = tables.relnamespace
  WHERE schemas.nspname = 'public'
    AND tables.relkind IN ('r', 'p')
    AND tables.relrowsecurity
    AND tables.relname NOT IN (
      'companies', 'branches', 'app_users', 'user_profiles', 'employees',
      'employee_job_history', 'departments', 'department_staffing_rules',
      'payroll_runs', 'payroll_entries', 'payslips', 'payroll_approval_log',
      'nafis_reports', 'salary_advances', 'advance_repayments', 'expense_claims',
      'compliance_overrides', 'leave_settings', 'leave_types', 'public_holidays',
      'leave_requests', 'leave_audit_log', 'leave_balances',
      'leave_approval_delegates', 'attendance_settings', 'shifts',
      'shift_assignments', 'clock_events', 'attendance_records',
      'attendance_periods', 'regularisation_requests', 'attendance_audit_log',
      'roster_assignments', 'shift_swap_requests', 'biometric_mappings',
      'employee_documents', 'insurance_policies', 'employee_insurance',
      'insurance_dependants', 'notifications', 'employee_contracts',
      'offboarding_checklists', 'offboarding_tasks',
      'offboarding_task_templates', 'assets', 'asset_assignments',
      'training_records', 'certifications', 'appraisal_cycles', 'appraisals',
      'appraisal_sections', 'cme_requirements', 'incident_reports',
      'letter_requests', 'audit_events'
    );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'row-level security is enabled outside the approved Phase 5 tables';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_proc functions
  JOIN pg_catalog.pg_namespace schemas ON schemas.oid = functions.pronamespace
  WHERE schemas.nspname = 'public'
    AND functions.prokind = 'f'
    AND (
      CASE WHEN functions.prokind = 'f'
        THEN pg_catalog.pg_get_functiondef(functions.oid)
        ELSE ''
      END ~* '(auth|storage)[[:space:]]*\.'
      OR CASE WHEN functions.prokind = 'f'
        THEN pg_catalog.pg_get_functiondef(functions.oid)
        ELSE ''
      END ~* '\m(anon|authenticated|service_role|supabase_admin|supabase_auth_admin|supabase_storage_admin|authenticator|dashboard_user)\M'
    );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'a retained function contains a Supabase database dependency';
  END IF;

  RAISE NOTICE 'Phase 4F live database boundaries hold';
END
\$\$;
"

echo "Phase 4F PostgreSQL version, ownership, role, RLS, and Supabase boundaries passed."
