# Phase 5C completion record

## Status

Phase 5C completed its local gate on 2026-09-06 after the project owner explicitly authorized it.
The work started from synchronized commit `df076cd7e8ab3f1413c5273b42942807db2ebfff` on branch
`migration/fastapi-keycloak`.

The commit containing this record must pass the existing GitHub workflow. The task handoff will
report that run, so this file does not need a second commit for the workflow ID. Phase 5D has not
started and requires separate project-owner authorization.

## Canonical scope rules

`app.auth.scopes` now defines frozen authorization scopes and SQLAlchemy predicates for:

- tenant ownership by `company_id`;
- branch ownership by both `company_id` and `branch_id`;
- employee self access by company, branch, and linked employee;
- one-level direct reports through the current `employees.reporting_manager_id` relationship;
- active leave delegation through inclusive dates and the approver's current direct reports; and
- the approved expiry-processing actor limited to one company and optional branch.

The factories accept the Phase 5B principal. An admin branch scope requires the branch ID already
verified by the Phase 5B dependency. Staff cannot replace their linked branch with an admin
selector. Self and team scopes require the approved role and linked employee shape.

Direct-report predicates use a correlated `EXISTS` query. Each statement checks the target
employee's current company, branch, and reporting manager. It also rechecks the manager's active
account, manager profile, active employee row, and eligible employment status. No helper returns or
caches a report-ID list.

The leave-delegate predicate is separate from general manager scope. Each statement checks the
inclusive business date, current report relationship, same company and branch, eligible approver
and delegate employees, the approver's active manager profile, and the delegate's active manager or
employee profile. Delegation grants no predicate for another domain.

The system scope recognizes only `workloop_expiry_processing`. The login and transaction context
remain Phase 5D work. Migration and seed access keep their existing separate paths.

## Scoped repository statements

`app.repositories.scoped` provides one construction path for scoped collections, object lookups,
updates, and deletes. An object lookup combines the object ID and authorization predicate in its
first statement. A missing UUID and a UUID outside the caller's scope both raise the same
`ResourceNotFoundError`.

Every update and delete repeats the object IDs, authorization predicate, and optional state guards
in the mutation statement. The repository locks and validates every requested row under that same
scope before a batch mutation. Empty and duplicate batches fail before SQL. A nested transaction
rolls back the whole mutation when the locked set or affected-row count differs from the requested
set. One allowed row cannot make a mixed batch succeed.

If every object is visible but an affected-row check fails after the lock, the repository raises
`MutationConflictError`. The calling workflow can map that result to its approved safe `409` code.
Scope failure still raises only `ResourceNotFoundError`, so this distinction reveals no inaccessible
row.

SQLAlchemy binds object IDs, scope values, dates, and mutation values. The statement tests confirm
that an injection-shaped object value stays out of the SQL text.

## Mutation field guards

`app.schemas.mutations` adds strict Pydantic mutation input support and `MutationFieldGuard`.
Every action supplies an exact input allowlist. Role, tenant, branch, employee ownership,
reporting manager, salary and bank data, workflow state, payroll state, audit actors, and audit
timestamps need a separate protected-field approval before an action may accept them.

Server-derived fields must be supplied as one exact set by the service. A request body cannot
replace them. The approved branch behavior is supported: a body may omit the branch or repeat the
verified branch, but a different branch fails. The guard returns immutable
`GuardedMutationValues`, and scoped update helpers do not accept a raw request dictionary.

This part defines the shared mechanism. Later feature repositories must declare their action-level
allowlists from the Phase 5A catalogue rather than create a broad generic patch model.

## Test evidence

The focused authorization run passed 68 tests. It covered:

- tenant, admin branch, staff branch, employee self, direct-report, delegate, and system scopes;
- rejection of missing admin branch scope, staff branch selection, and non-manager team scope;
- current manager account and profile checks without cached report identifiers;
- active, expired, and future delegation dates plus current approver and delegate eligibility;
- object identity and authorization in the same lookup, update, and delete statements;
- bound injection-shaped values;
- empty and duplicate batch rejection;
- mixed-scope batch rollback with unchanged state;
- strict Pydantic fields, the protected-field catalogue, exact workflow approval, immutable guarded
  values, and server-derived field checks; and
- matching and conflicting body branch values.

The database verifier ran against an isolated PostgreSQL 17.11 container upgraded to Alembic head
`d307b9c1f25e`. It loaded the 334 Phase 4E rows, tested Horizon against Cedar, Dubai against Abu
Dhabi, Ravi self against other employees, Aisha's current reports, Fatima's active leave
delegation, guessed UUIDs, expired and future delegation, disabled manager and delegate accounts,
manager reassignment, and a mixed Horizon and Cedar batch. The denied batch left Ravi's row
unchanged. A stale state predicate returned a conflict and also left Ravi's row unchanged. The
verifier rolled back temporary relationship and date changes, removed all fixture rows, and exited
successfully.

The verifier's first container invocation could not import `app` because Python used the mounted
script directory as its import root. It failed before fixture setup. The workflow now invokes the
mounted file through `runpy` from `/app`, which keeps the application package on the import path.
The corrected invocation passed repeatedly, including after the field-guard hardening and the final
conflict-semantics change.

After the code settled, the complete backend gate passed:

- Pytest: 225 passed;
- Ruff lint: passed;
- Ruff formatting check: 58 files already formatted;
- strict Pyright: zero errors and warnings;
- dependency check: no broken requirements; and
- `git diff --check`: passed.

The unchanged frontend regression check also passed 32 unit tests and the production build. The
build kept its existing warning for a generated chunk larger than 500 kB.

The existing local `.venv` launchers point to a removed Python installation. The gate used the
Codex bundled Python 3.12.14 runtime with the repository virtual environment's installed locked
packages. GitHub will perform a clean locked installation and run the same backend quality job.

The full-stack workflow now runs the Phase 5C database verifier after the existing Phase 4E seed
gate. It mounts the verifier read-only into the migration container. The verifier always cleans its
own synthetic rows, including after an assertion failure.

## Limits and rollback

Phase 5C added no business route, business service, frontend consumer, PostgreSQL context, RLS
policy, grant, function, role, Alembic revision, schema change, Keycloak change, secret, persistent
fixture, cloud resource, or real data.

The local database gate created one temporary PostgreSQL 17.11 container, named volume, network,
and backend image. All four were removed after the verifier passed. The preserved PostgreSQL 16.15
container and `workloop-clinic_postgres_data` volume stayed running and were not attached to the
test container. A final read-only check found PostgreSQL 16.15 healthy at Alembic head
`d307b9c1f25e`, with zero rows in `companies`, `branches`, `employees`, `app_users`, and
`user_profiles`. No secret was created. The cloud cost change is zero.

Rollback consists of removing the scope, repository, mutation-guard, test, and verifier files and
restoring the workflow and exports. There is no database or infrastructure rollback.

Phase 5D remains separate. It will add transaction-local PostgreSQL context and pool-isolation
checks only after project-owner authorization.
