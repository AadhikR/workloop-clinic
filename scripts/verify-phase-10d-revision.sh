#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-10d-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
head_hash="$(verify_revision head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade b7d9e1f3a5c6
test "$(verify_revision predecessor)" = "$head_hash"
restore_head
test "$(verify_revision head)" = "$head_hash"
trap - EXIT HUP INT TERM

echo "Phase 10D exact predecessor rollback and replay passed."
