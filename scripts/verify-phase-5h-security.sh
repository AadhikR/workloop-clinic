#!/bin/sh
set -eu

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-workloop-phase5h-verify}"
export COMPOSE_PROJECT_NAME

"${DOCKER:-docker}" compose \
  -f docker-compose.yml \
  -f docker-compose.phase5h.yml \
  --profile tools run --rm --no-deps \
  --volume ./scripts:/verification:ro \
  --volume .:/workspace:ro \
  --entrypoint python migrate \
  /verification/verify-phase-5h-security.py
