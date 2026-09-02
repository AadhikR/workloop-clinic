# Phase 4C completion record

## Status

Part 4C completed on 2026-09-02, except the independent GPT-5.6 security review, which the project
owner still has to run. This part migrated the remaining business schema from the approved Phase 4A
catalogue into Alembic revisions and SQLAlchemy models. It added no RLS policy, function, trigger, or
runtime grant, and it left the Phase 3 authentication contract, the `app_users` identity mapping, the
runtime grant boundary, and the legacy Supabase frontend untouched.

## What landed

Five domain revisions on top of Phase 4B (`a4b7e2c91d05`), one per domain group so review and
rollback stay bounded.

| Revision | Domain group | Tables |
|---|---|---|
| `3f9a1c7b2e10` | People and organization | `employee_job_history`, `departments`, `department_staffing_rules` |
| `4a0b2d8c3f21` | Payroll, finance, compliance | `payroll_runs`, `payroll_entries`, `payslips`, `payroll_approval_log`, `nafis_reports`, `salary_advances`, `advance_repayments`, `expense_claims`, `compliance_overrides` |
| `5b1c3e9d4a32` | Leave | `leave_settings`, `leave_types`, `public_holidays`, `leave_requests`, `leave_audit_log`, `leave_balances`, `leave_approval_delegates` |
| `6c2d4f0e5b43` | Attendance and roster | `attendance_settings`, `shifts`, `shift_assignments`, `clock_events`, `attendance_records`, `attendance_periods`, `regularisation_requests`, `attendance_audit_log`, `roster_assignments`, `shift_swap_requests`, `biometric_mappings` |
| `7d3e5a1f6c54` | Documents, benefits, people operations, clinical | `employee_documents`, `insurance_policies`, `employee_insurance`, `insurance_dependants`, `notifications`, `employee_contracts`, `offboarding_checklists`, `offboarding_tasks`, `offboarding_task_templates`, `assets`, `asset_assignments`, `training_records`, `certifications`, `appraisal_cycles`, `appraisals`, `appraisal_sections`, `cme_requirements`, `incident_reports`, `letter_requests` |

The head is `7d3e5a1f6c54`. With `alembic_version` the `public` schema holds 55 tables, which is the
54-table target from the 4A catalogue plus the version table. Each revision has a matching SQLAlchemy
module under `backend/app/models/`: `people.py`, `payroll.py`, `leave.py`, `attendance.py`, and
`records.py`. The models register through `backend/app/models/__init__.py`, so `alembic check`
compares them against the migrated database.

## Design points worth recording

- Every legacy `auth.users` owner column became a required `company_id` plus, for operating records,
  a required `branch_id`. Branch references are composite foreign keys to `branches(id, company_id)`,
  and employee references on branch-owned rows are composite keys to
  `employees(id, company_id, branch_id)`. These reject cross-tenant and cross-branch rows before any
  RLS exists.
- Every trusted actor or recipient became an `app_users` reference (`_app_user_id` columns), or a
  `user_profiles(app_user_id, company_id)` reference for notification recipient and creator. Lifecycle
  actors delete with `RESTRICT` so removing an identity cannot erase history; other nullable audit
  actors use the column-list `SET NULL` form so required scope stays non-null.
- The deferred `employees.shift_id` foreign key is added in the attendance revision, once `shifts`
  and its `(id, company_id, branch_id)` unique key exist. The Employee model gained the matching
  constraint so metadata and database agree. This is the exact ordering the 4A catalogue calls for.
- `payroll_entries.du_cost` is gone. The target column is `leave_deduction`. The three redundant
  leave denormalizations (`leave_requests.leave_type_code`, `leave_balances.leave_type_code`,
  `leave_audit_log.employee_id`) are gone, derived through scoped foreign keys.
- The clock-event supersession key references
  `regularisation_requests(id, employee_id, company_id, branch_id)`, so a clock event cannot cite
  another employee's correction. `advance_repayments` carries the required company and branch scope
  and the caller idempotency key. `offboarding_tasks` and `appraisal_sections` carry their own
  company and branch scope with same-scope composite parent keys.

## Verification

All commands ran against the local Compose stack on PostgreSQL 16.15, the same image the CI
`full-stack-smoke` job builds.

Alembic round-trip on an empty database.

```
docker compose --profile tools run --rm migrate                       # upgrade head
docker compose --profile tools run --rm migrate alembic check         # no drift
docker compose --profile tools run --rm migrate alembic downgrade base
docker compose --profile tools run --rm migrate                       # upgrade head again
docker compose --profile tools run --rm migrate alembic current       # 7d3e5a1f6c54 (head)
```

`downgrade base` left one table (`alembic_version`); `upgrade head` rebuilt all 54 target tables with
no drift.

Per-domain round-trip. `scripts/verify-phase-4c-migrations.sh` tears the schema down to base, rebuilds
it, then steps every domain revision down to its own parent and back up, checking the recorded
position after each move and asserting no drift at the head.

Schema and boundary gate. `scripts/verify-phase-4c-schema.sh` confirms the 54 target tables exist,
inserts a connected row graph spanning every domain and every table, and proves the graph satisfies
every foreign key, scope, and check constraint end to end. It then confirms a cross-tenant branch
reference and a cross-branch employee reference are both rejected with a foreign-key violation, and
that `workloop_runtime` can neither read nor write a migrated business table. The 4B verifier,
`scripts/verify-phase-4b-schema.sh`, still passes, so the identity schema and its runtime grants are
unchanged.

Backend suite, 95 tests.

```
cd backend && python -m pytest      # 95 passed
python -m ruff check .              # clean
python -m ruff format --check .     # clean
python -m pyright                   # 0 errors
python -m pip check                 # clean
```

The suite includes `tests/test_db_base.py`, which asserts the metadata holds exactly the 54 target
tables, and `tests/test_phase4_schema.py`, which resolves every foreign key inside the target schema,
confirms no column keeps a `user_id` owner or `auth_user_id` shape, and scans every model and
migration for `auth.users`, `auth.uid`, `auth.email`, `auth.role`, `auth_user_id`, and Supabase
storage references. The Phase 3 application-user resolver tests pass unchanged.

Frontend and isolation.

```
npm run test:unit             # 32 passed
npm run test:migration-build  # 4 passed
docker compose --profile tools config --quiet  # valid
```

## Boundaries kept

- No RLS policy, function, trigger, or runtime grant. Those are Phase 4D.
- No business logic, API route, authorization, or migrated screen.
- No provisioning, Keycloak Admin API, DigitalOcean resource, SMTP, or real data.
- `app_users` columns, the composite employee and profile keys, and the role-to-employee-link check
  are exactly as Phase 4B left them.

## Outstanding gate

The independent GPT-5.6 security review of the migrated schema is the one completion-gate item this
session could not run, because GPT-5.6 is not reachable from here. No 4C table conflicts with a 4A
decision or carries a flagged legacy security defect that forced a stop, so the schema is ready for
that review. Part 4D remains unauthorized and does not start until the project owner authorizes it.
