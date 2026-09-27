\set ON_ERROR_STOP on
\connect workloop

DO $$
DECLARE
  unexpected integer;
  role_name text;
  role_names text[] := ARRAY[
    'workloop_migration',
    'workloop_runtime',
    'workloop_expiry_processing',
    'workloop_file_scanner',
    'workloop_storage_reconciler',
    'keycloak'
  ];
BEGIN
  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_roles
  WHERE rolname = ANY(role_names)
    AND (
      NOT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole
      OR rolreplication OR rolbypassrls
    );
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'a Phase 14C login role has elevated attributes';
  END IF;

  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_auth_members memberships
  JOIN pg_catalog.pg_roles member ON member.oid = memberships.member
  JOIN pg_catalog.pg_roles granted ON granted.oid = memberships.roleid
  WHERE member.rolname = ANY(role_names) OR granted.rolname = ANY(role_names);
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'a Phase 14C login role has role membership';
  END IF;

  IF has_database_privilege('public', 'workloop', 'CONNECT')
     OR has_database_privilege('public', 'workloop', 'TEMPORARY')
     OR has_schema_privilege('public', 'public', 'USAGE')
     OR has_schema_privilege('public', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'PUBLIC retains database or schema privileges';
  END IF;

  FOREACH role_name IN ARRAY role_names LOOP
    IF role_name = 'keycloak' THEN
      IF has_database_privilege(role_name, 'workloop', 'CONNECT') THEN
        RAISE EXCEPTION 'Keycloak can connect to the application database';
      END IF;
    ELSIF NOT has_database_privilege(role_name, 'workloop', 'CONNECT') THEN
      RAISE EXCEPTION '% lacks its explicit application database connection', role_name;
    END IF;
  END LOOP;

  IF has_database_privilege('workloop_migration', 'keycloak', 'CONNECT')
     OR has_database_privilege('workloop_runtime', 'keycloak', 'CONNECT')
     OR has_database_privilege('workloop_expiry_processing', 'keycloak', 'CONNECT')
     OR has_database_privilege('workloop_file_scanner', 'keycloak', 'CONNECT')
     OR has_database_privilege('workloop_storage_reconciler', 'keycloak', 'CONNECT') THEN
    RAISE EXCEPTION 'an application role can connect to the Keycloak database';
  END IF;

  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_default_acl defaults
  JOIN pg_catalog.pg_roles owner ON owner.oid = defaults.defaclrole
  CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) acl
  WHERE owner.rolname IN ('workloop_migration', 'keycloak') AND acl.grantee = 0;
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'PUBLIC retains an owner default privilege';
  END IF;

  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_class objects
  JOIN pg_catalog.pg_namespace namespace ON namespace.oid = objects.relnamespace
  CROSS JOIN LATERAL pg_catalog.aclexplode(
    coalesce(objects.relacl, pg_catalog.acldefault(
      CASE WHEN objects.relkind = 'S' THEN 'S'::"char" ELSE 'r'::"char" END,
      objects.relowner
    ))
  ) acl
  WHERE namespace.nspname = 'public'
    AND objects.relkind IN ('r', 'p', 'S')
    AND acl.grantee = 0;
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'PUBLIC retains a table or sequence privilege';
  END IF;

  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_proc functions
  JOIN pg_catalog.pg_namespace namespace ON namespace.oid = functions.pronamespace
  CROSS JOIN LATERAL pg_catalog.aclexplode(
    coalesce(functions.proacl, pg_catalog.acldefault('f', functions.proowner))
  ) acl
  WHERE namespace.nspname = 'public' AND acl.grantee = 0;
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'PUBLIC retains a function privilege';
  END IF;

  IF has_table_privilege('workloop_expiry_processing', 'public.file_security_scans', 'SELECT')
     OR has_table_privilege('workloop_file_scanner', 'public.companies', 'SELECT')
     OR has_table_privilege('workloop_storage_reconciler', 'public.companies', 'SELECT')
     OR has_function_privilege(
       'workloop_runtime',
       'public.append_storage_recovery_audit(uuid,uuid,text,uuid,text)',
       'EXECUTE'
     )
     OR has_function_privilege(
       'workloop_file_scanner',
       'public.file_security_scan_allows_download(uuid,text,uuid,text,text,bigint,text,text)',
       'EXECUTE'
     ) THEN
    RAISE EXCEPTION 'a cross-role application operation is allowed';
  END IF;
END
$$;

\connect keycloak

DO $$
DECLARE
  unexpected integer;
BEGIN
  IF has_database_privilege('public', 'keycloak', 'CONNECT')
     OR has_database_privilege('public', 'keycloak', 'TEMPORARY')
     OR has_schema_privilege('public', 'public', 'USAGE')
     OR has_schema_privilege('public', 'public', 'CREATE') THEN
    RAISE EXCEPTION 'PUBLIC retains a Keycloak database or schema privilege';
  END IF;

  IF NOT has_database_privilege('keycloak', 'keycloak', 'CONNECT') THEN
    RAISE EXCEPTION 'Keycloak lacks its explicit database connection';
  END IF;

  SELECT count(*) INTO unexpected
  FROM pg_catalog.pg_default_acl defaults
  JOIN pg_catalog.pg_roles owner ON owner.oid = defaults.defaclrole
  CROSS JOIN LATERAL pg_catalog.aclexplode(defaults.defaclacl) acl
  WHERE owner.rolname = 'keycloak' AND acl.grantee = 0;
  IF unexpected <> 0 THEN
    RAISE EXCEPTION 'PUBLIC retains a Keycloak default privilege';
  END IF;
END
$$;
