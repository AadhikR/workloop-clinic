# Phase 11 subphase plan

## Status

Phase 10 is complete at commit `bd0145d03b466b1831af2b1ac6fa4503a35d4932`. GitHub Migration
foundation run `35712919139` passed on 2026-09-22, and the project owner signed off Phase 10 on
2026-09-22.

The project owner authorized sequential execution of the consolidated Phase 11 parts 11A through
11H on 2026-09-22. This standing authorization covers local implementation, synthetic verification,
cutover preparation, commits, pushes, and routed GitHub checks. It does not authorize a cloud
resource, paid service, production data, real employee file, or legal-policy decision.

This document splits Phase 11 into eight parts, 11A through 11H. Each part must finish its focused
verification, boundary-matched local gate, commit, push, and routed GitHub checks before the next
part starts. Execution is sequential, not concurrent.

## Why Phase 11 needs subphases

Phase 11 combines private object storage with ten business areas that have different permissions,
retention rules, lifecycle states, and rollback risks. PostgreSQL and object storage cannot share a
transaction. Employee documents and certifications require review workflows, assets retain assignment
history, appraisals aggregate weighted sections, incidents retain clinical history, and offboarding
consumes settled state from workforce, leave, payroll, advances, contracts, and assets.

A single cutover would make storage recovery, document access, clinical history, and final settlement
share one rollback. Phase 11 therefore settles the common contract first, completes shared storage
recovery second, migrates each domain independently, and leaves offboarding until every source it
consumes is stable. The last part reviews the whole boundary independently.

## Starting point

- Phase 4 supplies the canonical tables, constraints, relationships, and status vocabularies for
  employee documents, insurance, contract history, offboarding, assets, training, certifications,
  CME, appraisals, incidents, and letter requests.
- Phase 5 supplies selected-branch, employee-self, direct-report, workflow, history, RLS, grant,
  protected-function, storage-outbox, and reconciliation boundaries.
- Phase 6 supplies HTTP, request-size, camelCase projection, pagination, error, idempotency, and
  frontend-client conventions.
- Phase 7 supplies trusted company, branch, employee, manager, employment, salary, bank, job-history,
  and portal-role state. Contract lifecycle and offboarding remain deliberately outside Phase 7.
- Phase 8 supplies approved leave, leave balances, leave-attachment metadata, the provider-neutral
  object-storage interface, a persistent synthetic provider, the Spaces adapter contract,
  `storage_operations`, and the storage reconciler.
- Phase 9 supplies approved expenses, expense receipts, advances, repayments, finalized payroll, and
  payslip snapshots. It leaves final settlement and complete receipt recovery to Phase 11.
- Phase 10 supplies closed attendance and published roster state. Phase 11 may read those only if an
  approved contract needs them; it must not mutate attendance or roster state.
- Leave attachments and expense receipts already use the shared private-storage interface. Phase 11
  must include them in common recovery proof without reopening their domain permissions.
- The migration build has no Phase 11 documents, insurance, contracts, assets, training,
  certifications, appraisals, incidents, requests, or offboarding screens.
- The retained legacy boundary is concentrated in `src/utils/storage.js`, `assetStorage.js`,
  `trainingStorage.js`, `appraisalStorage.js`, `incidentStorage.js`, `letterStorage.js`,
  `gratuityCalculator.js`, and their administrator, manager, and employee React consumers.

## Part status

| Part | Scope | Status |
| --- | --- | --- |
| 11A | Contracts, dependency inventory, golden cases, amendments, and cutover decisions | Authorized next; not started |
| 11B | Common private storage, malware boundary, recovery, backup, and operator proof | Sequentially authorized |
| 11C | Employee documents, insurance, and employment-contract lifecycle | Sequentially authorized |
| 11D | Assets, training, certifications, certificate files, and CME | Sequentially authorized |
| 11E | Appraisals and clinical incidents | Sequentially authorized |
| 11F | Letter and custom requests, decisions, and print projection | Sequentially authorized |
| 11G | Offboarding, checklist execution, final settlement, and completion | Sequentially authorized |
| 11H | Independent review, complete cutover proof, and Phase 11 gate | Sequentially authorized |

## Rules shared by every part

- Use synthetic local data and synthetic files only. Production data, real employee documents,
  cloud resources, paid services, malware-scanning services, legal interpretations, retention
  schedules, RPO, and RTO need explicit project-owner approval.
- PostgreSQL remains authoritative for object metadata, domain ownership, workflow state, history,
  outbox intent, and reconciliation state. Provider listing is never an ownership or orphan source.
- An object key, filename, download URL, employee ID, or browser-supplied company or branch ID grants
  no authority. FastAPI derives scope and authorizes every upload, download, signing, review, and
  delete operation before contacting storage.
- Private objects use non-guessable server-generated keys without personal names. Responses never
  expose an object key, provider credential, storage endpoint secret, signed token, or unrelated
  employee metadata.
- Accept only the approved detected file types and bounded sizes. Compare declared media type,
  extension, and file signature. Normalize display filenames separately from object keys.
- Real files remain unavailable until the approved malware result permits release. Scanner timeout,
  error, unknown result, or stale result fails closed. Logs contain stable operation IDs and safe
  error codes, never bytes, keys, filenames, signed URLs, medical details, or free-text evidence.
- PostgreSQL and storage changes use the existing durable-operation contract. Reserve an attempt
  before the provider call, enforce the eight-attempt ceiling, preserve terminal failures, and use
  an approved operator procedure for any manual requeue.
- Every mutation has one transaction owner. Failure leaves domain rows, history, audit,
  idempotency, object metadata, and durable cleanup intent in an explainable recoverable state.
- Protected commands use the Phase 6 idempotency contract. Mutable rows use a locked state check and
  an expected version or timestamp. Concurrent commands cannot review, assign, return, close,
  calibrate, settle, or complete the same state twice.
- The server derives actors, timestamps, business dates, employee relationships, branch scope,
  workflow states, money, and ratings. Request bodies cannot assign review actors, completion actors,
  tenant scope, final states, or calculated totals.
- Use `Decimal` and PostgreSQL `NUMERIC` for premiums, asset cost, training cost, leave encashment,
  gratuity, deductions, and settlement. Round only at the contract's named boundary.
- Historical contract events, asset assignments, verified documents, verified certifications,
  appraisals, incident reports, final settlements, and completed checklists are retained. Ordinary
  hard deletion cannot erase evidence.
- Every cutover record names one read authority, one write authority, a frozen opposite path, and a
  reverse rollback order. Dual writes are forbidden.
- Follow `docs/migration/VERIFICATION_WORKFLOW.md`. Use focused checks during development, run one
  boundary-matched local gate when a part settles, push once, and wait for every routed GitHub job.

## Cross-phase boundaries

Phase 11 owns the common production-storage and recovery boundary, employee documents, insurance,
contract history, assets, training, certifications, CME, appraisals, incidents, letter requests,
offboarding, and final settlement.

The following owners remain unchanged:

- Phase 7 owns employee identity, employment state, manager relationships, salary, bank, and job
  history. Phase 11 consumes strict projections and uses named Phase 7 workflows for any approved
  employment-state transition.
- Phase 8 owns leave policy, leave balances, leave decisions, and leave-attachment permissions.
  Phase 11 owns shared provider recovery and may consume an approved leave-encashment projection for
  final settlement.
- Phase 9 owns expenses, receipts, advances, repayments, payroll, and payslips. Phase 11 owns common
  receipt recovery and may consume settled advance and finalized-payroll projections for offboarding.
- Phase 10 owns attendance and roster state. Phase 11 has no authority to repair or recalculate it.
- Phase 12 owns notifications, tasks, dashboards, reports, expiry generation, CSV, PDF, ZIP, SIF,
  and other generated file bytes. Phase 11 exposes strict source projections only.
- Phase 13 owns final Supabase runtime removal and migration-build promotion.
- Phases 14 and 15 own broader DigitalOcean operations, full-system disaster recovery, and Azure
  handoff. Phase 11 proves the storage-specific recovery contract needed by those phases.

No migration Phase 11 route may call Supabase. A later-phase consumer may remain in the legacy build,
but a migration Phase 11 flow must use an approved FastAPI projection or fail closed.

## 11A: Contracts, inventory, golden cases, and cutover decisions

### Objective

Resolve authority, file safety, domain behavior, final-settlement policy, and rollback before adding
a route or changing a writer.

### Scope

- Inventory every legacy reader, writer, RPC, converter, calculator, bucket path, signed URL,
  component, task, notification, dashboard, report, print path, and indirect caller in Phase 11.
- Trace every dependency to Parts 11B through 11G or to an explicit Phase 12 or 13 owner. Include
  Phase 8 leave attachments and Phase 9 receipts in shared recovery ownership.
- Define strict request and response contracts for administrators, managers, employees, storage
  workers, and approved scheduled jobs. Fix filters, sort order, pagination, nulls, dates, decimals,
  safe errors, and redaction.
- Decide exact file categories, limits, detected types, quarantine states, malware-result expiry,
  signed-URL lifetime, retention, deletion, backup, recovery, credential rotation, RPO, RTO,
  monitoring, and operator escalation. Separate local proof from any real Space proof.
- Define lifecycle and concurrency rules for documents, insurance, contracts, assets, training,
  certifications, CME, appraisals, incidents, letter requests, and offboarding.
- Define final-settlement inputs and reviewed golden cases. Do not infer UAE gratuity, leave
  encashment, notice, deduction, repayment, or rounding policy where the repository has no approved
  legal decision.
- Decide whether any Phase 11 flow needs an append-only table, version, audit action, storage state,
  function, role, grant, RLS policy, constraint, or index beyond the approved Phase 4 and 5 design.
  Prepare exact amendment proposals before implementation.
- Prepare independent cutover records and reverse rollback order. No record changes authority in
  11A.

### Completion gate

The inventory has no unexplained dependency. Contracts, golden cases, storage decisions, policy
stops, amendment proposals, cutover records, and rollback order are complete and internally
consistent. Documentation checks and the routed GitHub workflow pass. The project owner explicitly
approves the contract before 11B begins.

### Rollback boundary

11A changes documentation only. Revert the contract documents and draft cutover records. Do not
change a database, object, credential, service, or authority during rollback.

## 11B: Common private storage and recovery

### Objective

Complete the shared production-ready object-storage boundary without changing a domain's business
permissions.

### Scope

- Review the existing provider-neutral interface, persistent synthetic provider, Spaces adapter,
  factory, outbox, reconciler, and leave and expense integrations against the approved 11A contract.
- Enforce private bucket policy, blocked public ACLs and listing, TLS, bounded streaming, conditional
  create, exact metadata, provider timeouts, narrow credentials, rotation, and secret-only server
  configuration.
- Add the approved malware-scanner interface and quarantine or release state. Make real-file
  availability fail closed until a current clean result exists.
- Complete missing-object, orphan-object, incomplete-delete, crash-before-call, crash-during-call,
  crash-after-call, expired-lease, terminal-failure, purge, alert, and approved manual-requeue proof.
- Include leave attachments and expense receipts in recovery and restore tests without changing
  their Phase 8 or 9 authorization contracts.
- Add encrypted storage snapshot, restore, integrity, RPO, RTO, credential-rotation, monitoring, and
  operator runbooks under the approved resource boundary.
- Use an approved local S3-compatible target for provider contract tests. Do not create or contact a
  real DigitalOcean Space unless the project owner separately authorizes the exact resource, region,
  cost, credential, backup target, and cleanup plan.

### Completion gate

Interface parity, privacy, conditional create, signing expiry, scanner fail-closed behavior, retries,
terminalization, reconciliation, backup, restore, rotation, and safe logging pass against synthetic
and approved S3-compatible local targets. Database and object state survive restart. No public URL,
listing, credential, key, or private metadata leaks.

### Rollback boundary

Disable new provider traffic before restoring the previously approved adapter configuration.
Preserve domain metadata and operation rows. The shared adapter cannot roll back independently while
any Phase 8, 9, or 11 consumer still depends on it.

## 11C: Employee documents, insurance, and employment contracts

### Objective

Move employee document metadata, private files, review, signing, retention, and guarded deletion.

### Scope

- Add selected-branch administrator document reads, upload, verified creation, employee-submission
  review, rejection with reason, authorized signing, and guarded deletion under the 11A contract.
- Add employee self list, upload, pending submission, authorized signing, and safe review-state
  reads. Managers receive no direct-report document access unless 11A explicitly approves it.
- Derive employee, company, branch, submitter, reviewer, object key, detected type, digest, byte count,
  normalized filename, timestamps, and review state on the server.
- Retain verified rows. Allow deletion only for approved pending or rejected cases and write durable
  object cleanup intent in the same transaction as metadata removal or tombstoning.
- Add migration administrator and employee document views. Leave expiry notifications, dashboard
  cards, tasks, reports, and generated exports to Phase 12.
- Freeze legacy employee-document RPCs, bucket uploads, signed reads, review, and delete paths only
  after the document cutover passes.

### Completion gate

Administrator and self scope, file validation, malware release, upload, signing, expiry, review,
rejection, retention, delete cleanup, replay, changed payload, concurrency, cross-branch, cross-tenant,
and restart cases pass. No object key or unauthorized employee metadata reaches the browser.

### Rollback boundary

Disable migration upload and signing before restoring the legacy document path. Preserve verified
metadata, review history, object state, and cleanup operations. Never delete a verified object merely
to simplify rollback.

## Insurance work within 11C

### Objective

Move branch insurance policies, employee coverage, dependants, and safe self-service reads.

### Scope

- Add selected-branch administrator policy list, create, update, and guarded delete with exact
  premium, renewal, broker, tier, and concurrency rules.
- Add administrator employee-coverage assignment or replacement. Lock policy, employee, and current
  coverage and validate branch, employment, effective dates, expiry, tier, member, and card data.
- Add administrator dependant create, update, list, and delete under the employee's selected branch.
- Add employee and manager self reads for their current safe coverage and linked policy projection.
  Do not expose another employee, branch-wide pricing, broker details, dependant data, or card values
  outside the approved self projection.
- Add migration policy, coverage, dependant, and self-service views. Notifications, tasks, expiry
  generation, dashboards, and reports remain Phase 12.
- Freeze matching legacy insurance readers and writers only after the cutovers pass.

### Completion gate

Premium decimals, dates, linked-policy scope, replacement, guarded delete, self projection,
dependants, stale updates, concurrency, branch isolation, redaction, and forced rollback pass.

### Rollback boundary

Disable migration insurance mutations before restoring legacy writers. Preserve current coverage and
dependants. Roll back insurance before employee documents only if the approved UI joins the two.

## Employment-contract work within 11C

### Objective

Move append-only contract history and named renewal, conversion, and non-renewal workflows.

### Scope

- Add selected-branch administrator contract-history reads. Staff contract-history reads remain
  unsupported unless 11A approves an exact safe projection.
- Add named `new`, `renewed`, `converted`, and `not_renewed` workflows. Lock the employee and current
  contract state, validate dates and allowed type transitions, and derive actor and timestamp.
- Update the employee's current contract fields through the approved Phase 7 workflow or one
  transaction owner. Append contract and job history without rewriting earlier contract events.
- Require idempotency and an expected current snapshot. Concurrent renewals cannot create two current
  outcomes or leave current employee fields inconsistent with history.
- Add migration administrator contract controls. Contract-expiry notifications, tasks, dashboard
  cards, reports, and generated contract files remain Phase 12.
- Freeze legacy contract lifecycle writers after the cutover passes.

### Completion gate

New, renewal, conversion, non-renewal, invalid transition, date, stale snapshot, replay, concurrent
command, current-field synchronization, history, audit, and rollback cases pass.

### Rollback boundary

Disable migration contract mutations before restoring legacy writers. Preserve all appended contract
and job-history rows. Never delete a contract event or reverse current employee fields without a
separately authorized compensating workflow.

## 11D: Assets, training, certifications, and CME

### Objective

Move asset inventory, assignment, return, state transitions, history, and employee self reads.

### Scope

- Add selected-branch administrator asset reads, create, ordinary edit, status transition, assignment,
  return, and guarded delete.
- Enforce unique nonempty branch asset codes, exact decimal purchase cost, allowed statuses, one open
  assignment, assignment and return dates, and retained assignment history.
- Lock asset, employee, and open assignment in deterministic order. Derive the actor and prevent
  cross-branch assignment, double assignment, return of an unassigned asset, and deletion after
  retained use.
- Add employee and manager self reads for currently and historically assigned assets under the
  approved safe projection. Direct-report inventory access requires an explicit 11A contract.
- Add migration administrator inventory and employee asset views. Tasks, notifications, dashboards,
  reports, and exports remain Phase 12.
- Freeze legacy asset and assignment paths only after the cutover passes.

### Completion gate

Create, edit, status, assign, return, history, guarded delete, stale state, replay, concurrent
assignment, decimal, cross-scope, self-read, audit, and forced rollback cases pass.

### Rollback boundary

Disable migration assignment and state writers before restoring legacy paths. Preserve assignment
history and current custody. Roll back offboarding before assets because offboarding may consume
unreturned-asset state.

## Training, certification, and CME work within 11D

### Objective

Move training lifecycle, certification review and private files, and CME targets and achieved hours.

### Scope

- Add selected-branch administrator training, certification, and CME reads and allowed maintenance.
  Use exact decimal hours and cost, date, score, passed-state, and status rules.
- Add employee self-enrolment and allowed self updates. Add manager direct-report training maintenance
  only under the Phase 5 `M1` boundary.
- Add employee and manager certification submission. Non-admin submissions start pending; admin
  creation starts verified. Add selected-branch administrator verify and reject commands.
- Reuse the 11B storage contract for certificate files. Derive object metadata and bind one object to
  one authorized training or certification record. Preserve verified certification evidence.
- Calculate achieved CME from approved completed training and expose the exact year target and gap.
  Do not let the browser persist a calculated total.
- Add migration administrator, manager, and employee training and certification views. Expiry jobs,
  notifications, tasks, dashboards, reports, and exports remain Phase 12.
- Freeze matching legacy training, certification, CME, and file paths after their cutovers pass.

### Completion gate

Role scope, self-enrolment, direct-report access, completion, decimal hours and costs, certificate
upload, malware release, review, rejection, retention, CME target and achieved totals, concurrency,
cleanup, and rollback pass.

### Rollback boundary

Disable migration file and certification mutations before training and CME writers. Preserve verified
certifications, completed training, object state, review history, and CME evidence.

## 11E: Appraisals and clinical incidents

### Objective

Move appraisal cycles, generated reviews, weighted sections, manager review, calibration, and closure.

### Scope

- Add selected-branch administrator cycle create, edit, activate, close, and guarded unused-draft
  delete under expected versions.
- Generate one appraisal per eligible employee and cycle with deterministic section templates and
  idempotent replay. Do not create duplicates under concurrent generation.
- Add employee self read and any self-rating path explicitly approved in 11A. Add manager direct-report
  reads and rating updates without exposing unrelated employees.
- Calculate weighted ratings on the server with approved decimal rules. Lock parent and sections so
  section changes advance the parent version and cannot race review or calibration.
- Add selected-branch administrator review and calibration. Derive reviewer, timestamps, status, and
  final rating. Closed cycles and calibrated reviews are retained.
- Add migration administrator, manager, and employee appraisal views. Notifications, tasks,
  dashboards, and reports remain Phase 12.
- Freeze matching legacy appraisal paths after the cutover passes.

### Completion gate

Cycle lifecycle, generation, eligibility, section weights, self and manager scope, weighted rating,
review, calibration, closure, guarded delete, stale state, concurrency, retention, and rollback pass.

### Rollback boundary

Disable migration calibration, review, rating, and cycle writers in that order before restoring
legacy paths. Preserve closed cycles, appraisals, sections, ratings, actors, and timestamps.

## Clinical-incident work within 11E

### Objective

Move incident reporting, investigation, corrective action, and retained closure history.

### Scope

- Add selected-branch administrator incident list, detail, create, ordinary update, investigation,
  corrective-action, and closure workflows with exact filters and deterministic ordering.
- Validate trusted branch employees for reporter and involved employee where present. Reject
  cross-branch references without disclosing whether the employee exists.
- Enforce incident type, severity, date, time, status, required closure evidence, and expected
  version. Derive closer and closure date.
- Treat incident descriptions, actions, causes, notes, and involved people as sensitive. Keep them
  out of logs, generic errors, unrelated role projections, dashboards, and tasks.
- Retain incident reports after creation. Ordinary hard delete remains unsupported.
- Add the migration administrator incident view. Phase 12 owns notifications, tasks, aggregates,
  reports, and exports.
- Freeze legacy incident writers and reads after the cutover passes.

### Completion gate

Create, investigate, correct, close, type, severity, employee scope, sensitive-field redaction, stale
state, concurrent close, retention, audit, error safety, and forced rollback pass.

### Rollback boundary

Disable migration incident mutations before restoring legacy paths. Preserve every report,
investigation, corrective action, closer, and closure date. Never reopen or delete an incident during
technical rollback.

## 11F: Letter and custom requests

### Objective

Move employee request submission and administrator decisions while leaving generated output bytes to
Phase 12.

### Scope

- Add employee and manager self submission and history for `letter` and `custom` requests. Derive the
  employee and trusted snapshot fields; validate exact letter type, purpose, subject, and detail
  bounds.
- Add selected-branch administrator queue, detail, complete, and reject with required reason.
  Derive action actor and timestamps and retain decided requests.
- Define a safe completed-request print projection from trusted employee and employer data. Do not
  render PDF, browser-download bytes, or arbitrary templates in Phase 11.
- Protect salary and personal fields from unrelated roles and logs. A generic missing response must
  not distinguish another employee's request.
- Add migration employee request and administrator queue views. Notifications, tasks, template
  rendering, PDF, and exports remain Phase 12.
- Freeze legacy request RPCs, writers, and reads after the cutover passes.

### Completion gate

Letter and custom validation, self scope, queue scope, completion, rejection, snapshot consistency,
safe print projection, stale state, replay, concurrent decision, redaction, and rollback pass.

### Rollback boundary

Disable migration request decisions and submissions before restoring legacy paths. Preserve completed
and rejected requests and their trusted snapshots. Do not change a decided request during rollback.

## 11G: Offboarding and final settlement

### Objective

Move checklist execution and produce one reviewed, auditable final settlement from stable upstream
sources.

### Scope

- Add selected-branch administrator checklist initialization from immutable templates, list, detail,
  custom task addition if approved, task completion, notes, visa-state transition, and final
  completion.
- Lock employee, checklist, tasks, open asset assignments, contract state, approved leave balance,
  finalized payroll source, salary advances, repayments, and other approved settlement inputs in a
  deterministic order or consume immutable source versions.
- Implement only the gratuity, leave encashment, notice, deduction, advance, asset, payroll, and
  rounding rules explicitly approved in 11A. Persist an immutable source snapshot and version for
  every calculated amount.
- Require all mandatory tasks and blocking returns or balances to settle before completion. A failed
  or stale completion leaves employee, checklist, tasks, settlement, advances, assets, audit, and
  idempotency unchanged.
- Coordinate any approved employment termination through the Phase 7 named workflow. Do not patch
  employee status directly or infer a termination date from the browser.
- Expose a strict settlement and offboarding-letter source projection. NOC, experience-letter, PDF,
  print, notification, task aggregation, dashboard, and report bytes remain Phase 12.
- Add migration administrator checklist and settlement views. Freeze legacy offboarding and
  gratuity writers only after the cutover passes.

### Completion gate

Checklist initialization, required and custom tasks, visa transitions, asset return, leave
encashment, gratuity, notice, advances, payroll, deductions, exact decimals, source versions, stale
inputs, concurrent completion, employment transition, audit, immutable settlement, replay, and
forced rollback pass against approved golden cases.

### Rollback boundary

Disable migration completion and settlement before task and checklist mutations, then restore legacy
paths only under the cutover record. Preserve completed checklists, settlements, source snapshots,
employment history, repayments, asset history, actors, and audit. Never undo a completed offboarding
by deleting evidence.

## 11H: Independent review and completion gate

### Objective

Prove the complete Phase 11 boundary before requesting Phase 11 signoff.

### Scope

- Review authorization, branch and self scope, direct-report access, sensitive-data disclosure,
  decimal arithmetic, transaction ownership, storage privacy, malware release, reconciliation, RLS,
  grants, protected functions, optimistic locking, idempotency, audit, retention, and rollback
  independently of the implementation passes.
- Trace every 11A inventory entry to a migrated route, an explicit Phase 12 or 13 owner, or a
  deliberately retained dependency. Prove that no migration Phase 11 path calls Supabase.
- Validate all cutover records, freeze guards, one-writer declarations, file cleanup, source
  versions, retained history, and reverse dependency rollback order.
- Prove every approved document, storage, insurance, contract, asset, training, certification, CME,
  appraisal, incident, request, and settlement golden case with exact intermediate values and source
  identities.
- Run one complete boundary-matched local Phase 11 gate in a fresh isolated environment. Prove
  append-only migration history, repeatable upgrade, exact predecessor restoration, and all changed
  RLS, grant, function, concurrency, storage, and recovery boundaries.
- Restart existing images without rebuilding. Compare database, Keycloak signing keys, synthetic
  storage, S3-compatible objects, malware state, and durable operations. Run the complete
  administrator, manager, and employee browser journey once after restart.
- Remove synthetic rows, files, credentials, containers, networks, buckets, and temporary volumes.
  Do not attach or modify `workloop-clinic_postgres_data`.
- Push the settled Phase 11 changes once and require every routed GitHub job before requesting owner
  signoff.

### Completion gate

Every Phase 11 feature has one read and write authority. Private objects are unavailable without
authorization and an approved malware state. Recovery, backup, restore, contracts, golden values,
restart, rollback, cutover, cleanup, and upstream integration proofs pass. Migration Phase 11 code
has no Supabase path. GitHub passes and the project owner signs off Phase 11.

### Rollback boundary

Use cutover records in reverse dependency order. Roll back offboarding first, then requests,
incidents, appraisals, training and certifications, assets, contracts, insurance, and employee
documents. Roll back the common storage adapter last and only after every Phase 8, 9, and 11 consumer
has a safe authorized provider path. Never restore a legacy writer while its FastAPI counterpart is
writable, and never delete retained evidence to simplify rollback.

## Recommended execution order

Execute `11A -> 11B -> 11C -> 11D -> 11E -> 11F -> 11G -> 11H`.

The contract settles before storage or domain changes. Shared storage and recovery settle before new
file consumers. Documents, insurance, contracts, assets, and training settle before offboarding may
consume them. Appraisals, incidents, and requests remain independent cutover units. Offboarding runs
last because it consumes workforce, leave, payroll, advance, contract, and asset state. The final
review runs only after every Phase 11 cutover is stable.
