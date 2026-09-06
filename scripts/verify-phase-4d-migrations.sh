#!/bin/sh
set -eu

# Per-concern Alembic round-trip gate for Phase 4D. Confirms each Phase 4D
# revision applies and reverts
# independently on top of the Phase 4C head with no metadata drift, and that the
# recorded Phase 4D head includes the security corrections. Leaves the database
# at the current project head. Run against the local Compose stack.

DOCKER="${DOCKER:-docker}"

alembic_cmd() {
  "$DOCKER" compose --profile tools run --rm migrate alembic "$@"
}

current_revision() {
  alembic_cmd current 2>/dev/null | tail -n 1 | cut -d' ' -f1
}

assert_current() {
  actual="$(current_revision)"
  if [ "$actual" != "$1" ]; then
    echo "expected revision $1, found ${actual:-<none>}" >&2
    exit 1
  fi
}

C_HEAD="7d3e5a1f6c54"
# Phase 4D chain on top of the 4C head, oldest first.
CHAIN="8e2b6a4c1f07 9f3c7b5d2a18 a0d4e6f8c92b b1e5f7a9d03c c2f6a8b0e14d d307b9c1f25e"
PHASE_4D_HEAD="d307b9c1f25e"
PROJECT_HEAD="d85a6f0c3b42"

alembic_cmd upgrade head >/dev/null
assert_current "$PROJECT_HEAD"
alembic_cmd downgrade "$PHASE_4D_HEAD" >/dev/null
assert_current "$PHASE_4D_HEAD"

# Step every Phase 4D revision down to the 4C head one at a time, then back up,
# checking the recorded position after each move so a broken downgrade or a
# grant left dangling cannot hide.
for revision in c2f6a8b0e14d b1e5f7a9d03c a0d4e6f8c92b 9f3c7b5d2a18 8e2b6a4c1f07 "$C_HEAD"; do
  alembic_cmd downgrade "$revision" >/dev/null
  assert_current "$revision"
done

for revision in $CHAIN; do
  alembic_cmd upgrade "$revision" >/dev/null
  assert_current "$revision"
done

alembic_cmd upgrade head >/dev/null
assert_current "$PROJECT_HEAD"

if ! alembic_cmd check 2>&1 | grep -q "No new upgrade operations detected"; then
  echo "metadata drift detected after Phase 4D round-trip" >&2
  exit 1
fi

echo "Phase 4D per-concern migration round-trip passed."
