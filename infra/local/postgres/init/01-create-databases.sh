#!/bin/sh
set -eu

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv workloop_migration_password WORKLOOP_MIGRATION_PASSWORD
\getenv workloop_runtime_password WORKLOOP_RUNTIME_PASSWORD
\getenv workloop_expiry_processing_password WORKLOOP_EXPIRY_PROCESSING_PASSWORD
\getenv workloop_storage_reconciler_password WORKLOOP_STORAGE_RECONCILER_PASSWORD
\getenv workloop_file_scanner_password WORKLOOP_FILE_SCANNER_PASSWORD
\getenv keycloak_db_password KEYCLOAK_DB_PASSWORD

CREATE ROLE workloop_migration LOGIN PASSWORD :'workloop_migration_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE workloop_runtime LOGIN PASSWORD :'workloop_runtime_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE workloop_expiry_processing LOGIN PASSWORD :'workloop_expiry_processing_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE workloop_storage_reconciler LOGIN PASSWORD :'workloop_storage_reconciler_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE workloop_file_scanner LOGIN PASSWORD :'workloop_file_scanner_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE keycloak LOGIN PASSWORD :'keycloak_db_password' NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE DATABASE workloop OWNER workloop_migration;
CREATE DATABASE keycloak OWNER keycloak;

REVOKE ALL PRIVILEGES ON DATABASE postgres FROM PUBLIC;
REVOKE ALL PRIVILEGES ON DATABASE workloop FROM PUBLIC;
REVOKE ALL PRIVILEGES ON DATABASE keycloak FROM PUBLIC;

GRANT CONNECT ON DATABASE workloop TO workloop_migration;
GRANT CONNECT, TEMPORARY ON DATABASE workloop TO workloop_runtime;
GRANT CONNECT ON DATABASE workloop TO workloop_expiry_processing;
GRANT CONNECT ON DATABASE workloop TO workloop_storage_reconciler;
GRANT CONNECT ON DATABASE workloop TO workloop_file_scanner;
GRANT CONNECT ON DATABASE keycloak TO keycloak;
SQL

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname workloop <<'SQL'
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO workloop_migration;
ALTER DEFAULT PRIVILEGES FOR ROLE workloop_migration IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE workloop_migration IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE workloop_migration IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
SET ROLE workloop_migration;
CREATE EXTENSION IF NOT EXISTS btree_gist;
RESET ROLE;
DO $$
DECLARE
  signature pg_catalog.regprocedure;
BEGIN
  FOR signature IN
    SELECT procedure.oid::pg_catalog.regprocedure
    FROM pg_catalog.pg_depend dependency
    JOIN pg_catalog.pg_extension extension ON extension.oid = dependency.refobjid
    JOIN pg_catalog.pg_proc procedure ON procedure.oid = dependency.objid
    WHERE dependency.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass
      AND dependency.refclassid = 'pg_catalog.pg_extension'::pg_catalog.regclass
      AND dependency.deptype = 'e'
      AND extension.extname = 'btree_gist'
  LOOP
    EXECUTE pg_catalog.format('ALTER FUNCTION %s OWNER TO workloop_migration', signature);
    EXECUTE pg_catalog.format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', signature);
    EXECUTE pg_catalog.format(
      'GRANT EXECUTE ON FUNCTION %s TO workloop_migration, workloop_runtime, '
      'workloop_expiry_processing, workloop_file_scanner, workloop_storage_reconciler',
      signature
    );
  END LOOP;
END
$$;
SQL

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname keycloak <<'SQL'
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO keycloak;
ALTER DEFAULT PRIVILEGES FOR ROLE keycloak IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE keycloak IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE keycloak IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
SQL
