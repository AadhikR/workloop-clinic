#!/bin/sh
set -eu

docker_command="${DOCKER:-docker}"
log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

"$docker_command" compose logs --no-color backend keycloak > "$log_file"

if grep -E -i 'Bearer [A-Za-z0-9_-]+\.|eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+|access_token|id_token|refresh_token|postgresql(\+psycopg)?://|identity_subject|SELECT .*app_users' "$log_file" >/dev/null; then
  exit 1
fi

for file in backend/.env.postgres backend/.env.keycloak; do
  while IFS='=' read -r name value; do
    case "$name" in
      *_PASSWORD)
        if git grep --fixed-strings --quiet -- "$value" || grep --fixed-strings --quiet -- "$value" "$log_file"; then
          exit 1
        fi
        ;;
    esac
  done < "$file"
done
