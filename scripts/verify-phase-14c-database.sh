#!/bin/sh
set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"${DOCKER:-docker}" compose exec -T postgres psql \
  --username postgres \
  --dbname postgres \
  --file - \
  <"$script_directory/harden-phase-14c-extension.sql"
"${DOCKER:-docker}" compose exec -T postgres psql \
  --username postgres \
  --dbname postgres \
  --file - \
  <"$script_directory/verify-phase-14c-database.sql"

printf '%s\n' 'Phase 14C database roles, grants, default privileges, and cross-role denials passed.'
