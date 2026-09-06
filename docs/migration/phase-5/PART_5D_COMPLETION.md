# Phase 5D completion record

## Status

Phase 5D completed its local gate on 2026-09-06 after the project owner explicitly authorized it.
Work started from clean, synchronized commit `555557ee44cdaa55144bd378c241c56a5313aacd` on branch
`migration/fastapi-keycloak`. Alembic head is now `e418c0d7a6b3`.

The commit containing this record must pass the existing GitHub workflow. The task handoff will
report that run, so this file does not need a second commit for the workflow ID. Phase 5E has not
started and requires separate project-owner authorization.

## Transaction context

The application now uses the ten approved settings and no others:

- `workloop.identity_issuer`
- `workloop.identity_subject`
- `workloop.app_user_id`
- `workloop.role`
- `workloop.company_id`
- `workloop.employee_id`
- `workloop.branch_id`
- `workloop.actor_kind`
- `workloop.actor_key`
- `workloop.business_date`

The application-user lookup sets only issuer and subject, as bound values, inside the explicit
transaction that performs the identity lookup. The protected transaction factory sets all ten
keys with transaction-local `set_config` calls. It derives issuer and subject from verified token
claims. It derives the application user, role, company, employee, and staff branch from the frozen
Phase 5B principal. An admin branch comes only from the Phase 5B verified branch dependency. The
factory derives the business date from a timezone-aware clock converted to `Asia/Dubai`. Human
transactions set actor kind to `human` and leave actor key blank.

Before yielding a connection, the same transaction rechecks the current database login, session
login, active account, issuer, subject, single profile, role, company, employee link, employment
eligibility, employee branch, and optional admin branch. A mismatch raises the existing safe
application-account denial before protected SQL runs. FastAPI dependencies keep the transaction
open for the full repository operation. Tenant transactions and verified admin-branch
transactions have separate dependencies.

The application does not log context values. The SQL text contains fixed setting names and bound
value placeholders. FastAPI still owns the database credential, and callers cannot submit SQL or
choose a context key. Phase 5C predicates and repositories remain the primary authorization
boundary. The database context is for the later defense-in-depth RLS policies.

## Database readers and privileges

Revision `e418c0d7a6b3` adds ten fixed, zero-argument context readers. Text readers reject blank and
overlength values. UUID and date readers use PostgreSQL input validation before conversion. Role,
actor-kind, and actor-key readers use exact allowlists. Missing, blank, malformed, and out-of-set
values return SQL `NULL` instead of raising or widening access.

Every reader is `STABLE`, `SECURITY INVOKER`, owned by `workloop_migration`, and has
`search_path=pg_catalog, pg_temp`. The revision revokes every `PUBLIC` privilege and grants only
`EXECUTE` to `workloop_runtime`. It adds no definer-rights helper and no database role.

`workloop_runtime` remains a direct `LOGIN` with `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`,
`NOREPLICATION`, and `NOBYPASSRLS`. It has no role membership, object ownership, or schema-create
privilege. Direct `SET ROLE workloop_migration` and object creation in `public` both fail.

## Verification

The focused authorization tests passed 64 tests after adding transaction-dependency coverage. The
complete backend gate passed:

- Pytest: 238 passed.
- Ruff lint: passed.
- Ruff formatting check: 60 files already formatted.
- Strict Pyright: zero errors and warnings.
- Dependency check: no broken requirements.
- `git diff --check`: passed.

The frontend regression gate passed 32 unit tests and the production build. The four migration
frontend isolation tests and the migration production build also passed. The legacy production
build retains its existing warning for one generated chunk larger than 500 kB.

The database gate used the isolated Compose project `workloop-phase5d-verify` with PostgreSQL
17.11 and volume `workloop-phase5d-verify_postgres_data`. It upgraded an empty database to
`e418c0d7a6b3`, downgraded exactly to `d307b9c1f25e`, proved all ten readers were gone while runtime
role boundaries remained unchanged, and upgraded to head again.

The Phase 5D verifier created a disposable four-row RLS probe outside the business schema contract,
loaded the 334 synthetic Phase 4E rows, and then proved:

- context visibility inside a protected transaction and absence after commit, explicit rollback,
  application exception, cancellation, and pool return;
- no identity or scope crossover among concurrent Horizon admin, manager, employee, and Cedar
  admin transactions;
- denial of incomplete context, malformed text, UUID, role, and date values, a scheduled-job actor
  on the runtime login, stale principals, issuer and subject mismatch, and the migration login;
- denied reads and updates affected no probe row; and
- exact helper owner, signature, invoker mode, stability, search path, and ACL state.

The verifier removed the probe and all 334 fixture rows. The inherited Phase 4 schema, per-revision
migration, grant, trigger, retained-function, function-security, shift-swap concurrency, repeated
seed, and boundary checks passed. The Phase 5C scoped-repository verifier also passed and removed
its fixtures.

After the gate, the isolated container, network, and PostgreSQL 17.11 volume were removed. They
contained only disposable synthetic data and cannot be recovered. The preserved PostgreSQL 16.15
container remained healthy on `workloop-clinic_postgres_data` at Alembic head `d307b9c1f25e`.
Final read-only counts for companies, branches, employees, application users, and profiles were
all zero. The preserved volume was never attached to PostgreSQL 17.

During the local pass, the new verifier first compared against the Phase 4E fixture date instead
of the injected Phase 5D date. A second pass showed that the disposable policy did not yet require
issuer and subject. Both test defects were corrected. The inherited Phase 4D migration and
function-security scripts also assumed no later migration or public function could exist. They now
test their own Phase 4D objects and return the database to the current project head. All corrected
runs passed.

## Limits and rollback

Phase 5D added no business route, service, RLS policy on a business table, table grant, database
role, definer-rights function, Keycloak change, frontend feature, secret, cloud resource, persistent
fixture, or real data. Cloud cost remains zero.

Downgrade `e418c0d7a6b3` to `d307b9c1f25e` to drop the ten readers and their execute grants. The
application transaction factory, FastAPI transaction dependencies, identity-bootstrap setting,
tests, verifier, workflow steps, and Compose override can then be removed independently. No later
application code or RLS policy depends on them yet.

Phase 5E remains separate and has not started.
