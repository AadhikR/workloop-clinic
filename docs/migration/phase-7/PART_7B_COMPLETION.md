# Phase 7B completion record

## Status

The project owner authorized Phase 7B on 2026-09-10. The implementation and complete local gate are
finished. The required GitHub result remains the final phase check and will be reported in the task
handoff.

Phase 7B adds organization reads only. Legacy Supabase remains the sole organization write
authority. Phase 7C has not started.

## Organization read boundary

FastAPI now exposes the four approved operations:

- `GET /api/v1/company`;
- `GET /api/v1/employer`;
- `GET /api/v1/branches`; and
- `GET /api/v1/branches/{branchId}`.

Strict response schemas expose the legal-company projection only to administrators. Managers and
employees receive the safe-employer projection and their own safe branch projection. Scoped
repositories select explicit columns and run inside the existing authorization transaction, where
PostgreSQL session context and RLS remain authoritative.

The server derives company and staff branch identity from the trusted principal. An administrator
branch detail request requires one canonical `X-Workloop-Branch-ID` value matching the path UUID.
Staff cannot use that header to select a branch. Inaccessible, cross-tenant, and cross-branch IDs use
the generic not-found response.

Branch listing supports the approved search, sort, limit, and encrypted keyset cursor contract. The
cursor is short-lived and bound to the actor, role, company, branch, operation, and normalized query
context. Malformed, expired, tampered, or context-mismatched cursors are rejected without exposing
their contents.

No organization write route, protected mutation, Alembic revision, model, RLS policy, grant, or
Keycloak provisioning change was added. The single Alembic head remains `2c4d6e8f0a1b`.

## Migration consumer

The migration build now loads organization data through the Phase 6 HTTP client and validates exact
camelCase response shapes. Its company context selects the legal-company view for administrators and
the safe-employer view for staff.

The administrator branch chooser may retain a branch UUID in tab-scoped `sessionStorage`. It uses
that value only after finding it in the complete current branch response. A missing, malformed,
stale, or inaccessible value is cleared and opens the chooser. Cancellation leaves no selection,
and neither the adapter nor the context falls back to the first branch or retries another branch.
The migration organization modules contain no Supabase import.

## Cutover and rollback

The organization-context cutover record replaces its planned reader locator with the backend and
migration-frontend implementation files. Fresh synthetic evidence covers the four routes, scoped
denials, unchanged read state, branch-selection behavior, restart persistence, authentication,
browser checks, log safety, fixture cleanup, and temporary-resource cleanup.

Read authority is now `migration-fastapi`. Write authority and the sole writable-system declaration
remain `legacy-supabase`. The other six Phase 7 cutover records were not changed.

The tested rollback sequence first confirms that no migration organization writer exists and that
legacy Supabase remains the only writable system. It then disconnects the migration organization
consumer, restores the legacy company context as read authority, validates the cutover declaration
and frontend build isolation, and reruns the scoped synthetic reader proof. No database or identity
rollback is required.

## Verification

Focused backend tests covered all four routes, exact projections, field leakage, administrator and
staff scope, inactive accounts, malformed and duplicate headers, malformed IDs, unknown query
fields, search, sorting, pagination, cursor binding, and generic not-found behavior. Focused frontend
tests covered exact camelCase parsing, all-page branch loading, validated session retention, stale
and malformed selection cleanup, chooser behavior, cancellation, safe errors, header placement, and
the absence of a first-branch fallback.

The settled local quality gate passed:

- 390 backend tests;
- Ruff lint and formatting checks;
- strict Pyright with zero errors;
- the locked Python dependency check;
- 87 frontend unit tests;
- the legacy and migration production builds;
- frontend build isolation across 449 legacy and 28 migration modules; and
- validation of all seven Phase 7 cutover records and the organization evidence digest.

The complete local gate used the isolated `workloop-phase7b-final` Compose project on PostgreSQL
port 15432, API port 18000, and Keycloak ports 18080 and 19000 with a fresh temporary PostgreSQL
volume. It built the changed image once, applied migrations twice, confirmed the current and sole
Alembic head, and found no pending migration operations. The HTTP, Keycloak-to-FastAPI,
organization database/RLS, application, browser, and log-safety checks passed.

The database/RLS proof covered administrator tenant reads, staff own-branch reads, cross-tenant and
cross-branch denial, inactive-account denial, and unchanged database state after denied reads. Its
synthetic row-state fingerprint was
`4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3`.

The gate recreated the isolated containers without rebuilding or deleting their data volume. The
catalog fingerprint remained `eeb158a9d2fcda117c6d603498d048b2`, and both Keycloak signing key IDs
remained unchanged. Migrations and authentication passed after restart without reconfiguring
Keycloak, followed by the browser and log-safety checks. All synthetic Workloop rows and Keycloak
users returned to zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording the evidence, the gate removed the
isolated containers, network, temporary credentials, and PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, or
deleted and remains present.

## Stop condition

Phase 7B closes when the commits containing this record pass the path-routed `Migration foundation`
workflow. Stop before Phase 7C and request separate project-owner authorization.
