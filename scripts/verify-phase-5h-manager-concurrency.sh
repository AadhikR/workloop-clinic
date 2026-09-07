#!/bin/sh
set -eu

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-workloop-phase5h-verify}"
export COMPOSE_PROJECT_NAME

"${DOCKER:-docker}" compose \
  -f docker-compose.yml \
  -f docker-compose.phase5h.yml \
  --profile tools run --rm --no-deps \
  --env PYTHONPATH=/app \
  --volume ./backend/app:/app/app:ro \
  --volume ./scripts:/verification:ro \
  --entrypoint python migrate \
  /verification/verify-phase-5h-manager-concurrency.py
