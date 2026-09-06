#!/bin/sh
set -eu

# Hash the persisted migration, role, RLS, grant, and function catalog. The
# restart gate compares this value before and after recreating the containers.
"${DOCKER:-docker}" compose exec -T postgres psql \
  --username postgres \
  --dbname workloop \
  --tuples-only \
  --no-align \
  --set ON_ERROR_STOP=1 \
  --command "
WITH snapshot(value) AS (
  SELECT 'revision|' || version_num
  FROM public.alembic_version
  UNION ALL
  SELECT pg_catalog.format(
    'table|%s|%s|%s|%s',
    namespace.nspname,
    object.relname,
    object.relrowsecurity,
    object.relforcerowsecurity)
  FROM pg_catalog.pg_class AS object
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = object.relnamespace
  WHERE namespace.nspname = 'public' AND object.relkind IN ('r', 'p')
  UNION ALL
  SELECT pg_catalog.format(
    'policy|%s|%s|%s|%s|%s|%s',
    schemaname,
    tablename,
    policyname,
    cmd,
    COALESCE(qual, ''),
    COALESCE(with_check, ''))
  FROM pg_catalog.pg_policies
  WHERE schemaname = 'public'
  UNION ALL
  SELECT pg_catalog.format(
    'table-grant|%s|%s|%s', grantee, table_name, privilege_type)
  FROM information_schema.role_table_grants
  WHERE table_schema = 'public' AND grantee LIKE 'workloop_%'
  UNION ALL
  SELECT pg_catalog.format(
    'column-grant|%s|%s|%s|%s', grantee, table_name, column_name, privilege_type)
  FROM information_schema.role_column_grants
  WHERE table_schema = 'public' AND grantee LIKE 'workloop_%'
  UNION ALL
  SELECT pg_catalog.format(
    'function|%s|%s|%s|%s|%s|%s',
    procedure.oid::pg_catalog.regprocedure,
    pg_catalog.pg_get_userbyid(procedure.proowner),
    procedure.prosecdef,
    procedure.provolatile,
    COALESCE(procedure.proconfig::text, ''),
    COALESCE(procedure.proacl::text, ''))
  FROM pg_catalog.pg_proc AS procedure
  JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = procedure.pronamespace
  WHERE namespace.nspname = 'public'
  UNION ALL
  SELECT pg_catalog.format(
    'role|%s|%s|%s|%s|%s|%s|%s',
    rolname,
    rolsuper,
    rolinherit,
    rolcreaterole,
    rolcreatedb,
    rolcanlogin,
    rolbypassrls)
  FROM pg_catalog.pg_roles
  WHERE rolname LIKE 'workloop_%'
)
SELECT pg_catalog.md5(
  COALESCE(pg_catalog.string_agg(value, E'\\n' ORDER BY value), ''))
FROM snapshot;
"
