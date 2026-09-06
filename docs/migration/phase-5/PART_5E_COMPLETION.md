# Phase 5E completion record

## Status

Phase 5E completed its local gate on 2026-09-06 after the project owner authorized the phase and
the narrow bootstrap amendment recorded in `PERMISSION_MATRIX_AND_RLS_DESIGN.md`. Work started from
clean, synchronized commit `c8977f1011d4bd16462598e05bd6b3e033fb955a` on branch
`migration/fastapi-keycloak`. Alembic head is now `f52e0a1b9c34`.

The commit containing this record must pass the existing GitHub workflow. The task handoff reports
that run, so this file does not need another commit for the workflow ID. Phase 5F has not started
and requires separate project-owner authorization.

## Database enforcement

Revision `f52e0a1b9c34` enables RLS on these eight tables and no others:

- `companies`
- `branches`
- `app_users`
- `user_profiles`
- `employees`
- `employee_job_history`
- `departments`
- `department_staffing_rules`

The revision creates 27 command-specific policies. Each table, login, and SQL command has at most
one permissive policy. Select and delete policies use `USING`, insert policies use `WITH CHECK`, and
update policies use both. The tables do not use forced RLS, so the migration owner keeps the
approved migration and synthetic-seed path.

Human policies authenticate the direct runtime login, require the human actor shape and a business
date, resolve the issuer and subject through the fixed bootstrap function, and compare every
principal field with the transaction context. Admin policies enforce tenant or selected-branch
scope. Staff policies enforce the linked branch, employee self scope, or the current one-level
reporting relationship. Missing, malformed, partial, stale, mismatched, and guessed context values
return no rows.

The identity bootstrap policy exposes one active `app_users` candidate from issuer and subject
alone. It exposes no company, branch, profile, or employee row. The approved
`resolve_workloop_principal()` function supplies only the link fields FastAPI needs to perform its
independent principal checks. It resolves the bootstrap cycle without adding a business-table
bootstrap policy.

The portal-role function `is_scoped_active_app_user(uuid)` returns only a boolean. It requires a
direct runtime login, a fully valid admin context, and an active target account with one valid
same-company profile. It returns false for missing, disabled, malformed, or cross-tenant targets.

The dedicated `workloop_expiry_processing` login is created during initialization with no
privileged attributes or role membership. Its policies require the exact login, scheduled-job
actor kind, `expiry_processing` actor key, company, branch shape, and business date. It receives
only the approved column reads on the five Phase 5E source tables. It cannot execute human helper
functions or mutate a business row.

Runtime grants now match the Phase 5A SQL ceilings for the eight tables. The role-only update grant
on `user_profiles` is column-specific. No login receives wildcard privileges, grant option,
ownership, schema creation, privileged membership, or RLS bypass.

## Application boundary

`ApplicationUserResolver` now reads the narrow principal function after setting issuer and subject
inside its transaction. FastAPI still validates account status, profile identity, role shape,
company membership, employee eligibility, and branch membership before constructing the immutable
principal. The protected transaction factory rechecks the same fields before repository SQL.

Phase 5B dependencies and Phase 5C scoped repositories remain the primary authorization boundary.
RLS does not replace field allowlists, response projections, protected workflow checks, scoped
mutation predicates, affected-row checks, or all-row batch validation.

## Verification

The backend gate passed 239 tests. Ruff lint and formatting passed, strict Pyright reported no
errors or warnings, the dependency check found no broken requirements, and `git diff --check`
passed.

The frontend regression gate passed 32 unit tests, four migration-build isolation tests, the main
production build, and the migration production build. The main build retains its existing warning
for one generated chunk larger than 500 kB.

The database gate used the isolated Compose project `workloop-phase5e-verify` with PostgreSQL
17.11 and volume `workloop-phase5e-verify_postgres_data`. It never attached the preserved
PostgreSQL 16.15 volume. An empty database upgraded to `f52e0a1b9c34`, downgraded exactly to
`e418c0d7a6b3`, passed the removal checks, and upgraded to head again.

The Phase 5E verifier loaded only the 334 deterministic Phase 4E rows. It checked direct runtime
and expiry-login behavior, the live FastAPI principal resolver, and the Phase 5C scope objects. It
covered tenant and branch reads, selector-free branch creation, selected-branch mutation, employee
self access, current direct reports, stale reporting relationships, portal-role checks, and all
approved SQL commands on the eight tables.

Denial checks covered cross-tenant and cross-branch rows, unrelated employees, restricted identity
and history tables, disabled accounts, inactive managers, issuer and subject mismatch, missing and
partial context, malformed UUID context, guessed identifiers, wrong job actors, invalid job branch
scope, excluded expiry columns, and direct job mutation. Every denied mutation compared stored
state before and after the attempt.

Catalog checks pinned the 27 policy names, commands, roles, clause shapes, owners, table flags,
runtime grants, exact expiry columns, helper signatures, results, definer mode, volatility, search
paths, execute ACLs, role attributes, memberships, and object ownership. They also proved that the
other 46 target tables have no RLS policy or flag.

The inherited Phase 4 migration, schema, trigger, function, function-security, shift-swap
concurrency, repeated-seed, and boundary checks passed. The Phase 5C repository verifier and Phase
5D transaction-context and pool-isolation verifier also passed. All verifiers removed their
synthetic rows.

## Limits and rollback

Phase 5E adds no business route, frontend feature, Phase 5F policy, Keycloak change, cloud resource,
persistent fixture, real data, or committed secret. Cloud cost remains zero.

Downgrading `f52e0a1b9c34` to `e418c0d7a6b3` drops all 27 policies, disables RLS on the eight tables,
drops both Phase 5E functions, revokes the expiry-processing database grants, and restores the
Phase 5D runtime grants. The provisioned expiry login remains inert with no public-schema object
access. Removing the Phase 5E application resolver change and local role provisioning completes
the code rollback.

Phase 5F remains separate and has not started.
