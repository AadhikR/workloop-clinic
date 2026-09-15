# Phase 8E amendment proposal

Status: approved by the project owner on 2026-09-15. Phase 8E implementation is authorized through
its stated stop condition.

This proposal closes the two gaps found during the required Phase 8E preflight. The current
protected audit function has no leave-request action, and the Phase 8A contract does not define
which type-specific request fields are required. A deeper RLS review also found that the Phase 5
request update policy permits an employee-owned `Pending` request to become only `Cancelled`. It
blocks the approved automatic `Pending` to `Approved` transition. The project owner approved
decisions `8E-POL-D1`, `8E-HTTP-D1`, `8E-TXN-D1`, `8E-TXN-D2`, and `8E-AUD-D1` exactly as written.
The project owner then approved `8E-RLS-D1` exactly as written.
The runtime database verifier later proved that the existing employee read policies do not permit
row locking. The owner's standing instruction to approve Phase 8E recommendations authorizes the
narrow `8E-RLS-D2` amendment below.

## Verified preflight

- Branch `migration/fastapi-keycloak` is clean and synchronized with its remote at
  `3a52735fa3db24ac02b8731a969fc7f78321fc63`.
- Alembic has one head, `a83d5e7c1b29`.
- The submission cutover remains in `preparation`. Legacy Supabase is its only read and write
  authority.
- `public.append_audit_event(text,text,uuid,text[],text,jsonb)` delegates unknown actions to the
  Phase 5 allowlist. That allowlist contains no leave-request submission, automatic approval, or
  cancellation action.
- `leave_audit_log` accepts the required domain records under its current insert policy. No table
  change is needed for those records.
- The current request, balance, attachment, employee, leave-type, settings, holiday, and
  idempotency fields can support Phase 8E without a new business column, role, grant, constraint,
  or index.
- The current `phase5f_leave_requests_update_runtime` policy blocks employee and manager
  self-submission from changing a newly inserted `Pending` request to `Approved`. Phase 8E needs the
  narrow policy amendment in `8E-RLS-D1`.
- `leave_requests.approved_by_app_user_id` is required for an `Approved` request. For automatic
  approval, it will record the authenticated user who initiated submission. The fixed
  `approval_comment`, domain audit action, and protected audit actor kind distinguish the policy
  decision from a human approval.
- The existing employee and branch indexes are sufficient because submission takes a transaction
  advisory lock for the employee before it checks overlap. The locked balance row serializes
  spending for one employee, leave type, and year.
- No preserved volume or cloud resource was accessed during preflight.

## Decision 8E-POL-D1: request fields and policy checks

The server accepts one strict request shape for self and administrator submission. Administrator
submission adds `employeeId`; self submission does not accept it.

```text
leaveTypeId uuid required
startDate date required
endDate date required
isHalfDay boolean required
halfDayPeriod "AM" | "PM" | null required
reason string required, trimmed, at most 2,000 characters
attachmentId uuid | null required
relationship "Spouse" | "Parent" | "Child" | "Sibling" | null required
deceasedName string | null required, trimmed, at most 200 characters
dateOfDeath date | null required
childBirthDate date | null required
childName string | null required, trimmed, at most 200 characters
expectedDueDate date | null required
institutionName string | null required, trimmed, at most 300 characters
examDates string | null required, trimmed, at most 1,000 characters
substituteEmployeeId uuid | null required
employeeId uuid required only on the administrator route
```

The body contains no company, branch, employee on the self route, leave-type code, status, day
count, approval level, warning, actor label, balance value, attachment token, object key, URL, or
timestamp.

All codes use the stored branch leave type. The code selects only these field rules:

| Leave-type code | Required fields | Fields that may also be present |
| --- | --- | --- |
| `BEREAVEMENT` | `relationship` | `deceasedName`, `dateOfDeath` |
| `PATERNITY` | `childBirthDate` | `childName` |
| `MATERNITY` | `expectedDueDate` | none |
| `STUDY` | `institutionName`, `examDates` | none |
| every other code | none | none of the type-specific fields |

An absent optional string is stored as the existing empty-string default. An absent optional date
is stored as null. A field from the wrong row in the table fails with `validation_failed`; the
server does not silently discard it.

Phase 8E applies no new statutory duration or pay rule. It enforces the stored leave-type fields:
`gender_restriction`, `min_service_months`, `probation_eligible`, `min_notice_days`,
`once_per_career`, `requires_reason`, `requires_attachment`, `day_count_type`, `is_unlimited`,
`not_deducted_from_annual`, `auto_approve`, and `requires_approval`. The current balance calculation
continues to own accrual, carry-forward, sick tiers, and the once-per-career flag.

Notice shorter than `min_notice_days` is a warning, not a denial. Sick leave during probation adds
the existing unpaid warning. Every other failed eligibility, overlap, attachment, required-field,
day-count, or available-balance check denies submission without changing a row. Bounded types may
not submit more than the locked available balance. Zero working-day ranges fail.

The server validates `childBirthDate <= startDate` and `dateOfDeath <= startDate`. It does not add a
six-month parental window, bereavement duration by relationship, maternity due-date window, or
study-service rule beyond the stored type fields. Adding one later is a legal-policy change and
needs a separate proposal.

The substitute must be a different active employee in the same company and branch with employment
status `Active`, `Probation`, or `On Leave`. The field remains optional for every leave type.

## Decision 8E-HTTP-D1: routes and idempotency

Add these routes:

| Method and path | Operation ID | Authority | Success |
| --- | --- | --- | --- |
| `POST /api/v1/leave/requests/self` | `submit_employee_leave_request` | active employee or manager for self | `201` request projection |
| `POST /api/v1/leave/requests/branch` | `submit_admin_leave_request` | administrator in selected branch | `201` request projection |
| `POST /api/v1/leave/requests/{request_id}/cancel/self` | `cancel_employee_leave_request` | owner of a `Pending` request | `200` request projection |
| `POST /api/v1/leave/requests/{request_id}/cancel/branch` | `cancel_admin_leave_request` | administrator in selected branch for a future `Approved` request | `200` request projection |

Cancellation accepts an empty strict JSON object. Every route requires one canonical UUIDv4
`Idempotency-Key`. The command fingerprint binds method, canonical path, company, effective branch,
actor, target employee where applicable, and canonical request body. Identical replay returns the
stored status, headers, and projection with `Idempotency-Replayed: true`. A changed command returns
`409 idempotency_conflict`.

Create responses include a relative `Location: /api/v1/leave/requests/{id}`. All four responses set
`Cache-Control: no-store`. Missing or inaccessible employee, type, request, attachment, substitute,
settings, or balance state uses the existing safe error envelope. Validation failures do not reveal
another tenant or branch.

## Decision 8E-TXN-D1: submission transaction

The transaction derives the company, branch, actor, employee, trusted business date, calendar
leave year, active leave type, settings, holidays, day count, approval level, warnings, and balance
effect.

It locks in this order:

1. Take `pg_advisory_xact_lock` over a stable 64-bit digest of company, branch, and employee UUIDs.
2. Lock the settings row.
3. Lock the employee row.
4. Lock the leave-type row.
5. Lock the optional substitute employee row.
6. Lock active overlapping request rows ordered by request UUID.
7. Lock the balance row for employee, type, and leave year.
8. Lock the optional staged attachment row.

The advisory lock serializes overlap checks even when no request row exists. The balance row
serializes available-balance checks. A missing balance is not created by submission; Phase 8C
initialization remains the only initializer.

For a normal submission, the transaction performs these writes:

1. Insert the request as `Pending` with server-derived fields.
2. Bind a staged attachment by setting its request ID, status to `attached`, attachment time to the
   database statement time, and expiry to null.
3. Add the requested amount to `leave_balances.pending_days` and recompute `remaining_days` for a
   bounded deductible type. Unlimited and non-deducted types keep balance amounts unchanged.
4. Insert `leave_audit_log` action `submitted`, reason `Leave request submitted`, old status empty,
   and new status `Pending`.
5. Append protected action `leave_request_submitted`.

For an active type with `auto_approve=true`, the same transaction first performs the pending writes,
then:

1. Change the request to `Approved`.
2. Set `approved_by_app_user_id` to the authenticated initiating user, set `approved_at` from the
   database statement time, and set `approval_comment` to `Auto-approved by leave type policy`.
3. Move the requested amount from pending to used for a bounded deductible type. Update the sick
   tier counters and `hajj_taken` when their existing balance rules apply.
4. Insert `leave_audit_log` action `auto_approved`, reason
   `Leave request auto-approved by leave type policy`, old status `Pending`, and new status
   `Approved`.
5. Append protected action `leave_request_auto_approved` as a `system_rule` event initiated by the
   authenticated user.

All request, attachment, balance, domain audit, protected audit, and idempotency writes commit or
roll back together.

If submission fails after locking a staged attachment, the request transaction rolls back without
changing that attachment. Validation failure does not destroy a reusable staged upload. The
existing `failed_submission` cleanup path is used only when a caller explicitly abandons an upload
after a failed submission or when the storage coordinator has already created a durable failed
operation. Phase 8E adds no automatic deletion on an ordinary validation error.

## Decision 8E-TXN-D2: cancellation transaction

Cancellation takes the same employee advisory lock, then locks the request, type, balance, and
optional attachment.

An employee or manager acting for self may cancel only an owned `Pending` request. An administrator
may cancel only an `Approved` request in the selected branch whose `start_date` is later than
`public.workloop_business_date()`. Managers, delegates, unrelated staff, inactive staff,
cross-branch administrators, and cross-tenant actors cannot cancel.

Pending cancellation subtracts the exact request days from `pending_days`. Approved cancellation
subtracts them from `used_days`. Both recompute `remaining_days` for bounded deductible types.
Approved sick cancellation recomputes all sick tier counters from the employee's remaining
non-cancelled approved sick requests in the leave year. Approved once-per-career cancellation
recomputes `hajj_taken` from remaining non-cancelled approved requests. No counter may become
negative.

If the request has an attached object, cancellation changes the attachment to `cleanup_pending`,
inserts and claims the approved delete operation, and appends
`leave_attachment_cleanup_requested` with trigger `request_cancelled` in the same database
transaction. The provider delete and final `removed` state use the existing Phase 8D coordinator
after commit. A provider failure leaves the claimed operation for the reconciler and does not roll
back the committed cancellation.

The transaction then changes the request to `Cancelled`, inserts `leave_audit_log` action
`cancelled`, reason `Leave request cancelled`, and the exact old and new statuses, and appends
protected action `leave_request_cancelled`. The idempotency result commits with those writes.

## Decision 8E-AUD-D1: protected audit amendment

Reserve revision `d1e5f8a2c904` as
`backend/alembic/versions/d1e5f8a2c904_add_phase8e_leave_request_audit.py`, with
`down_revision = "a83d5e7c1b29"`.

The revision renames the current public audit function to
`_append_audit_event_phase8e_prior`, revokes public and runtime access to that predecessor, and
installs a public wrapper with the same signature, owner, volatility, security mode, and pinned
search path. Unrelated actions delegate unchanged.

Add only these actions:

| Action | Actor | Changed fields | Reason | Exact metadata |
| --- | --- | --- | --- | --- |
| `leave_request_submitted` | current human | `id`, `status`, `days_requested`, `approval_level_required` | `Leave request submitted` | `transition=created_to_pending`, `submission_mode=self|administrator` |
| `leave_request_auto_approved` | `system_rule` key `leave_auto_approval`, initiated by current human | `status`, `approved_by_app_user_id`, `approved_at`, `approval_comment` | `Leave request auto-approved by leave type policy` | `transition=pending_to_approved`, `decision_source=leave_type_policy` |
| `leave_request_cancelled` | current human | `status` | `Leave request cancelled` | `transition=pending_to_cancelled|approved_to_cancelled` |

The wrapper accepts only a direct `workloop_runtime` login with a valid human context and verified
principal. It requires entity type `leave_request`, a matching company and branch, exact field
arrays in the listed order, exact reason, and exactly the listed metadata keys and values.

For submission, the wrapper proves the current request is `Pending`, the actor is either its active
employee owner or a selected-branch administrator, the matching latest domain audit row has action
`submitted`, empty old status, new status `Pending`, and the current actor, and any linked
attachment is `attached` to that request.

For automatic approval, the wrapper proves the current request is `Approved`, its active leave type
has `auto_approve=true`, `approved_by_app_user_id` is the initiating app user,
`approval_comment` has the fixed policy text, the matching latest domain audit row has action
`auto_approved`, old status `Pending`, new status `Approved`, and the initiating actor. It inserts
the shared event with actor kind `system_rule`, no actor app user, system key
`leave_auto_approval`, and `initiated_by_app_user_id` set to the current app user.

For cancellation, the wrapper proves the current request is `Cancelled`, the matching latest
domain audit row has action `cancelled`, new status `Cancelled`, the metadata transition matches
its old status, and the current actor. A `pending_to_cancelled` event requires the active owner.
An `approved_to_cancelled` event requires a selected-branch administrator and a request start date
later than the trusted business date. Any linked attachment must be `cleanup_pending` or `removed`.

The wrapper never accepts or records employee identifiers, leave-type identifiers, dates, day
values, balance values, attachment identifiers, object keys, filenames, URLs, tokens, warnings,
reason text from the request, or request payloads in metadata.

Downgrade drops the wrapper, restores `_append_audit_event_phase8e_prior` under the public name with
its exact owner and grants, and changes no table. The predecessor definition, ACL, and behavior must
match revision `a83d5e7c1b29` after the round trip.

No new role, table grant, business constraint, index, or schema field is approved by this decision.

## Decision 8E-RLS-D1: automatic self-approval update

The `d1e5f8a2c904` revision also replaces only the current
`phase5f_leave_requests_update_runtime` policy. It does not change the table grant or any other
policy.

The replacement keeps the existing `USING` expression exactly. An administrator may select a
branch request for update. An employee or manager may select an owned `Pending` request. A manager
or active delegate may select an existing team request under the Phase 5 rules.

The replacement keeps every existing `WITH CHECK` branch and adds one branch for automatic
self-approval. That branch requires all of these conditions:

- the direct login, actor kind, business date, company, branch, role, app user, and employee context
  pass the existing `HUMAN_CONTEXT` checks;
- the role is `employee` or `manager`;
- the request company, branch, and employee match the current context;
- the new status is `Approved`;
- `approved_by_app_user_id` equals the current application user;
- `approved_at` is not null;
- `approval_comment` is exactly `Auto-approved by leave type policy`; and
- the request's leave type exists in the same company and branch, is active, and has
  `auto_approve=true`.

The added branch does not permit a browser-selected approver, another employee's request, an
inactive type, a type without automatic approval, a different status, or a later update to an
already approved request. The service must still insert the request as `Pending`, lock and validate
the type and balance, and perform the automatic transition in the same transaction. The policy is
only the database backstop for that transition.

Upgrade renames the existing policy to `phase8e_prior_leave_requests_update_runtime`, changes its
role to `workloop_migration`, and creates the replacement under the original policy name for
`workloop_runtime`. Restricting the renamed policy prevents PostgreSQL's permissive-policy OR rules
from retaining the old runtime path.

Downgrade drops the replacement, changes the renamed predecessor role back to `workloop_runtime`,
and restores its original name. The predecessor command, roles, `USING`, and `WITH CHECK`
expressions must match revision `c74f5e9b2a31` after the round trip.

## Decision 8E-RLS-D2: read-only policy row locks

PostgreSQL applies update-policy visibility to `SELECT FOR UPDATE` and `SELECT FOR SHARE`. The
existing staff select policies expose active same-branch leave types and same-branch settings, but
the administrator-only update policies hide those rows when employee submission tries to lock
them. Plain reads pass while the required transaction locks return no row.

Revision `d1e5f8a2c904` adds one update policy to `leave_settings` and one to `leave_types`. Each
policy applies only to a direct `workloop_runtime` human context for an active employee or manager
in the same company and branch. The leave-type policy also requires `is_active=true`. Their `USING`
expressions permit the rows to participate in `SELECT FOR SHARE` or `SELECT FOR UPDATE`. Their
`WITH CHECK (false)` expressions deny every staff update. The existing administrator update policy
continues to authorize administrator changes.

No grant changes are needed because `workloop_runtime` already holds the table update grants used
by the administrator policies. Downgrade drops the two Phase 8E lock policies. It changes no Phase
5 policy definition or grant.

## Decision 8E-IDEM-D1: leave-request replay resource

The shared idempotency record requires every completed mutation to name an approved replay resource.
Its existing constraint permits branches, employees, departments, user profiles, and tenant-scoped
results, but not a leave request. The Phase 8E service transaction therefore succeeds and then the
idempotency completion update fails closed before commit.

Revision `d1e5f8a2c904` adds `leave_request` to the non-null replay-resource branch of
`ck_idempotency_records_replay_resource`. It changes no response, retention, actor, company, branch,
or replay-authorization rule. The application still authorizes the stored request in the current
database context before returning a replay. Downgrade restores the exact predecessor allowlist.

## Frontend and cutover

After the backend and database checks pass, the migration frontend will use the two submission
routes and two cancellation routes. It will send only server-accepted fields, calculate no
authoritative day or balance value, create a fresh UUIDv4 idempotency key for each user action, and
reuse it only for an identical retry.

The employee form uses the authenticated employee. The administrator form uses the existing
selected branch and employee picker. Both display the returned server day count, warnings, status,
and fixed automatic-approval comment. Cancellation controls appear only for the two allowed states.

The submission cutover moves to `migration-fastapi` only after application, database, concurrency,
route, production-build, browser, restart, and legacy-freeze checks pass. The legacy submission and
cancellation RPCs then fail closed. Manager and delegate decisions, administrator approval queues,
delegation, notifications, payroll, attendance, exports, reports, and Phase 8F remain unchanged.

## Verification contract

The focused application suite will cover strict parsing, every stored policy flag, type-specific
fields, trusted dates, day counts, warnings, balance denial, automatic approval, attachment binding,
both cancellations, safe errors, identical replay, changed-payload conflict, and unchanged state
after denial.

The database verifier will prove self and selected-branch administrator success, every denied
actor and scope, the three protected actions, malformed metadata, false current state, domain-audit
mismatch, automatic actor provenance, unchanged state after denial, grants, forced RLS, model
parity, one Alembic head, empty-schema replay, and exact predecessor restoration.

The concurrency verifier will race duplicate submissions, overlapping requests across different
leave types, balance exhaustion, attachment reuse, and repeated cancellation. It will assert one
committed effect for each race.

The final gate is database, authentication, storage, Compose, and frontend sensitive. It will use a
fresh isolated PostgreSQL volume and synthetic-storage volume, apply migrations twice, run the
required history checks, restart existing images without rebuilding, compare persisted database,
Keycloak, and storage state, then run employee and administrator browser journeys. It will remove
all Phase 8E synthetic resources and leave `workloop-clinic_postgres_data` and the retained empty
FRA1 default VPC untouched.

## Authorization record

Decisions `8E-POL-D1`, `8E-HTTP-D1`, `8E-TXN-D1`, `8E-TXN-D2`, `8E-AUD-D1`, and `8E-RLS-D1` have
exact owner approval. The owner's standing instruction to approve any Phase 8E recommendation
without another question covers `8E-RLS-D2` and `8E-IDEM-D1` exactly as written. Phase 8E
implementation, focused verification, submission cutover, the local final gate, one implementation
commit, one push, and the required GitHub workflow remain authorized.

Approval authorizes no real employee data, production object, cloud resource, paid service, legal
rule beyond `8E-POL-D1`, notification, payroll or attendance effect, manager or delegate decision,
administrator approval queue, delegation change, export, report, general-document migration,
Phase 8F work, or later phase.

Phase 8F remains unauthorized.
