# Phase 2C local PostgreSQL

## Status

**Completed on 2026-08-31.**

Phase 2C configures PostgreSQL for local development. It creates separate empty
databases and credentials for Workloop and Keycloak. It does not create application tables,
start FastAPI or Keycloak, or use DigitalOcean.

## Local layout

Docker Compose runs one PostgreSQL container with:

- A `workloop` database owned by the migration role.
- A restricted Workloop runtime role for the future FastAPI service.
- A `keycloak` database owned by a separate Keycloak role.
- A bootstrap PostgreSQL administrator used only for local database administration.
- A named volume that persists after the container is stopped or replaced.
- A host port bound to `127.0.0.1:5432`, not to the local network.

The project uses the official PostgreSQL `17.11-bookworm` image pinned to OCI index digest
`sha256:051f7b7b3abdd564d5d1bd1e8c4b9c1b6e77087d1dd22020ede611c096a272e0`.
Phase 4A selected PostgreSQL 17 as the portable target, and the Phase 4D corrective review aligned
Compose and CI with that decision on 2026-09-05.

PostgreSQL 17 cannot open a PostgreSQL 16 data directory directly. Existing local PostgreSQL 16
volumes require `pg_upgrade` or, when they contain no needed data, explicit approval to recreate the
volume before the updated Compose service is started.

## Password file

`backend/.env.postgres` contains four unique local passwords. Git ignores this file. Do not
commit it, paste it into chat, use its values in `VITE_` variables, or reuse its passwords in
DigitalOcean or Azure.

`backend/.env.postgres.example` contains placeholders and is safe to commit.

Initialization scripts run only when the PostgreSQL volume is empty. Changing the password
file later does not rotate credentials in an existing database.

Create the ignored PostgreSQL, API, migration, and Keycloak environment files once from the
repository root:

```powershell
& ".\scripts\new-local-postgres-env.ps1"
```

The script never overwrites either file. On a new setup, it generates four unique 256-bit values,
writes the database roles to `backend/.env.postgres`, gives `backend/.env.api` only the Workloop
runtime connection URL, gives `backend/.env.migration` only the migration connection URL, and
gives `backend/.env.keycloak` only the Keycloak database and administrator credentials. If the
PostgreSQL file already exists, it creates only missing service files with the matching existing
passwords. It does not display secret values. Store a protected copy outside Git if the local
database must be recoverable after losing these files.

## Commands

Run Docker commands from the repository root. If `docker` is not available in the current
PowerShell `PATH`, use:

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

Start PostgreSQL:

```powershell
& $docker compose up --detach --wait postgres
```

Show service status:

```powershell
& $docker compose ps
```

Show PostgreSQL logs without printing the environment:

```powershell
& $docker compose logs postgres
```

Stop the service while retaining its container and volume:

```powershell
& $docker compose stop postgres
```

Restart the stopped service:

```powershell
& $docker compose start postgres
```

Remove the container and project network while retaining the database volume:

```powershell
& $docker compose down
```

Do not add `--volumes` to `docker compose down`. Do not run `docker volume rm` for the project
volume without separate approval. Both actions destroy the local databases.

## Boundaries

- Use synthetic development data only.
- Do not expose port 5432 on `0.0.0.0`.
- Do not use the bootstrap or migration credentials as the FastAPI runtime identity.
- Do not manually change database files inside the volume.
- Do not treat this local volume as a backup.

## Completion evidence

The Phase 2C gate passed on 2026-08-31.

| Check | Result |
|---|---|
| Compose validation | Passed with `docker compose config --quiet` |
| Image | Official PostgreSQL `17.11-bookworm`, pinned by OCI digest |
| Server version | `17.11 (Debian 17.11-1.pgdg12+2)` |
| Health | Container reported healthy after initial creation and replacement |
| Host port | `127.0.0.1:5432`; no all-interface host binding |
| Workloop database | Owned by `workloop_migration` |
| Keycloak database | Owned by `keycloak` |
| Role flags | All service roles are non-superuser, cannot create databases, and cannot create roles |
| Password authentication | Passed for bootstrap, migration, runtime, and Keycloak accounts over TCP |
| Database isolation | Keycloak cannot connect to Workloop; Workloop runtime cannot connect to Keycloak |
| Runtime restriction | Workloop runtime cannot create a database |
| Persistence | Marker survived `docker compose down` and container replacement; marker was then removed |
| Initialization script | Shell syntax check passed inside the pinned image |
| Backend checks | 1 test passed; Ruff, format, Pyright, and `pip check` passed |
| Frontend checks | 14 unit tests passed; production build passed with the known 522 kB chunk warning |
| Credential check | Real file is ignored; committed example contains placeholders only |
| DigitalOcean | No resource created; cost remains USD 0 |

The first image pull failed because this automation shell could not find
`docker-credential-desktop` on `PATH`. Retrying with Docker's installed binary directory added
to that command's `PATH` succeeded. A Docker inspection template and two shell-wrapped negative
test attempts also failed because PowerShell altered their quoting. Simpler commands reran the
same checks successfully. An initial credential-scan expression used unsupported regular
expression look-ahead; a compatible scan then found only the four documented placeholders and
SQL variable references.

Measured while the service was idle:

| Resource | Measured use |
|---|---:|
| PostgreSQL container memory | 37.07 MiB |
| PostgreSQL image | 621.9 MB reported by `docker system df` |
| PostgreSQL volume | 72.24 MB |

The container remains running and healthy. The named volume is
`workloop-clinic_postgres_data`. It has no backup and contains only empty development databases.

## Files changed

- `docker-compose.yml`
- `backend/.env.postgres.example`
- `infra/local/postgres/init/01-create-databases.sh`
- `scripts/new-local-postgres-env.ps1`
- `backend/README.md`
- `docs/migration/phase-2/LOCAL_POSTGRESQL.md`
- `DIGITALOCEAN_MIGRATION_PLAN.md`

The ignored `backend/.env.postgres` file was created as local machine state. It contains the
four generated passwords and must remain outside Git.

## Rollback status

`docker compose down` safely removes the container and project network while retaining the
named volume. Removing the volume would destroy both local databases and requires separate
project-owner approval. No rollback is currently needed.
