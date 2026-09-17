# Phase 9D completion

Status: implementation and local verification complete. Phase 9E is authorized but not started.

## Delivered

- Added selected-branch administrator payroll list, detail, create, repeat, refresh, save, and
  guarded draft-delete routes with strict request and response projections.
- Made FastAPI authoritative for employee selection, salary snapshots, payment dates, calculation,
  validation, run totals, and editable draft state. Calculations use fixed-decimal half-up rounding
  and reject stale, mixed-scope, duplicate, unknown, or invalid input atomically.
- Preserved recurring manual adjustments when repeating a run while excluding one-time and
  automatic items. Automatic leave, attendance, roster, expense, and advance inputs remain disabled
  until Phase 9E.
- Added revision `c5e7a9b1d3f4` with immutable salary snapshot fields, payroll-entry constraints,
  protected entry replacement and draft deletion, payroll replay support, protected audit actions,
  and an exact predecessor restoration boundary.
- Added the migration payroll list and draft editor without approval, finalization, payslip, WPS,
  file, export, or notification controls. Legacy payroll draft writers and browser-owned payroll
  calculations now fail closed.
- Completed the payroll draft and calculation cutover with `migration-fastapi` as the sole read and
  write authority.

## Evidence

- The native backend gate passed all 486 tests. Ruff lint and formatting, strict Pyright,
  dependency checks, application import, and OpenAPI generation passed. The unchanged disconnect
  cancellation test also passed after the installed environment was warm; its first invocation can
  exceed the test's half-second setup deadline on Windows and Docker Desktop.
- The staged canonical LF snapshot passed all 161 frontend unit tests and both production builds.
  The payroll client and legacy-freeze tests and targeted ESLint also passed.
- A fresh `workloop-phase9d-final-c488` PostgreSQL 17 environment applied the migration repeatedly,
  replayed the empty-schema chain, finished at the single `c5e7a9b1d3f4` head with no model/schema
  drift, restored `a1c3e5f7b9d2` with predecessor digest
  `b48e3e58ad19f7e2b61a24bb64dea2519b860b60ebfd8ebc8514b15bec2d99ce`, and replayed the head.
- The deep database verifier covered branch scope, one-run-per-period enforcement, salary and
  employment snapshots, decimal calculations, recurring-item filtering, exclusions, refresh,
  replacement, draft deletion, optimistic timestamps, protected audit, exact replay, changed-payload
  conflicts, and rollback. Phase 4, 5, 7G, 8B through 8F, and 9B through 9C database regressions also
  passed at the new head.
- The stack restarted without rebuilding its data volumes. The database catalog fingerprint,
  Keycloak signing keys, private synthetic object, and storage signing key survived the restart;
  authentication and the browser journey passed afterward.
- Synthetic browser fixtures and both isolated stacks, networks, and temporary volumes were
  removed. `workloop-clinic_postgres_data` retained the same creation timestamp and was not
  attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the Phase 9D gate passes.
