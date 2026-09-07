# Phase 6E completion record

## Status

The project owner authorized Phase 6E on 2026-09-07. The implementation and complete local gate are
finished. The required GitHub result remains the final phase check and will be reported in the task
handoff.

Phase 6E adds a non-business API sample only. Every business screen and write path still uses legacy
Supabase. Phase 6F has not started.

## Sample API

`GET /api/v1/public/status` uses operation ID `get_public_status` and returns exactly
`{"data":{"status":"ok"}}`. It has no authentication dependency and opens no authorized
transaction. Its public request bucket uses the approved trusted-IP limit.

`GET /api/v1/account/me` uses operation ID `get_current_account`. It verifies the Keycloak access
token, resolves the PostgreSQL application principal, applies the authenticated-read limits, and
enters one service-owned authorized transaction. It returns only `appUserId`, `role`, `companyId`,
nullable `employeeId`, and nullable `branchId`. It accepts no query parameter and requires no branch
header.

Both operations use strict Pydantic response models, the Phase 6A data envelope, server-generated
correlation IDs, `Cache-Control: no-store`, safe errors, the ordinary request deadline, exact CORS,
and reviewed OpenAPI declarations. The protected operation declares bearer security. The public
operation declares none.

## Migration screen

The migration authentication screen calls both operations through the Phase 6C client. The public
call declares public access, so the client never reads or forwards a token. The current-account call
mounts only after the authentication session reaches `signed-in`, which means the in-memory user has
already passed the token and account check.

The screen shows the public status and the five approved current-account fields. It adds no business
navigation or editable field. Component cleanup cancels either in-flight request. The sample client
rejects extra fields, malformed UUIDs, unsupported roles, and invalid role-link shapes.

## Verification

Focused checks passed during development:

- seven backend sample-route and OpenAPI tests covered the exact public response, absence of an
  authentication or transaction dependency, all three roles, the exact protected projection, no
  branch requirement, guessed identity input, missing authentication, unavailable authorization
  context, rate-limit classes, strict schemas, headers, operation IDs, and security declarations;
- the affected backend HTTP, authorization-dependency, and service-execution set passed with 44
  tests, including deadline, cancellation, rollback, safe-error, and correlation behavior;
- three frontend sample-client tests covered public and protected access declarations, cancellation,
  exact response validation, roles, nullable links, and malformed responses; and
- the affected authentication and sample-client set passed with 18 tests, followed by changed-file
  ESLint checks and the migration production build.

The settled local checks passed with 352 backend tests, Ruff lint and formatting, strict Pyright,
`pip check`, 71 frontend unit tests, both production builds, and the frontend isolation verifier. The
isolation verifier scanned 449 legacy modules and 23 migration modules.

The complete local gate used the separate `workloop-phase6e` Compose project with PostgreSQL 17.11,
FastAPI on port 18000, Keycloak on ports 18080 and 19000, the migration frontend on port 5174, and a
fresh temporary volume. It built the backend image once, applied the schema twice, confirmed the
single Alembic head `2c4d6e8f0a1b`, and configured the existing access-token subject mapper once.

The Phase 6B HTTP verifier and Phase 3 Keycloak-to-FastAPI protocol verifier passed. The browser gate
then ran synthetic admin, manager, and employee accounts through the public status and protected
current-account operations. It checked the exact displayed role and identifiers, token-free public
requests, bearer-protected account requests, approved token destinations, renewal, restoration,
disabled-account handling, logout, nonce and state rejection, and durable-storage absence.

Before restart, the database fingerprint was `eeb158a9d2fcda117c6d603498d048b2` and Keycloak had two
signing keys. The gate recreated the isolated containers without rebuilding. The database
fingerprint, signing-key set, and image identities stayed unchanged. The HTTP, protocol, and
three-persona browser checks passed again without another Keycloak configuration pass. Backend and
Keycloak log scans found no token, database credential, generated secret, identity subject, or
account-query leak.

All synthetic Workloop rows and Keycloak users returned to zero. The gate removed the temporary
containers, network, and PostgreSQL volume.

Database-history, deep RLS, and database-function checks were not repeated because Phase 6E adds no
database revision, policy, grant, role, function, or repository query.

## Resource and rollback boundary

The existing `workloop-clinic` PostgreSQL, FastAPI, and Keycloak services remain healthy. The
`workloop-clinic_postgres_data` volume still has its `2026-08-31T07:31:48Z` creation time. Phase 6E
did not restart, rebuild, attach, upgrade, recreate, or delete that stack or volume.

Verification used local synthetic identities only. It accessed no Supabase account, production data,
SMTP service, paid service, or cloud resource.

Rollback removes the two sample routes and response schemas, authenticated-read dependency, public
rate-limit classification, migration sample client and view, focused tests, browser assertions, and
this record. It requires no schema, data, Keycloak, or legacy-build rollback.

## Stop condition

Phase 6E closes when the implementation commit passes the path-routed `Migration foundation`
workflow. Stop before Phase 6F and request separate project-owner authorization.
