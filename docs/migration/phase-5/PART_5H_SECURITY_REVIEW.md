# Phase 5H security review ledger

## Review state

The project owner authorized Phase 5H on 2026-09-07. An independent GPT-5.6 reviewer inspected
Phases 5A through 5G in read-only mode. The reviewer changed no file, started no service, and did
not alter repository state.

This ledger was created before any Phase 5H correction. It records every review finding,
supporting evidence, and final disposition.

## Verified starting point

- Branch: `migration/fastapi-keycloak`
- Commit: `d05e975d911b9ff844bea76ce67ec744388b644d`
- Remote state: synchronized with `origin/migration/fastapi-keycloak`
- Alembic head: `1b29d4e7f860`
- Target database: PostgreSQL 17.11 in a new isolated Compose project
- Preserved database: `workloop-clinic_postgres_data`, PostgreSQL 16.15 at `d307b9c1f25e`

The preserved database had no rows in `companies`, `app_users`, `user_profiles`, or `employees` at
preflight. Its container, volume, and data have not been changed by the review.

The evidence below refers to commit `d05e975d911b9ff844bea76ce67ec744388b644d`, before any Phase
5H correction.

## Review scope

The review covers the approved permission matrix, principal resolution, authorization
dependencies, scoped repositories, transaction context, every RLS policy and grant, protected
functions, audit controls, synthetic fixtures, tests, and verification scripts. It also checks the
19 Phase 4E authorization controls at the application and RLS layers where each layer exists.

Storage-provider checks for controls 10, 17, and 18 remain assigned to the storage phase. Business
route checks remain assigned to the phase that creates each route. Phase 5H still requires current
metadata, repository, RLS, protected-function, audit, and no-browser-database proof.

## Findings and dispositions

The independent review failed its first pass. The owner approved the fail-closed course on
2026-09-07 as decision `5A-D21`: runtime offboarding-task deletion and employee branch correction
remain unavailable, unsupported audit actions remain denied, and one fixed-purpose relationship-lock
helper serializes report mutations with manager reassignment. All findings are now closed and the
complete local gate passed.

### Implementation findings

| ID | Severity | Finding and evidence | Disposition |
|---|---|---|---|
| `5H-SEC-01` | High | Admin branch selection queries `branches` without authorization context in `backend/app/auth/application_user.py:168`. The Phase 5E policy requires full human context, and the lookup runs before the authorized transaction in `backend/app/auth/dependencies.py:183`. | Move selection into a full admin authorization transaction and revalidate the branch there. Add a live dependency test. This fits the approved design unless the correction adds a new definer helper. |
| `5H-SEC-02` | High | `ScopedRepository.lock_batch` locks only business rows. Direct-report authority reads `employees.reporting_manager_id` separately, so a manager action can race with reassignment. | Lock and recheck the employee relationship, delegation, and approver rows in a fixed order. Add a two-connection barrier test and prove the new manager gains access. A new helper or schema object would require owner review. |
| `5H-SEC-03` | High | The appraisal-section update policy in `backend/alembic/versions/0a18c3d6e75f_add_development_clinical_rls.py:183` includes employee self scope. The matrix permits self read but only admin or current-manager update. | Add an update-only predicate that excludes employee and manager-self writes. Add denied-mutation and unchanged-state tests. No owner decision is needed. |
| `5H-SEC-04` | High | `create_workflow_notification` checks account, role, and company but does not bind context employee and branch to the resolved profile before trusting manager scope. | Repeat complete active-principal and context equivalence before producer checks. Add forged and stale-manager tests. No owner decision is needed. |
| `5H-SEC-05` | High | `append_audit_event` has the same incomplete context binding and trusts the employee context for manager authority. | Apply complete context equivalence before action dispatch and add forged-context tests. No owner decision is needed. |
| `5H-SEC-06` | High | Expiry notification policies permit any same-scope recipient and caller-supplied content without proving an active tenant admin, the exact type and entity pair, source state, or linked audit event. Deduplication reads include non-expiry types. | Restrict recipients, producer pairs, source state, deduplication reads, and audit linkage to the approved J1 contract. Prefer policy-only corrections. A new helper requires owner review. |
| `5H-SEC-07` | High | The offboarding delete policy permits every uncompleted task. The matrix permits only custom uncompleted tasks, but `offboarding_tasks` has no template reference or provenance field. | Owner decision required. Add durable provenance through an approved schema change, or change the approved operation by withholding task delete. Task-name matching is unsafe. |
| `5H-SEC-08` | Medium | The application delegate predicate does not exclude a delegate's own employee ID. RLS correctly denies the same case. | Add explicit self-exclusion or a decision-only delegate predicate with a fixture-backed test. No owner decision is needed. |
| `5H-SEC-09` | Medium | Employee update uses the same branch context for `USING` and `WITH CHECK`, so an approved pre-activity correction cannot move from the source branch to the destination branch. | Add a guarded application and policy path that scopes the old row and verifies the destination plus the zero-dependent-row rule. This fits the approved design unless it needs a new helper or schema object. |
| `5H-SEC-10` | Medium | The audit helper accepts `employment_access_changed`, `employee_branch_corrected`, and `payroll_wps_changed` without proving the matching transition. `role_changed` proves only that a profile exists. | Add action-specific post-state and actor checks or couple the actions to fixed workflows. Changing the helper signature or action contract requires owner review. |
| `5H-SEC-11` | Medium | The audit actor check can accept a nonhuman row with both actor fields null because a PostgreSQL `CHECK` accepts a null result. | Require a non-null, nonblank system actor key and add a behavior test. No owner decision is needed. |
| `5H-SEC-12` | Medium | Required tenant-scoped branch create and delete audit actions are absent from the allowlist, and the helper otherwise requires branch context. | Add the two approved tenant-scoped actions with safe state checks and tests. No owner decision is needed unless the action contract changes. |
| `5H-SEC-13` | Medium | `PROTECTED_MUTATION_FIELDS` omits several payroll state, actor, document path, training evidence, CME, appraisal rating, and closure fields named by the design. | Use an authoritative per-table action catalogue or require every input field to be classified. Intentional exceptions need review; filling omissions does not. |
| `5H-SEC-14` | Medium | Authorized transaction checkout, context setup, and principal revalidation have no deadline or database-error translation. Failures can escape as an unbounded `500`. | Add a bounded setup path and a distinct availability error mapped to the existing generic `503`. Keep stale identity at `403`. No owner decision is needed. |
| `5H-SEC-15` | Medium | The audit wrapper requires `AsyncSession`, while the authorization boundary supplies `AsyncConnection`. Its test does not prove transaction identity. | Accept the authorized connection or a narrow executor protocol. Test business mutation and audit rollback through the transaction factory. No owner decision is needed. |
| `5H-SEC-16` | Medium | Admin notification SELECT and UPDATE accept null branch context for tenant-wide rows. Decision `5A-D13` requires a verified branch for the admin inbox. | Require verified branch context while retaining the null-tenant plus selected-branch partition. No owner decision is needed. |
| `5H-SEC-17` | Medium | `admin_execute_shift_swap` reads employee eligibility without locking the two employee rows, although it locks the request and rosters. | Lock both employees in a fixed order before rechecking eligibility. Add a concurrent termination test. No owner decision is needed. |
| `5H-SEC-18` | Low | Audit reads do not require a trusted business date, unlike the full human context contract. | Require a non-null business date and add a malformed-context test. No owner decision is needed. |
| `5H-SEC-19` | Low | Fixture apply and cleanup reject only `workloop_runtime` and may use generic `DATABASE_URL`. The approved path requires the migration identity. | Require `current_user = session_user = workloop_migration`. No owner decision is needed. |

### Verification findings

| ID | Severity | Finding and evidence | Disposition |
|---|---|---|---|
| `5H-VER-01` | High | The 19 control names are counted but not mapped to executable assertions. Most application obligations are absent or incomplete, several RLS denials omit secondary state, and controls 10, 17, and 18 lack an explicit current-versus-storage disposition. | Add an executable control-ID manifest that maps every A, R, and deferred S obligation to named assertions. Require before and after counts or hashes for every denial. Relaxing an A+R obligation requires owner review. |
| `5H-VER-02` | Medium | The Phase 5G downgrade chain checks counts and names but not exact expressions, roles, grants, RLS flags, protected-function properties, audit constraints, indexes, or restored grants at every stop. | Run the exact catalogue assertions at each relevant chain boundary. |
| `5H-VER-03` | Medium | Expense and regularisation denial checks rely on affected-row results without the required independent unchanged-state snapshot. | Add before and after state comparisons for every denied mutation. |
| `5H-VER-04` | Medium | CI does not route repository, schema-guard, authorization-scope test, mutation-test, or `phase-5g-catalogue.json` changes through deep database checks. | Add those paths to database-deep classification and verify routing. |
| `5H-VER-05` | Medium | The restart workflow does not rerun an empty-context probe and authorized-transaction cleanup check after restart. | Add a post-restart context probe and cleanup assertion. |
| `5H-VER-06` | Low | The automated Supabase scan omits authorization, repository, schema-guard, audit, and context modules. Manual inspection found no forbidden dependency. | Extend the machine scan and prove its corpus is nonempty. |
| `5H-VER-07` | Low | `DIGITALOCEAN_MIGRATION_PLAN.md` still lists Phase 5E through 5G as not started. | Correct the phase tracker and immediate next action during Phase 5H. |

### Gate preflight finding

| ID | Severity | Finding and evidence | Disposition |
|---|---|---|---|
| `5H-OP-01` | Medium | Live authentication verifiers and Compose ports were fixed to the main stack's host ports. That prevented the required isolated restart gate from using unique ports while the preserved PostgreSQL 16 stack remained untouched. | A Phase 5H override now binds PostgreSQL, FastAPI, Keycloak, and Keycloak management to separate loopback ports. The live verifiers accept explicit Keycloak and API base URLs with unchanged defaults. The reviewer found no product security regression. Treat the override URLs as trusted test configuration. |

## Final resolution

All 27 findings are closed. The correction set stayed within decisions `5A-D21` and `5A-D22` and
did not add a role, business table, route, cloud service, or storage integration.

| ID | Final disposition |
|---|---|
| `5H-SEC-01` | Resolved. Admin branch selection now runs inside the authorized transaction and revalidates the selected branch. |
| `5H-SEC-02` | Resolved under `5A-D21`. The fixed-purpose relationship lock serializes delegation, approver, and employee relationships before business rows, with concurrent reassignment and revocation proof. |
| `5H-SEC-03` | Resolved. Appraisal-section updates exclude employee self scope and manager self writes. |
| `5H-SEC-04` | Resolved. Notification creation revalidates the active principal and exact context before producer checks. |
| `5H-SEC-05` | Resolved. Audit creation applies the same principal and context revalidation. |
| `5H-SEC-06` | Resolved under `5A-D22`. Expiry writes prove the active admin recipient, source truth, threshold-specific notification link, exact content, and matching audit metadata. |
| `5H-SEC-07` | Resolved under `5A-D21`. Runtime offboarding-task deletion remains unavailable until durable custom-task provenance is designed. |
| `5H-SEC-08` | Resolved. Delegate scope explicitly excludes the delegate's own employee record. |
| `5H-SEC-09` | Resolved under `5A-D21`. Employee branch correction remains unavailable until a dedicated source-and-destination workflow is approved. |
| `5H-SEC-10` | Resolved under `5A-D21`. Unsupported audit actions remain denied instead of accepting caller-asserted transitions. |
| `5H-SEC-11` | Resolved. Nonhuman audit actors require a non-null, nonblank system actor key. |
| `5H-SEC-12` | Resolved. Branch creation and deletion have tenant-scoped audit actions with state checks. |
| `5H-SEC-13` | Resolved. Protected mutation coverage includes the omitted payroll, document, training, CME, appraisal, and closure fields. |
| `5H-SEC-14` | Resolved. Context setup is bounded and database failures map to the existing generic `503` response. |
| `5H-SEC-15` | Resolved. The audit wrapper accepts the authorized connection and rollback proof covers the business mutation and audit event together. |
| `5H-SEC-16` | Resolved. Admin notification reads and updates require verified branch context. |
| `5H-SEC-17` | Resolved. Shift-swap execution locks both employees before rechecking eligibility, with concurrent termination proof. |
| `5H-SEC-18` | Resolved. Audit reads require a valid trusted business date. |
| `5H-SEC-19` | Resolved. Fixture apply, validate, and cleanup require `current_user = session_user = workloop_migration`. |
| `5H-VER-01` | Resolved. The executable manifest maps every application, RLS, and deferred storage obligation for all 19 controls to named assertions. |
| `5H-VER-02` | Resolved. Exact catalogue assertions cover every Phase 5G downgrade and re-upgrade stop, including the Phase 5H head. |
| `5H-VER-03` | Resolved. Every denied mutation records and compares whole-table counts and hashes. |
| `5H-VER-04` | Resolved. Database-deep workflow classification includes repositories, schema guards, authorization tests, mutation tests, and catalogue files. |
| `5H-VER-05` | Resolved. The workflow reruns context isolation and cleanup proof after restart. |
| `5H-VER-06` | Resolved. The automated Supabase scan covers authorization, repositories, schema guards, audit, context, migrations, and fixtures. |
| `5H-VER-07` | Resolved. The main tracker now reflects the completed Phase 5 parts and the remaining owner signoff. |
| `5H-OP-01` | Resolved. The isolated stack used distinct loopback ports and left `workloop-clinic_postgres_data` untouched. |

## Confirmed coverage

The reviewer found no defect in these areas:

- JWT validation pins the algorithm, issuer, audience, token type, date claims, key strength, cache
  behavior, refresh serialization, and deadlines.
- Principal resolution trusts only verified issuer and subject, ignores browser and token business
  roles, checks active account and employee linkage, and returns generic failures.
- Fixed context readers safely reject malformed values, use invoker rights and pinned paths, revoke
  `PUBLIC`, and have symmetric downgrade behavior.
- Generic repository statements combine scope and object identity, bind values, reject raw mutation
  mappings and invalid batches, and roll back mixed batches.
- Context cleanup covers commit, rollback, exception, cancellation, pool reuse, and concurrent tenant
  requests before restart.
- Current-head catalogue checks cover policy identities and commands, grants, RLS state, role
  attributes, ownership, and helper security metadata.
- All 55 tables have an RLS disposition. Runtime and expiry roles do not own objects, inherit
  privileged roles, bypass RLS, or create objects in `public`.
- Fixtures contain 334 deterministic synthetic rows across 48 tables and have repeatable apply and
  cleanup behavior.
- Manual inspection found no Supabase database dependency or trusted browser role in current Phase 5
  authorization code.
- Audit storage is append-only for runtime actors, uses restrictive provenance foreign keys, and
  denies direct runtime mutation.

## Evidence before the decision stop

- Read-only preflight confirmed the expected branch and commit with no local or remote divergence.
- The preserved volume remains PostgreSQL 16.15 at Alembic revision `d307b9c1f25e`. Its four checked
  identity roots remain empty.
- Eighty-five focused principal, dependency, scope, repository, transaction-context, and audit unit
  tests passed.
- Python and JavaScript syntax checks passed for the isolated-gate verifier changes.
- The effective Phase 5H Compose configuration passed validation. It resolves to project
  `workloop-phase5h-verify`, PostgreSQL 17.11, volume
  `workloop-phase5h-verify_postgres_data`, and loopback ports 15432, 18000, 18080, and 19000.
- A whole-file Ruff check of `scripts/verify-phase-3c-keycloak.py` found two existing findings at
  lines 667 and 675 outside the edited code. The configured backend lint gate does not include this
  script.
- `git diff --check` passed with only the existing line-ending warnings.

The final local gate passed on a fresh isolated PostgreSQL 17.11 volume. Authentication, database
state, and signing keys survived restart; synthetic data was removed; and all isolated Phase 5H
containers, networks, and volumes were deleted. The preserved `workloop-clinic_postgres_data`
volume remains untouched.
