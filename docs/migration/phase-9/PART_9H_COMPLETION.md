# Phase 9H completion

Status: independent review corrections, the final local gate, and the routed-verifier repair are
complete. The required GitHub result is pending the corrective push.

## Review result

The review found one implementation gap and three integration defects. PAY-03 named an approved
legacy `duCost` conversion but the converter did not exist. The new offline converter maps that
field to `leaveDeduction`, rejects conflicting or invalid values, and returns explicit conversion
evidence. It is not reachable from a migration HTTP route.

The cutover validator hashed local CRLF bytes even though the records use canonical LF digests. It
now normalizes text line endings before hashing and still rejects content changes. Live browser
proof also found lowercase UUID characters in automatic payroll adjustment codes and missing
idempotency replay-resource entries for compliance overrides and Nafis snapshots. Automatic codes
now use the contract's uppercase form. The append-only Phase 9H revision extends only the existing
idempotency constraint; its downgrade restores the exact Phase 9G allowlist.

No review finding requires a new product rule, legal or policy decision, role, grant, RLS policy,
protected function, or later-phase implementation. Phase 10 still owns attendance and roster source
state. Phase 11 still owns production storage recovery and offboarding settlement. Phase 12 still
owns files, reports, tasks, notifications, and downloads.

## Inventory trace

| ID | Verified disposition |
| --- | --- |
| `UI-01` | Migrated payroll state routes in 9D through 9G; Phase 12 retains files, reports, and notifications. |
| `UI-02` | Migrated payroll list, selection, and guarded deletion in 9D. |
| `UI-03` | Migrated draft calculation and save in 9D and automatic input refresh in 9E. |
| `UI-04` | Migrated administrator advance workflows in 9C. |
| `UI-05` | Migrated administrator expense workflows and receipt access in 9B. |
| `UI-06` | Migrated direct-manager expense queue and decisions in 9B. |
| `UI-07` | Migrated employee expense and receipt workflows in 9B. |
| `UI-08` | Migrated employee advance workflows in 9C. |
| `UI-09` | Migrated immutable payslip data in 9F; Phase 12 retains PDF generation and download. |
| `UI-10` | Migrated SIF input projection in 9G; Phase 12 retains file generation and download. |
| `UI-11` | Migrated Nafis snapshots in 9G; Phase 12 retains report output. |
| `UI-12` | Deliberately retained legacy dashboard consumer; Phase 12 owns its replacement. |
| `UI-13` | Deliberately retained legacy report and export consumer; Phase 12 owns its replacement. |
| `UI-14` | Deliberately retained offboarding consumer; Phase 11 owns final-settlement handling. |
| `UI-15` | Deliberately retained roster source; Phase 10 owns mutation and 9E fails closed without its projection. |
| `UI-16` | Deliberately retained task links; Phase 12 owns tasks and notifications. |
| `JS-01` | Replaced by FastAPI payroll reads in 9D and frozen in the legacy migration path. |
| `JS-02` | Replaced by FastAPI payroll mutations in 9D and frozen in the legacy migration path. |
| `JS-03` | Replaced by atomic payslip creation in 9F. |
| `JS-04` | Replaced by locked payroll transitions and history in 9F. |
| `JS-05` | Replaced by employee and administrator advance routes in 9C. |
| `JS-06` | Replaced by protected repayment operations in 9C and 9F. |
| `JS-07` | Replaced by WPS routes and protected transitions in 9G. |
| `JS-08` | Replaced by Nafis snapshot routes in 9G. |
| `JS-09` | Replaced by immutable compliance overrides in 9G. |
| `JS-10` | Replaced by trusted branch-bank refresh in 9D; generated runs stay immutable. |
| `JS-11` | Replaced by Decimal server calculation in 9D; browser calculation is preview-only. |
| `JS-12` | Replaced by server draft validation in 9D and frozen-source rechecks in 9F. |
| `JS-13` | Replaced by exact decimal schedules in 9C. |
| `JS-14` | Replaced by expense and receipt state in 9B and atomic payroll application in 9F. |
| `JS-15` | Replaced by deterministic SIF input rows in 9G; Phase 12 retains file bytes. |
| `JS-16` | Replaced by WPS validation and immutable overrides in 9G. |
| `JS-17` | Deliberately retained document generator; Phase 12 owns replacement. |
| `JS-18` | Deliberately retained report shaping and exports; Phase 12 owns replacement. |
| `JS-19` | Deliberately retained financial task storage; Phase 12 owns replacement. |
| `JS-20` | Deliberately retained financial notifications; Phase 12 owns replacement. |
| `JS-21` | Phase 8 remains source owner; 9E consumes the approved projection. |
| `JS-22` | Phase 10 owns attendance source state; 9E fails closed until its projection exists. |
| `JS-23` | Deliberately retained gratuity calculation; Phase 11 owns final settlement. |
| `DB-01` | Canonical PostgreSQL payroll tables are used by 9D through 9G. |
| `DB-02` | Canonical immutable payroll approval history is used by 9F. |
| `DB-03` | Canonical immutable payslip snapshots are used by 9F. |
| `DB-04` | Canonical advances and repayments are used by 9C and 9F. |
| `DB-05` | Canonical expense claims are used by 9B and 9F. |
| `DB-06` | Canonical WPS entry state is used by 9G. |
| `DB-07` | Canonical Nafis snapshots are used by 9G. |
| `DB-08` | Canonical immutable compliance overrides are used by 9G. |
| `DB-09` | Deliberately retained legacy schema reference; Alembic is authoritative. |
| `DB-10` | Legacy payslip migration is replaced by 9F and is not callable from migration routes. |
| `DB-11` | Legacy Nafis SQL is retained as reference; 9G uses the canonical schema. |
| `DB-12` | Legacy advance SQL is retained as reference; 9C uses the canonical schema. |
| `DB-13` | Legacy WPS SQL is retained as reference; 9G uses the canonical schema. |
| `DB-14` | Legacy expense SQL is retained as reference; 9B uses the canonical schema. |
| `DB-15` | Legacy approval SQL is retained as reference; 9F uses the canonical schema. |
| `DB-16` | Legacy tenant SQL is retained as reference; Phase 4, 5, and 7 scope is canonical. |
| `DB-17` | Legacy manager expense RPCs are replaced by 9B services. |
| `DB-18` | The canonical rejection-reason field is retained and enforced by 9C. |
| `DB-19` | Legacy security SQL is retained as reference; Phase 5 plus approved Phase 9 revisions are canonical. |
| `DB-20` | Legacy feature flags are replaced by the six completed cutover records. |
| `DB-21` | Legacy scheduling SQL is replaced by 9C schedule and repayment authority. |
| `DB-22` | Legacy employee request RPCs are replaced by 9B and 9C routes. |
| `DB-23` | Legacy employee expense RPC callers are frozen after 9B cutover. |
| `DB-24` | Legacy manager expense RPC callers are frozen after 9B cutover. |
| `DB-25` | Legacy employee advance RPC callers are frozen after 9C cutover. |
| `DB-26` | Protected `replace_payroll_entries` is deliberately retained behind 9D validation and locking. |
| `DB-27` | Protected `record_advance_repayment` is deliberately retained behind 9C and 9F validation and locking. |
| `DB-28` | Legacy browser financial RLS roots are not used by migration flows; service grants are authoritative. |
| `EXT-01` | Phase 9B uses the private-storage interface; Phase 11 retains provider and recovery ownership. |
| `EXT-02` | Browser receipt URLs are rejected as authority. |
| `EXT-03` | Replaced by five-minute authorized receipt downloads in 9B. |
| `EXT-04` | Phase 12 owns payslip PDF and ZIP bytes. |
| `EXT-05` | Phase 12 owns SIF bytes and download. |
| `EXT-06` | Phase 12 owns financial CSV and PDF reports. |
| `EXT-07` | Phase 12 owns financial task creation. |
| `EXT-08` | Phase 12 owns approval, finalization, and payslip notifications. |
| `EXT-09` | Phase 10 owns closed attendance and approved overtime source state. |
| `EXT-10` | Phase 10 owns published roster actual-hours source state. |
| `EXT-11` | Phase 8 owns approved leave inputs; 9E consumes its projection. |

## Golden-case proof map

| Case | Automated proof |
| --- | --- |
| `PAY-01` | Payroll unit tests assert every fixed, variable, deduction, gross, net, and WPS value. |
| `PAY-02` | Payroll unit tests assert original and recurring-only repeated values. |
| `PAY-03` | Offline converter tests assert mapping, evidence, conflicts, invalid money, and API rejection. |
| `PAY-04` | Payroll unit tests assert each joiner component and aggregate. |
| `PAY-05` | Payroll unit and Phase 9D database tests assert leaver components and exclusion. |
| `PAY-06` | Payroll unit tests assert every rounded component before aggregation. |
| `PAY-07` | Payroll unit and Phase 9F lifecycle tests assert the exact negative preview and blocked finalization. |
| `INP-01` | Phase 9E database tests assert leave source identity, replacement, and stale-source denial. |
| `INP-02` | Phase 9E database tests assert exact attendance additions, deduction, and readiness denial. |
| `INP-03` | Phase 9E database tests assert roster values, source identity, and duplicate-source denial. |
| `INP-04` | Phase 9E database tests assert the fail-closed Phase 10 boundary. |
| `EXP-01` | Phase 9B database and Phase 9F lifecycle tests assert the full paid-claim transaction and replay. |
| `EXP-02` | Phase 9B database tests assert optional manager review and actor separation. |
| `EXP-03` | Phase 9B database tests assert self, report, and branch denial with unchanged state. |
| `EXP-04` | Phase 9B receipt tests assert type detection, byte limits, expiry, cleanup, redaction, and signing. |
| `ADV-01` | Advance unit, Phase 9C database, and Phase 9F lifecycle tests assert equal schedules and payroll repayment. |
| `ADV-02` | Advance unit and Phase 9C database tests assert the rounded final installment and settlement. |
| `ADV-03` | Phase 9E database tests assert deterministic ordering and constrained pay capacity. |
| `ADV-04` | Phase 9C database tests assert decisions, withdrawal, concurrent repayment, and replay. |
| `APP-01` | Phase 9F lifecycle tests assert creator, submitter, approver separation and immutable history. |
| `APP-02` | Phase 9F lifecycle tests assert reject, refresh, resubmit, approve, and recall. |
| `APP-03` | Phase 9F lifecycle tests assert immutable payslips and atomic forced-failure rollback. |
| `WPS-01` | WPS unit and Phase 9G lifecycle tests assert integer values, totals, and ordering. |
| `WPS-02` | WPS unit tests assert independent basic and variable rounding. |
| `WPS-03` | Phase 9G lifecycle tests assert partial rejection and corrected rejected-only projection. |
| `CMP-01` | Phase 9G lifecycle and database tests assert closed codes, reasons, scope, and immutability. |
| `NAF-01` | Phase 9G lifecycle and authenticated browser tests assert trusted inputs, replay, API idempotency, and source-version replacement. |

## Authority and rollback result

All six cutover records are complete. Each names `migration-fastapi` as its only read and write
authority and freezes the corresponding legacy read and write path. Their evidence files, source
digests, identity mappings, status histories, and rollback steps validate. No migration source file
calls Supabase.

The dependency rollback order remains WPS and Nafis, payroll approval and payslips, payroll inputs,
payroll drafts and calculations, advances and repayments, then expenses. Each unit freezes the
migration writer before restoring a legacy writer.

## Gate evidence

The exact staged tree passed the boundary-matched local gate in a fresh isolated stack:

- all 499 backend tests, Ruff lint and format checks, Pyright, and dependency checks;
- all 180 frontend tests and the production build;
- the Phase 9H inventory, golden-case, cutover, conversion, and idempotency checks;
- the complete historical database, RLS, grant, security, seed, and Phase 9 lifecycle checks;
- empty-schema migration replay, repeatable head application, exact Phase 9H-to-9G rollback and
  replay, the complete historical exact-predecessor chain, and an Alembic current-head check;
- unchanged normalized database catalogue fingerprint, Keycloak signing-key identifiers, synthetic
  private-storage state, and PostgreSQL, backend, and Keycloak image digests after container
  recreation without rebuilding; and
- post-restart transaction-context isolation, Keycloak and FastAPI authentication, the complete
  employee, manager, and administrator browser journey, synthetic-data cleanup, and the service-log
  safety scan.

## GitHub result

The first routed run exposed stale current-head assertions in the historical database verifiers.
The repair tracks the Phase 9H head and adds a live Phase 9H-to-9G rollback/replay check. The required
result is pending the corrective push.

## Resource boundary

Verification uses synthetic local data only. The preserved volume
`workloop-clinic_postgres_data` was not attached, modified, deleted, or recreated. Its creation
timestamp remained `2026-08-31T07:31:48Z` before and after the gate.

## Stop condition

Phase 10 remains unauthorized. After the local and routed gates pass, stop and request explicit
project-owner Phase 9 signoff.
