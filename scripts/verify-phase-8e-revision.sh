#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

revision_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-8e-revision.py "$1"
}

phase8d_hash() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-8d-revision.py "$1"
}

head_hash="$(revision_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade a83d5e7c1b29
test "$(revision_hash predecessor)" = "$head_hash"

phase8d_head_hash="$(phase8d_hash head)"
compose run --rm migrate alembic -c /app/alembic.ini downgrade 4d8a7c2e9f31
test "$(phase8d_hash predecessor)" = "$phase8d_head_hash"
compose run --rm migrate alembic -c /app/alembic.ini downgrade 8f6b2d1a4c70
sh scripts/verify-phase-7g-revision.sh

compose run --rm migrate
test "$(revision_hash head)" = "$head_hash"

echo "Phase 8E, Phase 8D, and Phase 7G audit wrapper predecessor downgrades passed."
