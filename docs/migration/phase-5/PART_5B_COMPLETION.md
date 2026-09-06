# Phase 5B completion record

## Status

Phase 5B completed its local gate on 2026-09-06 after the project owner explicitly authorized it.
The work started from synchronized commit `dcf3931e8601a2bf58b67f4bad2200f06750d467` on branch
`migration/fastapi-keycloak`.

The commit containing this record must pass the existing GitHub workflow. The task handoff will
report that run, so this file does not need a second commit for the workflow ID. Phase 5C has not
started and requires separate project-owner authorization.

## Authorization principal

`ApplicationUserResolver` now returns one frozen `AuthorizationPrincipal` after access-token
verification. The principal contains only these database-derived fields:

- application user ID and active account status;
- business role and company ID; and
- employee ID and employee branch ID for manager and employee roles.

One bounded SQL statement joins `app_users`, `user_profiles`, `companies`, `employees`, and
`branches`. `LIMIT 2` catches duplicate joined results. The resolver requires one active account,
one matching profile, a valid `admin`, `manager`, or `employee` role, and consistent UUID links.
It rejects a missing company record and every malformed or mismatched result.

Admins resolve with company scope and null employee and branch scope. Managers and employees must
link to an employee in the same company and to a branch in that company. The employee must have
`active = true` and an employment status of `Active`, `Probation`, or `On Leave`. Missing,
inactive, terminated, cross-company, and cross-branch links fail closed.

The principal is a frozen, slotted dataclass. A caller cannot add or replace fields after
resolution. The compatibility name `ApplicationUser` refers to the same principal type, so the
Phase 3 application-user boundary does not create a second identity object.

## FastAPI dependencies

The authentication dependency now exposes the principal directly. Small dependencies provide:

- approved role sets for admin, manager, employee, or manager-and-employee callers;
- the database-derived tenant ID;
- the linked employee self ID;
- the trusted manager employee ID; and
- a request-time admin branch ID.

Role failure returns the approved `403 operation_not_permitted` response. Employee self identity
is available to managers and employees because the approved manager role includes self-service.
Manager identity is available only to managers.

The admin branch dependency reads only `X-Workloop-Branch-ID`. It returns `400 branch_required`
when the header is absent and `422 invalid_branch` when the value is malformed or repeated. A
well-formed UUID triggers a bounded lookup that matches both branch ID and the principal's company
ID. Missing branches and branches in another company return the same `404 resource_not_found`
response. The selected branch is returned for the current dependency call and never added to the
token, profile, or principal. Managers and employees cannot use the selector.

The migration frontend CORS allowlist now permits `X-Workloop-Branch-ID` from its existing exact
origin. No new origin, method, route, or browser authority was added.

## Failure and disclosure behavior

The Phase 3 responses remain unchanged:

- invalid token returns `401 invalid_access_token` with `WWW-Authenticate: Bearer`;
- unavailable or invalid application identity returns `403 application_account_unavailable`; and
- a timed-out or failed authorization lookup returns
  `503 application_account_lookup_unavailable`.

Lookup failures log only `application_user_lookup_failed` or
`authorization_scope_lookup_failed`. Responses and logs contain no token, subject, employee ID,
profile value, selected branch ID, SQL detail, or database exception. Email, Keycloak roles,
browser fields, unapproved headers, query values, request bodies, and caller-supplied IDs do not
enter principal resolution.

The access-token verifier was not changed. Its signature, RS256 algorithm, issuer, audience,
token-time, token-type, subject, JWKS, cache, refresh, and timeout checks remain the Phase 3
implementation.

## Test evidence

Focused work ran the authentication, application-user, authorization dependency, and CORS tests
several times. The final focused run passed 98 tests. It covered:

- exact principals for the Horizon admin, Aisha manager, and Ravi employee fixtures;
- eligible `Active`, `Probation`, and `On Leave` employee states;
- missing and duplicate accounts or profiles, pending and disabled accounts, malformed values,
  invalid roles, invalid role links, and inconsistent company, employee, or branch links;
- inactive, terminated, missing, cross-company, and cross-branch employees;
- role-set, tenant, employee-self, manager, and admin-branch dependencies;
- branch selector success plus the approved `400`, `422`, and safe `404` responses;
- rejection of manager and employee branch selection;
- ignored browser fields, emails, Keycloak roles, altered token claims, and caller IDs;
- timeout and connection failures, generic `503` behavior, and log and response leakage checks;
- principal immutability; and
- one database principal lookup when a route composes several authorization dependencies.

After the code settled, the single complete backend gate passed:

- Pytest: 157 passed;
- Ruff lint: passed;
- Ruff formatting check: 49 files already formatted;
- strict Pyright: zero errors and warnings; and
- dependency check: no broken requirements.

The existing local `.venv` launchers point to a Python installation that is no longer present.
The gate therefore used the Codex bundled Python 3.12.14 runtime with the repository virtual
environment's installed locked packages. GitHub will perform the clean locked installation and
run the same backend quality job.

The first post-push GitHub run, 34026961643, passed backend quality and frontend regression but
failed its live authentication job. The Phase 3 protocol verifier created an active temporary
`app_users` row without the profile that Phase 5B now requires. The verifier now creates one
temporary admin company and profile only for the active case, then removes the profile, account,
and company. Pending and disabled cases still have no profile and remain rejected. The replacement
GitHub run is reported in the task handoff instead of another documentation-only commit.

The corrected Keycloak and FastAPI verifier passed against the local stack. Its cleanup left
`companies`, `branches`, `employees`, `app_users`, and `user_profiles` empty. PostgreSQL remained
at version 16.15 and Alembic head `d307b9c1f25e`.

## Limits and rollback

Phase 5B added no business API route, repository, business-row query, transaction-local PostgreSQL
context, RLS policy, grant, helper function, Alembic revision, schema change, Keycloak realm change,
frontend feature, persistent fixture, secret, or external resource. The live verifier correction
uses only temporary synthetic identity rows and deletes them before exit.

Only synthetic fixture metadata was used. During setup for the live verifier, a backend rebuild
omitted `--no-deps`. Compose replaced the stopped database container with the repository's
PostgreSQL 17 image and attached the preserved volume. PostgreSQL detected the 16.15 data directory
and exited with the expected incompatibility error before server startup or initialization. The
database container was restored immediately with the exact PostgreSQL 16.15 image. It returned
healthy at `d307b9c1f25e` with all five identity-root counts at zero before and after the verifier.
No data conversion, initialization, or volume deletion occurred. Later service commands used
`--no-deps`.

The cloud cost change is zero.

Rollback consists of removing the expanded principal and dependencies and restoring the Phase 3
active-application-user result. There is no database or infrastructure rollback.

Phase 5C remains separate. It will add scoped repository statements and protected mutation guards
only after project-owner authorization.
