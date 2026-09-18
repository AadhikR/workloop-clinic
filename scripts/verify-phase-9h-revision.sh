#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose --profile tools "$@"
}

verify_revision() {
  compose run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python migrate \
    /verification/verify-phase-9h-revision.py "$1"
}

restore_head() {
  compose run --rm migrate
}

trap restore_head EXIT HUP INT TERM
verify_revision head
compose run --rm migrate alembic -c /app/alembic.ini downgrade e3a7c9d1f5b2
verify_revision predecessor
restore_head
verify_revision head
trap - EXIT HUP INT TERM

echo "Phase 9H exact predecessor rollback and replay passed."
