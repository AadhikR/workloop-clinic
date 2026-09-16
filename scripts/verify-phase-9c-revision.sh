#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

revision_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-9c-revision.py "$1"
}

head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade f9b2c4d6e8a1
test "$(revision_hash predecessor)" = "$head_hash"
compose run --rm migrate
test "$(revision_hash head)" = "$head_hash"

echo "Phase 9C exact predecessor rollback and replay passed."
