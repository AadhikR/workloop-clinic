# Phase 3B identity schema

## Status

**Local implementation and validation completed on 2026-08-31. GitHub checks are pending.**

Phase 3B adds the smallest Workloop-owned identity schema needed for later token-to-user
resolution. It creates no Keycloak realm, OIDC client, login flow, frontend, seed data, or business
module.

## Schema

The `f41c9a7b23d1` Alembic revision creates two PostgreSQL enum types:

- `account_status`: `pending_identity`, `active`, and `disabled`.
- `app_role`: `admin`, `manager`, and `employee`.

It creates four tables:

- `companies` has only an application-owned UUID key.
- `employees` has an application-owned UUID key and a required company link.
- `app_users` has an application-owned UUID key, opaque `identity_issuer` and
  `identity_subject` fields, a unique issuer and subject pair, and account status.
- `user_profiles` has one row per application user, a PostgreSQL role, a required company link,
  and an optional employee link.

An employee profile must reference an employee in the same company. Admin profiles cannot reference
an employee. Manager and employee profiles must reference one. Every foreign key uses `RESTRICT` so
identity records cannot be silently removed through a parent deletion.

Keycloak remains responsible for credentials. Workloop stores no password, token, email ownership
key, Keycloak role, realm configuration, or client configuration.

## Database access

`workloop_migration` owns the `workloop` database, both enum types, and all identity tables. The
revision grants `workloop_runtime` only `USAGE` on `public` and `SELECT` on the four identity tables.
Phase 3B has no runtime write path, so it grants no insert, update, delete, schema-create, ownership,
or migration privilege to FastAPI.

Later migrations must grant runtime privileges explicitly for any reviewed runtime operation. They
must not widen this role through `PUBLIC` or default privileges.

## Validation

`scripts/verify-phase-3b-schema.sh` runs against the local Compose stack. It verifies:

- The four expected tables and two enum types exist.
- The migration identity owns every identity table.
- Duplicate issuer and subject mappings fail.
- Invalid enum values and invalid role to employee combinations fail.
- Cross-company employee profile links and parent deletion fail.
- The runtime identity can read but cannot write.

The GitHub full-stack job creates a fresh database, applies the revision, repeats the upgrade, runs an
empty-schema downgrade followed by a final upgrade, and confirms the final Workloop table count.

The local validation on 2026-08-31 passed the script, a repeated `upgrade head`, `alembic check`, a
bounded `downgrade base` followed by `upgrade head`, FastAPI and Keycloak health checks, nine backend
tests, Ruff, strict Pyright, `pip check`, 14 frontend unit tests, and the frontend production build.

## Correction boundary

This revision can downgrade only when the identity schema is empty. The local downgrade check ran with
no identity records. Do not downgrade a populated Workloop database. Add an append-only Alembic
revision for any shared or populated-schema correction.

## Completion gate

The local gate passed. Phase 3B remains incomplete until the GitHub workflow passes on the commit that
contains this revision and documentation. Phase 3C remains on hold until the project owner authorizes
it.
