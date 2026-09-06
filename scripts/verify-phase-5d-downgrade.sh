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
  IF current_revision <> 'd307b9c1f25e' THEN
    RAISE EXCEPTION 'unexpected downgrade revision %', current_revision;
  END IF;

  SELECT pg_catalog.count(*) INTO mismatch_count
  FROM pg_catalog.pg_proc AS procedure
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
  WHERE namespace.nspname = 'public'
    AND procedure.proname IN (
      'workloop_identity_issuer',
      'workloop_identity_subject',
      'workloop_app_user_id',
      'workloop_role',
      'workloop_company_id',
      'workloop_employee_id',
      'workloop_branch_id',
      'workloop_actor_kind',
      'workloop_actor_key',
      'workloop_business_date'
    );
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5D downgrade left context readers behind';
  END IF;

  SELECT pg_catalog.count(*) INTO mismatch_count
  FROM pg_catalog.pg_roles
  WHERE rolname = 'workloop_runtime'
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls);
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5D downgrade changed runtime role attributes';
  END IF;

  SELECT pg_catalog.count(*) INTO mismatch_count
  FROM pg_catalog.pg_auth_members AS membership
  JOIN pg_catalog.pg_roles AS member ON member.oid = membership.member
  WHERE member.rolname = 'workloop_runtime';
  IF mismatch_count <> 0 THEN
    RAISE EXCEPTION 'Phase 5D downgrade left runtime role membership';
  END IF;

  IF pg_catalog.has_schema_privilege('workloop_runtime', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'Phase 5D downgrade granted schema creation';
  END IF;
END
\$\$;
"

echo "Phase 5D exact downgrade removed its readers and preserved runtime boundaries."
