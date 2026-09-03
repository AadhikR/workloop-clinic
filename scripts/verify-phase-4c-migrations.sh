#!/bin/sh
set -eu

# Per-domain Alembic round-trip gate for Phase 4C. Confirms every domain
# revision applies and reverts independently on an empty database, that the full
# chain rebuilds from base with no metadata drift, and that the recorded head is
# the records revision. Run against the local Compose stack.

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

# base -> head is the ordered domain chain, oldest first.
CHAIN="a4b7e2c91d05 3f9a1c7b2e10 4a0b2d8c3f21 5b1c3e9d4a32 6c2d4f0e5b43 7d3e5a1f6c54"
HEAD="7d3e5a1f6c54"

# Full teardown and rebuild from empty. Pinned to the 4C head so later Phase 4D
# revisions on top of it do not perturb this per-domain 4C round-trip.
alembic_cmd downgrade base >/dev/null
alembic_cmd upgrade "$HEAD" >/dev/null
assert_current "$HEAD"

# Step every domain revision down to base one at a time, then back up, checking
# the recorded position after each move so a broken downgrade cannot hide.
for revision in 6c2d4f0e5b43 5b1c3e9d4a32 4a0b2d8c3f21 3f9a1c7b2e10 a4b7e2c91d05 base; do
  alembic_cmd downgrade "$revision" >/dev/null
  if [ "$revision" != "base" ]; then
    assert_current "$revision"
  fi
done

for revision in $CHAIN; do
  alembic_cmd upgrade "$revision" >/dev/null
  assert_current "$revision"
done

# Restore the full head so downstream Phase 4D grant and function checks run
# against a fully migrated database. alembic check also requires the database to
# be at head before it will diff the metadata.
alembic_cmd upgrade head >/dev/null

if ! alembic_cmd check 2>&1 | grep -q "No new upgrade operations detected"; then
  echo "metadata drift detected after per-domain round-trip" >&2
  exit 1
fi

echo "Phase 4C per-domain migration round-trip passed."
