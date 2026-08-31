# Phase 3E application-user resolution

## Status

**Implementation and local gate passed on 2026-08-31. GitHub checks are pending.**

Phase 3E maps a verified Keycloak access token to one active Workloop application user. It adds no
role, company, employee, manager-scope, or business authorization. It creates no persistent user,
provisioning path, frontend, schema revision, or Keycloak setting.

## Resolution boundary

`require_application_user` runs after `require_access_token`. It passes only the verified issuer and
opaque subject to `ApplicationUserResolver`. The resolver checks the issuer against the configured
issuer again, rejects malformed subjects before opening a database connection, and runs one bound
query against `app_users`.

The query selects only the application-owned UUID and account status. It does not select or inspect
email, profile, role, company, employee, manager, realm-role, or client-role data. `LIMIT 2` lets the
resolver reject an unexpected duplicate even if the database constraint is missing or corrupt.

Exactly one row with a UUID application ID and `active` status succeeds. Missing, duplicate,
`pending_identity`, `disabled`, malformed-status, and malformed-ID results all receive the same
generic `403` response:

```json
{
  "detail": {
    "code": "application_account_unavailable",
    "message": "Application account unavailable"
  }
}
```

The response does not reveal whether a mapping exists or why it was rejected. Token failures keep
the Phase 3D generic `401` response and `WWW-Authenticate: Bearer` header.

## Database failure behavior

The lookup has a five-second default deadline covering connection-pool acquisition and query
execution. `APPLICATION_USER_LOOKUP_TIMEOUT_SECONDS` accepts values above zero and no greater than
30 seconds. A timeout or database error returns this generic `503` response:

```json
{
  "detail": {
    "code": "application_account_lookup_unavailable",
    "message": "Service temporarily unavailable"
  }
}
```

FastAPI logs only `application_user_lookup_failed`. It does not log the token, claims, issuer,
subject, user record, SQL, database URL, or internal exception.

## Route behavior

`GET /api/v1/auth/token-check` now requires both a valid access token and one active application
mapping. Success remains an empty `204` response with `Cache-Control: no-store`, so the route does
not disclose claims or application-user data.

The Phase 3 protocol verifier creates a temporary mapping for its temporary Keycloak identity. It
checks missing, pending, disabled, and active behavior, then removes both records. The application
mapping uses a reserved test UUID. Each run removes stale use of that UUID before testing and
confirms zero matching rows afterward. The test does not create a provisioning or runtime write
path. FastAPI retains read-only access to the identity tables.

## Test evidence

Local validation on 2026-08-31 passed:

- 76 backend tests, including active, missing, duplicate, pending, disabled, malformed mapping,
  malformed input, changed email, ignored role and company claims, database failure, lookup timeout,
  safe response, and log leakage cases.
- Ruff lint and format checks, strict Pyright, and `pip check`.
- Fourteen legacy frontend unit tests and the production build.
- Compose configuration validation and healthy PostgreSQL, FastAPI, and Keycloak services.
- Repeated Alembic upgrade, current, heads, and metadata checks at `f41c9a7b23d1`.
- Real Authorization Code and PKCE access-token checks against missing, pending, disabled, and active
  Workloop mappings.
- Keycloak container replacement, repeated subject-mapper configuration, and a second live flow
  against the persisted realm.
- Zero retained users in `workloop-dev` and zero retained `app_users` rows after the protocol tests.
- Backend service-log scanning for authorization headers, bearer tokens, identity fields, database
  URLs, SQL text, and test claim markers.

GitHub Actions runs 16 and 17 were also checked through the GitHub API before implementation. Every
backend, frontend, full-stack authentication, realm-upgrade, and persistence job passed for the
Phase 3D commits.

## Security review

An independent security review found no authorization bypass, claim-trust flaw, SQL injection,
active-status bypass, token or JWKS regression, or sensitive error leakage. Its first pass found two
availability and test-cleanup gaps:

- The database lookup had no total deadline. The resolver now applies the bounded timeout described
  above and has a stalled-query test.
- Abrupt test termination could leave a random active mapping that later runs could not identify.
  The verifier now uses a reserved test UUID, removes stale use before testing, deletes it in
  `finally`, and verifies its absence.

The reviewer checked the fixes, ran all 76 backend tests in an isolated source container, and
returned no findings. A real locked-query or exhausted-pool integration test remains a test gap.
The reserved UUID must remain reserved for this local verifier.

## Rollback

Removing the resolver, application-user dependency, lookup timeout setting, and Phase 3E tests
returns the route to token-only Phase 3D behavior. No database migration, realm setting, persistent
identity, credential, or cloud resource changed. Do not delete the PostgreSQL volume or Keycloak
realm as part of rollback.

## Next part

Phase 3F remains on hold. It owns the separate React migration build and requires separate
project-owner authorization. Phase 3E does not authorize it.
