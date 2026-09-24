# Part 12A output and delivery contract

## Authority and source rule

FastAPI authorizes every notification, task, dashboard, report, preview, render, and download before
reading a source projection. The server derives company, branch, employee, manager relationships,
and recipient identity from the authenticated principal. An ID, filename, format, filter, cursor, or
browser route grants no authority.

Phase 12 consumes the following owners:

- Phase 7 for company, branch, department, employee, employment, salary, bank, profile, job-history,
  and identity projections.
- Phase 8 for leave settings, requests, approvals, attachments, calendars, and persisted balances.
- Phase 9 for expenses, advances, repayments, finalized payroll entries, immutable payslips, WPS SIF
  input, WPS state, and Nafis snapshots.
- Phase 10 for clock events, calculated attendance, attendance periods, regularisations, shifts,
  published rosters, swaps, staffing validation, and compliance overrides.
- Phase 11 for documents, insurance, contracts, assets, training, certifications, CME, appraisals,
  incidents, letter requests, offboarding, final settlement, and strict print sources.

A Phase 12 service may filter, order, paginate, summarize, format, and render these projections. It
must not reconstruct a missing domain fact, repair source state, update a source row, retry a domain
workflow, or treat legacy Supabase data as a fallback. Missing required source data returns a safe
error or an explicit unavailable item.

## Authorization matrix

| Consumer | Scope | Allowed output |
| --- | --- | --- |
| Administrator | Verified selected branch in the caller's company | Branch notifications, admin tasks, admin and clinical dashboards, approved reports, SIF, branch payslips, letters, settlement output, CSV, PDF, and ZIP |
| Manager | Self plus current direct reports where the source domain grants manager scope | Own notifications, manager tasks, self dashboard, and explicitly approved direct-report summaries. No payroll, bank, incident, or broad report access |
| Employee | Linked employee self scope | Own notifications, tasks, self dashboard, own payslip PDF, own completed requested letter, and own source-safe downloads |
| Expiry job | One company, one branch or approved tenant-wide null branch, and one trusted business date | Insert only allowlisted expiry notifications and matching audit events |
| Migration and seed | Existing controlled database duties | No HTTP output access by role alone |

Unknown roles, inactive accounts, stale employee links, disabled principals, missing selected branch,
cross-company IDs, cross-branch IDs, stale manager relationships, and output types outside this table
return denial. The service does not hide a denial by returning an empty result.

## Time, dates, and decimals

The business time zone is `Asia/Dubai`. Public business dates use `YYYY-MM-DD`. Periods use
`YYYY-MM`. API timestamps use RFC 3339 UTC with millisecond precision and a trailing `Z`. Source
timestamps remain authoritative and are never replaced with the renderer clock.

Expiry calculations compare SQL dates to the trusted Dubai business date. A source expiring on the
business date has zero days remaining. Calendar-day differences do not divide JavaScript
milliseconds. Reports that accept `from` and `to` include both dates. Invalid dates, reversed
ranges, and ranges beyond the report's documented ceiling return `422 validation_error`.

Money uses `Decimal` and PostgreSQL `NUMERIC`. Values cross the HTTP boundary as fixed-point strings.
Calculations use source-domain precision and apply `ROUND_HALF_UP` only at the named output boundary.
SIF basic and variable amounts round to integer AED with `ROUND_HALF_UP`; the SCR total is the sum of
the emitted EDR integer values. Counts remain integers. Durations use decimal hours as strings when a
fraction is possible.

## Response and pagination contract

JSON field names are camelCase. A successful collection returns:

```json
{
  "items": [],
  "nextCursor": null,
  "asOf": "2026-09-24T08:00:00.000Z",
  "sourceVersion": "opaque-source-version"
}
```

`nextCursor` is opaque, signed or integrity-protected, scoped to the route, principal, selected
branch, normalized filters, and sort. Clients cannot reuse it with different filters. Default limit
is 50 and maximum limit is 200 unless a named route sets a lower maximum. Invalid and expired
cursors return `400 invalid_cursor`.

Each collection defines one total order and appends an immutable UUID tie-breaker. Null optional
values are JSON `null`; omitted fields are reserved for role redaction or a documented response
variant. Empty authorized results return an empty list and `nextCursor: null`. A failed source
category returns an explicit failure and never disappears.

## Notifications and expiry

The notification routes are:

- `GET /api/v1/notifications?limit={n}&cursor={cursor}` ordered by `createdAt DESC, id DESC`.
- `GET /api/v1/notifications/unread-count` returning `{ "count": 0, "asOf": "..." }`.
- `PUT /api/v1/notifications/{notificationId}/read` as a monotonic, replay-safe update.
- `POST /api/v1/notifications/read-all` with `Idempotency-Key`, scoped to the same inbox partition as
  the list route.

The item shape is `{ id, type, title, body, relatedEntityType, relatedEntityId, readAt, createdAt }`.
No endpoint returns creator identity, recipient identity, company ID, branch ID, or an unrelated
source record. Read endpoints never mark an item read.

Workflow notifications use the existing fixed-purpose database function for `leave_approved`,
`leave_rejected`, `payslip_available`, and `roster_published`. The source transaction calls it after
the authoritative state transition. The function derives recipient, branch, title, body, and source
identity. Failure aborts the source transaction only where the source contract already makes the
notification atomic; otherwise it records a safe retryable failure without changing source state.

Expiry production is an explicit command, not a scheduler. It requires exact company ID, branch ID
or approved null branch, and business date. It runs under `workloop_expiry_processing`, obtains a
transaction-scoped advisory lock for that tuple, reads only granted columns, inserts through the
existing source-linked policy, and writes the matching audit event. A repeated run creates no new
notification because the five-part dedup key and threshold-specific related entity ID are stable.
Concurrent runs produce the same final rows. No catch-up run fabricates an alert for a threshold
that the trusted business date has passed.

The approved expiry bands are frozen from the existing security policy: standard employee and
uploaded documents 60, 30, and 14 days; clinical documents 90, 30, and 14 days; insurance coverage
and policy renewal 60 and 30 days; probation 14 and 7 days; limited contracts 60, 30, 14, and 7 days;
certifications and professional licences 60, 30, and 14 days. Expired rows do not create new future
alerts. Inactive or terminated employees are excluded where the source contract marks them out of
scope.

## Task aggregation

`GET /api/v1/tasks` returns a role-derived catalogue. Administrators may pass no branch ID because
the selected branch is already verified in context. Supported optional filters are category,
urgency, `limit`, and `cursor`. Ordering is category order from the server catalogue, then urgency
rank, source business date ascending with missing dates last, created timestamp ascending with
missing timestamps last, and task ID ascending.

```json
{
  "categories": [
    {
      "code": "leaveApprovals",
      "label": "Leave requests",
      "status": "ok",
      "count": 1,
      "items": [
        {
          "id": "leaveApproval:00000000-0000-0000-0000-000000000001",
          "entity": "leaveRequest",
          "entityId": "00000000-0000-0000-0000-000000000001",
          "title": "Employee name",
          "subtitle": "Annual leave, 2.00 days",
          "urgency": "action",
          "dueDate": null,
          "createdAt": "2026-09-24T08:00:00.000Z",
          "navigation": { "screen": "leaveApprovals" }
        }
      ]
    }
  ],
  "asOf": "2026-09-24T08:00:00.000Z",
  "sourceVersion": "opaque-source-version"
}
```

Every role has a fixed category list. A category with no items returns `status: "empty"`. A source
failure returns `status: "failed"`, `items: []`, and a safe `errorCode`; the overall response uses
`503 task_source_unavailable` when any required category fails. `Promise.allSettled` omission is not
parity. Task IDs are stable summaries and are not mutation tokens.

## Dashboards

The routes are `GET /api/v1/dashboards/admin`, `GET /api/v1/dashboards/clinical`, and
`GET /api/v1/dashboards/self`. Each returns one internally consistent snapshot with `asOf`,
`businessDate`, `sourceVersion`, cards, and bounded drill-down links. Cards contain machine code,
label, value, unit, severity, and optional comparison. They do not embed unrestricted domain rows.

Admin payroll, WPS, and Nafis cards use Phase 9 projections. Expiry cards share the exact 12B date
policy. Clinical staffing uses the Phase 10 publication and validation result. Credential compliance
counts only Phase 11 verified, download-eligible evidence. Self cards use linked employee scope and
never accept an employee ID. Dashboard endpoints do not produce notifications as a side effect.

## Reports

`GET /api/v1/reports/{reportId}` returns `{ reportId, columns, rows, totals, filters, asOf,
sourceVersion, nextCursor }`. Approved report IDs are `headcount`, `payrollCost`, `leaveUtilization`,
`attendanceSummary`, `overtime`, `documentExpiry`, `salaryMovement`, `turnover`,
`staffingCompliance`, `wpsCompliance`, `emiratization`, `eosLiability`, and `leaveBalance`.

Only a report's documented filters are accepted. Unknown filters return `422 unknown_filter`.
Employee and department filters must resolve inside the caller's scope. Status filters use the
source domain's exact case. Period reports sort by period descending. Employee reports sort by
normalized employee name ascending and employee ID ascending. Event reports sort by business date
ascending, event timestamp ascending, and ID ascending. Document expiry sorts by expiry date
ascending, employee name ascending, source kind ascending, and source ID ascending.

Report columns carry `{ key, label, type, scale, nullable }`. Row values retain their JSON type;
money remains a fixed-point string. Totals state which rows they cover. Paginated totals cover the
full normalized filter set, not only the current page. EOS liability uses the approved Phase 11
policy. Unsupported workers appear with `status: "unavailable"` and a safe reason rather than a
fabricated amount.

## CSV and SIF

CSV endpoints are `GET /api/v1/reports/{reportId}.csv` plus the named employee-template,
employee-export, leave-balance, attendance, roster, and Nafis export routes implemented in 12F.
They use the same authorization, filters, source version, column order, and row order as JSON.

CSV is UTF-8 with a BOM only for the roster compatibility export. All other CSV files are UTF-8
without a BOM. Records end with CRLF. Fields use RFC 4180 double-quote escaping. A null is empty, a
boolean is `true` or `false`, a date keeps `YYYY-MM-DD`, a timestamp keeps UTC RFC 3339, and money
keeps its fixed scale without grouping separators. Formula-leading text beginning with `=`, `+`,
`-`, `@`, tab, or carriage return is prefixed with a single quote. This is an output encoding rule,
not a change to source data.

SIF routes are `GET /api/v1/payroll-runs/{runId}/sif/preview` and
`GET /api/v1/payroll-runs/{runId}/sif`, with `scope=all` or `scope=rejected`. They consume only the
Phase 9 SIF input projection. EDR rows sort by MOL employee ID ascending and employee ID ascending;
one SCR row follows. Encoding is strict ASCII, fields contain no comma or control character, and
records end with CRLF including the final record. Preview parses the exact generated bytes and
returns the same `sourceDigest`; it is not a second implementation.

## PDF, letters, print, ZIP, and download delivery

PDF routes include report PDF, administrator payslip PDF, self payslip PDF, completed requested
letter PDF, offboarding letter PDF, and final-settlement PDF. A print action opens the authorized PDF
response in a browser viewer. There is no separate browser HTML calculation path. A requested letter
uses the Phase 11 print-source snapshot; offboarding letters use the Phase 11 letter source; final
settlement uses the persisted approved settlement.

PDF renderers pin page size, margins, fonts, font versions, asset digests, locale, metadata, source
timestamp, and document identifier. They disable wall-clock creation timestamps, random IDs, and
network-fetched assets. The same normalized source and renderer version produce deterministic bytes
and the same SHA-256 digest. A missing approved font or logo fails closed.

Bulk payslip ZIP is ordered by employee number, employee ID, and filename. Entry timestamps use the
payroll finalization timestamp rounded to the ZIP format's supported precision. Compression level,
UTF-8 filename flag, permissions, and entry order are fixed. The archive contains only authorized
PDF files and a deterministic UTF-8 manifest with filenames, byte counts, and SHA-256 digests.

The service streams bytes and never stores them in a database or object bucket. It calculates a
`sourceDigest` from canonical source JSON and records safe audit metadata after authorization and
before the response completes. Failure to record required sensitive-output audit denies the output.

## Filenames and headers

The server owns filenames. It normalizes Unicode to NFC, replaces path separators and control
characters, collapses whitespace to `_`, permits letters, digits, `_`, `-`, and `.`, caps the base
name at 120 UTF-8 bytes, and appends the fixed extension. User input cannot supply a path or
extension.

Successful byte responses include:

- the exact `Content-Type` for CSV, PDF, ZIP, or SIF;
- `Content-Disposition: attachment; filename="ascii-fallback.ext"; filename*=UTF-8''encoded-name`;
- `Content-Length` when known;
- `Digest: sha-256=...`;
- `ETag` derived from renderer version and source digest;
- `Cache-Control: no-store` and `Pragma: no-cache`;
- `X-Content-Type-Options: nosniff`;
- `X-Request-ID`; and
- `Vary: Authorization`.

PDF preview may use `Content-Disposition: inline` only on a route that has already performed the
same authorization as download. Range requests are not supported in Phase 12. Responses never
redirect to a public or signed object URL.

## Idempotency, concurrency, and limits

Reads and deterministic downloads need no `Idempotency-Key`. `PUT` notification read is naturally
idempotent. Notification read-all and any explicit output command that persists audit or state
requires `Idempotency-Key` and the Phase 6 fingerprint contract. Reusing a key with a changed body,
query, principal, or branch returns `409 idempotency_conflict`.

Expiry runs use the tuple lock described above. Renderers use bounded worker concurrency and a
per-principal limit. JSON and CSV reports cap date span, page size, and maximum total exported rows.
PDF and ZIP routes cap page count, entry count, uncompressed bytes, and render time. A limit breach
returns `413 output_limit_exceeded` before partial bytes are sent.

## Safe errors and logging

Errors use `application/problem+json` with `{ type, title, status, code, requestId, detail? }`.
`detail` is safe and optional. The service distinguishes `401`, `403`, `404`, `409`, `413`, `422`,
and `503` without exposing whether an out-of-scope object exists. Output routes do not send partial
files after an error.

Logs may contain request ID, route, actor app-user ID, company ID, branch ID, report or output code,
source digest, result code, duration, row count, and byte count. Logs must not contain notification
bodies, report rows, employee names, salary or bank data, filenames containing personal data, SIF
content, PDF bytes, letter text, access tokens, or database credentials.

## Audit contract

Notification creation and read changes use existing notification and audit controls. Sensitive
output generation uses the proposed `append_phase12_output_audit` protected function. Audit actions
are allowlisted by output family. Metadata contains format, normalized filter digest, source digest,
renderer version, byte count, row or entry count, and response result. It does not contain output
bytes, report rows, names, filenames with personal data, or free text.

Ordinary JSON dashboard and task reads rely on request logs. SIF, payslip, letter, final settlement,
bulk ZIP, and administrator report exports require the persistent output audit. The actor cannot
supply company, branch, or actor identity to the protected writer.

## Cutover and rollback

Each cutover record names the migration route, frozen legacy caller, output authority, source
projection, audit action, test evidence, and reverse rollback step. Dual generation is forbidden.
Preview and final download switch together when they share a renderer.

Rollback disables 12G output routes, then 12F byte routes, 12E reports, 12D dashboards, 12C tasks,
and 12B notification producers and inbox routes. It preserves source rows, notifications, read
timestamps, audit events, source snapshots, and renderer evidence. Legacy readers may return only
after their migration counterpart is disabled. Phase 13 owns final Supabase removal and legacy file
deletion.

No Phase 12 rollback reverses a Phase 7 through 11 domain transition or deletes a generated audit
event. A renderer defect rolls back the renderer and delivery route, not the payroll, leave,
attendance, request, or offboarding source.
