# Phase 6B completion record

## Status

The project owner authorized Phase 6B on 2026-09-07. The backend HTTP boundary now implements the
approved Phase 6A contract for the existing `/health` and `/api/v1/auth/token-check` operations.
Phase 6C remains separately gated and has not started.

## HTTP boundary

FastAPI now assigns a fresh lowercase UUIDv4 correlation ID before origin checks and routing, ignores
caller-supplied request identifiers, binds the generated value to structured logs, and returns it on
every response. Uvicorn access logging is disabled so raw paths and private identifiers do not bypass
the safe request log.

The boundary provides:

- the 24-code error registry, common safe error envelope, bounded validation details, required error
  headers, and the `/health` error exception;
- the exact local origin, CORS methods, request headers, exposed headers, 600-second preflight cache,
  and an empty cloud allowlist;
- declared and streamed 1 MiB request limits, rejected request compression, JSON media checks, and
  constants for the separately gated upload boundary;
- 15-second ordinary and 5-second health deadlines with cancellation propagation;
- strict request and response model bases, success envelopes, pagination, query, sort, strict JSON,
  and canonical idempotency-key helpers; and
- explicit operation IDs plus reviewed success, error, and correlation-header documentation for the
  two existing operations.

No business endpoint, upload route, idempotency record, external limiter store, frontend transport,
or cloud origin was added.

## Authorization and transaction boundary

The administrator branch dependency now checks only presence and canonical UUID syntax. It does not
open a preliminary transaction. `AuthorizedServiceExecutor` enters the existing
`AuthorizationTransactionFactory` once, passes any parsed administrator branch into that transaction,
and keeps Phase 5 context setup, branch verification, protected work, commit, rollback, timeout, and
cancellation under one owner.

The in-process rate-limit interface covers the approved public, authentication, protected-attempt,
invalid-token, authenticated-read, authenticated-write, and financial or approval classes. Phase 6B
uses an inactive implementation until public exposure supplies shared state. The HTTP boundary maps a
limiter refusal to the approved `429` body and `Retry-After` header.

## Verification

Focused middleware, helper, transaction, cancellation, authentication-dependency, configuration,
health, and logging tests passed during implementation. The final focused run contained 27 tests.

The settled local quality gate passed:

- 345 backend tests;
- Ruff lint and formatting checks;
- Pyright with zero errors and warnings;
- the locked Python dependency check;
- 33 frontend unit tests; and
- the legacy and migration production builds.

The workflow classifier routes this change through backend, frontend, and full-stack checks while
correctly leaving database-deep and authentication-configuration checks disabled. Phase 6B adds no
database revision and leaves the single Alembic head at `2c4d6e8f0a1b`.

The complete local gate used an isolated PostgreSQL 17.11, FastAPI, Keycloak, and migration-browser
stack. It built changed images once, applied the migration twice, passed Alembic current, heads, and
drift checks, configured Keycloak once, and passed the HTTP, authentication, browser, and log-safety
checks. It then stopped the stack without deleting its data, restarted the same images without a
build, and confirmed unchanged database and signing-key fingerprints. HTTP, authentication, and
browser checks passed again without reconfiguring Keycloak. The gate retained no synthetic Workloop
rows or Keycloak users and removed its containers, network, and volume.

The required GitHub result is reported with the task handoff after the commit passes. The verification
workflow does not permit a second documentation-only push to store that URL.

## Resource and rollback boundary

The existing `workloop-clinic` stack remained running with three services. Its
`workloop-clinic_postgres_data` volume kept its `2026-08-31T07:31:48Z` creation time and stayed on
PostgreSQL 16. The Phase 6B gate did not attach, upgrade, recreate, or delete it. Verification used
only local synthetic data and created no cloud, SMTP, paid-service, or production resource.

Rollback removes the HTTP middleware, handlers, helper modules, service executor, tests, and workflow
hook together. No database or data rollback is required.

## Stop condition

Phase 6B closes when the commit containing this record passes the path-routed GitHub workflow. Stop
before Phase 6C and request separate project-owner authorization.
