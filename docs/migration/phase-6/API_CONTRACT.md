# Phase 6A API contract

## Status

This is the canonical Phase 6A contract. Phase 6A started with project-owner authorization on
2026-09-07. The project owner approved decisions `6A-D1` through `6A-D14` without amendment on the
same date. No runtime or schema work is authorized by this document.

The contract governs new business endpoints under `/api/v1`. The existing health and Phase 3
authentication endpoints must adopt the common error and correlation rules in Phase 6B. The health
success body stays unchanged. Parts 6B through 6G remain separately gated.

## Sources and precedence

This document applies the authentication rules in
[`AUTHENTICATION_DESIGN.md`](../phase-3/AUTHENTICATION_DESIGN.md), the database and authorization
rules in [`PERMISSION_MATRIX_AND_RLS_DESIGN.md`](../phase-5/PERMISSION_MATRIX_AND_RLS_DESIGN.md),
and the Phase 6 scope in [`SUBPHASE_PLAN.md`](SUBPHASE_PLAN.md). Those documents control if a later
route design conflicts with this HTTP contract.

Keycloak proves identity. PostgreSQL supplies application status, role, company, employee, branch,
and business authorization. A request field, query parameter, route identifier, token role, or
frontend state never grants business scope.

## Decision register

| ID | Category | Approved contract | Reason |
|---|---|---|---|
| `6A-D1` | Path and media type | New application endpoints use `/api/v1`. JSON requests and responses use `application/json` encoded as UTF-8. | One versioned namespace and media type keeps the first client small. |
| `6A-D2` | JSON names and scalar values | JSON property names use `camelCase`. UUIDs, dates, times, instants, decimals, money, nulls, and enums use the exact forms below. | React receives native property names while Python and PostgreSQL keep `snake_case` internally. |
| `6A-D3` | Schemas and success responses | Every operation has separate strict request and response schemas. Success responses use the status and envelope rules below. | Database rows cannot leak through an implicit serializer. |
| `6A-D4` | Lists and pagination | Collections use an opaque cursor with default limit 50 and maximum limit 100. Responses contain `data` and `page`. | Cursor pagination stays stable while authorized rows change. |
| `6A-D5` | Filtering and sorting | Each operation publishes exact filter and sort allowlists. Unknown, repeated, or malformed parameters fail validation. | No route grows an accidental query language or silently ignores mistakes. |
| `6A-D6` | Errors | Every API error uses the single body, safe message, code, and status registry below. | The frontend can branch on codes without displaying internals. |
| `6A-D7` | Correlation | FastAPI generates one lowercase UUIDv4 per request and returns it in `X-Correlation-ID`. Client-supplied correlation headers are ignored. | Callers can report a failure without choosing a trusted log identifier. |
| `6A-D8` | Transactions | The service is the logical owner of one authorized transaction. The existing authorization transaction factory opens, commits, or rolls it back. Handlers and repositories never commit. | RLS context, protected SQL, and the business change stay in one transaction. |
| `6A-D9` | Idempotency | Named financial and approval mutations require a canonical UUIDv4 `Idempotency-Key`, scoped and replayed as specified below, with a seven-day completed-record retention floor. | A lost response can be retried without duplicating a protected change. |
| `6A-D10` | CORS | Local CORS allows only `http://127.0.0.1:5174`. The cloud allowlist remains empty until Part 6G approves one exact HTTPS frontend origin. Credentials are disabled. | This preserves the approved loopback build and prevents premature cloud exposure. |
| `6A-D11` | Body and upload limits | Ordinary requests allow 1 MiB. A future upload route may allow one 10 MiB file inside a 12 MiB request. Request content encoding is not accepted. | Limits are large enough for structured HR data and bounded for future documents. |
| `6A-D12` | Timeouts and cancellation | Ordinary API work has a 15-second server deadline and a 20-second browser deadline. Health keeps 5 seconds. Future proxied uploads use 60 and 70 seconds. | The server rolls back before the caller gives up, including on cancellation. |
| `6A-D13` | Rate limiting | Public exposure requires the exact per-minute limits and trusted-key rules below. A `429` includes `Retry-After`. | Authentication and idempotency do not replace traffic controls. |
| `6A-D14` | OpenAPI and compatibility | Explicit operation IDs and reviewed schemas are required. Breaking changes stay in `/api/v1` only before a consumer ships; otherwise they require `/api/v2`. | Generated OpenAPI becomes a checked contract, not incidental output. |

## JSON representation

### Names and objects

- External JSON property names use `camelCase`. Python models and PostgreSQL columns keep
  `snake_case`; explicit schema aliases translate between them.
- Request models reject unknown properties. They do not accept aliases, database column names, or
  case variants.
- Response models serialize only declared properties. They never serialize ORM objects, exception
  objects, authorization context, or arbitrary JSONB without a response schema.
- JSON objects reject duplicate property names. JSON request bodies must contain one value and no
  trailing data.

### Scalar forms

| Value | JSON form | Rule |
|---|---|---|
| UUID | string | Canonical lowercase `8-4-4-4-12` hexadecimal form. Braces, URNs, uppercase, whitespace, and compact forms are invalid. |
| Date | string | `YYYY-MM-DD`, interpreted as a calendar date. |
| Time | string | `HH:MM:SS` with required seconds and no offset. It represents a wall-clock or shift-template time. |
| Instant | string | UTC RFC 3339 form `YYYY-MM-DDTHH:MM:SS.sssZ`, with exactly three fractional digits. Requests with an explicit offset are normalized only when an operation accepts a caller-supplied instant. Responses always use `Z`. |
| Decimal | string | Plain base-10 notation with no exponent, plus sign, surrounding whitespace, leading zero except before the decimal point, or negative zero. The operation schema fixes precision and scale. |
| Money | string | Exactly two fractional digits. Bounds follow the Phase 4 money catalogue. JSON numbers are invalid for money, including values nested in JSONB. The current product currency remains AED and is not inferred from a request. |
| Null | `null` | A response includes a declared nullable property with `null`; it does not omit it. In a request, omission means no value was supplied. Explicit `null` clears a value only when that operation marks the field nullable and clearable. |
| Enum | string | The API schema lists exact, case-sensitive values. New API enum values use lowercase `snake_case`. A route maps older database spellings explicitly and never exposes a database check as the API contract. Unknown and empty values are invalid. |

Boolean values are JSON booleans. Integers are JSON numbers and must fall within the bound in the
operation schema. Decimal and money strings never pass through a binary floating-point conversion.

## Requests and success responses

Each route defines a request model, a response model, its authorization class, allowed headers, and
safe error codes. Read models and write models are separate. Server-owned identifiers, scope,
actors, approval state, audit fields, and timestamps are absent from write models unless the
governing workflow expressly accepts them.

`Content-Type: application/json` is required when a request has a JSON body. `Accept` may be absent,
`*/*`, or include `application/json`. Other response media types return `406 not_acceptable`.
Malformed JSON returns `400 invalid_request`. A well-formed value that fails its schema returns
`422 validation_failed`.

### Statuses and envelopes

| Operation result | Status | Body and headers |
|---|---:|---|
| Fetch one resource | 200 | `{"data": { ... }}` |
| Fetch a collection | 200 | `{"data": [ ... ], "page": { ... }}`; an empty authorized collection is 200 with an empty array. |
| Create a resource | 201 | `{"data": { ... }}` and a relative or same-origin `Location` header for the new resource. |
| Update a resource or run a synchronous command | 200 | `{"data": { ... }}` containing the authoritative post-change representation. |
| Delete with no representation | 204 | No body and no `Content-Type` header. |
| Accept asynchronous work | 202 | Allowed only after a later phase defines a job resource; the response then uses `{"data": { ... }}` and `Location`. |

Protected success responses and every error use `Cache-Control: no-store`. A public operation may
document another cache rule. An operation does not return a bare object or array.

Bulk mutations are atomic. A request containing a missing or inaccessible member returns
`404 resource_not_found` and changes nothing. It never reports which member failed.

## Collections

### Pagination

Collection requests accept `limit` and `cursor`:

- `limit` is an integer from 1 through 100. It defaults to 50.
- `cursor` is an opaque, server-authenticated, unpadded base64url string of at most 512 characters.
- A cursor records the operation ID, verified `app_user_id`, company and branch scope, effective
  filters, effective sort, last position, and an expiry 15 minutes after issue. It contains no token,
  secret, name, email, private object key, or other display data.
- Changing scope, filters, or sort while reusing a cursor returns `400 invalid_cursor`. A malformed,
  expired, or tampered cursor returns the same error.
- A cursor is bound to the principal that requested it. Another principal receives
  `400 invalid_cursor`, even in the same company and branch. The query still runs under the current
  authorization of the bound principal. A cursor never grants access.
- The sort gains the resource UUID in ascending order as its final tie-breaker unless the UUID is
  already present.

The response page object always has this shape:

```json
{
  "limit": 50,
  "nextCursor": "opaque-value-or-null",
  "hasMore": true
}
```

`nextCursor` is `null` and `hasMore` is `false` on the last page. Counts are not returned by default.
An endpoint that needs a count must define a separately authorized count field and query.

### Filtering and sorting

Filters are named camelCase query parameters. Each operation lists every allowed name, value type,
comparison, and bound in OpenAPI. Equality is the only implicit comparison. Range endpoints use
explicit names such as `createdFrom` and `createdTo`. Free-text search exists only when an operation
defines a bounded `search` parameter.

Each filter may appear once. Different filters combine with AND. An endpoint that needs several
values defines one comma-free repeated-value alternative in its own schema; no shared route accepts
an arbitrary operator, column name, JSON path, SQL fragment, or comma-separated expression.

`sort` is a comma-separated list of at most three unique field names. A leading `-` means descending;
no prefix means ascending. Each operation publishes an allowlist and a default. Unknown fields,
duplicates, empty segments, and more than three fields return `422 validation_failed`. Null ordering
is fixed per allowed field in the operation schema.

Unknown or repeated query parameters return `422 validation_failed`. Query names are case-sensitive.
The API does not ignore unsupported filters or sorts.

## Error contract

Every error under `/api/v1`, including framework routing, validation, and unexpected failures, uses
`application/json` and this body:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "Request validation failed",
    "correlationId": "00f202d5-2ef0-4d6f-9553-830e5dcfb833",
    "details": [
      {
        "path": "body.amount",
        "code": "invalid_format",
        "message": "Value has an invalid format"
      }
    ]
  }
}
```

`code` and `message` come from the registry. They are never raw exception text. `details` is always
an array and is empty except for `validation_failed`. Validation returns at most 20 details. It sorts
them by path, then detail code, then message.

A detail path starts with `body`, `path`, `query`, or `header`. External camelCase names follow as
dot-separated segments. A zero-based array index uses brackets, as in `body.items[0].amount`. A root
error uses the source name alone. Internal model names and raw validator locations never appear.

| Detail code | Exact message |
|---|---|
| `required` | `Field is required` |
| `invalid_type` | `Value has an invalid type` |
| `invalid_format` | `Value has an invalid format` |
| `out_of_range` | `Value is outside the allowed range` |
| `unknown_field` | `Field is not allowed` |
| `duplicate_parameter` | `Parameter must appear once` |

The mapper reduces every framework or Pydantic validation error to one of these six rows. It never
echoes a supplied value, regular expression, internal enum, Python type, or validator message.

Errors never expose SQL, constraint or table names, Python types or traces, Keycloak or JWT internals,
tokens, secrets, request bodies, object ownership, authorization context, private object keys, or the
existence of an inaccessible tenant object. HTML error pages are not allowed under `/api/v1`.

The common error body and correlation header also apply to `/health`. Its successful 200 body remains
`{"status":"ok","database":"ok"}`. A failed probe returns `503 service_unavailable` instead of its
old database-status body. No other route outside `/api/v1` adopts this contract.

### Error precedence

The first failing stage wins. Later stages do not run, except for bounded rollback and cleanup.

| Order | Stage | Failure result |
|---:|---|---|
| 1 | Generate correlation ID and bind safe request logging. | This stage has no request-validation outcome. Failure is process-fatal rather than a response without a valid ID. |
| 2 | Validate an optional `Origin` and handle preflight. | A disallowed origin returns `403 origin_not_allowed` without an allow-origin header. An allowed preflight checks the fixed method and header lists and ends here. Invalid preflight syntax returns `400 invalid_request`. |
| 3 | Match route and method for a non-preflight request. | `404 resource_not_found` or `405 method_not_allowed`. |
| 4 | Apply 60 per minute to a public route, 30 per minute to the authentication-check route, or 600 per minute to another protected route before token verification, keyed by trusted IP. | `429 rate_limit_exceeded`. |
| 5 | Check declared and streamed size, content encoding, request media type, and `Accept`. | 413, 415, or 406 from the registry. The server does not parse the body. |
| 6 | Validate the bearer token for a protected operation. A failure increments the invalid-token trusted-IP bucket. | Of requests that pass the stricter stage 4 route bucket, the first 60 token failures in the minute return `401 invalid_access_token`. The 61st and later return `429 rate_limit_exceeded`. A valid token does not enter this 60-failure bucket. |
| 7 | Resolve the application principal. | `403 application_account_unavailable` or `503 application_account_lookup_unavailable`. |
| 8 | Apply authenticated principal and company rate limits. | `429 rate_limit_exceeded`. |
| 9 | Check non-idempotency shared headers, including admin branch presence and canonical syntax. | `400 branch_required`, `422 invalid_branch`, or `400 invalid_request`. |
| 10 | Parse JSON, then validate path, query, and body schemas. | `400 invalid_request` or `422 validation_failed`. |
| 11 | Enter the one authorized transaction and recheck current principal, branch, route authorization, and object visibility. | The safe 403, 404, or 503 assigned by the operation and Phase 5. |
| 12 | Validate `Idempotency-Key` presence and canonical syntax, then acquire its lock and compare or insert its record when the operation requires it. | The registered 400 or 409 idempotency error. |
| 13 | Execute the service and commit. | The operation's safe error, `409` workflow code, `504 request_timeout`, `503 service_unavailable`, or `500 internal_error`. |

Public operations skip stages 6 through 9 and enter a transaction only if their approved design needs
one. A body fault never takes precedence over failed authentication, account resolution, or required
branch scope. Size and media checks happen earlier because the server must bound untrusted input before
it performs identity work. An unexpected failure at any stage maps to `500 internal_error` after safe
cleanup.

### Error-code registry

| Code | Status | Safe message | Use and required headers |
|---|---:|---|---|
| `invalid_request` | 400 | `Invalid request` | Malformed JSON, duplicate JSON names, invalid shared header syntax, or invalid query encoding. |
| `branch_required` | 400 | `Branch selection required` | An administrator omitted `X-Workloop-Branch-ID`. |
| `invalid_cursor` | 400 | `Invalid pagination cursor` | A cursor is malformed, expired, tampered, or does not match the request scope and query. |
| `idempotency_key_required` | 400 | `Idempotency key required` | A protected mutation omitted `Idempotency-Key`. |
| `invalid_idempotency_key` | 400 | `Invalid idempotency key` | The header is duplicated or is not a canonical UUIDv4. |
| `invalid_access_token` | 401 | `Authentication required` | Bearer token is missing or invalid. Include `WWW-Authenticate: Bearer`. |
| `application_account_unavailable` | 403 | `Application account unavailable` | The database account or profile cannot authorize application access. |
| `operation_not_permitted` | 403 | `Operation not permitted` | A visible object exists but the action, field, state transition, or separation rule denies the caller. |
| `origin_not_allowed` | 403 | `Origin not allowed` | A request supplied an `Origin` outside the exact CORS allowlist. Return no CORS allowance. |
| `resource_not_found` | 404 | `Resource not found` | A route resource is absent or well-formed but inaccessible. The same response covers both. |
| `method_not_allowed` | 405 | `Method not allowed` | The path exists but the method does not. Include the framework-generated `Allow` header. |
| `not_acceptable` | 406 | `Requested response type is not available` | `Accept` excludes `application/json`. |
| `state_conflict` | 409 | `Resource state changed` | A general optimistic version check failed outside a named business workflow. |
| `idempotency_conflict` | 409 | `Idempotency key already used` | The key has a different request fingerprint. |
| `idempotency_in_progress` | 409 | `Request with this idempotency key is in progress` | An identical request is still running. Include `Retry-After: 1`. |
| `request_too_large` | 413 | `Request is too large` | Encoded or streamed body exceeds its operation limit. |
| `unsupported_media_type` | 415 | `Unsupported request content type` | Content type or content encoding is not accepted. |
| `validation_failed` | 422 | `Request validation failed` | A well-formed body, path, or query value fails the published schema. |
| `invalid_branch` | 422 | `Invalid branch selection` | Branch header is duplicated or is not a canonical UUID. A valid inaccessible UUID uses 404. |
| `rate_limit_exceeded` | 429 | `Too many requests` | A limit is exhausted. Include integer-seconds `Retry-After`. |
| `internal_error` | 500 | `Unexpected server error` | Unhandled application failure. Log only the safe event and correlation ID at the HTTP boundary. |
| `application_account_lookup_unavailable` | 503 | `Service temporarily unavailable` | Account or authorization-context lookup times out or fails. |
| `service_unavailable` | 503 | `Service temporarily unavailable` | A required database or approved dependency is unavailable. |
| `request_timeout` | 504 | `Request timed out` | The server deadline expires before a transaction commits. |

A later workflow must add its specific safe 409 code to this registry before the route ships, as
required by Phase 5. It may not use `state_conflict` to hide an unspecified workflow contract or use
a status or message that reveals object ownership or another tenant's state.
Database uniqueness, foreign-key, check, serialization, and RLS failures map through an explicit
operation rule. Raw database error names never decide the public body.

## Correlation IDs

FastAPI generates a fresh UUIDv4 before route, CORS, authentication, or body processing. The value is
lowercase canonical text. The same value appears in `X-Correlation-ID`, the error body when there is
one, and safe structured logs for that request.

The server ignores `X-Correlation-ID`, `X-Request-ID`, and tracing headers supplied by an untrusted
client when choosing the public correlation ID. A trusted cloud proxy trace may be stored in a
separate internal log field after Part 6G names the proxy and header. It never replaces the public
value. The response header is present on success, error, preflight, timeout, and rate-limit responses.

## Transaction ownership

One protected request calls one service operation. The service is the logical transaction owner and
enters the existing `AuthorizationTransactionFactory` context once. The factory remains the only
component that acquires the connection, begins the transaction, sets and revalidates transaction-local
Phase 5 context, commits after a successful service return, rolls back on every exception or
cancellation, and returns a clean connection to the pool.

For an administrator, the service passes the parsed branch UUID into that one transaction. The
factory verifies the branch while it establishes context. There is no preliminary branch transaction
and no gap between branch verification and protected work.

| Layer | Allowed | Forbidden |
|---|---|---|
| Handler and dependencies | Parse HTTP input, validate the access token and principal, parse an admin branch UUID without treating it as authorized, call one service, and map the result. | Begin, commit, roll back, verify business scope in a preliminary transaction, run unscoped business SQL, or call several independently committing services. |
| Service | Enter one authorized transaction, coordinate repositories and protected functions, set the request deadline, and return only after the unit of work is complete. | Open a second business connection, commit early, catch cancellation without re-raising it, or perform a non-transactional duplicate write. |
| Repository | Execute scoped statements on the supplied connection and return typed domain data. It may flush through that connection when needed. | Acquire a connection, begin, commit, roll back, change transaction context, translate raw database errors into public text, or bypass RLS scope. |
| Protected database function | Lock, recheck, mutate, and audit the approved workflow within the caller's transaction. | Commit, start an autonomous transaction, trust caller-supplied scope or actors, or weaken the Phase 5 direct-login and context checks. |

Read-only protected operations also use an authorized transaction because RLS consumes
transaction-local context. Public operations that touch no protected data open no transaction.
External side effects do not occur inside a database transaction. Storage uses the approved Phase 5
outbox. Any later provider integration needs an equivalent durable handoff before it can commit a
business change.

## Idempotency

Phase 6A defines the future contract but adds no mutation or persistence table.

### Header and scope

- An operation marked financial or approval requires exactly one `Idempotency-Key` header.
- The value is a client-generated, lowercase canonical UUIDv4. It has no whitespace, prefix, or
  business identifier. The frontend creates a new key for each user intent.
- A key is unique for the verified `app_user_id` across operations. Its stored scope also contains the
  company, verified branch or null tenant scope, explicit OpenAPI operation ID, HTTP method, and
  normalized route parameters. Reusing the key with any different stored scope is a conflict.
- Authorization, correlation, transport, and retry headers never enter the scope or fingerprint.

### Canonical fingerprint

The server builds a typed internal value tree after strict validation. Its root contains fingerprint
version `wlp-idem-fp-v1`, operation ID, method, normalized route parameters, effective query
parameters, and body. Every declared value that affects the command appears. An omitted field with a
schema default uses that normalized default. An omitted field without a default uses the encoded
absent value and differs from JSON null.

The tree uses these arrays so absence cannot collide with caller JSON:

- absent value: `["absent"]`
- null: `["null"]`
- boolean: `["boolean",true]` or `["boolean",false]`
- integer: `["integer","<canonical-base-10>"]`
- string or any string-backed API scalar: `["string","<canonical-value>"]`
- array: `["array",[<encoded-items-in-order>]]`
- object: `["object",[["<member-name>",<encoded-value>],...]]`

Object member pairs sort by member name in Unicode code-point order. UUIDs, dates, times, instants,
decimals, money, and enums use this document's canonical strings. Other strings use Unicode NFC for
both the command and fingerprint after any operation-specific validation; no implicit trimming or
case change occurs. Arrays keep their order.

The server serializes the typed tree with RFC 8785 JSON Canonicalization Scheme and hashes the exact
UTF-8 bytes. RFC 8785 fixes member ordering, string escaping, and non-ASCII encoding. The fingerprint
is the lowercase hexadecimal SHA-256 digest of those bytes. Floating-point values cannot enter the
tree.

The record stores the fingerprint version and digest. A deployment keeps every fingerprint version
used by a retained record available for comparison. It computes a retry with the version stored on
that record. Changing canonicalization requires a new version and cannot remove the old implementation
until its last record expires. OpenAPI default changes remain breaking under `6A-D14`.

### Atomic behavior

The idempotency claim, protected mutation, audit event, and completed response record commit in one
database transaction. A protected database function that already accepts an idempotency key, such as
`record_advance_repayment`, receives the same UUID.

Before reading or inserting a record, the authorized transaction calls
`pg_try_advisory_xact_lock` with a signed 64-bit key made from the first eight bytes, in network byte
order, of SHA-256 over `wlp-idem-lock-v1`, verified `app_user_id`, and the idempotency UUID. Fields use
lowercase canonical text separated by a zero byte. Failure to acquire returns
`409 idempotency_in_progress` without waiting. A rare advisory-key collision may delay an unrelated
request with that same response, but it cannot execute or expose the other request.

After acquiring the lock, the service reads by verified `app_user_id` and idempotency UUID. An absent
record is inserted inside the transaction before mutation. A committed record is visible and compared.
The advisory lock releases at transaction end. This gives the in-progress response without exposing
an uncommitted row or opening a second transaction.

| Condition | Result |
|---|---|
| First valid request | Reserve the key in the authorized transaction, run the mutation once, and store the success status, response body, and safe response headers before commit. |
| Same key, scope, and fingerprint after commit | Recheck the current principal, route authorization, and safe visibility of the stored resource. If they still pass, return the stored status and body without rerunning mutation code, generate a fresh correlation ID, and add `Idempotency-Replayed: true`. Otherwise return the normal safe 403 or 404 and do not reveal that a record exists. |
| Same key and scope with another fingerprint | Return `409 idempotency_conflict`; reveal no original payload or result. |
| Same key and fingerprint while the first transaction is open | Return `409 idempotency_in_progress` with `Retry-After: 1`. |
| Validation, authentication, or authorization fails before a claim | Do not store an idempotency record. |
| Transaction rolls back, is cancelled, or reaches its deadline | The claim rolls back with it. A retry may execute as the first request. |
| Response delivery fails after commit | A retry returns the stored committed response. |

Only committed 2xx results are replayed. The record stores the status, JSON body, and `Location` header
when present. No other response header is stored. `Content-Type`, CORS, date, rate-limit,
authentication, correlation, and `Idempotency-Replayed` headers are generated for the replay.

Completed records remain for at least seven days. Callers must not retry an intent after seven days.
A business workflow must keep any permanent uniqueness rule required to prevent a financial duplicate
after retention; the HTTP key is not a substitute for that rule. Records contain no bearer token or
raw authorization context, and cleanup is tenant-safe.

### Client retry and recovery

The migration frontend keeps unresolved idempotency UUIDs, creation times, and an opaque recovery
namespace in browser `localStorage` for at most seven days. It stores no token, operation name,
route, object identifier, payload, fingerprint, response, user claim, or business value with them. A
key and namespace are random-looking identifiers and grant no access.

The recovery namespace has the form `rn1.<key-id>.<digest>`. `key-id` is an eight-character lowercase
hexadecimal identifier generated from four random bytes with the key and is not derived from the
secret. `digest` is unpadded base64url for the first 16 bytes of HMAC-SHA-256 over that key and the
UTF-8 bytes of `wlp-idem-recovery-v1`, a zero byte, and the canonical `app_user_id`. The dedicated
key contains at least 32 random bytes, remains on the server, never uses a `VITE_` setting, and is not
reused for tokens, cursors, or another purpose.

The protected `GET /api/v1/idempotency-recovery-namespaces` operation returns
`{"data":{"current":"...","accepted":["..."]}}`. `accepted` contains the current namespace and,
during rotation, each prior namespace whose seven-day overlap has not ended. The server keeps a prior
key active for at least seven days after the new key becomes primary. The frontend checks only stored
keys bearing an accepted namespace, writes new entries under `current`, and leaves other namespaces
untouched until their seven-day expiry.

The future protected `GET /api/v1/idempotency-status` operation requires the key in the
`Idempotency-Key` header, uses the current principal, and takes the same nonblocking advisory lock.
It returns `{"data":{"status":"in_progress"}}` when the lock is held,
`{"data":{"status":"completed"}}` when a committed record exists for that `app_user_id`, and
`{"data":{"status":"not_found"}}` after it acquires the lock and finds no record. It never puts the
key in a URL or returns the stored response or another principal's status. Rate limits apply. The
status operation and record are implemented with the first idempotent business mutation, not in
Phase 6A.

| Outcome observed by the client | Key behavior |
|---|---|
| 2xx response | Treat the intent as complete and remove the key after refreshing the authoritative resource. |
| 400, 405, 406, workflow-specific 409, 413, 415, or 422 | The request did not commit. Correcting it is a new user intent with a new key. |
| 403 or 404 after submitting a key | Check status before removing the key. A replay can return a safe 403 or 404 after the earlier request committed but current access changed. Never create a replacement key automatically. |
| `409 idempotency_conflict` | Stop automatic retries. Refresh current state and require a new user decision before using a new key. |
| `409 idempotency_in_progress` or 429 | Keep the key and retry status after `Retry-After`. Do not create a new key. |
| 401 | Keep the key, restore authentication, check status, then retry the same intent only when status is `not_found`. |
| 500, 503, 504, network failure, browser timeout, or cancellation after send | Treat the result as ambiguous. Keep the key and check status. Do not create a new key automatically. |
| Page reload or browser restart with an unresolved stored key | Authenticate, check status, refresh current business state, and remove completed keys. A `not_found` result permits a new submission only after the user confirms the still-current intent. |

The browser does not remove a stored key merely because status is `not_found`. It removes that key
only when the current in-memory intent owns it, an accepted recovery namespace receives `completed`,
or seven days pass. The keyed namespace separates users of a shared browser without persisting an
account identifier.

The API's duplicate-execution guarantee applies when the caller keeps and reuses the key during the
retention window. The recovery operation prevents a lost browser response from forcing a blind new
key. Permanent business uniqueness remains mandatory where repeating an intent after the seven-day
window could create a second financial effect.

## CORS

The local allowlist is exactly `http://127.0.0.1:5174`. It does not include `localhost`, the legacy
frontend at port 5173, wildcard hosts or ports, `null`, `file:`, the API origin, or a regex.

No cloud browser origin is approved in Phase 6A, so the cloud allowlist is empty. Part 6G may add one
exact owner-approved HTTPS frontend origin after deployment assigns it. That addition fills a
deployment value under this rule; it does not permit a wildcard or authorize another phase.

| Setting | Value |
|---|---|
| Credentials | `false`; Workloop cookies are not API credentials. |
| Methods | `GET`, `POST`, `PATCH`, `DELETE`, `OPTIONS`. `PUT` is not allowed until a route defines full replacement semantics. |
| Request headers | `Accept`, `Authorization`, `Content-Type`, `Idempotency-Key`, `X-Workloop-Branch-ID`. |
| Exposed response headers | `X-Correlation-ID`, `Idempotency-Replayed`, `Location`, `Retry-After`. |
| Preflight cache | 600 seconds. |

The middleware returns no authenticated data on preflight. A supplied disallowed origin returns
`403 origin_not_allowed` with no CORS allowance, even when the operation is public. A request with no
`Origin` is allowed to proceed. Authorization continues to run on the API; CORS is not an
authorization control.

## Limits, deadlines, and cancellation

### Request limits

| Request class | Maximum |
|---|---:|
| JSON or other ordinary request body | 1,048,576 bytes |
| One future uploaded file | 10,485,760 bytes |
| Entire future upload request, including multipart framing and metadata | 12,582,912 bytes |
| Upload files per request | 1 |
| Upload metadata JSON | 65,536 bytes |

The server rejects an oversized declared `Content-Length` before reading the body and also counts
streamed bytes so a missing or false length cannot bypass the limit. It does not buffer an oversized
body. `Content-Encoding` must be absent or `identity`; compressed request bodies return
`415 unsupported_media_type`. Each future upload route also publishes a content-type allowlist and
checks file signatures. Phase 6A approves no upload route or file type.

### Deadlines

| Work | Server deadline | Browser deadline |
|---|---:|---:|
| Ordinary API request, including authorization and database work | 15 seconds | 20 seconds |
| Health database probe | 5 seconds | 10 seconds when called by a client |
| Future API-proxied upload | 60 seconds | 70 seconds |

Existing lower OIDC, account lookup, authorization setup, and database probe timeouts remain bounded
inside the server deadline. A service cannot raise the deadline. Work that cannot finish within it
must use a later approved job resource rather than keeping the request open.

Browser navigation, component disposal, or an explicit cancel aborts the request. Server timeout or
disconnect cancellation rolls back the transaction and releases the connection. Code may shield only
the bounded cleanup needed to roll back. It then re-raises cancellation. A response is successful only
after commit.

## Rate-limit boundary

No endpoint may receive public traffic until the deployment enforces these fixed-window defaults.
The minute boundary uses a monotonic server clock. Successful and rejected requests both count after
the request can be assigned to a bucket.

| Class | Limit | Key |
|---|---:|---|
| Anonymous public endpoints, including health | 60 requests per minute | Trusted client IP |
| Protected-route attempts before token verification, except authentication check | 600 requests per minute | Trusted client IP |
| Failed bearer-token checks | 60 failures per minute | Trusted client IP |
| Authentication check | 30 requests per minute | Trusted client IP, plus verified principal when available |
| Authenticated reads | 300 requests per minute | Verified `app_user_id`; also 3,000 per company |
| Authenticated writes | 60 requests per minute | Verified `app_user_id`; also 600 per company |
| Financial or approval mutations | 20 requests per minute | Verified `app_user_id`; also 200 per company |

The most restrictive matching bucket wins. A valid protected request counts against the
pre-authentication IP bucket and its principal and company buckets. A failed token check counts
against a separate 60-per-minute invalid-token IP bucket at stage 6; it does not spend the public
endpoint bucket. Only the direct peer address is trusted locally. Part 6G must name the exact proxy
chain before FastAPI can trust its forwarded client-IP header. Arbitrary forwarding headers never
select a bucket.

`429 rate_limit_exceeded` includes integer-seconds `Retry-After` and the correlation ID. The response
does not reveal company size, another user's traffic, or internal bucket state. If shared limiter state
is unavailable, financial, approval, and other authenticated writes fail with
`503 service_unavailable`; health and authenticated reads keep their local per-instance safety limit
and emit a safe operational alert. Part 6G must prove the deployed topology cannot multiply the
stated limits unnoticed.

## OpenAPI and compatibility

FastAPI's generated document at `/openapi.json` is the source generated from reviewed code. Local and
test environments may expose `/docs` and `/openapi.json`. A public environment disables interactive
docs and does not expose the schema unless a later deployment decision approves it.

Every operation must have:

- an explicit, unique, stable `snake_case` operation ID;
- one authorization class and its required headers;
- strict request, success, and error schemas with examples that use synthetic data;
- documented success statuses, list rules, filter and sort allowlists, limits, idempotency behavior,
  `X-Correlation-ID`, and any `Location`, `Retry-After`, or `WWW-Authenticate` header; and
- no undocumented 2xx response or framework-default error body.

Phase 6E captures and reviews the first generated schema. Later phases compare the generated schema
with the accepted baseline. Generated clients must treat undocumented response properties as absent,
but the server still uses explicit response schemas.

The following changes are breaking after a consumer ships: removing or renaming an operation or
field; changing a type, format, meaning, nullability, required state, default, status, envelope,
header, filter, sort, or error code; narrowing an accepted input; adding an enum value unless every
consumer of that enum has a reviewed unknown-value path; or changing pagination and idempotency
semantics. A breaking change requires `/api/v2` and a cutover plan. An unreleased endpoint in the
current migration build may change within `/api/v1` only when its frontend changes in the same commit
and the OpenAPI review records that no shipped consumer exists.

Additive optional response fields and new operations are compatible. New optional request fields are
compatible only when omission preserves the old behavior. Deprecation marks an operation or field in
OpenAPI and keeps it for at least one shipped frontend release before removal in a new major API
version.

## Review and approval gate

The independent Phase 6A review inspected error safety and every idempotency rule against the Phase 3
and Phase 5 boundaries. All twelve findings are closed in
[`PART_6A_INDEPENDENT_REVIEW.md`](PART_6A_INDEPENDENT_REVIEW.md). The project owner approved
`6A-D1` through `6A-D14` without amendment on 2026-09-07. That approval authorized only the
documentation closure steps for Phase 6A. It does not authorize Parts 6B through 6G.

Rollback is one documentation revert. No runtime, schema, database, container, cloud, or preserved
volume state changes in Phase 6A.
