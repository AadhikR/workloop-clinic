# Phase 9C completion

Status: implementation and local verification complete. Phase 9D is authorized but not started.

## Delivered

- Added employee advance requests, self reads, and pending withdrawal, plus selected-branch
  administrator listing, creation, schedule replacement, approval, rejection, manual repayment, and
  settlement.
- Enforced the approved transitions, actor separation, branch and employee scope, fixed-decimal
  inputs, database business date, optimistic timestamps, strict projections, safe missing responses,
  scoped cursors, exact replay, and changed-payload conflicts.
- Calculated monthly deductions with half-up decimal rounding and retained the final partial
  installment. Repayments reduce the outstanding balance exactly once and preserve cancelled and
  settled history.
- Added revision `a1c3e5f7b9d2` with protected advance locking, hardened repayment recording,
  `salary_advance` replay support, approved protected audit actions, trusted repayment dates, and an
  exact predecessor restoration boundary.
- Added employee and administrator migration views with no Supabase dependency. Legacy advance and
  repayment writers now fail closed; the retained read helper remains available only to the later
  payroll and offboarding owners.
- Completed the advance and repayment cutover with `migration-fastapi` as the sole read and write
  authority. Offboarding settlement remains owned by Phase 11.

## Evidence

- The backend gate passed 478 tests together. The existing half-second disconnect timing test was
  then run against the installed wheel on the container filesystem and passed, avoiding Windows bind
  mount latency. Ruff lint and formatting, strict Pyright, dependency checks, application import,
  and OpenAPI generation passed.
- The frontend gate passed the advance client and legacy-freeze tests, the line-ending-independent
  unit suite, targeted ESLint, both production builds, and the complete browser authentication
  journey. GitHub provides the canonical LF-checkout run for the older digest and prose fixtures.
- A fresh `workloop-phase9c-final-9e08` PostgreSQL 17 environment applied the migration repeatedly,
  replayed the empty-schema chain, finished at the single `a1c3e5f7b9d2` head with no model/schema
  drift, restored `f9b2c4d6e8a1` with predecessor digest
  `08fecb62a870005ea921884335ed1044bbf87ef26c478379a688165668b74b45`, and replayed the head.
- The deep database verifier covered request, withdrawal, schedule, approval, rejection, manual
  repayment, settlement, stale commands, identical replay, changed-payload conflict, concurrent
  repayment, branch scope, actor separation, protected audit, exact balance reduction, final partial
  installments, and immutable cancelled and settled history. Phase 7G, 8B through 8F, and 9B deep
  regressions also passed at the new head.
- The stack restarted without rebuilding its data volumes. The database catalog fingerprint,
  Keycloak signing keys, private synthetic object, and storage signing key survived the restart;
  authentication and the browser journey passed afterward.
- Synthetic browser fixtures and the isolated containers and volumes were removed.
  `workloop-clinic_postgres_data` was not attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the single phase push.
