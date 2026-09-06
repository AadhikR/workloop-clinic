#!/bin/sh
set -eu

"${DOCKER:-docker}" compose \
  -f docker-compose.yml \
  -f docker-compose.phase5f.yml \
  --profile tools run --rm --no-deps \
  --volume ./scripts:/verification:ro \
  --entrypoint python migrate \
  -c "import runpy; runpy.run_path('/verification/verify-phase-5f-rls.py', run_name='__main__')"
