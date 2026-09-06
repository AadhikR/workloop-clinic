#!/bin/sh
set -eu

docs_only=true
backend=false
frontend=false
full_stack=false
database_deep=false
auth_deep=false
seen=false
carriage_return=$(printf '\r')

while IFS= read -r path; do
  path=${path%"$carriage_return"}
  [ -n "$path" ] || continue
  seen=true

  case "$path" in
    docs/*|*.md) ;;
    *) docs_only=false ;;
  esac

  case "$path" in
    backend/*|scripts/*.py|scripts/*.ps1) backend=true ;;
  esac

  case "$path" in
    src/*|public/*|migration/*|tests/*|scripts/*.mjs|package.json|package-lock.json|index.html|eslint.config.js|vite*.js|fix-dist.js)
      frontend=true
      ;;
  esac

  case "$path" in
    .github/*|docker-compose*.yml|backend/Dockerfile|backend/requirements*.lock|backend/pyproject.toml|infra/*|keycloak/*|migration/*|package.json|package-lock.json|scripts/new-local-postgres-env.ps1|scripts/configure-phase-*|scripts/verify-phase-*|backend/app/main.py|backend/app/auth/*|backend/app/db/*)
      full_stack=true
      ;;
  esac

  case "$path" in
    .github/workflows/*|docker-compose*.yml|backend/alembic/*|backend/app/models/*|backend/app/db/*|infra/local/postgres/*|scripts/database-persistence-*|scripts/verify-phase-*-schema.*|scripts/verify-phase-*-migration*|scripts/verify-phase-*-rls.*|scripts/verify-phase-*-grants.*|scripts/verify-phase-*-function*|scripts/verify-phase-*-triggers.*|scripts/verify-phase-*-seed.*|scripts/verify-phase-*-context.*|scripts/verify-phase-*-boundaries.*|scripts/verify-phase-*-repositories.*|scripts/verify-phase-*-revision.*|scripts/verify-phase-*-downgrade.*|scripts/verify-phase-*-concurrency.*)
      database_deep=true
      ;;
  esac

  case "$path" in
    .github/workflows/*|docker-compose*.yml|backend/app/auth/*|backend/tests/test_access_token.py|backend/tests/test_application_user.py|infra/*|keycloak/*|migration/*|scripts/configure-phase-*|scripts/verify-phase-*-keycloak.*|scripts/verify-phase-*-browser.*|scripts/verify-phase-*-logs.*)
      auth_deep=true
      ;;
  esac
done

if [ "$seen" = false ]; then
  docs_only=false
  full_stack=true
fi

if [ "$docs_only" = false ] && [ "$backend" = false ] && [ "$frontend" = false ]; then
  full_stack=true
fi

if [ "$database_deep" = true ] || [ "$auth_deep" = true ]; then
  full_stack=true
fi

if [ "$full_stack" = true ]; then
  backend=true
  frontend=true
fi

if [ "$seen" = true ] && [ "$docs_only" = true ]; then
  backend=false
  frontend=false
  full_stack=false
  database_deep=false
  auth_deep=false
fi

write_outputs() {
  echo "docs_only=$docs_only"
  echo "backend=$backend"
  echo "frontend=$frontend"
  echo "full_stack=$full_stack"
  echo "database_deep=$database_deep"
  echo "auth_deep=$auth_deep"
}

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  write_outputs >> "$GITHUB_OUTPUT"
else
  write_outputs
fi
