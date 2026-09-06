#!/bin/sh
set -eu

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop \
  --set ON_ERROR_STOP=1 --command "
DO \$\$
DECLARE
  mismatch_count integer;
  current_revision text;
BEGIN
  SELECT version_num INTO current_revision FROM public.alembic_version;
  IF current_revision <> 'e418c0d7a6b3' THEN
    RAISE EXCEPTION 'unexpected downgrade revision %', current_revision;
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_policies
  WHERE schemaname = 'public' AND policyname LIKE 'phase5e_%';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left policies behind';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_class AS table_object
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = table_object.relnamespace
  WHERE namespace.nspname = 'public'
    AND table_object.relname IN (
      'companies', 'branches', 'app_users', 'user_profiles', 'employees',
      'employee_job_history', 'departments', 'department_staffing_rules'
    )
    AND (table_object.relrowsecurity OR table_object.relforcerowsecurity);
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left row security enabled';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_proc AS procedure
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
  WHERE namespace.nspname = 'public'
    AND procedure.proname IN (
      'resolve_workloop_principal', 'is_scoped_active_app_user'
    );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left a helper behind';
  END IF;

  IF has_table_privilege('workloop_runtime', 'companies', 'UPDATE')
     OR has_table_privilege('workloop_runtime', 'branches', 'DELETE')
     OR has_table_privilege('workloop_runtime', 'employees', 'INSERT')
     OR has_table_privilege('workloop_runtime', 'employees', 'UPDATE')
     OR has_column_privilege('workloop_runtime', 'user_profiles', 'role', 'UPDATE')
     OR has_table_privilege('workloop_runtime', 'departments', 'DELETE')
     OR has_table_privilege(
       'workloop_runtime', 'department_staffing_rules', 'DELETE'
     ) THEN
    RAISE EXCEPTION 'Phase 5E downgrade left a runtime grant change behind';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM information_schema.column_privileges
  WHERE grantee = 'workloop_expiry_processing' AND table_schema = 'public';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left expiry table access behind';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_proc AS procedure
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
  WHERE namespace.nspname = 'public'
    AND pg_catalog.has_function_privilege(
      'workloop_expiry_processing', procedure.oid, 'EXECUTE'
    );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left expiry function access behind';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_namespace AS namespace
  CROSS JOIN LATERAL pg_catalog.aclexplode(namespace.nspacl) AS acl
  WHERE namespace.nspname = 'public'
    AND pg_catalog.pg_get_userbyid(acl.grantee) = 'workloop_expiry_processing';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade left an explicit expiry schema grant behind';
  END IF;

  SELECT count(*) INTO mismatch_count
  FROM pg_catalog.pg_roles
  WHERE rolname IN ('workloop_runtime', 'workloop_expiry_processing')
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5E downgrade changed protected role attributes';
  END IF;
END
\$\$;
"

echo "Phase 5E downgrade removed its policies, grants, helpers, and RLS flags."
