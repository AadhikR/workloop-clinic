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

head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade c5e7a9b1d3f4
test "$(revision_hash predecessor)" = "$head_hash"
compose run --rm migrate
test "$(revision_hash head)" = "$head_hash"

echo "Phase 9E exact predecessor rollback and replay passed."
