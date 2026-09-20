#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

revision_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-9e-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
compose run --rm migrate alembic -c /app/alembic.ini downgrade f4b8d2e6a901
head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade c5e7a9b1d3f4
test "$(revision_hash predecessor)" = "$head_hash"
compose run --rm migrate alembic -c /app/alembic.ini upgrade f4b8d2e6a901
test "$(revision_hash head)" = "$head_hash"
restore_head
trap - EXIT HUP INT TERM

echo "Phase 9E exact predecessor rollback and replay passed."
