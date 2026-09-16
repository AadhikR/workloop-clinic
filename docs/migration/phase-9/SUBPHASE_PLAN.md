# Phase 9 subphase plan

## Status

Phase 8 is complete at commit `2f4956b9ac356e979140ae4be0163017324e9aa4`. GitHub Migration
foundation run `35006999072` passed on 2026-09-15. Parts 9A through 9C are complete, Phase 9D is
authorized next, and Alembic has one head at `a1c3e5f7b9d2`.

This document splits Phase 9 into eight parts, 9A through 9H. The project owner authorized sequential
execution on 2026-09-16. Only the next part may run after the prior part has a clean, synchronized
branch and a passing routed GitHub workflow.

## Why Phase 9 needs subphases

Payroll combines money calculations, employee salary data, leave and attendance inputs, approval,
immutable payslips, debt repayment, expense reimbursement, and WPS state. The legacy browser owns
many calculations and performs several related writes separately. A single cutover would make one
rollback responsible for every financial workflow.

Phase 9 therefore settles claims and advances before payroll consumes them. It separates editable
draft calculation from approval and finalization. WPS and Nafis projections come after the immutable
payroll result exists. The last part reviews the whole boundary independently.

## Starting point

- Phase 4 supplies the canonical payroll, payslip, approval-log, Nafis, salary-advance,
  advance-repayment, expense-claim, and compliance-override tables.
- Phase 4 also supplies the protected `replace_payroll_entries` and `record_advance_repayment`
  functions.
- Phase 5 supplies branch, employee-self, direct-report, workflow, history, RLS, grant, and
  protected-function boundaries for the financial tables.
- Phase 6 supplies the HTTP, idempotency, error, pagination, and frontend-client conventions.
- Phase 7 supplies trusted branch, employee, salary, bank, MOL, IBAN, WPS, nationality, and
  employment data.
- Phase 8 supplies approved-leave projections and server-owned leave deductions.
- The migration build has no payroll, advance, expense, payslip, WPS, SIF, or Nafis screen yet.
- The legacy payroll path is concentrated in `src/utils/storage.js`,
  `src/utils/payrollCalculator.js`, `src/utils/payrollValidation.js`,
  `src/utils/advanceSchedule.js`, `src/utils/expenseStorage.js`,
  `src/utils/sifGenerator.js`, `src/utils/sifCompliance.js`, and the matching React components.

## Part status

| Part | Scope | Status |
| --- | --- | --- |
| 9A | Financial contracts, dependency inventory, golden cases, and cutover decisions | Complete |
| 9B | Expense claims, manager review, administrator decisions, and receipt boundary | Complete |
| 9C | Salary advances, schedules, withdrawal, decisions, and repayment authority | Complete |
| 9D | Payroll drafts, entries, server calculation, validation, and editable-run lifecycle | Authorized next; not started |
| 9E | Leave, attendance, roster, expense, and advance payroll inputs | Authorized in sequence; not started |
| 9F | Payroll approval, finalization, immutable payslips, and financial audit | Authorized in sequence; not started |
| 9G | WPS state, SIF input projection, compliance overrides, and Nafis snapshots | Authorized in sequence; not started |
| 9H | Independent review, complete cutover proof, and Phase 9 gate | Authorized in sequence; not started |

## Rules shared by every part

- Use synthetic local data only. Production data, real employee or banking data, paid services,
  cloud resources, and legal-policy decisions need separate project-owner authorization.
- PostgreSQL remains authoritative for company, branch, employee, salary, bank, payroll, claim,
  advance, repayment, approval, payslip, WPS, and compliance state.
- The server derives the trusted company, selected branch, actor, employee, business date, payroll
  period, workflow state, and calculated money. Browser fields grant no authority.
- Use `Decimal` and PostgreSQL `NUMERIC` for money. Reject binary floating-point persistence,
  non-finite values, excess scale, excess precision, and totals that violate database bounds.
- Every mutation has one transaction owner. A failed or stale command leaves the run, entries,
  claim, advance, repayment, payslip, domain history, protected audit, and idempotency state
  unchanged wherever the operation touches them.
- Protected commands use the Phase 6 idempotency contract. The same key and payload return the
  original result. A changed payload fails.
- Mutable rows use a locked state check and an expected version or timestamp. Concurrent commands
  cannot reimburse twice, repay twice, replace approved entries, or finalize twice.
- The server writes actor IDs and timestamps from trusted context. Request bodies cannot assign
  approval actors, audit actors, company IDs, branch IDs, employee owners, or final states.
- Employees receive immutable payslip projections, not payroll-run or payroll-entry access.
  Managers receive only the expense queue approved in 9A. They receive no team payroll detail.
- Responses use strict camelCase projections and safe missing-or-inaccessible errors. They do not
  expose bank details, government identifiers, raw audit rows, receipt object keys, or another
  employee's financial data outside the exact approved response.
- Every cutover record names one read authority, one write authority, a frozen opposite path, and
  rollback order. Dual writes are forbidden.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks while developing, run one
  boundary-matched local gate after each part settles, push once, and wait for every routed GitHub
  job.

## Cross-phase boundaries

Phase 9 owns expense and advance workflows, payroll calculation and state, payroll approval,
payslip snapshots, application of approved financial inputs, WPS tracking, SIF input projections,
and Nafis snapshots.

The following owners remain unchanged:

- Phase 10 owns attendance records, overtime approval, absence and late deductions, roster actual
  hours, and payroll-ready period closure. Phase 9 may consume approved, closed projections. It must
  not create or repair Phase 10 source state.
- Phase 11 owns the common production object-storage adapter and full receipt recovery. Phase 9A
  must approve a bounded use of the existing private-storage contract or defer receipt upload.
- Phase 11 owns gratuity, final settlement, offboarding deductions, and advance handling during
  offboarding.
- Phase 12 owns notification delivery, tasks, dashboards, reports, CSV, PDF, ZIP, and SIF file
  generation or download. Phase 9 may expose strict inputs and persisted snapshots only.
- Phase 13 owns final removal of Supabase and the legacy build.

No Phase 9 route may call Supabase. A later-phase source may remain in the legacy build, but a
migration payroll flow must use a named FastAPI projection or fail closed.

## 9A: Financial contracts, inventory, and cutover decisions

### Objective

Resolve financial behavior and authority before adding a route or changing a writer.

### Scope

- Inventory every legacy payroll, payslip, WPS, SIF, Nafis, advance, repayment, expense, receipt,
  converter, calculator, validator, RPC, storage path, task, report, and notification dependency.
- Trace every caller to Phase 9 or to an explicit Phase 10, 11, or 12 owner.
- Define strict request and response contracts for administrators, managers, and employees. Record
  filters, sort order, pagination, nulls, dates, decimals, redaction, and safe errors.
- Approve the payroll period format, trusted UAE business date, payment-date rule, salary snapshot
  date, joiner and leaver proration, rounding points, adjustment signs, exclusion behavior, and
  negative-net-pay handling.
- Reconcile the legacy `duCost` alias with canonical `leave_deduction`. Define the only accepted
  adjustment keys and metadata. Browser-computed totals remain previews.
- Review every synthetic golden case. Fix exact expected inputs and results for normal payroll,
  allowances, deductions, leave, attendance, roster overtime, expense reimbursement, advance
  repayment, mid-period employment, compliance override, WPS rounding, and SIF input rows.
- Decide payroll approval separation of duties. The current roles provide one administrator role,
  while the legacy UI lets that actor submit, approve, and generate the same run.
- Define expense and advance transitions, self-action restrictions, manager scope, administrator
  decisions, required reasons, repayment order, early settlement, and payroll application rules.
- Decide the receipt boundary with Phase 11. Record file limits, detected content types, signing,
  authorization, metadata, cleanup, and recovery if Phase 9 may reuse the private adapter.
- Define read-only Phase 10 input contracts. A closed payroll-ready attendance period and approved
  overtime or published roster values must be distinguishable from provisional data.
- Define WPS run and entry transitions, correction rules, SIF projection fields, compliance
  overrides, and Nafis snapshot inputs. File generation and downloads stay in Phase 12.
- Prepare proposals for any missing protected audit action, function, role, grant, RLS policy,
  constraint, index, or immutable-snapshot field. Do not create an Alembic revision before the
  project owner approves the exact proposal.
- Prepare separate cutover records for expenses, advances and repayments, payroll drafts and
  calculations, payroll approval and payslips, payroll inputs, and WPS and Nafis.

### Completion gate

The inventory accounts for every financial dependency. Every route and workflow has an exact role,
scope, calculation, transaction, idempotency, concurrency, audit, error, cutover, and rollback
contract. The receipt, Phase 10 input, approval-separation, and compliance decisions have no open
question.

### Rollback boundary

9A changes documents only. Revert its documents if the contract is rejected. It permits no runtime,
schema, storage, or cutover change.

## 9B: Expense claims and approvals

### Objective

Move expense submission and decisions before payroll can reimburse a claim.

### Scope

- Add employee self submission and self reads. Derive the employee from the principal and validate
  category, amount, expense date, description, and optional receipt binding on the server.
- Add direct-manager queues from the current reporting relationship. A manager may approve or
  reject only a current direct report under the approved transition table.
- Add selected-branch administrator queues and final approval or rejection. Require the exact
  reasons approved in 9A.
- Permit employee deletion only in the approved nonfinal states. Permit administrator deletion only
  under the Phase 5 matrix and only before retained payroll use.
- If 9A authorizes receipt work, use the private storage interface. Generate opaque object keys,
  authorize each upload and download, and record durable cleanup intent. Do not store a browser URL
  as authority.
- Add migration employee, manager, and administrator expense views. Do not add reimbursement or
  notification delivery yet.
- Freeze the matching legacy claim and decision paths only after the expense cutover passes.

### Completion gate

Self, direct-report, branch, state, amount, receipt, stale-command, idempotency, and concurrency
tests pass. Every allowed decision changes the claim, domain history if approved, protected audit,
and idempotency state together. No claim can be approved, rejected, deleted, or viewed outside its
scope.

### Rollback boundary

Disable migration expense mutations before restoring legacy writers. Preserve final claims and
their audit history. Reconcile only receipt objects proven orphaned by the approved operation
record.

## 9C: Salary advances and repayments

### Objective

Move advance requests and debt accounting before payroll applies a scheduled installment.

### Scope

- Add employee self request, read, and pending withdrawal. Derive employee and branch identity from
  the principal.
- Add selected-branch administrator list, creation, approval, rejection, schedule update, manual
  repayment, and settlement commands under the 9A transition contract.
- Calculate repayment start month, installment count, monthly deduction, outstanding balance, and
  final installment with decimal arithmetic. Keep settled and cancelled history immutable.
- Use `record_advance_repayment` only after FastAPI locks and validates the advance, optional
  payroll run, scope, state, amount, remaining balance, and idempotency key.
- Prove one repayment per advance and payroll run. A retry cannot reduce the balance twice.
- Add migration employee and administrator advance views. Do not add offboarding settlement work.
- Freeze legacy advance and repayment paths only after the cutover passes.

### Completion gate

Pending, active, settled, and cancelled cases pass. Schedule boundaries, partial final installments,
manual repayment, early settlement, withdrawal, rejection, stale commands, concurrent repayment,
cross-branch access, and exact balance reduction are proven.

### Rollback boundary

Disable migration repayment and advance mutations before restoring legacy writers. Preserve all
repayment rows and settled history. Payroll rollback must stop creating repayments before this unit
rolls back.

## 9D: Payroll drafts and server calculation

### Objective

Make FastAPI authoritative for editable payroll runs and calculated entries.

### Scope

- Add selected-branch administrator list, detail, create, repeat, refresh, save, and guarded draft
  delete operations.
- Enforce one run per branch and period. Derive branch scope, employee population, salary values,
  payment date, sequence, routing code, and run actor from trusted data.
- Port the approved calculator and validators to server-owned decimal code. Validate named
  allowances and deductions, recurrence, source metadata, bounds, exclusions, and net pay.
- Treat browser calculations as previews. FastAPI recomputes and compares every persisted entry and
  run total.
- Call `replace_payroll_entries` inside the authorized transaction after strict request validation.
  Unknown keys, duplicate employees, stale versions, non-draft state, and mixed scope abort the
  whole replacement.
- Repeat only the approved recurring manual items. Do not copy one-time or automatic adjustments
  from the prior run.
- Add the migration payroll list and editable draft view. Approval, finalization, payslips, WPS,
  files, exports, and notifications remain disabled.
- Freeze legacy draft writers only after the draft cutover passes.

### Completion gate

All approved golden calculations match to two decimals. Create, repeat, refresh, replace, and delete
are branch-scoped, idempotent, and concurrency-safe. An invalid employee or adjustment leaves the
run and every entry unchanged.

### Rollback boundary

Disable migration draft writes before restoring the legacy draft writer. Approval and finalization
must roll back first because they consume migration-calculated entries.

## 9E: Payroll input integration

### Objective

Apply approved leave, expense, advance, attendance, and roster inputs without letting those source
domains mutate payroll directly.

### Scope

- Consume Phase 8 approved leave through its scoped server projection and calculate the approved
  payroll deduction without reading legacy leave state.
- Consume approved unpaid expenses and active in-period advance installments under row locks. Add
  deterministic automatic adjustments that retain source IDs and periods.
- Consume only the Phase 10 input states approved in 9A. Closed payroll-ready attendance may supply
  absence, late, and approved overtime values. Published roster actual hours may supply its approved
  overtime value.
- If Phase 10 has not produced an approved source projection, fail closed for that automatic input.
  Do not call Supabase, infer provisional values in the browser, or mark the missing input as final.
- Keep manual and automatic adjustments separate. Refreshing automatic inputs must not erase valid
  manual items or duplicate a source item.
- Lock sources in deterministic order. Record their IDs, versions, and calculation result so an
  approval attempt can detect changed inputs.
- Add source explanations and blocking warnings to the migration payroll editor. Do not add Phase 10
  mutation controls.

### Completion gate

The integrated golden case produces exact leave, expense, advance, attendance, roster, gross, total
deduction, net, and WPS variable values. Refresh is repeatable. Changed or provisional source data
blocks approval, and cross-branch source rows never affect the run.

### Rollback boundary

Stop migration input refresh before rolling back expenses, advances, or payroll drafts. Restore a
legacy input reader only after its payroll writer is the sole active writer.

## 9F: Approval, finalization, payslips, and audit

### Objective

Move the locked payroll lifecycle and issue immutable employee payslips.

### Scope

- Add submit, recall, approve, reject, and generate commands under the 9A transition and actor
  rules.
- Before every transition, lock and recheck the run, entries, employee eligibility, source versions,
  approval state, totals, and required validation results.
- Append `submitted`, `recalled`, `approved`, and `rejected` payroll history with trusted actors and
  required notes. Add protected audit actions only if 9A approved them.
- Finalization writes the generated run state, aggregate totals, immutable payslip snapshots,
  advance repayments, and applied expense links in one database transaction.
- Mark an expense paid only when its automatic reimbursement belongs to a non-excluded finalized
  entry. Record each advance repayment exactly once.
- Expose strict administrator approval history and employee self payslip projections. Payslip rows
  have no update or delete path.
- Add migration approval controls and employee payslip screens. Leave PDF, ZIP, and notification
  production to Phase 12.
- Freeze legacy approval, finalization, repayment-application, expense-payment, and payslip writers
  only after their cutover records pass.

### Completion gate

Allowed transitions, required reasons, actor separation, changed-source rejection, stale commands,
same-key replay, changed-payload conflict, concurrent finalization, expense application, repayment,
totals, history, audit, and immutable payslips pass. Employees can read only their own snapshots.

### Rollback boundary

Disable migration approval and finalization before restoring legacy writers. Preserve generated
runs, payslips, repayments, expense links, and approval history. Roll back this unit before payroll
inputs, drafts, advances, or expenses.

## 9G: WPS, SIF inputs, compliance, and Nafis

### Objective

Move post-finalization compliance state while leaving file generation and reports with Phase 12.

### Scope

- Add WPS run transitions for `draft`, `sif_generated`, `submitted`, `confirmed`,
  `partial_rejection`, and `failed`. Add entry transitions for `pending`, `paid`, and `rejected`.
- Derive MOL ID, routing code, IBAN, period, payment date, days, basic pay, variable pay, employee
  count, and total from trusted finalized snapshots.
- Expose a strict SIF input projection with deterministic ordering and exact integer-AED rounding.
  Phase 12 will turn that projection into CRLF file bytes and downloads.
- Add corrected-SIF input filtering for rejected entries. Require a reason for every rejected entry.
- Append reasoned compliance overrides under the approved tenant or branch scope. Keep them
  immutable.
- Generate or replace one Nafis snapshot per branch and period from trusted employee and company
  data. Do not schedule generation or build dashboards.
- Add migration WPS tracking, SIF preview data, compliance-override, and Nafis snapshot views. Do
  not generate downloadable files or notifications.
- Freeze matching legacy state writers only after WPS and Nafis cutovers pass.

### Completion gate

WPS transition, entry-state, correction, scope, concurrency, compliance-override, and Nafis tests
pass. The SIF golden projection has the exact EDR values, count, total, order, and rounding expected
by the later Phase 12 generator.

### Rollback boundary

Disable migration WPS, compliance, and Nafis mutations before restoring legacy writers. Preserve
submitted and confirmed history. Roll back 9G before payroll finalization.

## 9H: Independent review and completion gate

### Objective

Prove the complete Phase 9 boundary before requesting Phase 9 signoff.

### Scope

- Review authorization, decimal arithmetic, trusted dates, salary and bank disclosure, transaction
  ownership, RLS, grants, protected functions, optimistic locking, idempotency, receipt access,
  audit coverage, error disclosure, and rollback independently of the implementation passes.
- Trace every 9A inventory entry to a migrated route, an explicit Phase 10 through 12 owner, or a
  deliberately retained legacy dependency.
- Validate all cutover records, freeze guards, single-writer declarations, receipt cleanup, and
  reverse dependency rollback order.
- Prove every reviewed financial golden case with exact intermediate values, not only final totals.
- Run one complete boundary-matched local Phase 9 gate in a fresh isolated environment.
- Prove append-only migration history, empty-schema replay, repeatable current-head upgrade, and
  exact predecessor restoration for each Phase 9 revision.
- Restart existing images without rebuilding. Compare database, Keycloak signing-key, and synthetic
  storage state. Run the complete payroll, expense, advance, payslip, WPS, and Nafis browser journey
  once after the final restart.
- Remove synthetic rows, objects, credentials, containers, networks, and temporary volumes. Do not
  attach or modify `workloop-clinic_postgres_data`.
- Push the settled Phase 9 changes once and require every routed GitHub job before requesting owner
  signoff.

### Completion gate

Focused suites and the complete local gate pass. Every Phase 9 feature has one read and write
authority. Migration financial code has no Supabase path. Golden values, restart, rollback, cutover,
and cleanup proofs pass. GitHub passes and the project owner signs off Phase 9.

### Rollback boundary

Use the cutover records in reverse order. Roll back WPS and Nafis first, then approval and payslips,
payroll inputs, payroll drafts, advances and repayments, and expenses. Never restore a legacy writer
while its FastAPI counterpart remains writable.

## Recommended execution order

Execute `9A -> 9B -> 9C -> 9D -> 9E -> 9F -> 9G -> 9H`.

Expenses and advances settle before payroll reads them. Draft calculation settles before automatic
inputs. Approval and immutable payslips depend on both. WPS and Nafis depend on finalized payroll.
The independent review runs after every financial cutover is stable.
