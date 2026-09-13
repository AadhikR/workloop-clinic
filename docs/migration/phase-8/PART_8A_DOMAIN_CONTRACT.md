# Phase 8A leave domain contract

Status: preparation, authorized by the project owner on 2026-09-13. This document fixes the contract for later implementation. It does not add routes, services, repositories, frontend screens, storage behavior, migrations, or cutover authority.

## Authority and common rules

PostgreSQL remains authoritative for company, branch, employee, reporting manager, portal role, delegation, request status, and balance state. The selected branch comes from the canonical branch header and authenticated scope. The actor comes from the verified principal. A browser employee ID, manager ID, delegate ID, role, status, actor email, day count, approval level, timestamp, leave-type code, object path, or signed URL does not grant authority.

The seven in-scope tables are `leave_settings`, `leave_types`, `public_holidays`, `leave_requests`, `leave_audit_log`, `leave_balances`, and `leave_approval_delegates`. The Phase 4 columns, constraints, indexes, retention rules, and status check remain the baseline. Alembic revisions are unchanged. Phase 8A proposes no schema, constraint, index, RLS, grant, role, function, or audit amendment for execution.

The trusted business date is `public.workloop_business_date()`, which supplies the UAE date used for leave year, notice, delegation, expiry, and eligibility. The default leave year is the calendar year of that trusted date because the current canonical `leave_year_type` supports `calendar`; a future non-calendar type requires an owner-approved contract and schema decision. Browser clocks cannot affect entitlement.

Responses use strict camelCase projections. UUIDs remain UUID strings. Dates are ISO `YYYY-MM-DD`; timestamps are RFC 3339 UTC; nullable database values remain JSON `null`; numeric day values are decimal strings with two fractional places. Collections use the Phase 6 cursor envelope. Every list binds company, branch, actor, filters, sort, and projection into its cursor.

## Projections

The following fields are the only fields each projection exposes. `id`, `companyId`, and `branchId` are included only where named.

| Projection | Exact fields and rules |
|---|---|
| leaveSettings | `id`, `branchId`, `leaveYearType`, `weekendDefinition`, `carryForwardEnabled`, `carryForwardMaxDays`, `approvalChain`, `ramadanActive`, `ramadanStart`, `ramadanEnd`, `createdAt`, `updatedAt`; administrator branch read and write only |
| leaveType | `id`, `branchId`, `code`, `name`, `color`, `isPaid`, `isUnlimited`, `requiresApproval`, `requiresAttachment`, `requiresReason`, `minNoticeDays`, `annualEntitlementDays`, `accrualType`, `dayCountType`, `autoApprove`, `carryForwardAllowed`, `carryForwardMaxDays`, `genderRestriction`, `minServiceMonths`, `oncePerCareer`, `notDeductedFromAnnual`, `affectsPayroll`, `lawReference`, `isActive`, `sortOrder`, `probationEligible`, `createdAt`, `updatedAt`; staff reads active types sorted by `sortOrder`, `name`, `id` |
| publicHoliday | `id`, `branchId`, `date`, `name`, `type`, `year`, `createdAt`; sorted by `date`, `id` |
| leaveRequest | `id`, `branchId`, `employeeId`, `leaveTypeId`, `startDate`, `endDate`, `isHalfDay`, `halfDayPeriod`, `daysRequested`, `status`, `reason`, `attachment`, `rejectionReason`, `managerRejectionReason`, `relationship`, `deceasedName`, `dateOfDeath`, `childBirthDate`, `childName`, `expectedDueDate`, `institutionName`, `examDates`, `substituteEmployeeId`, `approvalLevelRequired`, `approvalComment`, `warnings`, `submittedAt`, `createdAt`, `updatedAt`; actor IDs and approval timestamps are omitted from staff projections unless the approved queue projection names them |
| attachment | `id`, `fileName`, `contentType`, `sizeBytes`, `sha256`, `uploadedAt`, `expiresAt`; never expose provider key or public URL; `attachment` is `null` when absent |
| leaveBalance | `employeeId`, `leaveTypeId`, `leaveYear`, `entitledDays`, `accruedDays`, `usedDays`, `pendingDays`, `carriedForward`, `remainingDays`, `sickFullPayUsed`, `sickHalfPayUsed`, `sickUnpaidUsed`; all day fields are decimal strings |
| leaveQueueItem | `request`, `employee`, `leaveType`, `balance`, `canDecide`, `visibleBecause`; employee data is limited to the queue contract and `visibleBecause` is `directReport` or `activeDelegation` |
| leaveApprovalDelegate | `id`, `branchId`, `approverEmployeeId`, `delegateEmployeeId`, `fromDate`, `toDate`, `createdAt`, `updatedAt`; only administrators manage rows, and active or expired rows are immutable |
| leaveAuditEntry | `id`, `leaveRequestId`, `action`, `reason`, `oldStatus`, `newStatus`, `createdAt`; only the request owner, authorized approver, or administrator receives the permitted projection; no direct audit-table endpoint |

`leave_type_code` is not a request or balance field. The server resolves `leaveTypeId` to the branch-scoped type. The legacy `Info Requested` label is unsupported. The canonical status set is `Pending`, `ManagerApproved`, `ManagerRejected`, `Approved`, `Rejected`, and `Cancelled`. If the old screen needs that display, it maps a safe warning or action prompt without writing a new status.

## Server-owned leave rules

The service loads the selected branch settings, active type, holidays for the derived leave year, employee lifecycle and attributes, overlapping requests, and the locked balance before validating. Working-day counts exclude configured weekends and branch holidays. Calendar-day counts include both endpoints. A half-day is exactly `0.50` on the selected `AM` or `PM` period and cannot be combined with a multi-day range. The service returns two-decimal Decimal values and never uses binary floating point.

The server derives notice, service months, probation eligibility, gender restriction, once-per-career use, required reason, required attachment, substitute eligibility, and overlap warnings. It computes accrual from the trusted business date and leave-year boundary. Carry-forward is capped by both setting and type. Sick tiers update the balance counters in order: full pay, half pay, then unpaid. Unlimited and non-deducted types follow their stored type rules but still pass scope, overlap, and eligibility checks.

Available balance is `accruedDays + carriedForward - usedDays - pendingDays` for bounded types. Pending requests reserve days. Approval converts the reservation to used days. Rejection and cancellation release the reservation. Auto-approval converts it immediately. A request never changes balance without the matching request transition and audit records in the same transaction.

## Transaction contracts

| Operation | Authority and locks | Atomic writes and result |
|---|---|---|
| configuration | administrator in selected branch; lock settings/type/holiday row | validate branch, year, future/unused rule, and version; write one row and return projection |
| balance initialization/read | administrator recalculation or scoped self/queue/admin read; lock employee, type, requests, then balance in deterministic order | recompute Decimal fields or return a projection; no browser write |
| attachment | employee owner, selected-branch administrator, or queue-visible manager/delegate | validate content and digest, bind to request or one-use submission token, record metadata and storage operation; orphan intent is recoverable |
| submission | employee self or administrator submitting for a scoped employee; idempotency required | derive all fields, validate, reserve pending balance, write request, attachment reference, domain audit, and protected audit; auto-approval consumes balance in the same transaction |
| cancellation | employee on owned `Pending`, administrator on future `Approved` | recheck status/date/actor, release or reverse balance, write status and both audit records atomically |
| manager decision | current one-level direct manager or active same-branch delegate; idempotency required | lock request, employee, manager relation, delegation, type, settings, attachment, and balance; apply only the transition table and write balance plus audits together |
| administrator decision | administrator in selected branch; idempotency required | decide one-level `Pending` or finalize `ManagerApproved`; require override reason where applicable and preserve actor separation |
| audit | produced by the transaction owner and protected function | request, balance, domain audit, protected audit, and storage-operation state commit together or roll back together |

Allowed transitions are `Pending -> ManagerApproved`, `Pending -> ManagerRejected`, `Pending -> Approved` for one-level administrator or auto-approval, `ManagerApproved -> Approved`, `ManagerApproved -> Rejected`, `Approved -> Cancelled` only for the administrator future-cancellation rule, and `Pending -> Cancelled` for employee cancellation. No arbitrary status patch is accepted.

## Attachments and cutover decisions

The Phase 6 limit is one file up to 10 MiB inside a 12 MiB request. The allowed content types, magic-byte signature, filename normalization, digest, metadata, timeout, and short-lived signing rules must be implemented by 8D against the approved Phase 11 adapter. The object key is opaque and server-generated from trusted tenant, branch, request or one-use token, category, and randomness. A signed URL is a presentation result, not an API credential.

Decision 8A-ATT-1: 8D is blocked until the project owner approves a minimum Phase 11-owned signing and recovery prerequisite. That prerequisite must provide put/get/head/delete, bounded metadata, short-lived signing, and durable orphan-operation recovery. 8D must use a local synthetic storage double. No cloud proof is authorized. If the prerequisite is not approved, defer 8D and the attachment portion of Phase 8 signoff until Phase 11.

Decision 8A-DATE-1: use `public.workloop_business_date()` and calendar-year derivation as above. Decision 8A-AUTH-1: use server-owned values for every authority-sensitive field. Decision 8A-STATUS-1: retain the canonical six statuses and remove `Info Requested` as a persisted status. These are contract decisions; legal leave-policy interpretation remains outside 8A and needs owner review before a policy-specific implementation.

## Amendment register

No amendment is approved for execution. Review items are proposals only:

| ID | Possible gap | Phase 8A action |
|---|---|---|
| 8a-amend-attachment-metadata | `leave_requests.attachment_url` cannot represent approved metadata or operation state | Owner review before 8D. Prepare a later revision only if metadata is approved |
| 8a-amend-protected-audit | protected audit action may need explicit attachment and balance actions | Compare 8E/8F transaction calls with Phase 5 protected function contract; do not change it here |
| 8a-amend-balance-concurrency | existing unique key does not itself define recalculation locking | 8C must use row locks and deterministic order; propose an index or constraint only if focused checks prove it necessary |
| 8a-amend-rpc-contract | legacy leave RPCs accept browser-controlled inputs | Replace them with FastAPI transactions in 8E/8F; do not alter legacy functions in 8A |

The existing leave notification producer remains unused by migration workflows until Phase 12. Any change to a protected function, role, grant, RLS policy, schema, constraint, index, or legal policy stops for project-owner review.

## Cutover and rollback

The five preparation records in `cutover/` cover configuration, balances and reads, attachments, submission, and approval workflows. Each record names one authority, frozen opposite path, synthetic refresh, and reverse-dependency rollback. Dual writes are forbidden. Migration writes remain disabled in preparation.

Configuration rolls back before dependent balances. Approval decisions roll back before submission, balances, attachments, or configuration. Attachment rollback preserves metadata for committed requests and reconciles only objects proven orphaned by an operation record. No data, storage bucket, volume, or cloud resource changes in 8A.

## Verification boundary

The focused verifier is `scripts/verify-phase-8a-contract.py`. It checks seven-table coverage, unique inventory IDs, Phase 9–12 ownership, documentation-only exclusions, five preparation records, and preparation rollback structure. The cutover records are then validated with `node scripts/cutover-record-validator.mjs <record>`.

The Phase 8A gate is documentation formatting, JSON validation, the focused verifier, and `git diff --check`. Backend, frontend, browser, Docker, migration, authentication, storage, and full-stack checks are deferred to the phase that adds each consumer. Alembic revisions are unchanged.
