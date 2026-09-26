# DigitalOcean deployment and recovery plan

## Status

The application migration runtime is complete through the current Phase 13 work. Production-style
DigitalOcean deployment belongs to Phase 14 and has not been promoted. This file describes the
approved target and the evidence required before promotion.

## Target services

| Responsibility | Target |
| --- | --- |
| Frontend | Static site built from `npm run build` and `dist/` |
| API | Containerized FastAPI service |
| Authentication | Keycloak with a pinned image and persistent PostgreSQL database |
| Application data | Managed PostgreSQL with private connectivity and encrypted backups |
| Private files | S3-compatible private object storage |
| Workers | Explicit expiry, scanner, and reconciliation jobs |
| Delivery | GitHub checks followed by reviewed deployment promotion |

The deployed frontend must use the same six public settings as `.env.example`. All other credentials
belong in managed secret storage and must reach only the service that owns them.

## Network and access rules

- Expose the static frontend, FastAPI HTTPS endpoint, and Keycloak HTTPS endpoint through approved
  hostnames.
- Keep PostgreSQL and object-storage administration private.
- Restrict FastAPI CORS to deployed frontend origins.
- Validate OIDC issuer, audience, signature, and time claims at the API.
- Give migrations, API runtime, expiry processing, scanner, and reconciliation separate database
  identities.
- Give object-store jobs only the bucket and operations they need.

## Deployment order

1. Provision networking, PostgreSQL, private object storage, Keycloak persistence, secret entries,
   logs, and backup policies.
2. Apply Alembic with the migration identity and confirm the expected single head.
3. Configure the Keycloak realm, clients, redirect URIs, signing keys, and administrative ownership.
4. Deploy FastAPI and verify database, OIDC, object-store, worker, and safe-log checks.
5. Build the frontend from the reviewed commit and publish `dist/` with the deployed public values.
6. Run the complete synthetic administrator, manager, and employee journey.
7. Record the release commit, image digests, schema head, configuration owners, and rollback point.

No deployment step may create an automatic fallback to a different application runtime.

## Health and operations

Monitor at least:

- frontend availability and asset errors;
- FastAPI health, request latency, error rate, and authorization denials;
- Keycloak readiness, token failures, signing-key changes, and administrative events;
- PostgreSQL connections, storage, locks, replication, and backup completion;
- private-object errors, size growth, failed scans, and reconciliation differences; and
- worker success, retries, dead-letter state, and delayed expiry processing.

Logs must omit tokens, passwords, connection strings, private object keys, signed URLs, and document
contents. Retention and access need named owners before staging promotion.

## Backup policy

Back up the application and Keycloak databases on a documented schedule with point-in-time recovery
where the selected plan supports it. Version or snapshot private objects separately. Encrypt backups,
keep them outside the application account where practical, and record custody without placing keys or
exports in Git.

A successful backup job is not recovery proof. Restore each data class into an isolated target and
compare schema head, row counts, identity metadata counts, object counts, byte counts, and recorded
digests.

## Recovery order

1. Stop writes or place the affected service in a documented maintenance state.
2. Identify the exact release, schema head, database recovery point, Keycloak state, and object-store
   version set.
3. Restore PostgreSQL and Keycloak into isolated targets first.
4. Restore private objects and run reconciliation before enabling downloads.
5. Deploy the matching FastAPI image and run health, authentication, authorization, and file checks.
6. Publish the matching frontend only after the API boundary passes.
7. Reopen writes, monitor the agreed recovery window, and record the result.

Never point current application code at an unverified restored database. Never recreate deleted
external resources as an automatic rollback.

## Rollback

Application rollback selects a previously reviewed frontend build and FastAPI image that remain
compatible with the current schema. Schema rollback is allowed only when the migration plan names an
exact predecessor path and proves that no committed data would be lost. Otherwise, roll the
application forward with a corrective revision.

Keycloak and private-object rollback use verified backups, not image recreation alone. Record signing
key continuity, active sessions, object versions, and reconciliation state.

## Promotion gate

DigitalOcean staging can be promoted only after:

- infrastructure and secret review;
- fresh schema creation and repeatable migration;
- complete unit, API, database, authentication, storage, and browser gates;
- isolated database, identity, and object restore proof;
- restart proof without rebuilding or losing state;
- rollback rehearsal from recorded release artifacts;
- cost, monitoring, alert, retention, and on-call ownership; and
- explicit release signoff.
