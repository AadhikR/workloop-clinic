# Portal restoration C completion

## Work completed

On October 4, 2026, this task restored the administrator leave, attendance, and roster work areas.
Leave now separates overview, requests, calendar, balances, and settings while keeping decisions,
policy, holidays, and delegations on the current scoped clients. Attendance now separates its
dashboard, manual entry, records, absences, overtime, corrections, periods, and settings. Biometric
mapping and import controls remain excluded.

Successful leave changes advance a shared refresh revision so already-mounted leave views do not
show stale request or balance data when the administrator changes tabs.

Roster administration now separates shift templates, the monthly roster, and swap requests. The
monthly roster uses an employee-by-day grid and retains validation, exact-version publication,
actual-hours, overtime, and swap operations. Failed writes keep the entered values available for a
retry.

The employee Job and contract tab now reads the effective shift assignment and replaces it with the
current assignment identifier and version. No unassignment operation was added because the current
domain has no branch default shift to supply a deterministic fallback. Department staffing now
follows the selected branch's `enableStaffingRules` setting and fails closed when the setting is
absent or disabled.

The module comparison and remaining dependencies are recorded in
`PORTAL_RESTORATION_PROGRESS.md`. C's assigned implementation is complete. F still owns final
populated interaction, presentation, and database proof for A-06 and B-02.

## Local evidence

- The final local gate passed 429 frontend tests and the production build.
- Every changed source and verifier file passed lint. Repository whitespace validation passed.
- The schema head remains `e8a1c3f5b7d9`.
- A focused backend boundary run passed 99 leave, attendance, roster, shift-swap, and department
  tests. It emitted the six existing SQLAlchemy relationship warnings.
- Seven focused frontend tests cover work-area wiring, biometric exclusion, effective-shift
  concurrency fields, branch staffing visibility, and administrator routes.
- The Part C browser check passed leave, attendance, roster, staffing, and employee-shift journeys.
  It covers keyboard tab movement, cross-tab leave refresh, failed-write retention and retry, exact
  assignment concurrency fields, publication, both staffing states, and 390-pixel containment.
- Nine desktop and mobile screenshots are stored in `evidence/restoration-c`.

The full-stack browser verifier now follows the restored leave tabs. Its cleanup contract assumes
an otherwise empty database, so it was not used as evidence against the preserved populated
development volume. The verifier's fixed synthetic identifiers were cleaned. No existing product
row or preserved volume was removed.

## Independent completion gate

The independent GitHub gate is pending for the Part C code commit. Add the successful run to the
Part D handoff after every routed job passes; do not create a second commit only to store its URL.

## Preservation and continuation

No live deployment, real employee record, credential, provider resource, or preserved volume
changed. Preserve `workloop-clinic_postgres_data`, the Phase 13 external archive,
`workloop-clinic-dev`, and `fra1-default`. Autodeploy remains off. The accepted live payroll
release remains `e42808894b1c1a66c5e42738bbf9fa0cb46c538e` until restoration Part F.

Create restoration Part D after this completion record and Part C commit pass the required GitHub
gate and synchronize with the upstream branch. D owns the administrator and clinical dashboards,
reports, task groups and notifications, and remaining payroll, advance, expense, WPS, SIF, and
output presentation differences. It must close B-01 through one atomic routing-code cascade while
preserving the accepted payroll correction. The owner already authorized this continuation. Do not
deploy or start Phase 16.
