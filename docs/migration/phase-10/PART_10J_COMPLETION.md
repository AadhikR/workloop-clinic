# Part 10J completion

Status: complete and signed off by the project owner on 2026-09-22.

## Result

Part 10J reviewed the complete Phase 10 boundary and closed the remaining proof gaps. All eight
cutover records name `migration-fastapi` as the only readable and writable authority. Migration
source code contains no Supabase path. Every Phase 10 revision has an exact predecessor check, and
the database verifiers exercise the current head from configuration through protected shift-swap
execution.

The review found four integration defects that isolated unit mocks had not exposed. Phase 10
clients rejected the shared HTTP transport envelope, roster reads passed untyped null filters to
PostgreSQL, successful 200 shift-swap transitions attempted to persist a forbidden `Location`
header, and CI omitted the Phase 10C database verifier. The browser proof also lacked Phase 10
attendance, biometric, roster, and swap journeys. Those defects and coverage gaps are corrected.

The final review added explicit proof for consecutive unexplained absences across a weekend,
per-occurrence late deductions, concurrent swap approval, payroll-frozen swap rejection, and
cleanup of biometric imports and attendance periods. The complete browser journey now covers all
three roles and removes every synthetic database row and temporary Keycloak credential it creates.

## Review boundary

- Trusted scope and identity are derived inside the authorization transaction. Selected-branch,
  employee-self, and administrator paths remain distinct.
- Dubai business dates and overnight ownership are calculated on the server. Hours and money use
  decimal arithmetic with one final currency rounding step.
- Clock events, audit events, close versions, publication versions, memberships, and swap history
  retain append-only provenance. Forced-failure checks prove transaction rollback.
- Idempotency fingerprints cover the command shape. Replays reauthorize the retained resource,
  and only 201 or 202 responses retain a location.
- Publication and swap operations lock and recheck their mutable sources. Payroll snapshots freeze
  the referenced source version.
- Runtime grants remain least-privilege, Phase 10 tables retain forced RLS, and protected functions
  validate the trusted actor and scope before data access.
- Error documents and browser projections expose no biometric secret, salary source, raw audit
  metadata, or cross-branch record.

## Inventory trace

| ID | Final disposition | Automated proof |
| --- | --- | --- |
| `ATT-JS-01` | Replaced by the 10B settings API; legacy reads and writes are frozen. | `verify-phase-10b-database.py`; `phase-10b-legacy-freeze.test.js` |
| `ATT-JS-02` | Replaced by the 10B shift catalogue API with retained-use guards. | `verify-phase-10b-database.py`; `migration-attendance-configuration.test.js` |
| `ATT-JS-03` | Replaced by protected effective-dated assignment commands. | `verify-phase-10b-database.py` |
| `ATT-JS-04` | Replaced by append-only manual and biometric event APIs. | `verify-phase-10c-database.py`; `phase-10c-legacy-freeze.test.js` |
| `ATT-JS-05` | Browser calculation and upsert are replaced by the 10D service. | `verify-phase-10d-database.py`; `phase-10d-legacy-freeze.test.js` |
| `ATT-JS-06` | Period reads and close are replaced by the atomic 10F service. | `verify-phase-10f-database.py`; `phase-10f-legacy-freeze.test.js` |
| `ATT-JS-07` | Regularisation and decision helpers are replaced by 10E workflows. | `verify-phase-10e-database.py`; `phase-10e-legacy-freeze.test.js` |
| `ATT-JS-08` | Payroll attendance reads use the closed 10F projection. | `verify-phase-10f-database.py`; `verify-phase-9e-database.py` |
| `ATT-JS-09` | Payroll roster reads use the published 10H projection. | `verify-phase-10h-database.py`; `verify-phase-9e-database.py` |
| `ATT-JS-10` | Draft commands belong to 10G and publication commands to 10H. | `verify-phase-10g-database.py`; `verify-phase-10h-database.py` |
| `ATT-JS-11` | Schedule reads belong to 10H and swap commands to 10I. | `verify-phase-10h-database.py`; `verify-phase-10i-database.py` |
| `ATT-JS-12` | Daily calculation moved to 10D; closed aggregation moved to 10F. | `test_attendance_calculation.py`; `verify-phase-10f-database.py` |
| `ATT-JS-13` | Biometric persistence and deduplication moved to 10C; parsing is presentation-only. | `verify-phase-10c-database.py`; `migration-attendance-ingestion.test.js` |
| `ATT-JS-14` | Phase 7 remains the staffing-rule writer; 10G is read-only. | `verify-phase-10g-database.py`; `verify-phase-7e-database.py` |
| `ATT-UI-01` | Migration attendance views route settings, events, calculation, exceptions, and close to 10B-10F APIs. | Phase 10 client tests; `verify-phase-3g-browser.mjs` |
| `ATT-UI-02` | Migration biometric import uses the bounded 10C API. | `migration-attendance-ingestion.test.js`; `verify-phase-3g-browser.mjs` |
| `ATT-UI-03` | Migration roster views use 10B, 10G, 10H, and 10I APIs. | Phase 10 roster client tests; `verify-phase-3g-browser.mjs` |
| `ATT-UI-04` | Personal attendance uses 10D reads and 10E correction requests. | Phase 10 attendance client tests; `verify-phase-3g-browser.mjs` |
| `ATT-UI-05` | Personal schedule uses 10H reads and 10I swap submission. | `test_roster_publication_api.py`; `migration-shift-swaps.test.js` |
| `ATT-UI-06` | The personal today summary uses the self-only 10D projection. | `verify-phase-10d-database.py`; `test_attendance_records_api.py` |
| `ATT-UI-07` | Employee editing consumes the safe active-shift projection from 10B. | `migration-attendance-configuration.test.js` |
| `ATT-UI-08` | Dashboard replacement remains assigned to Phase 12; Phase 10 exposes source projections only. | `phase-10j-boundary.test.js` inventory and Supabase scan |
| `ATT-UI-09` | Reports and exports remain assigned to Phase 12. | `phase-10j-boundary.test.js` inventory trace |
| `ATT-UI-10` | Phase 9E keeps browser payroll calculation frozen and consumes internal projections only. | `phase-9e-legacy-freeze.test.js`; `verify-phase-9e-database.py` |
| `ATT-UI-11` | Department staffing administration remains under the completed Phase 7 boundary. | `verify-phase-7e-database.py`; `verify-phase-10g-database.py` |
| `ATT-UI-12` | Notification producers and presentation remain assigned to Phase 12. | `phase-10j-boundary.test.js` inventory trace |
| `ATT-UI-13` | Task aggregation remains assigned to Phase 12; Phase 10 exposes safe workflow reads only. | `phase-10j-boundary.test.js` inventory trace |
| `ATT-DB-01` | 10B owns constrained, branch-scoped attendance settings. | `verify-phase-10b-revision.py`; `verify-phase-10b-database.py` |
| `ATT-DB-02` | 10B owns validated shifts and retained-use behavior. | `verify-phase-10b-revision.py`; `verify-phase-10b-database.py` |
| `ATT-DB-03` | 10B owns nonoverlapping effective-dated shift assignments. | `verify-phase-10b-database.py` |
| `ATT-DB-04` | 10C owns append-only event provenance and normalized biometric methods. | `verify-phase-10c-revision.py`; `verify-phase-10c-database.py` |
| `ATT-DB-05` | 10C owns badge mappings and import-batch provenance. | `verify-phase-10c-database.py` |
| `ATT-DB-06` | 10D-10F own versioned calculation, correction, and closed snapshots. | `verify-phase-10d-database.py`; `verify-phase-10f-database.py` |
| `ATT-DB-07` | 10E owns versioned correction evidence and decisions. | `verify-phase-10e-revision.py`; `verify-phase-10e-database.py` |
| `ATT-DB-08` | 10F owns immutable close versions and amendments. | `verify-phase-10f-revision.py`; `verify-phase-10f-database.py` |
| `ATT-DB-09` | 10E and 10F append constrained attendance-domain audit actions. | `verify-phase-10e-database.py`; `verify-phase-10f-database.py` |
| `ATT-DB-10` | 10G owns drafts; 10H owns immutable publication versions and memberships. | `verify-phase-10g-database.py`; `verify-phase-10h-database.py` |
| `ATT-DB-11` | 10I replaces swap execution under the publication-version contract. | `verify-phase-10i-revision.py`; `verify-phase-10i-database.py` |
| `ATT-DB-12` | Phase 7 staffing rules are a read-only 10G input. | `verify-phase-10g-database.py` |
| `ATT-DB-13` | Phase 8 leave, holiday, and Ramadan data are read-only Phase 10 inputs. | `verify-phase-10d-database.py`; `verify-phase-10g-database.py` |
| `ATT-DB-14` | Phase 7 employee, salary, department, and branch state are read-only inputs. | Phase 10 database verifiers; authorization tests |
| `ATT-DB-15` | 10G narrows immutable roster compliance overrides to exact rule digests. | `verify-phase-10g-database.py` |
| `ATT-RPC-01` | Replaced by the 10E correction request API; legacy RPC use is frozen. | `verify-phase-10e-database.py`; `phase-10e-legacy-freeze.test.js` |
| `ATT-RPC-02` | No portal clock command is exposed in migration scope. | `phase-10c-legacy-freeze.test.js`; migration-source scan |
| `ATT-RPC-03` | Replaced by one 10H personal schedule projection. | `verify-phase-10h-database.py`; `test_roster_publication_api.py` |
| `ATT-RPC-04` | Replaced by the eligible same-branch 10H colleague selector. | `verify-phase-10h-database.py` |
| `ATT-RPC-05` | Replaced by protected 10I submission. | `verify-phase-10i-database.py`; `migration-shift-swaps.test.js` |
| `ATT-RPC-06` | Exact 10H definition is retained for rollback; 10I owns current execution. | `verify-phase-10i-revision.py`; `verify-phase-10i-database.py` |
| `ATT-EXT-01` | 10C accepts bounded synthetic request data; production storage remains Phase 11. | `verify-phase-10c-database.py`; request-size tests |
| `ATT-EXT-02` | 10F supplies the closed attendance payroll projection. | `verify-phase-10f-database.py`; `verify-phase-9e-database.py` |
| `ATT-EXT-03` | 10H supplies the published roster payroll projection. | `verify-phase-10h-database.py`; `verify-phase-9e-database.py` |
| `ATT-EXT-04` | Reports, exports, dashboards, tasks, and notifications remain assigned to Phase 12. | `phase-10j-boundary.test.js` inventory trace |
| `ATT-EXT-05` | Final legacy and Supabase removal remains assigned to Phase 13. | `phase-10j-boundary.test.js` migration-source scan |

## Golden-case proof map

| ID | Automated proof |
| --- | --- |
| `CFG-01` | `verify-phase-10b-database.py` settings replacement and persisted day partition |
| `CFG-02` | `test_attendance_configuration_service.py` strict day-partition validation |
| `CFG-03` | `verify-phase-10b-database.py` secret omission and configured-state projection |
| `CFG-04` | `test_attendance_configuration_service.py` fixed-shift validation |
| `CFG-05` | `test_attendance_configuration_service.py`; `test_attendance_calculation.py` overnight ownership |
| `CFG-06` | `test_attendance_configuration_service.py`; split-shift calculation test |
| `CFG-07` | `test_attendance_configuration_service.py`; flexible-shift calculation test |
| `CFG-08` | `verify-phase-10b-database.py` effective-dated assignment replacement |
| `CFG-09` | `verify-phase-10b-database.py` concurrent overlap rejection |
| `CFG-10` | `verify-phase-10b-database.py` retained-shift rejection |
| `EVT-01` | `verify-phase-10c-database.py` manual append-only events and trusted actor |
| `EVT-02` | `verify-phase-10c-database.py` biometric method normalization |
| `EVT-03` | `verify-phase-10c-database.py` fingerprint duplicate outcome |
| `EVT-04` | `verify-phase-10c-database.py` minute-tolerance duplicate outcome |
| `EVT-05` | `verify-phase-10c-database.py` mixed accepted and unknown-badge outcomes |
| `EVT-06` | `test_attendance_ingestion_api.py` and schema bounds for row and byte limits |
| `EVT-07` | `test_attendance_calculation.py` overnight start-date ownership |
| `EVT-08` | `verify-phase-10d-database.py` late event marks an open source stale |
| `EVT-09` | `verify-phase-10f-database.py` closed evidence creates an amendment without rewriting version 1 |
| `ATT-01` | `test_attendance_calculation.py` standard-day decimal calculation |
| `ATT-02` | `test_attendance_calculation.py` late status and six chargeable minutes |
| `ATT-03` | `test_attendance_calculation.py` early-departure grace calculation |
| `ATT-04` | `test_attendance_calculation.py` four-hour half day |
| `ATT-05` | `test_attendance_calculation.py` missing-clock-out blocker |
| `ATT-06` | `test_attendance_calculation.py`; `verify-phase-10f-database.py` close blocker |
| `ATT-07` | `test_attendance_calculation.py` approved-leave precedence |
| `ATT-08` | `test_attendance_calculation.py` public-holiday status |
| `ATT-09` | `test_attendance_calculation.py`; `verify-phase-10f-database.py` weekend status |
| `ATT-10` | `test_attendance_calculation.py` approved WFH result |
| `ATT-11` | `test_attendance_calculation.py` Ramadan six-hour expectation |
| `ATT-12` | `verify-phase-10d-database.py` required-day streak across the intervening weekend |
| `MNY-01` | `test_attendance_calculation.py`; `verify-phase-10f-database.py` AED 400.00 absence |
| `MNY-02` | `test_attendance_calculation.py`; `verify-phase-10f-database.py` AED 144.23 standard overtime |
| `MNY-03` | `test_attendance_calculation.py` AED 173.08 night overtime |
| `MNY-04` | `test_attendance_calculation.py` AED 173.08 rest-day overtime |
| `MNY-05` | `test_attendance_calculation.py` zero overtime with a rest-day substitute |
| `MNY-06` | `test_attendance_calculation.py`; `verify-phase-10f-database.py` AED 7.50 minute deduction |
| `MNY-07` | `test_attendance_calculation.py` AED 25.00 per-occurrence deduction |
| `CLS-01` | `verify-phase-10f-database.py` first atomic close and audit |
| `CLS-02` | `verify-phase-10f-database.py` unresolved blockers reject close |
| `CLS-03` | `verify-phase-10f-database.py` concurrent close serialization |
| `CLS-04` | `test_attendance_periods_api.py` idempotency fingerprint conflict |
| `CLS-05` | `verify-phase-10f-database.py` linked immutable amendment |
| `ROS-01` | `verify-phase-10h-database.py` publication version 1 and source digest |
| `ROS-02` | `verify-phase-10g-database.py` leave conflict and exact override |
| `ROS-03` | `verify-phase-10g-database.py` staffing shortfall count and requirement |
| `ROS-04` | `verify-phase-10g-database.py` disabled-staffing result |
| `ROS-05` | `verify-phase-10h-database.py` stale publication rejection and rollback |
| `ROS-06` | `verify-phase-10h-database.py` AED 288.46 approved roster overtime |
| `ROS-07` | `verify-phase-10h-database.py` attendance-overlap payroll fail-closed result |
| `ROS-08` | `verify-phase-10h-database.py` append-only actual-hours evidence and source increment |
| `ROS-09` | `verify-phase-10i-database.py` exact two-row successor publication |
| `ROS-10` | `verify-phase-10i-database.py` payroll-frozen source rejection with unchanged state |
| `ROS-11` | `verify-phase-10i-database.py` concurrent approval creates one successor version |
| `PAY10-01` | `verify-phase-10f-database.py` exact attendance projection amounts and sorted IDs |
| `PAY10-02` | `verify-phase-10f-database.py` open, stale, and unready fail-closed paths |
| `PAY10-03` | `verify-phase-10h-database.py` exact roster payroll projection |
| `PAY10-04` | `verify-phase-10h-database.py` missing evidence, overlap, and stale fail-closed paths |
| `PAY10-05` | `verify-phase-9f-database.py` stale source approval and generation rejection |

## Cutover and rollback proof

`tests/phase-10j-boundary.test.js` validates all eight cutover records through the shared validator,
requires completed status, and requires one writable system. It also checks the documented reverse
rollback order: swaps, roster publication and payroll projection, roster drafts and gates,
attendance close and payroll projection, corrections and approvals, calculation and reads, event
ingestion, then configuration. A legacy writer must never be restored while its FastAPI counterpart
is writable.

The workflow runs every `verify-phase-10b-revision.sh` through
`verify-phase-10i-revision.sh` predecessor check and every corresponding database verifier. The
revision checks prove deterministic downgrade and re-upgrade behavior without discarding retained
business data.

## Gate evidence

The final local gate uses a fresh isolated stack and the locked runtime versions. It runs all
backend and frontend tests, Ruff lint and formatting, strict Pyright, ESLint, the production build,
repeatable migrations, schema and model drift checks, all historical security and rollback checks,
all Phase 10 database verifiers, authentication checks, persistence fingerprints across a restart
without rebuild, and the browser-backed role journeys.

The restart comparison covers PostgreSQL, Keycloak signing keys, and synthetic storage. Cleanup
requires zero synthetic organization, identity, attendance, payroll, roster, swap, mapping, event,
and period rows; removal of temporary Keycloak credentials; safe backend logs; and removal of the
disposable containers, networks, and volumes.

## Resource boundary

Only synthetic local data and disposable Phase 10J resources are permitted. The protected volume
`workloop-clinic_postgres_data` is not attached, modified, deleted, or recreated.

## Writing review

The repository-required `.opencode/skill/unslop/SKILL.md` is absent. New prose received a manual
review for direct language, concrete claims, sentence-case headings, and consistent terms.

## Authorization boundary

The project owner signed off Phase 10 on 2026-09-22 after commit
`bd0145d03b466b1831af2b1ac6fa4503a35d4932` and GitHub Migration foundation run
`35712919139` passed. Phase 11 planning is authorized. Phase 11 implementation remains
unauthorized.
