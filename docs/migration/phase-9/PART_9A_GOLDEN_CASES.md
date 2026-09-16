# Part 9A financial golden cases

## Test conventions

All people and account values in these cases are synthetic. Unless a case says otherwise, the branch
is `DXB-MAIN`, the period is `2026-08`, the employee is active for the whole period, and inputs are
ready and unchanged. Money uses half-up rounding. Persisted components round to cents before totals.

The two synthetic administrators are `Admin A` and `Admin B`. They belong to the same company and
selected branch. They are different principals.

## Payroll calculation cases

### PAY-01 integrated normal payroll

| Component | Input | Expected stored value |
| --- | ---: | ---: |
| Basic | 12000.00 | 12000.00 |
| Housing | 3000.00 | 3000.00 |
| Transport | 1000.00 | 1000.00 |
| Fixed allowance | 500.00 | 500.00 |
| Bonus | 1000.00 | 1000.00 |
| Approved expense reimbursement | 350.00 | 350.00 |
| Published roster overtime | 288.46 | 288.46 |
| Advance repayment | 500.00 | 500.00 deduction |
| Approved leave deduction | 400.00 | 400.00 deduction |

Expected fixed pay is `16500.00`. Expected variable pay is `1638.46`. Expected gross pay is
`18138.46`. Expected total deductions are `900.00`. Expected net pay is `17238.46`. Expected WPS
basic pay is `12000.00`; expected WPS variable pay is `5238.46`.

### PAY-02 named manual adjustments and recurrence

Start with fixed pay `10000.00`. Add recurring `SHIFT_ALLOWANCE=250.25` and one-time
`PROJECT_BONUS=499.75`. Subtract recurring `PARKING=100.00` and one-time `EQUIPMENT=50.00`.

Expected gross is `10750.00`, deductions are `150.00`, and net is `10600.00`. Repeating this run
copies `SHIFT_ALLOWANCE` and `PARKING` only. The repeated entry has gross `10250.25`, deductions
`100.00`, and net `10150.25` before automatic inputs refresh.

### PAY-03 legacy `duCost` conversion

The cutover converter receives `duCost=225.00` and no `leaveDeduction`. It writes
`leaveDeduction=225.00` and records the legacy source name in conversion evidence. If both names are
present, or a public API request contains `duCost`, validation fails. No entry changes.

### PAY-04 mid-month joiner

The period is February 2026, which has 28 days. The employee joins on 2026-02-15 and has basic
`12000.00`, housing `3000.00`, transport `1000.00`, and fixed allowance `500.00`. Fourteen eligible
days produce:

| Component | Calculation | Expected |
| --- | --- | ---: |
| Basic | 12000.00 x 14 / 28 | 6000.00 |
| Housing | 3000.00 x 14 / 28 | 1500.00 |
| Transport | 1000.00 x 14 / 28 | 500.00 |
| Fixed allowance | 500.00 x 14 / 28 | 250.00 |

Expected fixed, gross, and net pay are `8250.00` with no other inputs.

### PAY-05 mid-month leaver

The period is February 2026. The employee's last employment date is 2026-02-10. The salary values
match PAY-04. Ten eligible days produce basic `4285.71`, housing `1071.43`, transport `357.14`, and
fixed allowance `178.57`. Expected fixed, gross, and net pay are `5892.85`.

An employee joining on 2026-03-01 is excluded from February. An employee whose last employment date
is 2026-01-31 is also excluded. An excluded employee has no payroll entry.

### PAY-06 component rounding

For a 31-day month, a joiner with 17 eligible days and fixed components `10000.00`, `3333.33`,
`777.77`, and `111.11` produces `5483.87`, `1827.96`, `426.52`, and `60.93`. The expected fixed-pay
sum is `7799.28`. The calculator must not round only the unpersisted aggregate.

### PAY-07 negative net

Fixed and gross pay are `1000.00`; deductions total `1000.01`. Draft validation returns a blocking
`negative_net_pay` error and preview net `-0.01`. Submit, approve, and generate fail. No payslip,
expense payment, or advance repayment is written.

## Leave, attendance, roster, and source cases

### INP-01 approved leave deduction

The Phase 8 projection supplies one approved unpaid-leave deduction of `400.00` with a source ID and
version. Refresh creates one `LEAVE_` automatic deduction. Refreshing the same version leaves one
item. Changing the source version after submission blocks approval.

### INP-02 closed attendance values

For basic salary `12000.00`, the approved projection supplies absence deduction `400.00`, standard
overtime `144.23`, and rest-day overtime `173.08`. Expected automatic additions are `317.31` and the
expected attendance deduction is `400.00`. Open, provisional, or `payrollReady=false` periods return
`payroll_input_not_ready`.

### INP-03 published roster overtime

The published roster projection supplies `288.46`. Refresh creates one `ROSTER_` addition with the
roster row ID and version. An unpublished roster, missing actual hours, or changed version blocks
approval. Attendance and roster items with the same source event are rejected as a duplicate rather
than paid twice.

### INP-04 missing Phase 10 implementation

Before Phase 10 implements the approved attendance and roster projections, refresh reports a
blocking source warning and approval returns `409 payroll_input_not_ready`. It does not read the
legacy browser cache or Supabase.

## Expense cases

### EXP-01 employee claim through payroll

The employee submits `350.00` with a verified PDF receipt. A current direct manager approves it.
Admin B, who is not the manager actor or claim owner, gives final approval. Payroll refresh creates
one `EXPENSE_` addition for `350.00`. Generating the non-excluded entry marks the claim paid and links
it to the run in the same transaction. A retry returns the first result and does not add another
reimbursement.

### EXP-02 optional manager step

A pending claim may go directly to final administrator approval. If a manager rejected it, an
administrator override requires a reason. If a manager acted, the same principal cannot make the
final administrator decision even if that principal also has the administrator role.

### EXP-03 self and scope restrictions

The claim owner cannot make a manager or administrator decision. A manager cannot see a former or
indirect report's claim. An administrator cannot see a claim from another selected branch. All
return the safe missing response and leave state unchanged.

### EXP-04 receipt validation and cleanup

A file whose body is JPEG but whose declared type is PDF is rejected. A 10 MiB PDF is accepted; a
file one byte larger is rejected. An unbound staged object expires after 24 hours and enters the
cleanup outbox. The API never returns its object key. An authorized download URL expires after five
minutes.

## Advance cases

### ADV-01 equal schedule and payroll repayment

An advance of `1500.00` has three monthly installments starting `2026-08`. Expected installments are
`500.00` in August, September, and October. With `4500.00` nonnegative pay capacity, August payroll
deducts `500.00`; generation writes one repayment and leaves `1000.00` outstanding.

### ADV-02 rounded final installment

An advance of `1000.00` over three months produces `333.33`, `333.33`, and `333.34`. After the first
two repayments, early settlement records exactly `333.34` and sets the advance to settled.

### ADV-03 constrained pay capacity

Two due advances have installments of `500.00` and `400.00`. The employee has `650.00` available
after other deductions. The older advance receives `500.00`; the second receives `150.00`. The
remaining `250.00` stays due. Neither net pay nor either advance balance becomes negative.

### ADV-04 decisions and concurrency

The employee can withdraw only their pending request. The request creator and owner cannot approve
or reject it. Two concurrent repayment commands for the same advance and payroll run produce one
repayment. The other command receives the original idempotent response or a stale-state conflict.

## Approval and payslip cases

### APP-01 separation of duties

Admin A creates and submits the run. Admin A cannot approve or reject it. Admin B approves it. Admin
A or Admin B may generate it after the approval recheck passes. Approval history records the submit
and approval actors. Generation cannot replace them.

### APP-02 recall and reject

Admin A submits the run. Admin B rejects it with a reason. The run returns to draft and retains the
rejection history. After refresh, Admin A resubmits and Admin B approves. A pending run may also be
recalled by its submitter or another branch administrator with a reason.

### APP-03 immutable payslip and atomic failure

Generation creates one immutable payslip per non-excluded entry. A forced failure while inserting an
advance repayment leaves run state approved, writes no payslip, leaves the expense approved, leaves
the advance balance unchanged, and stores no successful idempotency response.

## WPS, SIF, compliance, and Nafis cases

### WPS-01 integer-AED SIF values

PAY-01 yields SIF basic `12000`, variable `5238`, and total `17238`. The row total is the sum of the
two emitted integers. The header total is the sum of emitted row totals. Employee rows sort by MOL
identifier and then payroll entry ID.

### WPS-02 independent rounding

Basic `1000.50` and WPS variable `200.50` emit `1001` and `201`, so the row emits total `1202`.
Rounding net `1201.00` as a single value is not an accepted substitute.

### WPS-03 correction filter

Three entries begin pending. Two become paid and one becomes rejected with a reason. The run becomes
`partial_rejection`. The corrected SIF input contains only the rejected entry and keeps its finalized
pay values. Recording the corrected projection digest returns that entry to pending. Confirmation is
allowed only after all three entries are paid.

### CMP-01 compliance override

A run fails one approved compliance rule. Admin B appends an override with the exact rule code and a
reason. The override records trusted scope, actor, and time. It has no update or delete path. An
unknown code, blank reason, or cross-branch run is rejected.

### NAF-01 branch-period snapshot

Snapshot generation uses employee and company values effective at the period end and stores their
source version. Repeating with unchanged sources returns the same values. Replacing the snapshot
after a source change records the new version and result. It does not send a notification or create a
download.

## Required assertions

Each implementation part must turn its assigned cases into automated tests. Tests assert every
intermediate component shown here, transaction rollback, same-key replay, changed-payload conflict,
stale-version rejection, branch isolation, role restrictions, and the absence of duplicate source
application. A test that checks only the final net or HTTP status does not prove the case.
