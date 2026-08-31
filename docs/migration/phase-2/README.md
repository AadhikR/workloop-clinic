# Phase 2 local foundation

## Status

**Completed on 2026-08-31.**

Phase 2 provides a repeatable local foundation for the migration:

- PostgreSQL 16.15 with separate Workloop and Keycloak databases and credentials.
- FastAPI with validated configuration, JSON logs, and a database-backed health endpoint.
- Alembic through a separate migration-only database identity.
- Keycloak 26.7.2 with PostgreSQL persistence and a local bootstrap administrator.
- GitHub Actions checks for backend, frontend, and the complete local stack.

No Workloop business table, Workloop realm, OIDC client, synthetic employee identity, or migrated
feature exists yet. DigitalOcean still has no running Workloop resource.

## Phase records

| Part | Evidence |
|---|---|
| 2A computer readiness | [`READINESS.md`](READINESS.md) |
| 2B backend package | [`BACKEND_SCAFFOLD.md`](BACKEND_SCAFFOLD.md) |
| 2C PostgreSQL | [`LOCAL_POSTGRESQL.md`](LOCAL_POSTGRESQL.md) |
| 2D FastAPI | [`FASTAPI_SERVICE.md`](FASTAPI_SERVICE.md) |
| 2E Alembic | [`ALEMBIC_FOUNDATION.md`](ALEMBIC_FOUNDATION.md) |
| 2F Keycloak | [`KEYCLOAK_RUNTIME.md`](KEYCLOAK_RUNTIME.md) |
| 2G GitHub Actions | [`GITHUB_CHECKS.md`](GITHUB_CHECKS.md) |
| 2H restart and clean-checkout gate | This file |

## Fresh checkout setup

Start Docker Desktop and close unnecessary memory-heavy applications. Run these commands from the
repository root.

Create the four ignored environment files:

```powershell
& ".\scripts\new-local-postgres-env.ps1"
```

The script never prints a password. It creates missing files without replacing existing local
credentials:

```text
backend/.env.postgres
backend/.env.api
backend/.env.migration
backend/.env.keycloak
```

Create and install the isolated backend environment:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv "backend\.venv"
& "backend\.venv\Scripts\python.exe" -m pip install --require-hashes --requirement "backend\requirements-dev.lock"
& "backend\.venv\Scripts\python.exe" -m pip install --no-deps "backend"
```

Install frontend dependencies without package lifecycle scripts:

```powershell
npm.cmd ci --ignore-scripts
```

If `docker` is missing from the PowerShell `PATH`, define its full path:

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

Build and start all long-running services:

```powershell
& $docker compose up --build --detach --wait postgres backend keycloak
```

Run pending Workloop migrations once:

```powershell
& $docker compose --profile tools run --rm migrate
```

## Expected checks

FastAPI:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Expected fields:

```text
status=ok
database=ok
```

Keycloak:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9000/health/ready"
```

Expected field:

```text
status=UP
```

The local Keycloak administrator console is:

```text
http://127.0.0.1:8080/admin/
```

Do not paste its password into chat. It is stored only in the ignored Keycloak environment file
and should also be retained in an approved password manager if recovery matters.

## Development checks

Run backend checks from `backend`:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m ruff format --check .
& ".\.venv\Scripts\pyright.exe"
& ".\.venv\Scripts\python.exe" -m pip check
```

Run frontend checks from the repository root:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

The full frontend ESLint and Playwright commands retain the Phase 0 baseline failures. See
[`GITHUB_CHECKS.md`](GITHUB_CHECKS.md) for the reason they are not migration-foundation gates.

## Stop, restart, and rebuild

Stop services while retaining their containers and PostgreSQL data:

```powershell
& $docker compose stop
```

Start those containers again:

```powershell
& $docker compose start
```

Remove containers and the project network while retaining PostgreSQL data:

```powershell
& $docker compose down
```

Recreate the stack from its definitions:

```powershell
& $docker compose up --build --detach --wait postgres backend keycloak
& $docker compose --profile tools run --rm migrate
```

Never add `--volumes` to the main project's shutdown command. Never remove the
`workloop-clinic_postgres_data` volume without a separate backup review and explicit approval.
The volume contains both Workloop and Keycloak databases.

## Local ports and resources

| Service | Host binding | Purpose |
|---|---|---|
| PostgreSQL | `127.0.0.1:5432` | Local database access |
| FastAPI | `127.0.0.1:8000` | API and health endpoint |
| Keycloak | `127.0.0.1:8080` | Login and administration |
| Keycloak management | `127.0.0.1:9000` | Readiness and liveness |

All ports are loopback-only. Stable measured use is roughly 30 MiB for PostgreSQL, 61 MiB for
FastAPI, and 560 MiB for Keycloak. Keycloak has a 1 GiB limit. Docker images occupy about 1.5 GB
in total, and the shared database volume is about 78 MB.

## Restart and clean-checkout evidence

The Phase 2H gate used commit `c216291`.

The main stack was stopped with `docker compose down`, which retained
`workloop-clinic_postgres_data`. Rebuilding and restarting all services preserved the Keycloak
master realm, local administrator, and signing-key identifiers. FastAPI, Keycloak readiness, and
Alembic passed after restart.

An isolated detached Git worktree and Compose project named `workloop-phase2h-clean` then tested a
fresh checkout. It used separate generated credentials and
`workloop-phase2h-clean_postgres_data`, never the main volume. The clean checkout passed:

- Hash-locked Python 3.12 installation and local package build.
- Eight backend tests, Ruff lint and format, strict Pyright, and `pip check`.
- `npm ci --ignore-scripts`, 14 frontend unit tests, and the Vite build.
- FastAPI and Keycloak health on all documented loopback ports.
- Alembic through the migration-only identity.
- Zero Workloop application tables, one Keycloak master realm, and one local administrator.
- Administrator login without printing its password or token.
- FastAPI JSON logs and service-log secret scans.

The project owner separately approved deletion of the isolated test volume and worktree. The
temporary containers, network, volume, credentials, virtual environment, node modules, and source
checkout were removed. Verification confirmed that the main PostgreSQL volume remained. The main
stack was then restored and passed health, migration, administrator, and signing-key checks.

The environment-generation wrapper once checked a stale native-process exit code after a
successful PowerShell script and reported a false failure. A cleanup verifier later called
`.Trim()` on the expected empty volume result and produced a null-handling error after Docker had
already deleted the approved test volume. Direct existence checks confirmed the intended result
in both cases.

The clean checkout's Vite build did not emit the main worktree's historical 522 kB warning and
produced a smaller main chunk. The source and lockfile were the same, but the clean checkout had no
ignored root Supabase environment file. Treat the bundle difference as environment-dependent
until a later frontend phase measures and explains it.

## Known risks and deferred work

- Keycloak uses `start-dev`; cloud deployment requires production mode, an optimized image, TLS
  termination review, fixed external hostname behavior, and administrator hardening.
- DigitalOcean remains synthetic-only and Azure UAE remains the production destination.
- The local PostgreSQL volume is not a backup.
- npm reports one moderate production advisory and five development advisories, including four
  high findings. Resolve them in a separate reviewed dependency update.
- The bootstrap Keycloak administrator needs rotation or replacement during Phase 3.
- No Workloop realm, token validation, business schema, authorization, or migrated feature exists.

## Completion gate

Phase 2 passes because a fresh checkout can install locked dependencies, start PostgreSQL,
FastAPI, and Keycloak through documented commands, run Alembic through its separate identity,
reach healthy services, pass automated foundation checks, survive a non-destructive restart, and
retain Keycloak identity state. All data remains local and synthetic.

Phase 3 requires separate project-owner authorization.
