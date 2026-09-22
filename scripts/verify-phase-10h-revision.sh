#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-10h-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
compose run --rm migrate alembic -c /app/alembic.ini downgrade b4d7f9a2c816
head_hash="$(verify_revision head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade a1c3e5f7b902
test "$(verify_revision predecessor)" = "$head_hash"
compose run --rm migrate alembic -c /app/alembic.ini upgrade b4d7f9a2c816
test "$(verify_revision head)" = "$head_hash"
restore_head
trap - EXIT HUP INT TERM

echo "Phase 10H exact predecessor rollback and replay passed."
