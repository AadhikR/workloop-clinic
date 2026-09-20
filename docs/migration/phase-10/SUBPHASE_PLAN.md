# Phase 10 subphase plan

## Status

Phase 9 implementation and verification are complete at commit
`093895acfaf28b123ca592ecf95a7af841a0832c`. GitHub Migration foundation run
`35350832324` passed on 2026-09-18, and Alembic has one head at `f4b8d2e6a901`.
The project owner signed off Phase 9 and authorized 10A on 2026-09-18. The owner directed 10A to
settle bounded Phase 10 decisions with best judgment, commit its approved contract artifacts, and
continue into 10B without an intermediate authorization pause. Parts 10A and 10B are complete.

This document splits Phase 10 into ten parts, 10A through 10J. The completed authorization covered
10A and 10B. Part 10C is next but remains unauthorized, as do Parts 10D through 10J. The completed
authorization did not include production data, external biometric devices, paid services, cloud
resources, or the preserved PostgreSQL volume.

## Why Phase 10 needs subphases

Attendance and rostering share shifts, employees, branch rules, leave, staffing rules, payroll
inputs, and employee self-service. They do not share the same lifecycle. Raw clock events must stay
append-only, calculated attendance can be corrected, closed periods must become payroll-stable,
rosters are drafted before publication, and published assignments may change only through a
protected swap.

The legacy browser also performs calculation, deduplication, period close, roster publication, and
several related writes in separate operations. A single cutover would make one rollback responsible
for event ingestion, payroll deductions, roster publication, and employee schedules. Phase 10
therefore establishes common configuration first, moves raw input before derived records, closes
attendance before exposing payroll data, and settles roster publication before enabling swaps. The
last part reviews the complete boundary independently.

## Starting point

- Phase 4 supplies canonical tables for `attendance_settings`, `shifts`, `shift_assignments`,
  `clock_events`, `attendance_records`, `attendance_periods`, `regularisation_requests`,
  `attendance_audit_log`, `roster_assignments`, `shift_swap_requests`, and
  `biometric_mappings`.
- Phase 5 supplies selected-branch, employee-self, workflow, history, RLS, grant, and
  protected-function boundaries. It retains `admin_execute_shift_swap` behind the runtime role.
- Phase 6 supplies HTTP, camelCase projection, idempotency, error, pagination, frontend-client, and
  cutover conventions.
- Phase 7 supplies trusted companies, branches, departments, staffing rules, employees,
  employment state, reporting relationships, salaries, and portal roles.
- Phase 8 supplies public holidays and approved-leave projections. Attendance and roster workflows
  consume them but do not mutate leave state.
- Phase 9 supplies the exact read-only attendance and roster payroll-input contracts. Payroll fails
  closed with `409 payroll_input_not_ready` until Phase 10 provides a closed attendance projection
  and a published roster projection.
- The migration build has no attendance, roster, biometric, correction, or schedule screen yet.
- The legacy boundary is concentrated in `src/utils/attendanceStorage.js`,
  `src/utils/attendanceEngine.js`, `src/utils/biometricStorage.js`,
  `src/components/AttendanceManager.jsx`, `src/components/BiometricImport.jsx`,
  `src/components/RosterManager.jsx`, `src/components/employee/EmpAttendance.jsx`, and
  `src/components/employee/EmpSchedule.jsx`.
- The current canonical roster rows have no month-level publication state, publication timestamp,
  or source version. Published roster rows are immutable except through the protected swap, while
  the Phase 9 contract expects approved actual hours and overtime. Phase 10A must resolve that
  mismatch before a roster or payroll writer changes.

## Part status

| Part | Scope | Status |
| --- | --- | --- |
| 10A | Contracts, dependency inventory, golden cases, amendments, and cutover decisions | Complete |
| 10B | Attendance settings, shift templates, and effective-dated shift assignment | Complete |
| 10C | Manual and biometric event ingestion, badge mappings, provenance, and deduplication | Next; not authorized |
| 10D | Server attendance calculation, administrator reads, and employee self reads | Planned; not authorized |
| 10E | Regularisation, absence resolution, overtime approval, and attendance audit | Planned; not authorized |
| 10F | Atomic period close and the closed attendance payroll projection | Planned; not authorized |
| 10G | Roster drafts, leave conflicts, staffing gates, and compliance overrides | Planned; not authorized |
| 10H | Roster publication, employee schedules, actual-hours authority, and payroll projection | Planned; not authorized |
| 10I | Shift-swap requests, cancellation, rejection, and protected execution | Planned; not authorized |
| 10J | Independent review, complete cutover proof, and Phase 10 gate | Planned; not authorized |

## Rules shared by every part

- Use synthetic local data only. Production data, real employee data, external biometric devices,
  paid services, cloud resources, and legal-policy decisions need separate project-owner
  authorization.
- PostgreSQL remains authoritative for attendance settings, shifts, assignments, raw events,
  calculated records, corrections, periods, rosters, swaps, audit, and payroll-input source state.
- The server derives company, selected branch, actor, employee identity, employment eligibility,
  UAE business date, attendance date, payroll period, workflow state, and calculated values.
  Browser fields grant no authority.
- Store instants as timezone-aware values and business dates as dates. Apply the approved UAE
  timezone and overnight-shift rule once on the server. Browser locale parsing cannot decide which
  attendance day owns an event.
- Raw clock events are append-only. Corrections supersede source events and preserve provenance;
  they do not rewrite or delete history.
- Use `Decimal` and PostgreSQL `NUMERIC` for hours, rates, deductions, and overtime amounts. Reject
  binary floating-point persistence, non-finite values, excess scale, excess precision, and values
  outside database bounds.
- Every mutation has one transaction owner. Failed, stale, or unauthorized commands leave source
  rows, derived rows, status, audit, idempotency, publication, and payroll-input versions unchanged
  wherever the operation touches them.
- Protected commands use the Phase 6 idempotency contract. The same key and payload return the
  original result. A changed payload fails. Import batches also use a durable batch identity and
  event fingerprint so a retry cannot insert the same punch twice.
- Mutable rows use a locked state check and an expected version or timestamp. Concurrent commands
  cannot calculate over changed inputs, approve the same correction twice, close a period twice,
  publish a changed roster, or execute a swap twice.
- Closed attendance inputs and published roster inputs are immutable under their approved contract.
  A correction, late import, actual-hours update, or swap either follows an explicit versioned
  amendment path approved in 10A or fails. No route silently changes payroll source data.
- The server writes actor IDs and timestamps from trusted context. Request bodies cannot assign
  company IDs, branch IDs, employee owners, approval actors, audit actors, closed state, published
  state, or payroll readiness.
- Administrators operate only in the selected branch. Employees and managers receive only their
  personal attendance and published schedule contracts unless 10A approves a narrowly scoped
  colleague selector for a swap. Managers receive no team attendance or roster-management power.
- The employee portal has no self clock-in or clock-out command. Manual events are administrator
  operations; biometric events come only through the approved import boundary.
- Responses use strict camelCase projections and safe missing-or-inaccessible errors. They do not
  expose biometric secrets, raw audit rows, another employee's attendance, unpublished rosters, or
  internal source fingerprints.
- Every cutover record names one read authority, one write authority, a frozen opposite path, and
  rollback order. Dual writes are forbidden. A legacy fallback cannot run inside a migration flow.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks while developing, run one
  boundary-matched local gate after each part settles, push once, and wait for every routed GitHub
  job.

## Cross-phase boundaries

Phase 10 owns attendance configuration, shifts, shift-assignment history, clock-event ingestion,
attendance calculation and corrections, overtime approval, attendance period closure, roster
drafting and publication, actual-hours source state, employee schedules, shift swaps, and the exact
read-only attendance and roster payroll projections.

The following owners remain unchanged:

- Phase 7 owns company, branch, department, staffing-rule, employee, employment, reporting-line,
  salary, and portal-role state. Phase 10 consumes those scoped projections and never repairs them.
- Phase 8 owns public holidays, approved leave, and leave conflict source state. Phase 10 consumes
  them and never changes a leave request or balance.
- Phase 9 owns payroll calculations, automatic adjustments, approval, finalization, and payslips.
  Phase 10 exposes versioned read-only inputs; it does not create payroll entries or mark payroll
  inputs as applied.
- Phase 11 owns common production object storage and unrelated employee lifecycle domains. Phase 10
  accepts bounded attendance import bytes in the approved request; it does not introduce a device
  file archive or vendor storage integration.
- Phase 12 owns notifications, tasks, dashboards, reports, and CSV, PDF, or ZIP output. Attendance
  and roster input CSV parsing belongs to Phase 10, but report and roster export remain Phase 12.
- Phase 13 owns final removal of Supabase and the legacy build.

No Phase 10 route may call Supabase. A later-phase consumer may remain in the legacy build, but a
migration attendance, roster, schedule, swap, or payroll-input flow must use a named FastAPI
projection or fail closed.

## 10A: Attendance and roster contracts, inventory, and cutover decisions

### Objective

Resolve attendance, rostering, payroll-source, and lifecycle behavior before adding a route or
changing a writer.

### Scope

- Inventory every legacy attendance, shift, assignment, event, calculation, correction, period,
  biometric, roster, staffing, compliance, swap, employee self-service, payroll-input, task,
  notification, dashboard, report, and export dependency.
- Trace every caller to Parts 10B through 10I or to an explicit Phase 11, 12, or 13 owner. Record
  retained SQL functions and every legacy fallback that must be frozen.
- Define strict administrator and employee request and response contracts, including filters,
  ordering, pagination, nulls, dates, instants, decimals, redaction, safe errors, and whether any
  swap colleague selector is allowed.
- Approve the trusted UAE timezone, business-date boundary, overnight-shift event association,
  split-shift behavior, flexible-shift threshold, effective-assignment precedence, and the source
  snapshot used by a recalculation.
- Reconcile event method names, including the legacy `BIOMETRIC_API` fixture and canonical
  `BIOMETRIC` constraint. Define actor and device provenance, accepted import columns, batch limits,
  timestamp formats, event ordering, deduplication tolerance, and late-arriving-event behavior.
- Approve the attendance status precedence and every calculation rule for weekend work, holidays,
  leave, missing clock-out, lateness, early departure, half days, WFH, Ramadan hours, unexplained
  absence, consecutive absence flags, and overtime premiums.
- Fix exact decimal rounding points for hourly rates, late deductions, absence deductions, standard
  overtime, night overtime, and rest-day overtime. Decide whether salary is snapshotted at
  calculation, approval, or period close.
- Define correction, absence-resolution, overtime-approval, recalculation, period-close, and any
  period-amendment transitions. State which changes are forbidden after close and how a permitted
  amendment produces a new payroll source version without rewriting history.
- Define roster draft, validation, publication, actual-hours, and swap transitions. Decide how a
  published roster remains immutable while actual hours and approved overtime become durable
  payroll inputs.
- Decide the only authority for roster actual hours and overtime approval. Prevent the same work
  from appearing in both attendance overtime and roster overtime unless the contract identifies
  distinct, non-overlapping sources.
- Define month-level roster publication status, `publishedAt`, source version, affected-row set,
  republish rules, swap versioning, and behavior when payroll has already snapshotted a roster
  version. The current row-only `published` flag is insufficient for the Phase 9 contract.
- Define staffing-gate evaluation from Phase 7 rules, approved-leave conflict behavior, disabled
  staffing behavior, immutable compliance overrides, and the exact lock set used during publish.
- Review the synthetic golden cases for all attendance statuses, manual and biometric events,
  duplicate and unknown badges, corrections, close blockers, deductions, each overtime class,
  roster staffing, leave conflict, actual hours, publication, and swaps. Add missing exact expected
  inputs and results before implementation.
- Define the exact Phase 9 attendance and roster projections, including deterministic
  `sourceVersion` construction, source row IDs, readiness errors, stale-version behavior, and
  calculation of the roster golden value of AED 288.46.
- Prepare proposals for every missing audit action, idempotency resource, role, grant, RLS policy,
  protected function, constraint, index, version field, publication entity, or immutable snapshot.
  Do not create an Alembic revision before the project owner approves the exact proposal.
- Prepare separate cutover records for configuration, event ingestion, attendance calculation,
  exceptions, period close and projection, roster drafting, roster publication and projection, and
  shift swaps.

### Completion gate

The inventory accounts for every dependency. Every route and workflow has an exact role, scope,
timezone, calculation, transaction, idempotency, concurrency, audit, error, cutover, and rollback
contract. Event methods, post-close behavior, actual-hours authority, overtime overlap, roster
publication versioning, payroll projections, and all required schema or security amendments have no
open question. The project owner has approved the contract and the exact amendments needed for the
next authorized part.

### Rollback boundary

10A changes documents only. Revert its documents if the contract is rejected. It permits no runtime,
schema, security, import, or cutover change.

## 10B: Attendance settings, shifts, and effective assignments

### Objective

Move the branch rules and shift foundation used by every later attendance and roster operation.

### Scope

- Add selected-branch administrator reads and updates for attendance settings. Validate working and
  weekend days, hours, grace periods, overtime limits, deduction policy, WFH, regularisation limits,
  and biometric flags on the server.
- Keep the biometric API key administrator-only, write-only in ordinary projections, and redacted
  from logs and errors. Do not add vendor communication unless 10A explicitly approved it.
- Add selected-branch administrator shift list, create, edit, and soft-deactivate operations. Enforce
  unique names and codes, valid categories and types, time requirements, expected hours, breaks,
  grace periods, staffing minimums, overnight semantics, and retained-use guards.
- Add effective-dated employee shift-assignment history. Lock overlapping assignments, validate
  active same-branch employees and shifts, and end-date the prior assignment under the approved
  rule instead of creating ambiguous history.
- Expose only the safe active shift fields required by later employee projections. Staff receive no
  settings secret and no direct shift-assignment history.
- Add the migration administrator settings, shift-template, and assignment controls approved in
  10A. Do not add clock events, attendance calculation, roster drafts, or schedules yet.
- Freeze matching legacy settings, shift, and shift-assignment writers only after the configuration
  cutover passes.

### Completion gate

Settings bounds, secret redaction, branch scope, soft deactivation, referenced-shift retention,
overnight and split validation, effective-date precedence, non-overlap, stale updates, and
concurrent assignment changes pass. Every later workflow can obtain one trusted settings snapshot
and at most one effective shift for an employee and date.

### Rollback boundary

Disable migration configuration mutations before restoring legacy writers. Preserve referenced
shifts and assignment history. Later attendance, roster, and swap parts must roll back before 10B.

## 10C: Clock-event and biometric ingestion

### Objective

Make FastAPI the sole writer of append-only manual and biometric attendance evidence.

### Scope

- Add selected-branch administrator clock-event reads with bounded employee and date filters. Add
  employee self reads only through the minimal projection needed by personal attendance.
- Add administrator manual `CLOCK_IN` and `CLOCK_OUT` commands. Derive the actor, method, company,
  and branch, validate employee eligibility and trusted date rules, and require the approved note or
  reason fields.
- Add selected-branch biometric mapping list, create or replace, and guarded delete operations.
  Validate branch-unique badges and active same-branch employees.
- Keep CSV parsing local only where it is presentation-safe. Send normalized candidate rows to a
  bounded server import that validates badge, device, event type, timestamp, timezone, scope, and
  file or batch limits again.
- Insert an import batch atomically under the approved partial-failure rule. Persist batch identity,
  row provenance, and deterministic event fingerprints. Same-key replay returns the first result;
  duplicate punches are skipped without hiding malformed or unknown-badge rows.
- Preserve raw events. There is no update or delete route, and no import path may set correction,
  approval, audit, or payroll fields.
- Add migration manual-entry, mapping, and biometric-import controls. Do not expose portal clock
  buttons or background device polling.
- Freeze legacy manual-event, biometric-mapping, and biometric-import writers only after ingestion
  cutover passes.

### Completion gate

Manual, matched-badge, unknown-badge, duplicate, malformed timestamp, out-of-branch employee,
oversized batch, retry, changed-payload, concurrent import, event order, overnight, and secret
redaction cases pass. Every accepted punch has durable provenance and exactly one raw event. No
ordinary route can update or delete it.

### Rollback boundary

Disable migration ingestion before restoring a legacy writer. Preserve all accepted events,
fingerprints, batch results, and mappings. Reconcile no event by deletion; a later correction may
supersede it under 10E.

## 10D: Attendance calculation and personal reads

### Objective

Move daily attendance derivation and scoped reads from browser code to one server calculation.

### Scope

- Port the approved attendance engine to server-owned decimal and timezone-aware code. Browser
  calculations may preview but cannot persist a record or money value.
- For each employee and business date, read a locked or versioned snapshot of settings, effective
  shift, nonsuperseded clock events, employment state, public holidays, approved leave, salary, and
  the approved Ramadan calendar.
- Apply the 10A status precedence and calculations for all canonical attendance states, missing
  clock-out, total hours, lateness, early departure, half day, rest-day work, overtime class,
  absence deduction, late deduction, and consecutive unexplained absence evidence.
- Upsert one branch-scoped record per employee and date under an expected source version. Reject a
  recalculation if its inputs changed, the period is closed, or the employee is outside the
  selected branch.
- Add bounded selected-branch administrator list and daily calculation operations with safe batch
  limits and deterministic employee ordering.
- Add employee and manager personal today and history reads. Permit the approved fallback to their
  own raw events when a calculated record does not yet exist; never return another employee's data.
- Add the migration administrator attendance view and personal attendance screen. Do not add
  correction decisions, overtime approval, period close, reports, exports, tasks, or notifications.
- Freeze matching legacy calculation and attendance-read paths only after their cutovers pass.

### Completion gate

Every canonical attendance state and approved financial golden case passes with exact intermediate
values. UAE date edges, overnight events, split and flexible shifts, rest days, holidays, leave,
Ramadan, missing punches, late events, changed inputs, closed periods, branch scope, self scope,
batch failure, and concurrent calculation are proven.

### Rollback boundary

Disable migration calculation before restoring the legacy calculation writer. Preserve raw events
and any records already consumed by a correction or close. Personal reads may return to legacy only
after there is one authoritative record source.

## 10E: Corrections, resolutions, overtime approval, and audit

### Objective

Move every attendance exception through a locked, audited server workflow.

### Scope

- Add employee self regularisation submission and history. Derive employee and branch from the
  principal; enforce the approved date window, monthly limit, clock ordering, maximum span, reason,
  and pending-request rules.
- Add selected-branch administrator correction queues and approve or reject commands. Approval
  locks the request, source events, and attendance record; creates the approved superseding
  evidence; recalculates the record; changes request state; and appends audit in one transaction.
- Add selected-branch administrator absence resolution for `LEAVE_LINKED`, `UNAUTHORISED`, and
  `WFH`. Revalidate current leave and source state and calculate any deduction on the server.
- Add selected-branch overtime approval under the approved overtime class and amount rules. The
  approval actor, time, source version, and audit entry are trusted server values.
- Reject stale, repeated, self-decided, cross-branch, closed-period, or invalid transition commands
  without partial request, event, record, or audit changes.
- Keep attendance audit append-only and expose it only through the approved administrator
  projection. Employee history receives correction status, not raw audit rows.
- Add migration employee correction controls and administrator correction, resolution, and
  overtime controls. Leave reports, notifications, and task aggregation to Phase 12.
- Freeze matching legacy exception writers only after the correction cutover passes.

### Completion gate

Submission limits, approval, rejection, supersession, recalculation, absence resolutions, overtime
approval, reasons, actor rules, stale versions, idempotent replay, changed payload, concurrent
decisions, closed-period denial, self scope, branch scope, and forced transaction rollback pass.
Every successful transition has one matching immutable audit entry.

### Rollback boundary

Disable migration exception mutations before restoring legacy writers. Preserve decided requests,
superseded events, approved overtime, resolutions, and audit history. Roll back 10F before 10E
because period close consumes resolved state.

## 10F: Attendance period close and payroll projection

### Objective

Close a branch attendance period atomically and provide the exact payroll-ready projection required
by Phase 9.

### Scope

- Add selected-branch period list and detail reads with strict `YYYY-MM` periods and safe status,
  blocker count, close actor, and close timestamp fields.
- Add one idempotent close command that locks the period, all included records, unresolved
  corrections, source events required by the contract, and any version inputs in deterministic
  order.
- Recompute the approved close blockers, including missing clock-outs, unresolved unexplained
  absences, pending corrections, unapproved overtime where required, missing calculation days, and
  changed source snapshots. Browser-provided blocker counts are informational only.
- In one transaction, create or close the period, mark its complete record set closed, record the
  trusted actor and time, set `payrollReady=true`, append required audit, and persist the immutable
  source version. A failure leaves the entire period open.
- Expose the internal Phase 9 attendance projection identified by company, branch, period,
  `status=closed`, and `payrollReady=true`. Include `sourceVersion`, `closedAt`, and deterministic
  employee rows with absence days and amount, late minutes and amount, approved standard overtime
  hours and amount, approved rest-day overtime hours and amount, and source row IDs.
- Return `409 payroll_input_not_ready` for missing, open, provisional, mixed-branch, changed, or
  otherwise unapproved input. Do not expose a public mutation route to payroll and do not mark a
  payroll item applied.
- Add migration close controls and readiness details. Period reports and CSV or PDF output remain
  Phase 12.
- Freeze legacy period-close and attendance-payroll readers only after close and projection
  cutovers pass.

### Completion gate

Every close blocker, exact employee aggregate, source row ID, source version, money value, lock
order, replay, changed payload, concurrent close, forced rollback, branch scope, and immutable
post-close behavior passes. The Phase 9E attendance-input integration accepts the exact closed
projection and continues to reject every provisional or changed case.

### Rollback boundary

Disable the migration close command and Phase 9 attendance-input refresh before restoring a legacy
close writer. Preserve closed periods, their records, versions, audit, and payroll snapshots.
Never reopen or delete closed evidence as a rollback shortcut.

## 10G: Roster drafts, leave conflicts, and staffing gates

### Objective

Move selected-branch roster authoring and publication validation before any roster becomes visible
to staff.

### Scope

- Add selected-branch administrator month reads and draft create, replace, and guarded delete
  operations. Validate active employee, active shift, date, branch, planned hours, notes, and one
  assignment per employee and date.
- Reject edits to published rows. Permit delete only for unpublished rows with no retained workflow
  use, as defined by the Phase 5 retention rule.
- Add deterministic department and employee filters to the migration roster editor without using
  browser filtering as authorization.
- Evaluate approved and manager-approved leave conflicts from the Phase 8 projection. Keep the
  roster unchanged until the administrator corrects the conflict or follows the approved override
  contract.
- Evaluate effective Phase 7 staffing rules by department, date, and shift category. When staffing
  enforcement is disabled, omit the report and do not block publication. When it is enabled, a
  shortfall blocks publication unless an approved immutable branch override applies.
- Append compliance overrides with a closed code, required reason, trusted actor, affected month,
  and exact violation snapshot. Do not update or delete an override.
- Add migration shift-template reuse, monthly roster editing, leave-conflict review, staffing-gate
  review, and override controls. Do not publish, notify, export, or expose schedules yet.
- Freeze the legacy roster draft writer only after the draft cutover passes.

### Completion gate

Draft create, replace, guarded delete, published-row denial, employee eligibility, shift state,
branch scope, duplicate date, decimal hours, stale edits, concurrent cells, leave conflicts,
effective staffing rules, disabled staffing, violation details, override reasons, override
immutability, and forced rollback pass.

### Rollback boundary

Disable migration draft and override mutations before restoring the legacy draft writer. Preserve
published rows and immutable overrides. Roster publication and swaps must roll back before 10G.

## 10H: Roster publication, schedules, and payroll projection

### Objective

Publish one versioned branch roster, expose personal schedules, and provide the exact approved
roster input required by payroll.

### Scope

- Add one idempotent publish command that locks the roster month, draft rows, employees, shifts,
  leave-conflict inputs, staffing-rule inputs, and applicable overrides in deterministic order.
- Recompute every gate on the server. Publish the exact validated row set atomically with trusted
  `publishedAt`, actor, affected-row identity, and `sourceVersion`. A failed or stale publish leaves
  every row unpublished.
- Enforce published-row immutability except through the protected swap in 10I and any distinct
  versioned actual-hours mechanism approved in 10A. Do not retrofit ordinary updates onto published
  rows.
- Implement the approved actual-hours and roster-overtime authority. Preserve provenance and
  approval, avoid overlap with attendance overtime, and create a new source version when the
  contract permits a change.
- Add employee and manager personal schedule reads for published rows only. Add only the minimal
  same-branch colleague selector approved for shift-swap requests; do not expose attendance,
  salaries, unpublished schedules, or unrelated employees.
- Expose the internal Phase 9 roster projection identified by company, branch, period, and
  `status=published`. Include `sourceVersion`, `publishedAt`, and deterministic employee rows with
  actual hours, approved overtime hours and amount, and source row IDs.
- Return `409 payroll_input_not_ready` for missing, draft, provisional, mixed-branch, changed,
  unapproved, or overlapping overtime inputs. Do not mutate payroll state.
- Add migration publication controls and personal schedule screens. Publication notifications and
  roster CSV or PDF output remain Phase 12.
- Freeze legacy roster publication, employee schedule, and roster-payroll readers only after their
  cutovers pass.

### Completion gate

Complete, incomplete, stale, concurrent, under-staffed, leave-conflicted, overridden, and forced
failure publication cases pass. Staff see only their published schedules. The roster golden case
produces four approved overtime hours and AED 288.46 with exact source identity. Phase 9E accepts the
published projection and rejects every draft, changed, mixed, duplicated, or overlapping source.

### Rollback boundary

Disable migration publication, schedule reads, actual-hours mutation, and Phase 9 roster-input
refresh before restoring legacy paths. Preserve published versions, actual-hours evidence,
overrides, and payroll snapshots. Roll back 10I before 10H.

## 10I: Shift swaps

### Objective

Move employee swap requests and administrator decisions while preserving published-roster
integrity.

### Scope

- Add employee and manager personal swap reads, same-branch request submission, and own pending
  cancellation. Derive the requester from the principal and validate both published source rows,
  participants, dates, eligibility, relationship to the request, reason, and duplicate-pending
  rules.
- Add selected-branch administrator pending and history reads plus rejection with a required reason.
  A direct update cannot approve a swap.
- Approve only through `admin_execute_shift_swap` after FastAPI validates authorization,
  idempotency, expected versions, payroll-source state, and the approved transition contract.
- Lock the request, both employees, and both roster rows in deterministic order. Recheck current
  employment, branch, publication, shift compatibility, leave, staffing, and any frozen payroll
  boundary required by 10A before swapping atomically.
- Derive the actor from trusted context. If 10A approves removal of the retained actor parameter,
  add only the reviewed append-only revision; otherwise enforce its equality guard.
- Update the roster source version and audit or history atomically under the approved publication
  contract. A failed swap leaves both roster rows and the request unchanged.
- Add migration employee request and cancellation controls plus administrator approve and reject
  controls. Swap notifications remain Phase 12.
- Freeze legacy swap RPC callers and writers only after the swap cutover passes.

### Completion gate

Request, participant read, cancellation, rejection, approval, stale roster, changed employee,
leave, staffing, same-row, cross-branch, cross-tenant, duplicate, replay, changed payload,
concurrent approval, terminated employee, payroll-version, and forced rollback cases pass. Approval
changes exactly two roster assignments, one request, one source version, and the required audit or
history in one transaction.

### Rollback boundary

Disable migration swap mutations before restoring legacy callers. Preserve decided requests,
executed swaps, publication versions, and audit. Never reverse an approved swap by deleting its
history; use only a separately authorized compensating workflow.

## 10J: Independent review and completion gate

### Objective

Prove the complete Phase 10 boundary before requesting Phase 10 signoff.

### Scope

- Review authorization, branch and self scope, timezone and overnight handling, decimal arithmetic,
  event provenance, deduplication, transaction ownership, RLS, grants, protected functions,
  optimistic locking, idempotency, audit coverage, secret and error disclosure, and rollback
  independently of the implementation passes.
- Trace every 10A inventory entry to a migrated route, an explicit Phase 11 through 13 owner, or a
  deliberately retained dependency. Prove that no migration attendance, roster, schedule, swap, or
  payroll-input path calls Supabase.
- Validate all cutover records, freeze guards, single-writer declarations, source versions,
  post-close and post-publication immutability, and reverse dependency rollback order.
- Prove every attendance and roster golden case with exact intermediate values, source row IDs, and
  versions, not only final totals.
- Run one complete boundary-matched local Phase 10 gate in a fresh isolated environment.
- Prove append-only migration history, empty-schema replay, repeatable current-head upgrade, and
  exact predecessor restoration for each Phase 10 revision.
- Restart existing images without rebuilding. Compare database, Keycloak signing-key, and synthetic
  storage state. Run the complete administrator, manager, employee, attendance, biometric, roster,
  payroll-input, and swap browser journey once after the final restart.
- Remove synthetic rows, imported test files, credentials, containers, networks, and temporary
  volumes. Do not attach or modify `workloop-clinic_postgres_data`.
- Push the settled Phase 10 changes once and require every routed GitHub job before requesting owner
  signoff.

### Completion gate

Focused suites and the complete local gate pass. Every Phase 10 feature has one read and write
authority. Raw evidence, calculations, corrections, close, publication, payroll projections, and
swaps are scoped, atomic, versioned, and auditable. Migration Phase 10 code has no Supabase path.
Golden values, restart, rollback, cutover, cleanup, and Phase 9 integration proofs pass. GitHub
passes and the project owner signs off Phase 10.

### Rollback boundary

Use the cutover records in reverse order. Roll back swaps first, then roster publication and payroll
projection, roster drafts and gates, attendance period close and payroll projection, corrections and
approvals, attendance calculation and reads, clock-event ingestion, and configuration. Never
restore a legacy writer while its FastAPI counterpart remains writable, and never delete closed,
published, corrected, or swapped evidence to simplify rollback.

## Recommended execution order

Execute `10A -> 10B -> 10C -> 10D -> 10E -> 10F -> 10G -> 10H -> 10I -> 10J`.

Configuration and effective shifts settle before event calculation. Raw events settle before
derived attendance. Exceptions settle before a period can close. Roster drafting and its staffing
gates settle before publication, personal schedules, and payroll input. Swaps depend on stable
published-roster versioning. The independent review runs after every attendance and roster cutover
is stable.
