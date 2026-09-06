# Phase 5A permission matrix and RLS design

## Status

Phase 5A completed on 2026-09-06 after the project owner signed off Phase 4 and authorized this
part. The owner approved `5A-D1` through `5A-D20`, the full 54-table catalogue, and the 119-policy
reconciliation without amendment. The independent GPT-5.6 review closed all 51 findings. Final
documentation validation passed. No authorization code, repository, policy, grant, database
helper, schema revision, route, frontend change, secret, external resource, or real data was
implemented in Phase 5A.

The design covers the 54 tables at Alembic head `d307b9c1f25e`. The proposed audit and storage
operation tables are decisions, not existing target tables.

## Sources and precedence

This contract uses the following order when sources disagree:

1. Approved decisions in `DIGITALOCEAN_MIGRATION_PLAN.md`.
2. The approved Phase 4 schema catalogue and the implemented Phase 4 models, migrations,
   constraints, retained functions, and grant verifier.
3. The Phase 3 token and application-user boundary.
4. The Phase 0 feature and contract matrix, synthetic test data, and SQL inventory.
5. The legacy frontend only as evidence of an operation. A legacy broad policy or unsafe direct
   write does not become an authorization rule.

The current runtime grant matrix is an implementation starting point, not the final Phase 5 grant
contract. It gives `workloop_runtime` `SELECT` on every table, with selected `INSERT` and `UPDATE`
grants. It grants no table `DELETE`. Direct writes to `payroll_runs`, `payroll_entries`,
`salary_advances`, `roster_assignments`, and `shift_swap_requests` are blocked. The three retained
business functions are the only current runtime mutation path for their protected operations.

## Trust boundary

Keycloak proves the issuer and subject of an access token intended for `workloop-api`. It does not
grant a Workloop role or data scope. FastAPI resolves the active `app_users` row and its single
`user_profiles` row from PostgreSQL. PostgreSQL supplies the role, company, employee link, employee
branch, reporting relationship, and leave delegation.

FastAPI dependencies and scoped repository statements are the primary authorization boundary.
PostgreSQL RLS is defense in depth. RLS does not replace endpoint role checks, field allowlists,
state-transition checks, scoped `UPDATE` and `DELETE` predicates, affected-row checks, or all-row
validation for bulk work.

The following values never grant business scope:

- Keycloak realm or client roles.
- Browser role, company, branch, employee, manager, delegate, or actor fields.
- Email addresses.
- Request headers, query values, route IDs, body IDs, object paths, or other caller-supplied
  identifiers.

A branch ID or object ID may select a candidate. FastAPI must still prove it belongs to the
database-derived company and permitted scope.

## Scope rules

### Tenant and branch

`companies.id` is the tenant key. `branches.id` is an operating and payroll location within that
tenant. A tenant-wide row has `company_id` and no branch requirement. A branch-owned row must match
both `company_id` and `branch_id`.

An admin principal contains `company_id` but no employee or default branch. Each branch-scoped
request must send `X-Workloop-Branch-ID`. FastAPI parses the value as a UUID, then runs a scoped
lookup equivalent to:

```sql
SELECT id
FROM branches
WHERE id = :selected_branch_id
  AND company_id = :principal_company_id;
```

A missing header on a branch-scoped operation returns `400 branch_required`. A malformed value
returns `422 invalid_branch`. A well-formed branch outside the admin's company returns the same
generic `404 resource_not_found` used for a missing branch. FastAPI puts the verified result into
the transaction context. A body or query branch field must be absent or equal to the verified
branch. It never replaces it.

Tenant-wide endpoints do not accept the branch header as a way to widen or narrow ownership.
Collection filters may include a verified branch, but a filter is not authorization.

An admin discovers valid choices through selector-free `GET /branches`, which returns only branches
in the database-derived company. Selector-free `POST /branches` creates a branch in that company.
Company settings and other tenant-wide operations are also selector-free. Reading, updating, or
deleting one existing branch requires the header and path identifier to name the same branch. All
other branch-owned collection, object, and workflow operations require the verified header. The UI
may remember the choice for convenience, but the server proves it again on every request.

Managers and employees use the branch on their linked employee row. They cannot select another
branch. The Phase 4 composite foreign key requires a reporting manager and report to share company
and branch, so cross-branch manager access is unsupported. Phase 4 child foreign keys also make a
branch change unsafe once the employee has retained branch-owned records. Only a pre-activity
branch correction is allowed after proving that no dependent row exists. Transfer of an employee
with retained history is deferred under approved decision `5A-D10`.

### Self, direct report, and delegation

Employee self scope is exact equality with the principal's linked `employee_id`. It does not use
email, name, employee number, an object path, or an ID supplied without a scoped join.

Manager team scope is one level. The target employee must currently satisfy all of these checks:

```text
employee.company_id = principal.company_id
employee.branch_id = principal.branch_id
employee.reporting_manager_id = principal.employee_id
```

The application must join that relationship in every team read and mutation. It must not cache a
list of report IDs across requests. After a committed `reporting_manager_id` change, a new statement
removes the report from the old manager and grants it to the new manager if all branch rules pass.
An in-flight mutation locks and rechecks the target relationship before changing data.

Leave delegation is narrower than manager scope. A delegate may read and decide the leave queue
that the named approver could decide only when the current trusted UAE business date is within the
inclusive `from_date` and `to_date`. The approver and delegate must have active application
accounts, profiles, and employee rows in the same company and branch. Under approved decision
`5A-D3`, the delegate may otherwise hold either the `manager` or `employee` role. The delegated queue
may read the minimum employee, leave type, balance, and probation fields needed for the decision.
Delegation grants no expense, appraisal, training, payroll, document, or general employee access.
It follows the approver's current direct reports, so a reporting-manager change takes effect for
the delegate too. A manager may read delegation records that name them for historical clarity, but
only a currently active record grants `L1` decision authority.

### Read projections

RLS limits rows. FastAPI response models limit columns. Managers receive only the direct-report
fields needed by the feature. Team responses exclude salary, bank details, government identifiers,
home address, personal contact data, and unrelated document or insurance data. Employees receive
their own approved profile projection. Safe employer context excludes private identity-provider
and audit fields.

## Role and system access

### Human roles

The only business roles remain `admin`, `manager`, and `employee`.

- Admins act within their database-derived company. Branch-owned operations also require the
  verified branch selection described above.
- Managers receive employee self-service plus the exact one-level team operations listed in the
  table catalogue.
- Employees receive personal reads and named self-service operations only.

Manager and employee principals are eligible only when the application account is active, the
profile and employee link are valid, `employees.active = true`, and `employment_status` is one of
`Active`, `Probation`, or `On Leave`. A mismatch fails closed. `Terminated`, inactive, missing, and
out-of-set employee states receive no self or team scope. The portal-role workflow uses the same
eligibility rule. Under approved decision `5A-D11`, demoting, disabling, or terminating a manager
with current direct reports must atomically reassign those reports to another eligible same-branch
manager or reject the change.

An unsupported operation is denied even when the SQL role has the underlying verb for another
approved path.

### Migration, seed, and jobs

`workloop_migration` remains the schema owner. It applies reviewed Alembic revisions and may perform
the exact data changes inside those revisions. It does not serve requests. Table ownership bypasses
ordinary RLS, so its credential remains outside FastAPI.

The seed remains a local or CI operation using the migration credential. It may insert, verify,
upsert, and remove only the deterministic fixture IDs on the 48 tables in the Phase 4E manifest.
Seed access is unsupported in a deployed application process. The six unseeded tables are
`employee_job_history`, `nafis_reports`, `compliance_overrides`, `leave_audit_log`,
`shift_assignments`, and `attendance_audit_log`.

There is no generic scheduled-job permission or shared job credential. The recommended design adds
one dedicated `workloop_expiry_processing` login, keeps it `NOBYPASSRLS`, and makes the database
login, rather than a caller-set context value, the job's authentication. Other scheduled jobs have
no login or grant until their own table, operation, scope, retry, and audit contract is approved.
Approved decision `5A-D15` adds a dedicated storage reconciler and durable operation table in the
later storage phase. Neither exists in Phase 5A.

Expiry processing runs one company and, where needed, one branch per transaction. It may read
companies, branches, active tenant-admin recipients, employees, employee documents, insurance
policies, employee insurance, certifications, and existing notification
deduplication keys. It may insert notifications. It may not change an expiry source, review state,
employee state, or existing notification. Notification read state belongs to the recipient.

Each alert is sent to every app user whose active account has exactly one `admin` profile in the
context company. No nominated-admin field is added, and employees do not receive expiry alerts from
this job. A branch sweep writes branch-owned alerts; tenant-only alerts use a null branch. Deduplication
includes each recipient.

The trusted Asia/Dubai business date and these source filters preserve the current bands:

- Active, non-terminated employee identity dates use 0 to 60 days and 14, 30, and 60-day keys.
- Probation uses status `Probation`, 0 to 14 days, and 7 and 14-day keys.
- Limited employee contracts use `employees.contract_end_date`, not append-only
  `employee_contracts`, with 0 to 60 days and 7, 14, 30, and 60-day keys.
- Verified clinical employee documents use 0 to 90 days and 14, 30, and 90-day keys. Other verified
  documents use 0 to 60 days and 14, 30, and 60-day keys.
- Active-employee insurance uses 0 to 60 days and 30 and 60-day keys.
- Verified active-employee certifications and professional licences use 0 to 60 days and 14, 30,
  and 60-day keys.
- Insurance-policy renewal uses 0 to 60 days and 30 and 60-day keys.

Null dates, expired dates, inactive or terminated employees, rejected or pending document and
certification records, and superseded contract-history rows produce no alert.

## PostgreSQL transaction context

FastAPI sets every key with transaction-local semantics inside the same explicit transaction that
runs protected SQL. A pooled connection must contain no request context after commit, rollback,
exception, cancellation, or return to the pool. Context values are never logged.

PostgreSQL stores custom settings as text. The policy implementation must parse them with
allowlisted, safe helpers that return SQL `NULL` for missing, blank, malformed, or out-of-set
values. A bad value must not raise an error that reveals policy internals. Any required `NULL`
causes the policy expression to evaluate false.

| Key | Logical type | Required for | Null behavior and consumer |
|---|---|---|---|
| `workloop.identity_issuer` | Nonempty text, at most 255 characters | Human bootstrap | Required with subject only for the `app_users` identity lookup. It identifies a candidate account but grants no business scope. |
| `workloop.identity_subject` | Nonempty opaque text, at most 255 characters | Human bootstrap | Required with issuer. Missing or malformed values expose no `app_users` row. |
| `workloop.app_user_id` | UUID | Every human transaction | Consumed by profile, recipient, actor, self, and separation-of-duties policies. Null denies human access. |
| `workloop.role` | `admin`, `manager`, or `employee` | Every human transaction | Must equal the current PostgreSQL profile. A token or browser role is ignored. Null or another value denies access. |
| `workloop.company_id` | UUID | Every human and expiry transaction; every scoped storage mutation | Consumed by every tenant or branch policy. Null never means all companies. The only null exception is the dedicated storage reconciler's `S1` queue scan and atomic claim, which can see no business table. Later updates and deletion require the claimed row's company and branch context. |
| `workloop.employee_id` | UUID | Manager and employee transactions | Must equal the profile link and employee company. Null is valid for admins and jobs, but self and manager policies then deny. |
| `workloop.branch_id` | UUID | Every branch-scoped operation | Must be the verified admin selection or linked employee branch. Null never means all branches. Tenant-only policy families do not consume this key. |
| `workloop.actor_kind` | `human` or `scheduled_job` | Every runtime or job transaction | Must agree with `current_user`. `workloop_runtime` accepts `human`; each approved dedicated job login accepts `scheduled_job`. Null denies. |
| `workloop.actor_key` | Allowlisted text | Job transactions | Null for humans. The dedicated expiry runner sets `expiry_processing`; proposed storage reconciliation uses `storage_reconciliation`. Policy also requires the matching dedicated `current_user`. The value labels an authenticated job but does not authenticate it. |
| `workloop.business_date` | Date | Delegation and expiry rules | FastAPI or the job runner derives the Asia/Dubai date from its trusted clock. Null denies time-bound access. |

The initial issuer and subject come only from the already verified access token. FastAPI resolves
the `app_users` and `user_profiles` rows, verifies active account status and role-link integrity,
then sets the remaining human keys from those rows. The same transaction rechecks that the profile
still matches the context before protected work.

The recommended implementation adds safe context-reader functions with fixed key names. It does
not add a generic helper that reads an arbitrary setting name. It revokes function execution from
`PUBLIC`, pins the search path, and grants only the required calls to `workloop_runtime` or the
dedicated expiry login.

## RLS policy families

Every target table will have RLS enabled. It will not use `FORCE ROW LEVEL SECURITY` because the
migration owner must apply migrations and the synthetic seed. `workloop_runtime` and the proposed
job role remain `NOBYPASSRLS` and do not own tables.

Policies are restrictive by default through absence. New policies use new names. No legacy
Supabase policy name, role, helper, `auth.*`, or `storage.*` reference returns.

Family codes below are predicate templates, not standalone policies that grant every SQL command.
For each table and database login, the later RLS subphase creates at most one deliberate permissive policy per
command. A `SELECT` policy has `USING`; `INSERT` has `WITH CHECK`; `UPDATE` has both; and `DELETE`
has `USING`. Each expression contains the required human-role or job-login gate and the exact OR of
the catalogue routes allowed for that command. A family listed on a table does not imply read or
write permission unless the matching catalogue cell allows that verb. This avoids accidental OR
composition between PostgreSQL permissive policies. SQL grants, policy command coverage, FastAPI
dependencies, and scoped repository statements must all agree.

| Code | Family | Rule |
|---|---|---|
| `B0` | Identity bootstrap | Select one active candidate from `app_users` by verified issuer and subject. No write. |
| `P0` | Current profile | Select the current profile. Admin role workflows may update only approved profile columns within the same tenant. |
| `T1` | Tenant admin | Admin row access requires row company equal to context company. Tenant-only operations do not infer a branch. |
| `B1` | Branch admin | Admin row access requires both company and verified branch equality. |
| `R1` | Staff reference read | Manager or employee may read safe reference rows for their linked company or branch, as the table requires. FastAPI restricts columns. |
| `E1` | Employee self | The row employee key equals the context employee, company, and branch. |
| `M1` | Direct report | The row employee currently reports directly to the manager employee in the same company and branch. |
| `L0` | Delegation record read | An active manager or employee may read retained delegation rows that name their employee as approver or delegate. It grants no delegated action. |
| `L1` | Leave delegate | An active same-branch delegate may use the approver's current `M1` scope for leave decision data only during the inclusive delegation dates. |
| `I1` | Self insurance reference | Staff may read the safe projection of a policy currently linked to their own `employee_insurance` row. It is not a branch-wide policy read. |
| `A1` | Appraisal-linked cycle read | Staff may read a cycle only through an appraisal visible under `E1` or `M1`. Closed cycles remain visible with historical appraisals. |
| `N1` | Notification recipient | A human may select and mark read only rows addressed to the context app user in the same company. |
| `H1` | Append-only history | Scoped select and trusted workflow insert. Ordinary update and delete are absent. Actor comes from context. |
| `W1` | Protected workflow | Direct table writes are absent or state-limited. The approved service transaction or retained function repeats scope and state checks. |
| `J1` | Expiry job | `current_user`, actor kind, actor key, company, branch, and read or insert allowlist must all match. |
| `O1` | Storage application outbox | Runtime insert, pre-call attempt reservation, status read, and immediate result update require context company, branch, and creator app user. No business endpoint returns the row. |
| `S1` | Storage reconciliation | Only `workloop_storage_reconciler` with actor kind `scheduled_job` and key `storage_reconciliation` may use null company context to discover claimable rows below eight attempts, expired count-eight leases, and purge-eligible successful rows. Null-context update may only claim rows with `attempt_count < 8`. Later terminalization and deletion require company and branch context copied from the discovered row. |

For nullable branch ownership, the table expression must partition the cases. On
`compliance_overrides`, the `T1` clause includes `branch_id IS NULL`; the `B1` clause includes
`branch_id IS NOT NULL` and equality to the verified branch. The clauses cannot expose a
branch-specific row through tenant scope.

The following nonstandard row shapes use explicit predicates:

- `companies.T1` compares `companies.id` with context company. Staff `R1` reaches only that same
  company through the resolved profile, not through a caller-supplied company ID.
- `app_users.B0` uses verified issuer and subject only for human bootstrap. `app_users.J1` selects
  only `id` and `status` where an existing `user_profiles` row binds the app user to context company
  with role `admin` and the account status is active. `user_profiles.J1` uses that same company and
  role predicate; it does not require an employee link.
- `assets.E1` requires an `asset_assignments` row for the asset with context employee, matching
  company and branch, and a null return date. The asset row has no employee-owner column, so scope
  is never inferred from an asset ID alone.
- `shift_swap_requests.E1` requires context employee to equal either `requesting_employee_id` or
  `target_employee_id`, with company and branch equality.
- `notifications.N1` always requires recipient app user and company equality. For manager and
  employee recipients, a business notification must also match their linked branch; a null-branch
  staff notification is denied until a tenant-wide staff type is separately approved. Under
  approved decision `5A-D13`, an admin inbox returns null-branch tenant notifications plus rows for the
  verified selected branch. `notifications.J1` requires context company and either a null branch
  for a tenant event or the current job branch. Insert checks use the same rule.
- `insurance_policies.I1` and `appraisal_cycles.A1` use the linked `EXISTS` joins defined above;
  neither falls back to a branch-wide staff predicate.

Human notification producers are allowlisted by type and related object: `leave_approved` and
`leave_rejected` require a visible employee-owned `leave_request`; `payslip_available` requires an
issued payslip for that recipient employee and payroll run; `roster_published` requires a published
roster containing that recipient employee in the named branch and month. The expiry job may produce
only `document_expiry`, `clinical_credential_expiry`, `insurance_expiry`, `probation_ending`,
`contract_expiry`, `cert_expiry`, `clinical_licence_expiry`, and `policy_renewal`, with the related
entity types listed by the source workflow. Unknown type and entity pairs are rejected. A title,
body, recipient ID, or related ID supplied by a caller never establishes scope.

## Field-level write rules

These rules apply before SQL. The database grant column records the maximum SQL capability, not a
permission for every caller or field.

| Field class | Rule |
|---|---|
| Role | A caller cannot change their own role. A tenant admin may assign `employee` or `manager` to an eligible employee in the same company through the portal-role workflow. Creating an admin profile or changing a profile's company remains provisioning-only. |
| Company | FastAPI derives `company_id`. Ordinary updates cannot change it. Moving data between companies is unsupported. |
| Branch | FastAPI derives `branch_id`. Ordinary updates cannot change it. Only a pre-activity correction with no dependent row is currently executable. Transfer with retained history awaits `5A-D10`; it must not rewrite historical child branches. |
| Employee ownership | Self-service creates use the principal employee. Team creates use a currently scoped direct report. Admin creates use the verified branch. An ordinary patch cannot change the owner employee. |
| Salary and bank | Only an admin may write employee salary, allowance, bank, WPS, and government payroll fields. Payroll snapshots come from the payroll workflow. Managers and employees cannot write them. |
| Approval status | Leave, expense, salary advance, regularisation, payroll, shift swap, document, certification, appraisal, overtime, incident closure, offboarding completion, and letter status fields change only through named workflows. Generic patch bodies reject them. |
| Payroll state | Run status, approval, WPS state, totals, entry ownership, payslip snapshots, repayment balance, and expense payment links are workflow-owned. `replace_payroll_entries` and `record_advance_repayment` keep their Phase 4 checks. |
| Document state | Employee document and certification submissions start in the pending state. Manager-created direct-report certifications also start pending. Admin-created documents or certifications are immediately verified with reviewer ID and time derived from context. Other submitters cannot set reviewer, review time, verified state, or rejection fields. Storage paths come from the storage service, not the browser. |
| Audit actors | FastAPI or a protected database function writes actors from trusted context. A request body cannot set an actor, actor kind, timestamp, company, branch, or audit event ID. |

Employee contact editing remains limited to `phone`, `personal_email`,
`emergency_contact_name`, and `emergency_contact_phone`. Training self-service cannot change
employee ownership, completion evidence belonging to an administrator, or protected review state.
Certification self-service always sets `pending_review`.

Under approved decision `5A-D18`, employee and manager-self training create forces employee ownership,
`status = 'planned'`, zero cost, empty score, null pass result, and `is_cme = false`. While still
planned, self update is limited to title, type, provider, start and end dates, duration, and notes.
The service may attach an uploaded evidence key, but that does not complete the record. Only an
admin or a manager acting on a current direct report may set cost, CME classification, completion
status, score, pass result, or accepted evidence. A manager cannot use team authority on their own
training row.

An admin document create forces `submitted_by = 'hr'`, `status = 'verified'`, and reviewer ID and
time from trusted context. An admin certification create likewise forces verified state and trusted
reviewer evidence. Employee document creates force `pending_verification`; employee and manager
certification creates force `pending_review`. A manager cannot verify their own submission for a
direct report. Only a later admin review can set verified or rejected state for pending rows.

An employee advance request always forces `status = 'pending'`, a null disbursement date, zero
monthly deduction, and zero outstanding balance until approval establishes the schedule. Employee
input cannot set status, schedule, balance, repayment, rejection, or settlement fields. The
existing admin-issued path creates an `active` advance only after the workflow validates and writes
the disbursement date, repayment month, monthly deduction, and outstanding balance atomically.

### Storage-backed operations

Object storage remains private and provider-neutral. FastAPI generates an opaque key from the
database-derived company, verified branch, authorized employee, object category, and a random
identifier. It never uses an identity-provider subject, email, browser path, or caller-supplied
employee ID as authority. Metadata authorization happens before upload or signing. A signed URL is
short-lived and grants no authorization for a later request.

| Object class | Supported operations and scope | Unsupported operations |
|---|---|---|
| Company or branch logo | This remains the `branches.logo_url` database field. Admin read and update require tenant ownership and, for an existing branch, the selected branch. No object-store operation is introduced in Phase 5A. | Staff write, public bucket access, and using the URL as scope. |
| Employee document | Admin may upload, sign, and delete for an employee in the selected branch. An employee may upload and sign their own document; manager access is unsupported. Delete records a durable storage operation with metadata removal, then reconciles object removal. | Employee delete or review, manager access, public URL, direct download, list, copy, and move. |
| Leave attachment | Employee may upload and sign an attachment for their own request. Admin may do so for a request in the selected branch. A manager or active delegate may sign only the attachment on a request currently visible in their leave queue. | Separate object delete, arbitrary team-folder access, list, copy, move, and using a path as request scope. Orphans are removed after request cancellation or failed submission. |
| Expense receipt | Employee may upload and sign for their own claim. Admin may upload and sign in the selected branch. A manager may sign only for a current direct-report claim in the expense queue. Claim deletion records a durable storage operation with metadata removal, then reconciles object removal. | Standalone object delete, cross-report access, public URL, list, copy, and move. |
| Training or certification evidence | Employee may upload and sign their own evidence. A manager may do so only for a current direct report under the matching training or certification operation. Admin may do so in the selected branch. An authorized row delete records a durable storage operation with metadata removal, then reconciles object removal. | A manager-owned path prefix, path-based ownership, unrelated document access, public URL, direct list, copy, and move. |

Every upload is size- and content-type-limited by its feature contract. The adapter returns only an
opaque metadata key to the service, never a reusable provider credential. The storage audit and
failure sequence is defined in the audit section below.

## Approval and separation of duties

- Leave request owners cannot make a discretionary decision on their own requests. From `Pending`,
  an eligible manager or active delegate may approve a current direct report: one-level becomes
  `Approved`, while two-level becomes `ManagerApproved`. A manager or delegate rejection becomes
  `ManagerRejected`. An admin may approve or reject `Pending` one-level requests directly and may
  make the final `Approved` or `Rejected` decision from `ManagerApproved`. An admin may cancel a
  future `Approved` request; an employee may cancel only their own `Pending` request. A delegate
  cannot decide their own request.
- Under approved decision `5A-D4`, an active leave type with `auto_approve = true` is approved in
  the same transaction as submission, including balance changes and audit insertion. This is a
  deterministic rule, not human self-approval. Because the Phase 4 approved-state constraint
  requires an app-user actor, the request and domain audit use the submitter's app-user ID as the
  initiator and set action `auto_approved_by_rule`, reason `leave_types.auto_approve`, and an
  explicit rule marker in the approval comment. That actor field does not claim a discretionary
  decision. A failed audit or balance write rolls back the request.
- Expense owners cannot approve or reject their own claims. A manager may approve `pending` to
  `manager_approved` or reject `pending` to `manager_rejected` for a current direct report. Manager
  pre-approval is not mandatory. An admin may approve `pending`, `manager_approved`,
  `manager_rejected`, or `rejected` to `approved`; may reject `pending` or `manager_approved` to
  `rejected`; and may mark `approved` as `paid` only through payroll. When a manager decision actor
  exists, the final admin actor must differ. An admin override of manager rejection is audited with
  a required reason.
- A payroll run creator or submitter cannot approve or reject that run. Recall belongs to the
  submitter or another tenant admin before approval. Generation requires an approved run and may
  not alter approval evidence.
- A manager cannot rate their own appraisal. A manager may rate a current direct report. An admin
  calibrator must differ from the recorded reviewer.
- Employees cannot approve their own regularisation, overtime, shift swap, document,
  certification, advance, offboarding, or letter request. Managers receive no implied approval
  power outside the leave, expense, appraisal, and training operations listed in this document.
- Admin profiles have no employee link. If a later design permits an admin employee link, every
  separation rule must compare the actor's employee identity before that change is approved.

The fixture set currently has one admin per tenant. Strict payroll submitter-versus-approver tests
need a second synthetic admin for each affected tenant. Expense and appraisal separation use the
existing manager and admin roles. The extra payroll fixture is not approved by this draft.

## HTTP authorization responses

| Case | Response |
|---|---|
| Missing, malformed, expired, or otherwise invalid bearer token | Existing generic `401 invalid_access_token` with `WWW-Authenticate: Bearer`. |
| Missing, disabled, pending, duplicate, or invalid application account | Existing generic `403 application_account_unavailable`. |
| Application-account database timeout or failure | Existing generic `503 application_account_lookup_unavailable`. |
| Missing admin branch selector | `400` with code `branch_required`. |
| Malformed branch selector | `422` with code `invalid_branch`. |
| Missing object or well-formed inaccessible object | `404` with code `resource_not_found` and message `Resource not found`. |
| Visible object but forbidden operation, field, state transition, or self-approval | `403` with code `operation_not_permitted` and message `Operation not permitted`. |
| State changed since the caller read it | `409` with a workflow-specific conflict code that reveals no other tenant data. |
| Collection request | Return only authorized rows. An empty authorized collection is `200` with an empty list. |
| Mixed-scope bulk request | Reject the whole request. Return `404 resource_not_found` if any member is missing or inaccessible, with no partial mutation. |

FastAPI must use one scoped statement where practical. It must not first fetch an object without
scope and then choose between 403 and 404. Logs may record the safe error code and correlation ID,
but not the guessed ID, another tenant's ownership, token claims, or context values.

## Operation and table catalogue

Codes in the three human columns are `R`, `C`, `U`, and `D`. `x` means the operation is unsupported
for that role. A qualified operation is supported only under the stated condition. `WF` names
stateful work that cannot use a generic patch. The grant column is the final SQL ceiling proposed
for the named table. `S`, `I`, `U`, and `D` mean `SELECT`, `INSERT`, `UPDATE`, and `DELETE` for
`workloop_runtime`. `X(function)` means execute only. A `job S` or `job I` entry is shorthand for
the column-level grant listed below, never a whole-table grant. Grants never replace RLS or
FastAPI checks.

| # | Table | Policy | Admin | Manager | Employee | Workflow and system operations | Required SQL grant |
|---:|---|---|---|---|---|---|---|
| 1 | `companies` | `T1,R1,J1` | `R,U`; `C,D x` | Safe employer `R`; `C,U,D x` | Safe employer `R`; `C,U,D x` | WF company settings. Migration only creates or removes a tenant. Expiry job verifies tenant context. | `S,U`; job `S` |
| 2 | `branches` | `T1,B1,R1,J1` | `R,C,U,D`, delete only with no active employee or retained reference | Own branch safe `R`; `C,U,D x` | Own branch safe `R`; `C,U,D x` | WF branch selection, logo, and guarded branch delete. Expiry job verifies branch context. | `S,I,U,D`; job `S` |
| 3 | `app_users` | `B0,J1` | `R,C,U,D x` through business API | `R,C,U,D x` | `R,C,U,D x` | Bootstrap `R` only. Provision, activate, disable, and delete are separate identity-lifecycle work. Expiry job reads active recipient identity only. | `S`; job `S` |
| 4 | `employees` | `B1,E1,M1,J1` | Branch `R,C,U`; `D x` | Self `R,U` contact only; direct-report projected `R`; team `C,U,D x` | Self `R,U` contact only; `C,D x` | WF archive, probation, job/salary change, pre-activity branch correction, and portal eligibility. Retained-history transfer awaits `5A-D10`. Hard delete unsupported. Expiry job reads expiry and recipient fields. | `S,I,U`; job `S` |
| 5 | `user_profiles` | `P0,T1,J1` | Same-tenant minimal `R`; role-only `U`; `C,D x` | Own minimal `R`; `C,U,D x` | Own minimal `R`; `C,U,D x` | WF portal role assignment. Provisioning creates links. Caller cannot change own role or company. Expiry job reads recipient links. | `S,UPDATE(role),X(is_scoped_active_app_user)`; job `S` |
| 6 | `employee_job_history` | `B1,H1` | Branch `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF appends job, salary, department, and status changes. Staff read is unsupported because the rows include salary history. | `S,I` |
| 7 | `departments` | `B1` | `R,C,U,D` | `R,C,U,D x` | `R,C,U,D x` | Delete requires no child department, head, staffing, or employee use. Staff receive department labels only inside an authorized employee projection, not direct table access. | `S,I,U,D` |
| 8 | `department_staffing_rules` | `B1` | `R,C,U,D` | `R,C,U,D x` | `R,C,U,D x` | WF roster staffing evaluation. | `S,I,U,D` |
| 9 | `payroll_runs` | `B1,W1` | `R,C,U`; unused draft `D` | `R,C,U,D x` | `R,C,U,D x` | WF create, repeat, submit, recall, approve, reject, generate, WPS and SIF state. Delete requires draft run and approval state with no approval log, payslip, retained use, or entries; one transaction may clear editable entries before deleting. Expiry and generic jobs have no access. | `S,I,U,D` |
| 10 | `payroll_entries` | `B1,W1` | `R`; direct `C,U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF replace draft entries only through retained `replace_payroll_entries`. Employee payroll detail is unsupported and superseded by payslips. | `S,X(replace_payroll_entries)` |
| 11 | `payslips` | `B1,E1,H1` | `R`; workflow `C`; `U,D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF issue immutable snapshot during payroll generation. | `S,I` |
| 12 | `payroll_approval_log` | `B1,H1` | `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF append submitted, recalled, approved, and rejected actions with trusted actor. | `S,I` |
| 13 | `nafis_reports` | `B1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF generate or replace a branch-period snapshot. No scheduled generation is approved. | `S,I,U` |
| 14 | `salary_advances` | `B1,E1,W1` | `R,C,U`; `D x` | Self `R,C`; own pending withdrawal `U`; `D x` | Self `R,C`; own pending withdrawal `U`; `D x` | WF employee request or pending withdrawal, admin approval/rejection/schedule/settlement, payroll repayment. | `S,I,U` |
| 15 | `advance_repayments` | `B1,E1,H1,W1` | `R`; direct `C,U,D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF insert only through retained `record_advance_repayment`; immutable afterward. | `S,X(record_advance_repayment)` |
| 16 | `expense_claims` | `B1,E1,M1,W1` | `R,U`; `D` only `pending`, `rejected`, or `manager_rejected`; `C x` | Self `R,C`; direct-report `R`; decision `U`; `D x` | Self `R,C`; own `pending`, `rejected`, or `manager_rejected` `D`; ordinary `U x` | WF submit, manager decision, admin final decision, reject, mark paid, and guarded delete. | `S,I,U,D` |
| 17 | `compliance_overrides` | `T1,B1,H1` | Tenant or branch `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF appends a reasoned tenant-wide payroll SIF or branch roster publication override. A null branch means tenant-wide, not unscoped. | `S,I` |
| 18 | `leave_settings` | `B1,R1` | `R,C,U`; `D x` | Branch `R`; `C,U,D x` | Branch `R`; `C,U,D x` | WF configure approval chain, weekends, carry-forward, and Ramadan dates. | `S,I,U` |
| 19 | `leave_types` | `B1,R1` | `R,C,U`; hard `D x` | Branch active `R`; `C,U,D x` | Branch active `R`; `C,U,D x` | WF soft deactivate and seed approved defaults. Cross-tenant read unsupported. | `S,I,U` |
| 20 | `public_holidays` | `B1,R1` | `R,C`; future unused `U,D` | Branch `R`; `C,U,D x` | Branch `R`; `C,U,D x` | WF seed a named year within the verified branch. Past or leave/attendance-used dates are retained and immutable. | `S,I,U,D` |
| 21 | `leave_requests` | `B1,E1,M1,L1,W1` | Branch `R,C`; decision/cancel `U`; `D x` | Self `R,C`; team/delegated `R`; decision/cancel `U`; `D x` | Self `R,C`; pending cancel `U`; `D x` | WF validate and submit, cancel, manager/delegate decision, admin final decision, and balance mutation. | `S,I,U,X(can_act_for_delegated_leave)` |
| 22 | `leave_audit_log` | `B1,H1` | Scoped `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF append every leave transition with trusted actor. Staff receive approved request status fields, not direct audit-log rows. | `S,I` |
| 23 | `leave_balances` | `B1,E1,M1,L1,W1` | `R,C,U`; `D x` | Self and minimum team/delegated `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF initialize, recalculate, reserve, release, and consume days. | `S,I,U,X(can_act_for_delegated_leave)` |
| 24 | `leave_approval_delegates` | `B1,L0,L1` | `R,C`; future-not-started `U,D` | Rows naming self as approver or delegate `R`; `C,U,D x` | Rows naming self as approver or delegate `R`; `C,U,D x` | `L0` supplies retained record visibility. Active and expired rows are immutable history. WF `L1` grants active-date leave authority only. | `S,I,U,D` |
| 25 | `attendance_settings` | `B1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF configure and consume attendance rules server-side. Biometric API key is admin-only and never returned to staff. | `S,I,U` |
| 26 | `shifts` | `B1,R1` | `R,C,U`; hard `D x` | Own branch active `R`; `C,U,D x` | Own branch active `R`; `C,U,D x` | WF soft deactivate. Global authenticated read is unsupported. | `S,I,U` |
| 27 | `shift_assignments` | `B1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF locked non-overlap assignment and end-date change. Staff schedule views use published `roster_assignments`, not this admin history. | `S,I,U` |
| 28 | `clock_events` | `B1,E1,H1` | `R`; manual/system `C`; `U,D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF append manual or biometric events. Corrections supersede rather than rewrite. Expiry job has no access. | `S,I` |
| 29 | `attendance_records` | `B1,E1,W1` | `R,C,U`; `D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF compute/upsert, resolve, approve overtime, apply correction, and close period. | `S,I,U` |
| 30 | `attendance_periods` | `B1,W1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF validate unresolved items and close a branch period atomically. | `S,I,U` |
| 31 | `regularisation_requests` | `B1,E1,W1` | `R`; decision `U`; `C,D x` | Self `R,C`; `U,D x` | Self `R,C`; `U,D x` | WF submit, approve with attendance correction, or reject. | `S,I,U` |
| 32 | `attendance_audit_log` | `B1,H1` | Scoped `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF append attendance corrections, resolutions, overtime, and period effects. Staff audit-log read is unsupported. | `S,I` |
| 33 | `roster_assignments` | `B1,E1,W1` | `R,C,U`; unpublished unused `D` | Own published `R`; `C,U,D x` | Own published `R`; `C,U,D x` | WF draft edit, delete only when `published = false` with no retained workflow use, publish, and retained atomic swap. Published rows are immutable except the protected swap. | `S,I,U,D,X(admin_execute_shift_swap)` |
| 34 | `shift_swap_requests` | `B1,E1,W1` | `R`; reject/cancel `U`; direct approval `U x`; `C,D x` | Participant `R,C`; own pending cancel `U`; `D x` | Participant `R,C`; own pending cancel `U`; `D x` | WF request, cancel, reject, and approve through retained `admin_execute_shift_swap`. | `S,I,U,X(admin_execute_shift_swap)` |
| 35 | `biometric_mappings` | `B1` | `R,C,U,D` | `R,C,U,D x` | `R,C,U,D x` | WF import validates mapped badge and deduplicates clock events. | `S,I,U,D` |
| 36 | `employee_documents` | `B1,E1,W1,J1` | `R,C,U`; pending or rejected `D` with storage reconciliation; create is trusted verified | Self `R,C` pending only; review and `D x` | Self `R,C` pending only; review and `D x` | WF upload metadata, sign, admin-create verified, employee-create pending, verify, reject, and guarded delete. Verified rows are retained. Expiry job `R`. File bytes stay outside PostgreSQL. | `S,I,U,D`; job `S` |
| 37 | `insurance_policies` | `B1,I1,J1` | `R,C,U,D` | Own-linked policy safe `R`; `C,U,D x` | Own-linked policy safe `R`; `C,U,D x` | WF policy maintenance. `I1` prevents branch-wide staff policy reads. Expiry job `R`. | `S,I,U,D`; job `S` |
| 38 | `employee_insurance` | `B1,E1,J1` | `R,C,U`; `D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF assign or replace current employee coverage. Expiry job `R`. | `S,I,U`; job `S` |
| 39 | `insurance_dependants` | `B1` | `R,C,U,D` | `R,C,U,D x` | `R,C,U,D x` | Direct staff access is unsupported. No expiry job exists because the table has no expiry field. | `S,I,U,D` |
| 40 | `notifications` | `N1,W1,J1` | Recipient `R,U`; workflow `C`; `D x` | Recipient `R,U`; workflow `C`; `D x` | Recipient `R,U`; workflow `C`; `D x` | WF creates or deduplicates a human notification only through proposed `create_workflow_notification`, which derives the recipient. Expiry job reads dedup keys and inserts. | `S,U,X(create_workflow_notification)`; job `S,I` |
| 41 | `employee_contracts` | `B1,H1` | `R`; workflow `C`; `U,D x` | `R,C,U,D x` | `R,C,U,D x` | WF append new, renewed, converted, or not-renewed history. Staff contract-history read is unsupported. Expiry processing uses the current field on `employees`, not append-only contract history. | `S,I` |
| 42 | `offboarding_checklists` | `B1,W1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF initialize, visa state change, and completion after every required task. | `S,I,U` |
| 43 | `offboarding_tasks` | `B1,W1` | `R,C,U,D` for custom uncompleted task; retained completed task `D x` | `R,C,U,D x` | `R,C,U,D x` | WF toggle completion with trusted actor and update checklist eligibility. | `S,I,U,D` |
| 44 | `offboarding_task_templates` | `B1` | `R`; `C,U,D x` | `R,C,U,D x` | `R,C,U,D x` | Business mutation unsupported. Migration or seed supplies templates. | `S` |
| 45 | `assets` | `B1,E1,W1` | `R,C,U,D`, delete only when never assigned and not retained | Self-assigned `R`; `C,U,D x` | Self-assigned `R`; `C,U,D x` | WF assign, return, state transition, and guarded delete. | `S,I,U,D` |
| 46 | `asset_assignments` | `B1,E1,H1,W1` | `R`; workflow `C,U`; `D x` | Self `R`; `C,U,D x` | Self `R`; `C,U,D x` | WF append assignment and close it on return. Assignment history is retained. | `S,I,U` |
| 47 | `training_records` | `B1,E1,M1,W1` | `R,C,U`; planned-only `D` | Self `R,C,U` limited fields; `D x`. Direct-report `R,C,U`; planned-only `D` | Self `R,C,U` limited fields; `D x` | WF self-enrol, direct-report maintenance, trusted completion, and certificate metadata under `5A-D18`. Non-planned rows are retained. Expiry processing does not use this table. | `S,I,U,D` |
| 48 | `certifications` | `B1,E1,M1,W1,J1` | `R,C,U`; pending or rejected `D`; create is trusted verified | Self `R,C,U`; `D x`. Direct-report `R,C,U`; pending or rejected `D`, pending create and no admin review fields | Self `R,C,U`; pending create; `D x` | WF employee or manager pending submission, direct-report maintenance, admin-create verified, admin verify/reject, guarded delete, and file signing. Verified rows are retained. Expiry job `R`. | `S,I,U,D`; job `S` |
| 49 | `appraisal_cycles` | `B1,A1,W1` | `R,C,U`; guarded draft `D` | Cycle linked to a visible direct-report appraisal `R`; `C,U,D x` | Cycle linked to own appraisal `R`; `C,U,D x` | `A1` includes closed historical cycles. WF activate, close, and purge an unused draft cycle. | `S,I,U,D` |
| 50 | `appraisals` | `B1,E1,M1,W1` | `R,C,U`; `D x` | Self `R`; direct-report `R,U`; `C,D x` | Self `R`; `C,U,D x` | WF generate, review, calculate rating, calibrate. Hard delete unsupported after Phase 4 retention decision. | `S,I,U` |
| 51 | `appraisal_sections` | `B1,E1,M1,W1` | `R,C,U`; direct `D x` | Self `R`; direct-report `R,U`; `C,D x` | Self `R`; `C,U,D x` | WF seed sections and rate. Runtime receives no section delete grant or policy. A draft cycle can be deleted only when no appraisal exists, so no section can exist under that cycle. | `S,I,U` |
| 52 | `cme_requirements` | `B1` | `R,C,U,D` | `R,C,U,D x` | `R,C,U,D x` | Training reads combine requirements with achieved CME hours. | `S,I,U,D` |
| 53 | `incident_reports` | `B1,H1,W1` | `R,C,U`; `D x` | `R,C,U,D x` | `R,C,U,D x` | WF investigate and close with trusted actor. Hard delete is unsupported because reports become clinical history. | `S,I,U` |
| 54 | `letter_requests` | `B1,E1,W1` | `R`; complete/reject `U`; `C,D x` | Self `R,C`; `U,D x` | Self `R,C`; `U,D x` | WF submit letter/custom request, complete, reject, and print from an authorized response. | `S,I,U` |

The 54 numbered rows are the complete existing table set. Each table appears once.

## Grant rules

- `workloop_runtime` receives only the table verbs and any column-specific grant shown above. It never
  receives `TRUNCATE`, `REFERENCES`, `TRIGGER`, grant option, schema `CREATE`, object ownership, role
  membership, or `BYPASSRLS`.
- A workflow that needs a verb not granted directly must use its named protected function. The
  function owner is `workloop_migration`, its search path is pinned, `PUBLIC` has no execute grant,
  and the function repeats company, branch, role, state, and actor checks.
- `replace_payroll_entries`, `record_advance_repayment`, and `admin_execute_shift_swap` retain their
  Phase 4 execute grants. Their application checks become stricter under this matrix.
- A table `DELETE` grant exists only where the catalogue names a hard-delete operation. RLS and the
  scoped statement must both enforce its tenant, branch, owner, and state rule. Finalized or
  historical rows stay retained.
- `workloop_expiry_processing` receives only the column grants below. It cannot execute any human
  business function.
- Migration and seed do not receive grants through the runtime roles. Their existing owner path is
  separate and unavailable to the web or job containers.

### Expiry-processing column grants

These are the complete grants to `workloop_expiry_processing`. Columns omitted here remain
unreadable even when RLS would admit the row.

| Table | Exact job grant |
|---|---|
| `companies` | `SELECT(id)` |
| `branches` | `SELECT(id,company_id)` |
| `app_users` | `SELECT(id,status)` |
| `user_profiles` | `SELECT(app_user_id,company_id,employee_id,role)` |
| `employees` | `SELECT(id,company_id,branch_id,name,active,employment_status,probation_end_date,contract_type,contract_end_date,visa_expiry,passport_expiry,emirates_id_expiry,labour_card_expiry,licence_authority,licence_expiry)` |
| `employee_documents` | `SELECT(id,company_id,branch_id,employee_id,document_type,expiry_date,status)` |
| `insurance_policies` | `SELECT(id,company_id,branch_id,insurer_name,tier_name,renewal_date)` |
| `employee_insurance` | `SELECT(id,company_id,branch_id,employee_id,policy_id,expiry_date,tier_name)` |
| `certifications` | `SELECT(id,company_id,branch_id,employee_id,certification_name,issuing_body,expiry_date,status)` |
| `notifications` | `SELECT(company_id,branch_id,recipient_app_user_id,type,related_entity_type,related_entity_id)` and `INSERT(company_id,branch_id,created_by_app_user_id,recipient_app_user_id,type,title,body,related_entity_type,related_entity_id)` |

The login has no access to identity issuer or subject, Keycloak roles, salary or bank fields,
government ID values, document or certificate paths, insurance member or card numbers, notes, or
notification bodies already stored. It can read only the application `user_profiles.role` column
needed to select tenant admins. The job sets `created_by_app_user_id` to null. Database defaults
create the notification ID and timestamps; the job cannot supply or update read state.

### Retained function boundary

All three retained functions are `SECURITY DEFINER`, so their `current_user` is the function owner
and their owner bypasses RLS. Each function must reject unless `session_user = 'workloop_runtime'`,
context actor kind is `human`, the context app-user has active account status and resolves to
exactly one valid same-company profile with role `admin`, and company plus verified
branch context are present. None may trust token claims, browser fields, email, or an unscoped
identifier.

Runtime connections log in directly as `workloop_runtime`; that role receives no membership that
permits `SET ROLE`. The functions therefore use `session_user` only for invoker authentication.
Ordinary RLS policies and the dedicated expiry login still use `current_user`, because no
`SECURITY DEFINER` identity switch applies there.

- `replace_payroll_entries` locks the run, proves its company and branch equal context, requires
  draft run and approval state, validates every employee against that same branch, and replaces
  entries atomically. It accepts no actor argument.
- `record_advance_repayment` locks the advance and payroll run, proves both share context company
  and branch, validates the advance state, remaining balance, amount, and idempotency key, and
  records the repayment and balance change atomically. It accepts no actor argument.
- `admin_execute_shift_swap` proves the request, both employees, and both roster rows share context
  company and branch, locks them, requires an eligible pending swap, and swaps atomically. Until a
  later revision removes `p_actor_app_user_id`, the function requires that argument to equal
  `workloop.app_user_id`; it then derives the audit actor from context.

Decision `5A-D17` proposes four additional fixed-purpose `SECURITY DEFINER` helpers. All require
`session_user = 'workloop_runtime'`, a pinned search path, valid context, and revoked `PUBLIC`
execution. Their business-role gates differ as stated below; they do not inherit the retained
functions' admin-only gate.

- `is_scoped_active_app_user(p_app_user_id uuid) returns boolean` returns true only when the target
  account is active and its single valid profile belongs to context company. It returns false for
  missing or inaccessible IDs. The admin portal-role workflow may execute it; no endpoint returns
  identity issuer, subject, or raw account status.
- `create_workflow_notification(p_type text, p_related_entity_id text) returns uuid` accepts only
  the allowlisted producer pairs. It loads the source object under context, proves admin, direct
  manager, active delegate, or other named workflow authority, derives employee and active app-user
  recipient through `user_profiles`, constructs approved content, and inserts the correctly scoped
  notification. It accepts no recipient, company, branch, title, or body argument.
- `can_act_for_delegated_leave(p_target_employee_id uuid) returns boolean` returns true only when
  context employee is an eligible same-branch delegate on the trusted business date, the named
  approver is eligible, and the target employee currently reports directly to that approver in
  context company and branch. It is consumed only by `L1` policies on leave requests and minimum
  leave-balance reads. It returns false for every missing, malformed, expired, or inaccessible
  relationship and exposes no employee row.
- `append_audit_event(p_action text,p_entity_type text,p_entity_id uuid,p_changed_fields text[],p_reason text,p_metadata jsonb) returns uuid` accepts only an allowlisted action for the caller's current authorized workflow, derives company, verified or null branch, actor and initiator from context, validates safe metadata keys, and inserts one immutable event. Admin, manager, employee, and active delegate callers pass only when the named source workflow permits them. It accepts no actor, company, branch, timestamp, or system key.

`workloop_runtime` receives execute on these helpers only if `5A-D17` is approved. It receives no
direct notification insert grant and no extra `app_users` row policy.

A failure in any identity, scope, state, amount, or actor check aborts without mutation. Direct
table grants remain revoked for the protected operations.

## Audit design

The recommended design uses both existing domain history and one new shared append-only table.

The existing `employee_job_history`, `payroll_approval_log`, `leave_audit_log`,
`attendance_audit_log`, payslips, advance repayments, compliance overrides, and employee contracts
remain append-only domain history. Assignment records become immutable after their allowed close,
return, publication, or finalization transition. None of these retained rows can be deleted through
the runtime role.

The proposed `audit_events` table records sensitive operations that have no complete domain audit:
role and employment-access changes, pre-activity branch corrections, advance decisions, expense
decisions and payment, regularisation decisions, payroll lifecycle and WPS changes, roster
publication, shift-swap decisions, document and certification review or deletion, appraisal review
and calibration, incident closure, offboarding completion, letter completion or rejection,
expiry-processing writes, and protected storage actions. Its proposed fields are:

```text
id uuid primary key
company_id uuid not null
branch_id uuid null
occurred_at timestamptz not null
actor_kind text not null
actor_app_user_id uuid null
system_actor_key text null
initiated_by_app_user_id uuid null
action text not null
entity_type text not null
entity_id uuid not null
changed_fields text[] not null
reason text not null
metadata jsonb not null
```

The proposed Phase 5G schema includes an actor-kind check for `human`, `scheduled_job`, `migration`,
`seed`, and `system_rule`; an exactly-one-primary-actor check; company, optional branch, human actor,
and initiator foreign keys; and nonblank action, entity type, reason, and system-key checks. A human
actor requires `actor_app_user_id` and no system key. A nonhuman actor requires a fixed system key
and no actor app user. `initiated_by_app_user_id` is optional and records the human who triggered a
rule-driven action. Human actor and initiator references use `(app_user_id,company_id)` to bind them
to the event company. Company, branch, actor, and initiator references use `ON DELETE RESTRICT`.
This retains provenance and means a branch or profile referenced by a retained event cannot later
be hard-deleted. Branch create and delete events are tenant-scoped with `branch_id` null and put the
created or deleted branch UUID in `entity_id`; this records the lifecycle without making creation
itself block deletion. A branch-scoped event from later use still blocks hard deletion.

FastAPI supplies no raw before/after record. `changed_fields` and `metadata` use per-action
allowlists so salary, bank, government IDs, document paths, tokens, and file URLs are not copied
into a general log. Only admins may read the table: a tenant-wide event requires tenant scope and
`branch_id IS NULL`; a branch event requires the verified branch. Managers and employees receive
no direct audit-event access. The future policy disposition is `T1(null-only),B1(non-null),H1,W1,J1`:
admin `SELECT` uses the two partitioned scopes, human insert uses the protected writer, and expiry
insert uses `J1`. No runtime or job actor may update or delete one.

`workloop_runtime` receives `SELECT` and
`EXECUTE(append_audit_event)`, but no direct insert, update, or delete. The admin audit repository
has a selector-free tenant-event query restricted to null branch and a branch query that requires
the verified selector. `workloop_expiry_processing` receives only
`INSERT(company_id,branch_id,actor_kind,system_actor_key,action,entity_type,entity_id,changed_fields,reason,metadata)`.
Database defaults supply ID and occurrence time; its `J1` check forces actor kind `scheduled_job`,
key `expiry_processing`, context company, and a null or matching branch. The storage reconciler has
no audit-table grant. Migration and seed use the separate owner path and must label any business
data event with their fixed system actor.

Every database-backed event insert occurs in the same transaction as its protected mutation. If
the audit insert fails, the mutation rolls back. The retained `SECURITY DEFINER` functions write
their events before commit.

Storage cannot share a PostgreSQL transaction. Under approved decision `5A-D15`, a later storage phase
adds a private `storage_operations` outbox with these fields:

```text
id uuid primary key
company_id uuid not null
branch_id uuid not null
employee_id uuid null
created_by_app_user_id uuid not null
entity_type text not null
entity_id uuid not null
operation text not null
object_key text not null
status text not null
attempt_count integer not null
last_error_code text not null
next_attempt_at timestamptz null
claimed_at timestamptz null
lease_expires_at timestamptz null
completed_at timestamptz null
created_at timestamptz not null
updated_at timestamptz not null
```

The table has scoped restrictive company, branch, employee, and creator-profile foreign keys;
checks for `upload` or `delete` and `pending`/`claimed`/`succeeded`/`failed`/`reconciled`; a
nonnegative attempt count; and lease and terminal timestamp consistency. Defaults are `pending`,
zero attempts, empty error code, null retry, claim, lease, and completion times, and database
timestamps for create and update. It is not human-readable through an API.

`O1` is the application outbox family. It requires `session_user = current_user =
'workloop_runtime'`, actor kind `human`, creator app user equal to context app user, and company and
branch equality. `workloop_runtime` receives
`INSERT(company_id,branch_id,employee_id,created_by_app_user_id,entity_type,entity_id,operation,object_key)`,
`SELECT(id,company_id,branch_id,status,created_by_app_user_id)`, and
`UPDATE(status,attempt_count,last_error_code,next_attempt_at,claimed_at,lease_expires_at,completed_at,updated_at)`.
The repository never returns the row through a business API. Its command-specific `O1` policies
allow insert, a scoped pre-call reservation from pending count zero to claimed count one with a
15-minute lease, and the expected row's immediate success or failure transition only. The provider
request deadline must remain shorter than the lease.

The dedicated reconciler receives `SELECT` on every listed outbox column,
`UPDATE(status,attempt_count,last_error_code,next_attempt_at,claimed_at,lease_expires_at,completed_at,updated_at)`,
and guarded `DELETE`. It cannot read any of the 54 business tables or `audit_events`.

`S1` gives null-company `SELECT` visibility only to three queue classes under the dedicated login:
pending, retryable failed, or expired-lease rows below eight attempts; expired leases at count eight
that need terminalization; and `succeeded` or `reconciled` rows at least 90 days past
`completed_at`. Null-context `UPDATE` may atomically claim only the first class with
`FOR UPDATE SKIP LOCKED` and `attempt_count < 8`. Every claim increments the count before a provider
call, stamps `claimed_at`, and creates a 15-minute lease. After discovering one row, the reconciler
starts a new transaction with company and branch context copied from that row. Later update and
delete policies require those values. An expired lease at count eight cannot be reclaimed. The
reconciler uses copied scope to mark it terminal `failed`, clear retry and lease fields, and emit
the safe alert without making a provider call. Purge deletion also uses copied scope and requires
the approved successful status and 90-day age. No outbox row receives more than eight provider
attempts. Attempt one is reserved by `O1` and then made immediately. Failures one through seven
set `next_attempt_at` to 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours, 24 hours, and 72 hours
later. Failure eight keeps status `failed`, sets `next_attempt_at = NULL`, clears the lease, and
ends automatic claiming. A safe operational alert contains the operation UUID and error code, never
the object key. Delete rows may retry the provider call under this schedule. Upload rows never retry
bytes: if the provider object exists without domain metadata, the reconciler removes the orphan; if
no object exists, it marks the operation reconciled so the user can upload again. Successful and
reconciled outbox rows are operational records, not the audit trail, and may be deleted 90 days
after `completed_at`. A terminal failed row remains until an approved operator procedure resolves
it. Manual requeue needs separate approval. The safe event in `audit_events` is not purged.

An upload first commits the outbox row for a pre-generated metadata UUID and object key, reserves
attempt one under `O1`, calls the provider, then commits domain metadata, outbox success, and the
safe audit event. A delete commits domain metadata removal, the outbox row containing the former
object key, and the safe audit event, reserves attempt one, then calls the provider and marks the
outbox row succeeded. Provider or database failure leaves a durable counted reservation for retry
or orphan removal. The general audit event stores the operation UUID, not the object key.
Signing-only reads record no token, URL, or path in either audit surface.

There is no automated audit purge in Phase 5. Synthetic development audit data may be removed with
its isolated environment. Before real data is allowed, the legal and security owners must approve
retention periods, legal-hold behavior, archive format, restore tests, and deletion authority.
Until then, production use remains blocked and audit records are retained.

## Fixture authorization controls

`A` means a FastAPI dependency, repository, field, workflow, or HTTP test. `R` means a direct
`workloop_runtime` RLS and grant test with transaction-local context. `S` means a later storage
authorization test. Every denied mutation also compares row counts and hashes before and after.

| # | Fixture control | Test layer | Required proof |
|---:|---|---|---|
| 1 | `horizon-admin.cedar-employee` | `A+R` | Read returns no row; update and delete affect zero rows. |
| 2 | `horizon-admin.cedar-payroll` | `A+R` | Run and entries are absent under Horizon context. |
| 3 | `horizon-admin.replace-cedar-payroll` | `A+R` | Application and retained function reject; entries remain unchanged. |
| 4 | `horizon-admin.repay-cedar-advance` | `A+R` | Application and retained function reject; balance and repayment count remain unchanged. |
| 5 | `horizon-admin.approve-cedar-swap` | `A+R` | Application and retained function reject; both rosters and swap state remain unchanged. |
| 6 | `aisha.approve-omar-report-leave` | `A+R` | Cross-branch, non-report, and non-delegate decision is absent or denied. |
| 7 | `aisha.act-on-priya-report-expense` | `A+R` | Cross-tenant manager queue and mutation deny with unchanged claim. |
| 8 | `aisha.rate-leila-or-cedar-appraisal` | `A+R` | Cross-branch and cross-tenant section and parent mutations affect zero rows. |
| 9 | `ravi.other-employee-records` | `A+R` | Payslip, attendance, document, advance, expense, and appraisal reads reveal no peer row. |
| 10 | `ravi.other-employee-storage-folder` | `A+S` | Metadata authorization and object signing reject Maria's path. Storage work remains later scope. |
| 11 | `ravi.delete-approved-expense` | `A+R` | State guard denies; claim and receipt metadata remain unchanged. |
| 12 | `ravi.cancel-active-or-settled-advance` | `A+R` | State guard denies both cases and preserves balances. |
| 13 | `ravi.request-cedar-swap` | `A+R` | Target employee lookup does not reveal Cedar and no request appears. |
| 14 | `dubai-view.abu-dhabi-core` | `A+R` | Employee, payroll, roster, swap, and incident branch reads are empty. |
| 15 | `dubai-view.abu-dhabi-supporting` | `A+R` | Leave, expense, asset, training, appraisal, department, and attendance branch reads are empty. |
| 16 | `leila.explicit-abu-dhabi-company-resolution` | `A+R` | Employer and branch come from Leila's database link, not the first company or a browser field. |
| 17 | `caller.expired-signed-url` | `A+S` | FastAPI refuses a new authorization after expiry and the storage provider rejects the old URL. |
| 18 | `horizon-user.cedar-object-path` | `A+S` | Metadata scope blocks signing before the provider receives a request. |
| 19 | `aisha.manager-reassignment` | `A+R` | After commit, Aisha loses the report immediately; only the new valid same-branch manager gains it. |

## Legacy RLS reconciliation

Each semicolon-delimited policy name below is one legacy policy identity. The Phase 4 source chain
and `Replace in Phase 5` or `Omit superseded` classification remain authoritative. The final column
gives each identity one Phase 5 disposition. Replacement means a new policy family supplies the
approved capability under a new name. Omission means the legacy policy stays absent.

### Root and core identities

| Table | Legacy policy name | Phase 5 disposition |
|---|---|---|
| `companies` | `Users can manage their own company` | Replace with `T1` admin and `R1` safe context read. |
| `employees` | `Users can manage their own employees` | Replace with `B1,E1,M1`. |
| `employee_job_history` | `Users can manage their own job history` | Replace with admin-only `B1,H1`; broad staff access stays absent. |
| `payroll_runs` | `Users can manage their own payroll runs` | Replace with `B1,W1`. |
| `payroll_entries` | `Users can manage their own payroll entries` | Replace with `B1,W1`. |
| `user_profiles` | `user_profiles: read own` | Replace with `P0`. |
| `user_profiles` | `user_profiles: insert own` | Omit. Provisioning creates profiles; self-insert stays unsupported. |
| `employees` | `employees: read own via auth_user_id` | Replace with `E1`; no Auth UUID column returns. |
| `leave_types` | `employees: read leave types` | Replace with branch `R1`. |
| `public_holidays` | `employees: read public holidays` | Replace with branch `R1`. |
| `leave_settings` | `employees: read leave settings` | Replace with branch `R1`. |
| `leave_requests` | `employees: read own leave requests` | Replace with `E1`. |
| `leave_balances` | `employees: read own leave balances` | Replace with `E1`. |
| `payroll_entries` | `employees: read own payroll entries` | Omit. Employee payroll detail is superseded by immutable payslip responses. |
| `payroll_runs` | `employees: read payroll runs for own entries` | Omit. Employee run access is superseded by payslip responses. |
| `attendance_records` | `employees: read own attendance records` | Replace with `E1`. |
| `clock_events` | `employees: read own clock events` | Replace with `E1`. |
| `regularisation_requests` | `employees: read own regularisation requests` | Replace with `E1`. |
| `leave_settings` | `Users manage their own leave settings` | Replace with `B1,R1`. |
| `leave_types` | `Users manage their own leave types` | Replace with `B1,R1`. |
| `public_holidays` | `Users manage their own public holidays` | Replace with `B1,R1`. |
| `leave_requests` | `Users manage their own leave requests` | Replace with `B1,E1,M1,L1,W1`. |
| `leave_audit_log` | `Users view their own leave audit log` | Replace with admin-only `B1,H1`; direct staff audit-log access stays absent. |
| `leave_balances` | `Users manage their own leave balances` | Replace with `B1,E1,M1,L1,W1`. |
| `attendance_settings` | `Users manage their own attendance settings` | Replace with admin-only `B1`. |
| `shifts` | `Users manage their own shifts` | Replace with `B1,R1`. |
| `shift_assignments` | `Users manage their own shift assignments` | Replace with admin-only `B1`; staff schedules use published rosters. |
| `clock_events` | `Users manage their own clock events` | Replace with `B1,E1,H1`. |
| `attendance_records` | `Users manage their own attendance records` | Replace with `B1,E1,W1`. |
| `attendance_periods` | `Users manage their own attendance periods` | Replace with `B1,W1`. |
| `regularisation_requests` | `Users manage their own regularisation requests` | Replace with `B1,E1,W1`. |
| `attendance_audit_log` | `Users view their own attendance audit log` | Replace with admin-only `B1,H1`; direct staff audit-log access stays absent. |
| `companies` | `employees: read own company` | Replace with `R1` using profile and employee scope. |
| `payslips` | `payslips: admin read own` | Omit as a legacy identity; `B1` supplies the capability. |
| `payslips` | `payslips: employee read own` | Replace with `E1`. |
| `payslips` | `payslips: admin insert` | Omit. The payroll finalization workflow inserts under `H1`. |
| `payslips` | `payslips: admin update` | Omit. Issued snapshots are immutable. |

### Numbered feature identities

| Table | Legacy policy names | Phase 5 disposition for each named identity |
|---|---|---|
| `nafis_reports` | `nafis_reports_owner` | Replace with `B1`. |
| `employee_documents` | `employee_documents_admin`; `employee_documents_self_read`; `employee_documents_self_update_pending` | Replace with `B1`; replace with `E1`; omit broad self-update and use submission workflow. |
| `insurance_policies` | `insurance_policies_admin` | Replace with admin `B1`, self-linked `I1`, and expiry `J1`. |
| `employee_insurance` | `employee_insurance_admin`; `employee_insurance_self` | Replace with `B1`; replace with `E1`. |
| `insurance_dependants` | `insurance_dependants_admin` | Replace with admin-only `B1`; direct staff access stays absent. |
| `notifications` | `notifications_select`; `notifications_insert`; `notifications_update`; `notifications_delete` | Replace select with `N1`; replace insert with trusted workflow and `J1`; replace update with recipient read-state `N1`; omit delete. |
| `salary_advances` | `salary_advances_admin`; `salary_advances_employee_read` | Replace with `B1,W1`; replace with `E1`. |
| `advance_repayments` | `advance_repayments_admin`; `advance_repayments_employee_read` | Replace with `B1,H1,W1`; replace with `E1`. |
| `leave_approval_delegates` | `leave_approval_delegates_admin`; `leave_approval_delegates_actor_read` | Replace with `B1`; replace record visibility with `L0`, while active authority uses `L1`. |
| `roster_assignments` | `roster_assignments_admin_all`; `roster_assignments_employee_read` | Replace with `B1,W1`; replace with published `E1`. |
| `shift_swap_requests` | `shift_swap_requests_admin_all`; `shift_swap_requests_employee_read` | Replace with `B1,W1`; replace with participant `E1`. |
| `employee_contracts` | `employee_contracts_admin` | Replace with admin-only `B1,H1`; expiry processing uses the current contract field on `employees`. |
| `offboarding_checklists` | `offboarding_checklists_admin` | Replace with `B1,W1`. |
| `offboarding_tasks` | `offboarding_tasks_admin` | Replace with `B1,W1`. |
| `offboarding_task_templates` | `offboarding_task_templates_admin` | Replace with admin branch read only. |
| `expense_claims` | `expense_claims_admin`; `expense_claims_employee_read` | Replace with `B1,M1,W1`; replace with `E1`. |
| `assets` | `assets_admin`; `assets_employee_read` | Replace with `B1,W1`; replace with self-assigned `E1`. |
| `asset_assignments` | `asset_assignments_admin`; `asset_assignments_employee_read` | Replace with `B1,H1,W1`; replace with `E1`. |
| `payroll_approval_log` | `payroll_approval_log_admin` | Replace with `B1,H1`. |
| `training_records` | `training_records_admin`; `training_records_employee_read`; `training_records_manager_all`; `training_records_employee_insert`; `training_records_employee_update` | Replace with `B1`; replace with `E1`; replace with `M1`; replace with self-service `E1`; replace with field-limited self-service `E1`. |
| `certifications` | `certifications_admin`; `certifications_employee_read`; `certifications_manager_all`; `certifications_employee_insert`; `certifications_employee_update` | Replace with `B1`; replace with `E1`; replace with `M1`; replace with pending self-submission `E1`; omit broad self-update and use field-limited workflow. |
| `clock_events` | `Admins view their employees' clock events` | Omit as a duplicate identity; `B1` supplies branch admin read. |
| `letter_requests` | `letter_requests_admin`; `letter_requests_employee_read` | Replace with `B1,W1`; replace with `E1`. |
| `biometric_mappings` | `biometric_mappings_admin` | Replace with `B1`. |
| `departments` | `departments_admin` | Replace with admin-only `B1`; staff receive labels through other projections. |
| `appraisal_cycles` | `appraisal_cycles_admin`; `appraisal_cycles_manager_read` | Replace with `B1,W1`; replace with historical appraisal-linked `A1`. |
| `appraisals` | `appraisals_admin`; `appraisals_employee_read`; `appraisals_manager_read`; `appraisals_manager_update` | Replace with `B1,W1`; replace with `E1`; replace with `M1`; replace with workflow-limited `M1`. |
| `appraisal_sections` | `appraisal_sections_admin`; `appraisal_sections_employee_read`; `appraisal_sections_manager_read`; `appraisal_sections_manager_update` | Replace with `B1,W1`; replace with `E1`; replace with `M1`; replace with workflow-limited `M1`. |
| `compliance_overrides` | `compliance_overrides_admin` | Replace with tenant or branch `T1,B1,H1`, according to nullable `branch_id`. |
| `department_staffing_rules` | `dept_staffing_admin` | Replace with `B1`. |
| `employees` | `employees_manager_read` | Replace with projected `M1`. |
| `employees` | `employees_self_update_contact` | Omit. The four-field FastAPI contact workflow supersedes broad row update. |
| `leave_requests` | `leave_requests_manager_read` | Replace with `M1,L1`. |
| `leave_balances` | `leave_balances_manager_read` | Replace with minimum-field `M1,L1`. |
| `leave_types` | `leave_types_authenticated_read` | Omit. Branch `R1` replaces its cross-tenant read. |
| `shifts` | `shifts_admin_all`; `shifts_authenticated_read` | Omit duplicate admin identity in favor of `B1`; omit global read in favor of branch `R1`. |
| `cme_requirements` | `cme_requirements_admin_all` | Replace with `B1`. |
| `incident_reports` | `incident_reports_admin_all` | Replace with `B1,H1,W1`. |

### Baseline 045 identities

| Table | Legacy policy name | Phase 5 disposition |
|---|---|---|
| `companies` | `companies_owner_all` | Replace with `T1,R1`; legacy name stays absent. |
| `user_profiles` | `user_profiles_owner_all` | Replace with `P0,T1`; no owner-wide `ALL`. |
| `employees` | `employees_owner_all` | Replace with `B1`; no owner-wide `ALL`. |
| `employees` | `employees_self_read` | Replace with `E1`. |
| `payroll_runs` | `payroll_runs_owner_all` | Replace with `B1,W1`; no owner-wide `ALL`. |
| `payroll_entries` | `payroll_entries_owner_all` | Replace with `B1,W1`; no owner-wide `ALL`. |
| `payslips` | `payslips_owner_all` | Replace with `B1,H1`; no update or delete. |
| `payslips` | `payslips_employee_read` | Omit duplicate legacy identity; `E1` supplies self-read. |
| `attendance_records` | `attendance_records_owner_all` | Replace with `B1,W1`; no owner-wide `ALL`. |
| `attendance_records` | `attendance_records_employee_read` | Omit duplicate legacy identity; `E1` supplies self-read. |
| `clock_events` | `clock_events_owner_all` | Replace with `B1,E1,H1`; no owner-wide `ALL`. |

### Storage object identities

| Table | Legacy policy name | Phase 5 disposition |
|---|---|---|
| `storage.objects` | `employee_documents_employee_upload` | Omit. FastAPI and the private storage adapter authorize upload. No PostgreSQL storage policy returns. |
| `storage.objects` | `employee_documents_employee_read_own` | Omit. FastAPI authorizes short-lived download after metadata scope checks. |

## Contradiction checks

- No role has both an allowed hard delete and a retention rule for the same final or historical
  state. Draft-only and uncompleted-child deletes state their guard.
- No manager team rule crosses a branch. The Phase 4 foreign key and `M1` agree.
- No delegate family grants a non-leave permission.
- Employee payroll entry and payroll-run reads remain omitted. Payslips are the employee contract.
- Append-only tables have no runtime update or delete grant.
- Context `NULL` never means tenant-wide, branch-wide, all employees, or system access.
- An SQL verb may be broader than one role because human roles share `workloop_runtime`. FastAPI
  field and operation checks plus RLS row checks must both pass. No catalogue cell treats the SQL
  grant alone as authorization.

## Approved decision packet

The project owner approved every answer below without amendment on 2026-09-06. The approval also
covers the full 54-table catalogue and all 119 legacy-policy reconciliation entries.

| ID | Decision | Approved answer | Consequence |
|---|---|---|---|
| `5A-D1` | Branch selection | Require `X-Workloop-Branch-ID` on admin branch-owned requests and verify `(branch.id, branch.company_id)` against the database-derived company. Keep company settings, branch list, and branch create selector-free. Existing-branch detail, update, or delete requires the header to equal the path branch. Do not persist authority in the token or profile. | The UI can discover and remember choices, but the server verifies every selected branch. Missing, malformed, and inaccessible selectors have distinct safe handling. |
| `5A-D2` | Cross-branch manager access | Do not allow it. Managers and reports must share a branch, matching the Phase 4 composite foreign key. | A pre-activity branch correction must reassign or clear the manager. A manager cannot run one queue across branches. Retained-history transfers are covered by `5A-D10`. |
| `5A-D3` | Manager and delegate scope | Use one-level current direct reports. Leave delegation is inclusive-date, same-branch, leave-only, and follows the approver's current reports. Permit an otherwise eligible manager or employee to be a delegate; both approver and delegate must have active account status, one valid profile, and eligible employee state. Retained delegation rows are readable by their named participants, but only an active row grants action. | No recursive org access or generic delegate role exists. Every query joins current relationships. An employee delegate temporarily gains only the named leave decision capability. |
| `5A-D4` | Self-approval | Enforce the separation rules above. Retain admin direct leave decisions, future-approved cancellation, and rule-based `auto_approve`. Keep manager expense review optional: admins may act directly on pending claims and may override a manager rejection with a reason; actor difference applies when a manager decision exists. Payroll submitter and approver differ; appraisal reviewer and calibrator differ. | Only strict payroll testing needs a second synthetic admin per affected tenant. Auto-approved leave stays distinguishable from human approval, and expense tests cover direct and manager-first paths. |
| `5A-D5` | Missing versus inaccessible objects | Return the same `404 resource_not_found` for both. Use `403 operation_not_permitted` only after the caller can access the row but cannot perform the action. | UUID guessing reveals no tenant ownership. Repository lookups must include scope in the first statement. |
| `5A-D6` | System actor handling | Keep migration and seed separate. Add a dedicated `workloop_expiry_processing` login, not a shared job login. Authenticate the job by `current_user`; use context only for its scoped company, branch, business date, and audit label. Approve only the exact column reads and notification insert listed above. | This adds one PostgreSQL login later. Generic scheduled work remains denied. The credential never enters the web container. A future job needs its own review and login. |
| `5A-D7` | Audit storage | Keep domain histories and add the proposed append-only `audit_events` table, admin-only reads, scoped actor FKs, and atomic database writes. Defer production retention duration to legal and security review, with no purge before that approval. | Phase 5G adds one table, its checks and restrictive FKs, and audit writers. The target becomes 55 tables. Referenced branches and profiles cannot be hard-deleted. Storage durability is decided separately in `5A-D15`. |
| `5A-D8` | Hard deletes | Keep only the guarded deletes listed in the catalogue. Delegations delete only before their start date; rosters only while unpublished and unused; training only while planned; documents and certifications only while pending or rejected; holidays only while future and unused. Retain employees, issued payroll, audit/history, verified evidence, completed training, appraisals, incidents, completed assignments, finalized workflows, and referenced branches or profiles. | Some legacy delete buttons become archive, deactivate, or conflict behavior. A never-used branch remains deletable because its lifecycle audit event is tenant-scoped. |
| `5A-D9` | New roles, tables, constraints, and context | Add no business enum role and implement no schema change in 5A. Approve for later phases the dedicated expiry login; `audit_events` with its fields and constraints; the ten context keys; fixed-name context readers; and the four helpers in `5A-D17`. If `5A-D15` is approved, also approve its dedicated reconciler login, `storage_operations` fields, checks, and scoped FKs. Propose no other role, table, constraint, context key, or helper. | These are designs only. Later parts need separate authorization and Alembic revisions. Any implementation discovery that needs another object returns to the owner. |
| `5A-D10` | Employee branch transfer | Treat branch as immutable after any retained dependent row exists. Permit only a pre-activity correction with zero dependent rows. Defer a real transfer until a separate employment-assignment/history schema is designed and approved. | Existing records keep truthful historical branch ownership and Phase 4 FKs remain valid. Established employees cannot transfer branches during Phase 5 without another owner decision and schema revision. |
| `5A-D11` | Principal employment eligibility | Require active account status, exactly one valid role and employee link, `employees.active = true`, and status `Active`, `Probation`, or `On Leave`. Reject all mismatches and terminated access. A manager demotion, disable, or termination must atomically reassign every direct report to an eligible same-branch manager or fail. | On-leave staff retain portal access. Terminated or inconsistent links fail closed. Manager lifecycle actions must include report reassignment. No profile-status column is added. |
| `5A-D12` | Database field enforcement | Keep one `workloop_runtime` login. Treat each table grant as the minimum verb union needed by trusted FastAPI repositories, with column restriction where one safe union exists. Enforce per-caller field and transition rules in FastAPI; use RLS for row scope and the named protected functions where direct verbs are revoked. Do not add a database role or function for every business operation. | This matches the stated primary-boundary model and keeps RLS as defense in depth. It does not treat the shared SQL grant as a caller permission or as protection against compromise of the runtime credential. |
| `5A-D13` | Notification inbox scope | Require staff notifications to match the recipient's linked branch; approve no null-branch staff type now. For admins, require a verified branch and return that branch plus tenant-wide null-branch notifications. Keep the producer type/entity allowlist above. | The admin bell follows the selected branch instead of aggregating every branch. A wrongly addressed notification cannot become a cross-branch data channel. |
| `5A-D14` | Expiry recipients and sources | Send each expiry alert to every active tenant admin. Do not nominate one admin or notify employees. Use current employee fields for probation, contract, identity, and licence dates; do not scan append-only contract history. Apply the state and threshold rules above. | Tenants with several admins receive one deduplicated alert per admin. No nominated-recipient column or contract-current marker is needed. |
| `5A-D15` | Storage durability | Add the private `storage_operations` outbox, `O1` and `S1` policies, defaults and lease fields, exact grants, and dedicated `workloop_storage_reconciler` login in the later storage phase. The reconciler can retry deletes and remove upload orphans, but cannot retry upload bytes. Purge terminal outbox rows after 90 days; retain safe audit events. | Durable claims, retries, and orphan cleanup become implementable without exposing paths to audit readers. This adds a second system login, raises the post-storage target to 56 tables, and permits no business-table access. |
| `5A-D16` | Document and certification creation | Keep legacy admin creation as immediately verified, with reviewer ID and time from trusted context. Employee document and certification creates remain pending. Manager direct-report certification creates are pending and require admin review. | Admin upload stays one step. Manager and employee submissions cannot self-verify. Expiry processing ignores pending and rejected rows. |
| `5A-D17` | Workflow-only protected helpers | Add the four fixed-purpose helpers defined above: scoped active-account check, derived workflow notification creation, delegated-leave predicate, and allowlisted audit writer. Apply their stated caller gates plus the common owner, invoker, pinned search path, context validation, and revoked `PUBLIC` rules. | Portal-role checks and notifications work without broadening `app_users` visibility. Employee delegates act without general employee reads. Audit inserts cannot forge scope or actors. Runtime receives only named execute grants. |
| `5A-D18` | Training completion authority | Allow employee and manager-self enrolment and planned-row descriptive edits, but not self-completion, score, pass result, CME classification, cost, or accepted evidence. Admins and managers acting on current direct reports may record completion. Retain every non-planned row. | Existing self-completion UI must stop using that path until a separate review-state design is approved. CME totals cannot be increased by self-attestation. |

This approval fixes the Phase 5A product and schema design. Any later implementation discovery that
would change one of these answers requires another project-owner decision.

## Approved storage retry decision

The post-approval review found one behavior that `5A-D15` did not settle. The project owner approved
`5A-D19` without amendment on 2026-09-06.

| ID | Decision | Approved answer | Consequence |
|---|---|---|---|
| `5A-D19` | Storage reconciliation retry limit | Permit no more than eight provider attempts per outbox row. Attempt one is reserved under `5A-D20` and then made immediately. After failures one through seven, set `next_attempt_at` to 1 minute, 5 minutes, 15 minutes, 1 hour, 6 hours, 24 hours, and 72 hours later. After failure eight, keep `status = 'failed'`, set `next_attempt_at = NULL`, clear the lease, and stop automatic claims. Retain that row until an approved operator procedure resolves it. Purge only `succeeded` and `reconciled` rows after 90 days. Emit a safe operational alert keyed by the operation UUID and error code, never the object key. A future manual requeue needs its own approved operator procedure and must not be inferred from migration ownership. | Retries terminate predictably and tests can pin every transition. Persistent delete failures remain visible for manual recovery instead of retrying forever or losing the private object key. This adds no role, table, constraint, context key, helper, or business-table access, but the later storage phase must provide monitoring and an operator runbook before production use. |

## Approved attempt reservation decision

The final closure check found that `5A-D19` limited claimed retries but did not reserve the immediate
provider call. The project owner approved `5A-D20` without amendment on 2026-09-06.

| ID | Decision | Approved answer | Consequence |
|---|---|---|---|
| `5A-D20` | Storage attempt reservation | Reserve every provider attempt before making the call. After inserting a pending row at count zero, `workloop_runtime` must make an `O1` transition to `claimed`, set `attempt_count = 1`, stamp the claim time, and set a 15-minute lease before the immediate provider call. Give runtime column-update access to `claimed_at` and `lease_expires_at` only for that transition. The provider request deadline must stay below the lease. `S1` may claim or reclaim only while `attempt_count < 8`; each claim increments the count before a provider call. An expired lease at count eight cannot be claimed. The reconciler copies the row scope into a new transaction, marks it terminal `failed`, clears retry and lease fields, emits the safe alert, and makes no provider call. | The database counter becomes a reservation count, so crashes cannot permit a ninth provider call. The later storage phase must test crash-before-call, crash-during-call, crash-after-call, expired leases at counts one and eight, and concurrent claims. This changes the approved `O1` runtime column grant and policy transition but adds no role, table, constraint, context key, helper, or business-table access. |

## Independent review

An independent GPT-5.6 reviewer inspected the named Phase 0, 3, 4, and 5 sources, authentication
code, models, migrations, grants, fixtures, tests, and this draft. The reviewer made no edits. A
post-approval pass confirmed the catalogue, reconciliation, fixture mapping, delete guards, field
rules, scope rules, protected helpers, audit access, and notification rules. It found four remaining
items, recorded as `IR-46` through `IR-49`. The owner approved `5A-D19`. The next confirmation pass
closed those items but found the attempt-reservation issue recorded as `IR-50`. The owner approved
`5A-D20`. The following pass found the command-specific discovery omission recorded as `IR-51`.
The last pass confirmed that every finding is closed and found no remaining omission,
contradiction, unsafe grant, unsupported scope, or new decision.

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| `IR-01` | High | `payroll_entries` mapped `E1` while staff reads were unsupported. | Resolved: removed `E1`; payslips remain the staff contract. |
| `IR-02` | High | Expiry source rows lacked matching `J1` policies and job grants. | Resolved: every source now has `J1` and an exact column grant. |
| `IR-03` | High | Notification workflow insert had no human policy path. | Resolved by the protected writer proposed in `5A-D17`. |
| `IR-04` | High | Appraisal-cycle staff reads had no usable policy and excluded historical cycles. | Resolved with appraisal-linked `A1`, including closed history. |
| `IR-05` | High | Permissive `T1` could expose branch compliance overrides. | Resolved: null branch uses `T1`; nonnull branch uses selected `B1`. |
| `IR-06` | High | A shared job login could claim the expiry actor key. | Owner: `5A-D6` uses a dedicated authenticated login. |
| `IR-07` | High | Retained definer functions lacked exact scope, state, and actor checks. | Resolved in the retained-function contract. |
| `IR-08` | High | `current_user` inside a definer function would be the owner, not the invoker. | Resolved with direct-login `session_user` checks and no `SET ROLE` membership. |
| `IR-09` | High | Policy families did not define command, `USING`, `WITH CHECK`, role gates, or OR composition. | Resolved with one deliberate policy per login and command. |
| `IR-10` | High | The branch list and create paths cannot require a preselected branch. | Owner: selector-free exceptions and existing-branch matching are in `5A-D1`. |
| `IR-11` | Medium | Appraisal, insurance, asset, swap, app-user, and notification rows need nonstandard predicates. | Resolved with explicit linked predicates and safe joins. |
| `IR-12` | Medium | Branch-wide `R1` exposed all insurance policies to staff. | Resolved with self-linked `I1`. |
| `IR-13` | Medium | Manager self and direct-report training and certification writes were conflated. | Resolved in the catalogue; completion authority returns in `5A-D18`. |
| `IR-14` | Medium | Delegation record visibility and active decision authority were conflated. | Owner: separate `L0` and `L1` behavior is in `5A-D3`. |
| `IR-15` | Medium | Delegate role and approver/delegate eligibility were unspecified. | Owner: active account, valid profile, eligible employee, and manager-or-employee delegate are in `5A-D3`. |
| `IR-16` | Critical | `L1` could not see the approver's reports under caller RLS. | Owner: the non-row-returning predicate helper is in `5A-D17`. |
| `IR-17` | Medium | Staff reads of six admin-only tables expanded legacy scope. | Resolved: direct staff access to leave and attendance audit, dependants, shift assignments, departments, and attendance settings is denied. |
| `IR-18` | Critical | Phase 4 retained child FKs make an established employee branch transfer invalid or history-corrupting. | Owner: branch immutability and pre-activity correction are in `5A-D10`. |
| `IR-19` | High | Terminated employees could retain portal or manager scope; manager demotion could strand reports. | Owner: fail-closed eligibility and atomic reassignment are in `5A-D11`. |
| `IR-20` | High | Admin leave decisions, future cancellation, and auto-approval actor semantics were missing. | Owner: exact transitions and rule-marked auto-approval are in `5A-D4`. |
| `IR-21` | High | Expense manager review was ambiguously mandatory and admin states were unspecified. | Owner: direct and manager-first state transitions are in `5A-D4`. |
| `IR-22` | High | Employee advance creation could inherit the schema's `active` default. | Resolved: employee requests force pending and protected financial fields. |
| `IR-23` | High | Whole-table expiry `SELECT` exposed sensitive columns. | Resolved with exact job column grants and exclusions. |
| `IR-24` | Critical | Expiry recipient selection required an employee link, but admins have none. | Owner: all active tenant admins and no employee recipients are in `5A-D14`. |
| `IR-25` | High | Append-only contract history could create stale expiry alerts. | Owner: current employee contract fields and exact source filters are in `5A-D14`. |
| `IR-26` | High | Notification reads could become a cross-branch data channel. | Owner: role-aware branch rules and producer allowlists are in `5A-D13`. |
| `IR-27` | High | Leave and other workflows could not resolve a recipient app user without broad profile access. | Owner: derived notification creation is in `5A-D17`. |
| `IR-28` | High | Portal-role assignment could not safely check target account status. | Owner: the scoped boolean account helper is in `5A-D17`. |
| `IR-29` | High | Shared runtime verb grants cannot enforce different per-role field lists. | Owner: the FastAPI-primary and RLS-row-defense boundary is explicit in `5A-D12`. |
| `IR-30` | High | Audit coverage, readers, actor-company binding, FKs, grants, and write atomicity were incomplete. | Owner: exact future policy, grants, protected writer, FKs, coverage, and retention are in `5A-D7`, `5A-D9`, and `5A-D17`. |
| `IR-31` | Medium | Branch lifecycle audit could make creation itself prevent deletion. | Resolved: create and delete events are tenant-scoped with null branch. |
| `IR-32` | Medium | Assignment history was described as wholly append-only despite allowed close transitions. | Resolved: immutability begins after the allowed transition. |
| `IR-33` | Medium | Appraisal-section purge claimed a nonexistent cascade and lacked a delete grant. | Resolved: unused-cycle delete requires no appraisal, so no section exists. |
| `IR-34` | High | File operations omitted several buckets and the manager path-owner trap. | Resolved with the storage operation matrix and server-generated object keys. |
| `IR-35` | Critical | General audit could not retain a private object key for reliable storage recovery. | Owner: restricted outbox and dedicated reconciler are in `5A-D15`. |
| `IR-36` | High | The outbox lacked runtime policy, defaults, grants, leases, concurrency, and terminal retention. | Resolved by approved `5A-D15` and `5A-D19`: `O1`, `S1`, exact fields and grants, lease claiming, bounded retries, terminal failures, and 90-day successful-row purge are settled. |
| `IR-37` | High | Delete grants conflicted with delegation, roster, evidence, training, and holiday retention. | Owner: exact guarded exceptions are in `5A-D8`. |
| `IR-38` | Medium | Expense, advance, payroll-run, and roster delete or withdrawal states were vague. | Resolved with exact catalogue guards. |
| `IR-39` | High | Training self-completion could inflate score, pass, or CME totals. | Owner: planned self-edit versus trusted completion is in `5A-D18`. |
| `IR-40` | High | Admin, manager, and employee document or certification create states were unspecified. | Owner: trusted admin verification and pending staff submissions are in `5A-D16`. |
| `IR-41` | Medium | Several legacy reconciliation dispositions lagged behind catalogue changes. | Resolved: all affected entries now match their catalogue families. |
| `IR-42` | Low | The prose referred to nonexistent active profile state. | Resolved: only account and employee have active state; profile validity is structural. |
| `IR-43` | Low | The draft incorrectly required a second admin for expense separation tests. | Resolved: only strict payroll needs the extra admin fixture. |
| `IR-44` | Low | Title-case headings violated the loaded prose rules. | Resolved: headings use sentence case. |
| `IR-45` | Low | Company-row logo ownership conflicted with Phase 4 branch storage. | Resolved: `branches.logo_url` owns the setting. |
| `IR-46` | High | The approved storage outbox did not set a maximum attempt count, backoff schedule, or terminal failure behavior. | Owner: approved `5A-D19` sets eight attempts, exact delays, retained terminal failures, safe alerting, and a separately approved manual-recovery boundary. |
| `IR-47` | High | The short `S1` rule required company context for the initial claim even though the detailed flow requires a null-context atomic claim. | Resolved: `S1` and the context table now allow a null-context scan and atomic claim for pending, retryable failed, or expired-lease rows. Later updates and deletion require copied company and branch context. |
| `IR-48` | Medium | Several passages still described approved decisions as pending. | Resolved: the operative text records approval of `5A-D1` through `5A-D20`. |
| `IR-49` | Low | `IR-17` counted five affected tables but named six. | Resolved: `IR-17` now says six. |
| `IR-50` | High | The immediate provider call did not reserve attempt one, and an expired lease at count eight remained claimable. Either path could permit a ninth provider call. | Owner: approved `5A-D20` adds a runtime pre-call reservation, a strict `attempt_count < 8` claim predicate, and no-call terminal handling for an expired eighth reservation. |
| `IR-51` | High | Null-context `S1` visibility omitted exhausted leases and purge candidates, so the reconciler could not obtain their company and branch before scoped terminalization or deletion. | Resolved: null-context `SELECT` can discover the three exact queue classes, null-context `UPDATE` can claim only rows below eight attempts, and terminalization or deletion requires copied scope plus its approved state guard. |

Findings marked `Owner` changed product, schema, role, helper, grant, or retention decisions. The
project owner's approval of `5A-D1` through `5A-D18` on 2026-09-06 accepts each cited disposition.
The reviewer confirmed every owner disposition in the post-approval passes. `IR-51` fit the
approved design and changed no product or schema decision. The independent review is closed.

## Validation record

Final validation ran on 2026-09-06 after the owner approvals and independent review closure:

- The catalogue has 54 numbered rows and 54 unique names. It exactly matches the 54 Phase 4 target
  table names, with no missing or extra table.
- The reconciliation has 119 unique `(table, policy name)` identities. It exactly matches the Phase
  4 source, with no missing or extra identity.
- The fixture mapping has 19 numbered, unique controls. It exactly matches
  `NEGATIVE_CONTROL_MATRIX`, with no missing or extra control.
- The decision packet has 20 unique IDs, `5A-D1` through `5A-D20`. The review ledger has 51 unique
  IDs, `IR-01` through `IR-51`.
- Manual and independent allow-and-deny passes covered row scope, field scope, state guards,
  retention, actor rules, nullable branches, grants, storage retries, and helper paths. No internal
  contradiction remains.
- Across the six changed documentation files, Markdown fences are balanced, headings have no level
  jump, and all 49 local links resolve. The design's eight fences are balanced and it has no local
  link to resolve.
- The unfinished-marker, trailing-space, nonstandard-dash, and curved-quotation scans returned zero
  for the Phase 5 documents.
- `git diff --check` passed. Git printed only the preserved LF-to-CRLF working-copy warnings.

No backend, frontend, Compose, or database suite was run because Phase 5A changed documentation
only.
