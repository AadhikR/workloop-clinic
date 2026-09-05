# Phase 4D completion record

## Status

Part 4D completed on 2026-09-03. A corrective security review on 2026-09-05 found and fixed unsafe
temporary-schema lookup, direct workflow-table grants, stale roster reads during concurrent shift
swaps, and the PostgreSQL version mismatch. The independent GPT-5.6 review completed in Phase 4F on
2026-09-06. This part adds the four retained PostgreSQL functions, the 19 canonical `updated_at`
triggers, and the
least-privilege runtime grants from the approved Phase 4A catalogue. It adds no table, column, or RLS
policy, and it leaves the Phase 3 authentication contract, the `app_users` identity mapping, and the
legacy Supabase frontend untouched.

## What landed

Six revisions on top of the Phase 4C head (`7d3e5a1f6c54`). The first three implement the approved
concerns; the next three contain one corrective security change each.

| Revision | Concern | Contents |
|---|---|---|
| `8e2b6a4c1f07` | Triggers | `set_updated_at()` plus the 19 named `BEFORE UPDATE` triggers |
| `9f3c7b5d2a18` | Functions | `replace_payroll_entries`, `record_advance_repayment`, `admin_execute_shift_swap` |
| `a0d4e6f8c92b` | Grants | Per-table runtime grants and the three function execute grants |
| `b1e5f7a9d03c` | Search paths | Put `pg_catalog` first and the caller's temporary schema last |
| `c2f6a8b0e14d` | Grant correction | Remove direct writes from function-protected workflow tables |
| `d307b9c1f25e` | Concurrency | Revalidate locked roster rows before executing a shift swap |

The head is `d307b9c1f25e`. No table or column changed, so `alembic check` still reports no drift and
the metadata still holds exactly 54 tables.

## Triggers

One canonical helper backs every trigger:

```
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path TO pg_catalog, public, pg_temp AS $$
BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END; $$;
```

The helper uses `clock_timestamp()`, not the legacy `NOW()`, so `updated_at` advances even when a row
is modified more than once inside one transaction. The legacy schema carried two duplicate timestamp
helpers and four duplicate triggers; only this helper and one trigger per covered table survive. The
19 triggers cover companies, branches, employees, payroll_runs, payroll_entries, salary_advances,
leave_settings, leave_types, leave_requests, leave_balances, attendance_settings, shifts,
attendance_records, roster_assignments, shift_swap_requests, expense_claims, appraisals,
cme_requirements, and incident_reports. Four of them (branches, roster_assignments,
shift_swap_requests, appraisals) are new Phase 4A decisions for tables that gained an `updated_at`
column without a legacy trigger. The helper's PUBLIC execute privilege is revoked; a trigger fires
through its registered attachment, so the runtime role needs no direct execute privilege on it.

## Functions

All three are SECURITY DEFINER with `SET search_path TO pg_catalog, public, pg_temp`, and each has
its PUBLIC execute privilege revoked. Putting the caller's temporary schema last prevents temporary
objects from shadowing catalog or application objects. The caller's identity arrives as an explicit
`app_users` argument where one is needed. None reads a Supabase-era session identity or role, so the
`admin_set_employee_portal_role` privilege-escalation gap does not return.

- `replace_payroll_entries(uuid, jsonb)` locks the run, requires a draft run and draft approval
  state, derives company and branch from the run, and rejects unknown keys, missing or duplicate
  employees, employees outside the run's scope, non-numeric or non-finite money, money with a scale
  over two or an absolute value over ten integer digits, and any fixed scalar below zero except
  `variable_allowance`. It deletes and re-inserts the draft entries in one transaction. It removed
  the legacy caller-controlled `user_id` ownership and writes `leave_deduction`, never the retired
  `du_cost`.
- `record_advance_repayment(uuid, uuid, uuid, numeric, date)` locks the advance, then runs both
  replay checks before any state or balance check. A matching request under the same key returns
  `alreadyRecorded=true` with no mutation; a mismatched key raises `advance_repayment_idempotency_conflict`;
  a second key against the same payroll run raises `advance_repayment_payroll_conflict`. Only then
  does it require an active advance with a positive balance, validate the optional run's scope, and
  refuse an amount over the outstanding balance rather than capping it. It validates the amount's
  finiteness, scale, and range itself, since the argument carries no typmod.
- `admin_execute_shift_swap(uuid, uuid)` resolves the actor through `user_profiles` to an admin of
  the swap's own company joined to an active `app_users` row before any mutation. It locks the swap
  and the roster rows, holds the two roster rows in ascending id order to avoid deadlocks, then
  revalidates each locked row's employee, date, company, and branch. A roster row changed while the
  function waited for its lock raises `shift_swap_roster_changed`. The function enforces same company
  and branch scope and applies the two-way swap or one-way coverage atomically with the approval
  fields.

## Grant matrix

`workloop_runtime` gets an explicit privilege set per table. There is no `GRANT ... ON ALL TABLES`,
no `PUBLIC` grant, no default privilege, and no browser or service role grant. No table grants
`DELETE` or `TRUNCATE`: the only delete path in the schema is inside `replace_payroll_entries`, which
runs with definer rights, and every other purge is left to a Phase 5 endpoint-specific review. The
four identity tables keep the Phase 3 read-only `SELECT` grant; identity writes wait for the Phase 5
permission matrix.

| Class | Privileges | Tables |
|---|---|---|
| Identity (unchanged from Phase 3) | SELECT | companies, employees, app_users, user_profiles |
| Function-protected | SELECT | advance_repayments, payroll_runs, payroll_entries, salary_advances, roster_assignments, shift_swap_requests |
| Append-only, audit, issued snapshot | SELECT, INSERT | employee_job_history, payslips, payroll_approval_log, compliance_overrides, leave_audit_log, clock_events, attendance_audit_log, employee_contracts |
| Operational | SELECT, INSERT, UPDATE | branches, departments, department_staffing_rules, nafis_reports, expense_claims, leave_settings, leave_types, public_holidays, leave_requests, leave_balances, leave_approval_delegates, attendance_settings, shifts, shift_assignments, attendance_records, attendance_periods, regularisation_requests, biometric_mappings, employee_documents, insurance_policies, employee_insurance, insurance_dependants, notifications, offboarding_checklists, offboarding_tasks, offboarding_task_templates, assets, asset_assignments, training_records, certifications, appraisal_cycles, appraisals, appraisal_sections, cme_requirements, incident_reports, letter_requests |
| Function execute | EXECUTE | replace_payroll_entries, record_advance_repayment, admin_execute_shift_swap |

The six function-protected tables are SELECT only. Repayment rows and payroll entries are written by
their retained functions. Payroll runs, advances, roster assignments, and swap requests stay
read-only until a later API phase adds a narrower reviewed mutation path.
The append-only class withholds UPDATE and DELETE from history, audit, log, and issued-snapshot rows
that the application creates and reads but never edits in place. `set_updated_at` is a trigger helper
and gets no execute grant.

The 4A catalogue set the grant principles but left the per-table read and write choice to 4D, and
the subphase plan flags the grant matrix, table by table, as a decision that needs the project
owner's approval. The matrix above is the least-privilege proposal, still open for that sign-off and
the deferred GPT-5.6 review.

## Verification

The corrective gate ran against the official PostgreSQL 17.11 image pinned by OCI digest, matching
the Phase 4A target and the CI `full-stack-smoke` job.

Alembic round-trip.

```
docker compose --profile tools run --rm migrate                       # upgrade head
alembic check                                                         # no drift at d307b9c1f25e
alembic downgrade 7d3e5a1f6c54                                        # 4D revisions revert cleanly
alembic upgrade head                                                  # back to d307b9c1f25e
```

`sh scripts/verify-phase-4d-migrations.sh` tears each Phase 4D revision down to the 4C head and back
up one at a time, checks the recorded position after each move, and asserts no drift at the head.

`sh scripts/verify-phase-4d-grants.sh` checks the exact matrix with `has_table_privilege` and
`has_function_privilege`. It rejects direct writes to every function-protected table, checks that no
table grants DELETE, TRUNCATE, REFERENCES, or TRIGGER, and confirms PUBLIC cannot execute any retained
function. Its live runtime session also proves each protected mutation is refused.

`sh scripts/verify-phase-4d-triggers.sh` confirms all 19 exact trigger and table pairs are enabled as
`BEFORE UPDATE FOR EACH ROW` triggers backed by `set_updated_at()`, with no other user trigger in the
public schema. A behavior probe confirms the helper advances the timestamp.

`sh scripts/verify-phase-4d-functions.sh` runs a connected row graph in one rolled-back transaction
and proves the trigger advances `updated_at` within one transaction, `replace_payroll_entries`
inserts, replaces, and rejects each malformed input class, `record_advance_repayment` is idempotent
by request key and refuses conflicts, over-outstanding amounts, and over-scale money and settles at
zero, and `admin_execute_shift_swap` refuses a disabled or non-admin actor, swaps both roster rows,
records the approval fields, and refuses a stale non-pending swap.

`sh scripts/verify-phase-4d-function-security.sh` creates caller-owned temporary tables that shadow
the first business table each retained function reads. Every function still resolves the public
table and returns its deterministic not-found error. `sh scripts/verify-phase-4d-shift-swap-concurrency.sh`
uses two database sessions to change a roster row while the swap waits for its lock, then proves the
function rejects the stale row without approving or partly applying the swap.

The Phase 4B, 4C schema, and 4C per-domain verifiers still pass. The 4C schema verifier's runtime
boundary block moved to `verify-phase-4d-grants.sh`, since 4D is where the runtime gains write
access; the 4B verifier now checks that the identity tables stay read-only to the runtime after 4D.

Static scan. The Phase 4C `test_no_supabase_identity_or_storage_references` test globs every model
and migration, so it also scans all six Phase 4D migrations. The scanned corpus is clean of
`auth.users`, `auth.uid`, `auth.email`, `auth.role`, `auth_user_id`, `storage.objects`,
`storage.foldername`, and any Supabase role. The metadata still holds exactly 54 tables and no column
keeps a `user_id` or `auth_user_id` ownership shape.

## Boundaries kept

- No RLS policy, no new table or column, no business logic, API route, authorization, or migrated
  screen.
- No provisioning, Keycloak Admin API, DigitalOcean resource, SMTP, or real data.
- No wildcard, PUBLIC, default-privilege, browser, or service role grant, and no DELETE or TRUNCATE.
- The Phase 3 identity contract, `app_users`, and the read-only identity grants are unchanged.

## Independent review closure

The Phase 4F independent GPT-5.6 review found no Phase 4D implementation defect. It confirmed the
corrected search paths, ownership path, PUBLIC revokes, grant matrix, retained function behavior,
and downgrade order. Four test gaps were fixed without changing an approved database object or
behavior. See [`PART_4F_COMPLETION.md`](PART_4F_COMPLETION.md).
