# Phase 4E completion record

## Status

Part 4E completed on 2026-09-05. The seed now matches the Phase 0 scenario catalogue. It remains
separate from Alembic and stops before Phase 4F.

The later Phase 4F gate completed the independent GPT-5.6 review of the 4C schema and corrected 4D
functions and grant matrix on 2026-09-06.

## What changed

- Expanded `backend/app/db/seed/fixtures.py` from 79 rows across 14 tables to 334 rows across
  48 tables.
- Added the fixed UTC timestamp to the seed constants. Defaulted database timestamps now use the
  Phase 0 clock rather than the machine clock.
- Changed repeated application to `ON CONFLICT DO NOTHING`. The second run no longer fires
  `updated_at` triggers.
- Made validation compare every fixed value, not only primary-key presence and scoped counts.
- Added a full-row SHA-256 fingerprint, notification deduplication check, tenant and branch query
  controls, cross-scope insert rejection, runtime-role refusal, and per-table cleanup checks.
- Expanded the static fixture tests to pin the complete status, type, date-band, calculation,
  replacement, and negative-control catalogue.
- Updated the Phase 4 tracker, subphase plan, and executable manifest.

No Alembic revision, schema object, function, trigger, grant, RLS policy, API route, Keycloak realm,
cloud resource, SMTP setting, or real record changed.

## Exact row counts

The completed manifest has these counts:

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

The executable catalogue also has 26 non-persisted payload or calculation cases, 19 later
authorization controls, and six approved replacements or omissions. The full mapping is in
[`SYNTHETIC_FIXTURE_MANIFEST.md`](SYNTHETIC_FIXTURE_MANIFEST.md).

## Fresh PostgreSQL 17 evidence

Local database verification used isolated Compose project `workloop-phase4e-20260905a`. It created
a new named volume, then removed that isolated project and volume after validation. It did not
attach to, delete, or recreate the preserved PostgreSQL 16 volume.

- Server version was PostgreSQL 17.11.
- Alembic upgraded the empty Workloop database to `d307b9c1f25e`.
- All 334 rows inserted in foreign-key-safe order and passed every schema check.
- The second application inserted and updated zero rows.
- The complete stored-row fingerprint stayed unchanged.
- Final fingerprint was
  `0c8093dcab9bf142c01e046cf80723e527da00c3db7a08a32a685a600ba658f9`.
- A duplicate notification dedup key left one row.
- Mixed-tenant and mixed-branch employee references failed at the composite foreign keys.
- `workloop_runtime` received the expected refusal before any seed action.
- Cleanup removed all 334 rows and checked all 48 affected tables. Companies, branches, employees,
  application users, and profiles each returned zero afterward.

The full Phase 4B, 4C, and corrected 4D migration suite also passed against this database. That
included per-revision round trips, schema checks, the grant matrix, all 19 triggers, retained
function behavior, temporary-table search-path attacks, and the shift-swap concurrency test.

## Repository checks

The pre-push gate passed locally:

- Backend Pytest, Ruff, formatting, Pyright, and dependency checks.
- Frontend locked install, 32 unit tests, four migration-build isolation tests, legacy production
  build, migration production build, and Phase 3G browser authentication.
- Compose validation, PostgreSQL 17.11 startup, Alembic current, heads, no-drift check, schema
  verifiers, fixture verifier, cleanup, and the migrated database dependency scan.
- `git diff --check` and repository secret-pattern checks.

GitHub Actions runs `33983867569` and `33984505721` passed Backend quality, Frontend regression,
and the complete Alembic and database boundary step, including the Phase 4E fixture verifier. Both
then failed an existing Keycloak check that compared the example token's OAuth scopes as one
ordered string. An isolated fresh-stack reproduction returned the same approved `email` and
`profile` scopes in the other valid order. The verifier now requires those two exact scopes without
depending on their order. Corrected GitHub Actions run `33985573395` passed Backend quality,
Frontend regression, and Full stack smoke, including authentication, restart persistence, fixture
cleanup, and log-safety checks.

## Boundaries and next step

The migration identity remains the normal seed identity. A future dedicated seed identity may use
the same runner. `workloop_runtime` remains blocked.

The corrected Phase 4D search paths, grants, and function behavior are unchanged. The main local
PostgreSQL 16 volume remains intact. See [`PART_4F_COMPLETION.md`](PART_4F_COMPLETION.md) for the
later independent review and complete local gate.
