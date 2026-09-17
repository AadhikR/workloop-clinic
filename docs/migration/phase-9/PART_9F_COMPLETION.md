# Phase 9F completion

Status: implementation and local full-stack verification complete. Phase 9G is authorized next but
has not started.

## Delivered

- Added submit, recall, approve, reject, and generate commands with expected timestamps,
  idempotency, required reasons, and creator/submitter separation from the approving administrator.
- Added revision `b8e2c4d6f9a1`. Runtime payroll-run updates now pass through protected locking,
  transition, and finalization functions while direct `UPDATE` remains revoked.
- Made generated payslips and approval history immutable. Employees can read only their own payslip
  snapshots; administrators can read branch approval history; managers receive neither payroll nor
  payslip detail.
- Finalization now creates payslips, marks included expenses paid, records each advance repayment,
  verifies counts and totals, and appends protected financial audit events in one transaction.
- Added migration approval controls and an employee payslip screen without PDF, ZIP, export, or
  notification work from Phase 12. Legacy approval, finalization, payslip, expense-payment, and
  repayment-application paths fail closed.
- Completed the approval-and-payslip cutover with `migration-fastapi` as the sole read and write
  authority.

## Evidence

- All 166 frontend unit tests passed from an LF staged snapshot. The legacy and migration production
  builds and changed-file ESLint checks passed.
- The backend suite passed all 491 tests on the staged implementation before the final protected-lock
  adjustment. After that adjustment, 490 tests and every payroll test passed; the only local failure
  was the existing 500 ms disconnect scheduling check under Windows Docker. Ruff lint and format,
  dependency checks, application import, and strict Pyright passed.
- A fresh `workloop-phase9f-gate-f467` environment applied the migration twice and finished at the
  single `b8e2c4d6f9a1` head with no model/schema drift. Exact predecessor rollback and replay restored
  `d7f1b3c5e9a2` with digest
  `6dd47d672b94f64bc33cf35b500ffb29612e51de5564a1b8a2afc6af9a19fe8f`.
- Database regressions through Phase 9E passed at the new head. The Phase 9F lifecycle proof covered
  administrator separation, stale-state rejection, serialized mutation, immutable employee-owned
  payslips, expense payment, advance settlement, totals, history, and protected audit actions.
- The stack restarted without rebuilding its data volumes. Database catalog fingerprint
  `b87bd9af567491363d46a1a042f80453`, Keycloak signing keys, the private synthetic object, and its
  signing key survived. Authentication and the complete headless browser journey passed afterward.
- Synthetic records, browser identities, temporary containers, networks, and volumes were removed.
  `workloop-clinic_postgres_data` retained creation timestamp `2026-08-31T07:31:48Z` and was not
  attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the Phase 9F gate passes.
