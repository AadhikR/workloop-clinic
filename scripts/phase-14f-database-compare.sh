#!/bin/sh
set -eu

case "${COMPOSE_PROJECT_NAME:-}" in
  workloop-phase14f-source|workloop-phase14f-restore) ;;
  *) echo "comparison requires an exact Phase 14F project" >&2; exit 1 ;;
esac

keycloak_url=${WORKLOOP_KEYCLOAK_BASE_URL:-}
[ -n "$keycloak_url" ] || { echo "Keycloak base URL is required" >&2; exit 1; }

query() {
  database=$1
  sql=$2
  docker compose exec -T postgres psql --username postgres --dbname "$database" \
    --tuples-only --no-align --set ON_ERROR_STOP=1 --command "$sql"
}

table_counts() {
  database=$1
  query "$database" "
CREATE TEMP TABLE phase14f_counts(name text PRIMARY KEY, row_count bigint NOT NULL);
DO \$\$
DECLARE item record; item_count bigint;
BEGIN
  FOR item IN
    SELECT schemaname, tablename FROM pg_catalog.pg_tables
    WHERE schemaname = 'public' ORDER BY tablename
  LOOP
    EXECUTE pg_catalog.format('SELECT count(*) FROM %I.%I', item.schemaname, item.tablename)
      INTO item_count;
    INSERT INTO phase14f_counts VALUES (item.tablename, item_count);
  END LOOP;
END \$\$;
SELECT name || '|' || row_count FROM phase14f_counts ORDER BY name;
" | sed '/^CREATE TABLE$/d;/^DO$/d'
}

workloop_counts=$(table_counts workloop)
keycloak_counts=$(table_counts keycloak)
workloop_total=$(printf '%s\n' "$workloop_counts" | awk -F '|' '{ total += $2 } END { print total + 0 }')
keycloak_total=$(printf '%s\n' "$keycloak_counts" | awk -F '|' '{ total += $2 } END { print total + 0 }')
workloop_digest=$(printf '%s\n' "$workloop_counts" | sha256sum | cut -d ' ' -f 1)
keycloak_digest=$(printf '%s\n' "$keycloak_counts" | sha256sum | cut -d ' ' -f 1)
workloop_identity=$(query workloop "SELECT count(*) FROM public.companies; SELECT count(*) FROM public.branches; SELECT count(*) FROM public.employees; SELECT count(*) FROM public.app_users; SELECT count(*) FROM public.user_profiles;" | paste -sd ':' -)
keycloak_identity=$(query keycloak "SELECT count(*) FROM public.user_entity;")
signing_digest=$(curl --fail --silent --show-error "$keycloak_url/realms/workloop-dev/protocol/openid-connect/certs" \
  | jq -r '.keys[].kid' | sort | sha256sum | cut -d ' ' -f 1)
head=$(query workloop "SELECT version_num FROM public.alembic_version;")

printf 'alembic-head|%s\n' "$head"
printf 'workloop-identity-count|%s\n' "$workloop_identity"
printf 'workloop-row-count|%s\n' "$workloop_total"
printf 'workloop-row-count-digest|sha256:%s\n' "$workloop_digest"
printf 'keycloak-identity-count|%s\n' "$keycloak_identity"
printf 'keycloak-row-count|%s\n' "$keycloak_total"
printf 'keycloak-row-count-digest|sha256:%s\n' "$keycloak_digest"
printf 'signing-key-id-digest|sha256:%s\n' "$signing_digest"
