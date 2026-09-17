# Phase 9E completion

Status: implementation and local verification complete. Phase 9F is authorized but not started.

## Delivered

- Added selected-branch, locked payroll projections for approved leave, approved unpaid expenses,
  and due active salary advances. Attendance and roster remain unavailable until Phase 10 and now
  produce explicit blocking warnings instead of provisional values.
- Made automatic adjustments deterministic by source type, source ID, source version, period,
  calculation inputs, and rounded amount. Refresh replaces automatic inputs while preserving manual
  adjustments, and repeated refreshes keep the same source fingerprint and entry values.
- Kept payroll calculations and validation on the server. Browser previews display automatic items
  but cannot submit them as manual adjustments or override their source data.
- Added revision `d7f1b3c5e9a2` for the protected `payroll_inputs_refreshed` audit action. Its metadata
  contains only per-source counts and SHA-256 digests, and downgrade restores the exact 9D audit
  function after refusing unsafe rollback when 9E audit rows exist.
- Completed the payroll-input cutover with `migration-fastapi` as the sole read and write authority.
  The legacy payroll editor no longer reads leave, attendance, roster, expense, or advance inputs.

## Evidence

- All 490 backend tests passed from container-local source. Ruff lint and formatting, dependency
  checks, application import, and strict Pyright on the changed payroll files passed.
- The payroll client, automatic-input, and legacy-freeze tests passed. Both legacy and migration
  production builds completed successfully.
- A fresh `workloop-phase9e-final-141f` environment applied the migration twice, replayed the
  empty-schema chain, finished at the single `d7f1b3c5e9a2` head with no model/schema drift, and
  restored `c5e7a9b1d3f4` with predecessor digest
  `eeaa456b5a0fc353b98905d14d231f16da1c8c73e97ab06aa983c19809d08d72` before replaying head.
- The deep verifier covered source scope and order, source versions and fingerprints, exact leave,
  expense, and advance cents, unchanged refresh replay, changed-payload conflict, optimistic
  concurrency, manual-item preservation, protected audit metadata, and fail-closed attendance and
  roster inputs. Phase 8B through 8F and 9B through 9D database regressions passed at the new head.
- The stack restarted without rebuilding its data volumes. Database catalog fingerprint
  `da659e11d2899fb6a60c528406f09fb5`, Keycloak signing keys, the private synthetic object, and its
  signing key survived. The complete authentication and headless browser journey passed afterward,
  and service logs contained no token, database credential, identity subject, or generated secret.
- Synthetic records, browser fixtures, temporary containers, networks, and volumes were removed.
  `workloop-clinic_postgres_data` retained creation timestamp `2026-08-31T07:31:48Z` and was not
  attached, upgraded, seeded, recreated, or deleted.
- The required GitHub result is recorded in the task report after the Phase 9E gate passes.
