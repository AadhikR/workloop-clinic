#!/bin/sh
set -eu

run_migration() {
  "${DOCKER:-docker}" compose --profile tools run --rm migrate \
    alembic -c /app/alembic.ini "$@"
}

run_revision_check() {
  "${DOCKER:-docker}" compose --profile tools run --rm --no-deps \
    --volume ./scripts:/verification:ro --entrypoint python migrate \
    /verification/verify-phase-5g-revision.py "$1"
}

run_revision_check d85a6f0c3b42
run_migration upgrade e96f7a1b4c53
run_revision_check e96f7a1b4c53
run_migration upgrade f07a8b2c5d64
run_revision_check f07a8b2c5d64
run_migration upgrade 0a18c3d6e75f
run_revision_check 0a18c3d6e75f
run_migration upgrade 1b29d4e7f860
run_revision_check 1b29d4e7f860

for parent in 0a18c3d6e75f f07a8b2c5d64 e96f7a1b4c53 d85a6f0c3b42; do
  run_migration downgrade "$parent"
  run_revision_check "$parent"
  run_migration upgrade 1b29d4e7f860
  run_revision_check 1b29d4e7f860
done
