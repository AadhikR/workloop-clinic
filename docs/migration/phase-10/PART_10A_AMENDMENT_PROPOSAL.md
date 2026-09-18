# Part 10A approved amendment proposal

## Decision

The project owner authorized 10A to settle bounded Phase 10 amendments with best judgment. The
decisions below are approved for their owning parts. No new human role is needed. This document does
not change schema or runtime behavior; each authorized implementation part owns an append-only
revision and exact downgrade proof.

## Approved decisions

| ID | Decision | Approved answer |
| --- | --- | --- |
| `10A-D01` | Time authority | Use `Asia/Dubai`, server-derived business dates, and the overnight start-date rule in the contract. |
| `10A-D02` | Shift precedence | Published roster row, then one effective assignment, then branch flexible default. Overlap is invalid. |
| `10A-D03` | Event methods | New writers persist only `MANUAL` and `BIOMETRIC`; convert legacy `BIOMETRIC_API` to `BIOMETRIC`. |
| `10A-D04` | Import behavior | Limit to 5,000 rows and 2 MiB; validate per row, insert valid unique rows atomically, and retain durable batch outcomes. |
| `10A-D05` | Deduplication | Use a canonical event fingerprint plus same-employee, type, method, and UTC-minute uniqueness. |
| `10A-D06` | Calculation | Use the stated precedence, evidence flags, Decimal arithmetic, and final-component half-up rounding. |
| `10A-D07` | Salary timing | Snapshot at daily calculation, recheck at close, and freeze the close version. |
| `10A-D08` | Period amendments | Never reopen or rewrite a closed version. Append a linked replacement version and make older payroll snapshots stale. |
| `10A-D09` | Roster publication | Add a branch-month publication entity with immutable versions and affected-row membership. |
| `10A-D10` | Actual hours | Append separate actual-hours evidence; do not update published scheduling rows. |
| `10A-D11` | Overtime authority | Attendance owns clock-derived overtime. Roster overtime is a distinct approved duty adjustment and must prove zero overlap. |
| `10A-D12` | Swaps | Approval creates a successor publication version. Generated-payroll use freezes the referenced version. |
| `10A-D13` | Staffing and leave | Recheck effective Phase 7 staffing and Phase 8 approved or manager-approved leave at publication and swap. |
| `10A-D14` | Colleague selector | Permit only active same-branch employees with a published target-date row and return minimal identity and shift data. |
| `10A-D15` | Phase 9 versions | Hash canonical immutable source JSON and sorted source IDs; provisional or overlapping input fails closed. |

## Part 10B schema and security amendment

The first 10B revision will:

- change the `attendance_settings.working_days` default to `Sun` through `Thu`, backfill uncovered
  weekdays into existing `working_days`, and add exact day-partition and numeric-bound checks;
- add a secret-length and enabled-secret consistency check without exposing the stored key;
- add shift name, code, color, numeric, type/category, time-shape, and duration checks;
- add `shift_assignments.updated_at`, its standard update trigger, and a GiST exclusion constraint
  over company, branch, employee, and inclusive `daterange(effective_from,effective_to,'[]')`;
- create `btree_gist` only if absent to support the scoped exclusion constraint;
- add an index on `(company_id, branch_id, employee_id, effective_from desc, id)`;
- extend the idempotency replay-resource allowlist with `attendance_settings`, `shift`, and
  `shift_assignment`;
- wrap the protected audit function for `attendance_settings_changed`, `shift_created`,
  `shift_changed`, `shift_deactivated`, and `shift_assigned`, with exact entity, scope, field, state,
  reason, and metadata checks;
- retain existing selected-branch RLS policies and direct runtime verbs; repository predicates and
  FastAPI role and field checks remain the primary boundary; and
- add no staff settings or assignment policy, no secret read grant, and no new database login.

The 10B downgrade first rejects removal when overlapping assignments exist or when a stored row
violates the predecessor shape. It restores prior defaults, checks, replay-resource allowlist, audit
wrapper, trigger state, indexes, and columns. It does not delete a shift or assignment row.

## Later append-only proposals

| Owner | Required additions |
| --- | --- |
| 10C | Import-batch and row-outcome entities; event fingerprint and provenance columns; append-only guards; mapping and event indexes; exact idempotency and audit actions. |
| 10D | Attendance record source snapshot, source digest, calculation version, evidence flags, and stale-input indexes. |
| 10E | Correction evidence and decision versions; overtime and resolution provenance; exact attendance audit actions. |
| 10F | Attendance close-version and amendment entities, immutable membership, source-version uniqueness, payroll-ready checks, and internal projection indexes. |
| 10G | Draft row versions and immutable roster compliance override linkage. |
| 10H | Roster month, publication version, publication membership, actual-hours evidence, overtime approval, overlap proof, and projection indexes. |
| 10I | Swap source-version fields and a replacement protected function that creates one successor publication version atomically. |

All new tenant data is company and branch scoped with composite foreign keys. RLS is enabled and
forced where the surrounding domain requires it. Browser roles receive no direct database access.
Every protected function is owned by `workloop_migration`, pins its search path, revokes `PUBLIC`,
checks trusted context, and grants execution only to the required service login.

## Rollback effects

10A rollback is a document revert only. Runtime rollback in later parts disables the migration
writer before restoring a legacy writer. Raw events, correction evidence, closed attendance
versions, published roster versions, actual-hours evidence, executed swaps, audit, and payroll
snapshots are retained. No downgrade or operational rollback may delete or rewrite them to recover
authority.
