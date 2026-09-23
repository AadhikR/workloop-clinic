# Phase 11H independent review

## Review status

The project owner authorized sequential execution through Phase 11H on 2026-09-22. This review
started from the completed Phase 11G baseline at commit
`88713c421e732cb693ce2a087d561fea433543d2`. It compared the approved Phase 11 contract and
amendments with current routes, schemas, services, repositories, migrations, frontend clients,
legacy guards, cutover records, evidence files, tests, and workflow routing. Earlier completion
records were treated as context, not as independent proof.

## Findings

### Finding 1: the post-restart browser journey omitted Phase 11

- Severity: High
- Evidence: `scripts/verify-phase-3g-browser.mjs` exercised organization, workforce, leave,
  payroll, attendance, and roster behavior, but it did not name or assert any Phase 11 screen,
  client, route, or cleanup table.
- Effect: Unit and database checks proved Phase 11 behavior, but the Phase 11H requirement for a
  complete administrator, manager, and employee browser journey after restart had no direct proof.
- Fix: Added an explicit three-role Phase 11 journey. It opens every Phase 11 screen, verifies
  scoped records, benefits, assets, development, appraisal, incident, request, and offboarding
  reads, submits employee and manager requests, completes them as an administrator, verifies their
  print sources, and exercises custom offboarding-task provenance. Cleanup now requires zero letter
  requests, offboarding checklists, offboarding tasks, and final settlements.
- State: Resolved. The post-restart administrator, manager, and employee browser journey passed with
  explicit Phase 11 coverage and zero synthetic rows after cleanup.

### Finding 2: request decisions compared a public millisecond token with private microseconds

- Severity: High
- Evidence: Letter-request responses serialize `requestedAt` to milliseconds, while the decision
  service compared that value with the database timestamp at full microsecond precision.
- Effect: A legitimate administrator complete or reject command could return `state_conflict` for a
  pending request created through the HTTP API.
- Fix: The service now compares both timestamps at the public millisecond boundary while retaining
  the pending-state lock. The Phase 11F database verifier sends the same timestamp precision as an
  HTTP client, and the browser journey completes and reads the print source for both submitted
  requests.
- State: Resolved. The strengthened database verifier, concurrency proof, and browser journey passed.

No review finding requires a new product policy, legal interpretation, cloud resource, schema
revision, role, grant, RLS policy, protected function, or Phase 12 feature.

## Inventory trace

| ID | Final disposition | Automated proof |
| --- | --- | --- |
| `P11-STO-01` | Retained as the sole provider-neutral object interface. | `test_phase11b_storage.py`; `verify-phase-11b-storage.py` |
| `P11-STO-02` | Retained for persistent synthetic storage, signing, backup, restore, and restart proof. | `verify-phase-11b-storage.py`; `verify-phase-11b-restart.py` |
| `P11-STO-03` | Retained as the S3-compatible adapter and tested only against the local target. | `test_phase11b_storage.py`; `verify-phase-11b-storage.py` |
| `P11-STO-04` | Extended with scanner and backup settings while keeping secrets server-only. | `test_phase11b_storage.py`; `phase-11b-compose.test.js` |
| `P11-STO-05` | Retained as the durable eight-attempt operation queue. | `verify-phase-11b-database.py` |
| `P11-STO-06` | Extended with missing-object classification, inspection, and bounded manual requeue. | `verify-phase-11b-database.py` |
| `P11-STO-07` | Phase 8 leave attachments use the shared scan and recovery boundary without permission changes. | `verify-phase-11b-database.py`; `verify-phase-8f-approval.py` |
| `P11-STO-08` | Phase 9 expense receipts use the shared scan and recovery boundary without permission changes. | `verify-phase-11b-database.py`; `verify-phase-9b-database.py` |
| `P11-STO-09` | Replaced by the complete Phase 11B storage and restart proof. | `verify-phase-11b-storage.py`; `verify-phase-11b-restart.py` |
| `P11-STO-10` | Legacy bucket paths are frozen for migrated domains; final runtime removal remains Phase 13. | Phase 11 legacy-freeze tests; migration Supabase scan |
| `P11-DOC-01` | Replaced by scoped document APIs and private-file workflows. | `verify-phase-11c-database.py`; `phase-11c-legacy-freeze.test.js` |
| `P11-DOC-02` | Replaced by the employee-self document projection. | `test_phase11c_contracts.py`; Phase 11H browser journey |
| `P11-DOC-03` | Direct bucket upload and submission RPC are frozen. | `phase-11c-legacy-freeze.test.js` |
| `P11-DOC-04` | Replaced by migration document administration. | `migration-records-benefits.test.js`; Phase 11H browser journey |
| `P11-DOC-05` | Retained with scan linkage, trusted review, and verified-row retention. | `verify-phase-11c-database.py` |
| `P11-INS-01` | Replaced by selected-branch insurance APIs. | `verify-phase-11c-database.py`; `phase-11c-legacy-freeze.test.js` |
| `P11-INS-02` | Replaced by migration policy administration; notifications remain Phase 12. | `migration-records-benefits.test.js`; Phase 11H browser journey |
| `P11-INS-03` | Replaced by migration coverage and dependant administration. | `test_phase11c_contracts.py`; Phase 11H browser journey |
| `P11-INS-04` | Retained with one current coverage, safe self projection, and optimistic locking. | `verify-phase-11c-database.py` |
| `P11-CON-01` | Generic writes are replaced by named append-only contract commands. | `verify-phase-11c-database.py`; `phase-11c-legacy-freeze.test.js` |
| `P11-CON-02` | Replaced by migration contract history and lifecycle controls. | `migration-records-benefits.test.js`; Phase 11H browser journey |
| `P11-CON-03` | Retained through one transaction owner with immutable prior events. | `verify-phase-11c-database.py` |
| `P11-AST-01` | Replaced by scoped inventory, custody, return, and history APIs. | `verify-phase-11d-database.py`; `phase-11d-legacy-freeze.test.js` |
| `P11-AST-02` | Replaced by migration asset administration. | `migration-development-assets.test.js`; Phase 11H browser journey |
| `P11-AST-03` | Replaced by the safe employee-self asset projection. | `verify-phase-11d-database.py`; Phase 11H browser journey |
| `P11-AST-04` | Retained with normalized codes, one open assignment, history, and locking. | `verify-phase-11d-database.py` |
| `P11-TRN-01` | Replaced by scoped training, certification, evidence, and CME APIs. | `verify-phase-11d-database.py`; `phase-11d-legacy-freeze.test.js` |
| `P11-TRN-02` | Replaced by migration administrator development controls. | `migration-development-assets.test.js`; Phase 11H browser journey |
| `P11-TRN-03` | Replaced under the direct-report boundary. | `verify-phase-11d-database.py`; Phase 11H browser journey |
| `P11-TRN-04` | Replaced by employee self-enrolment, submission, upload, and signed reads. | `test_phase11d_contracts.py`; Phase 11H browser journey |
| `P11-TRN-05` | Retained with trusted completion, verified evidence, and server-calculated CME. | `verify-phase-11d-database.py` |
| `P11-APP-01` | Replaced by versioned cycle, generation, rating, review, and calibration APIs. | `verify-phase-11e-database.py`; `phase-11e-legacy-freeze.test.js` |
| `P11-APP-02` | Replaced by migration appraisal administration. | `migration-appraisals-incidents.test.js`; Phase 11H browser journey |
| `P11-APP-03` | Replaced by manager direct-report and self projections under `M1` and `E1`. | `verify-phase-11e-database.py`; Phase 11H browser journey |
| `P11-APP-04` | Replaced by employee self history; self-rating remains unavailable. | `test_phase11e_contracts.py`; Phase 11H browser journey |
| `P11-APP-05` | Retained with fixed sections, parent locking, and exact weighted ratings. | `verify-phase-11e-database.py` |
| `P11-INC-01` | Generic mutation and hard delete are replaced by named retained workflows. | `verify-phase-11e-database.py`; `phase-11e-legacy-freeze.test.js` |
| `P11-INC-02` | Replaced by migration incident administration. | `migration-appraisals-incidents.test.js`; Phase 11H browser journey |
| `P11-INC-03` | Retained as sensitive branch-scoped clinical history. | `verify-phase-11e-database.py` |
| `P11-REQ-01` | Replaced by self history, administrator queue, and decision APIs. | `verify-phase-11f-database.py`; `phase-11f-legacy-freeze.test.js` |
| `P11-REQ-02` | Submission and reads moved to migration; rendered bytes remain Phase 12. | `migration-letter-requests.test.js`; Phase 11H browser journey |
| `P11-REQ-03` | Replaced by the migration administrator queue and decisions. | `test_phase11f_contracts.py`; Phase 11H browser journey |
| `P11-REQ-04` | Browser rendering is frozen; only the strict print-source projection remains. | `verify-phase-11f-database.py`; `phase-11f-legacy-freeze.test.js` |
| `P11-REQ-05` | Retained with trusted snapshots, scoped decisions, and immutable final states. | `verify-phase-11f-database.py` |
| `P11-OFF-01` | Replaced by provenance-aware checklist and task APIs. | `verify-phase-11g-database.py`; `phase-11g-legacy-freeze.test.js` |
| `P11-OFF-02` | Replaced by mandatory-task completion; letter bytes remain Phase 12. | `offboarding-api.test.js`; Phase 11H browser journey |
| `P11-OFF-03` | Browser calculations are replaced by the approved versioned settlement service. | `verify-phase-11g-database.py`; `phase-11g-legacy-freeze.test.js` |
| `P11-OFF-04` | Conflicting floating-point calculators now fail closed. | `phase-11g-legacy-freeze.test.js` |
| `P11-OFF-05` | EOS liability reporting remains Phase 12 and must consume the approved projection. | Phase 11H inventory trace and migration Supabase scan |
| `P11-OFF-06` | Extended with task provenance and immutable final-settlement linkage. | `verify-phase-11g-database.py` |
| `P11-OFF-07` | Consumed through the locked Phase 7 projection and named termination workflow. | `verify-phase-11g-database.py` |
| `P11-OFF-08` | Consumed as a read-only versioned annual-leave source. | `verify-phase-11g-database.py` |
| `P11-OFF-09` | Consumed as immutable payslip and outstanding-advance identities. | `verify-phase-11g-database.py` |
| `P11-OFF-10` | Current contract and open asset custody are locked blockers. | `verify-phase-11g-database.py` |
| `P11-LTR-01` | Dashboard cards remain assigned to Phase 12; Phase 11 exposes source projections only. | Phase 11H boundary test and migration Supabase scan |
| `P11-LTR-02` | Task aggregation remains assigned to Phase 12. | Phase 11H boundary test and migration Supabase scan |
| `P11-LTR-03` | Notification production and presentation remain assigned to Phase 12. | Phase 11H boundary test and migration Supabase scan |
| `P11-LTR-04` | Reports, archives, and rendered output remain assigned to Phase 12. | Phase 11H boundary test and migration Supabase scan |
| `P11-LTR-05` | Final Supabase runtime removal remains assigned to Phase 13. | Phase 11H migration-source scan |

## Golden-case proof map

| ID | Automated proof |
| --- | --- |
| `11A-G-STO-01` | `test_phase11b_storage.py` conditional-create conflict |
| `11A-G-STO-02` | `test_phase11b_storage.py` signature, trailer, and size validation |
| `11A-G-STO-03` | `verify-phase-11b-database.py` clean scan and signing lifetime |
| `11A-G-STO-04` | `verify-phase-11b-database.py` infected-file fail-closed behavior and safe logs |
| `11A-G-STO-05` | `verify-phase-11b-database.py` bounded retry and terminalization schedule |
| `11A-G-STO-06` | `verify-phase-11b-database.py` stale-scan requeue |
| `11A-G-STO-07` | `verify-phase-11b-database.py` orphan upload reconciliation |
| `11A-G-STO-08` | `verify-phase-11b-database.py` missing-object alert and metadata retention |
| `11A-G-STO-09` | `verify-phase-11b-storage.py` local snapshot and restore integrity |
| `11A-G-STO-10` | `verify-phase-11b-restart.py` database, key, object, and scan persistence |
| `11A-G-DOC-01` | `verify-phase-11c-database.py` employee upload, quarantine, self scope, and redaction |
| `11A-G-DOC-02` | `verify-phase-11c-database.py` trusted administrator creation and scan gate |
| `11A-G-DOC-03` | `verify-phase-11c-database.py` rejection replay and changed-payload conflict |
| `11A-G-DOC-04` | `verify-phase-11c-database.py` durable delete cleanup and verified retention |
| `11A-G-INS-01` | `verify-phase-11c-database.py` exact premium and safe self projection |
| `11A-G-INS-02` | `verify-phase-11c-database.py` concurrent coverage replacement |
| `11A-G-CON-01` | `verify-phase-11c-database.py` append-only renewal and current-field sync |
| `11A-G-CON-02` | `verify-phase-11c-database.py` conversion replay and stale renewal rejection |
| `11A-G-CON-03` | `verify-phase-11c-database.py` invalid-date transaction rollback |
| `11A-G-AST-01` | `verify-phase-11d-database.py` normalized code, exact cost, and uniqueness |
| `11A-G-AST-02` | `verify-phase-11d-database.py` assignment and concurrent custody exclusion |
| `11A-G-AST-03` | `verify-phase-11d-database.py` return history and guarded deletion |
| `11A-G-TRN-01` | `verify-phase-11d-database.py` bounded employee self-enrolment |
| `11A-G-TRN-02` | `verify-phase-11d-database.py` manager completion and relationship recheck |
| `11A-G-CERT-01` | `verify-phase-11d-database.py` pending quarantined certificate submission |
| `11A-G-CERT-02` | `verify-phase-11d-database.py` verified evidence retention |
| `11A-G-CME-01` | `verify-phase-11d-database.py` exact achieved and gap rounding |
| `11A-G-APP-01` | `verify-phase-11e-database.py` idempotent and concurrent generation |
| `11A-G-APP-02` | `verify-phase-11e-database.py` exact weighted rating |
| `11A-G-APP-03` | `verify-phase-11e-database.py` parent locking and stale review rejection |
| `11A-G-APP-04` | `verify-phase-11e-database.py` guarded cycle closure |
| `11A-G-INC-01` | `verify-phase-11e-database.py` retained critical incident and safe ordering |
| `11A-G-INC-02` | `verify-phase-11e-database.py` investigation, correction, closure, and replay |
| `11A-G-INC-03` | `verify-phase-11e-database.py` generic cross-branch employee denial |
| `11A-G-REQ-01` | `verify-phase-11f-database.py` trusted request snapshot and salary redaction |
| `11A-G-REQ-02` | `test_phase11f_contracts.py` exact custom-request length bounds |
| `11A-G-REQ-03` | `verify-phase-11f-database.py` concurrent immutable decision |
| `11A-G-REQ-04` | `verify-phase-11f-database.py` allowlisted completed print source |
| `11A-G-OFF-01` | `verify-phase-11g-database.py` replay-safe initialization and template provenance |
| `11A-G-OFF-02` | `verify-phase-11g-database.py` custom deletion and template retention |
| `11A-G-OFF-03` | `verify-phase-11g-database.py` mandatory-task and open-asset blockers |
| `11A-G-OFF-04` | `verify-phase-11g-database.py` forward-only visa transition |
| `11A-G-SET-01` | `verify-phase-11g-database.py` unsupported-policy fail-closed result |
| `11A-G-SET-02` | `verify-phase-11g-database.py` exact source identities and AED 59,666.66 net |
| `11A-G-SET-03` | `verify-phase-11g-database.py` stale source rejection with no writes |
| `11A-G-SET-04` | `test_phase11g_contracts.py` service-day gratuity boundaries |
| `11A-G-SET-05` | `test_phase11g_contracts.py` two-year basic-salary cap |
| `11A-G-SET-06` | `test_phase11g_contracts.py` half-up component rounding |
| `11A-G-SET-07` | `verify-phase-11g-database.py` negative-net blocker |
| `11A-G-SET-08` | `verify-phase-11g-database.py` independent completer requirement |

## Boundary review

Every Phase 11 route derives tenant, branch, employee relationship, actor, timestamp, workflow
state, and calculated amount on the server. Administrator selection, employee self scope, and
manager direct-report scope remain distinct. Sensitive clinical, salary, insurance, document, file,
and settlement fields stay out of unrelated projections and safe error responses.

Money, hours, ratings, premiums, costs, encashment, gratuity, and settlement totals use decimal
arithmetic with the contract's named rounding boundary. Protected mutations have one transaction
owner, lock mutable sources, enforce expected versions or immutable source digests, and include
idempotency, domain history, and protected audit in the same outcome. Retained evidence has no
ordinary hard-delete path.

Private object access requires domain authorization and a current clean scan before signing. Storage
operations retain bounded attempts, terminal failures, safe operator inspection, and recovery intent.
Provider listing grants no ownership. The migration source tree contains no Supabase import or call.

All ten cutover records validate, name `migration-fastapi` as the only reader and writer, freeze the
legacy path, and preserve the standard rollback steps. Reverse rollback is offboarding, requests,
incidents, appraisals, training and certifications, assets, contracts, insurance, employee
documents, then common storage. Migration writes freeze before any legacy writer can return.

## Final gate boundary

The Phase 11H local gate passed in a fresh isolated environment after both corrections. It covered
all backend and frontend tests, lint, formatting, strict types, builds, repeatable migrations, the
complete historical and Phase 11 database verifiers, authentication, restart persistence, the
corrected three-role browser journey, cleanup, and safe logs. All 605 backend tests and 255 frontend
tests passed. The isolated stack preserved its database fingerprint, Keycloak signing keys, stored
objects, and scan state across restart before the browser journey ran.

GitHub Migration foundation run `35911809133` passed every routed job on 2026-09-24. The remaining
Phase 11 completion condition is explicit project-owner signoff.

Only synthetic local data and disposable Phase 11H resources are permitted. The protected
`workloop-clinic_postgres_data` volume must not be attached, modified, deleted, or recreated.
