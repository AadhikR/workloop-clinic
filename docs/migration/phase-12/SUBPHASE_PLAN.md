# Phase 12 subphase plan

## Status and authorization

The project owner started Part 12A on 2026-09-24 and authorized Parts 12A through 12H under
`docs/migration/PHASE_EXECUTION_WORKFLOW.md`. Each part runs in a separate Codex task. A part must
pass its focused checks, boundary-matched local gate, push, and routed GitHub jobs before the next
part starts automatically.

Phase 11 is complete and signed off. Phase 12 starts from commit
`ca78715ffe813a5cc47e7ad24680dfd0035ba746` on `migration/fastapi-keycloak`, with Alembic head
`c3e5a7b9d1f6`. The protected `workloop-clinic_postgres_data` volume remains present and must not be
attached, modified, deleted, or recreated.

Phase 12 is complete. The project owner signed it off on 2026-09-26 after commits `583c1d6` and
`0aedf02` and GitHub Migration foundation run `36175462925` passed. Phase 13 requires a separate
owner instruction and has not started.

## Phase boundary

Phase 12 replaces notifications, task aggregation, dashboards, reports, expiry production, CSV, SIF,
PDF, letters, print delivery, ZIP, previews, and generated downloads in the migration build. It reads
the authoritative projections supplied by Phases 7 through 11. It does not own source-domain
workflows or repair their state.

The following work is outside this phase:

- Not authorized: email delivery.
- Not authorized: SMS delivery.
- Not authorized: push delivery.
- Not authorized: production credential.
- Not authorized: cloud scheduler.
- No cloud service, paid resource, production data, real employee data, or regulated record.
- No Supabase removal or migration-build promotion. Phase 13 owns both.
- No optional analytics, data warehouse, scheduled report, or persistent output archive.

Expiry production remains an explicit deterministic command. A scheduler requires a separately
approved resource and operating contract. On-demand file bytes are streamed and discarded. Only
safe metadata enters the audit log.

## Part plan

| Part | Scope | Required result | Rollback boundary |
| --- | --- | --- | --- |
| 12A | Contracts, dependency inventory, golden cases, amendment decision, and cutover design | Every dependency and upstream assignment has one owner; 50 golden cases and strict delivery rules pass the focused verifier | Revert 12A documents and verifier only |
| 12B | Notifications and expiry production | Recipient-scoped inbox and read actions, allowlisted workflow producers, explicit expiry command, source-linked audit, migration UI cutover | Disable expiry command and migration inbox before restoring legacy producers and bell |
| 12C | Task aggregation | Fixed role category catalogues, explicit empty and failure states, stable ordering, migration task screens | Disable migration task endpoint and screen before restoring legacy aggregation |
| 12D | Dashboards | Internally consistent admin, clinical, and self snapshots with no write side effects | Disable migration dashboards before restoring legacy reads and calculations |
| 12E | Reports | Thirteen approved server report projections with exact filters, ordering, decimals, totals, and pagination | Disable migration reports before restoring legacy report reads |
| 12F | CSV and SIF output | Deterministic CSV and SIF bytes, exact preview parity, filenames, headers, output audit, and migration download controls | Disable byte routes before restoring browser CSV or SIF generation |
| 12G | PDF, letters, print, ZIP, and output cutovers | Deterministic PDFs and ZIP, source-only letters and settlement, safe delivery, all Phase 12 cutover records | Disable render routes and print controls before restoring browser generators |
| 12H | Independent review and complete Phase 12 gate | Trace the complete catalogue and golden cases, prove all cutovers, reverse rollback, restart, browser paths, safe logs, and routed full-stack gate | Freeze Phase 12 consumers in reverse order and preserve all source and audit evidence |

## Part 12A result

Part 12A creates:

- `PART_12A_DEPENDENCY_INVENTORY.md` with 97 owned dependencies and the exact upstream assignment
  trace;
- `PART_12A_OUTPUT_AND_DELIVERY_CONTRACT.md` with authorization, shapes, filters, ordering,
  pagination, date, decimal, deterministic byte, filename, encoding, header, error, audit,
  idempotency, and rollback rules;
- `PART_12A_GOLDEN_CASES.md` with 50 fixed cases;
- `PART_12A_AMENDMENT_PROPOSAL.md` with the one required protected audit writer and no new table or
  column;
- `scripts/verify-phase-12a-contract.py`; and
- `PART_12A_COMPLETION.md` after the local and GitHub gates pass.

12A does not add a runtime route, migration revision, frontend screen, worker, scheduler, or cutover
record.

## Part 12B notification and expiry production

12B adds recipient-scoped list, unread count, read-one, and read-all HTTP routes. It integrates only
the existing allowlisted workflow notification types. The explicit expiry command receives company,
branch, and trusted business date, runs under `workloop_expiry_processing`, takes the tuple lock,
uses the existing source grants and policies, and writes linked audits. It adds migration bell UI and
cutover evidence.

Focused proof covers every notification type and threshold, recipient and branch isolation,
pagination, read replay, workflow derivation, explicit run repeatability, concurrency, missing
context denial, safe logs, and restart persistence. No external delivery or scheduler is added.

## Part 12C task aggregation

12C adds the role-derived task endpoint and migration task screen. The server owns category codes,
labels, navigation codes, urgency, completeness, and ordering. It uses only current projections and
does not copy stale `doc_type`, payroll month and year, or `eid_expiry` assumptions.

Focused proof covers every admin, manager, and employee category, empty categories, required source
failure, direct-report changes, branch and tenant denial, stable pagination, task IDs, navigation,
and absence of Supabase calls in the migrated path.

## Part 12D dashboards

12D adds admin, clinical, and self snapshot endpoints and migration screens. A response uses one
`asOf`, trusted business date, and source version. Dashboard reads have no notification or domain
write side effect. Payroll, Nafis, leave, attendance, roster, staffing, documents, insurance,
certifications, requests, appraisals, assets, and employment cards retain their source owner.

Focused proof covers cross-source snapshot consistency, branch and self scope, expiry-policy reuse,
published versus draft roster, verified versus unavailable evidence, source failure, decimals, safe
drill-down links, and no-write assertions.

## Part 12E reports

12E implements the approved JSON reports: headcount, payroll cost, leave utilization, attendance
summary, overtime, document expiry, salary movement, turnover, staffing compliance, WPS compliance,
Emiratization, EOS liability, and leave balance. It does not add the optional domain reports listed
only as future possibilities in the legacy UI.

Focused proof covers normalized filters, inclusive ranges, exact source status values, stable total
order, cursor binding, full-filter totals, nulls, decimal strings, unsupported settlement policy,
branch isolation, and safe source failure.

## Part 12F CSV and SIF output

12F adds CSV delivery for approved reports and named compatibility exports. It adds SIF preview,
full SIF, and rejected-entry SIF from the Phase 9 input projection. Preview parses the generated
bytes. It applies the protected output audit amendment with the 12F allowlist.

Focused proof covers UTF-8, BOM policy, RFC 4180 escaping, formula protection, CRLF, SIF ASCII, EDR
order, integer-AED rounding, SCR totals, final line ending, filenames, headers, digests, limits,
audit denial, and byte equality across processes.

## Part 12G rendered outputs and cutovers

12G adds report PDF, administrator and self payslip PDF, bulk payslip ZIP, completed request letter,
offboarding letters, and final-settlement PDF. Browser print opens the authorized PDF. The renderer
pins fonts, assets, metadata, timestamps, IDs, layout, locale, and archive settings. It extends the
protected output audit allowlist for 12G actions and writes all Phase 12 cutover records.

Focused proof covers source-only rendering, byte determinism, page limits, self and branch denial,
missing assets, unsafe filenames, ZIP manifest and order, download headers, audit failure, partial
stream prevention, print parity, legacy path freeze, and reverse rollback.

## Part 12H independent review

12H reviews all 97 inventory entries, every upstream assignment, and all 50 golden cases. It scans
the migration build for Supabase or browser-generator paths, validates each cutover record, checks
the protected audit writer and expiry login, and runs the complete full-stack gate in a fresh
isolated environment.

The final gate applied migrations twice, verified the append-only head and exact predecessor
rollback, exercised deep database and security checks, restarted existing images without rebuilding,
compared database and signing-key state, ran the complete three-role browser journey, checked safe
logs, and cleaned only disposable resources. The project owner signed off Phase 12 on 2026-09-26.
Phase 13 has not started.

## Shared verification and source control

Each part follows `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks while changing one
bounded unit, then run one boundary-matched local gate. Database, authentication, Compose, or shared
infrastructure changes require an isolated full-stack gate. Push the settled part once and wait for
every routed Migration foundation job. Documentation-only completion updates after a passing code
gate use lightweight validation only.

Every nonfinal part leaves a clean synchronized `migration/fastapi-keycloak` branch, generates the
next handoff from verified repository state, creates a new task in the same saved project and local
checkout, and starts it without asking for approval.

## Resource and data boundary

Use synthetic local data and disposable isolated services only. Preserve
`workloop-clinic_postgres_data` untouched. Do not use production data, employee records, patient
records, payroll or banking records, paid services, cloud resources, or production credentials.
Verify an exact disposable target before cleanup and remove only resources created by the current
part.
