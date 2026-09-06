#!/bin/sh
set -eu

compose() {
  "${DOCKER:-docker}" compose "$@"
}

run_verifier() {
  service="$1"
  mode="$2"
  compose --profile tools run --rm --no-deps \
    --volume ./scripts:/verification:ro \
    --entrypoint python "$service" \
    -c "import runpy, sys; sys.argv = ['verify-phase-5d-context.py', '$mode']; runpy.run_path('/verification/verify-phase-5d-context.py', run_name='__main__')"
}

cleanup() {
  run_verifier migrate cleanup
}

trap cleanup EXIT HUP INT TERM
run_verifier migrate setup
run_verifier backend verify
cleanup
trap - EXIT HUP INT TERM

echo "Phase 5D transaction context and pool isolation checks passed."
