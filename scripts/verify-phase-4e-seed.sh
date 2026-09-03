#!/bin/sh
set -eu

# Phase 4E synthetic-seed gate. Proves the fixture seed applies to the migrated
# database, is idempotent (a second run leaves the same 79 rows and the exact
# per-table counts), validates its own manifest, and cleans up to nothing. It
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
seed                     # second run must stay idempotent and revalidate
seed --validate-only     # counts and ids still match with no new writes
seed --clean             # remove only the fixture rows

remaining="$(
  "$DOCKER" compose exec -T postgres psql --username postgres --dbname workloop --tuples-only \
    --no-align --command "SELECT count(*) FROM employees UNION ALL SELECT count(*) FROM companies \
    UNION ALL SELECT count(*) FROM payroll_entries;" | sort -u
)"
if [ "$remaining" != "0" ]; then
  echo "seed cleanup left rows behind: $remaining" >&2
  exit 1
fi

echo "Phase 4E synthetic seed applied, revalidated, and cleaned."
