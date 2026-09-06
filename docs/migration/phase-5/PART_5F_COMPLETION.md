# Phase 5F completion record

## Status

Phase 5F completed its local gate on 2026-09-06 after the project owner authorized this part only.
Work started from clean, synchronized commit `dca5a24dd57627dd360c7de1f892f443eb497d85`
on branch `migration/fastapi-keycloak`. Alembic head is now `d85a6f0c3b42`.

The commit containing this record must pass the existing GitHub workflow. The task handoff reports
that run, so this file does not need a second commit for the workflow ID. Phase 5G has not started
and requires separate project-owner authorization.

## Database enforcement

Phase 5F uses three chained Alembic revisions:

- `b63e4d8a1f20` adds payroll and finance RLS for nine tables and 22 policies.
- `c74f5e9b2a31` adds leave RLS for seven tables and 22 policies.
- `d85a6f0c3b42` adds attendance and roster RLS for 11 tables and 33 policies.

The 77 policies cover exactly the 27 tables approved in the Phase 5A catalogue. Each table, login,
and SQL command has at most one permissive policy. Select and delete policies use `USING`, insert
policies use `WITH CHECK`, and update policies use both. The tables do not use forced RLS, so the
migration owner keeps the approved migration and synthetic-seed path.

Human policies authenticate the direct runtime login, require the human actor shape and business
date, and compare the full database-resolved principal with transaction-local context. Admin
policies enforce tenant or verified branch scope. Staff policies enforce employee self scope,
current one-level direct reports, or inclusive active delegation dates. Missing, malformed,
partial, stale, mismatched, and guessed context values return no rows.

The revision chain preserves immutable issued payslips and append-only payroll approval history,
advance repayments, compliance overrides, leave audit records, clock events, and attendance audit
records. Published roster rows cannot be changed directly. The protected shift-swap function is
the only approved mutation path for them. Nullable compliance overrides separate tenant-wide rows
from rows bound to the selected branch.

Runtime table grants match the Phase 5A SQL operation ceilings. No Phase 5F table has an expiry
policy or grant. The runtime and expiry roles remain unable to own objects, create objects in
`public`, inherit privileged membership, switch to privileged roles, or bypass RLS.

## Protected functions and delegation

Phase 5F hardens the retained `replace_payroll_entries`, `record_advance_repayment`, and
`admin_execute_shift_swap` functions without changing their public signatures. Each function now
checks the direct `session_user`, human context, complete active admin principal, tenant, selected
branch, object state, affected employees, caller actor, and operation-specific values. A failed
check aborts the transaction without changing business data.

The only new helper is `can_act_for_delegated_leave(uuid)`. It returns a boolean and exposes no
employee row. It requires the direct runtime login and a complete active principal. It accepts only
current reporting relationships and delegations whose inclusive dates contain the business date.
Missing, future, expired, inactive, cross-tenant, and cross-branch relationships return false.

All four functions use `SECURITY DEFINER`, belong to `workloop_migration`, pin the search path to
`pg_catalog, public, pg_temp`, revoke `PUBLIC`, and grant execution only to `workloop_runtime`.

## Approval rules

The policies enforce the Phase 5A separation rules that belong at the database row boundary. A
payroll creator or submitter cannot approve or reject the same run. Leave owners cannot approve
their own requests, and manager or delegate decisions remain limited to current direct reports.
Expense owners cannot approve their own claims. Employees cannot approve their own attendance
regularisation or shift swaps. Employees may withdraw only their own pending salary advance and
may cancel only their own pending leave request.

FastAPI remains responsible for field allowlists, exact state transitions, calculations,
multi-row validation, protected workflow calls, and affected-row checks. RLS supplies a second
tenant, branch, employee, manager, delegate, state, and actor boundary.

## Verification

The backend gate passed 242 tests. Ruff lint and formatting passed, strict Pyright reported no
errors or warnings, and the dependency check found no broken requirements.

The frontend regression gate passed 32 unit tests, four migration-build isolation tests, the main
production build, and the migration production build. The main build retains its existing warning
for one generated chunk larger than 500 kB.

The database gate used the isolated Compose project `workloop-phase5f-verify` with PostgreSQL
17.11 and volume `workloop-phase5f-verify_postgres_data`. It never attached the preserved
PostgreSQL 16.15 volume. An empty database upgraded through all three revisions. Each revision then
passed its exact policy, grant, function, and rollback-state check before the chain returned to
`f52e0a1b9c34` and upgraded to the new head again.

The direct verifier checked all 77 policy identities, command shapes, runtime grants, RLS flags,
role attributes, function owners, volatility, search paths, and execute ACLs. It covered tenant,
branch, self, peer, direct-report, and delegated access. It also covered missing and invalid
context, expiry-role denial, immutable tables, self-approval denial, strict payroll
submitter-versus-approver separation with a second synthetic admin, successful and denied protected
finance calls, and successful, forged-actor, and cross-tenant shift swaps. Every denied protected
mutation compared stored state before and after the attempt.

The inherited Phase 4 schema, migration, trigger, function, function-security, fixture, grant,
shift-swap concurrency, and live database boundaries passed at their correct revision boundaries.
The Phase 5C repository verifier and Phase 5D transaction-context and pool-isolation verifier also
passed. The complete Phase 5E verifier passed at `f52e0a1b9c34`. After a persistence restart, the
isolated database remained at `d85a6f0c3b42`, Alembic reported no pending operations, and the full
Phase 5F verifier passed again.

## Limits and rollback

Phase 5F adds no business route, frontend feature, Phase 5G policy, shared audit foundation,
Keycloak change, cloud resource, persistent fixture, real data, or committed secret. Cloud cost
remains zero.

Each Phase 5F revision downgrades to its parent independently. Its downgrade drops only that
domain's policies, restores the prior runtime grants and protected-function definitions, removes
the delegation helper when leaving the leave revision, and disables RLS only for that revision's
tables. Earlier Phase 5E policies, helpers, grants, and table flags remain exact.

Phase 5G remains separate and has not started.
