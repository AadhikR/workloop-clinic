# Phase 8A leave dependency inventory

Status: complete. This inventory records the legacy boundary before any leave runtime or schema change. IDs are stable within Phase 8A and are traced to their current disposition in `PART_8G_INDEPENDENT_REVIEW.md`.

## Inventory rules

The source location is the smallest useful location checked during Phase 8A. A dependency is a reader, writer, RPC, converter, calculation, object path, caller, or downstream consumer. A later phase may replace a dependency only after its cutover record names the frozen opposite path.

## Legacy modules and callers

| ID | Kind | Source location | Behavior | Later owner |
|---|---|---|---|---|
| phase8a-legacy-leave-storage | module | `src/utils/leaveStorage.js:1-879` | Supabase reads, writes, RPC calls, mapping, upload, and balance recalculation | Phases 8B–8F |
| phase8a-legacy-leave-engine | module | `src/utils/leaveEngine.js:1-872` | Browser day counts, accrual, carry-forward, sick tiers, validation, payroll and encashment calculations | Phases 8C, 9, 10, 11 |
| phase8a-admin-leave-screen | caller | `src/components/LeaveManager.jsx:1-620` | Administrator configuration, request queue, balances, delegation, CSV export, notifications | Phases 8B, 8C, 8F, 12 |
| phase8a-request-modal | caller | `src/components/LeaveRequestModal.jsx:1-250` | Shared request form and client validation/calculation display | Phases 8E and 8D |
| phase8a-employee-leave-screen | caller | `src/components/employee/EmpLeave.jsx:1-280` | Employee reads, submission, cancellation, upload, and direct cancellation RPC | Phases 8C, 8D, 8E |
| phase8a-manager-leave-queue | caller | `src/components/manager/ManagerLeaveQueue.jsx:1-260` | Direct-report queue and manager approve/reject actions | Phase 8F |

## Table operations and projections

| ID | Table or operation | Source location | Observed legacy behavior | Contract disposition |
|---|---|---|---|---|
| phase8a-settings-read-write | `leave_settings` | `src/utils/leaveStorage.js:21-67` | `select('*')`, browser `user_id`, update/upsert | Replace with branch-scoped administrator projection in 8B |
| phase8a-types-read-seed-write | `leave_types` | `src/utils/leaveStorage.js:69-240` | `select('*')`, client defaults, insert/update, soft-delete | Replace with branch-scoped configuration in 8B |
| phase8a-holidays-read-seed-write | `public_holidays` | `src/utils/leaveStorage.js:258-355` | year read, seeded defaults, insert/update/delete | Replace with retained future-only rules in 8B |
| phase8a-request-read-write | `leave_requests` | `src/utils/leaveStorage.js:357-467` | `select('*')`, client fields including `leave_type_code`, insert, arbitrary status update, cancel | Replace with server-owned transactions in 8E and 8F |
| phase8a-audit-read-write | `leave_audit_log` | `src/utils/leaveStorage.js:417-486` | audit insert occurs after request update and can fail separately | Replace with atomic domain and protected audit in 8E/8F |
| phase8a-balance-read-write | `leave_balances` | `src/utils/leaveStorage.js:665-864` | `parseFloat`, browser upsert and full recalculation | Replace with locked Decimal arithmetic in 8C |
| phase8a-queue-read | `leave_requests` plus `leave_balances` | `src/utils/leaveStorage.js:533-600` | direct-report lookup, current browser year, joins by legacy code | Replace with queue projection in 8F |
| phase8a-delegation-read-write | `leave_approval_delegates` | `src/utils/leaveStorage.js:620-663` | read, insert/update/delete from browser | Replace with administrator-only future-row mutations in 8F |

The canonical seven-table set is `leave_settings`, `leave_types`, `public_holidays`, `leave_requests`, `leave_audit_log`, `leave_balances`, and `leave_approval_delegates`. No table is omitted because it is read-only, audit-only, or used only by a later phase.

## RPCs and protected functions

| ID | Location | Operation | Disposition |
|---|---|---|---|
| phase8a-rpc-employee-submit | `src/components/employee/EmpLeave.jsx:188-204` | `employee_submit_leave_request` with browser employee, code, dates, days, and fields | Replace in 8E |
| phase8a-rpc-employee-cancel | `src/components/employee/EmpLeave.jsx:123-130` | `employee_cancel_leave_request` | Replace in 8E |
| phase8a-rpc-manager-approve | `src/utils/leaveStorage.js:602-608` | `manager_approve_leave` | Replace in 8F |
| phase8a-rpc-manager-reject | `src/utils/leaveStorage.js:610-618` | `manager_reject_leave` | Replace in 8F |
| phase8a-delegate-function | `backend/alembic/versions/c74f5e9b2a31_add_leave_rls.py:28,127-203` | `public.can_act_for_delegated_leave(uuid)` uses trusted business date and same-branch direct-report relation | Retain as Phase 5 authority; propose contract amendment only if 8F needs a changed signature |
| phase8a-protected-audit | `docs/migration/phase-5/PERMISSION_MATRIX_AND_RLS_DESIGN.md:629-776` | protected audit records actor and request transition | Inspect and amend only by owner-approved proposal |
| phase8a-notification-producer | `src/components/LeaveManager.jsx:209-220` | creates `leave_approved` or `leave_rejected` notifications | Freeze for Phase 12; do not call from migration leave workflows |

## Calculations and converters

| ID | Source location | Calculation or converter | Later owner |
|---|---|---|---|
| phase8a-day-count | `src/utils/leaveEngine.js:268-369` | weekend, holiday, working-day, calendar-day, and half-day counts | 8C |
| phase8a-accrual | `src/utils/leaveEngine.js:371-440` | annual accrual from browser date and leave-year type | 8C |
| phase8a-carry-forward | `src/utils/leaveEngine.js:441-484` | carry-forward from requests and client leave type | 8C |
| phase8a-sick-tier | `src/utils/leaveEngine.js:485-538` | full-pay, half-pay, unpaid sick tiers | 8C |
| phase8a-request-validation | `src/utils/leaveEngine.js:675-810` | notice, eligibility, overlap, balance, reason, attachment, and type fields | 8C and 8E |
| phase8a-payroll-calculation | `src/utils/leaveEngine.js:576-610` | approved leave deductions | Phase 9 |
| phase8a-encashment-calculation | `src/utils/leaveEngine.js:539-575` | unused leave encashment | Phase 11 |
| phase8a-attendance-consumer | `src/utils/leaveStorage.js:865-879` and `src/components/AttendanceManager.jsx` | approved leave used by attendance month reads | Phase 10 |
| phase8a-balance-csv | `src/components/LeaveManager.jsx:70-87` | browser CSV export of balances | Phase 12 |

## Object paths and storage

| ID | Source location | Behavior | Owner |
|---|---|---|---|
| phase8a-legacy-leave-object | `src/utils/leaveStorage.js:243-256` | uploads to `employee-documents` using `${adminUserId}/${employeeId}/leave/...` and returns a signed URL | 8D, with common adapter and recovery in 11 |
| phase8a-storage-interface | `backend/app/storage/base.py:14-40` | provider-neutral put/get/head/delete with size, content type, and sha256 metadata | Phase 11 prerequisite proposal |
| phase8a-storage-proof-only | `backend/app/storage/proof.py:1-51` | Phase 6 synthetic proof object, not a leave attachment contract | Retain as proof; do not extend in 8A |
| phase8a-fixture-attachment | `backend/app/db/seed/fixtures.py:1332-1396` | synthetic legacy attachment URLs and missing-object scenarios | Synthetic evidence only |

The 10 MiB file limit and 12 MiB request limit come from `docs/migration/phase-6/API_CONTRACT.md:457-491`. Browser paths, provider keys, public URLs, and direct credentials have no authority.

## Downstream assignments

| ID | Consumer | Evidence | Assignment |
|---|---|---|---|
| phase8a-payroll-leave | payroll deductions and advance pay | `src/utils/leaveEngine.js:576-610`; `src/components/PayrollEditor.jsx`; `backend/app/models/payroll.py:172-210` | Phase 9 |
| phase8a-attendance-leave | attendance resolution and holiday treatment | `src/utils/leaveStorage.js:865-879`; `src/utils/attendanceStorage.js`; `src/utils/attendanceEngine.js` | Phase 10 |
| phase8a-roster-leave | staffing and roster conflict handling | `src/components/RosterManager.jsx`; `src/utils/leaveEngine.js:675-810` | Phase 10 |
| phase8a-storage-recovery | common storage, signing, recovery, employee documents, offboarding encashment | `backend/app/storage/base.py`; `src/components/EndOfServiceScreen.jsx` | Phase 11 |
| phase8a-notifications | leave notification delivery | `src/components/LeaveManager.jsx:209-220`; `src/utils/notificationStorage.js` | Phase 12 |
| phase8a-tasks | follow-up tasks | `src/components/TasksPanel.jsx`; `src/utils/taskStorage.js` | Phase 12 |
| phase8a-dashboards-reports | dashboard, report, CSV, and PDF readers | `src/components/ClinicalDashboard.jsx`; `src/components/Reports.jsx`; `src/utils/reportUtils.js` | Phase 12 |
| phase8a-offboarding | leave encashment at offboarding | `src/components/EndOfServiceScreen.jsx`; `src/utils/leaveEngine.js:539-575` | Phase 11 |

Phase 8 publishes request, balance, configuration, attachment metadata, queue, and audit projections. It does not migrate the consumers listed above.
