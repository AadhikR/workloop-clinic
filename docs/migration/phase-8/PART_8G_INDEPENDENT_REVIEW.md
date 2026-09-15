# Phase 8G independent review

## Review status

The project owner authorized Phase 8G on 2026-09-15. The read-only review started from clean,
synchronized branch `migration/fastapi-keycloak` at commit
`1c19972c058360d876802ff55439ed5163fef227`.

The review compared the approved Phase 8 contract and amendments with the current routes, schemas,
services, repositories, migrations, frontend clients, legacy guards, tests, cutover records, and
evidence files. It did not treat earlier completion records as proof.

## Findings

### Finding 1: four cutover records use an obsolete contract digest

- Severity: High
- Evidence: `PART_8A_DOMAIN_CONTRACT.md` now hashes to
  `1193ba0007aa23ad5840cf404d96d0eb46e02603cbd320891ea7baa38c6d87c1`. The configuration,
  balances and reads, attachments, and request submission records still name
  `9de8058d41693f4297f721324d7d947b0ee00b673dd5bae030400ef1ee245819`.
- Effect: The shared cutover validator rejects those four completed records. Their evidence-file
  hashes still match the stored evidence digests, but the records do not prove the current contract.
- Fix: Refreshed each affected record with the current contract digest, refresh timestamp, and
  evidence digest.
- State: Resolved. The shared validator accepts all five completed records.

### Finding 2: the Phase 8A verifier rejects the completed approval cutover

- Severity: Medium
- Evidence: `scripts/verify-phase-8a-contract.py` permits `completed` for four named records but not
  `leave-approval-workflows.json`. The verifier fails against the valid Phase 8F state.
- Effect: The complete Phase 8 contract check cannot pass after all five cutovers complete.
- Fix: Permit either `preparation` or `completed` for each of the five structurally valid records.
  Phase 8G separately requires every record to be completed.
- State: Resolved in `scripts/verify-phase-8a-contract.py` with regression coverage in
  `tests/phase-8g-boundary.test.js`.

The review found no implementation defect that requires a new leave policy, schema revision, role,
grant, RLS policy, protected function, status, or phase-boundary decision. The local gate remains
responsible for runtime proof of the reviewed database and browser behavior.

## Inventory trace

| Dependency ID | Current disposition |
| --- | --- |
| `phase8a-legacy-leave-storage` | Phase 8 configuration, balance, attachment, submission, decision, delegation, and audit exports fail closed. `getLeaveRequests` and the approved-month reader remain in the legacy graph only for Phase 9, Phase 10, and Phase 12 consumers. |
| `phase8a-legacy-leave-engine` | FastAPI owns Phase 8 day counts, accrual, carry-forward, sick tiers, and request validation. Payroll, attendance, and encashment helpers remain with Phases 9, 10, and 11. |
| `phase8a-admin-leave-screen` | `migration/src/LeaveOverview.jsx` owns the Phase 8 administration workflows. Legacy notification and export consumers remain assigned to Phase 12. |
| `phase8a-request-modal` | `migration/src/LeaveOverview.jsx`, `leaveAttachmentApi.js`, and `leaveRequestApi.js` replace the Phase 8 request and attachment flow. |
| `phase8a-employee-leave-screen` | `migration/src/LeaveOverview.jsx` and the leave clients replace Phase 8 employee reads, submission, cancellation, upload, and download. |
| `phase8a-manager-leave-queue` | `migration/src/LeaveOverview.jsx` and `leaveApprovalApi.js` replace the manager and delegate queue and decision flow. |
| `phase8a-settings-read-write` | `GET` and `PUT /api/v1/leave/settings` are the only Phase 8 settings authority. |
| `phase8a-types-read-seed-write` | `/api/v1/leave/types` supplies the scoped list, create, update, and seed operations. |
| `phase8a-holidays-read-seed-write` | `/api/v1/leave/holidays` supplies the scoped list, create, update, delete, and seed operations. |
| `phase8a-request-read-write` | Leave balance reads project requests, and the request and approval routes own every Phase 8 mutation. The retained legacy reader serves named later-phase consumers only. |
| `phase8a-audit-read-write` | Request and decision transactions append domain and protected audit together. The approval audit route returns the protected projection. |
| `phase8a-balance-read-write` | `/api/v1/leave/balances` and the initialization and recalculation commands own Phase 8 balance access. Legacy balance exports fail closed. |
| `phase8a-queue-read` | `/api/v1/leave/approvals/queue` and `/api/v1/leave/approvals/branch` own queue reads. |
| `phase8a-delegation-read-write` | `/api/v1/leave/delegations/branch` owns delegation list, create, update, and delete operations. |
| `phase8a-rpc-employee-submit` | `POST /api/v1/leave/requests/self` replaces the legacy RPC. |
| `phase8a-rpc-employee-cancel` | `POST /api/v1/leave/requests/{request_id}/cancel/self` replaces the legacy RPC. |
| `phase8a-rpc-manager-approve` | `POST /api/v1/leave/approvals/{request_id}/decision` replaces the legacy approval RPC. |
| `phase8a-rpc-manager-reject` | The same staff decision route replaces the legacy rejection RPC. |
| `phase8a-delegate-function` | `public.can_act_for_delegated_leave(uuid)` remains a protected Phase 5 authority function and supports Phase 8 scoped reads. |
| `phase8a-protected-audit` | The Phase 8D, 8E, and 8F wrappers add only the approved attachment, request, decision, and delegation actions. |
| `phase8a-notification-producer` | Retained and unused by migration leave workflows. Phase 12 owns notification delivery. |
| `phase8a-day-count` | `backend/app/services/leave_balance.py` owns Decimal working-day, calendar-day, and half-day calculations. |
| `phase8a-accrual` | `backend/app/services/leave_balance.py` computes accrual from the trusted business date. |
| `phase8a-carry-forward` | `backend/app/services/leave_balance.py` caps carry-forward under settings and type rules. |
| `phase8a-sick-tier` | `backend/app/services/leave_balance.py` and locked request transitions own sick-tier accounting. |
| `phase8a-request-validation` | `backend/app/services/leave_request.py` derives and validates the complete submission policy. |
| `phase8a-payroll-calculation` | Retained for Phase 9. Migration leave workflows do not call it. |
| `phase8a-encashment-calculation` | Retained for Phase 11 offboarding. Migration leave workflows do not call it. |
| `phase8a-attendance-consumer` | Retained for Phase 10. It is absent from the migration build. |
| `phase8a-balance-csv` | Retained for Phase 12 reports and exports. It is absent from the migration build. |
| `phase8a-legacy-leave-object` | The legacy upload export fails closed. The private attachment routes and synthetic storage adapter own Phase 8 objects. |
| `phase8a-storage-interface` | The approved Phase 11 prerequisite supplies put, get, head, delete, and short-lived signing for Phase 8D. |
| `phase8a-storage-proof-only` | Retained as Phase 6 synthetic evidence. It is not used as leave attachment authority. |
| `phase8a-fixture-attachment` | Retained as synthetic verification data only. |
| `phase8a-payroll-leave` | Assigned to Phase 9. The Phase 8 API produces no payroll effect. |
| `phase8a-attendance-leave` | Assigned to Phase 10. The Phase 8 API produces no attendance effect. |
| `phase8a-roster-leave` | Assigned to Phase 10. The Phase 8 API produces no roster effect. |
| `phase8a-storage-recovery` | The minimum prerequisite is present for Phase 8 attachments. Phase 11 retains common recovery and production-storage ownership. |
| `phase8a-notifications` | Assigned to Phase 12. Migration leave workflows call no notification producer. |
| `phase8a-tasks` | Assigned to Phase 12 and absent from the migration leave graph. |
| `phase8a-dashboards-reports` | Assigned to Phase 12 and absent from the migration leave graph. |
| `phase8a-offboarding` | Assigned to Phase 11 and absent from the migration leave graph. |

## Boundary review

The server reads `public.workloop_business_date()` for leave year, notice, delegation, cancellation,
and eligibility decisions. Browser dates grant no authority. Decimal arithmetic owns day counts,
accrual, carry-forward, sick tiers, reservations, use, and release.

The authorized executor owns each database transaction. Submission, cancellation, and decisions
write request, balance, domain audit, protected audit, attachment-operation, and idempotency state
together where the operation requires them. Provider calls occur outside the database transaction,
with durable claimed operations covering upload and delete recovery.

Forced RLS remains active. Runtime access depends on direct login and verified human context.
Protected functions remain owned by `workloop_migration`, pin their search paths, revoke public
access, and expose only their approved projections or actions. Mutable configuration, requests, and
delegations use locked rows and expected versions. Employee advisory locks serialize empty overlap
sets, and balance locks serialize spending.

The migration source tree contains no Supabase import or call. Legacy Phase 8 entry points fail
before a Supabase call. The remaining legacy request readers are confined to the named Phase 9,
Phase 10, and Phase 12 consumers. They are not part of the migration build and perform no Phase 8
write.

Each cutover names `migration-fastapi` as its only read system, write system, and writable system.
Rollback must run in this order: decisions and delegation, submission and cancellation,
attachments, balances and reads, then configuration. Each unit freezes migration writes before it
restores a legacy writer.

## Verification result

The fresh `workloop-phase8g-01a0a616` gate proved the single `e8f4c7b2a610` head, empty-schema
replay, repeatable upgrade, exact restoration of `d1e5f8a2c904`, RLS, grants, protected functions,
concurrency, idempotency, attachment cleanup, restart persistence, and the complete leave browser
journey. Final cleanup left zero synthetic database rows, Keycloak users, storage objects, and
Phase 8G Docker resources.
