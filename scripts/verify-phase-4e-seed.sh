#!/bin/sh
set -eu

# Phase 4E synthetic-seed gate. Proves the fixture seed applies to the migrated
# database, is idempotent (a second run leaves the same 334 rows and the exact
# values and per-table counts), validates its own manifest, and cleans up. It
# runs as the migration identity, never as workloop_runtime, and touches only
# the two fixture tenants. It leaves the database empty so later cleanup checks
# still see zero rows.
#
# The migrate image must contain the current app package. CI builds it fresh; a
# local run needs "docker compose build migrate" first.

DOCKER="${DOCKER:-docker}"

seed() {
  "$DOCKER" compose --profile tools run --rm --entrypoint python migrate -m app.db.seed "$@"
}

seed                     # apply and validate
before="$(seed --validate-only --fingerprint)"
seed                     # second run must be a true no-op
after="$(seed --validate-only --fingerprint)"
if [ "$before" != "$after" ]; then
  echo "second seed application changed fixture values" >&2
  exit 1
fi

if "$DOCKER" compose run --rm --no-deps --entrypoint python backend -m app.db.seed \
  --validate-only >/tmp/workloop-runtime-seed.out 2>&1; then
  echo "workloop_runtime was allowed to run the seed" >&2
  exit 1
fi
if ! grep -q "must not run as the runtime role workloop_runtime" /tmp/workloop-runtime-seed.out; then
  echo "runtime refusal did not return the expected guard error" >&2
  exit 1
fi

seed --clean             # remove only the fixture rows

# The seed's cleanup transaction checks all 48 affected tables. This separate
# database check covers the identity roots that own every scoped child row.
remaining="$(
  "$DOCKER" compose exec -T postgres psql --username postgres --dbname workloop --tuples-only \
    --no-align --command "SELECT count(*) FROM companies UNION ALL SELECT count(*) FROM branches \
    UNION ALL SELECT count(*) FROM employees UNION ALL SELECT count(*) FROM app_users \
    UNION ALL SELECT count(*) FROM user_profiles;" | sort -u
)"
test "$remaining" = "0"

scan_paths="backend/app/db/seed/*.py backend/app/models/*.py backend/alembic/versions/*.py"
if grep -E -i -n "auth[[:space:]]*\.|storage[[:space:]]*\.|auth_user_id|service_role|supabase_admin|supabase_auth_admin|supabase_storage_admin|authenticator|dashboard_user" \
  $scan_paths; then
  echo "seed or migration contains a Supabase database dependency" >&2
  exit 1
fi
if grep -E -i -n "['\"](anon|authenticated)['\"]|(grant|revoke|set[[:space:]]+role|create[[:space:]]+role|alter[[:space:]]+role|drop[[:space:]]+role)[^;]*(anon|authenticated)" \
  $scan_paths; then
  echo "seed or migration contains a Supabase browser-role dependency" >&2
  exit 1
fi

echo "Phase 4E synthetic seed applied twice without change, refused runtime, and cleaned."
