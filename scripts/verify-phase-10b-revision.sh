#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-10b-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
head_hash="$(verify_revision head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade f4b8d2e6a901
test "$(verify_revision predecessor)" = "$head_hash"
restore_head
test "$(verify_revision head)" = "$head_hash"
trap - EXIT HUP INT TERM

echo "Phase 10B exact predecessor rollback and replay passed."
