# Phase 4D completion record

## Status

Part 4D completed on 2026-09-03, except the independent GPT-5.6 security review, which the project
owner chose to defer. This part added the four retained PostgreSQL functions, the 19 canonical
`updated_at` triggers, and the least-privilege runtime grants from the approved Phase 4A catalogue.
It added no table, column, or RLS policy, and it left the Phase 3 authentication contract, the
`app_users` identity mapping, and the legacy Supabase frontend untouched.

## What landed

Three revisions on top of the Phase 4C head (`7d3e5a1f6c54`), one per concern so review and rollback
stay bounded.

| Revision | Concern | Contents |
|---|---|---|
| `8e2b6a4c1f07` | Triggers | `set_updated_at()` plus the 19 named `BEFORE UPDATE` triggers |
| `9f3c7b5d2a18` | Functions | `replace_payroll_entries`, `record_advance_repayment`, `admin_execute_shift_swap` |
| `a0d4e6f8c92b` | Grants | Per-table runtime grants and the three function execute grants |

The head is `a0d4e6f8c92b`. No table or column changed, so `alembic check` still reports no drift and
the metadata still holds exactly 54 tables.

## Triggers

One canonical helper backs every trigger:

```
CREATE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path TO public AS $$
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
with its owner's rights regardless, so no role needs execute on it.

## Functions

All three are SECURITY DEFINER with `SET search_path TO public`, and each has its PUBLIC execute
privilege revoked. The caller's identity arrives as an explicit `app_users` argument where one is
needed. None reads a Supabase-era session identity or role, so the `admin_set_employee_portal_role`
privilege-escalation gap and the search-path-injection defect Phase 0 flagged do not return.

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
  and the roster rows, holds the two roster rows in ascending id order to avoid deadlocks, enforces
  same company and branch scope, and applies the two-way swap or the one-way coverage atomically with
  the approval fields.

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
| Function-written | SELECT | advance_repayments |
| Append-only, audit, issued snapshot | SELECT, INSERT | employee_job_history, payslips, payroll_approval_log, compliance_overrides, leave_audit_log, clock_events, attendance_audit_log, employee_contracts |
| Operational | SELECT, INSERT, UPDATE | branches, departments, department_staffing_rules, payroll_runs, payroll_entries, nafis_reports, salary_advances, expense_claims, leave_settings, leave_types, public_holidays, leave_requests, leave_balances, leave_approval_delegates, attendance_settings, shifts, shift_assignments, attendance_records, attendance_periods, regularisation_requests, roster_assignments, shift_swap_requests, biometric_mappings, employee_documents, insurance_policies, employee_insurance, insurance_dependants, notifications, offboarding_checklists, offboarding_tasks, offboarding_task_templates, assets, asset_assignments, training_records, certifications, appraisal_cycles, appraisals, appraisal_sections, cme_requirements, incident_reports, letter_requests |
| Function execute | EXECUTE | replace_payroll_entries, record_advance_repayment, admin_execute_shift_swap |

`advance_repayments` is SELECT only because every write reaches it through `record_advance_repayment`.
The append-only class withholds UPDATE and DELETE from history, audit, log, and issued-snapshot rows
that the application creates and reads but never edits in place. `set_updated_at` is a trigger helper
and gets no execute grant.

The 4A catalogue set the grant principles but left the per-table read and write choice to 4D, and
the subphase plan flags the grant matrix, table by table, as a decision that needs the project
owner's approval. The matrix above is the least-privilege proposal, still open for that sign-off and
the deferred GPT-5.6 review.

## Verification

All commands ran against the local Compose stack on PostgreSQL 16.15, the same image the CI
`full-stack-smoke` job builds.

Alembic round-trip.

```
docker compose --profile tools run --rm migrate                       # upgrade head
alembic check                                                         # no drift at a0d4e6f8c92b
alembic downgrade 7d3e5a1f6c54                                        # 4D revisions revert cleanly
alembic upgrade head                                                  # back to a0d4e6f8c92b
```

`sh scripts/verify-phase-4d-migrations.sh` tears each Phase 4D revision down to the 4C head and back
up one at a time, checks the recorded position after each move, and asserts no drift at the head.

`sh scripts/verify-phase-4d-grants.sh` checks the exact matrix with `has_table_privilege` and
`has_function_privilege`: identity tables read-only, `advance_repayments` SELECT only, the append-only
class SELECT and INSERT with no UPDATE or DELETE, operational tables SELECT, INSERT, and UPDATE with
no DELETE, no DELETE or TRUNCATE on any of the 50 business tables, EXECUTE on the three business
functions, and no EXECUTE on `set_updated_at`. It then opens a `workloop_runtime` session that reads
a granted table but is refused an ungranted DELETE and an ungranted identity INSERT.

`sh scripts/verify-phase-4d-functions.sh` runs a connected row graph in one rolled-back transaction
and proves the trigger advances `updated_at` within one transaction, `replace_payroll_entries`
inserts, replaces, and rejects each malformed input class, `record_advance_repayment` is idempotent
by request key and refuses conflicts, over-outstanding amounts, and over-scale money and settles at
zero, and `admin_execute_shift_swap` refuses a disabled or non-admin actor, swaps both roster rows,
records the approval fields, and refuses a stale non-pending swap.

The Phase 4B, 4C schema, and 4C per-domain verifiers still pass. The 4C schema verifier's runtime
boundary block moved to `verify-phase-4d-grants.sh`, since 4D is where the runtime gains write
access; the 4B verifier now checks that the identity tables stay read-only to the runtime after 4D.

Static scan. The Phase 4C `test_no_supabase_identity_or_storage_references` test globs every model
and migration, so it now also scans the three Phase 4D migrations. All 16 scanned files are clean of
`auth.users`, `auth.uid`, `auth.email`, `auth.role`, `auth_user_id`, `storage.objects`,
`storage.foldername`, and any Supabase role. The metadata still holds exactly 54 tables and no column
keeps a `user_id` or `auth_user_id` ownership shape.

## Boundaries kept

- No RLS policy, no new table or column, no business logic, API route, authorization, or migrated
  screen.
- No provisioning, Keycloak Admin API, DigitalOcean resource, SMTP, or real data.
- No wildcard, PUBLIC, default-privilege, browser, or service role grant, and no DELETE or TRUNCATE.
- The Phase 3 identity contract, `app_users`, and the read-only identity grants are unchanged.

## Outstanding gate

The independent GPT-5.6 security review is the one completion-gate item this session did not run: the
prerequisite review of the migrated 4C schema, and the 4D review of the grant matrix and every
retained security-definer-equivalent function. The project owner authorized Part 4D and deferred both
reviews, so this work is committed and review-ready with the gate open, following the same pattern as
Part 4C. The grant matrix also still needs the project owner's own table-by-table sign-off. Part 4E
remains unauthorized.
