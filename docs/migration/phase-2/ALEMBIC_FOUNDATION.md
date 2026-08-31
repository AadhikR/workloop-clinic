# Phase 2E Alembic foundation

## Status

**Completed on 2026-08-31.**

Phase 2E adds the versioned database migration runner. Alembic reads SQLAlchemy metadata, orders
schema revisions, and applies each revision through the dedicated `workloop_migration` account.
FastAPI continues to use the restricted `workloop_runtime` account.

This part deliberately contains no migration revisions, application tables, Supabase SQL, seed
data, or business models. Phase 4 owns the portable schema baseline. Earlier identity tables may
be added in Phase 3 only when that phase's documented prerequisite begins.

## Files and responsibilities

| Path | Purpose |
|---|---|
| `backend/alembic.ini` | Points Alembic to the versioned migration directory |
| `backend/alembic/env.py` | Validates the migration URL and runs online or offline migrations |
| `backend/alembic/script.py.mako` | Template for future typed revision files |
| `backend/alembic/versions/` | Append-only revision directory; currently empty |
| `backend/app/db/base.py` | Shared SQLAlchemy metadata and deterministic constraint names |
| `backend/.env.migration.example` | Safe migration configuration example |
| `backend/.env.migration` | Ignored local migration URL; never committed |

The FastAPI image contains the Alembic runner. Compose adds a `migrate` service under the `tools`
profile. It starts only for a migration command, receives only `MIGRATION_DATABASE_URL`, and exits
afterward. It does not open a host port.

The migration container runs as the unprivileged `workloop` Linux user with no capabilities, no
privilege escalation, and a read-only root filesystem. Only `backend/alembic` is mounted writable
so a deliberate revision-generation command can create a file in the repository.

## Secret handling

`backend/.env.migration` contains one value:

```text
MIGRATION_DATABASE_URL
```

The URL contains the `workloop_migration` password and is a secret. Git ignores the file. Do not
paste it into chat, logs, documentation, GitHub settings, or a `VITE_` variable.

`backend/.env.api` remains separate and contains only the restricted FastAPI runtime URL. The
FastAPI container cannot read the migration environment file, and the migration container does
not receive the PostgreSQL bootstrap or Keycloak passwords.

The local environment generator creates missing files without overwriting existing credentials:

```powershell
& ".\scripts\new-local-postgres-env.ps1"
```

## Commands

Run from the repository root. Set the full Docker path first if needed:

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

Apply every pending revision once and remove the one-shot container afterward:

```powershell
& $docker compose --profile tools run --rm migrate
```

Show the database's current revision:

```powershell
& $docker compose --profile tools run --rm migrate alembic -c /app/alembic.ini current
```

Show repository heads:

```powershell
& $docker compose --profile tools run --rm migrate alembic -c /app/alembic.ini heads
```

Check whether SQLAlchemy metadata requires a new revision:

```powershell
& $docker compose --profile tools run --rm migrate alembic -c /app/alembic.ini check
```

Future phases can generate a reviewed revision with:

```powershell
& $docker compose --profile tools run --rm migrate alembic -c /app/alembic.ini revision --autogenerate -m "short description"
```

Generating a file does not apply it. Review every operation, especially drops, type changes,
defaults, ownership, and data updates, before running `upgrade head`.

Do not edit an applied revision to hide a correction. Add a new revision. Do not run downgrade or
delete the database volume without a separate explanation and approval.

## Completion evidence

The Phase 2E gate passed on 2026-08-31.

| Check | Result |
|---|---|
| Alembic version | 1.19.1 |
| Migration identity | `workloop_migration` connected to `workloop` |
| Migration environment | Contains only `MIGRATION_DATABASE_URL` |
| FastAPI environment | Does not contain the migration URL or database passwords |
| Current and heads commands | Connected successfully; no revision exists yet |
| Upgrade | `upgrade head` passed repeatedly without changes |
| Offline mode | `upgrade head --sql` passed without emitting schema SQL |
| Metadata check | `No new upgrade operations detected` |
| Invalid configuration | Missing and non-PostgreSQL migration URLs were rejected |
| Revision template | Local and container-generated test revisions compiled successfully |
| Writable boundary | Container revision appeared in the host revision directory, then was removed |
| Database contents | Zero application or Alembic tables after the empty upgrade |
| Migration lifecycle | One-shot containers exited and were removed |
| Container user | `workloop`, UID and GID 999 |
| Backend tests | 8 passed |
| Ruff | Lint and format checks passed |
| Pyright | Application, Alembic environment, and tests passed strictly |
| DigitalOcean | No resource created; cost remains USD 0 |

Ruff initially found two import-order differences in the new files; both were fixed. The first
migration-file verifier incorrectly indexed a single PowerShell string and reported a false
failure. Array-safe validation then confirmed the ignored file contains one non-empty variable.
An inline Python identity command also lost SQL quotes through PowerShell; a base64-encoded check
then confirmed the migration role and database.

Building the same image tag for two Compose services in one parallel BuildKit invocation produced
separate image manifests. A final single backend build established the shared image used by both
services. No database or source rollback was needed.

## Rollback

Removing the Alembic configuration and `migrate` service would return the code to Phase 2D. The
database has no migration revision or application table to reverse. The PostgreSQL volume remains
untouched and must not be deleted without separate approval.

## Remaining work

Phase 2F owns the local Keycloak runtime. Phase 2E authorization does not authorize Keycloak,
realm creation, an administrator account, or any identity data.
