# Phase 2D FastAPI service

## Status

**Completed on 2026-08-31.**

Phase 2D adds the first running FastAPI service. It validates configuration, writes structured
JSON logs, connects to PostgreSQL through the restricted Workloop runtime account, and reports
database readiness through `GET /health`.

It does not add authentication, CORS, business routes, application tables, Alembic, Keycloak,
or cloud infrastructure.

## Service behavior

The local API is available at `http://127.0.0.1:8000`. Docker does not publish it on other host
interfaces.

`GET /health` executes `SELECT 1` through SQLAlchemy and Psycopg. A successful response is:

```json
{"status":"ok","database":"ok"}
```

The endpoint returns HTTP 503 with a fixed response when PostgreSQL is unavailable:

```json
{"status":"error","database":"unavailable"}
```

Database errors are not returned to the caller. The database probe has a configurable timeout
with a maximum accepted value of 30 seconds.

## Configuration

FastAPI requires these environment variables:

| Variable | Purpose |
|---|---|
| `APP_ENV` | Named runtime environment |
| `APP_BASE_URL` | Public address of this API |
| `FRONTEND_URL` | Expected frontend address for later CORS configuration |
| `LOG_LEVEL` | Python and Uvicorn log level |
| `DATABASE_HEALTH_TIMEOUT_SECONDS` | Maximum health-probe duration |
| `DATABASE_URL` | Secret SQLAlchemy and Psycopg connection URL |

`backend/.env.example` contains safe placeholders. The generated `backend/.env.api` file is
ignored by Git and contains the local runtime connection URL. It does not contain the bootstrap,
migration, or Keycloak database passwords.

Settings reject non-Psycopg database URLs and hide `DATABASE_URL` in model representations.
No backend secret uses a `VITE_` variable.

## Container

The FastAPI image uses the official Python 3.12 Debian Bookworm image pinned to OCI index digest
`sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579`.
The resolved runtime reports Python 3.12.14.

The image installs `requirements.lock` with hash checking. The running container:

- Uses the unprivileged `workloop` account with UID and GID 999.
- Drops all Linux capabilities.
- Prevents privilege escalation.
- Uses a read-only root filesystem with a temporary `/tmp` mount.
- Exposes port 8000 only through `127.0.0.1:8000` on the host.
- Starts only after PostgreSQL reports healthy.
- Has its own health check against the real database-backed endpoint.

## Commands

Run from the repository root. Set the Docker path first if the current PowerShell session cannot
find `docker`:

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

Build and start PostgreSQL and FastAPI:

```powershell
& $docker compose up --build --detach --wait postgres backend
```

Check the API:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
```

Show logs:

```powershell
& $docker compose logs backend
```

Stop only FastAPI:

```powershell
& $docker compose stop backend
```

Start it again:

```powershell
& $docker compose start backend
```

These commands do not remove the PostgreSQL volume. Do not add `--volumes` to a Compose shutdown
command without separate approval.

## Completion evidence

The Phase 2D gate passed on 2026-08-31.

| Check | Result |
|---|---|
| Backend tests | 6 passed |
| Ruff | Lint and format checks passed |
| Pyright | 0 errors, warnings, or information messages |
| Dependency check | `pip check` passed on Windows and in the Linux image |
| Linux lock installation | Hash-locked runtime dependencies installed successfully |
| Container health | FastAPI and PostgreSQL report healthy |
| Healthy response | HTTP 200 with the documented fixed body |
| Failure response | HTTP 503 while PostgreSQL was stopped |
| Recovery | Returned to HTTP 200 after PostgreSQL restarted |
| Database identity | PostgreSQL observed `workloop_runtime` connected to `workloop` |
| Container user | `workloop`, UID and GID 999 |
| Container restrictions | Read-only root, all capabilities dropped, no new privileges |
| Host port | `127.0.0.1:8000` only |
| Logs | All raw startup and access lines parsed as JSON |
| Log redaction | No secret variable names or database URL appeared |
| OpenAPI | Title `Workloop API`, version `0.1.0` |
| Frontend tests | 14 existing unit tests passed |
| Frontend build | Passed with the existing 522 kB chunk warning |
| DigitalOcean | No resource created; cost remains USD 0 |

The first backend test run had five failures because uppercase environment aliases were not
declared. Strict type checking also rejected the deprecated FastAPI test client. Explicit aliases
and HTTPX ASGI tests fixed both problems. A later test run passed with one warning because a helper
name began with `test_`; renaming it removed the accidental test collection. Ruff requested one
format-only change.

The first log review found two plain Uvicorn startup lines before application logging began. A
startup log configuration now formats the complete raw container stream as JSON. One inline
container identity check failed because PowerShell removed Python string quotes; the replacement
PostgreSQL activity query confirmed the runtime identity.

The image build emitted pip's standard warning about installing packages as root during the image
layer build. The final process does not run as root.

## Resource use

| Resource | Measured use |
|---|---:|
| FastAPI container memory | About 61.6 MiB while idle |
| FastAPI image | About 65.1 MB through Docker image inspection |
| FastAPI idle CPU | About 0.2% during measurement |

Docker shares base image layers, so total disk allocation can differ from the per-image figure.

## Rollback

Stopping or removing the FastAPI container leaves the PostgreSQL container and named volume
unchanged. Reverting the Phase 2D code returns the repository to the Phase 2C PostgreSQL-only
state. No rollback is needed, and no database volume deletion is authorized.

## Remaining work

Phase 2E owns Alembic initialization and migration commands. Authentication, user identities,
and Keycloak remain later work. Phase 2D authorization does not authorize Phase 2E.
