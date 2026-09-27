#!/bin/sh
set -eu

mode=${1:-}
database=${2:-}
archive=${3:-}
release_id=${4:-}
key_id=${5:-}

case "$database" in
  workloop|keycloak) ;;
  *) echo "database must be workloop or keycloak" >&2; exit 1 ;;
esac

[ -n "$archive" ] || { echo "encrypted archive path is required" >&2; exit 1; }
[ -n "$release_id" ] || { echo "release ID is required" >&2; exit 1; }
[ -n "$key_id" ] || { echo "key ID is required" >&2; exit 1; }
[ -n "${WORKLOOP_RECOVERY_KEY_BASE64:-}" ] || { echo "recovery key is required" >&2; exit 1; }

case "$mode" in
  export)
    [ "${COMPOSE_PROJECT_NAME:-}" = "workloop-phase14f-source" ] || {
      echo "export requires the exact Phase 14F source project" >&2
      exit 1
    }
    nonce_hex=$(od -An -N12 -tx1 /dev/urandom | tr -d ' \n')
    docker compose exec -T postgres pg_dump --username postgres --dbname "$database" \
      --format=custom \
      | node scripts/phase-14f-recovery.mjs seal --input - --output "$archive" \
          --database "$database" --release-id "$release_id" --key-id "$key_id" \
          --nonce-hex "$nonce_hex"
    ;;
  restore)
    [ "${COMPOSE_PROJECT_NAME:-}" = "workloop-phase14f-restore" ] || {
      echo "restore requires the exact Phase 14F restore project" >&2
      exit 1
    }
    [ -f "$archive" ] || { echo "encrypted archive does not exist" >&2; exit 1; }
    node scripts/phase-14f-recovery.mjs open --input "$archive" --output - \
      --database "$database" --release-id "$release_id" --key-id "$key_id" \
      | docker compose exec -T postgres pg_restore --username postgres --dbname "$database" \
          --clean --if-exists --exit-on-error
    ;;
  *)
    echo "use export or restore" >&2
    exit 1
    ;;
esac
