# Part 11A domain and storage contract

## Status and authority

This contract is proposed for project-owner approval. It changes no read or write authority. Legacy
Supabase remains authoritative for all Phase 11 domains until each cutover record passes its own
implementation gate.

The contract uses synthetic data and synthetic files only. It authorizes no DigitalOcean Space,
external scanner, production credential, paid service, real employee file, production retention
period, recovery point objective, recovery time objective, or legal interpretation.

## Approved decision packet

| ID | Decision | Contract |
| --- | --- | --- |
| `11A-D1` | HTTP and scope | Use the Phase 6 envelope, strict unknown-field rejection, `Cache-Control: no-store`, UUID identifiers, generic inaccessible-row 404, and safe stable error codes. Administrators require a selected branch. Employees and managers use self scope unless a named direct-report route says otherwise. |
| `11A-D2` | Lists and concurrency | Lists use `limit` 1 through 100, default 50, and an opaque cursor. Every list has the exact deterministic sort named below. Commands require a UUIDv4 `Idempotency-Key`. Mutable rows require `expectedUpdatedAt`; append-only commands require an expected current source snapshot. |
| `11A-D3` | File acceptance | Employee documents, leave attachments, expense receipts, training evidence, and certification evidence accept only PDF, PNG, and JPEG under the Phase 8 signature rules. One file is 1 through 10,485,760 bytes. The whole multipart request is at most 12,582,912 bytes. |
| `11A-D4` | Private objects and signing | Keep server-generated opaque keys, conditional create, exact size, media type, and SHA-256 metadata, and five-minute signed downloads. A key, filename, URL, or digest grants no authority. The API never returns an object key. |
| `11A-D5` | Malware release | Add a provider-neutral scanner. States are `pending`, `claimed`, `clean`, `infected`, and `failed`. A clean result is valid for 30 days for the exact SHA-256 and scanner definition. Pending, expired, failed, unknown, timeout, or scanner error blocks signing. Infected is terminal until an approved replacement upload creates a new object. |
| `11A-D6` | Recovery and production policy stop | Local proof uses encrypted snapshots, a disposable synthetic provider, and a disposable S3-compatible service. It proves recovery from the most recent completed snapshot and a 15-minute local restore objective. These are test assertions, not production RPO or RTO. Production retention, backup location, schedule, RPO, RTO, and restore owner remain a production-policy stop. |
| `11A-D7` | Employee documents | Administrators may list, upload as verified, review, reject, sign, and remove only pending or rejected rows in the selected branch. Employees may list, upload as pending, sign their own released files, and inspect review state. Managers get no direct-report document access. Verified rows are retained. |
| `11A-D8` | Insurance | Administrators maintain selected-branch policies, one current coverage row per employee, and dependants. Employees and managers may read only their own safe current coverage. Staff never receive branch pricing, broker fields, another employee, dependant rows, or card values. |
| `11A-D9` | Employment contracts | Administrators may read selected-branch history and issue `new`, `renewed`, `converted`, or `not_renewed` commands. Staff contract history remains unsupported. Earlier events never change. One transaction updates current employee contract fields and appends contract and job history. |
| `11A-D10` | Assets | Administrators maintain selected-branch inventory and named status, assign, return, and guarded delete commands. Employees and managers may read only assets assigned to themselves, including retained history. Managers get no direct-report asset inventory. |
| `11A-D11` | Training, certifications, and CME | Employees may self-enrol and edit descriptive fields while planned. Managers may maintain direct-report planned rows. Only administrators and current direct-report managers may record completion. Non-admin certification submissions start pending and need administrator review. Achieved CME is the sum of verified completed CME training in the requested year. |
| `11A-D12` | Appraisals | The fixed section template is Clinical Competency 2.00, Patient Care Quality 2.00, Communication and Teamwork 1.50, Punctuality and Attendance 1.00, and Professional Development 1.00. Employees receive read-only self history. Managers rate direct reports. Administrators generate, review, calibrate, and close. |
| `11A-D13` | Clinical incidents | Only selected-branch administrators can read or mutate incidents. Reports are retained after creation. Investigation, corrective action, and closure are named commands. Free text and involved people never enter logs, task payloads, or generic errors. |
| `11A-D14` | Letter and custom requests | Employees and managers submit and read only their own requests. Administrators decide selected-branch requests. Completed requests expose a strict source projection. Phase 12 owns templates, print windows, PDF, and other output bytes. |
| `11A-D15` | Offboarding checklist | Administrators initialize one checklist per employee from immutable templates, add a provenance-marked custom task, complete or reopen an incomplete task, move visa state forward, and complete only after every required task and blocker passes. Template tasks cannot be deleted. Custom-task deletion is allowed only before completion and only after provenance exists. |
| `11A-D16` | Final settlement | Phase 11 records a locked source snapshot for employment, salary, contract, leave, finalized payroll, advances, assets, and approved manual adjustments. Settlement policy `1.0.0` in `PART_11G_SETTLEMENT_POLICY.md` defines the supported legal and product rules. Unsupported cases fail closed. |
| `11A-D17` | Schema amendment | Add file-security scan state, missing private-file metadata, optimistic-lock timestamps, offboarding task provenance, and immutable final-settlement tables as specified in the amendment proposal. Reuse existing Phase 5 roles and policies where possible. Add one scanner login with no business-table grant. |
| `11A-D18` | Cutover and rollback | Use ten independent cutover records. Each names exactly one reader and writer, freezes the other path, and preserves retained evidence. Rollback disables migration writes before legacy writes return. Reverse dependency order is mandatory. |

## Common representation

Dates are `YYYY-MM-DD`. Years are four-digit integers. Instants are UTC RFC 3339 with milliseconds.
Money is a decimal string with two places. Hours and ratings are decimal strings with no exponent.
The API rejects nonfinite values, excess scale, excess precision, and locale-formatted numbers.
Optional fields are present as `null`.

FastAPI derives company, selected branch, employee relationship, actor, timestamps, workflow state,
object key, canonical media type, digest, byte count, review actor, completion actor, and calculated
values. A browser cannot supply any of them.

Every protected command locks rows in ascending table and UUID order, checks scope and state after
locking, then compares the expected timestamp or source version. An identical replay returns the
stored result. Reusing a key with another payload returns `409 idempotency_conflict`. A stale command
returns `409 state_conflict` and changes no domain row, history, audit, file metadata, operation row,
or idempotency record.

## Common storage and malware contract

### File categories

| Category | Owner | Maximum files | Deletion rule |
| --- | --- | ---: | --- |
| Leave attachment | Phase 8 request | One per request | Phase 8 cancellation and failed-submission cleanup only. |
| Expense receipt | Phase 9 claim | One per claim | Phase 9 preapproval deletion and failed-submission cleanup only. |
| Employee document | Phase 11 employee document | One object per row | Pending or rejected row only. Verified evidence is retained. |
| Training evidence | Phase 11 training record | One object per row | Planned row only. Completed evidence is retained. |
| Certification evidence | Phase 11 certification | One object per row | Pending or rejected row only. Verified evidence is retained. |

The Phase 8 filename, extension, signature, digest, and request-size rules apply without change.
Object keys use a category prefix, version, scope HMAC digest, and record UUID. They contain no name,
email, employee number, filename, browser path, or request text.

### Scanner interface and state

```text
scan_object(stream, size_bytes, sha256, content_type, definition) -> ScanResult
ScanResult(verdict, scanner_name, definition, signature, scanned_at)
verdict = clean | infected | error
```

The worker reserves each attempt before reading the provider. The provider deadline and scanner
deadline are each below the 15-minute lease. It uses the storage retry schedule and eight-attempt
ceiling. `clean` records `validUntil = scannedAt + 30 days`. `infected` records no malware name or
file content in the database or logs. `error` becomes a retryable or terminal failed row with an
allowlisted error code. A current clean result must match object key, size, content type, SHA-256,
and scanner definition before the service may sign.

The local scanner is deterministic. It reports infected when the synthetic fixture contains the
tracked test marker and clean otherwise. It is test-only and makes no claim about real malware.
Production stays disabled until an external scanner, credentials, cost, data location, and operator
contract receive separate approval.

### Recovery, backup, and operator rules

Object ownership comes from PostgreSQL metadata and durable operations, never provider listing.
Listing may compare a scoped backup manifest with a disposable test bucket, but it cannot create or
delete an object by itself. A missing object makes signing fail with `503 service_unavailable`, adds
a safe operation or alert, and does not erase metadata. An orphan is removable only when a durable
upload operation proves that domain metadata never committed.

The local snapshot contains a canonical manifest, encrypted object bodies and metadata, scan rows,
and operation rows. AES-256-GCM uses a dedicated test key. Restore verifies manifest digest, object
digest, metadata, scan binding, and record count before enabling reads. The rotation drill installs
a new signing or storage credential, proves old and new key behavior, revokes the old credential,
and never prints either secret.

Safe operational logs contain operation UUID, scan UUID, entity type, attempt count, and allowlisted
error code. They exclude object keys, filenames, signed URLs, digests, employee IDs, incident text,
document numbers, card numbers, and request payloads.

## Employee document routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/employee-documents` | Administrator. Required `employeeId`; optional `status`, `documentType`; sort `uploadedAt desc,id desc`. |
| `POST /api/v1/employee-documents/submissions` | Administrator or self. Issue a one-use upload intent. Admin supplies selected-branch `employeeId`; staff omit it. |
| `POST /api/v1/employee-documents/submissions/{submissionId}/file` | Consume the intent, validate and conditionally store one file, then queue scanning. |
| `GET /api/v1/employee-documents/self` | Employee or manager self. Sort `uploadedAt desc,id desc`. |
| `POST /api/v1/employee-documents/{documentId}/verify` | Administrator. Pending to verified under `expectedUpdatedAt`. |
| `POST /api/v1/employee-documents/{documentId}/reject` | Administrator. Pending to rejected; reason is 1 through 500 trimmed characters. |
| `POST /api/v1/employee-documents/{documentId}/download` | Administrator in selected branch or employee self. Requires current clean scan. |
| `DELETE /api/v1/employee-documents/{documentId}` | Administrator for pending or rejected, or self for own pending or rejected. Queue durable object cleanup. |

Document type is one of the Phase 0 `DOC_GROUPS` labels. Document number is trimmed, 1 through 120
characters for new uploads. Notes are 0 through 1,000 characters. Expiry is optional and cannot
precede the trusted upload business date. Responses include review state, normalized filename,
size, media type, expiry, review actor display name when allowed, and timestamps. They exclude
document number from list responses, object key, digest, scan internals, and signed URL.

## Insurance routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/insurance/policies` | Administrator. Filters `renewalFrom`, `renewalTo`, `search`; sort `renewalDate nulls last,insurerName,id`. |
| `POST /api/v1/insurance/policies` | Administrator. Create selected-branch policy. |
| `PATCH /api/v1/insurance/policies/{policyId}` | Administrator. Ordinary fields under `expectedUpdatedAt`. |
| `DELETE /api/v1/insurance/policies/{policyId}` | Administrator. Only when no current coverage references it. |
| `PUT /api/v1/insurance/employees/{employeeId}/coverage` | Administrator. Assign or replace current coverage in one transaction. |
| `GET /api/v1/insurance/employees/{employeeId}/dependants` | Administrator. Sort `name,id`. |
| `POST /api/v1/insurance/employees/{employeeId}/dependants` | Administrator. Create a dependant. |
| `PATCH /api/v1/insurance/dependants/{dependantId}` | Administrator. Update under `expectedUpdatedAt`. |
| `DELETE /api/v1/insurance/dependants/{dependantId}` | Administrator. Delete before offboarding settlement snapshot use. |
| `GET /api/v1/insurance/self` | Employee or manager self. Safe current coverage and linked policy only. |

Annual premium is `0.00` through `9999999999.99`. Policy number, tier, member, and card values are
trimmed at 120 characters. Names are 1 through 180. Contact and notes are at most 500 and 1,000.
Coverage expiry cannot precede effective date. Replacement locks employee, current coverage, and
policy, and keeps one row per employee.

## Employment contract routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/employees/{employeeId}/contracts` | Administrator. Sort `createdAt desc,id desc`. |
| `POST /api/v1/employees/{employeeId}/contracts/new` | Administrator. Only when no event exists and expected current fields match. |
| `POST /api/v1/employees/{employeeId}/contracts/renew` | Administrator. Append `renewed`; contract type is unchanged. |
| `POST /api/v1/employees/{employeeId}/contracts/convert` | Administrator. Append `converted`; type must change. |
| `POST /api/v1/employees/{employeeId}/contracts/not-renewed` | Administrator. Append `not_renewed`; no current-field rewrite beyond the approved non-renewal marker. |

Start and end are optional only where the Phase 4 row permits null, but a new, renewed, or converted
limited contract requires both and `endDate >= startDate`. An unlimited contract requires null end.
Notes are at most 1,000 characters. The expected snapshot contains employee `updatedAt`, current
contract type and end date, and latest contract event ID. Staff history is unsupported.

## Asset routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/assets` | Administrator. Filters `status`, `category`, `search`; sort `assetCode,name,id`. |
| `POST /api/v1/assets` | Administrator. Create selected-branch asset. |
| `PATCH /api/v1/assets/{assetId}` | Administrator. Edit ordinary fields under `expectedUpdatedAt`. |
| `POST /api/v1/assets/{assetId}/status` | Administrator. Named state transition. |
| `POST /api/v1/assets/{assetId}/assign` | Administrator. Assign to one active same-branch employee. |
| `POST /api/v1/assets/{assetId}/return` | Administrator. Close the sole open assignment. |
| `DELETE /api/v1/assets/{assetId}` | Administrator. Only an asset with no assignment history. |
| `GET /api/v1/assets/self` | Employee or manager self. Current and returned history; sort `assignedDate desc,id desc`. |

Asset name is 1 through 180 characters. Nonempty asset code is normalized uppercase and unique in
the branch. Purchase cost is null or `0.00` through `9999999999.99`. Assignment and return dates are
trusted business dates, and return cannot precede assignment. Assignment locks asset, employee, and
open assignment in UUID order.

## Training, certification, and CME routes

Administrator lists use selected branch. Staff routes are self or named direct-report scope.

| Method and path | Behavior |
| --- | --- |
| `GET,POST /api/v1/training-records` | Admin list or create. Filters employee, year, status, type, and CME; sort `startDate desc,id desc`. |
| `PATCH,DELETE /api/v1/training-records/{recordId}` | Edit allowed fields or delete a planned row. |
| `POST /api/v1/training-records/{recordId}/complete` | Admin or current direct-report manager. Set end date, duration, score, passed, CME flag, and optional evidence. |
| `GET,POST /api/v1/training-records/self` | Self list and planned enrolment. |
| `GET,POST /api/v1/training-records/direct-reports` | Manager list and planned creation for current reports. |
| `GET,POST /api/v1/certifications` | Admin list and trusted verified creation. |
| `GET,POST /api/v1/certifications/self` | Self list and pending submission. |
| `GET,POST /api/v1/certifications/direct-reports` | Manager list and pending direct-report submission. |
| `POST /api/v1/certifications/{certificationId}/verify` | Admin pending to verified. |
| `POST /api/v1/certifications/{certificationId}/reject` | Admin pending to rejected with reason. |
| `POST /api/v1/training-files/...`; `POST /api/v1/certification-files/...` | One-use upload, scan, download, and guarded cleanup under the common file contract. |
| `GET,PUT,DELETE /api/v1/cme-requirements/{employeeId}/{year}` | Admin maintains one target. |
| `GET /api/v1/cme/self?year=YYYY` | Self target, achieved total, and nonnegative gap. |

Duration is `0.00` through `9999.99` hours. Cost is `0.00` through `9999999999.99`. CME target is
`0.0` through `9999.9`. Achieved CME includes only `status=completed`, `passed=true`, `isCme=true`,
start date in the year, and current clean evidence when evidence is required. The server sums exact
stored hours and returns one decimal place. A browser never persists achieved hours.

## Appraisal routes

| Method and path | Role and behavior |
| --- | --- |
| `GET,POST /api/v1/appraisal-cycles` | Administrator list or create; sort `reviewFrom desc,id desc`. |
| `PATCH /api/v1/appraisal-cycles/{cycleId}` | Administrator edits a draft under `expectedUpdatedAt`. |
| `POST /api/v1/appraisal-cycles/{cycleId}/activate` | Administrator. Draft to active. |
| `POST /api/v1/appraisal-cycles/{cycleId}/generate` | Administrator. Create missing employee appraisals and fixed sections idempotently. |
| `POST /api/v1/appraisal-cycles/{cycleId}/close` | Administrator. Active to closed when every appraisal is reviewed or calibrated. |
| `DELETE /api/v1/appraisal-cycles/{cycleId}` | Administrator. Unused draft only. |
| `GET /api/v1/appraisals/self` | Employee or manager self history. |
| `GET /api/v1/appraisals/direct-reports` | Manager current direct reports only. |
| `PUT /api/v1/appraisals/{appraisalId}/sections/{sectionId}` | Manager rates one direct-report section under parent `expectedUpdatedAt`. |
| `POST /api/v1/appraisals/{appraisalId}/review` | Administrator records review, comments, development plan, and calculated rating. |
| `POST /api/v1/appraisals/{appraisalId}/calibrate` | Administrator changes reviewed to calibrated with final rating. |

Rating values are `1.0` through `5.0` with one decimal place. The weighted rating is
`sum(rating * weight) / sum(weight)`, rounded once to one decimal with `ROUND_HALF_UP`. Every fixed
section must be rated before review. Self-rating remains read-only and no Phase 11 route writes it.

## Clinical incident routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/clinical-incidents` | Administrator. Filters date range, type, severity, status; sort `incidentDate desc,incidentTime desc nulls last,id desc`. |
| `POST /api/v1/clinical-incidents` | Administrator. Create an open retained report. |
| `PATCH /api/v1/clinical-incidents/{incidentId}` | Administrator. Edit ordinary fields while open under `expectedUpdatedAt`. |
| `POST /api/v1/clinical-incidents/{incidentId}/investigate` | Administrator. Open to investigating with root cause. |
| `POST /api/v1/clinical-incidents/{incidentId}/corrective-action` | Administrator. Update required corrective action while investigating. |
| `POST /api/v1/clinical-incidents/{incidentId}/close` | Administrator. Close only with nonempty root cause and corrective action. |

Description is 1 through 10,000 characters. Location and department are at most 180. Immediate
action, root cause, corrective action, and notes are each at most 10,000. Reporter and involved
employee are optional same-branch employees. The API does not expose whether a rejected employee ID
exists. Hard delete is unsupported.

## Letter and custom request routes

| Method and path | Role and behavior |
| --- | --- |
| `GET /api/v1/requests/self` | Employee or manager self. Optional status and kind; sort `requestedAt desc,id desc`. |
| `POST /api/v1/requests/self` | Submit `letter` or `custom`. Server derives employee and snapshot. |
| `GET /api/v1/requests` | Administrator selected-branch queue. Filters status, kind, employee; same sort. |
| `GET /api/v1/requests/{requestId}` | Administrator selected branch or owner self. Role-specific projection. |
| `POST /api/v1/requests/{requestId}/complete` | Administrator. Pending to completed under `expectedRequestedAt`. |
| `POST /api/v1/requests/{requestId}/reject` | Administrator. Pending to rejected with 1 through 500 character reason. |
| `GET /api/v1/requests/{requestId}/print-source` | Completed owner self or selected-branch administrator. Trusted source fields only. |

Letter type is one of the five Phase 0 labels. Purpose is 0 through 500 characters, except external
letter types require at least 5. A custom subject is 3 through 120 and detail is 5 through 2,000.
The submission snapshot fixes employee display name, job title, department, start date, branch legal
name, and the salary fields required by the selected letter type. Staff list responses omit salary.
The print source never accepts a browser template.

## Offboarding and final settlement routes

| Method and path | Role and behavior |
| --- | --- |
| `POST /api/v1/offboarding/{employeeId}/initialize` | Administrator. Create one checklist and copy immutable templates. |
| `GET /api/v1/offboarding`; `GET /api/v1/offboarding/{checklistId}` | Administrator selected branch; list sort `createdAt desc,id desc`. |
| `POST /api/v1/offboarding/{checklistId}/tasks` | Administrator. Add custom task with explicit provenance. |
| `POST /api/v1/offboarding/{checklistId}/tasks/{taskId}/complete` | Administrator. Complete under expected checklist and task timestamps. |
| `POST /api/v1/offboarding/{checklistId}/tasks/{taskId}/reopen` | Administrator. Reopen only before checklist completion. |
| `DELETE /api/v1/offboarding/{checklistId}/tasks/{taskId}` | Administrator. Incomplete custom task only. |
| `POST /api/v1/offboarding/{checklistId}/visa` | Administrator. Forward-only visa transition with trusted date. |
| `POST /api/v1/offboarding/{checklistId}/settlement/preview` | Administrator. Return locked source identities, exact amounts, and the source digest. Persist nothing. |
| `POST /api/v1/offboarding/{checklistId}/complete` | Administrator. Persist one immutable approved settlement, complete employment through Phase 7, then complete checklist in one transaction. |
| `GET /api/v1/offboarding/{checklistId}/letter-source` | Administrator. Strict source data only. Phase 12 renders bytes. |

Visa states move `not_started` to `initiated` to `submitted_gdrfa` to `cancelled`. A technical
rollback never moves them backward. Completion locks employee, checklist, tasks, open assets, latest
contract event, leave balance, latest finalized payroll snapshot, active advances and repayments,
and policy configuration in that order. It stores every source ID, version, amount, policy version,
intermediate value, and final amount.

### Settlement policy

The legacy browser calculator remains outside the migration build. It contains obsolete resignation
reductions, contradictory service-date handling, and binary floating-point arithmetic.

`PART_11G_SETTLEMENT_POLICY.md` defines policy `1.0.0`. The service supports foreign, full-time UAE
mainland private-sector employees under the traditional gratuity scheme. It uses inclusive calendar
service days minus approved unpaid leave, a 365-day year, the statutory 21-day and 30-day tiers, the
24-month cap, annual leave at basic salary divided by 30, approved termination-month payroll, exact
advance settlement, reviewed manual adjustments, half-up cent rounding, negative-net rejection, and
separation between checklist initializer and completer. Other jurisdictions or worker schemes return
`409 settlement_policy_unavailable`.

## Phase boundaries

Phase 12 owns notifications, tasks, dashboards, reports, expiry jobs, letter templates, NOC and
experience-letter rendering, print windows, PDF, CSV, ZIP, SIF, and every other generated output.
Phase 13 owns final Supabase removal. Phase 11 routes do not call Supabase and do not provide a legacy
fallback.
