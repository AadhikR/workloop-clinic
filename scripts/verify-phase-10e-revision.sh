#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-10e-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
compose run --rm migrate alembic -c /app/alembic.ini downgrade c9e5a7d1f642
head_hash="$(verify_revision head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade f2d4a8c6b901
test "$(verify_revision predecessor)" = "$head_hash"
compose run --rm migrate alembic -c /app/alembic.ini upgrade c9e5a7d1f642
test "$(verify_revision head)" = "$head_hash"
restore_head
trap - EXIT HUP INT TERM

echo "Phase 10E exact predecessor rollback and replay passed."
