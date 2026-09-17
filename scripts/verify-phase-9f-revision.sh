#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

revision_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-9f-revision.py "$1"
}

head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade d7f1b3c5e9a2
test "$(revision_hash predecessor)" = "$head_hash"
compose run --rm migrate
test "$(revision_hash head)" = "$head_hash"

echo "Phase 9F exact predecessor rollback and replay passed."
