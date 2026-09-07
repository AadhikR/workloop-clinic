# Phase 6C completion record

## Status

The project owner authorized Phase 6C on 2026-09-07. The migration frontend now sends every FastAPI
request through one HTTP client. Authentication uses that client for the existing protected account
check, and the browser verifier uses the same client for the public health check. Phase 6D remains
separately gated and has not started.

## HTTP client

`migration/src/http.js` owns API destination checks, request construction, browser deadlines,
cancellation, response parsing, correlation IDs, and safe client errors.

The client:

- accepts only `/health` and `/api/v1/...` paths relative to the configured API root;
- rejects absolute URLs, protocol-relative URLs, path traversal, fragments, backslashes, Supabase,
  localhost aliases, and every origin outside the existing `127.0.0.1:8000` and
  `127.0.0.1:18000` allowlist before it calls `fetch`;
- requires each call to declare public or protected access, reads the current access token for each
  protected call, and never reads or sends a token for a public call;
- fixes credentials to `omit`, redirects to `error`, caching to `no-store`, and response acceptance to
  JSON;
- supports the approved JSON request headers and body without retrying a request;
- enforces the 10-second health and 20-second ordinary browser deadlines while keeping caller
  cancellation distinct from a timeout;
- accepts only lowercase UUIDv4 correlation IDs and requires the response header and error body to
  agree; and
- handles the health body, API data and collection envelopes, and bodyless `204` responses.

Server messages do not reach the user. The client maps the approved registry to authentication,
authorization, validation, conflict, rate-limit, availability, timeout, and unexpected errors. It
also provides separate safe results for caller cancellation, network failure, and malformed
responses. Required `WWW-Authenticate`, `Allow`, and `Retry-After` headers remain part of response
validation.

## Authentication and browser boundary

`AuthenticationSession` owns one client instance. Its token provider reads only the current
in-memory OIDC user. The existing account states remain unchanged: `204` signs in, `401` removes the
in-memory user and expires the session, `403` marks the application account unavailable, and `503`
or a browser transport failure marks the service unavailable. Other failures remain generic.

The Phase 3 browser verifier now makes a real public health request through that same client after
login. It checks that health has no authorization header, every account check has a bearer header,
and no bearer header leaves the approved API origin. The existing login, renewal, reload restoration,
changed-email, disabled-account, logout, replay, state, nonce, and durable-storage checks remain in
place.

No business screen, business endpoint, legacy `src/` import, Supabase call, FastAPI code, Keycloak
configuration rule, database revision, token store, mutation retry, or idempotency recovery flow was
added.

## Verification

Focused development checks passed:

- 15 HTTP client tests covering public and protected calls, fresh token reads, approved destinations,
  transport settings, JSON requests, `204`, data and collection envelopes, malformed and unexpected
  responses, correlation failures, all approved client error groups, deadlines, caller cancellation,
  and network failure;
- 15 affected authentication tests covering in-memory storage, account-state mapping, expiry,
  renewal, response races, and the existing callback and logout behavior; and
- changed-file ESLint checks for the client, authentication module, client tests, and browser
  verifier.

The settled frontend checks passed with 48 unit tests, the migration production build, and the legacy
production build. The migration isolation suite built the real graph and kept legacy `src/` and
Supabase dependencies out of it.

The complete local gate used the separate `workloop-phase6c` Compose project with PostgreSQL 17.11,
FastAPI on port 18000, Keycloak on ports 18080 and 19000, the migration frontend on port 5174, and a
fresh temporary volume. It built the current backend image once, applied the schema twice, and
configured the existing access-token subject mapper once. The Phase 6B HTTP verifier and the Phase 3
Keycloak-to-FastAPI protocol verifier passed.

The three-persona browser verifier then passed login, renewal, restoration, account-state, storage,
public health, protected token-check, and token-destination checks. Backend and Keycloak log scans
found no token, database credential, generated secret, identity subject, or account-query leak. All
synthetic Workloop tables and Keycloak users returned to zero. The gate removed its containers,
network, and PostgreSQL 17 volume.

The first pre-gate browser attempt used the long-running stack and reached its older backend image,
which returned `503` during application-user lookup. The preserved stack was not rebuilt or
restarted. The fresh isolated gate used the current image and passed.

The required GitHub result will be reported in the task handoff after the implementation commit
passes. Per the verification workflow, no later documentation-only commit will store that URL.

## Resource and rollback boundary

The existing `workloop-clinic` stack remains running with three services. Its
`workloop-clinic_postgres_data` volume kept its `2026-08-31T07:31:48Z` creation time and remains on
PostgreSQL 16. Phase 6C did not attach, upgrade, recreate, delete, or restart it. Verification used
only local synthetic data and created no cloud, SMTP, paid-service, or production resource.

Rollback removes the HTTP client and its tests, restores the direct migration authentication account
check, and removes the browser transport assertions and this record. It requires no backend, realm,
schema, or data rollback.

## Stop condition

Phase 6C closes when the implementation commit passes the path-routed GitHub workflow. Stop before
Phase 6D and request separate project-owner authorization.
