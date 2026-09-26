# Workloop API

The backend is the only business and data API for Workloop Clinic. It validates Keycloak access
tokens, resolves application users, enforces role and tenant scope, writes PostgreSQL through
application-owned repositories, and controls private object storage.

## Requirements

- Python 3.12.10
- PostgreSQL 17 through the repository Compose stack
- Keycloak through the same stack

Use a local virtual environment at `backend/.venv`. Do not install project dependencies into the
system Python or Anaconda environment.

## Install locked dependencies

From `backend/` on Windows:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install --require-hashes --requirement requirements-dev.lock
& ".\.venv\Scripts\python.exe" -m pip install --no-deps .
```

On Linux, use the equivalent Python 3.12 virtual-environment interpreter.

## Checks

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m ruff format --check .
& ".\.venv\Scripts\pyright.exe"
& ".\.venv\Scripts\python.exe" -m pip check
```

## Local services

Generate untracked local environment files from the repository root:

```powershell
./scripts/new-local-postgres-env.ps1
```

Start the database, API, and identity service, then apply Alembic:

```powershell
docker compose up --build --detach --wait postgres backend keycloak
docker compose --profile tools run --rm migrate
```

The API health endpoint is `http://127.0.0.1:8000/health`. Business routes are versioned under
`/api/v1` and require a valid access token unless a route explicitly documents a public boundary.

## Database and process roles

Alembic uses the migration role. FastAPI, expiry processing, storage reconciliation, and file
scanning use separate roles with narrower grants. Keep those credentials in their generated
environment files. Do not combine them into one broad runtime role.

Add schema changes as new files under `alembic/versions/`. Never edit an applied revision. Verify a
single head, an empty-database upgrade, a second no-op migration pass, and any required predecessor
rollback.

## Private storage

`app/storage/` defines the private-file boundary. The local default is a synthetic filesystem-backed
adapter in a named volume. The full storage gate uses an S3-compatible adapter. API routes own object
authorization, metadata, quarantine, and signed access. Browser code never receives provider
credentials.

## Dependency locks

Change `pyproject.toml`, then regenerate and review both locks deliberately:

```powershell
& ".\.venv\Scripts\pip-compile.exe" --extra dev --generate-hashes --strip-extras --allow-unsafe --output-file requirements-dev.lock pyproject.toml
& ".\.venv\Scripts\pip-compile.exe" --generate-hashes --strip-extras --allow-unsafe --output-file requirements.lock pyproject.toml
```

## Boundaries

- Never log secrets, tokens, database URLs, private objects, or signed URLs.
- Keep authorization in FastAPI and scoped repositories, not in frontend visibility rules.
- Use synthetic data for local and migration verification.
- Do not add provider-specific database roles, schemas, bootstrap SQL, or browser data clients.
