#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-10c-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
compose run --rm migrate alembic -c /app/alembic.ini downgrade b7d9e1f3a5c6
head_hash="$(verify_revision head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade a6c8e0f2b4d7
test "$(verify_revision predecessor)" = "$head_hash"
compose run --rm migrate alembic -c /app/alembic.ini upgrade b7d9e1f3a5c6
test "$(verify_revision head)" = "$head_hash"
restore_head
trap - EXIT HUP INT TERM

echo "Phase 10C exact predecessor rollback and replay passed."
