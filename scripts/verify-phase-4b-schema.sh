#!/bin/sh
set -eu

"${DOCKER:-docker}" compose exec -T postgres psql --username postgres --dbname workloop --set ON_ERROR_STOP=1 \
  --command "
BEGIN;
DO \$\$
DECLARE
  table_count integer;
BEGIN
  SELECT count(*) INTO table_count
  FROM pg_tables
  WHERE schemaname = 'public'
    AND tablename IN ('companies', 'branches', 'employees', 'app_users', 'user_profiles');
  IF table_count <> 5 THEN
    RAISE EXCEPTION 'expected five Phase 4B tables, found %', table_count;
  END IF;

  INSERT INTO companies (id, name) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Company One'),
    ('00000000-0000-0000-0000-000000000002', 'Company Two');
  INSERT INTO branches (id, company_id, name) VALUES
    ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'Main'),
    ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000002', 'Other');
  INSERT INTO employees (id, company_id, branch_id, name, mol_id, work_email) VALUES
    ('00000000-0000-0000-0000-000000000021', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Employee One', 'MOL-1', 'employee@example.test');
  INSERT INTO app_users (id, identity_issuer, identity_subject, status) VALUES
    ('00000000-0000-0000-0000-000000000031', 'https://issuer.test', 'employee-subject', 'active'),
    ('00000000-0000-0000-0000-000000000032', 'https://issuer.test', 'admin-subject', 'active'),
    ('00000000-0000-0000-0000-000000000033', 'https://issuer.test', 'manager-subject', 'active');
  INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) VALUES
    ('00000000-0000-0000-0000-000000000031', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000021', 'employee');
  INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) VALUES
    ('00000000-0000-0000-0000-000000000032', '00000000-0000-0000-0000-000000000001', NULL, 'admin');

  BEGIN
    INSERT INTO employees (id, company_id, branch_id, name, mol_id)
    VALUES ('00000000-0000-0000-0000-000000000022', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000012', 'Cross Scope', 'MOL-2');
    RAISE EXCEPTION 'cross-company branch reference was accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO employees (id, company_id, branch_id, name, mol_id, work_email)
    VALUES ('00000000-0000-0000-0000-000000000023', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000011', 'Duplicate Email', 'MOL-3', ' EMPLOYEE@example.test ');
    RAISE EXCEPTION 'duplicate normalized work email was accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
  BEGIN
    INSERT INTO user_profiles (app_user_id, company_id, employee_id, role)
    VALUES ('00000000-0000-0000-0000-000000000033', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000021', 'manager');
    RAISE EXCEPTION 'duplicate employee profile was accepted';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END
\$\$;
SET ROLE workloop_runtime;
DO \$\$
BEGIN
  -- The four identity tables keep the Phase 3 read-only grant after Phase 4D:
  -- the runtime reads them but cannot write them. Branch and business write
  -- grants added in Phase 4D are proven by scripts/verify-phase-4d-grants.sh.
  PERFORM count(*) FROM app_users;
  BEGIN
    INSERT INTO companies (id) VALUES ('00000000-0000-0000-0000-000000000041');
    RAISE EXCEPTION 'workloop_runtime unexpectedly has identity write access';
  EXCEPTION WHEN insufficient_privilege THEN NULL;
  END;
END
\$\$;
RESET ROLE;
ROLLBACK;
"
