# Phase 5G completion record

## Status

Phase 5G completed its local gate on 2026-09-06 after the project owner authorized this part only.
Work started from clean, synchronized commit `92045f82370b342eac5c3c0fec61ea44a668073b`
on branch `migration/fastapi-keycloak`. Alembic head is now `1b29d4e7f860`.

The commit containing this record must pass the existing GitHub workflow. The task handoff reports
that run, so this file does not need a second commit for the workflow ID. Phase 5H has not started
and requires separate project-owner authorization.

## Remaining domain enforcement

Phase 5G uses four chained Alembic revisions:

- `e96f7a1b4c53` adds 22 policies for employee documents, insurance, and notifications.
- `f07a8b2c5d64` raises the total to 39 policies by adding contracts, offboarding, and assets.
- `0a18c3d6e75f` raises the total to 68 policies by adding training, certifications, appraisals,
  CME, incidents, and letters.
- `1b29d4e7f860` adds the append-only audit table and raises the total to 70 policies across 20
  Phase 5G tables.

Together with Phases 5E and 5F, all 55 current tables now have their approved RLS disposition. The
new policies enforce tenant, verified branch, employee self, current direct-report, nullable-branch,
and dedicated expiry-job scope. Runtime and expiry grants match the approved command and column
ceilings. Notifications permit recipient reads and `read_at` updates only; the expiry login receives
only its approved source columns and notification insert columns.

The verifier compares every Phase 5G policy identity and command shape with the machine-readable
catalogue. It also confirms that the remaining legacy Supabase policies are absent. The Phase 5F
NAFIS and compliance policies remain unchanged.

## Protected notification and audit writers

`create_workflow_notification(text,text)` accepts only the approved leave-decision, payslip, and
roster producer types. It loads the source inside trusted scope, derives the recipient and content,
and deduplicates repeated calls. It accepts no caller-supplied recipient, company, branch, title, or
body.

The new `audit_events` table records immutable, safe event metadata. Runtime callers receive no
direct insert, update, or delete grant. Admin reads separate tenant-wide events from selected-branch
events, while managers and employees have no direct audit read. The expiry login can insert only
the fixed scheduled-job actor shape and approved metadata keys.

`append_audit_event(text,text,uuid,text[],text,jsonb)` derives company, branch, and actor from trusted
transaction context. Its action, entity, changed-field, and metadata allowlists exclude private
document paths and sensitive employee values. It verifies the source row, its current workflow
state, branch scope, caller role, and direct-report relationship where manager authority applies.
Unknown, stale, missing, cross-scope, and false-state events fail before insert.

The retained `admin_execute_shift_swap(uuid,uuid)` function now appends its event in the same
transaction as the protected roster and request changes. Audit failure rolls back the business
mutation. The asynchronous application wrapper uses the caller's existing transaction and never
commits or rolls back on its own.

Both new functions use `SECURITY DEFINER`, belong to `workloop_migration`, pin the search path to
`pg_catalog, public, pg_temp`, revoke `PUBLIC`, and grant execution only to the approved login.

## Verification

The backend gate passed 247 tests. Ruff lint and formatting passed, strict Pyright reported no
errors or warnings, and the dependency check found no broken requirements.

The frontend regression gate passed 32 unit tests, four migration-build isolation tests, the main
production build, and the migration production build. The main build retains its existing warning
for one generated chunk larger than 500 kB.

The database gate used the isolated Compose projects `workloop-phase5g-dev` and
`workloop-phase5g-verify` with PostgreSQL 17.11. A fresh empty database upgraded through every new
revision. Each revision passed its exact policy, grant, helper, table, and rollback-state check.
Every new revision then downgraded independently to its parent and returned to head.

The current-head gate passed the inherited schema, migration, trigger, fixture, repository,
transaction-context, Phase 5E, Phase 5F, ownership, role, and Supabase-removal checks. The focused
Phase 5G verifier covered admin, manager, employee, peer, cross-branch, cross-tenant, missing-context,
notification, audit, expiry-job, immutable-history, false-state, and atomic-rollback cases.

The isolated backend and Keycloak services passed health and live authentication checks. Migration
was repeatable, Alembic reported one head and no metadata drift, and the backend connected as
`workloop_runtime`. After a no-build restart, the database catalogue fingerprint and both Keycloak
signing keys were unchanged. Authentication passed again, synthetic application and Keycloak users
were absent, and the service log scan found no tokens or database credentials.

## Limits and rollback

Phase 5G adds no business route, frontend feature, storage adapter, upload or signing behavior,
Keycloak configuration change, cloud resource, persistent fixture, real data, or committed secret.
Cloud cost remains zero.

The two isolated Phase 5G projects and their PostgreSQL volumes were removed after verification.
The preserved `workloop-clinic_postgres_data` volume remains on PostgreSQL 16.15 at its prior
Alembic head, with all five identity-root tables empty and its pre-gate database fingerprint
unchanged. During restoration, the current base Compose file briefly tried its PostgreSQL 17.11
image against that version 16 volume. PostgreSQL rejected the data directory before server startup
or initialization. The service was restored with the exact cached PostgreSQL 16.15 image, and the
fingerprint comparison confirmed that no catalog or data change occurred.

Each Phase 5G policy revision downgrades independently. The audit revision downgrade is safe only
while `audit_events` is empty; later application use must roll back before the database revision.
Earlier Phase 5E and 5F policies, grants, functions, and table flags remain exact at every Phase 5G
rollback boundary.

Phase 5H remains separate and has not started.
