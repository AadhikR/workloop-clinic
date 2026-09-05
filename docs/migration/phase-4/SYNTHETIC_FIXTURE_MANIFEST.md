# Phase 4E synthetic fixture manifest

## Status

Phase 4E completed on 2026-09-05. The executable manifest contains 334 deterministic rows across
48 tables. It covers every persisted Phase 0 scenario and records every payload, calculation,
legacy omission, and later authorization case that does not create a database row.

The seed lives in `backend/app/db/seed/`. `fixtures.py` defines each row and the non-persisted
catalogues. `constants.py` fixes the clock and UUID rules. `runner.py` applies, validates,
fingerprints, and removes the fixtures. Alembic never calls the seed.

## Determinism and identity safety

The seed does not read the machine clock or create a random UUID. It uses the Phase 0 clock,
`2026-08-27T08:00:00Z`, for every defaulted fixture timestamp. Explicit Phase 0 UUIDs remain exact.
Every other UUID uses namespace `00000000-0000-5000-8000-000000000001` and this canonical name:

```text
workloop/<table>/<tenant>/<branch>/<actor>/<scenario>
```

All emails use `.test`. Government, bank, policy, member, badge, document, certificate, and asset
identifiers are synthetic. Employee identifier sequences follow the Phase 0 formulas. H-DXB-002
still produces MOL `90000000000002`, IBAN `AE000000000000000000002`, and Emirates ID
`784-1990-0000000-2`.

All 15 seeded application users use issuer `https://seed.workloop.test`. That issuer differs from
the configured Keycloak issuer, so the application-user resolver cannot match these rows to a live
Keycloak token. The Phase 3 browser verifier keeps its own temporary identities and removes them.

## Exact row counts

| Table | Rows | Table | Rows |
|---|---:|---|---:|
| `advance_repayments` | 1 | `app_users` | 15 |
| `appraisal_cycles` | 5 | `appraisal_sections` | 9 |
| `appraisals` | 8 | `asset_assignments` | 2 |
| `assets` | 6 | `attendance_periods` | 2 |
| `attendance_records` | 13 | `attendance_settings` | 4 |
| `biometric_mappings` | 1 | `branches` | 4 |
| `certifications` | 8 | `clock_events` | 6 |
| `cme_requirements` | 4 | `companies` | 2 |
| `department_staffing_rules` | 3 | `departments` | 6 |
| `employee_contracts` | 4 | `employee_documents` | 9 |
| `employee_insurance` | 1 | `employees` | 15 |
| `expense_claims` | 7 | `incident_reports` | 9 |
| `insurance_dependants` | 1 | `insurance_policies` | 1 |
| `leave_approval_delegates` | 2 | `leave_balances` | 3 |
| `leave_requests` | 12 | `leave_settings` | 4 |
| `leave_types` | 36 | `letter_requests` | 6 |
| `notifications` | 12 | `offboarding_checklists` | 4 |
| `offboarding_task_templates` | 16 | `offboarding_tasks` | 5 |
| `payroll_approval_log` | 4 | `payroll_entries` | 8 |
| `payroll_runs` | 16 | `payslips` | 1 |
| `public_holidays` | 4 | `regularisation_requests` | 3 |
| `roster_assignments` | 9 | `salary_advances` | 7 |
| `shift_swap_requests` | 3 | `shifts` | 8 |
| `training_records` | 10 | `user_profiles` | 15 |
| Total | 334 | Tables | 48 |

The 334 rows include the 79-row first increment from commit `90dea21`. The completion increment
adds 255 rows and raises table coverage from 14 to 48.

## Persisted scenario coverage

- Identity and organization contain two tenants, four branches, four managers, their reports,
  terminated employees, Horizon Dubai departments, staffing rules, and shift templates. Managers
  occur before reports in insertion order.
- Payroll has four periods in every branch. Run, approval, WPS payment, exclusion, signed legacy
  variable, recurring adjustment, one-time adjustment, rejection, payslip, and approval-log cases
  are present. The canonical August entry retains leave deduction `400.00` and variable allowance
  `5238.46`.
- Advances cover pending, active, settled, and both cancellation reasons. A Cedar advance supplies
  the tenant-control target. The August repayment remains one idempotent `500.00` row.
- Expenses cover pending, manager approved, manager rejected, approved, paid, and rejected. Receipt
  and empty-receipt rows are both present. The paid row links to a generated run.
- Leave contains all nine default and custom types in every branch. Requests cover the six states,
  half day, current leave, weekend and holiday spans, maternity, bereavement, study, Hajj, and an
  attachment case. Sick balance use is exactly 15 full-pay, 30 half-pay, and 5 unpaid days.
- Attendance contains every Phase 0 state, both pending and approved overtime, all three resolution
  types, three correction states, open and closed periods, web, manual, and biometric clock events,
  a missing clock-out, a matched badge, roster publication controls, and three swap states.
- Documents and certifications cover every listed state, type, and expiry band. Insurance renewal
  is at 30 days, employee cover is at 60 days, and the dependant has no expiry field. One document
  metadata row points to a deliberately missing object key.
- Notifications contain all 12 types with read and unread rows. The database verifier replays one
  deduplication key and proves that one row remains.
- Training covers planned, in progress, completed pass, completed fail, and cancelled records, plus
  all four training types. CME totals are 30, 12, 0, 8, and 25 hours for the five Phase 0 cases.
- Appraisal cycles cover draft, active, and closed. Appraisals cover pending, reviewed, and
  calibrated, including unrated, partly rated, manager-own, other-manager, tenant-control, and the
  exact 3.8 weighted result.
- Assets cover all five states, an open assignment, a returned assignment, and a Cedar mutation
  control. Incidents cover all nine types, all four severities, all three states, and every branch.
- Contracts cover new, renewed, converted, and not renewed. Offboarding covers both checklist
  states, all four visa cancellation states, mixed completion, default tasks, and a custom task.
- Letter requests cover the five named letter types, one custom request, and all three states.

## Non-persisted catalogue entries

Invalid requests and pure calculations do not create seed rows. `NON_PERSISTED_SCENARIOS` records
26 exact entries: leave overlap, insufficient balance, probation eligibility, biometric unknown and
duplicate punches, invalid payroll identifiers, a future expense, safe-file rejection payloads,
eight letter length boundaries, six gratuity examples, the gratuity cap, and final settlement.

`NEGATIVE_CONTROL_MATRIX` records all 19 Phase 0 tenant, branch, manager, employee, and object access
attempts. The seed supplies rows on both sides of those tests. Phase 4E proves that scoped reads use
different tenant and branch IDs and that mixed tenant or branch foreign-key inserts fail. Phase 5
will execute the authenticated read and mutation decisions because Phase 4 has no permission API or
RLS policy.

## Approved replacements and omissions

| Phase 0 or legacy case | Phase 4 treatment |
|---|---|
| Null-company employee `H-LEG-001` | Omitted. The approved schema requires company and branch on every employee. |
| Legacy object-storage table rows | Omitted. Domain metadata remains; private object storage belongs to a later API phase. |
| Clock method `BIOMETRIC_API` | Replaced with approved target value `BIOMETRIC`. |
| Task field `doc_type` | Replaced with `employee_documents.document_type`. |
| Task field `eid_expiry` | Replaced with `employees.emirates_id_expiry`. |
| Payroll task fields `month` and `year` | Replaced with `payroll_runs.period`. |

The Phase 0 phrase "parental leave" maps to the existing `PATERNITY` default code. This is a naming
match to the current application definition, not a new schema decision.

## Verification contract

`backend/tests/test_seed_fixtures.py` fixes every per-table count and every required status, type,
date band, golden value, replacement, and negative-control list. It rejects duplicate primary keys,
unknown columns, manager ordering errors, non-deterministic output, unsafe identity issuers, invalid
profile links, non-`.test` emails, and migrated database dependencies on Supabase schemas or roles.

`scripts/verify-phase-4e-seed.sh` applies the seed, fingerprints every stored column, applies it
again, and requires the same fingerprint. It then validates all IDs, fixed values, exact scoped
counts, notification deduplication, and cross-scope database rejection. It proves that
`workloop_runtime` cannot run the seed. Cleanup checks every affected table before commit and leaves
the five identity roots at zero.

The completed PostgreSQL 17.11 run at Alembic head `d307b9c1f25e` produced fingerprint
`0c8093dcab9bf142c01e046cf80723e527da00c3db7a08a32a685a600ba658f9`.
