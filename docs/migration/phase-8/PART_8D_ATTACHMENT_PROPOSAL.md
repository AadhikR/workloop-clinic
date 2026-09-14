# Phase 8D attachment proposal

Status: approved by the project owner on 2026-09-14; implementation is in progress.

This proposal defines the minimum Phase 11-owned storage prerequisite and the Phase 8D leave
attachment amendment. The project owner approved Decision `8A-ATT-1` and decisions `8D-STO-D1`
through `8D-AUD-D1` exactly as written.

## Verified preflight

- Branch `migration/fastapi-keycloak` is clean and synchronized with its remote at
  `9f26866eb118a3d4014fb9c0b85b893ef76447e0`.
- Alembic has one head, `8f6b2d1a4c70`.
- No Docker container is running. Ports 25432, 28000, 28080, 29000, and 19000 are free.
- The preserved `workloop-clinic_postgres_data` volume exists and was not attached, upgraded,
  seeded, recreated, or deleted.
- The attachment cutover remains in `preparation`. Legacy Supabase is its sole read and write
  authority.
- `ObjectStorage` has `put_object`, `get_object`, `head_object`, and `delete_object`. It has no
  signing method, conditional create contract, local persistent implementation, operation outbox,
  or reconciler.
- `leave_requests.attachment_url` is a required text field with an empty-string default. It cannot
  hold a private object key, digest, byte size, media type, normalized filename, upload state, or
  cleanup evidence.
- Revision IDs `4d8a7c2e9f31` and `a83d5e7c1b29` are unused.
- The latest recorded GitHub Migration foundation run is
  `https://github.com/AadhikR/workloop-clinic/actions/runs/34774914175`, which the Phase 8D handoff
  records as successful.

## Decision 8A-ATT-1

Approve the minimum Phase 11-owned prerequisite before Phase 8D. The prerequisite implements the
already approved `storage_operations`, `O1`, `S1`, reconciler login, lease, retry, terminal failure,
and cleanup rules from decisions `5A-D15`, `5A-D19`, and `5A-D20`. It also adds the signing contract
and local synthetic provider required by Phase 8D.

This approval does not move employee documents, receipts, certifications, training files, contracts,
or general document storage into Phase 8. It authorizes no cloud object store or real file.

## Decision 8D-STO-D1: minimum storage prerequisite

### Interface

Keep the existing four object operations and add these exact provider-neutral types and behaviors:

```text
StorageConflictError
SignedDownload(url: str, expires_at: datetime)
put_object(..., if_absent: bool = true)
create_download_url(
  key: str,
  expires_in_seconds: int,
  download_name: str,
  content_type: str,
) -> SignedDownload
```

`put_object` must fail with `StorageConflictError` when `if_absent` is true and the key exists. The
adapter accepts only a server-generated key. Signing accepts 1 through 300 seconds and never returns
the key separately. `download_name` affects only `Content-Disposition`; it does not select an
object. The provider response uses `Cache-Control: private, no-store` and
`X-Content-Type-Options: nosniff`.

Object metadata is exactly byte size, canonical content type, and lowercase SHA-256. No caller can
add provider metadata. Provider calls have a 45-second deadline, below the 60-second upload deadline
and 15-minute operation lease.

The Spaces adapter implements conditional create and signed GET generation for contract tests only.
Phase 8D does not create or contact a Space.

### Local synthetic provider

Add a filesystem-backed provider for local and test use. It stores each body and its three metadata
values under a configured absolute directory mounted from a disposable Phase 8D volume. It hashes
the private object key before deriving a filesystem name, writes through a same-directory temporary
file, and replaces no existing object. `head`, `get`, and `delete` verify that the metadata file and
body agree. A missing or malformed pair fails closed.

The local provider encrypts the private key, expiry, normalized download name, and canonical media
type in an AES-256-GCM token using a dedicated 32-byte signing secret. Its signed URL uses
`GET /_synthetic-storage/v1/{token}`. The handler is enabled only with the local synthetic backend,
accepts no object key or filename parameter, rejects expired or altered tokens, and checks the
encrypted media type against stored metadata before sending the approved download name.
The URL grants only that download until its five-minute expiry. It cannot authorize an API call.
The same signing secret and disposable object volume are reused during the final restart proof.

### Storage operation revision

Reserve revision `4d8a7c2e9f31` as
`backend/alembic/versions/4d8a7c2e9f31_add_storage_operations_prerequisite.py`, with
`down_revision = "8f6b2d1a4c70"`.

Create `public.storage_operations` with the approved fields and these exact types:

| Column | Type | Null | Default |
| --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` |
| `company_id` | `uuid` | No | None |
| `branch_id` | `uuid` | No | None |
| `employee_id` | `uuid` | Yes | None |
| `created_by_app_user_id` | `uuid` | No | None |
| `entity_type` | `text` | No | None |
| `entity_id` | `uuid` | No | None |
| `operation` | `text` | No | None |
| `object_key` | `text` | No | None |
| `status` | `text` | No | `'pending'` |
| `attempt_count` | `integer` | No | `0` |
| `last_error_code` | `text` | No | `''` |
| `next_attempt_at` | `timestamptz` | Yes | None |
| `claimed_at` | `timestamptz` | Yes | None |
| `lease_expires_at` | `timestamptz` | Yes | None |
| `completed_at` | `timestamptz` | Yes | None |
| `created_at` | `timestamptz` | No | `statement_timestamp()` |
| `updated_at` | `timestamptz` | No | `statement_timestamp()` |

The table has the approved restrictive foreign keys to company, branch, optional employee, and
creator profile. Each uses the existing scoped unique key and `ON DELETE RESTRICT`. It has no generic
foreign key from `entity_type` and `entity_id` to a business table.

Named checks enforce all of the following:

- `entity_type` is 1 through 64 lowercase snake-case characters;
- `operation` is `upload` or `delete`;
- `object_key` is 1 through 1,024 bytes and contains no control character, backslash, leading slash,
  empty segment, `.` segment, or `..` segment;
- `status` is `pending`, `claimed`, `succeeded`, `failed`, or `reconciled`;
- `attempt_count` is from zero through eight;
- `last_error_code` is empty or 1 through 64 lowercase snake-case characters;
- a pending row has count zero, no error, and no claim, lease, retry, or completion timestamp;
- a claimed row has count one through eight, claim and future lease timestamps, no retry or
  completion timestamp, and an empty error code;
- a failed row has count one through eight, a nonempty error code, no claim, lease, or completion
  timestamp, and a retry timestamp only while the count is below eight;
- a succeeded or reconciled row has count one through eight, a completion timestamp, no claim,
  lease, or retry timestamp, and an empty error code; and
- every stored timestamp is on or after `created_at`, and `updated_at` never precedes `created_at`.

Create one claim index on `(status, next_attempt_at, lease_expires_at, created_at, id)` and one
partial purge index on `(completed_at, id)` for `succeeded` and `reconciled` rows. Do not index the
object key.

### O1 and S1

Implement `O1` and `S1` without widening the Phase 5 contract.

`workloop_runtime` receives only the approved insert, select, and update columns. `O1` requires the
direct runtime login, a valid human context, creator equality with the current application user, and
matching company and branch. It allows the initial pending insert, the expected pending row's
pre-call move to claimed count one with a 15-minute lease, and that claimed row's immediate success
or scheduled failure transition. No business response returns an operation row.

Create `workloop_storage_reconciler` through the existing local and cloud database bootstrap code as
`LOGIN NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`. Its credential is
absent from the web container. It receives schema usage, the fixed context readers needed by `S1`,
select on the listed operation columns, update on the approved state columns, and guarded delete. It
has no grant on a business table or `audit_events`, and it is not a member of another role.

Under actor kind `scheduled_job` and actor key `storage_reconciliation`, a null-scope transaction may
discover these rows only:

- pending, due failed, or expired claimed rows with `attempt_count < 8`;
- expired claimed rows at count eight; and
- succeeded or reconciled rows whose completion is at least 90 days old.

The first class is claimed with `FOR UPDATE SKIP LOCKED`. Every claim increments the count and writes
a new 15-minute lease before a provider call. The worker copies the row's company and branch to a new
transaction before any later state update or purge. It terminalizes an expired count-eight lease
without another provider call.

Failures one through seven retry after 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours, 24 hours,
and 72 hours. Failure eight remains failed with no next attempt. The worker writes one structured
`storage_reconciliation_terminal` error log containing only the operation UUID and allowlisted error
code. Manual requeue remains unsupported.

For `delete`, provider not-found counts as success. For `upload`, the worker never recreates bytes.
It checks the object. If the object exists without committed domain metadata, it deletes the object
and marks the operation reconciled. If the object does not exist, it marks the operation reconciled.
It purges only succeeded or reconciled rows after 90 days. Terminal failures remain.

The worker infers the absence of committed domain metadata from the upload operation's non-success
state. Domain metadata and upload success commit in one transaction. The worker does not query a
business table to make that inference.

The prerequisite is one reviewable unit. Its model, migration, repository, worker, storage adapters,
configuration, bootstrap changes, contract tests, database verifier, and local synthetic provider
must land together before Phase 8D consumes them.

## Decision 8D-ATT-D1: leave attachment metadata

Reserve revision `a83d5e7c1b29` as
`backend/alembic/versions/a83d5e7c1b29_add_leave_attachment_metadata.py`, with
`down_revision = "4d8a7c2e9f31"`.

Create `public.leave_attachments` with these columns:

| Column | Type | Null | Default |
| --- | --- | --- | --- |
| `id` | `uuid` | No | `gen_random_uuid()` |
| `company_id` | `uuid` | No | None |
| `branch_id` | `uuid` | No | None |
| `employee_id` | `uuid` | No | None |
| `leave_request_id` | `uuid` | Yes | None |
| `created_by_app_user_id` | `uuid` | No | None |
| `submission_token_digest` | `bytea` | No | None |
| `file_name` | `text` | Yes | None |
| `content_type` | `text` | Yes | None |
| `size_bytes` | `bigint` | Yes | None |
| `sha256` | `text` | Yes | None |
| `object_key` | `text` | Yes | None |
| `status` | `text` | No | `'pending'` |
| `expires_at` | `timestamptz` | Yes | None |
| `token_consumed_at` | `timestamptz` | Yes | None |
| `uploaded_at` | `timestamptz` | Yes | None |
| `attached_at` | `timestamptz` | Yes | None |
| `cleanup_requested_at` | `timestamptz` | Yes | None |
| `removed_at` | `timestamptz` | Yes | None |
| `created_at` | `timestamptz` | No | `statement_timestamp()` |
| `updated_at` | `timestamptz` | No | `statement_timestamp()` |

The scoped company, branch, employee, creator-profile, and optional leave-request foreign keys use
`ON DELETE RESTRICT`. A unique constraint on `leave_request_id` permits at most one attachment for a
request. The token digest is exactly 32 bytes and unique. The digest is never returned or logged.

The status set is `pending`, `uploading`, `staged`, `attached`, `cleanup_pending`, and `removed`.
Named checks pin these states:

- pending has only scope, creator, token digest, and an expiry 15 minutes after issue;
- uploading has a consumed token and no exposed file metadata;
- staged has complete file metadata, an object key, upload time, and an expiry 24 hours after upload;
- attached has complete file metadata, an object key, request ID, upload time, attachment time, and
  no expiry;
- cleanup pending retains complete metadata and has a cleanup-request time; and
- removed retains metadata and request linkage when one existed, has no signable object, and records
  its removal time.

`size_bytes` is 1 through 10,485,760. `sha256` is 64 lowercase hexadecimal characters. Media type is
one of the three values in `8D-FILE-D1`. The filename is 1 through 180 UTF-8 bytes. The object key
uses the prerequisite's key check. Complete metadata fields are all null or all present.

Keep `leave_requests.attachment_url` for legacy compatibility, but migration code must neither read
nor write it. Do not backfill a private key from an old URL. The new relation is the only migration
attachment representation. The existing leave-request projection loads the related row and returns
only `id`, `fileName`, `contentType`, `sizeBytes`, `sha256`, `uploadedAt`, and `expiresAt`.

Runtime RLS permits metadata reads to the owner, an administrator in the selected branch, and a
manager or active delegate only through a linked request currently visible in their leave queue.
Only the owner or selected-branch administrator may create an upload intent or move its approved
states. Managers and delegates have no insert, update, or delete path. Runtime receives no table
delete grant. The reconciler receives no grant on this table.

An opaque key has this form:

```text
leave-attachments/v1/{scope-digest}/{attachment-uuid-hex}
```

`scope-digest` is the first 22 unpadded base64url characters of HMAC-SHA-256 under a dedicated key
over the canonical company, branch, employee, and attachment UUIDs separated by zero bytes. The key
contains no name, email, filename, browser path, or request value. It never crosses the API boundary.

## Decision 8D-HTTP-D1: routes and one-use token

### Issue an upload intent

`POST /api/v1/leave/attachment-submissions` has operation ID
`create_leave_attachment_submission`. It accepts strict JSON with optional `requestId` and
`employeeId`.

- An active employee or manager acting for self omits `employeeId`. They may name only their own
  accessible request.
- An administrator supplies `X-Workloop-Branch-ID`. For a pre-request upload, `employeeId` is
  required and must identify an eligible employee in that branch. For an existing request,
  `requestId` is required and `employeeId` is absent.
- `requestId` and `employeeId` cannot both be present. Both may be absent only for self pre-request
  upload.
- Existing-request upload is allowed only while the request is `Pending` and has no attachment.

The response is 201 with a relative `Location`, `Cache-Control: no-store`, and:

```json
{
  "data": {
    "id": "8d000000-0000-4000-8000-000000000001",
    "submissionToken": "wlat1.8d000000-0000-4000-8000-000000000001.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "expiresAt": "2026-09-14T12:15:00.000Z"
  }
}
```

The secret is 32 random bytes encoded as 43 unpadded base64url characters. PostgreSQL stores only
SHA-256 over the exact ASCII token. The token is bound to its intent UUID, company, branch, employee,
creator application user, and optional request. It grants no scope by itself.

### Upload one file

`POST /api/v1/leave/attachment-submissions/{submission_id}/file` has operation ID
`upload_leave_attachment`. It accepts `multipart/form-data` with exactly one `file` part, one
`submissionToken` text part, and one `sha256` text part. Duplicate or unknown parts fail. The request
contains no employee, company, branch, request, path, key, media-type override, or timestamp field.

The authenticated principal and current database scope must match the intent. The service locks the
pending row, compares the token digest in constant time, checks its expiry, and consumes it before
the provider call. A replay, concurrent claim, expired token, wrong principal, or wrong scope returns
`409 attachment_submission_unavailable` without exposing which check failed. A failed or ambiguous
upload needs a new intent and token.

The upload coordinator follows the approved storage sequence:

1. Read and validate the bounded body without touching object storage.
2. In one authorized transaction, lock and consume the intent, insert the upload operation, and
   reserve attempt one with a 15-minute lease.
3. Put the object with conditional create, then head it and compare size, media type, and digest.
4. In a second authorized transaction, lock the same rows, write staged or attached metadata, mark
   the operation succeeded, and append the safe audit event.
5. On a provider or final-database failure, record the approved failed operation state. The
   reconciler removes only the object named by that operation. It never retries upload bytes.

The response is 201 with `Location: /api/v1/leave/attachments/{id}` and the strict attachment
projection. Upload is a 60-second server operation and the browser deadline is 70 seconds.

### Authorize a download

`POST /api/v1/leave/attachments/{attachment_id}/download` has operation ID
`create_leave_attachment_download`. It accepts no body and returns 200:

```json
{
  "data": {
    "url": "provider-signed-url",
    "expiresAt": "2026-09-14T12:05:00.000Z"
  }
}
```

The URL expires after five minutes. The service first loads the metadata within scope, then checks
the object head against stored size, media type, and digest before signing. An employee or manager
may sign their own request attachment. An administrator may sign within the selected branch. A
manager or active delegate may sign only while the linked request is in their current queue.
Inaccessible and missing identifiers share `404 resource_not_found`. A missing or mismatched object
requests the approved `missing_object` cleanup, writes a structured safe alert with the operation
UUID and error code, returns `503 service_unavailable`, and never returns a URL.

No route lists objects, copies, moves, replaces, or directly deletes an attachment. Failed submission
and cancellation call one internal cleanup command. That command changes retained metadata to
`cleanup_pending`, inserts and reserves a delete operation in the same transaction, calls the
provider, and records `removed` only after provider success or not-found. Staged uploads expire after
24 hours. Phase 8E must request the same cleanup when submission fails or a request is cancelled.

## Decision 8D-FILE-D1: accepted files

The allowlist is deliberately small:

| Canonical media type | Extension | Required byte rules |
| --- | --- | --- |
| `application/pdf` | `.pdf` | Starts with `%PDF-1.` or `%PDF-2.` and contains `%%EOF` after the final non-whitespace bytes within the last 1,024 bytes. |
| `image/png` | `.png` | Starts with the eight-byte PNG signature, has `IHDR` as the first chunk with length 13, and ends with a complete `IEND` chunk. |
| `image/jpeg` | `.jpg` | Starts with `FF D8 FF`, has a valid marker byte after the start marker, and ends with `FF D9`. `.jpeg` normalizes to `.jpg`. |

The declared multipart media type, normalized extension, and detected signature must name the same
row. Empty files, polyglot mismatches, malformed signatures, and trailing bytes after the required
terminal marker fail. Office files, archives, SVG, HTML, text, executables, and an absent or generic
media type are unsupported.

The file part is 1 through 10,485,760 bytes. The whole multipart request is at most 12,582,912 bytes.
All non-file parts together are at most 65,536 bytes. The server counts streamed bytes even when
`Content-Length` is absent, rejects an oversized declared length before reading, and accepts no
content encoding except absent or `identity`.

The server computes lowercase SHA-256 while reading. The required `sha256` form value must be exactly
64 lowercase hexadecimal characters and must match. After upload, the server compares that digest,
the byte count, and canonical media type with `head_object`. No client digest or media type becomes
authoritative.

Filename normalization uses Unicode NFC, rejects control characters, path separators, bidi-control
characters, and a leading or trailing dot. It trims outer whitespace, collapses internal whitespace
to one ASCII space, replaces characters outside Unicode letters, digits, space, `.`, `_`, and `-`
with `_`, collapses repeated underscores, and lowercases the approved extension. It truncates only
the stem at a code-point boundary so the final UTF-8 name is at most 180 bytes. An empty stem becomes
`attachment`. The normalized display name never enters the object key.

This synthetic-only phase does not claim malware safety. Real files remain blocked until the project
owner approves the Phase 11 malware-scanning and production-storage rules.

## Decision 8D-AUD-D1: protected audit amendment

The attachment revision wraps the current
`public.append_audit_event(text,text,uuid,text[],text,jsonb)` function. It renames the current public
function to `_append_audit_event_phase8d_prior`, revokes all runtime and public access to that
predecessor, and installs a public wrapper with the same signature, owner, security mode, volatility,
and pinned search path. Unrelated actions delegate unchanged.

Add only these actions:

| Action | Entity | Changed fields | Exact metadata and state proof |
| --- | --- | --- | --- |
| `leave_attachment_uploaded` | `leave_attachment`, attachment ID | `file_name`, `content_type`, `size_bytes`, `sha256`, `status` | One key, `storage_operation_id`. The operation is a succeeded upload for the same attachment and scope. The attachment is staged or attached and the current human actor created it. |
| `leave_attachment_cleanup_requested` | `leave_attachment`, attachment ID | `status` | Two keys, `storage_operation_id` and `trigger`. Trigger is `failed_submission`, `request_cancelled`, `staged_expired`, or `missing_object`. The operation is a delete for the same attachment and scope, and attachment status is cleanup pending. |

Metadata carries canonical UUID text only and never contains an object key, filename, URL, token,
digest, media type, employee identifier, or request payload. Reasons are the fixed strings `Leave
attachment uploaded` and `Leave attachment cleanup requested`. The wrapper validates current
database state before insert. Runtime keeps only execute access to the public function.

Downgrade drops the wrapper, restores `_append_audit_event_phase8d_prior` under the public name with
its exact owner and grants, then drops attachment policies and metadata. The predecessor definition,
ACL, behavior, and Phase 7G private predecessor must match revision `4d8a7c2e9f31` after the round
trip.

## Frontend and cutover

The migration frontend adds a single-file picker, local size and extension feedback, SHA-256
calculation, upload progress, retry with a new intent, and authorized download action. Client checks
improve feedback only. FastAPI repeats every check. The browser stores no submission token, signed
URL, digest, object key, or file bytes in local storage.

After backend, database, storage, and browser checks pass, update the attachment cutover to make
`migration-fastapi` the only read and write authority. Freeze `uploadLeaveAttachment` and every
legacy Supabase leave-bucket read. Do not freeze submission, cancellation, approval, notification,
payroll, attendance, or general document paths early.

Rollback disables migration upload and signing before restoring the legacy attachment path. It
does not erase committed metadata or use provider listing to infer orphans. Only an operation row may
authorize cleanup. The Alembic downgrade is for empty-schema and disposable synthetic proof; do not
downgrade a retained environment that contains committed attachment metadata.

## Verification contract

The prerequisite verifier will cover interface parity, conditional create, metadata bounds, signing
expiry, altered tokens, traversal attempts, local persistence, provider timeouts, and adapter-safe
errors. The database verifier will cover every field, check, foreign key, index, grant, `O1` and `S1`
policy, direct-login requirement, claim race, crash boundary, retry delay, eighth-attempt terminal
state, purge guard, and unchanged rows after denial.

The Phase 8D verifier will cover owner and administrator upload, owner, administrator, direct-manager,
and active-delegate signing, plus expired delegate, unrelated actor, cross-branch, cross-tenant,
inaccessible request, token replay, content, size, digest, filename, missing-object, and cleanup
cases. It will also inspect strict projections, OpenAPI, route inventory, frontend isolation,
attachment cutover state, and the legacy freeze.

The final gate is database, storage, authentication, Compose, and frontend sensitive. It must use a
fresh isolated PostgreSQL volume and local synthetic object volume, apply both migrations twice,
prove exact predecessor rollback, restart existing images without rebuilding, compare database and
signing-key state, run the attachment browser journey once, and remove all Phase 8D synthetic rows,
objects, credentials, containers, networks, and volumes.

## Decision request

Approve Decision `8A-ATT-1` to execute the minimum Phase 11-owned prerequisite before Phase 8D.

Approve `8D-STO-D1`, `8D-ATT-D1`, `8D-HTTP-D1`, `8D-FILE-D1`, and `8D-AUD-D1` exactly as written.
Approval authorizes the two reserved Alembic revisions, prerequisite, attachment backend and
frontend, focused verification, cutover, and final gate. It authorizes no cloud resource, real data,
general document migration, notification work, Phase 8E request submission, or later phase.

Stop after this proposal. Do not create either migration or change storage, backend, frontend,
Compose, bootstrap, cutover authority, or legacy code until the project owner records approval.
