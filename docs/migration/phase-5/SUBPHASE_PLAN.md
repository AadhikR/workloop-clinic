# Phase 5 subphase plan

## Status

Phase 5 is in progress. Phase 5A through Phase 5E completed on 2026-09-06 after separate
project-owner approvals. No later part is authorized.

Phase 5 is split into eight parts, 5A through 5H. The original phase combined policy design,
FastAPI authorization, scoped data access, PostgreSQL RLS across 54 tables, audit controls, and a
security closeout. That is too much security-sensitive work for one implementation and review
cycle.

The project owner may authorize one part at a time. Completing a part does not authorize the next
part unless the owner explicitly permits automatic progression under the migration plan's phase
execution protocol. Every part stops at a recorded decision, security boundary, or external
action.

## Starting point

- Phase 5B started from synchronized commit `dcf3931e8601a2bf58b67f4bad2200f06750d467` on branch
  `migration/fastapi-keycloak`.
- Alembic head is `e418c0d7a6b3`.
- The schema has 54 target tables. Phase 4 added no RLS policy or application authorization.
- Phase 3 validates Keycloak access tokens and resolves an active `app_users` row by trusted issuer
  and subject. It ignores Keycloak roles and browser-supplied business identity.
- Phase 4E provides 334 deterministic fixture rows across 48 tables and 19 authorization controls.
- PostgreSQL 17.11 is the Compose and CI target.
- The preserved local PostgreSQL 16 volume must not be upgraded, recreated, deleted, or attached
  to PostgreSQL 17 without project-owner approval. Database-backed Phase 5 work must use an
  isolated PostgreSQL 17.11 volume.
- Phase 4 approved PostgreSQL RLS as defense in depth. Phase 5 must design new policies from the
  approved permission matrix. It must not copy the legacy Supabase policies.
- No Phase 5 part creates DigitalOcean resources, changes Keycloak provisioning, adds business API
  routes, migrates React features, configures storage, or uses real data.

## Part status

| Part | Scope | Status |
|---|---|---|
| 5A | Permission matrix, RLS contract, and audit decisions | Completed 2026-09-06; see [`PERMISSION_MATRIX_AND_RLS_DESIGN.md`](PERMISSION_MATRIX_AND_RLS_DESIGN.md) and [`PART_5A_COMPLETION.md`](PART_5A_COMPLETION.md) |
| 5B | Trusted authorization principal and FastAPI dependencies | Completed 2026-09-06; see [`PART_5B_COMPLETION.md`](PART_5B_COMPLETION.md) |
| 5C | Scoped repository rules and protected mutation guards | Completed 2026-09-06; see [`PART_5C_COMPLETION.md`](PART_5C_COMPLETION.md) |
| 5D | Transaction-local PostgreSQL context and pool isolation | Completed 2026-09-06; see [`PART_5D_COMPLETION.md`](PART_5D_COMPLETION.md) |
| 5E | Identity, organization, and workforce RLS | Completed 2026-09-06; see [`PART_5E_COMPLETION.md`](PART_5E_COMPLETION.md) |
| 5F | Payroll, leave, attendance, and roster RLS | Not started; depends on 5E |
| 5G | Remaining domain RLS and audit foundation | Not started; depends on 5E and 5F |
| 5H | Independent security review and completion gate | Not started; depends on 5A through 5G |

## Rules shared by every part

- PostgreSQL is the source of business roles, company membership, employee identity, branch scope,
  reporting relationships, and delegation dates. Keycloak roles and browser fields never grant
  business access.
- The server must apply tenant, branch, self, direct-report, and object-state checks. A React filter
  does not count as authorization.
- Requests for an inaccessible UUID must not reveal whether another tenant owns the row.
- Bulk reads and writes must authorize every row. One allowed row must not widen the whole batch.
- The migration identity owns schema objects. `workloop_runtime` must not own objects, inherit a
  privileged role, bypass RLS, create objects in `public`, or gain wildcard privileges.
- RLS is defense in depth. FastAPI dependencies and scoped queries remain the primary authorization
  boundary.
- Missing, malformed, stale, or partial authorization context must deny access.
- Every denied mutation test must compare database state before and after the request or statement.
- Do not weaken the Phase 3 token and account checks or the Phase 4 function, ownership, search-path,
  grant, and fixture boundaries.
- Use only synthetic fixtures. No cloud account, secret, billing change, or third-party permission is
  needed for local Phase 5 work.

## 5A: Permission matrix, RLS contract, and audit decisions

### Objective

Write the authorization contract before adding enforcement code. This part turns the Phase 0
feature matrix, the Phase 4 policy reconciliation, and the 19 fixture controls into one reviewable
decision record.

### Scope

- Create `PERMISSION_MATRIX_AND_RLS_DESIGN.md` under this directory.
- List every target table and every supported read, create, update, delete, workflow, and system
  operation. Mark unsupported operations explicitly.
- Define admin, manager, employee, migration, seed, scheduled-job, and expiry-processing access.
- Separate tenant scope from branch scope. Record when an admin selects a branch and how the server
  proves that the branch belongs to the admin's company.
- Define employee self scope, one-level direct-report scope, active leave delegation, and the effect
  of a reporting-manager change.
- Record field-level write rules for role, company, branch, salary, approval state, ownership,
  payroll state, document state, and other protected fields.
- Decide self-approval and separation-of-duties rules for leave, expenses, payroll, appraisals, and
  any other approval workflow.
- Define the HTTP response rule for an authenticated caller who requests an inaccessible object.
- Specify the transaction-local PostgreSQL context keys, their null behavior, and which roles may
  set or consume them.
- Specify the RLS policy families and exact table-to-policy mapping. Reconcile every Phase 4 row
  marked `Replace in Phase 5` or `Omit superseded`.
- Decide whether audit records use existing domain audit tables, a new shared append-only table, or
  both. Record retention and actor requirements.
- Map each of the 19 fixture authorization controls to an application test, an RLS test, or both.

### Approved decisions

On 2026-09-06, the owner approved the complete permission matrix and decisions `5A-D1` through
`5A-D20`. These cover branch selection, manager and delegate scope, self-approval, inaccessible
objects, system actors, audit storage, storage retries, and attempt reservation. The owner also
approved the full 54-table catalogue and 119-policy reconciliation. A later change to a role,
tenant concept, cross-branch manager rule, table, constraint, context key, helper, or approved
behavior requires another decision.

### Dependencies and files

Phase 4 must have project-owner sign-off. Inputs are the Phase 0 feature and fixture catalogues, the
Phase 3 authentication contract, and the Phase 4 schema, grant, function, and policy reconciliation
records. This part writes documentation under `docs/migration/phase-5/` only.

### Security and data boundaries

No code, schema, grant, role, policy, fixture, route, or environment changes in this part. The design
must preserve the synthetic-data rule and cannot authorize Phase 6 feature work.

### Tests and review

This part changes documentation only. A consistency check must prove that all 54 tables, all Phase 4
policy reconciliation entries, and all 19 negative controls appear exactly once in the design. An
independent reviewer must check for gaps, contradictory permissions, accidental cross-branch
access, and operations that lack a denial case.

### Rollback boundary

No runtime or schema change occurs. Revert the planning files if the owner rejects the design.

### Completion gate

The owner approves a complete matrix with no unresolved cell or policy mapping. Every later part
has a named input, expected denial behavior, and test obligation.

The gate passed on 2026-09-06. The independent GPT-5.6 review closed all 51 findings. Documentation
checks proved 54 exact table rows, 119 exact reconciliation identities, and 19 exact fixture-control
mappings. See [`PART_5A_COMPLETION.md`](PART_5A_COMPLETION.md).

### Recommended model and effort

Use GPT-5.6. This part makes the authorization and RLS decisions that all later code will enforce.
Expect one or two sessions plus owner review.

## 5B: Trusted authorization principal and FastAPI dependencies

### Objective

Extend the Phase 3 application-user result into one immutable, server-derived authorization
principal and expose small FastAPI dependencies for the approved roles and scopes.

### Scope

- Resolve `app_user_id`, account status, role, company, employee link, and employee branch in one
  bounded database lookup after token verification.
- Require exactly one valid `user_profiles` row. Enforce the approved role-to-employee-link rules.
- Derive manager and employee identity from the linked employee row. Do not accept identity, role,
  company, branch, or manager scope from token claims, headers, query parameters, or request bodies.
- Add reusable dependencies for an authenticated principal, approved role sets, tenant scope,
  employee self scope, manager scope, and an admin-selected branch that belongs to the principal's
  company.
- Keep authentication failures, disabled-account failures, authorization denials, and temporary
  database failures distinct without exposing private row existence.
- Preserve the Phase 3 issuer, subject, audience, algorithm, token lifetime, JWKS, timeout, and
  account-status behavior.

### Files and areas

`backend/app/auth/`, shared error handling under `backend/app/`, and focused tests under
`backend/tests/`. This part adds no business route.

### Dependencies and decisions

This part depends on owner-approved 5A. Stop if implementation reveals an identity state, role,
company membership, or branch-selection case that the matrix does not resolve.

### Security and data boundaries

The authorization principal contains database-derived identifiers only. It must not expose private
profile fields in errors or logs. No schema, RLS, grant, Keycloak realm, or frontend change belongs
here.

### Tests and negative tests

- Admin, manager, and employee fixtures resolve to the exact approved principal.
- Disabled, pending, missing, duplicate, unlinked, cross-company, and cross-branch profile states
  fail closed.
- Browser fields, Keycloak roles, and altered token claims cannot change the resolved scope.
- Database timeout and connection failure return the approved temporary-failure response and log no
  token, subject, employee identifier, or private profile value.
- Existing Phase 3 token and application-user tests pass unchanged.

### Rollback boundary

This is application code only. Removing the new principal and dependencies returns to the Phase 3
authenticated-user boundary.

### Completion gate

One server-derived principal drives every authorization dependency, all negative cases fail closed,
and no feature route or frontend behavior has changed.

### Recommended model and effort

Use GPT-5.6. Identity-to-role resolution is a security boundary and a bad join could grant another
tenant's scope. Expect one session.

## 5C: Scoped repository rules and protected mutation guards

### Objective

Make authorization constraints part of database statements so a route cannot fetch a broad row set
and filter it afterward.

### Scope

- Add reusable SQLAlchemy predicates or repository helpers for company, branch, employee self,
  direct report, active delegate, and system scope.
- Define object lookups that return the same result for a missing row and an inaccessible row where
  the 5A design requires nondisclosure.
- Require scoped update and delete statements to include both object identity and authorization
  predicates. Check affected-row counts.
- Add batch helpers that validate every requested row under the same scope before mutation.
- Add allowlisted mutation models or field guards so request payloads cannot assign role, company,
  branch, employee owner, salary, approval status, payroll state, or audit actor unless the matrix
  grants that exact action.
- Implement manager scope from current reporting relationships and active delegation dates. Do not
  cache a scope past a relationship change.
- Provide a test harness for repository authorization without creating business API routes.

### Files and areas

New modules under `backend/app/repositories/` and `backend/app/auth/`, narrowly shared Pydantic
models under `backend/app/schemas/`, and focused tests.

### Dependencies and decisions

This part depends on 5A and 5B. Stop if a repository needs access not listed in the matrix or if a
manager, delegate, field-write, bulk, or object-state rule is ambiguous. If the matrix exposes a
missing database invariant, record it and obtain owner approval before adding a constraint in its
own Alembic revision.

### Security and data boundaries

No business endpoint or frontend consumer is added. A repository helper cannot accept a
caller-supplied principal or widen an approved scope for convenience.

### Tests and negative tests

- Tenant, branch, self, direct-report, delegate, guessed-UUID, stale-manager, and bulk mixed-scope
  cases use the Phase 4E fixtures.
- A manager loses access immediately after `reporting_manager_id` changes.
- Expired and future delegates cannot act.
- Restricted fields are rejected or ignored according to the 5A contract, and the database row is
  unchanged.
- SQL injection strings remain bound values and cannot alter scope.

### Rollback boundary

The helpers have no schema effect. They may be removed while no Phase 6 or later route imports
them. Any separately approved constraint revision must state its own data-safe downgrade rule.

### Completion gate

Every scope type in the permission matrix has one canonical query rule and negative tests. No test
or production code performs authorization by loading an unscoped business row first.

### Recommended model and effort

Use GPT-5.6. The code will be reused by every business API and must fail closed under missing or
mixed scope. Expect one or two sessions.

## 5D: Transaction-local PostgreSQL context and pool isolation

### Objective

Create the database context that RLS policies consume and prove that pooled connections cannot
carry one request's identity into another request.

### Scope

- Define the approved PostgreSQL context keys for application user, role, company, employee, and
  branch.
- Set context only inside the same explicit transaction that executes protected statements.
- Use transaction-local values. Never use session-persistent context for request identity.
- Add narrowly scoped SQL helper functions only if the approved design needs them. Pin search paths,
  set ownership explicitly, revoke PUBLIC execution, and grant only the required calls.
- Make missing, blank, malformed, or incomplete context evaluate to no access.
- Keep migration and seed operations explicit. Do not make the shared runtime role an RLS bypass
  role.
- Document the defense-in-depth limit: FastAPI owns the database credential, and parameterized
  statements still prevent callers from issuing arbitrary context changes.

### Files and areas

`backend/app/db/`, an Alembic revision if database helpers are approved, verification scripts, and
database integration tests.

### Dependencies and decisions

This part depends on 5A and 5B. The owner-approved design must name every context key and the system
actor behavior before a migration is written. Any new database role or definer-rights helper needs
separate owner approval.

### Security and data boundaries

Do not attach PostgreSQL 17 to the preserved PostgreSQL 16 volume. Do not log context values or make
the database reachable by the browser. Application authorization remains required even after the
RLS context works.

### Tests and negative tests

- Context is visible within its transaction and absent after commit, rollback, exception,
  cancellation, and connection return to the pool.
- Concurrent requests with different tenants and roles never observe each other's context.
- A request with incomplete context receives no rows and cannot mutate a row.
- `workloop_runtime` remains `NOBYPASSRLS`, cannot create schema objects, cannot change roles, and
  cannot execute an ungranted helper.
- Any helper has the exact owner, signature, definer mode, search path, and ACL approved in 5A.

### Rollback boundary

Database helper revisions must downgrade exactly while no RLS policy or later application code
depends on them. Application transaction wiring can then be removed independently.

### Completion gate

The application can set one request context per transaction, pool-reuse and concurrency tests pass,
and absent context denies access without relying on route checks.

### Recommended model and effort

Use GPT-5.6. Transaction pooling and RLS context leakage are security-sensitive database work.
Expect one or two sessions.

## 5E: Identity, organization, and workforce RLS

### Objective

Apply the approved policy families to identity and workforce tables first. This smaller policy set
proves the design before it reaches payroll and employee self-service data.

### Scope

- Add RLS for `companies`, `branches`, `app_users`, `user_profiles`, `employees`,
  `employee_job_history`, `departments`, and `department_staffing_rules`.
- Add or revise exact runtime grants when RLS alone would leave an operation broader than the 5A
  matrix.
- Enforce tenant and branch scope, employee self-read fields, manager direct-report reads, and
  approved admin operations.
- Keep identity and history writes limited to their approved service or system paths.
- Add no legacy policy name, Supabase helper, Supabase role, `auth.*`, or `storage.*` reference.

### Dependencies and decisions

This part depends on 5C and 5D. The 5A matrix must resolve every operation on the eight named tables.
Stop if direct tests show that the approved application rule and RLS rule disagree.

### Files and areas

Bounded Alembic policy and grant revisions, authorization verification scripts, database integration
tests, and only the application changes needed to consume the established transaction context.

### Security and data boundaries

The migration and seed identities keep their approved operational paths. `workloop_runtime` remains
the only application database role and remains subject to RLS.

### Tests and negative tests

- Run each allowed and denied operation as `workloop_runtime` with transaction-local context.
- Cover admin cross-tenant and cross-branch reads and writes, employee self versus other employee,
  manager direct-report versus unrelated employee, disabled user, missing context, and guessed UUID.
- Prove branch selection cannot escape the principal's company.
- Compare exact policy definitions, owners, grants, and table RLS flags with the 5A design.
- Upgrade and downgrade the new revision on an isolated empty PostgreSQL 17.11 database.

### Rollback boundary

The policy and grant revision may downgrade before Phase 6 routes depend on it. Once a route relies
on these policies, roll back the application consumer before the database revision.

### Completion gate

The eight named tables match the approved matrix under direct runtime-role tests. The application
and RLS layers agree on every tested allow and deny decision.

### Recommended model and effort

Use GPT-5.6. This is the first live RLS enforcement and includes employee records and identity
links. Expect one or two sessions.

## 5F: Payroll, leave, attendance, and roster RLS

### Objective

Protect the financial, approval, timekeeping, and scheduling tables with the same reviewed context
and policy families.

### Scope

- Add separate Alembic revisions for payroll and finance, leave, and attendance and roster policy
  groups. Do not place every policy in one revision.
- Cover payroll runs, entries, payslips, approval logs, advances, repayments, expenses, leave
  settings and workflows, attendance settings and workflows, shifts, assignments, rosters, swaps,
  audit logs, and biometric mappings.
- Preserve the Phase 4 protected-function boundaries. RLS and function checks must agree on tenant,
  branch, employee, manager, delegate, and object state.
- Enforce separation of duties and self-approval rules exactly as approved in 5A.
- Keep audit and issued-snapshot tables append-only where the matrix requires it.

### Dependencies and decisions

This part depends on 5E. Stop for owner review if a financial, approval, manager, delegate, or
object-state action is missing from 5A or conflicts with a retained Phase 4 function.

### Files and areas

Separate Alembic revisions and database verification scripts per domain group, with focused
application and integration tests. No payroll, leave, attendance, or roster API route is added.

### Security and data boundaries

Successful function calls and direct table operations must use the same trusted context. No policy
may trust an email address, token role, browser-selected employee, or bare object identifier.

### Tests and negative tests

- Exercise every matching Phase 4E authorization control as `workloop_runtime`.
- Cover Horizon versus Cedar, Dubai versus Abu Dhabi, employee self versus peer, manager direct
  report versus unrelated employee, active versus expired delegate, and mixed-scope bulk requests.
- Test each allowed operation and every SQL operation not granted by the matrix.
- Prove denied repayment, payroll replacement, approval, cancellation, correction, and shift-swap
  actions leave all affected rows unchanged.
- Run per-revision upgrade and downgrade checks plus the Phase 4 function, grant, fixture, and
  concurrency verifiers.

### Rollback boundary

Each domain policy revision downgrades to its parent before a later route depends on it. The
retained Phase 4 functions and their original grant boundaries must remain intact after downgrade.

### Completion gate

Every payroll, leave, attendance, and roster table has the exact approved RLS and grant state.
Application predicates, RLS policies, and retained functions return the same allow or deny result.

### Recommended model and effort

Use GPT-5.6. Payroll, approval, and timekeeping authorization combines financial and
security-sensitive behavior. Expect two or three sessions.

## 5G: Remaining domain RLS and audit foundation

### Objective

Finish RLS for the remaining business domains and add the audit mechanism approved in 5A.

### Scope

- Add bounded policy revisions for documents and insurance, notifications, contracts and
  offboarding, assets, training and certification, appraisals and CME, incidents, letters, NAFIS,
  compliance, and other remaining Phase 4 tables.
- Protect nullable branch scope so a tenant-wide row does not become cross-tenant and a branch row
  does not appear in another branch.
- Keep document metadata private. File bytes and signed URLs remain outside Phase 5 and wait for the
  storage phase.
- Implement the approved append-only audit foundation for role changes, approvals, payroll state,
  and sensitive document actions. Later business services will call it when those routes are built.
- Prevent ordinary runtime updates or deletes to audit history.
- Reconcile all remaining Phase 4 `Replace in Phase 5` decisions and prove that every omitted legacy
  policy stays absent.

### Dependencies and decisions

This part depends on 5E and 5F. The audit design from 5A must be approved before implementation.
Stop if a domain requires a new actor, cross-branch rule, retention rule, object-storage behavior, or
table not covered by the approved design.

### Files and areas

Bounded Alembic policy, grant, and audit revisions; shared audit code; verification scripts; and
focused tests. Storage adapters, upload routes, and signed URLs remain later-phase work.

### Security and data boundaries

Audit records take actor and scope from the trusted request context. Ordinary callers cannot update
or delete history, forge another actor, or use metadata access to infer a private object key.

### Tests and negative tests

- Cover every remaining Phase 4E authorization control, including documents, expenses, training,
  appraisals, incidents, reports, and branch-scoped administration.
- Test tenant-wide and branch-specific notification and compliance rows separately.
- Prove employee and manager writes cannot change ownership, approval state, audit actor, or another
  employee's record.
- Prove audit writes capture the trusted application user and approved scope, and that rollback
  removes both the business mutation and its audit record.
- Compare the complete 54-table policy and grant catalogue with the 5A matrix.

### Rollback boundary

Each policy revision downgrades independently before later routes depend on it. If 5A approves a
new audit table, its downgrade is safe only while empty. Existing domain audit rows must never be
dropped by a policy-only downgrade.

### Completion gate

All 54 target tables have an explicit approved RLS disposition, all required policies and grants
match the matrix, every legacy Supabase policy is absent, and the audit foundation is append-only.

### Recommended model and effort

Use GPT-5.6. This part spans sensitive employee records and completes the database authorization
boundary. Expect two or three sessions.

## 5H: Independent security review and completion gate

### Objective

Review Phase 5 independently, resolve every finding, and prove the application and PostgreSQL
authorization layers fail closed on a fresh database.

### Scope

- Arrange an independent GPT-5.6 review of the approved matrix, principal resolution, dependencies,
  repository rules, transaction context, RLS policies, grants, helper functions, and audit controls.
  The reviewer inspects implementation and tests and makes no edits.
- Record every finding and disposition. Fix confirmed defects that fit the approved design. Stop for
  project-owner approval if a finding changes a role, scope, policy, schema decision, or phase
  boundary.
- Run focused checks while resolving findings.
- After findings settle, run one complete local gate on an isolated fresh PostgreSQL 17.11 database
  upgraded from empty to the current Alembic head.
- Run the complete repository gate once after all changes settle, commit and push once, then use the
  existing GitHub workflow as the final automated gate.

### Dependencies and decisions

This part depends on completed 5A through 5G and their recorded evidence. The independent reviewer
must inspect the implementation and tests rather than rely on completion summaries. A review result
that changes an approved role, scope, policy, schema object, or phase boundary returns to the
project owner.

### Files and areas

CI configuration, focused corrections within the approved Phase 5 design, and
`docs/migration/phase-5/PART_5H_COMPLETION.md`.

### Security and data boundaries

Use an isolated fresh PostgreSQL 17.11 database and synthetic fixtures. Do not provision cloud
services, modify Keycloak accounts, introduce real data, or start Phase 6.

### Required proof

- The approved permission matrix has no missing or contradictory table or operation.
- All 19 Phase 4E authorization controls fail or succeed exactly as documented at both application
  and RLS layers where applicable.
- Missing context, stale manager scope, expired delegation, disabled account, guessed UUID,
  cross-tenant, cross-branch, peer employee, self-approval, mass-assignment, and mixed bulk cases
  fail closed.
- Transaction context does not leak after commit, rollback, cancellation, exception, pool reuse,
  restart, or concurrent requests.
- The runtime role has the exact grants, RLS state, helper execution, ownership, and role attributes
  approved in 5A.
- Alembic upgrade, repeated upgrade, documented downgrade boundaries, and re-upgrade pass from an
  empty database.
- The 334 deterministic fixtures apply twice without change and clean up completely.
- Authentication still works before and after restart.
- Migrations, models, authorization code, policies, functions, tests, and fixtures contain no
  dependency on `auth.*`, `storage.*`, Supabase roles, browser database access, or trusted token
  roles.

### Completion record and limits

Create `PART_5H_COMPLETION.md`, update this tracker and the main migration plan, and report the final
GitHub run URL in the task handoff. Do not make a second commit only to add the run ID.

Phase 5 does not add business feature routes, migrate React screens, provision Keycloak accounts,
configure object storage, create DigitalOcean resources, configure SMTP, or use real data. Those
items remain in their later phases.

### Rollback boundary

The clean gate changes no durable environment. Policy revisions remain reversible under the
boundaries recorded in 5D through 5G. After Phase 6 consumes them, application rollback must precede
database rollback.

### Completion gate

The independent review has no unresolved finding, the local and GitHub gates pass, the branch is
clean and synchronized, and the project owner signs off. Stop before Phase 6.

### Recommended model and effort

Use GPT-5.6. This is an independent authorization review and the final database security gate.
Expect one or two sessions if earlier parts closed their own findings.

## Overall completion rule

Phase 5 closes only when 5A through 5H pass their gates and the project owner signs off. Passing an
individual role's happy path does not close a part. A denied request without an unchanged-state
assertion does not count as proof.

The split increases the likely effort from the original one-to-two-week estimate. A safer working
estimate is three to five weeks across several review cycles, depending on policy decisions and the
number of findings. No DigitalOcean cost is expected because Phase 5 remains local and uses
synthetic data.
