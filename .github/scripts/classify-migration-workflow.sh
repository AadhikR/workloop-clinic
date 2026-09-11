#!/bin/sh
set -eu

docs_only=true
backend=false
frontend=false
full_stack=false
database_deep=false
database_history=false
auth_deep=false
seen=false
carriage_return=$(printf '\r')
tab=$(printf '\t')

while IFS= read -r line; do
  line=${line%"$carriage_return"}
  status=
  path=$line
  case "$line" in
    *"$tab"*)
      status=${line%%"$tab"*}
      path=${line##*"$tab"}
      ;;
  esac
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
    .github/*|docker-compose*.yml|backend/Dockerfile|backend/requirements*.lock|backend/pyproject.toml|infra/*|keycloak/*|migration/*|package.json|package-lock.json|scripts/new-local-postgres-env.ps1|scripts/configure-phase-*|scripts/verify-phase-*|backend/app/main.py|backend/app/auth/*|backend/app/db/*|backend/app/storage/*)
      full_stack=true
      ;;
  esac

  case "$path" in
    docker-compose*.yml|backend/alembic/*|backend/app/models/*|backend/app/db/*|backend/app/repositories/*|backend/app/schemas/*|backend/tests/test_authorization_*|backend/tests/test_mutation_*|backend/tests/test_scoped_repositories.py|infra/local/postgres/*|scripts/database-persistence-*|scripts/phase-5g-catalogue.json|scripts/phase-5h-control-manifest.json|scripts/verify-phase-*-schema.*|scripts/verify-phase-*-migration*|scripts/verify-phase-*-rls.*|scripts/verify-phase-*-grants.*|scripts/verify-phase-*-function*|scripts/verify-phase-*-triggers.*|scripts/verify-phase-*-seed.*|scripts/verify-phase-*-context.*|scripts/verify-phase-*-boundaries.*|scripts/verify-phase-*-repositories.*|scripts/verify-phase-*-revision.*|scripts/verify-phase-*-downgrade.*|scripts/verify-phase-*-concurrency.*|scripts/verify-phase-*-security.*)
      database_deep=true
      ;;
  esac

  case "$path" in
    .github/workflows/migration-foundation.yml|.github/scripts/classify-migration-workflow.sh|backend/alembic/env.py|backend/alembic/script.py.mako|scripts/verify-phase-4d-grants.*|scripts/verify-phase-4d-function*|scripts/verify-phase-4d-shift-swap-concurrency.*|scripts/verify-phase-5d-downgrade.*|scripts/verify-phase-5e-downgrade.*|scripts/verify-phase-5e-rls.*|scripts/verify-phase-5f-revision.*|scripts/verify-phase-5g-chain.*|scripts/verify-phase-5g-revision.*)
      database_history=true
      ;;
    backend/alembic/versions/*)
      if [ "$status" != "" ] && [ "$status" != "A" ]; then
        database_history=true
      fi
      ;;
  esac

  case "$path" in
    .github/workflows/migration-foundation.yml|docker-compose*.yml|infra/*|keycloak/*|migration/*|scripts/configure-phase-*)
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

if [ "$database_history" = true ]; then
  database_deep=true
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
  database_history=false
  auth_deep=false
fi

write_outputs() {
  echo "docs_only=$docs_only"
  echo "backend=$backend"
  echo "frontend=$frontend"
  echo "full_stack=$full_stack"
  echo "database_deep=$database_deep"
  echo "database_history=$database_history"
  echo "auth_deep=$auth_deep"
}

if [ -n "${GITHUB_OUTPUT:-}" ]; then
  write_outputs >> "$GITHUB_OUTPUT"
else
  write_outputs
fi
