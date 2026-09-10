# Phase 7C idempotency schema proposal

## Status

The project owner approved decision `7C-IDEM-D1` on 2026-09-10. Phase 7C implementation may use
this design. Any amendment requires a revised proposal before implementation.

## Verified preflight

- Branch `migration/fastapi-keycloak` is clean and synchronized with its remote at
  `b827e0daf771b31a005d5f6d99e6644f9acc5494`.
- The sole Alembic head is `2c4d6e8f0a1b`.
- No Docker container is running. The preserved volume `workloop-clinic_postgres_data` exists and
  remains untouched.
- Migration organization reads are authoritative. Legacy Supabase remains the sole organization
  write authority.
- The legacy writer entry points are `saveCompany`, `saveCompanyLogo`, `createBranch`, and
  `deleteBranch` in `src/utils/storage.js`. Their consumers are `src/components/CompanySettings.jsx`
  and `src/context/CompanyContext.jsx`.
- Revision ID `31d7b4c8e2f0` is unused. The proposed migration is
  `backend/alembic/versions/31d7b4c8e2f0_add_idempotency_records.py`, with
  `down_revision = "2c4d6e8f0a1b"`.
- The final isolated stack will use Compose project `workloop-phase7c-final`, PostgreSQL port 25432,
  API port 28000, and Keycloak ports 28080 and 29000. Those ports were free during this preflight.
  Its PostgreSQL volume will be `workloop-phase7c-final_postgres_data` and will be deleted after the
  evidence is recorded.
- Existing deterministic company, branch, and application-user fixtures remain the data source.
  Phase 7C will add deterministic idempotency keys and one created-branch UUID to a new
  `tests/fixtures/phase-7c` fixture. It will not change Phase 7B fixture identities.

## Proposed record

Create `public.idempotency_records` with these columns:

| Column | PostgreSQL type | Null | Default | Rule |
| --- | --- | --- | --- | --- |
| `app_user_id` | `uuid` | No | None | The verified application user. |
| `idempotency_key` | `uuid` | No | None | A canonical UUIDv4 parsed from `Idempotency-Key`. |
| `company_id` | `uuid` | No | None | The verified tenant at claim time. |
| `branch_id` | `uuid` | Yes | None | The verified branch, or null for a tenant-scoped operation. |
| `operation_id` | `text` | No | None | The explicit OpenAPI operation ID. |
| `http_method` | `text` | No | None | The uppercase command method. |
| `route_parameters` | `jsonb` | No | None | An object containing canonical route parameter strings. |
| `fingerprint_version` | `text` | No | None | The canonicalizer version used for this request. |
| `request_fingerprint` | `text` | No | None | The 64-character lowercase SHA-256 digest. |
| `replay_resource_kind` | `text` | Yes | None | The operation registry's authorization strategy after completion. |
| `replay_resource_id` | `uuid` | Yes | None | The resource that must remain visible, when the strategy needs one. |
| `response_status` | `smallint` | Yes | None | The committed 2xx status. |
| `response_body` | `jsonb` | Yes | None | The complete JSON response body. SQL null is used only for 204. |
| `response_location` | `text` | Yes | None | The relative `Location` value, when present. |
| `created_at` | `timestamptz` | No | `statement_timestamp()` | Reservation time. |
| `completed_at` | `timestamptz` | Yes | None | Completion time set before the transaction commits. |
| `retain_until` | `timestamptz` | Yes | None | Earliest permitted cleanup time. |

The primary key is `(app_user_id, idempotency_key)`. This makes a key unique for one verified user
across every operation, as Phase 6 requires.

The foreign keys are:

- `(app_user_id, company_id)` to
  `user_profiles(app_user_id, company_id) ON DELETE RESTRICT`;
- `company_id` to `companies(id) ON DELETE RESTRICT`; and
- `(branch_id, company_id)` to `branches(id, company_id) ON DELETE RESTRICT`.

The first key prevents a claim from recording a user under another tenant. The nullable branch key
prevents a branch scope from crossing tenants. Retained records may delay profile or tenant cleanup
until their seven-day floor expires. That is intentional.

Create an index on `(company_id, retain_until, created_at)` for bounded cleanup. Do not add an index
on the fingerprint or response fields.

## Constraints

The migration adds named checks with these exact rules:

- `idempotency_key` has UUID version 4.
- `operation_id` matches `^[a-z][a-z0-9_]{0,127}$`.
- `http_method` is one of `POST`, `PATCH`, `PUT`, or `DELETE`.
- `route_parameters` is a JSON object.
- `fingerprint_version` matches `^wlp-idem-fp-v[1-9][0-9]{0,3}$`.
- `request_fingerprint` matches `^[0-9a-f]{64}$`.
- `replay_resource_kind`, when present, matches `^[a-z][a-z0-9_]{0,63}$`.
- A reserved row has all completion columns null.
- A completed row has `replay_resource_kind`, `response_status`, `completed_at`, and `retain_until`.
- A completed status is from 200 through 299.
- `response_body` is SQL null only for status 204. Every other stored body is a JSON object.
- `response_location`, when present, is at most 2,048 bytes, begins with one `/`, does not begin
  with `//`, contains no carriage return or line feed, and accompanies status 201 or 202.
- `completed_at` is not earlier than `created_at`.
- `retain_until` is at least seven days after `completed_at`.
- `replay_resource_id` is required when `replay_resource_kind` is `branch`, `employee`,
  `department`, or `user_profile`. It is null when the kind is `tenant`.

Two non-callable trigger functions owned by `workloop_migration` enforce the reservation lifecycle.
A `BEFORE INSERT` trigger rejects completion values on the initial claim. A deferred constraint
trigger reads the current primary-key row at commit and rejects a reservation that was not
completed.
Both functions set `search_path` to `pg_catalog, public, pg_temp`; `PUBLIC` and runtime receive no
execute grant. A rollback removes the uncommitted reservation with the business mutation and audit
event.

The completion update may set only `replay_resource_kind`, `replay_resource_id`, `response_status`,
`response_body`, `response_location`, `completed_at`, and `retain_until`. Claim and fingerprint
columns remain immutable because runtime receives no update grant on them. The update policy also
rejects a second completion update.

## Request scope and fingerprint

The service validates authentication, principal state, route authorization, shared headers, route,
query, and body before it claims a key. Invalid work never stores a row.

The stored scope consists of `app_user_id`, `company_id`, nullable `branch_id`, `operation_id`,
`http_method`, and `route_parameters`. A retry must match every value. A difference returns
`409 idempotency_conflict` without disclosing the original scope, request, or result.

The fingerprint implementation is `wlp-idem-fp-v1` from the Phase 6 contract. Its root is the typed
object below, with member pairs sorted by Unicode code point before RFC 8785 serialization:

```text
["object",[
  ["body",<typed normalized body>],
  ["effectiveQueryParameters",<typed normalized query object>],
  ["fingerprintVersion",["string","wlp-idem-fp-v1"]],
  ["method",["string",<uppercase method>]],
  ["operationId",["string",<OpenAPI operation ID>]],
  ["routeParameters",<typed normalized route object>]
]]
```

The scalar, absent, null, array, and object encodings remain exactly those in the Phase 6 contract.
The service hashes the RFC 8785 UTF-8 bytes with SHA-256 and stores the lowercase hexadecimal
digest. It keeps the implementation for every fingerprint version referenced by a retained row.

For Phase 7C branch creation, the stored scope is operation ID `create_branch`, method `POST`, the
current company, null branch, and `{}` route parameters. The fingerprint contains an empty effective
query object and every strictly validated `BranchCreateRequest` field. Omitted fields use their
declared normalized defaults. Fields without a default use the typed absent value and differ from
JSON null.

The advisory lock key remains the Phase 6 definition. It uses the first eight bytes in network byte
order of SHA-256 over the UTF-8 string `wlp-idem-lock-v1`, a zero byte, canonical `app_user_id`, a
zero byte, and canonical `idempotency_key`. The bytes are interpreted as a signed 64-bit integer for
`pg_try_advisory_xact_lock`. Failure returns `409 idempotency_in_progress` with `Retry-After: 1`.

## Stored response and replay authorization

Only a committed 2xx result is stored. The record contains the complete response status and JSON
body, plus the relative `Location` value when the operation returns one. It stores no other header,
token, authorization context, request body, correlation ID, error, or log data.

The operation registry owns replay authorization. It binds each `operation_id` to one expected
`replay_resource_kind` and one authorization callback. A stored kind that does not match the
registry is an internal error and is never replayed.

`create_branch` stores kind `branch` and the created branch ID. Before replay, the current request
must again pass authentication, active-account resolution, selector-free admin authorization, and
tenant scope. The callback then verifies that the stored branch still exists in the current company
and remains visible to that admin. Lost role or company access returns the normal safe 403. A
missing or inaccessible branch returns `404 resource_not_found`. Neither response reveals that a
record exists.

A successful replay returns the stored status, body, and `Location`. The HTTP layer generates a new
correlation ID and current transport headers, then adds `Idempotency-Replayed: true`. The mutation,
audit append, and response completion code do not run again.

The two recovery routes required by Phase 6 ship with this first idempotent business mutation:

- `GET /api/v1/idempotency-recovery-namespaces`; and
- `GET /api/v1/idempotency-status`, with one canonical `Idempotency-Key` header and no key in the
  URL.

Status uses the same nonblocking advisory lock. A held lock returns `in_progress`. After obtaining
the lock, an owned committed row returns `completed`; no owned row returns `not_found`. The route
never returns the stored response or another user's status.

## Retention and cleanup

Completion sets `retain_until` to exactly `completed_at + interval '7 days'`. Runtime cannot delete
a row before that instant. The client also discards unresolved browser records after seven days and
must not retry an intent after that window.

Protected idempotency and status requests may delete at most 100 expired rows for the current
company inside their authorized transaction, ordered by `retain_until`, `created_at`, `app_user_id`,
and `idempotency_key`. Cleanup never crosses the verified company and does not affect claim
correctness. An expired row may remain longer than seven days if no bounded cleanup reaches it.
Reusing an old key is still outside the client contract.

The recovery namespace configuration adds these backend settings:

- `IDEMPOTENCY_RECOVERY_CURRENT_KEY_ID`, exactly eight lowercase hexadecimal characters;
- `IDEMPOTENCY_RECOVERY_CURRENT_KEY`, unpadded base64url encoding of exactly 32 random bytes; and
- `IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS`, a JSON array that defaults to `[]`. Each entry has a unique
  eight-character `keyId`, a 32-byte unpadded base64url `key`, and an RFC 3339 UTC `acceptUntil`.

The accepted list contains the current namespace and previous namespaces whose `acceptUntil` has not
passed. Rotation must keep a previous key accepted for at least seven days. These secrets are not
stored in the database, exposed through a `VITE_` setting, reused, or committed with real values.

## RLS and grants

The migration enables and forces RLS on `idempotency_records`. Every runtime policy repeats the
existing trusted human context and requires a currently resolved active principal.

- Select is limited to rows whose `app_user_id` and `company_id` match the current principal. It
  does not compare the current branch, because a key is unique across operations and the
  selector-free status route must find an owned claim from any stored scope.
- Insert requires the current `app_user_id` and `company_id`. `branch_id` must be null-safe equal to
  the verified transaction branch. Completion columns must be null.
- Update requires the current user and company, a null-safe branch match, and an incomplete row. The
  post-update row must be complete. Column grants restrict the update to completion columns.
- Delete requires the current company and `retain_until <= statement_timestamp()`. This lets any
  current active principal perform bounded tenant cleanup without reading another user's row.

`workloop_runtime` receives table `SELECT`, `INSERT`, and `DELETE`, plus column-level `UPDATE` for
the seven completion columns. `workloop_migration` owns the table and trigger functions. `PUBLIC`,
`workloop_expiry_processing`, browser roles, and legacy roles receive no privilege. The migration
adds no default privilege and no grant on all tables.

## Model and migration parity

Add `IdempotencyRecord` in `backend/app/models/idempotency.py` and export it from
`backend/app/models/__init__.py`. The SQLAlchemy table must match every column, primary key, foreign
key, check, and index above. The Alembic migration alone owns trigger, RLS, policy, ownership, and
grant DDL.

The downgrade revokes grants, drops policies and triggers, drops both trigger functions, drops the
table, and leaves revision `2c4d6e8f0a1b` as the sole head. It does not alter business rows, audit
events, identity data, or the preserved volume.

## Planned implementation artifacts

Approval authorizes these idempotency-specific artifacts as part of Phase 7C:

- the Alembic migration and SQLAlchemy model named above;
- `backend/app/repositories/idempotency.py` for claim, completion, lookup, and bounded cleanup SQL;
- `backend/app/services/idempotency.py` for locking, scope comparison, replay authorization, status,
  and namespace generation;
- `backend/app/http/idempotency_fingerprint.py` for the typed tree, RFC 8785 serialization, and
  version registry;
- extensions to `backend/app/http/idempotency.py`, `backend/app/core/config.py`, application wiring,
  OpenAPI, and environment templates;
- the two recovery routes;
- focused backend unit, migration, RLS, concurrency, rollback, retention, and model-parity tests;
  and
- a deterministic `tests/fixtures/phase-7c` fixture and Phase 7C verifier.

This proposal does not approve a new audit action, a protected-function allowlist change, a broader
grant, another table, or another migration. Phase 7C must stop for owner review if implementation
finds one necessary.

## Decision record

`7C-IDEM-D1` approves the `idempotency_records` table, constraints, request scope, fingerprint,
stored response, replay authorization, seven-day retention rule, bounded cleanup, RLS, grants,
configuration, SQLAlchemy model, Alembic revision `31d7b4c8e2f0`, downgrade, and planned artifacts
exactly as specified in this document.

The project owner approved this decision on 2026-09-10. The approval covers this design and the
already authorized Phase 7C organization mutations. It does not authorize Phase 7D.

Decision `7C-IDEM-D2`, approved on 2026-09-10, amends only the cleanup mechanism. See
`PART_7C_IDEMPOTENCY_SCHEMA_AMENDMENT.md` for the approved security-definer function and direct
runtime `DELETE` revocation.
