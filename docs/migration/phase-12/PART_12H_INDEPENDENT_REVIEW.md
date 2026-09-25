# Part 12H independent review

## Review status

The project owner authorized Phase 12 through Part 12H when Part 12A started. This review began from
commit `fe6e99b2152fac5834bd8f66db75aa9ac838015e`, the completed Part 12G baseline. It compared the
Phase 12 plan, inventory, golden cases, delivery contract, amendment, code, migrations, tests,
cutover records, evidence files, and workflow routing. Earlier completion records were treated as
context, not as independent proof.

## Findings

### Finding 1: the routed gate skipped several Phase 12 proofs

- Severity: High
- Evidence: the full-stack workflow routed the 12B boundary and database verifier and the 12F
  boundary and database verifier. It did not route the 12A contract, 12C through 12E boundaries or
  database verifiers, the 12G boundary and database verifier, the exact 12G predecessor check, or a
  12H closing verifier.
- Effect: a later change could break a task, dashboard, report, rendered-output, protected-function,
  or catalogue boundary without failing the required GitHub gate.
- Fix: the workflow now routes every Phase 12 static, frontend, database, cutover, predecessor, and
  closing-boundary check. `verify-phase-12g-revision.py` checks the exact
  `d6f8a0c2e4b7` predecessor, the `e8a1c3f5b7d9` head, function ownership, search path, grants,
  and the 12F versus 12G action sets.
- State: Resolved in focused checks. Final local and routed results belong in the completion record.

### Finding 2: the post-restart browser journey stopped at Phase 11

- Severity: High
- Evidence: `scripts/verify-phase-3g-browser.mjs` exercised Phases 7 through 11 but did not call a
  Phase 12 client or assert a Phase 12 screen.
- Effect: the required administrator, manager, and employee proof after restart did not cover
  notifications, tasks, dashboards, reports, output delivery, or cross-role denial.
- Fix: the journey now opens the Phase 12 UI, reads notifications and role catalogues, checks
  administrator and self dashboards, exercises JSON reports, CSV, SIF, PDF, ZIP, payslip, and
  requested-letter delivery, and proves manager, employee, administrator-route, and cross-branch
  denials.
- State: Resolved in the focused browser implementation. Final execution belongs in the completion
  record.

### Finding 3: managers saw controls for an output their role cannot request

- Severity: Medium
- Evidence: the approved role table grants requested-letter PDFs to administrators and employees.
  The server and protected audit writer deny managers, but `LetterRequests.jsx` rendered Print PDF
  and Download PDF for every completed non-administrator request.
- Effect: a manager could select a control that always failed with `operation_not_permitted`.
- Fix: the screen now keeps completed-letter PDF controls to administrators and employees. The
  server denial remains unchanged, and a focused frontend test pins the control rule.
- State: Resolved. No role or output entitlement changed.

### Finding 4: live Phase 12 read responses did not satisfy their delivery contract

- Severity: High
- Evidence: the browser journey reached the real employee inbox and returned an internal error. The
  notification repository had qualified an anchor column by replacing every `branch_id` token,
  including the `:branch_id` bind parameter. After that query was fixed, live notification, task,
  dashboard, and report timestamps still retained six fractional digits while the approved client
  contract requires milliseconds.
- Effect: notification lists failed against PostgreSQL, and successful Phase 12 read responses could
  still be rejected by the migration client.
- Fix: repository query construction now qualifies only column names and preserves the bind name.
  Notification, task, dashboard, and report timestamps now serialize to UTC milliseconds.
  Repository, service, and delivery-contract regression tests pin both boundaries.
- State: Resolved in focused checks. Final browser and routed results belong in the completion record.

### Finding 5: browser output delivery failed at two authorization boundaries

- Severity: High
- Evidence: live PDF delivery included the required `Vary` and `X-Content-Type-Options` headers, but
  the CORS boundary did not expose them to the migration client. After that mismatch was fixed, the
  administrator payslip route returned `resource_not_found` because the retained Phase 9 payslip
  policy still admitted employees only.
- Effect: the fail-closed browser client rejected successful binary responses, and administrators
  could not use an output that the approved Phase 12 role table grants to them.
- Fix: the CORS allowlist now exposes both validated headers. The Part 12G head admits verified
  administrators to branch-scoped payslips while retaining employee self scope and manager denial;
  its exact downgrade restores the employee-only policy. HTTP-boundary, revision, database, and
  three-role browser checks pin the result.
- State: Resolved in local integration checks. Final routed results belong in the completion record.

No finding requires a new table, cloud resource, scheduler, production credential, optional report,
legacy fallback, or Phase 13 work.

## Inventory trace

| ID | Final disposition | Automated proof |
| --- | --- | --- |
| `P12-NOT-01` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-02` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-03` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-04` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-05` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-06` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-07` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-08` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-09` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-10` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-11` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-12` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-13` | Completed under the FastAPI notification or expiry boundary. | `verify-phase-12b-boundary.py`; `verify-phase-12b-database.py` |
| `P12-NOT-14` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |
| `P12-TSK-01` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-02` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-03` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-04` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-05` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-06` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-07` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-08` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-09` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-10` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-11` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-12` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-13` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-14` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-15` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-16` | Completed under the server-owned task catalogue. | `verify-phase-12c-boundary.py`; `verify-phase-12c-database.py` |
| `P12-TSK-17` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |
| `P12-DSH-01` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-02` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-03` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-04` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-05` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-06` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-07` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-08` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-09` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-10` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-11` | Completed under the read-only dashboard projections. | `verify-phase-12d-boundary.py`; `verify-phase-12d-database.py` |
| `P12-DSH-12` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |
| `P12-RPT-01` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-02` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-03` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-04` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-05` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-06` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-07` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-08` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-09` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-10` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-11` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-12` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-13` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-14` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-15` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-16` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-17` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-18` | Completed under the thirteen server report projections. | `verify-phase-12e-boundary.py`; `verify-phase-12e-database.py` |
| `P12-RPT-19` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |
| `P12-OUT-01` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-02` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-03` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-04` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-05` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-06` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-07` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-08` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-09` | Completed under server CSV and SIF delivery. | `verify-phase-12f-boundary.py`; `verify-phase-12f-database.py` |
| `P12-OUT-10` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-11` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-12` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-13` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-14` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-15` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-16` | Completed under server PDF or ZIP delivery. | `verify-phase-12g-boundary.py`; `verify-phase-12g-database.py` |
| `P12-OUT-17` | Omitted because no approved output exists. | dependency catalogue fail-closed decision; `verify-phase-12g-boundary.py` |
| `P12-OUT-18` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |
| `P12-DB-01` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-02` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-03` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-04` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-05` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-06` | Completed under the notification and expiry database boundary. | `verify-phase-12b-database.py` |
| `P12-DB-07` | Completed under the protected rendered-output audit boundary. | `verify-phase-12g-revision.py`; `verify-phase-12g-database.py` |
| `P12-DB-08` | Completed under scoped report source reads. | `verify-phase-12e-database.py` |
| `P12-DB-09` | Completed under source-only rendered output. | `verify-phase-12g-database.py`; output renderer tests |
| `P12-IND-01` | Completed through the admin and clinical dashboard projections. | `verify-phase-12d-boundary.py`; browser journey |
| `P12-IND-02` | Completed through one notification authority. | notification cutover record; `verify-phase-12b-boundary.py` |
| `P12-IND-03` | Completed through one task authority. | dependency catalogue; `verify-phase-12c-boundary.py` |
| `P12-IND-04` | Completed through one dashboard authority. | dependency catalogue; `verify-phase-12d-boundary.py` |
| `P12-IND-05` | Completed through protected output delivery. | dependency catalogue; `verify-phase-12g-boundary.py` |
| `P12-IND-06` | Completed through protected output delivery. | dependency catalogue; `verify-phase-12g-boundary.py` |
| `P12-IND-07` | Completed through protected output delivery. | dependency catalogue; `verify-phase-12g-boundary.py` |
| `P12-IND-08` | Retained only for Phase 13 removal. | dependency catalogue; migration-source scan |

## Upstream assignment trace

| ID | Independent proof |
| --- | --- |
| `P0-NOTIFICATION-BELL` | 12B notification boundary |
| `P0-GENERATED-NOTIFICATIONS` | 12B producer and expiry proof |
| `P0-TASK-CENTER` | 12C task boundary |
| `P0-ADMIN-DASHBOARD` | 12D dashboard boundary |
| `P0-CLINICAL-DASHBOARD` | 12D dashboard boundary |
| `P0-REPORTS-EXPORTS` | 12E report and 12F/12G output proofs |
| `P0-PAYSLIP-FILE` | 12G renderer and database proofs |
| `P0-SIF-FILE` | 12F renderer and database proofs |
| `P0-REPORT-FILES` | 12F/12G renderer proofs |
| `P0-TASK-ACCEPTANCE` | 12C complete-category proof |
| `phase8a-admin-leave-screen` | 12F leave-balance export proof |
| `phase8a-notification-producer` | 12B workflow producer proof |
| `phase8a-balance-csv` | 12F CSV proof |
| `phase8a-notifications` | 12B notification proof |
| `phase8a-tasks` | 12C task proof |
| `phase8a-dashboards-reports` | 12D through 12G consumer proofs |
| `UI-01` | 12F SIF and 12G payslip controls |
| `UI-09` | 12G self-payslip proof |
| `UI-10` | 12F SIF preview and correction proof |
| `UI-11` | 12F Nafis CSV proof |
| `UI-12` | 12D payroll card proof |
| `UI-13` | 12E through 12G report-output proof |
| `UI-16` | 12C finance-task proof |
| `JS-15` | 12F SIF renderer tests |
| `JS-17` | 12G payslip renderer tests |
| `JS-18` | 12E report and 12F/12G output tests |
| `JS-19` | 12C task service tests |
| `JS-20` | 12B notification tests |
| `EXT-04` | 12G payslip delivery proof |
| `EXT-05` | 12F SIF delivery proof |
| `EXT-06` | 12E through 12G report-output proof |
| `EXT-07` | 12C aggregation proof |
| `EXT-08` | 12B workflow notification proof |
| `ATT-UI-01` | 12E attendance report and 12F CSV proof |
| `ATT-UI-03` | 12F roster CSV and 12B producer proof |
| `ATT-UI-08` | 12D clinical dashboard proof |
| `ATT-UI-09` | 12E attendance and roster report proof |
| `ATT-UI-12` | 12B notification proof |
| `ATT-UI-13` | 12C regularisation and swap task proof |
| `ATT-EXT-04` | 12H cross-part browser and workflow proof |
| `P11-INS-02` | 12B policy-expiry proof |
| `P11-AST-03` | 12D self-asset card proof |
| `P11-REQ-02` | 12G employee requested-letter proof |
| `P11-REQ-03` | 12G administrator requested-letter proof |
| `P11-REQ-04` | 12G server renderer and print proof |
| `P11-OFF-02` | 12G offboarding-letter proof |
| `P11-OFF-03` | 12G settlement PDF proof |
| `P11-OFF-05` | 12E EOS liability proof |
| `P11-LTR-01` | 12D dashboard proof |
| `P11-LTR-02` | 12C task proof |
| `P11-LTR-03` | 12B producer and inbox proof |
| `P11-LTR-04` | 12E through 12G output proof |

## Golden-case proof map

| ID | Automated proof |
| --- | --- |
| `12A-GC-001` | notification API and service tests; `verify-phase-12b-database.py` |
| `12A-GC-002` | notification API and service tests; `verify-phase-12b-database.py` |
| `12A-GC-003` | notification API and service tests; `verify-phase-12b-database.py` |
| `12A-GC-004` | notification API and service tests; `verify-phase-12b-database.py` |
| `12A-GC-005` | notification API and service tests; `verify-phase-12b-database.py` |
| `12A-GC-006` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-007` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-008` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-009` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-010` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-011` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-012` | workflow and expiry checks in `verify-phase-12b-database.py` |
| `12A-GC-013` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-014` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-015` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-016` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-017` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-018` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-019` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-020` | task API and service tests; `verify-phase-12c-database.py` |
| `12A-GC-021` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-022` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-023` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-024` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-025` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-026` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-027` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-028` | dashboard API and service tests; `verify-phase-12d-database.py` |
| `12A-GC-029` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-030` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-031` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-032` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-033` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-034` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-035` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-036` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-037` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-038` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-039` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-040` | report API and service tests; `verify-phase-12e-database.py` |
| `12A-GC-041` | CSV renderer and report-route tests; `verify-phase-12f-database.py` |
| `12A-GC-042` | CSV renderer and report-route tests; `verify-phase-12f-database.py` |
| `12A-GC-043` | SIF renderer and preview tests; `verify-phase-12f-database.py` |
| `12A-GC-044` | SIF renderer and preview tests; `verify-phase-12f-database.py` |
| `12A-GC-045` | SIF renderer and preview tests; `verify-phase-12f-database.py` |
| `12A-GC-046` | rendered-output tests; `verify-phase-12g-database.py` |
| `12A-GC-047` | rendered-output tests; `verify-phase-12g-database.py` |
| `12A-GC-048` | rendered-output tests; `verify-phase-12g-database.py` |
| `12A-GC-049` | rendered-output tests; `verify-phase-12g-database.py` |
| `12A-GC-050` | 12G database rollback proof; cutover validation; 12H rollback assertion |

## Cutover and rollback review

Both cutover records pass the canonical validator. Their evidence hashes match the tracked evidence
files, and both records name `migration-fastapi` as the only read and write authority. The
dependency catalogue contains 97 unique entries: 90 completed, six retained for Phase 13, and one
fail-closed omission. The migration source contains no Supabase client, retained storage import,
browser document generator, browser print call, or browser ZIP generator.

Rollback starts with 12G render routes and controls, then disables 12F byte routes, 12E reports, 12D
dashboards, 12C tasks, and 12B producers and inbox routes. A legacy reader or writer may return only
after its migration counterpart is disabled. Source rows, notification state, audit rows,
settlements, snapshots, renderer evidence, and generated-object scan evidence remain intact.

## Security and delivery review

The expiry command accepts only `EXPIRY_DATABASE_URL` and checks the fixed
`workloop_expiry_processing` login. Its database verifier covers trusted business date, tuple
locking, source grants, branch and tenant scope, replay, concurrency, and safe failure output.

The output audit function remains owned by `workloop_migration`, uses a pinned
`pg_catalog, public` search path, denies `PUBLIC`, grants only runtime execution, and leaves the
runtime role without a direct `audit_events` insert grant. The 12G revision adds six PDF and ZIP
actions to the eight 12F actions. It also grants verified administrators branch-scoped payslip read
access for the approved PDF and ZIP routes while retaining employee self scope and manager denial.
Its downgrade restores the 12F allowlist and employee-only payslip policy without deleting audit
rows. Services finish rendering and append the safe audit before returning bytes.

The browser journey and database verifiers cover role, company, branch, self, and direct-report
scope. Reports and administrative outputs remain administrator-only. Employee output is limited to
the employee's own payslip and completed requested letter. Managers retain no broad report, payroll,
bank, or document-output authority.

## Final gate contract

The closing gate must use a fresh disposable Compose project. It applies migrations twice, verifies
one head and no pending operation, downgrades exactly to `d6f8a0c2e4b7`, verifies the 12F
allowlist and retained audit evidence, and returns to `e8a1c3f5b7d9`. It runs the complete
historical and Phase 12 database sequence, restarts the existing images without rebuilding, compares
database and Keycloak signing-key state, verifies stored object and scan evidence, runs the
three-role browser journey after restart, checks authentication and logs, and removes only its own
synthetic resources.
