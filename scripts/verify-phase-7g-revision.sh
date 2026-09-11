#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

revision_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-7g-revision.py "$1"
}

head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade 7d4a9c2e6b10
predecessor_hash="$(revision_hash predecessor)"
test "$head_hash" = "$predecessor_hash"
compose run --rm migrate alembic -c /app/alembic.ini upgrade 8f6b2d1a4c70
test "$(revision_hash head)" = "$head_hash"

echo "Phase 7G audit wrapper and exact predecessor downgrade passed."
