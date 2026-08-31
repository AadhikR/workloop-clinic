#!/bin/sh
set -eu

psql() {
  docker compose exec -T postgres psql --username postgres --dbname workloop "$@"
}

psql --set ON_ERROR_STOP=1 --command "
SELECT CASE WHEN count(*) = 4 THEN 1 ELSE 0 END
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('companies', 'employees', 'app_users', 'user_profiles');
" | grep -q '1'

psql --set ON_ERROR_STOP=1 --command "
SELECT CASE WHEN count(*) = 2 THEN 1 ELSE 0 END
FROM pg_type
WHERE typname IN ('account_status', 'app_role');
" | grep -q '1'

psql --set ON_ERROR_STOP=1 --command "
SELECT CASE WHEN bool_and(tableowner = 'workloop_migration') THEN 1 ELSE 0 END
FROM pg_tables
WHERE schemaname = 'public';
" | grep -q '1'

psql --set ON_ERROR_STOP=1 --command "
BEGIN;
INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000001');
INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000002');
INSERT INTO employees (id, company_id)
VALUES ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001');
INSERT INTO app_users (id, identity_issuer, identity_subject, status)
VALUES ('00000000-0000-0000-0000-000000000021', 'https://issuer.test', 'opaque-subject', 'active');
INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'employee');
DO \$\$
BEGIN
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
  BEGIN
    INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
    VALUES ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000011', 'employee');
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
ROLLBACK;
"

psql --set ON_ERROR_STOP=1 --command "
SET ROLE workloop_runtime;
SELECT count(*) FROM app_users;
" >/dev/null

if psql --set ON_ERROR_STOP=1 --command "
SET ROLE workloop_runtime;
INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000031');
" >/dev/null 2>&1; then
  echo 'workloop_runtime unexpectedly has write access' >&2
  exit 1
fi
