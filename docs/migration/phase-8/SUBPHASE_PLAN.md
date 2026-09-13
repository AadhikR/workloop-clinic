# Phase 8 subphase plan

## Status

Phase 7 code and verification are complete at commit
`9edb754675240656b23c279d8b7be765182c1930`. GitHub Migration foundation run `34742244623`
passed on 2026-09-13. The project owner has not yet recorded explicit Phase 7 signoff.

This document prepares the Phase 8 split only. It does not authorize Phase 8A or any leave runtime,
database, storage, cutover, cloud, or production-data change. Phase 8 work starts only after the
project owner signs off Phase 7 and separately authorizes the named Phase 8 part.

## Why Phase 8 needs subphases

Phase 8 covers seven leave tables, private objects, three human roles, delegated authority, balance
accounting, and several irreversible workflow transitions. The legacy implementation mixes those
responsibilities in one browser module. It calculates days and balances in JavaScript, accepts broad
status updates, writes audit rows after request writes, and reads owner-wide data for later-phase
screens.

A single cutover would tie branch configuration, employee submission, manager authority, object
cleanup, and balance correctness to one rollback. That is too much state to move safely at once.
Phase 8 is therefore split into seven parts, 8A through 8G.

## Starting point

- Alembic has one head at `8f6b2d1a4c70`.
- Phase 4 supplies the canonical `leave_settings`, `leave_types`, `public_holidays`,
  `leave_requests`, `leave_audit_log`, `leave_balances`, and `leave_approval_delegates` tables.
- Phase 5 supplies branch, employee, manager, active-delegate, and workflow authorization. It also
  supplies `can_act_for_delegated_leave` and the protected audit and notification functions.
- Phase 6 supplies the HTTP contract, idempotency recovery, upload limits, frontend client, cutover
  records, and a provider-neutral object-storage interface.
- Phase 7 supplies trusted company, branch, department, employee, reporting-manager, self-contact,
  lifecycle, and portal-role behavior.
- No FastAPI leave route, leave repository, leave service, leave schema, migration-build leave page,
  or Phase 8 cutover record exists yet.
- The current object-storage adapter proved a small private synthetic object in Phase 6G. It does
  not yet provide the complete leave upload, signing, content validation, or orphan-recovery
  contract.
- The legacy leave runtime is concentrated in `src/utils/leaveStorage.js`,
  `src/utils/leaveEngine.js`, `src/components/LeaveManager.jsx`,
  `src/components/LeaveRequestModal.jsx`, `src/components/employee/EmpLeave.jsx`, and
  `src/components/manager/ManagerLeaveQueue.jsx`.

## Part status

| Part | Scope | Status |
| --- | --- | --- |
| 8A | Leave contracts, dependency inventory, cutover units, and amendment decisions | In progress |
| 8B | Leave settings, types, and public holidays | Not authorized |
| 8C | Balance authority, accrual, carry-forward, and leave read projections | Not authorized |
| 8D | Leave attachment metadata and private-object access | Not authorized; blocked by the 8A storage ownership decision |
| 8E | Employee and administrator submission, auto-approval, and cancellation | Not authorized |
| 8F | Manager, delegate, and administrator decisions with audit | Not authorized |
| 8G | Independent review, complete cutover proof, and Phase 8 gate | Not authorized |

## Rules shared by every part

- Use synthetic local data only. Cloud resources, production data, legal-policy changes, or paid
  services require separate project-owner authorization.
- PostgreSQL remains the source of company, branch, employee, reporting relationship, portal role,
  delegation, request status, and balance authority.
- The server derives the current company, selected branch, actor, employee identity, trusted UAE
  business date, approval level, request status, day count, and balance effects.
- A browser-supplied employee ID, manager ID, delegate ID, role, status, actor email, number of days,
  leave-type code, path, or timestamp grants no authority.
- New responses use strict camelCase projections. They do not expose raw database rows, mutable
  actor labels, provider keys, or unrelated employee fields.
- Requests for inaccessible identifiers return the Phase 6 safe error contract without confirming
  that another tenant or branch owns the record.
- Every mutation has one transaction owner. Request, balance, domain audit, protected audit, and
  storage-operation records either change together or remain unchanged.
- Protected mutations use the approved idempotency contract. A retry with the same key and payload
  returns the original result. A changed payload fails.
- Mutable configuration and balance operations use the version or locking rule approved in 8A.
  Concurrent submissions and decisions cannot overspend, reserve twice, or lose a balance update.
- Leave status remains case-sensitive. The canonical set is `Pending`, `ManagerApproved`,
  `ManagerRejected`, `Approved`, `Rejected`, and `Cancelled` unless 8A approves a schema change.
- Hard deletion of leave types, used or past holidays, requests, balances, and audit rows remains
  unsupported.
- Each cutover names one read authority, one write authority, the frozen opposite path, and rollback
  order. Dual writes are forbidden.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks during implementation, run one
  boundary-matched local gate after the part is stable, push once, and wait for every routed GitHub
  job.

## Cross-phase boundaries

Phase 8 owns leave configuration, request metadata, validation, balances, workflow status,
delegation, leave-domain audit, and leave attachment permissions.

The following consumers stay with their existing owners:

- Phase 9 owns payroll deductions, advance-pay handling, and payroll use of approved leave.
- Phase 10 owns attendance resolution, holiday treatment, roster conflicts, and staffing use of
  approved leave.
- Phase 11 owns the common object-storage adapter, durable storage recovery, employee documents,
  and offboarding leave encashment.
- Phase 12 owns leave notifications, tasks, dashboards, reports, and CSV or PDF output.
- Phase 13 owns final removal of Supabase and the legacy build.

Phase 8 must publish the scoped read contracts those phases will later consume. It must not migrate
their screens, calculations, exports, notifications, or write paths early.

## 8A: Leave contracts, inventory, and decisions

### Objective

Resolve leave behavior and authority before adding a route or changing a data source.

### Scope

- Inventory every legacy leave reader, writer, RPC, converter, calculation, object path, and caller.
  Account separately for Phase 9, Phase 10, Phase 11, and Phase 12 consumers.
- Define exact settings, leave-type, holiday, request, balance, queue, delegation, attachment, and
  audit projections. Fix filters, sort order, pagination, nulls, dates, decimals, and safe warnings.
- Define server-owned working-day, calendar-day, half-day, accrual, carry-forward, sick-tier,
  once-per-career, overlap, notice, gender, service, probation, and available-balance rules.
- Define request submission, auto-approval, pending reservation, cancellation, manager decision,
  delegated decision, final administrator decision, and balance transition transactions.
- Reconcile legacy-only behavior with the canonical model. This includes the unsupported
  `Info Requested` display status, browser-supplied day counts and approval levels, actor email
  fields, removed `leave_type_code` columns, and arbitrary status updates.
- Decide the trusted business-date source and how calendar-year or another approved leave year is
  derived. Browser clocks must not decide delegation or entitlement.
- Decide attachment sequencing. An upload must bind to an authorized request or one-use submission
  token without trusting an employee ID or path from the browser.
- Review the current object-storage interface against the 10 MiB file and 12 MiB request limits.
  Choose whether to authorize a minimum Phase 11-owned signing and recovery prerequisite before 8D,
  or defer 8D and Phase 8 signoff until Phase 11. This plan does not make that choice.
- Prepare amendment proposals for any protected audit action, attachment metadata field, function,
  role, grant, RLS policy, constraint, or index change. Confirm that the existing leave notification
  producer remains unused until Phase 12. Do not create an Alembic revision until the project owner
  approves the exact proposal.
- Prepare cutover records for leave configuration, balances and reads, attachments, request
  submission, and approval workflows.

### Completion gate

The inventory accounts for every leave dependency. Every route and workflow has an exact role,
scope, transaction, idempotency, audit, error, and rollback contract. Attachment ownership and every
database amendment are either approved or explicitly deferred. No implementation starts with an
open behavior decision.

### Rollback boundary

8A changes documents only. Revert its documents if the contract is rejected. No runtime, schema,
storage, or cutover change is permitted.

## 8B: Leave settings, types, and public holidays

### Objective

Move branch leave configuration before any new request calculation depends on it.

### Scope

- Add branch-scoped repositories, services, schemas, and routes for leave settings, active leave
  types, and public holidays.
- Let administrators create or update the one settings row for the selected branch. Enforce the
  approved leave-year type, weekend rule, carry-forward bounds, approval chain, and Ramadan dates.
- Seed approved default leave types idempotently per branch. Allow administrator edits only for
  fields approved in 8A and soft-deactivate types instead of deleting them.
- Seed a named holiday year idempotently. Permit changes only to future holidays that no leave or
  attendance record uses. Retain past and used dates.
- Return only active branch types to employees and managers. Cross-tenant and cross-branch reads
  remain unsupported.
- Build the Phase 8 configuration area in the migration frontend and freeze matching legacy
  configuration writes only when the cutover record passes.

### Completion gate

Administrator writes enforce branch scope and concurrency. Staff cannot mutate configuration.
Repeated seeds do not create duplicates. Unsafe deactivation, holiday edit, or holiday deletion
leaves every row unchanged. The migration configuration page has no Supabase path.

### Rollback boundary

Disable migration configuration writes before restoring legacy writes. Roll back request or balance
writers first if they have started depending on configuration created after the cutover.

## 8C: Balance authority and leave reads

### Objective

Move leave arithmetic to the server and establish stable read projections before accepting new
requests.

### Scope

- Implement server-side day counting, accrual, carry-forward, sick-tier tracking, entitlement,
  pending reservation, used days, and remaining days under the 8A contract.
- Add idempotent balance initialization and administrator recalculation for a selected branch and
  leave year. Lock affected employees, types, requests, and balances in a deterministic order.
- Add self balance and request-calendar reads, administrator branch reads, and the minimum balance
  fields later needed by direct managers and active leave delegates.
- Return decimals without binary floating-point drift. Bind cursors and filters to company, branch,
  actor, year, sort order, and projection.
- Build the migration leave overview for administrators and the read-only employee leave view.
- Freeze legacy balance writes after the balance cutover. Keep Phase 9 payroll calculations and
  Phase 11 offboarding encashment unchanged.

### Completion gate

Synthetic boundary dates, half days, weekends, holidays, leave-year rollover, carry-forward caps,
sick tiers, probation, and once-per-career rules match the approved contract. Recalculation is
repeatable. Concurrent operations cannot produce a negative balance or a lost update. Self, team,
delegate, and administrator reads expose only their approved rows and fields.

### Rollback boundary

Freeze migration balance mutations before restoring the legacy recalculator. New request writes must
roll back first because they depend on the migration balance rules. Read rollback may proceed only
when the restored writer produces the same projection.

## 8D: Leave attachments

### Objective

Add private leave attachments without making an object key or signed URL an authorization boundary.

### Scope

- Consume the Phase 11-owned storage prerequisite approved in 8A. Do not add common adapter,
  signing, or durable recovery behavior inside Phase 8.
- Accept one bounded file through FastAPI. Enforce the approved content-type list, file signature,
  size, digest, metadata size, timeout, and filename handling.
- Generate an opaque object key from trusted company, branch, request ownership, object category,
  and a random identifier. Store only approved leave metadata.
- Allow an employee to upload and sign their own request attachment. Allow an administrator within
  the selected branch. Allow a manager or active delegate to sign only an attachment on a request
  currently visible in their queue.
- Deny public URLs, browser paths, direct provider credentials, arbitrary list, copy, move, or
  standalone delete operations.
- Record orphan cleanup intent after failed submission or request cancellation. Let the approved
  Phase 11-owned recovery worker reconcile it. Use a local synthetic storage double unless the
  project owner separately authorizes a cloud proof.
- Build upload and authorized-view behavior in the migration leave forms. Freeze the legacy
  Supabase bucket path only after the attachment cutover passes.

### Completion gate

Content, size, signature, digest, ownership, branch, queue, expiry, and orphan-failure tests pass.
A signed URL is short-lived and cannot authorize another API call. Failed metadata or object writes
leave a recoverable state with no public object. No production or paid cloud resource is used.

### Rollback boundary

Disable new upload and signing routes before restoring the legacy attachment path. Preserve metadata
for committed requests. Reconcile only objects proven orphaned by the approved operation record.

## 8E: Submission, auto-approval, and cancellation

### Objective

Move employee and administrator request creation into one server-owned transaction.

### Scope

- Add self submission and administrator submission for an employee in the selected branch. Derive
  self identity from the trusted principal and validate administrator targets through Phase 7
  employee scope.
- Recompute dates, days, leave type, balance, overlap, service, gender, probation, required reason,
  type-specific fields, substitute, notice, and attachment ownership on the server.
- Reserve pending balance in the submission transaction. For an active auto-approve type, approve,
  consume balance, and append audit evidence in that same transaction.
- Add employee cancellation of an owned `Pending` request and administrator cancellation of a
  future `Approved` request. Release or reverse balance effects and append audit evidence atomically.
- Reject arbitrary request patches and browser-supplied status transitions.
- Use idempotency for submission and cancellation. Lock overlapping requests and relevant balance
  rows so concurrent submissions cannot double-spend or bypass overlap checks.
- Build the employee request form and administrator submit-for-staff flow in the migration frontend.
  Do not send notifications or update payroll, attendance, roster, task, dashboard, or report data.
- Freeze legacy submission and cancellation writers after the request cutover passes.

### Completion gate

Every valid request has the server-derived days, approval level, warnings, attachment reference,
balance effect, and audit row. Invalid, stale, duplicate, conflicting, wrong-scope, or concurrent
requests change nothing. Auto-approval is distinguishable from a human decision. Browser tests cover
administrator and employee behavior after token refresh and restart.

### Rollback boundary

Disable migration submission and cancellation before restoring legacy writers. Keep committed
requests, balance effects, and audit rows. Roll back the attachment writer first only if the restored
submission path cannot consume the migration attachment reference.

## 8F: Approval queues, delegation, and final decisions

### Objective

Move manager, delegate, and administrator decisions into named locked workflows.

### Scope

- Add manager queues from current one-level direct reports. Add delegated rows only when the trusted
  UAE business date is inside an active same-branch delegation for an eligible approver and delegate.
- Let administrators create delegations. Permit update or deletion only before the delegation starts.
  Keep active and expired rows as immutable history.
- Lock and recheck the request, employee, reporting manager, delegation, leave type, settings,
  attachment, and balance before each decision.
- Apply the approved transition table. A one-level manager approval becomes `Approved`. A two-level
  approval becomes `ManagerApproved`. Manager or delegate rejection becomes `ManagerRejected`.
  Administrators decide one-level `Pending` requests or finalize `ManagerApproved` requests.
- Prevent discretionary self-approval by request owners and delegates. Enforce required rejection
  and override reasons and exact actor separation.
- Consume, release, or preserve balance amounts in the same transaction as status, domain audit,
  and protected audit. Leave notification delivery to Phase 12.
- Build the migration manager queue, delegate management, administrator queue, audit view, and final
  decision controls. Staff receive request status, not direct audit-table access.
- Freeze legacy decision, queue, delegation, and audit writers only when all related cutover records
  pass.

### Completion gate

Direct-report changes immediately alter manager and delegate scope. Expired, future, cross-branch,
inactive, self, stale, repeated, and concurrent decisions fail safely. Every allowed transition
changes request, balance, and audit state together. No actor can use leave delegation for another
domain.

### Rollback boundary

Disable migration decisions before restoring legacy decision writers. Preserve all committed audit
and delegation history. Roll back approval workflows before submission, balances, attachments, or
configuration.

## 8G: Independent review and completion gate

### Objective

Prove the complete Phase 8 boundary before requesting Phase 8 signoff.

### Scope

- Review authorization, trusted dates, calculations, transaction ownership, RLS, protected
  functions, optimistic locking, idempotency, object access, audit coverage, error disclosure, and
  rollback independently of the implementation passes.
- Trace every 8A inventory entry to a migrated route, explicit later-phase owner, or retained legacy
  dependency.
- Validate all completed cutover records, freeze guards, attachment cleanup steps, single-writer
  declarations, and reverse dependency rollback order.
- Run one complete boundary-matched local Phase 8 gate in a fresh isolated environment.
- If Phase 8 adds an approved Alembic revision, prove append-only history, exact predecessor
  restoration, an empty-schema replay, and current-head repeatability.
- Restart existing images without rebuilding. Compare database, signing-key, and synthetic storage
  state. Run the complete leave browser journey once after the final restart.
- Remove synthetic rows, objects, credentials, containers, networks, and temporary volumes. Do not
  attach or modify `workloop-clinic_postgres_data`.
- Push the settled Phase 8 changes once and require every routed GitHub job before requesting owner
  signoff.

### Completion gate

Focused suites and the complete local gate pass. Every Phase 8 feature has one read and write
authority, migration leave code has no Supabase path, restart and rollback proof pass, synthetic
cleanup is complete, GitHub passes, and the project owner signs off Phase 8.

### Rollback boundary

Use the cutover records in reverse order: decisions and delegation, submission and cancellation,
attachments, balances and reads, then configuration. Never restore a legacy writer while its
FastAPI counterpart remains writable.

## Recommended execution order

Execute `8A -> 8B -> 8C -> 8D -> 8E -> 8F -> 8G`.

Configuration fixes the calendar and policy inputs. Balance authority must settle before submission.
Attachments must establish a trusted request binding before attachment-required submissions cut
over. Submission must settle before human decisions. The independent review runs only after all
leave code and cutover records are stable.
