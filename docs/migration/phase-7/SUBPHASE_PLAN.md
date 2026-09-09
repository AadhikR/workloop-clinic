# Phase 7 subphase plan

## Status

Phase 6 and its temporary Phase 6G DigitalOcean proof are complete. The proof resources and
credentials were removed on 2026-09-09; the retained empty FRA1 default VPC is non-billable and is
not managed by this repository.

Phase 7A is complete. No Phase 7 runtime implementation, deployment, cloud spending, or
production-data work is authorized by this document.

Phase 7 is split into eight parts, 7A through 7H. The original scope combines organization settings,
branch administration, employee data, departments, staffing rules, job history, and portal roles.
Those areas have different authorization rules, transaction boundaries, dependencies, and rollback
risks, so they should not move in one cutover.

The project owner may authorize one part at a time. Completing a part does not authorize the next
part. Phase 7 may instead receive one explicit authorization covering a named sequence of parts, but
Phase 8 remains separately gated.

## Starting point

- Branch `migration/fastapi-keycloak` is synchronized at Phase 6 closeout commit
  `d9cd18b86f95381b99531d0e974e5522c46ad0f9`.
- Alembic head is `2c4d6e8f0a1b`; the approved schema and RLS design already contain the Phase 7
  organization and workforce tables.
- Phase 3 supplies Keycloak login and trusted application-user resolution.
- Phase 5 supplies trusted principals, branch-scoped repositories, PostgreSQL RLS, protected
  workflows, and append-only audit controls.
- Phase 6 supplies the `/api/v1` contract, camelCase JSON, shared error handling, the frontend HTTP
  client, and cutover records.
- The legacy Supabase build remains the behavioral reference. The migration build must not read from
  one backend and write to the other for the same feature.
- Phase 6G proved the cloud architecture with synthetic data, then was torn down. Phase 7 is local
  by default and creates no DigitalOcean resources.
- The preserved `workloop-clinic_postgres_data` volume remains outside migration test stacks and
  must not be upgraded, attached, recreated, or deleted without separate owner approval.

## Part status

| Part | Scope | Status |
| --- | --- | --- |
| 7A | Domain contracts, dependency inventory, and cutover decisions | Complete |
| 7B | Company and branch read foundation | Not authorized |
| 7C | Company and branch administration | Not authorized |
| 7D | Employee directory, self, and manager read projections | Not authorized |
| 7E | Departments, hierarchy, and staffing rules | Not authorized |
| 7F | Employee onboarding, editing, and CSV import | Not authorized |
| 7G | Employee lifecycle, job history, and portal-role workflows | Not authorized |
| 7H | Independent review, cutover proof, and completion gate | Not authorized |

## Rules shared by every part

- Use only synthetic data. A cloud deployment, real-data migration, or billable resource requires
  separate authorization.
- PostgreSQL remains the source of company membership, branch scope, employee identity, reporting
  relationships, and portal roles. Keycloak roles and browser fields do not grant business access.
- The server derives `companyId`, `branchId`, actor identity, and permitted role transitions. A
  React filter is not an authorization boundary.
- New API responses use the Phase 6 camelCase contract. Do not expose a mixture of raw snake_case
  and camelCase employee objects.
- Requests for inaccessible UUIDs must not reveal whether another tenant owns the row.
- Mixed-tenant or mixed-branch bulk requests fail as one transaction. No partial mutation is
  allowed.
- Use optimistic concurrency for mutable records when the 7A contract requires a version. A stale
  write returns the Phase 6 `state_conflict` response.
- Server workflows, not arbitrary client input, append job-history and audit records.
- Employee hard deletion and general branch transfer remain unsupported. Branch correction or
  retained-history transfer requires a separately approved workflow.
- Demoting, disabling, archiving, or terminating a manager must reassign every direct report in the
  same transaction or fail without changing state.
- Each feature cutover must name its read authority, write authority, rollback path, and single
  writable system. Dual-write is prohibited.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`: use focused checks while implementing, then run
  one complete isolated Phase 7 gate after all code is stable and push the phase once.

## Explicit Phase 7 boundaries

Phase 7 owns legal company details, branches, departments, staffing rules, the employee master,
employee job history, and employee/manager portal-role assignment.

The existing legacy screens mix these responsibilities with later phases. Phase 7 must not pull the
following work forward:

- payroll routing and payroll calculations, which belong to Phase 9;
- shift assignment, roster, attendance, and scheduling, which belong to Phase 10;
- insurance, employee documents, and employment-contract lifecycle, which belong to Phase 11; or
- Keycloak user invitation or account provisioning beyond the already approved identity boundary.

The migration build should expose Phase 7-only settings and employee surfaces. Later-domain tabs may
remain in the legacy build until their owning phases migrate.

## 7A: Domain contracts, dependency inventory, and cutover decisions

### Objective

Fix the behavior and authority boundaries before creating business routes or changing React data
sources.

### Scope

- Inventory every legacy company, branch, employee, department, staffing, job-history, and
  portal-role reader and writer.
- Define list, detail, self, direct-report, and safe-employer projections. Specify pagination,
  filters, sorting, null handling, enums, dates, decimals, and writable fields.
- Separate legal-company fields from operating-branch fields. Record how an active branch is
  selected and how the server verifies that it belongs to the authenticated company.
- Define employee create, ordinary edit, bulk import, lifecycle, manager reassignment, job-change,
  salary-change, self-contact, and portal-role transactions.
- Decide whether CSV import is create-only or an explicit upsert. If it updates existing employees,
  every job, department, salary, status, or manager change must use the same history and
  authorization rules as an individual mutation.
- Reconcile legacy probation actions with the approved job-history change types. Do not add a new
  change type or overload an existing type without an approved decision.
- Register the protected mutations that require an idempotency key and define retry behavior.
- Prepare Phase 6 cutover records for each independently switched feature.

### Completion gate

- The dependency inventory accounts for every legacy reader and writer in scope.
- API and transaction contracts have no unresolved identity, authorization, history, or cutover
  decisions.
- Later-phase fields and workflows are explicitly excluded.
- The project owner approves the contract before 7B begins.

### Rollback boundary

This part changes documents only. Revert its documents if the contract is rejected; no runtime,
schema, or data change is permitted.

## 7B: Company and branch read foundation

### Objective

Provide the trusted organization context needed by all later Phase 7 work without enabling business
writes.

### Scope

- Add scoped repositories, services, schemas, and routes for safe company details and branch lists.
- Return the active company and branch through explicit projections rather than choosing the first
  owner company in the browser.
- Wire the migration build's company context and branch switcher to the Phase 6 HTTP client.
- Handle a missing, stale, or unauthorized branch selection without falling back to another branch.
- Add cross-tenant, inactive-account, malformed-ID, pagination, and field-leakage tests.

### Completion gate

- Admins can read only their company and its branches.
- Staff receive only the approved safe-employer and own-branch projection.
- The migration build uses camelCase organization objects and does not call Supabase for these
  reads.
- All denied requests leave the database unchanged and do not disclose foreign object existence.

### Rollback boundary

Remove the new read routes and migration-build adapters together. The legacy build remains unchanged
and authoritative.

## 7C: Company and branch administration

### Objective

Move legal-company settings and branch administration behind server-side authorization and guarded
transactions.

### Scope

- Add the approved legal-company update operation and branch create/update operations.
- Add guarded branch deletion. It must fail when active employees or retained references still use
  the branch.
- Build a Phase 7-only settings surface; do not include insurance configuration or payroll-routing
  cascades.
- Apply the 7A concurrency, idempotency, audit, and validation decisions.
- Cut over organization writes only after the corresponding legacy writes are frozen.

### Completion gate

- Admin-only mutations enforce tenant scope, exact validation, and concurrency behavior.
- Staff, managers, cross-tenant actors, and stale requests cannot mutate organization records.
- A guarded-delete denial and every other failed transaction preserve all related rows.
- The cutover record proves one writable system and a tested rollback path.

### Rollback boundary

Re-enable the frozen legacy organization writer only after disabling the new writer. Never leave
both writable during rollback.

## 7D: Employee directory, self, and manager read projections

### Objective

Create stable employee projections for administrators, employees, and direct managers before adding
employee mutations.

### Scope

- Add branch-scoped employee list and detail reads for admins.
- Add a minimal self projection and a one-level direct-report projection for managers.
- Add approved search, filter, sort, and pagination behavior without loading a company-wide employee
  set for browser-side authorization filtering.
- Add job-history reads only for roles and fields approved by the Phase 5 matrix.
- Update every Phase 7 migration-build consumer atomically so no caller depends on the legacy raw
  snake_case employee shape.

### Completion gate

- Admin, manager, and self responses expose only their approved fields and rows.
- A manager cannot expand direct-report scope through a query parameter or browser-supplied ID.
- Job-history salary data is unavailable to staff and unauthorized managers.
- Contract tests reject both accidental snake_case output and silent field removal.

### Rollback boundary

Remove the Phase 7 employee read adapters and routes together. Do not leave a migration-build screen
partly backed by Supabase and partly by FastAPI.

## 7E: Departments, hierarchy, and staffing rules

### Objective

Migrate the organization structures that employee administration depends on.

### Scope

- Add branch-scoped department create, update, and guarded-delete operations.
- Enforce same-branch parent and department-head references, cycle prevention, unique names, and
  supported hierarchy depth.
- Add staffing-rule reads and mutations with valid categories, non-negative minimum staffing, and
  valid date ranges.
- Build the department list, hierarchy view, head selection, and staffing-rule editor in the
  migration build.
- Keep shift planning and roster enforcement in Phase 10.

### Completion gate

- Cross-branch parents, heads, employees, and staffing rules are rejected without partial writes.
- Hierarchy cycles and unsafe deletes fail with stable errors.
- Only admins can mutate departments or staffing rules; other users receive labels only through
  authorized employee projections.
- The cutover records prove single read and write authorities for both features.

### Rollback boundary

Department and staffing cutovers may roll back independently only if no Phase 7 employee writer
has started depending on the new records. After 7F begins, roll back the dependent employee writer
first.

## 7F: Employee onboarding, editing, and CSV import

### Objective

Move ordinary employee administration to atomic, server-validated operations.

### Scope

- Add employee creation and the ordinary edit fields approved in 7A.
- Build a Phase 7-only employee form. Exclude documents, insurance, contracts, and shift assignment.
- Replace browser-side CSV merging with a server-validated, branch-scoped batch transaction.
- Return deterministic row diagnostics while preserving all-or-nothing writes.
- Route any import update that affects job, department, salary, status, or manager data through the
  same controls and history rules as the corresponding individual workflow.
- Enforce normalized non-empty work-email uniqueness per company and all approved relationship
  rules.

### Completion gate

- Create, edit, and import enforce tenant and branch scope from the trusted principal.
- Invalid or mixed-scope imports change no rows and return deterministic safe diagnostics.
- Retrying an idempotent request cannot create duplicate employees, history, or audit events.
- Employee hard delete and branch transfer are absent from the API and migration UI.

### Rollback boundary

Freeze the new employee writer before restoring the legacy writer. Employee reads may remain on the
new API only if the cutover record proves their schema remains compatible with the restored writer.

## 7G: Employee lifecycle, job history, and portal-role workflows

### Objective

Move privileged employee state transitions into named atomic workflows with complete history and
audit evidence.

### Scope

- Add approved archive, probation, title, department, salary, status, and manager-change workflows.
- Append allowed job-history entries and audit events in the same transaction as each state change.
- Add the employee self-contact update operation with a strict writable-field allowlist.
- Add employee/manager portal-role assignment for an eligible, already linked `user_profiles` row.
- Require manager demotion, disablement, archive, or termination to reassign all direct reports in
  the same transaction or fail.
- Do not provision Keycloak users, create new identity links, hard-delete employees, transfer
  branches, or migrate employment-contract lifecycle in this part.

### Completion gate

- Every state transition either changes the employee, history, reports, role, and audit state
  together or changes nothing.
- The server rejects self-role changes, unsupported roles, unlinked profiles, cross-branch reports,
  stale versions, and invalid transitions.
- Job history is append-only and cannot be supplied or rewritten as arbitrary client data.
- Synthetic browser flows prove admin, manager, and employee behavior after token refresh and
  restart.

### Rollback boundary

Disable the new workflow endpoints before restoring any legacy lifecycle or role writer. Rollback
must not delete history or audit evidence already committed.

## 7H: Independent review, cutover proof, and completion gate

### Objective

Prove the whole Phase 7 boundary is secure, restart-safe, reversible, and free of hidden legacy
dependencies before requesting Phase 7 signoff.

### Scope

- Review authorization, transaction ownership, RLS, optimistic locking, idempotency, audit coverage,
  and error disclosure independently of the implementation pass.
- Trace every inventory entry from 7A to a migrated route, an explicit later-phase owner, or a
  retained legacy dependency.
- Verify every completed cutover record, single-writer declaration, freeze step, and rollback step.
- Run the one complete local Phase 7 gate in a fresh isolated environment according to
  `docs/migration/VERIFICATION_WORKFLOW.md`.
- Prove migration repeatability where schema changes were approved, then restart existing images
  without rebuilding and compare persisted database and authentication state.
- Push the settled Phase 7 changes once and require the matching GitHub Actions result.

### Completion gate

- Focused suites and the complete local gate pass with synthetic data.
- Both builds succeed, and the migration build has no Supabase read or write path for cut-over
  Phase 7 features.
- Denial tests prove no partial mutation or cross-tenant disclosure.
- Restart and rollback evidence pass, GitHub Actions passes, and the owner signs off Phase 7.
- Phase 8 remains unauthorized until separately approved.

### Rollback boundary

Use the feature cutover records in reverse dependency order: lifecycle and employee writes, then
departments and staffing, then organization writes, then reads. Never reactivate a legacy writer
while its FastAPI counterpart remains writable.

## Recommended execution order

Execute `7A -> 7B -> 7C -> 7D -> 7E -> 7F -> 7G -> 7H`.

The order is intentional: organization scope precedes employee reads; employee projections precede
department-head selection; departments precede employee editing; and ordinary employee writes settle
before privileged lifecycle and role workflows. The final review occurs only after the phase code is
stable.
