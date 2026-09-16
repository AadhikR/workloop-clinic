# Phase 9A completion record

Status: complete. The project owner authorized sequential execution through Phase 9H. Part 9A made
documentation and contract changes only. Part 9B is the next permitted implementation task after
this commit passes its routed GitHub workflow.

## Scope completed

- Accounted for the legacy payroll, payslip, WPS, SIF, Nafis, advance, repayment, expense, receipt,
  calculation, validation, RPC, storage, task, report, notification, attendance, leave, roster, and
  offboarding dependencies.
- Assigned every dependency to Parts 9B through 9G or to its Phase 10, 11, or 12 owner.
- Fixed strict employee, manager, and administrator routes and projections, including filters, sort,
  pagination, null, date, decimal, redaction, safe-error, idempotency, and stale-write rules.
- Fixed the payroll period, trusted UAE business date, payment-date range, salary snapshot,
  calendar-day proration, component rounding, adjustment signs, exclusion, and negative-net rules.
- Fixed expense and advance transitions, self-action restrictions, direct-manager scope,
  administrator decisions, repayment order, early settlement, and payroll application.
- Approved two-administrator separation for payroll creation and submission versus approval.
- Approved a bounded Phase 8 private-storage reuse for expense receipts. Phase 11 still owns the
  production provider and complete recovery proof.
- Defined the closed, payroll-ready attendance and published-roster input projections that Phase 10
  must supply. Payroll fails closed until they exist.
- Fixed WPS and entry transitions, corrected SIF input filtering, integer-AED rounding, immutable
  compliance overrides, and Nafis snapshot inputs. Phase 12 still owns file bytes and downloads.
- Approved the exact amendment envelope for receipt metadata, payroll source snapshots, protected
  audit actions, grants, RLS, constraints, and indexes. No amendment was implemented in 9A.
- Prepared six synthetic cutover records. All remain in `preparation`, with legacy Supabase as the
  sole read and write authority and migration paths frozen.

## Decisions that differ from legacy behavior

The server uses decimal arithmetic, not JavaScript floating point. It prorates each fixed component
by inclusive eligible calendar days divided by actual days in the month. It rounds stored components
half up to cents before summing them. The cutover converter maps legacy `duCost` to
`leaveDeduction`; public APIs reject `duCost`.

The same administrator cannot create or submit and then approve a payroll. Synthetic fixtures must
contain two administrators in the same branch. A generated payslip can never have negative net pay.
SIF basic and variable pay round independently to integer AED.

Receipt URLs are not authority. The migration flow accepts one detected PDF, PNG, or JPEG up to 10
MiB in a request capped at 12 MiB. It uses opaque private keys, SHA-256 metadata, five-minute signed
downloads, and durable cleanup intent.

## Review findings

The canonical schema contains the required financial tables and protected functions. Later parts
must correct two audit allowlist names before relying on them: `disbursement_date` does not match
canonical `disbursed_date`, and `sif_status` is not a payroll-run column. The amendment proposal
records the accepted canonical fields.

No new human role is needed. No Phase 10 table is added by Phase 9. Phase 11 retains common storage
and recovery ownership. Phase 12 retains report, notification, task, PDF, ZIP, CSV, and SIF file
ownership.

## Verification evidence

- All six records passed `node scripts/cutover-record-validator.mjs` with matching tracked-source and
  evidence digests.
- The golden rounding values were recalculated with Python `Decimal` and `ROUND_HALF_UP`.
- `git diff --check` passed.
- The change contains no Alembic revision, runtime code, schema change, storage operation, cutover,
  or production-data access.

## Rollback and stop condition

Revert the Part 9A documents if the contract is rejected. No data rollback is needed because legacy
Supabase remains authoritative for all six units. Do not enable a migration financial route, create
a Phase 9 revision, change a financial writer, or touch `workloop-clinic_postgres_data` as part of
9A.

After the routed GitHub workflow passes, create exactly one Part 9B successor task in the saved
Workloop Clinic project and stop this task. Do not start Part 9B here.
