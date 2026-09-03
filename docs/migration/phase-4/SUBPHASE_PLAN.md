# Phase 4 subphase plan

## Status

**Parts 4A and 4B completed on 2026-09-01. Part 4C completed on 2026-09-02. Part 4D completed on
2026-09-03, with the GPT-5.6 security review deferred by the project owner. Parts 4E and 4F are not
authorized.**

This document breaks Phase 4 into six parts, 4A through 4F, so the project owner can authorize
one part at a time. It records objectives, dependencies, files, decisions, security boundaries,
tests, rollback boundaries, completion gates, and a recommended model per part. Part 4A produced
documentation only. It changed no runtime code, database schema, Alembic revision, grant, or
fixture. Parts 4C through 4F still require separate authorization.

## Current state

- Branch `migration/fastapi-keycloak`. Phase 3 is complete through 3H.
- Alembic has one revision, `f41c9a7b23d1`: enums `app_role` and `account_status`; tables
  `companies` (id only), `employees` (id, company_id), `app_users`, `user_profiles`; and
  read-only `SELECT` grants to `workloop_runtime` on those four tables.
- SQLAlchemy models in `backend/app/models/identity.py` mirror that revision exactly, using the
  shared `Base` and naming convention in `backend/app/db/base.py`.
- The legacy schema lives outside `supabase/migrations`, which does not exist in this repo. It is
  12 root SQL files plus `sql/001` through `sql/055` (five numbers skipped), covering roughly 52
  tables, 29 functions, 19 triggers, and over 100 RLS policies, per
  [`docs/migration/phase-0/SQL_SCHEMA_INVENTORY.md`](../phase-0/SQL_SCHEMA_INVENTORY.md) and
  [`docs/migration/phase-0/SUPABASE_DEPENDENCY_INVENTORY.md`](../phase-0/SUPABASE_DEPENDENCY_INVENTORY.md).
- Known legacy defects that Phase 4 must not carry forward unreviewed: invalid `IF NOT EXISTS`
  syntax on policies and constraints, two duplicate `updated_at` trigger functions, a missing
  `manager_get_leave_queue` definition, a tenant-scope bypass in two read policies, and a
  privilege-escalation gap in `admin_set_employee_portal_role`.
- `ApplicationUserResolver` (`backend/app/auth/application_user.py`) depends on the exact column
  shape of `app_users`. Any Phase 4 change to that table must keep its query working.
- Part 4A's approved catalogue and decisions are in
  [`SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md`](SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md).

## Part status

| Part | Scope | Status |
|---|---|---|
| 4A | Schema inventory and design decisions | Completed 2026-09-01; see [`SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md`](SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md) |
| 4B | Core identity and organization schema | Completed 2026-09-01; revision `a4b7e2c91d05` |
| 4C | Remaining business schema | Completed 2026-09-02; revisions `3f9a1c7b2e10`, `4a0b2d8c3f21`, `5b1c3e9d4a32`, `6c2d4f0e5b43`, `7d3e5a1f6c54` |
| 4D | Functions, triggers, constraints, and grants | Completed 2026-09-03; revisions `8e2b6a4c1f07`, `9f3c7b5d2a18`, `a0d4e6f8c92b`. GPT-5.6 review deferred. |
| 4E | Synthetic fixtures | In progress; first increment (identity, organization, golden cases) landed 2026-09-03. Status-coverage rows pending. |
| 4F | Clean-database, upgrade, security, and completion gate | Not started |

## 4A: Schema inventory and design decisions

**Objective.** Turn the Phase 0 inventory into one ordered, decision-annotated table catalogue
that every later part implements against, with no open questions left for the implementer to
guess at.

**Scope.**
- Merge and de-duplicate the root SQL files and `sql/001` through `sql/055` into one authoritative
  table, column, constraint, and index list. Resolve every superseded function or column chain
  Phase 0 already flagged by picking the final version and recording why.
- Decide, and write down:
  - Companies vs. branches: keep the flat one-row-per-branch model, or introduce a parent-company
    and branch hierarchy.
  - PostgreSQL version, confirmed available on both DigitalOcean and Azure managed Postgres.
  - UUID generation strategy: built-in `gen_random_uuid()` vs. `pgcrypto`.
  - `NUMERIC` precision and scale for each money column.
  - Timestamp policy: `timestamptz` everywhere, UTC storage, display-side conversion only.
  - Which status columns become native enums, following the `app_role` and `account_status`
    precedent, and which stay `TEXT` with a `CHECK` constraint.
  - Which of the 29 legacy functions become FastAPI services instead of database functions.
  - Whether Postgres RLS stays in scope for Phase 4/5, or authorization moves entirely into the
    application layer. Phase 4's schema must work either way.

**Dependencies.** None. This part gates 4B through 4F.

**Files and areas.** `docs/migration/phase-0/*`, root SQL files, `sql/*.sql`. Output is a new
`docs/migration/phase-4/` document, not code.

**Decisions requiring project-owner approval.** Every bullet under Scope above.

**Security and data boundaries.** None yet; no schema changes happen in this part.

**Tests and negative tests.** None; this is a planning artifact. Confirm every legacy table,
function, trigger, and policy appears exactly once in the inventory before calling it done.

**Rollback boundary.** Not applicable; no schema is touched.

**Completion gate.** A reviewed document lists every target table, column, constraint, index,
function, and trigger with a stated source and a stated decision, and every bullet under Scope
has a written, project-owner-approved answer.

Passed on 2026-09-01. The project owner approved every design decision and the final document.
The catalogue reconciles all 52 legacy tables, 29 function names, 19 trigger names, and 119 policy
identities exactly once, and defines the complete 54-table target. See
[`SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md`](SCHEMA_CATALOGUE_AND_DESIGN_DECISIONS.md).

**Recommended model.** GPT-5.6. This sets the schema and identity-relationship design every later
part depends on, and the migration plan reserves database-schema design for GPT-5.6.

**Estimated effort.** One to two sessions, mostly reading and decision recording.

## 4B: Core identity and organization schema

**Objective.** Extend `companies`, `employees`, `app_users`, and `user_profiles` with the real
business columns those tables need, without breaking the Phase 3 identity contract.

**Scope.**
- Add real columns to `companies` and `employees` per the 4A inventory, as a new Alembic revision
  with `down_revision = "f41c9a7b23d1"`.
- Preserve the composite foreign key tying `user_profiles.employee_id` to `company_id`, and the
  check constraint linking role to employee-link presence.
- Leave `app_users`' issuer, subject, and status columns exactly as they are; the application-user
  resolver depends on their current shape.
- Add whatever organization-tier tables 4A approves, such as a branch hierarchy, if any.

**Dependencies.** 4A's decisions on the company and branch model and on which status columns
become enums.

**Files and areas.** `backend/alembic/versions/`, `backend/app/models/identity.py`.

**Decisions requiring project-owner approval.** Final column list for `companies` and `employees`
if it deviates from the 4A inventory during implementation.

**Security and data boundaries.** `workloop_runtime` grants stay read-only in this part. Write
grants wait for 4D so schema and privilege changes are not mixed in one review.

**Tests and negative tests.** Alembic upgrade and downgrade round-trip on an empty database;
model-metadata-matches-migration check, following the Phase 3B pattern; a test confirming
`ApplicationUserResolver`'s query still returns the expected shape after the migration.

**Rollback boundary.** Safe to downgrade only while the new columns are empty, matching the
existing revision's documented boundary.

**Completion gate.** The new revision applies cleanly on top of `f41c9a7b23d1`, downgrading from
the new head returns to that exact prior state, and the Phase 3 identity-resolution tests still
pass unmodified.

**Completion evidence.** Passed on 2026-09-01. Revision `a4b7e2c91d05` adds the approved company,
branch, employee, and profile uniqueness schema without changing `app_users` or the Phase 3
revision. An empty local database upgraded from `f41c9a7b23d1`, downgraded back to that revision,
and upgraded again. `alembic check` reported no metadata drift. The Phase 4B schema verifier passed
the composite company and branch foreign key, normalized work-email uniqueness, profile employee
uniqueness, and runtime grant boundaries. The Phase 3 application-user test suite and three-persona
browser identity verifier also passed. Runtime grants remain unchanged.

**Recommended model.** GPT-5.6 Terra, once 4A is approved. This is bounded schema-migration work
against an already-approved design.

**Estimated effort.** One session for the current table set; more if 4A approves a branch
hierarchy redesign.

## 4C: Remaining business schema

**Objective.** Migrate the rest of the roughly 52-table legacy schema, covering payroll, leave,
attendance, finance and compliance, documents, benefits, notifications, contracts, offboarding,
assets, training, organization, appraisal, and clinical tables, into Alembic revisions on top of
4B.

**Scope.**
- One or more Alembic revisions per domain group, not one large revision, so review and rollback
  stay bounded.
- Every `auth_user_id` or `user_id` column that referenced `auth.users` becomes a reference to
  `app_users.id`, per the 4A decision, applied consistently across every table.
- Preserve every primary key, foreign key, unique constraint, check constraint, and index from the
  legacy schema unless 4A explicitly recorded a deliberate change.
- No RLS policies, no functions or triggers, and no grants beyond schema ownership in this part;
  those belong to 4D.

**Dependencies.** 4A (inventory and decisions) and 4B (identity tables these business tables
reference).

**Files and areas.** `backend/alembic/versions/`, new domain model modules under
`backend/app/models/` such as `payroll.py`, `leave.py`, and `attendance.py`.

**Decisions requiring project-owner approval.** Any table where 4A flagged a legacy defect, such
as the tenant-scope bypass tables or the missing `manager_get_leave_queue` backing data, needs an
explicit call: carry the defect forward and fix it in Phase 5, or fix it now.

**Security and data boundaries.** Runtime grants stay read-only. No business logic or
authorization is implemented in this part.

**Tests and negative tests.** Per-domain migration round-trip tests; a full-schema smoke test that
creates every table from empty and checks foreign-key integrity end to end; a grep-based negative
test confirming no column still points at `auth.users` or follows the `auth_user_id`/bare
`user_id` pattern.

**Rollback boundary.** Each domain revision downgrades independently while empty. Downgrading an
earlier revision while a later one is applied is unsupported, matching Alembic's linear-history
constraint.

**Completion gate.** All roughly 52 tables exist in Alembic with foreign keys resolved, the
Supabase-reference grep check passes clean, and `alembic upgrade head` followed by
`alembic downgrade base` both succeed on an empty database.

**Recommended model.** GPT-5.6 Terra for the bulk conversion; escalate any table 4A flagged as
carrying a security-relevant legacy defect to GPT-5.6 review.

**Estimated effort.** The largest part by volume. Expect several sessions given roughly 48
remaining tables across many domains.

**Completion evidence.** Passed on 2026-09-02, except the independent GPT-5.6 security review, which
the project owner still has to run. Five domain revisions land the 48 remaining tables on top of 4B,
one revision per domain group so review and rollback stay bounded: `3f9a1c7b2e10` people and
organization, `4a0b2d8c3f21` payroll and finance and compliance, `5b1c3e9d4a32` leave,
`6c2d4f0e5b43` attendance and roster, `7d3e5a1f6c54` documents and benefits and clinical records.
The head is `7d3e5a1f6c54` and the database now has all 54 target tables. Every legacy `auth.users`
owner became required `company_id` and `branch_id` scope, every trusted actor became an `app_users`
or `user_profiles` reference with an `_app_user_id` column, and the deferred `employees.shift_id`
foreign key was added once `shifts` existed. No revision adds an RLS policy, function, trigger, or
runtime grant; those stay Phase 4D work. `app_users` and the Phase 3 identity contract are untouched.

An empty local database upgraded from `f41c9a7b23d1` to `7d3e5a1f6c54`, downgraded to base, and
upgraded again with no error. Each domain revision also downgrades to its own parent and back on its
own. `alembic check` reports no metadata drift at the head. A cross-domain row graph covering all 54
tables inserts and satisfies every foreign key, scope, and check constraint; a cross-tenant branch
reference and a cross-branch employee reference are both rejected; and `workloop_runtime` still
cannot read or write any migrated business table, so the read-only grant boundary holds. The backend
suite passes 95 tests, including a metadata coverage check, a full-schema foreign-key resolution
check, and negative scans confirming no model or migration mentions `auth.users`, `auth.uid`,
`auth_user_id`, or a Supabase storage object. Ruff, ruff format, Pyright, and pip check are clean.
The frontend unit suite and the migration-build isolation suite pass unchanged, so the legacy
Supabase frontend keeps working. See
[`PART_4C_COMPLETION.md`](PART_4C_COMPLETION.md) for the full evidence and command log.

**Outstanding gate.** The GPT-5.6 security review of the migrated schema is the one completion-gate
item this session could not run itself, since GPT-5.6 is not reachable from here. No 4C table
conflicts with a 4A decision or carries a flagged legacy security defect that forced a stop, so the
schema is ready for that review rather than blocked on a redesign.

## 4D: Functions, triggers, constraints, and grants

**Objective.** Implement, per 4A's list, whichever legacy functions and triggers stay in
PostgreSQL, then add the exact runtime grants each new table needs.

**Scope.**
- Implement the retained functions and triggers as new Alembic revisions, using one canonical
  `updated_at` trigger helper instead of carrying forward the legacy duplicate.
- Add explicit, per-table `GRANT` statements to `workloop_runtime`, following the least-privilege
  pattern already set by `f41c9a7b23d1`. No `GRANT ... ON ALL TABLES`, no `PUBLIC`, no default
  privileges.
- Pin `SET search_path` on every retained security-definer-equivalent function and
  `REVOKE ... FROM PUBLIC` before granting to specific roles, closing the search-path-injection gap
  Phase 0 flagged.
- Confirm no retained function references `auth.uid()`, `auth.email()`, `auth.role()`, or a
  Supabase role.

**Dependencies.** 4C (the tables functions and grants attach to) and 4A (which functions move to
FastAPI).

**Files and areas.** `backend/alembic/versions/`, possibly new `backend/app/services/` modules for
functions that move out of the database.

**Decisions requiring project-owner approval.** The final function-placement list, if it changes
from 4A's draft, and the grant matrix, table by table.

**Security and data boundaries.** This part sets the runtime's actual write privileges. Review
grants per table, not as one batch approval.

**Tests and negative tests.** A test connecting as `workloop_runtime` confirming it can perform
only the granted operation on each table and fails on everything else; a static check confirming
zero `auth.*` references remain anywhere in the migrations; trigger-behavior tests, such as
confirming `updated_at` changes on modification.

**Rollback boundary.** Grants and function or trigger creation stay reversible while no runtime
code depends on them yet. Downgrade must revoke exactly what it granted.

**Completion gate.** `workloop_runtime` has a documented, minimal grant set with no wildcard
grants anywhere, every retained function has a pinned search path with no lingering Supabase role
reference, and the grep-based Supabase-reference check from 4C still passes.

**Recommended model.** GPT-5.6. Grants and security-definer-equivalent function behavior are
exactly the security-sensitive, database-schema work the plan reserves for GPT-5.6, and a mistake
here is the hardest kind to catch later.

**Estimated effort.** One to two sessions for the grant matrix and canonical trigger; more if a
large share of the 29 functions move into FastAPI.

**Completion evidence.** Passed on 2026-09-03, except the GPT-5.6 security review, which the project
owner chose to defer and still owes. Three bounded revisions land on top of `7d3e5a1f6c54`, one per
concern: `8e2b6a4c1f07` adds the canonical `set_updated_at` helper and the 19 named triggers,
`9f3c7b5d2a18` adds the three retained business functions, and `a0d4e6f8c92b` adds the per-table
runtime grants. The head is `a0d4e6f8c92b`. No table or column changed, so `alembic check` still
reports no drift, and the metadata still holds exactly 54 tables.

Each function is SECURITY DEFINER with `SET search_path TO public` and has its PUBLIC execute
privilege revoked; the helper `set_updated_at` also runs with a pinned search path and no PUBLIC
execute. No retained function reads a Supabase-era session identity or role. The grant revision adds
no `GRANT ... ON ALL TABLES`, no `PUBLIC` grant, no default privilege, and no browser or service
role grant, and grants no `DELETE` or `TRUNCATE` anywhere. The four identity tables keep the Phase 3
read-only `SELECT` grant.

The three new verifier scripts pass against the local Compose stack:
`verify-phase-4d-migrations.sh` (per-concern round-trip and no drift), `verify-phase-4d-grants.sh`
(the exact least-privilege matrix by `has_table_privilege`, plus a live runtime session refused an
ungranted write), and `verify-phase-4d-functions.sh` (trigger advance, `replace_payroll_entries`
validation, `record_advance_repayment` idempotency, and `admin_execute_shift_swap` authorization and
atomicity). The Phase 4C static Supabase-reference scan still passes over all migrations, including
the three new ones. See [`PART_4D_COMPLETION.md`](PART_4D_COMPLETION.md) for the full evidence.

**Outstanding gate.** The independent GPT-5.6 security review is the one completion-gate item this
session did not run: the prerequisite review of the 4C schema, and the 4D review of the grant matrix
and every retained security-definer-equivalent function. The project owner authorized 4D and deferred
both reviews, so the code is committed and review-ready with this gate open. The grant matrix, table
by table, still needs the project owner's own sign-off, since the plan flags it as a decision
requiring project-owner approval.

## 4E: Synthetic fixtures

**Objective.** Turn the Phase 0 scenario catalogue in
[`docs/migration/phase-0/SYNTHETIC_TEST_DATA.md`](../phase-0/SYNTHETIC_TEST_DATA.md) into an
executable, version-controlled seed script, kept separate from schema migrations.

**Scope.**
- Compile the deterministic fixture manifest, fixed clock, UUIDv5 IDs, two tenants, four branches,
  14 employees, and golden financial cases, into an exact, checked-in specification, then
  implement a seed script against it.
- The seed script must be idempotent, safe to run repeatedly against a development database, and
  contain no real personal data.
- Seed data must reference `app_users` and `user_profiles` correctly so it stays usable once
  Phase 3's synthetic login flow points at the same database.

**Dependencies.** 4B, 4C, and 4D: the full schema and grants the seed writes through.

**Files and areas.** A new `backend/app/db/seed/` module and a fixture manifest document under
`docs/migration/phase-4/`.

**Decisions requiring project-owner approval.** Any fixture scenario Phase 0 left ambiguous, such
as which golden financial cases are load-bearing for later phase tests.

**Security and data boundaries.** The seed script runs as the migration identity or a dedicated
seed identity, never as `workloop_runtime`, and never in a path reachable from a production
deployment target without an explicit flag.

**Tests and negative tests.** Running the seed script twice produces no duplicates and no errors;
a test confirming seeded data satisfies every foreign key and check constraint added in 4B through
4D; a test confirming no seed record collides with the account-lifecycle states in a way the
identity resolver would misread.

**Rollback boundary.** Truncating and re-seeding is always safe, since this is synthetic data by
definition. Seed scripts are not migrations and are never part of the Alembic upgrade path.

**Completion gate.** The seed script runs against an empty, fully migrated database and produces
exactly the fixture manifest's documented dataset, matching Phase 0's scenario catalogue one to
one.

**Recommended model.** Sonnet 5. This is routine data generation against an already-approved
manifest and schema, matching the plan's guidance for repetitive conversions once the design is
fixed.

**Estimated effort.** One session once 4A through 4D are done and the manifest is final.

**Progress.** First increment landed on 2026-09-03. The seed lives in
`backend/app/db/seed/` and is its own executable manifest: 79 rows across 14 tables covering the
identity and organization spine (two tenants, four branches, 15 employees and their app-user
identities and profiles, Horizon Dubai departments, staffing rules, and shifts) plus the load-bearing
golden financial cases (the canonical payroll entry, the six advance states, the idempotent August
repayment, the golden expense claim, and the roster overtime row). It is deterministic and idempotent,
runs as the migration identity and refuses to run as `workloop_runtime`, touches only the two fixture
tenants, and is not on the Alembic path. Seeded `app_users` use a synthetic issuer distinct from the
live Keycloak issuer, so no row can resolve against a real token. `scripts/verify-phase-4e-seed.sh`
runs apply, idempotent re-apply, revalidate, and clean in CI; `backend/tests/test_seed_fixtures.py`
checks the manifest without a database. Two legacy-only Phase 0 fixtures (the null-company `H-LEG-001`
employee and `storage.objects` rows) are retired because the target schema forbids them. See
[`SYNTHETIC_FIXTURE_MANIFEST.md`](SYNTHETIC_FIXTURE_MANIFEST.md).

The 4E completion gate, a one-to-one match with the Phase 0 scenario catalogue, is not yet met: the
status-coverage rows for every leave, attendance, document, incident, appraisal, training, asset, and
cross-tenant negative-control case are the next increment.

## 4F: Clean-database, upgrade, security, and completion gate

**Objective.** Prove the full baseline works end to end and close Phase 4 with an independent
review.

**Scope.**
- Verify `alembic upgrade head` creates a complete, working database from empty, with no manual
  SQL console step required anywhere.
- Verify the downgrade boundaries documented at each part hold, empty-only where stated.
- Run the grant-boundary tests from 4D against a freshly created database, not just a
  hand-migrated one.
- Confirm zero references remain to `auth.users`, `auth.uid()`, `auth.email()`, `auth.role()`,
  Supabase roles, or `storage.*` anywhere in the migrated schema, functions, or seed script.
- Independent security review of the grant matrix and any retained security-definer-equivalent
  functions, following the same pattern used to close Phase 3.
- Write the Phase 4 completion record.

**Dependencies.** 4A through 4E complete, each passing its own tests.

**Files and areas.** CI configuration and a Phase 4 completion document under
`docs/migration/phase-4/`.

**Decisions requiring project-owner approval.** Sign-off that the completion gate is met before
Phase 5 starts building on this schema.

**Security and data boundaries.** This is the last chance to catch a privilege or reference
mistake before Phase 5 treats this schema as the source of truth for authorization.

**Tests and negative tests.** A full clean-create-and-upgrade run in CI on a throwaway database;
the Supabase-reference grep check as a hard CI gate, not a manual step; the grant-boundary tests
from 4D, re-run after a clean create.

**Rollback boundary.** Not applicable to this part directly; it verifies the rollback boundaries
documented by 4B through 4D actually hold.

**Completion gate.** Matches the migration plan: Alembic can create an empty Workloop database
from scratch and upgrade it to the latest schema without Supabase schemas, roles, or services,
verified in CI, with an independent security review on record.

**Recommended model.** GPT-5.6, for the same reason as 4A and 4D: this is the security review and
final gate for schema and database work, not routine implementation.

**Estimated effort.** One session, mostly verification and writing the completion record,
assuming 4A through 4E already passed their own tests.

## Work that belongs to later phases

- Authorization and tenant isolation, including the permission matrix, FastAPI scoping
  dependencies, and the RLS-as-defense-in-depth decision's execution: Phase 5. Phase 4 only has to
  make the schema shape usable by Phase 5, not implement enforcement.
- Business APIs and services built on the new tables: later phases, per the phase tracker.
- Frontend migration off Supabase queries and PostgREST syntax: a separate phase. Phase 4 only
  removes the database-side dependencies those queries relied on.
- File storage replacement for the two unmanaged buckets, `employee-documents` and
  `expense-receipts`: Phase 4 documents that they are unmanaged in SQL and does not implement a
  storage backend.
- Cloud deployment or provisioning on DigitalOcean or Azure: Phase 4 only confirms UUID generation
  and PostgreSQL version compatibility; provisioning is a deployment phase.

## Summary

Six parts, 4A through 4F, each individually authorizable, moving from decision and inventory work
in 4A through schema in 4B and 4C, privilege and function work in 4D, fixtures in 4E, to
verification and sign-off in 4F. GPT-5.6 for 4A, 4D, and 4F, since those carry the schema and
security decisions and review. GPT-5.6 Terra for 4B and 4C, bounded implementation against an
approved design. Sonnet 5 for 4E, routine seed generation once the manifest is fixed. No part
starts until the project owner authorizes it, and 4A's decisions must be approved before 4B can
start.
