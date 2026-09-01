#!/bin/sh
set -eu

docker_command="${DOCKER:-docker}"
log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

"$docker_command" compose logs --no-color backend keycloak > "$log_file"

if grep -E -i 'Bearer [A-Za-z0-9_-]+\.|eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|(access_token|id_token|refresh_token)["'"'"'= :]+[A-Za-z0-9._~-]{32,}' "$log_file" >/dev/null; then
  echo "Service log token scan failed" >&2
  exit 1
fi

if grep -E -i 'postgresql\+psycopg://|postgresql://[^[:space:]"]+@' "$log_file" >/dev/null; then
  echo "Service log database credential scan failed" >&2
  exit 1
fi

if grep -E -i 'identity_subject|SELECT .*app_users' "$log_file" >/dev/null; then
  echo "Service log application identity scan failed" >&2
  exit 1
fi

for file in backend/.env.postgres backend/.env.keycloak; do
  while IFS='=' read -r name value; do
    case "$name" in
      *_PASSWORD)
        if git grep --fixed-strings --quiet -- "$value"; then
          echo "Tracked generated-secret scan failed" >&2
          exit 1
        fi
        if grep --fixed-strings --quiet -- "$value" "$log_file"; then
          echo "Service log generated-secret scan failed" >&2
          exit 1
        fi
        ;;
    esac
  done < "$file"
done
