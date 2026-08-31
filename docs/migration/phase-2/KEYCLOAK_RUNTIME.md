# Phase 2F local Keycloak runtime

## Status

**Completed on 2026-08-31.**

Phase 2F runs a local self-hosted Keycloak server against the separate `keycloak` PostgreSQL
database. It creates Keycloak's required internal schema, the built-in `master` realm, and one
local bootstrap administrator.

It does not create a Workloop realm, OIDC client, API audience, synthetic employee identity,
React login flow, or FastAPI token validator. Phase 3 owns those changes.

## Image and mode

The service uses official Keycloak `26.7.2`, released on 2026-08-19, pinned to OCI index digest:

```text
sha256:9d1f1b2b7261ff53c66cb1092dfcdc34a5fb77e81f9e6a6e75b8b6a795de8067
```

This release includes the security fixes listed in the upstream 26.7.2 release notes. The local
service uses `start-dev`. Development mode permits HTTP and other unsafe defaults for local work.
Never deploy this command to DigitalOcean, Azure, or any environment with real users or data.

The container reports:

```text
Keycloak 26.7.2
OpenJDK 21.0.12.1 LTS
Linux amd64
```

## Addresses

| Purpose | Local address |
|---|---|
| Login and administrator UI | `http://127.0.0.1:8080` |
| Administrator console | `http://127.0.0.1:8080/admin/` |
| Readiness | `http://127.0.0.1:9000/health/ready` |
| Liveness | `http://127.0.0.1:9000/health/live` |

Both ports bind only to `127.0.0.1`. Other computers on the local network cannot reach them
through these mappings.

## Database boundary

Keycloak connects as the PostgreSQL role `keycloak` to the database `keycloak`. It created 100
internal tables, all owned by that role. Keycloak manages these tables with its own Liquibase
changes. Workloop Alembic must never manage the Keycloak database.

The Workloop database still has zero application tables. The Keycloak container receives no
Workloop runtime URL, migration URL, PostgreSQL bootstrap password, or Workloop role password.

Keycloak data lives in PostgreSQL, not in the container. Replacing the container preserved the
master realm, local administrator, and master-realm signing-key identifiers.

## Credentials

`backend/.env.keycloak` is ignored by Git and contains only:

```text
KC_DB_PASSWORD
KC_BOOTSTRAP_ADMIN_USERNAME
KC_BOOTSTRAP_ADMIN_PASSWORD
```

The administrator username is `workloop-local-admin`. Its password was generated locally with
256 bits of randomness and was never displayed. The Keycloak database password matches the
separate value created in Phase 2C.

The bootstrap administrator is a temporary local administration mechanism. Phase 3 must review
its replacement, rotation, or removal before creating the Workloop realm. Never reuse these
passwords in DigitalOcean or Azure. Anyone with administrative Docker access to this computer
must be treated as able to inspect container environment values.

## Container restrictions

- Memory limit: 1 GiB.
- Runtime user: official-image UID 1000.
- Linux capabilities: all dropped.
- Privilege escalation: disabled.
- Host ports: loopback only.
- Database: external PostgreSQL container, not Keycloak's development file database.
- Health: readiness checks include Keycloak initialization and database connectivity.

The official image's UID 1000 uses group 0. It is still a non-root process and has all Linux
capabilities dropped. Production hardening and an optimized image remain required before cloud
deployment.

## Logging

Keycloak's runtime console output uses JSON. On each unoptimized development start, its launcher
prints four plain-text lines before the runtime logger begins. These lines report configuration
augmentation, development mode, and upstream deprecated default features. They contain no
credentials or connection strings.

The upstream warnings identify `identity-brokering-api:v1` and `twitter-broker:v1` as deprecated
defaults. Neither feature is configured or used by Workloop in this phase. Review Keycloak's
upgrade guide before changing the pinned version.

## Commands

Run from the repository root. Set the Docker path if needed:

```powershell
$docker = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
```

Start the local services:

```powershell
& $docker compose up --detach --wait postgres backend keycloak
```

Check Keycloak readiness:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9000/health/ready"
```

Show logs:

```powershell
& $docker compose logs keycloak
```

Stop only Keycloak:

```powershell
& $docker compose stop keycloak
```

Restart it:

```powershell
& $docker compose start keycloak
```

These commands retain the PostgreSQL volume. Do not use `docker compose down --volumes` or
`docker volume rm` without separate approval. The shared volume contains both Workloop and
Keycloak databases.

## Completion evidence

The Phase 2F gate passed on 2026-08-31.

| Check | Result |
|---|---|
| Image | Official Keycloak 26.7.2, pinned by OCI digest |
| Database | Connected as `keycloak` to `keycloak` |
| Schema | 100 Keycloak-owned internal tables |
| Workloop database | Zero application tables |
| Readiness and liveness | `UP` on the management port |
| Database health | Keycloak readiness reports its async database check `UP` |
| Administrator UI | HTTP redirect returned as expected |
| Administrator login | Token request and Admin API realm listing passed without displaying the token |
| Wrong password | Rejected with OAuth HTTP 400 |
| Realms | Only the built-in `master` realm exists |
| Synthetic users | None created |
| Graceful shutdown | Keycloak logged successful shutdown |
| Container replacement | Master realm, administrator, and signing-key identifiers persisted |
| Credential scope | No Workloop or PostgreSQL bootstrap secrets in Keycloak |
| Host binding | Ports 8080 and 9000 bound only to `127.0.0.1` |
| Container restrictions | 1 GiB limit, all capabilities dropped, no new privileges |
| Logs | 14 JSON runtime records and 4 safe launcher lines after final replacement |
| Secret scan | No password, token, or credential-bearing URL found in logs or tracked files |
| DigitalOcean | No resource created; cost remains USD 0 |

The first direct administrator-table query compared Keycloak's realm UUID to the text `master`
and returned zero. Joining through the realm table confirmed exactly one local administrator. The
first wrong-password test expected HTTP 401, while the OAuth endpoint correctly returned HTTP 400
for `invalid_grant`; the corrected check accepts only authentication-failure responses.

The first JSON assertion treated four pre-logger launcher messages as runtime log failures. A
separate check now records those unavoidable lines and verifies every subsequent runtime record
as JSON. All lines passed the secret check.

## Resource use

| Resource | Measured use |
|---|---:|
| Keycloak idle memory | About 560 MiB of the 1 GiB limit |
| Keycloak image | About 268 MB through Docker image inspection |
| Keycloak idle CPU | About 0.2% during the stable measurement |
| Shared PostgreSQL volume | About 78 MB after Keycloak initialization |

Startup briefly used more CPU while Quarkus initialized. The computer remained within the Docker
Desktop memory allocation recorded in Phase 2A.

## Rollback

Stopping and removing only the Keycloak container retains its database, realm, administrator,
and signing keys in PostgreSQL. Reverting the Phase 2F Compose and setup changes returns the local
stack to Phase 2E. Deleting the shared PostgreSQL volume would also destroy the Workloop database
and is not authorized.

## Remaining work

Phase 2G owns broader automated and GitHub checks. Phase 3 later owns the Workloop realm and OIDC
security design. Phase 2F authorization does not authorize either part.
