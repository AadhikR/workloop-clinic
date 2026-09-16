# Part 9A financial contract

## Authority and common HTTP rules

PostgreSQL is authoritative. FastAPI derives company, selected branch, actor, employee identity,
business date, state, and calculated money. A browser total is a preview and never becomes a stored
total without server recomputation.

All routes use the Phase 6 JSON, error, pagination, idempotency, and conditional-write rules. Money
is a JSON string with exactly two decimal places. Dates are `YYYY-MM-DD`, instants are UTC RFC 3339,
and payroll periods are `YYYY-MM`. Optional fields appear as `null`; projections do not omit them.
List routes accept `limit` from 1 through 100, default 50, and an opaque `cursor`. The response is
`{ "items": [...], "nextCursor": string | null }`.

Mutation requests reject unknown fields. Protected commands require `Idempotency-Key`. Mutable-row
commands also require `expectedUpdatedAt`, or `expectedVersion` when the projection names a numeric
version. Reusing a key with the same canonical payload returns the first response. Reusing it with a
different payload returns `409 idempotency_key_reused`. A stale state or version returns
`409 stale_financial_state`. Missing and inaccessible records both return the Phase 6 safe `404`.

The default selected branch comes from the trusted request context. Administrators can operate only
on that branch. Managers can access only the expense queue for current direct reports in that branch.
Employees can access only their own expense claims, advance requests, and payslips. Managers receive
no payroll, advance, salary, bank, WPS, or payslip data.

## Trusted dates and money

The database function `public.workloop_business_date()` supplies the UAE business date for commands.
The period identifies the calendar month in that date system. A new run may target the current month
or a past month. A future period is rejected.

`paymentDate` is required when a run is created. It must fall between the first day of the payroll
period and 31 days after that period ends. The default is the branch `default_salary_day` in the
payroll month, capped at the month's last day. An administrator may override it inside that range.
Changing it refreshes WPS-derived preview values and is forbidden after submission.

FastAPI uses `Decimal` and PostgreSQL `NUMERIC`. It rejects exponent notation, non-finite values,
more than two input decimal places, negative unsigned amounts, and values outside the destination
column. Intermediate rates keep decimal precision. The calculator rounds each persisted component
with `ROUND_HALF_UP` to two places, then calculates aggregates as sums of those rounded components.
It rounds WPS basic and variable pay independently to integer AED with `ROUND_HALF_UP`. The SIF total
is the sum of the emitted integer values, not a separately rounded net amount.

The only signed persisted payroll component is `variableAllowance`. Manual allowance and deduction
amounts are nonnegative. Their list decides the sign. `increment`, `bonus`, `otherPay`, expense
reimbursement, overtime, and roster overtime add to pay. Named deductions, `leaveDeduction`,
attendance deductions, and advance repayment subtract from pay. The legacy `duCost` input is accepted
only by the cutover converter and maps to `leaveDeduction`. Public APIs reject `duCost`.

The accepted manual adjustment object is:

```json
{
  "id": "UUID",
  "code": "UPPER_SNAKE_CASE",
  "label": "1 to 80 characters",
  "amount": "0.00",
  "recurrence": "one_time or recurring",
  "note": "string or null"
}
```

Codes must be unique within the employee entry and must not use the reserved prefixes `AUTO_`,
`LEAVE_`, `ATTENDANCE_`, `ROSTER_`, `EXPENSE_`, or `ADVANCE_`. Automatic items carry server-only
`sourceType`, `sourceId`, `sourceVersion`, and calculation inputs in the immutable source snapshot.

## Salary snapshot and employment eligibility

A draft refresh reads the employee salary and employment fields current at refresh time. It stores
the values and source fingerprint in `payroll_entries.source_snapshot`. Submission freezes that
snapshot. Approval and generation compare its employee, leave, expense, advance, attendance, and
roster versions with the current sources. Any difference blocks the transition until an
administrator recalls and refreshes the run.

Eligibility uses inclusive dates. An employee whose join date is after the period end is excluded.
An employee whose termination date is before the period start is excluded. Otherwise each fixed
salary component is prorated by `eligible calendar days / actual calendar days in the period`.
Eligible days start on the later of period start and join date, and end on the earlier of period end
and termination date. Basic, housing, transport, and fixed allowance are rounded separately. Manual
and automatic adjustments are not prorated unless their own source contract defines a period share.

An excluded employee has no payroll entry. An employee excluded during refresh but present in a
submitted snapshot causes a stale-source error. A draft may show a negative-net blocking error, but
submit, approve, and generate reject it. Every issued payslip has `netPay >= 0.00`.

## Expense routes and projections

| Method and path | Role | Contract |
| --- | --- | --- |
| `GET /api/v1/expenses/self` | Employee | Own claims. Filters `status`, `fromDate`, `toDate`. Sort `expenseDate desc, createdAt desc, id desc`. |
| `POST /api/v1/expenses/self` | Employee | Create a pending claim. Body has `category`, `amount`, `expenseDate`, `description`, and optional `receiptId`. |
| `DELETE /api/v1/expenses/self/{claimId}` | Employee | Delete only own `pending`, `manager_rejected`, or `rejected` claim before payroll use. |
| `GET /api/v1/expenses/manager-queue` | Manager | Current direct reports only. Filters `status`, `employeeId`, `fromDate`, `toDate`. Sort oldest pending first. |
| `POST /api/v1/expenses/{claimId}/manager-approve` | Manager | `pending` to `manager_approved`. Owner cannot decide. |
| `POST /api/v1/expenses/{claimId}/manager-reject` | Manager | `pending` to `manager_rejected`; `reason` is 1 through 500 characters. |
| `GET /api/v1/expenses` | Administrator | Selected-branch queue. Filters `status`, `employeeId`, `fromDate`, `toDate`. Sort `expenseDate desc, id desc`. |
| `POST /api/v1/expenses/{claimId}/approve` | Administrator | `pending`, `manager_approved`, `manager_rejected`, or `rejected` to `approved`. Owner cannot decide. Overriding manager rejection requires `reason`. |
| `POST /api/v1/expenses/{claimId}/reject` | Administrator | `pending` or `manager_approved` to `rejected`; `reason` is required. |
| `DELETE /api/v1/expenses/{claimId}` | Administrator | Delete only before approval and before any payroll reference. |

The employee projection contains `id`, `category`, `amount`, `expenseDate`, `description`, `status`,
`rejectionReason`, `hasReceipt`, `payrollPeriod`, `createdAt`, and `updatedAt`. It never exposes actor
IDs or receipt keys. Manager and administrator projections add `employeeId`, `employeeName`,
`managerDecisionAt`, `adminDecisionAt`, and `canDecide`. The administrator projection may include
decision actor display names, not raw audit rows.

Manager preapproval is optional. The final administrator actor must differ from a manager actor when
a manager decision exists. A claim becomes `paid` only inside 9F finalization when its approved
automatic reimbursement belongs to a non-excluded generated entry. It cannot be paid manually.

## Receipt boundary

9B may reuse the Phase 8 private-storage interface and outbox. It does not choose the Phase 11
production provider or claim that backup and recovery work is complete.

The receipt routes mirror the leave attachment flow:

| Method and path | Role | Contract |
| --- | --- | --- |
| `POST /api/v1/expenses/receipt-submissions` | Employee or administrator | Create one 15-minute upload intent in the selected branch. Returns a token once. |
| `POST /api/v1/expenses/receipt-submissions/{submissionId}/file` | Intent owner | Upload one raw file, at most 10 MiB in a request capped at 12 MiB. |
| `POST /api/v1/expenses/receipts/{receiptId}/download` | Claim owner, current direct manager, or selected-branch administrator | Return a five-minute signed private download after current authorization. |

The server accepts detected PDF, PNG, and JPEG only. It compares magic bytes with the declared media
type, records byte count and SHA-256, generates an opaque keyed object path, and never returns the
path. One receipt may bind to one claim. A staged object expires after 24 hours. Deletion or failed
binding writes durable cleanup intent in the same database transaction. The storage operation then
deletes the object and marks the outbox item complete. Phase 11 must include these rows and objects
in common recovery proof.

## Advance routes and projections

| Method and path | Role | Contract |
| --- | --- | --- |
| `GET /api/v1/advances/self` | Employee | Own advances, newest first. Optional `status`. |
| `POST /api/v1/advances/self` | Employee | Request a pending advance with `amount`, `reason`, `installmentCount`, and `repaymentStartPeriod`. |
| `POST /api/v1/advances/self/{advanceId}/withdraw` | Employee | Own `pending` to `cancelled`; reason recorded as employee withdrawal. |
| `GET /api/v1/advances` | Administrator | Selected branch. Filters `status`, `employeeId`, and start period. |
| `POST /api/v1/advances` | Administrator | Create for a selected-branch employee. The creator cannot decide the request. |
| `POST /api/v1/advances/{advanceId}/approve` | Administrator | `pending` to `active`. Locks the schedule. Owner and creator cannot approve. |
| `POST /api/v1/advances/{advanceId}/reject` | Administrator | `pending` to `cancelled`; `reason` required. Owner and creator cannot reject. |
| `PUT /api/v1/advances/{advanceId}/schedule` | Administrator | Replace amount, count, or start period only while pending. |
| `POST /api/v1/advances/{advanceId}/repayments` | Administrator | Record a positive manual repayment no greater than balance. |
| `POST /api/v1/advances/{advanceId}/settle` | Administrator | Record the exact remaining balance and set `settled`. |

The employee projection contains `id`, `amount`, `reason`, `status`, `repaymentStartPeriod`,
`installmentCount`, `monthlyInstallment`, `outstandingBalance`, `nextRepaymentPeriod`,
`rejectionReason`, `createdAt`, and `updatedAt`. The administrator projection adds employee identity,
creator display name, decision display name, schedule rows, and repayment rows. It does not expose
payroll entries outside the repayment reference and period.

An installment schedule divides the amount by count with half-up cents. Each installment except the
last uses that rounded amount. The last equals the exact remaining balance. Periods advance by
calendar month. A payroll refresh selects the oldest due unpaid installments by scheduled period,
then advance creation time, then advance ID. It never deducts more than the remaining balance or the
entry's nonnegative pay capacity. Finalization records one repayment for an advance and payroll run.
Manual repayment and finalization lock the advance and use `record_advance_repayment`.

## Payroll draft and input routes

| Method and path | Role | Contract |
| --- | --- | --- |
| `GET /api/v1/payroll-runs` | Administrator | Filters `period`, run status, approval status. Sort `period desc, sequence desc, id desc`. |
| `POST /api/v1/payroll-runs` | Administrator | Create one selected-branch draft for `period` and `paymentDate`. |
| `GET /api/v1/payroll-runs/{runId}` | Administrator | Strict run, entry, source-warning, and validation projection. |
| `POST /api/v1/payroll-runs/{runId}/repeat` | Administrator | Create the next requested draft from recurring manual adjustments only. |
| `POST /api/v1/payroll-runs/{runId}/refresh` | Administrator | Rebuild employee and automatic-input snapshots. Draft only. |
| `PUT /api/v1/payroll-runs/{runId}/entries` | Administrator | Replace every entry after server recomputation. Draft only. |
| `DELETE /api/v1/payroll-runs/{runId}` | Administrator | Delete a draft with no approval history, payslip, WPS row, or applied source. |

The run projection contains `id`, `period`, `paymentDate`, `sequence`, `runStatus`, `approvalStatus`,
`employeeCount`, `totalAmount`, `validationStatus`, `blockingErrors`, `sourceWarnings`, `createdAt`,
and `updatedAt`. Each entry contains employee identity, fixed components, variable components,
deductions, gross, total deductions, net, WPS basic, WPS variable, exclusion state, manual
adjustments, source explanations, and its source fingerprint. It excludes IBAN, government ID, and
raw audit fields.

`replace_payroll_entries` remains the sole entry replacement function. FastAPI first locks the run,
validates scope and draft state, recomputes every entry, rejects duplicate employees and unknown
adjustments, and then calls the function in the same transaction. Run totals are recomputed from the
stored entries.

### Read-only Phase 10 inputs

9E consumes repository projections, not public mutation routes. The attendance projection is
identified by company, branch, period, `status=closed`, and `payrollReady=true`. It includes
`sourceVersion`, `closedAt`, and employee rows with `employeeId`, absence days and amount, late
minutes and amount, approved standard overtime hours and amount, approved rest-day overtime hours
and amount, and the source row IDs.

The roster projection is identified by company, branch, period, `status=published`. It includes
`sourceVersion`, `publishedAt`, and employee rows with `employeeId`, actual hours, approved overtime
hours and amount, and source row IDs. Provisional, open, missing, mixed-branch, or changed projections
block approval. Until Phase 10 implements these exact projections, 9E reports
`409 payroll_input_not_ready`; it never substitutes a browser or Supabase result.

The Phase 8 leave projection must identify approved requests and the deduction source version. The
expense projection selects approved, unpaid, unlinked claims in the period. The advance projection
selects active due installments. Refresh locks sources in the fixed order leave, attendance, roster,
expense, then advance. Refresh replaces automatic items by source identity and leaves manual items
unchanged.

## Approval, generation, and payslip routes

| Method and path | Role | Contract |
| --- | --- | --- |
| `POST /api/v1/payroll-runs/{runId}/submit` | Administrator | Draft to pending approval after complete validation. |
| `POST /api/v1/payroll-runs/{runId}/recall` | Administrator | Pending approval to draft. Submitter or another administrator may recall before approval. Reason required. |
| `POST /api/v1/payroll-runs/{runId}/approve` | Administrator | Pending approval to approved. Actor must differ from creator and submitter. |
| `POST /api/v1/payroll-runs/{runId}/reject` | Administrator | Pending approval to draft with rejection history. Actor must differ from submitter; reason required. |
| `POST /api/v1/payroll-runs/{runId}/generate` | Administrator | Approved draft to generated. It cannot alter approval evidence. |
| `GET /api/v1/payroll-runs/{runId}/approval-history` | Administrator | Ordered safe history with display names and reasons. |
| `GET /api/v1/payslips/self` | Employee | Own immutable payslips, period descending. |
| `GET /api/v1/payslips/self/{payslipId}` | Employee | Own immutable snapshot. |

The synthetic environment must contain two administrators in the same company and branch. The same
person cannot create and approve, or submit and approve, a run. Generation may be performed by any
selected-branch administrator after approval, including the approver. It rechecks the approved
snapshot and writes generated state, payslips, expense links, expense paid states, repayments, run
totals, audit events, and idempotency result in one transaction.

The payslip projection contains period, payment date, employee display fields, rounded earning and
deduction lines, gross, total deductions, net, WPS values, and issued timestamp. It excludes bank
account, government identifiers, actor IDs, mutable source IDs, and raw audit data. It has no update
or delete route.

## WPS, SIF input, compliance, and Nafis

| Method and path | Role | Contract |
| --- | --- | --- |
| `GET /api/v1/payroll-runs/{runId}/wps` | Administrator | WPS run and entry projection for a generated run. |
| `POST /api/v1/payroll-runs/{runId}/wps/sif-generated` | Administrator | `draft` to `sif_generated`. Records projection digest, not file bytes. |
| `POST /api/v1/payroll-runs/{runId}/wps/submit` | Administrator | `sif_generated` to `submitted`. |
| `POST /api/v1/payroll-runs/{runId}/wps/confirm` | Administrator | `submitted` or `partial_rejection` to `confirmed` when all entries are paid. |
| `POST /api/v1/payroll-runs/{runId}/wps/fail` | Administrator | Nonconfirmed state to `failed`; reason required. |
| `POST /api/v1/payroll-runs/{runId}/wps/entries/{entryId}/paid` | Administrator | Pending entry to paid. |
| `POST /api/v1/payroll-runs/{runId}/wps/entries/{entryId}/reject` | Administrator | Pending entry to rejected; reason required; run becomes partial rejection. |
| `GET /api/v1/payroll-runs/{runId}/sif-input` | Administrator | Deterministic full EDR projection. |
| `GET /api/v1/payroll-runs/{runId}/sif-input?correction=rejected` | Administrator | Rejected entries only. |
| `POST /api/v1/payroll-runs/{runId}/compliance-overrides` | Administrator | Append a reasoned immutable override for an approved code. |
| `GET /api/v1/nafis-snapshots` | Administrator | Selected branch, optional period. |
| `PUT /api/v1/nafis-snapshots/{period}` | Administrator | Generate or replace one trusted branch-period snapshot. |

WPS run states are `draft`, `sif_generated`, `submitted`, `confirmed`, `partial_rejection`, and
`failed`. Entry states are `pending`, `paid`, and `rejected`. A rejected entry can return to pending
only when a corrected SIF projection has been recorded with a new digest. A confirmed run cannot
change. Every transition uses a locked state check and audit event.

The SIF input projection is ordered by employee MOL identifier, then payroll entry ID. Its header
contains employer MOL ID, branch routing code, period start and end, payment date, employee count,
and the sum of emitted integer pay. Each EDR row contains employee MOL ID, bank routing code, IBAN,
period start and end, paid days, integer basic pay, integer variable pay, and integer total. This
projection is administrator-only and `Cache-Control: no-store`. Phase 12 converts it to CRLF file
bytes and owns download authorization.

Compliance overrides use a closed code set established by 9G, a 1 through 500 character reason,
trusted actor, timestamp, and target run or entry. They cannot be updated or deleted. A corrected
projection includes only rejected entries and keeps the original finalized pay values.

The Nafis snapshot uses trusted company and employee data as of the payroll period end. It records
source version, Emirati employee count, qualifying wage inputs, period, branch, calculation result,
and generated timestamp. Report layout, export, scheduling, and notification remain in Phase 12.

## Cutover and rollback

The six cutover units are expenses; advances and repayments; payroll drafts and calculations;
payroll inputs; payroll approval and payslips; and WPS and Nafis. Each starts with the legacy path as
the read and write authority and the migration path frozen. A later part may switch one unit only
after its focused proof passes. Dual writes are forbidden.

Rollback reverses the dependency order: WPS and Nafis, approval and payslips, payroll inputs,
payroll drafts, advances and repayments, then expenses. Disable the migration writer before
restoring the legacy writer. Generated payrolls, payslips, repayments, paid expenses, submitted WPS
history, and immutable audit rows remain preserved during rollback.
