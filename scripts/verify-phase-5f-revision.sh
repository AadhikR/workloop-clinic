#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: verify-phase-5f-revision.sh REVISION" >&2
  exit 2
fi

"${DOCKER:-docker}" compose \
  -f docker-compose.yml \
  -f docker-compose.phase5f.yml \
  --profile tools run --rm --no-deps \
  --volume ./scripts:/verification:ro \
  --entrypoint python migrate \
  /verification/verify-phase-5f-revision.py "$1"
