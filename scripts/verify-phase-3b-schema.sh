#!/bin/sh
set -eu

docker compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 \
  --command "
BEGIN;
DO \$\$
DECLARE
  table_count integer;
  type_count integer;
  migration_owns_tables boolean;
BEGIN
  SELECT count(*) INTO table_count
  FROM pg_tables
  WHERE schemaname = 'public'
    AND tablename IN ('companies', 'employees', 'app_users', 'user_profiles');
  IF table_count <> 4 THEN
    RAISE EXCEPTION 'expected four identity tables, found %', table_count;
  END IF;

  SELECT count(*) INTO type_count
  FROM pg_type
  WHERE typname IN ('account_status', 'app_role');
  IF type_count <> 2 THEN
    RAISE EXCEPTION 'expected two identity enums, found %', type_count;
  END IF;

  SELECT bool_and(tableowner = 'workloop_migration') INTO migration_owns_tables
  FROM pg_tables
  WHERE schemaname = 'public';
  IF migration_owns_tables IS NOT TRUE THEN
    RAISE EXCEPTION 'workloop_migration does not own every public table';
  END IF;

  INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000001');
  INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000002');
  INSERT INTO employees (id, company_id)
  VALUES ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001');
  INSERT INTO app_users (id, identity_issuer, identity_subject, status)
  VALUES ('00000000-0000-0000-0000-000000000021', 'https://issuer.test', 'opaque-subject', 'active');
  INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
  VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'employee');

  BEGIN
    INSERT INTO app_users (id, identity_issuer, identity_subject)
    VALUES ('00000000-0000-0000-0000-000000000022', 'https://issuer.test', 'opaque-subject');
    RAISE EXCEPTION 'duplicate identity was accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO app_users (id, identity_issuer, identity_subject, status)
    VALUES ('00000000-0000-0000-0000-000000000023', 'https://issuer.test', 'another-subject', 'invalid');
    RAISE EXCEPTION 'invalid status was accepted';
  EXCEPTION WHEN invalid_text_representation THEN NULL;
  END;
  BEGIN
    INSERT INTO user_profiles (app_user_id, company_id, role)
    VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', 'invalid');
    RAISE EXCEPTION 'invalid role was accepted';
  EXCEPTION WHEN invalid_text_representation THEN NULL;
  END;
  INSERT INTO app_users (id, identity_issuer, identity_subject)
  VALUES ('00000000-0000-0000-0000-000000000024', 'https://issuer.test', 'admin-subject');
  BEGIN
    INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
    VALUES ('00000000-0000-0000-0000-000000000024', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'admin');
    RAISE EXCEPTION 'invalid role and employee link was accepted';
  EXCEPTION WHEN check_violation THEN NULL;
  END;
  INSERT INTO app_users (id, identity_issuer, identity_subject)
  VALUES ('00000000-0000-0000-0000-000000000025', 'https://issuer.test', 'cross-company-subject');
  BEGIN
    INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
    VALUES ('00000000-0000-0000-0000-000000000025', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000011', 'employee');
    RAISE EXCEPTION 'cross-company employee link was accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  BEGIN
    DELETE FROM companies WHERE id = '00000000-0000-0000-0000-000000000001';
    RAISE EXCEPTION 'referenced company was deleted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
END
\$\$;
SET ROLE workloop_runtime;
SELECT count(*) FROM app_users;
DO \$\$
BEGIN
  BEGIN
    INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000031');
    RAISE EXCEPTION 'workloop_runtime unexpectedly has write access';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END
\$\$;
ROLLBACK;
"
