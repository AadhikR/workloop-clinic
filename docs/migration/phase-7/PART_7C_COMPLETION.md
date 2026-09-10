# Phase 7C completion record

## Status

The project owner authorized Phase 7C and approved idempotency decisions `7C-IDEM-D1` and
`7C-IDEM-D2` on 2026-09-10. The implementation and complete local gate are finished. The required
GitHub result remains the final phase check and will be reported in the task handoff.

Phase 7D has not started and remains unauthorized.

## Organization write boundary

FastAPI now exposes the four approved administrator mutations:

- `PATCH /api/v1/company`;
- `POST /api/v1/branches`;
- `PATCH /api/v1/branches/{branchId}`; and
- `DELETE /api/v1/branches/{branchId}`.

Company updates are selector-free and accept only the approved legal-company fields plus
`expectedUpdatedAt`. Branch creation is also selector-free. Branch update and deletion require one
canonical `X-Workloop-Branch-ID` value that matches the path UUID. The server derives tenant and
actor scope from the verified principal in the existing authorized transaction.

Optimistic concurrency compares the public millisecond timestamp while retaining database
microsecond precision. A stale update returns `state_conflict`. Branch deletion checks the version,
appends its approved audit event, attempts the guarded delete, and forces deferred constraints before
the service returns. Any retained employee, department, staffing, audit, or other foreign-key
reference produces `branch_conflict` and rolls back the audit event and deletion.

The service accepts no company creation, company deletion, branch cascade, logo upload, payroll
routing cascade, employee mutation, department mutation, staffing mutation, or Keycloak
provisioning operation.

## Idempotency boundary

Alembic revision `31d7b4c8e2f0`, based on `2c4d6e8f0a1b`, adds the approved
`idempotency_records` table. The primary key binds one canonical UUIDv4 key to one verified
application user across operations. Stored scope, the versioned fingerprint, completion state,
response replay data, seven-day retention floor, restrictive foreign keys, forced RLS, column-level
completion grant, and deferred completion trigger match decisions `7C-IDEM-D1` and `7C-IDEM-D2`.

`POST /api/v1/branches` claims its key, creates the branch, appends `branch_created`, and completes
the replay record in one transaction. An identical retry rechecks current authorization before it
returns the stored 201 response and relative `Location`. A changed request returns
`idempotency_conflict`; a held advisory lock returns `idempotency_in_progress`. Failed mutations do
not retain a reservation.

The recovery namespace and status routes expose no stored response or key in a URL. The browser
keeps unresolved intents in namespace-bound session storage for no more than seven days. It checks
their status after session restoration, refreshes completed work, requires explicit confirmation
before resubmitting a missing intent, and never retries a mutation automatically.

The approved cleanup function takes no arguments and returns only a row count. It validates an
active trusted human context, derives the company from that context, and deletes at most 100 expired
rows in the approved order. Runtime cannot select another user's record or delete directly from the
table. Focused proof showed that an administrator can clean an expired record owned by another user
in the same company without crossing tenants or deleting an unexpired record.

## Migration settings and cutover

The migration settings screen supports legal-company updates and branch creation, editing, guarded
deletion, stale-write review, and recovery of unresolved branch creation. Exact camelCase adapters
validate every request and response. The shared HTTP client sends protected requests only to its
approved API origin and does not retry mutations.

Before migration writes became authoritative, `saveCompany`, `saveCompanyLogo`, `createBranch`, and
`deleteBranch` in `src/utils/storage.js` were changed to fail before any Supabase request. The old
company serializer was removed. Unrelated payroll and later-phase storage behavior remains in the
legacy build.

The organization-administration cutover record now names the real backend and migration frontend
locators. Both read and write authority are `migration-fastapi`, and it is the only writable system
for this cutover unit. The rollback order disables the migration mutations first, restores the four
legacy writer implementations, restores legacy readers, records legacy Supabase as the sole
authority, and then verifies unchanged synthetic company and branch data. This order never enables
both writers together. The other six Phase 7 cutover records were not changed.

## Verification

Focused checks covered strict organization schemas, all four API routes, selector rules, safe errors,
tenant and branch scope, staff and inactive-account denial, stale versions, guarded deletion,
idempotent first commit and replay, fingerprint conflicts, held locks, current-authorization replay,
rollback cleanup, retention, model parity, and the approved cleanup function.

Frontend checks covered request and response validation, cancellation, stale-write review, branch
selection, unresolved-key retention and recovery, absence of automatic retry, the four frozen legacy
writers, and the absence of Supabase imports from the migration build. The complete browser journey
saved company settings, rejected a referenced-branch deletion without changing data, created a
branch, updated it, deleted it, and returned to the chooser.

The settled quality gate passed:

- 406 backend tests;
- Ruff lint and formatting checks;
- strict Pyright with zero errors;
- the locked Python dependency check;
- 91 frontend unit tests;
- both production builds;
- frontend isolation across 449 legacy modules and 30 migration modules; and
- the Phase 7 cutover and evidence validators.

The complete local gate used Compose project `workloop-phase7c-final` on PostgreSQL port 25432, API
port 28000, and Keycloak ports 28080 and 29000. It used a fresh temporary PostgreSQL volume, built
the backend image once, applied migrations twice, confirmed the sole head, found no pending
migration operations, downgraded exactly to `2c4d6e8f0a1b`, confirmed the Phase 7C table and cleanup
function were absent, and upgraded back to `31d7b4c8e2f0`.

The HTTP, Phase 7B regression, Phase 7C database and RLS, Keycloak-to-FastAPI authentication,
browser, and log-safety checks passed. The Phase 7B synthetic row-state fingerprint remained
`4a0731e2e75bb0a0e534227af6500ebe64dc2ed9ad19ffe0fb8d315311fc18e3`. The Phase 7C mutation
fingerprint was `dd5e4f94ae8c89f41e738b8fe29f80f1e9a975bf49626f377ebd594fb9e68b55`.

The gate recreated the containers without rebuilding or deleting the temporary data volume. The
database catalogue fingerprint remained `91cdc830c87f0dc6d85f0a8615c8c83b`, both Keycloak signing
key IDs remained unchanged, and all three container image IDs matched. Authentication and the full
browser journey passed after restart without another Keycloak configuration pass. All synthetic
Workloop rows and Keycloak users returned to zero.

## Resource boundary

Verification used local synthetic data only. It accessed no production data, cloud resource, paid
service, or persistent external credential. After recording evidence, the gate removed the isolated
containers, network, generated credentials, and temporary PostgreSQL volume.

The protected `workloop-clinic_postgres_data` volume was not attached, upgraded, recreated, or
deleted. It remains present.

## Stop condition

Phase 7C closes when the commits containing this record pass the path-routed `Migration foundation`
workflow. Stop before Phase 7D and require separate project-owner authorization.
