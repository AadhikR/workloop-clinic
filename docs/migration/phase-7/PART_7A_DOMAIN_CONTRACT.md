# Phase 7A domain contract

## Status and authority

The project owner approved decisions `7A-D1` through `7A-D9` on 2026-09-09. This document is the
canonical Phase 7 domain contract. It does not authorize Phase 7B or any runtime, database, React,
infrastructure, or identity-provider change.

The contract uses the approved Phase 4 schema, Phase 5 authorization rules, and Phase 6 HTTP
conventions. One recommendation needs a schema-design amendment before implementation: the Phase 6
idempotency record does not yet exist. No migration is part of 7A.

## Scope

Phase 7 covers these existing target objects:

| Object | Phase 7 use |
| --- | --- |
| `companies` | Legal employer settings and tenant identity. |
| `branches` | Operating location, payroll routing defaults, local contact details, and feature flags. |
| `employees` | Employee master, current reporting line, current employment state, and current pay fields. |
| `user_profiles` | Existing employee or manager portal-role assignment only. |
| `employee_job_history` | Append-only title, department, salary, and status history. |
| `departments` | Branch department hierarchy and department head. |
| `department_staffing_rules` | Branch staffing minimum by department and shift category. |

Phase 7 does not own payroll calculations or routing cascades, attendance, rosters, shifts, insurance,
documents, employment-contract history, offboarding checklists, or Keycloak account provisioning.
Those screens may consume a Phase 7 employee label or identifier, but their business reads and writes
remain on their later-phase authority until their own cutover.

Employee hard deletion and branch transfer are absent. A branch correction remains unavailable until
the separately approved source-and-destination workflow can prove that the employee has no retained
dependent row.

## Evidence and inventory method

The inventory started from `docs/migration/phase-0/SUPABASE_DEPENDENCY_INVENTORY.md`, then used `rg`
over `src`, root Supabase SQL, `sql`, `migration`, `backend/app`, `backend/alembic/versions`, `tests`,
and `scripts`. The scan covered table names, storage function names, RPC names, converter names,
imports, and React calls. Indirect consumers are listed even when their owning feature stays in a
later phase.

### Stable dependency IDs

The cutover records use these IDs. A planned migration module uses a `synthetic://` locator until its
own implementation part creates a real file. A preparation record freezes every such dependency.

| ID | System | Locator | Purpose |
| --- | --- | --- | --- |
| `legacy-auth-company-profile` | Legacy | `src/context/AuthContext.jsx` | Reads company ownership and reads or writes legacy profiles during Supabase sign-in and signup. Account provisioning stays outside Phase 7. |
| `legacy-company-storage` | Legacy | `src/utils/storage.js` | `getCompanies`, `getCompany`, `saveCompany`, `saveCompanyLogo`, `createBranch`, and `deleteBranch`. Legacy company rows also act as branches. |
| `legacy-company-context` | Legacy | `src/context/CompanyContext.jsx` | Loads branch-like company rows, selects the first row as fallback, and supplies the selected row to admin screens. |
| `legacy-profile-storage` | Legacy | `src/utils/profileStorage.js` | Reads self employee and employer rows and gets or sets employee portal roles through legacy RPCs. |
| `legacy-employee-storage` | Legacy | `src/utils/storage.js` | Reads, creates, updates, imports, archives, hard-deletes, and converts employees. Also reads and writes job history. |
| `legacy-csv-converter` | Legacy | `src/utils/csvImport.js` | Converts payroll CSV rows to partial employee objects. |
| `legacy-department-storage` | Legacy | `src/utils/departmentStorage.js` | Reads, creates, updates, deletes, and converts departments. |
| `legacy-staffing-storage` | Legacy | `src/utils/staffingStorage.js` | Reads, upserts, updates, deletes, and converts staffing rules. |
| `legacy-employee-joined-readers` | Legacy | `src/utils/{appraisalStorage,assetStorage,attendanceStorage,expenseStorage,leaveStorage,taskStorage,trainingStorage}.js` | Reads employee identity, current manager relationships, or joined labels for later-phase features. |
| `legacy-phase7-consumers` | Legacy | `src/components` and `src/context` | React consumers detailed below. |
| `legacy-schema-contracts` | Legacy | `supabase_schema.sql`, root `supabase_migration_*.sql`, and `sql/*.sql` | Legacy table, RLS, converter, and RPC source evidence. |
| `target-domain-models` | Migration | `backend/app/models/identity.py` and `backend/app/models/people.py` | Existing approved SQLAlchemy models for all seven objects. |
| `target-scope-foundation` | Migration | `backend/app/auth`, `backend/app/repositories/scoped.py`, and `backend/app/services/execution.py` | Trusted principals, branch selection, row scope, relationship locks, and transaction ownership. |
| `target-schema-foundation` | Migration | `backend/alembic/versions` | Existing Phase 3 through Phase 5 schema, RLS, grants, audit, and concurrency objects. |
| `target-http-client` | Migration | `migration/src/http.js` | Phase 6 HTTP, error, timeout, and authentication behavior. |
| `target-build-isolation` | Migration | `migration/vite-isolation.js` and `scripts/frontend-build-isolation.mjs` | Prevents migration code from importing the legacy React or Supabase graph. |
| `planned-organization-reader` | Migration | `synthetic://phase-7b/organization-reader` | Planned company, employer, and branch read routes and client adapters. |
| `planned-organization-writer` | Migration | `synthetic://phase-7c/organization-writer` | Planned company and branch administration. |
| `planned-employee-reader` | Migration | `synthetic://phase-7d/employee-reader` | Planned list, detail, self, direct-report, and job-history reads. |
| `planned-department-writer` | Migration | `synthetic://phase-7e/department-writer` | Planned department reads and administration. |
| `planned-staffing-writer` | Migration | `synthetic://phase-7e/staffing-writer` | Planned staffing-rule reads and administration. |
| `planned-employee-writer` | Migration | `synthetic://phase-7f/employee-writer` | Planned create, ordinary edit, and create-only CSV import. |
| `planned-lifecycle-writer` | Migration | `synthetic://phase-7g/lifecycle-writer` | Planned job, pay, status, manager, probation, archive, and portal-role workflows. |
| `synthetic-identity-map` | Migration | `tests/fixtures/phase-6d/synthetic-users.json` | Existing two-person synthetic identity map required by every draft record. |

### Legacy operation inventory

| Object | Readers | Writers | Converter and behavior |
| --- | --- | --- | --- |
| `companies` and legacy branches | `getCompanies`, `getCompany`, `getMyCompany`, and direct company lookups in `AuthContext` | `saveCompany`, `saveCompanyLogo`, `createBranch`, `deleteBranch`, plus profile recovery and company creation in `AuthContext` | `dbToCompany` and `companyToDb` flatten legal and operating fields into one object. `getMyCompany` returns a raw row and chooses the first owner row. |
| `employees` | `getEmployees`, `getMyEmployeeRecord`, the employee lookup in `getEmployeeTasks`, manager-report lookups in leave and training, attendance ownership lookups, appraisal self lookup, and PostgREST joins in appraisal, asset, expense, task, and training storage | `saveEmployee`, `saveEmployees`, `archiveEmployee`, and unused `deleteEmployee` | `dbToEmployee` returns camelCase. `employeeToDb` accepts a full mutable object. `getMyEmployeeRecord` returns raw snake_case. CSV conversion returns a partial object and the browser merges it by MOL ID. |
| `user_profiles` | `getProfile`, `getEmployeePortalRole`, and profile resolution in `AuthContext` | `setEmployeePortalRole`, `createAdminProfile`, profile upserts in `AuthContext`, and `linkEmployeeAccount` | Legacy profile shape uses Auth UUID, `company_user_id`, and optional employee link. Phase 7 owns only the role change for an already linked profile. |
| `employee_job_history` | `getJobHistory` and `getAllJobHistory` | `addJobHistoryEntry` | Inline converter emits camelCase but exposes legacy email text as `changedBy`. Employee edits and history inserts are separate transactions. |
| `departments` | `getDepartments` | `saveDepartment` and `deleteDepartment` | `dbToDept` maps the hierarchy fields. Legacy validation for duplicate names and cycles runs in React. |
| `department_staffing_rules` | `getDeptStaffingRules` | `saveDeptStaffingRule` and `deleteDeptStaffingRule` | `dbToRule` maps dates to empty strings. Legacy create is an owner-scoped upsert by department and category. |

Legacy SQL sources for these operations include `supabase_schema.sql`,
`supabase_migration_existing_db.sql`, `supabase_migration_employee_auth_mapping.sql`,
`supabase_migration_employee_company_read.sql`, `supabase_migration_employee_rls.sql`, and SQL
revisions `001`, `009`, `021`, `029`, `033`, `034`, `035`, `041`, `043`, `044`, `045`, `046`, and
`049`. The Phase 4 catalogue, not any one legacy file, decides the target shape.

### React consumer inventory

| Data | Direct consumers | Indirect or later-phase consumers |
| --- | --- | --- |
| Company and branch | `App.jsx`, `CompanyContext.jsx`, `CompanySettings.jsx`, `Dashboard.jsx`, `EmployeeShell.jsx`, `ManagerShell.jsx`, `EmpPayslips.jsx`, and `EmpRequests.jsx` | `AttendanceManager.jsx`, `DepartmentManager.jsx`, `LetterRequestsManager.jsx`, `PayrollManager.jsx`, `PayrollList.jsx`, `Reports.jsx`, and `RosterManager.jsx` consume a branch field, label, setting, or selected ID. |
| Admin employee list or detail | `EmployeeManager.jsx`, `EmployeeModal.jsx`, and `DepartmentManager.jsx` | `AssetsManager.jsx`, `AdvancesManager.jsx`, `AppraisalManager.jsx`, `AttendanceManager.jsx`, `ClinicalDashboard.jsx`, `Dashboard.jsx`, `IncidentManager.jsx`, `LeaveManager.jsx`, `LetterRequestsManager.jsx`, `PayrollManager.jsx`, `PayrollList.jsx`, `Reports.jsx`, `RosterManager.jsx`, and `TrainingManager.jsx`. These later-phase screens remain on their existing feature authority until their own cutover. |
| Employee self | `EmployeeShell.jsx`, `ManagerShell.jsx`, `EmpHome.jsx`, `EmpProfile.jsx`, `EmpAdvances.jsx`, `EmpDocuments.jsx`, `EmpExpenses.jsx`, `EmpLeave.jsx`, `EmpPayslips.jsx`, `EmpRequests.jsx`, and `EmpTraining.jsx` | `ManagerLeaveQueue.jsx` uses self identity before loading its queue. |
| Direct reports | `ManagerLeaveQueue.jsx` and `ManagerExpenseQueue.jsx` currently combine manager identity with `getEmployees` | Manager appraisal and training utilities query direct reports independently. Their owning data remains later-phase work. |
| Job history | `EmployeeManager.jsx` and `Reports.jsx` | `EmployeeModal.jsx` also writes unsupported contract labels into job history. Contract lifecycle stays in Phase 11. |
| Departments | `DepartmentManager.jsx`, `EmployeeModal.jsx`, `ClinicalDashboard.jsx`, and `IncidentManager.jsx` | Employee and incident forms consume labels. Direct staff table access remains denied. |
| Staffing rules | `DepartmentManager.jsx`, `ClinicalDashboard.jsx`, `Reports.jsx`, and `RosterManager.jsx` | Roster enforcement remains Phase 10. Phase 7 exposes configuration only. |
| Portal role | `EmployeeModal.jsx` | `AuthContext.jsx` resolves a legacy role, but Phase 7 does not provision or repair identities. |

`EmployeeModal.jsx` combines employee master data with documents, insurance, shift assignment,
contract history, and portal roles. Phase 7 must split its consumer. A migration employee form may
use only the fields and workflows in this contract. It must not import that legacy component.

### Target build dependencies

The target models already contain the seven objects. The relevant schema path is
`f41c9a7b23d1`, `a4b7e2c91d05`, `3f9a1c7b2e10`, `f52e0a1b9c34`, `8e2b6a4c1f07`,
`a0d4e6f8c92b`, `1b29d4e7f860`, and `2c4d6e8f0a1b`. Other target migrations reference employees or
profiles for later domains and remain unchanged.

The migration build currently has authentication, `migration/src/http.js`, and sample architecture
routes only. It has no Phase 7 adapter or component. Every Phase 7 client module must stay inside
`migration/`; importing `src`, `@supabase/supabase-js`, or `src/lib/supabase.js` is forbidden by the
existing isolation check.

## Common API rules

All routes use `/api/v1`, strict camelCase JSON, the Phase 6 envelopes, a fresh correlation ID, and
`Cache-Control: no-store`. Requests reject unknown body fields and query parameters. Money uses a
two-decimal string. Dates use `YYYY-MM-DD`. Instants use UTC with exactly three fractional digits.
Declared nullable response fields are present as `null`.

Every collection uses the Phase 6 cursor contract with default `limit=50` and maximum `100`.
Sorts use at most three published fields and add ascending `id` as the last tie-breaker. Text search
is Unicode NFC, trimmed, case-insensitive, 1 to 100 characters, and contains no wildcard language.

### Scalar and enum mapping

The API does not expose the title-case database values as new enum spellings.

| API field | API values | Database mapping |
| --- | --- | --- |
| `employmentStatus` | `active`, `probation`, `on_leave`, `terminated` | `Active`, `Probation`, `On Leave`, `Terminated` |
| `visaType` | null, `employment_visa`, `investor_visa`, `dependent_visa`, `tourist_temp`, `exempt` | Empty string, `Employment Visa`, `Investor Visa`, `Dependent Visa`, `Tourist (Temp)`, `Exempt` |
| `workLocationType` | `mainland`, `free_zone` | `Mainland`, `Free Zone` |
| `gender` | null, `male`, `female`, `other` | Empty string, `Male`, `Female`, `Other` |
| `maritalStatus` | null, `single`, `married`, `divorced`, `widowed` | Empty string, `Single`, `Married`, `Divorced`, `Widowed` |
| `role` | `employee`, `manager` | Native `app_role` values |
| `changeType` | `title_change`, `department_change`, `salary_change`, `status_change` | Exact database values |
| `shiftCategory` | `morning`, `afternoon`, `night`, `flexible` | Exact database values |

Nullable dates return null and accept explicit null when the field is writable and clearable.
Required non-null database text uses `""` for an allowed empty value. The nullable API enums above
map a database empty string to null and accept null to clear it. UUID values use the Phase 6
canonical lowercase form.

Money fields are nonnegative strings with exactly two decimal places and the Phase 4 `numeric(12,2)`
bounds. `nafisQuotaPercent` is a plain two-decimal string from `0.00` through `100.00`.
`defaultSalaryDay` is null or an integer from 1 through 31. `minStaff` is an integer of at least zero.
Emails are trimmed before validation; work email is also lowercased before storage. Other free text is
trimmed where leading or trailing space has no business meaning. The API never turns a parse failure
into zero or a default.

### Branch selection state

The admin client stores a chosen branch ID in memory and may retain it in `sessionStorage` for the
current browser tab. It sends no branch header until `GET /api/v1/branches` confirms that the stored
ID is still in the current tenant response. Missing, stale, or inaccessible selection opens the
branch chooser. It does not select the first branch. A 404 from later branch verification clears the
client selection and returns to the chooser without retrying against another branch.

Managers and employees store no branch selector. Their branch comes from the current PostgreSQL
profile and employee link on every request.

An admin branch-owned request requires `X-Workloop-Branch-ID`. The service verifies the selected
branch in the same authorized transaction as the operation. Manager and employee scope comes from
their linked employee row and rejects that header. `GET /api/v1/branches`, `POST /api/v1/branches`,
and company endpoints are selector-free. Existing-branch detail, update, and delete require the admin
header and path ID to match.

The service owns one authorized transaction. Handlers do not perform business lookups. Repositories
use the supplied connection and never commit. Every employee change, job-history row, direct-report
reassignment, portal-role change, and audit event either commits together or rolls back together.

Missing and inaccessible UUIDs both return `404 resource_not_found`. A visible row with a denied
field or transition returns `403 operation_not_permitted`. Ordinary optimistic mismatch returns
`409 state_conflict`. Named workflows must register their safe conflict code before a route ships.
No response or log exposes a table, constraint, SQL value, token claim, guessed UUID, other tenant,
or raw database error.

Phase 7 adds these safe workflow conflicts to the registry before any matching route ships:

| Code | Status | Message | Use |
| --- | ---: | --- | --- |
| `branch_conflict` | 409 | `Branch state prevents this operation` | Duplicate name or a guarded delete with retained use. |
| `employee_conflict` | 409 | `Employee state prevents this operation` | Visible employee uniqueness or a non-lifecycle state guard. |
| `employment_transition_conflict` | 409 | `Employment state changed` | A named status, probation, termination, or archive transition no longer applies. |
| `manager_reassignment_conflict` | 409 | `Reporting relationships changed` | The locked report set, expected report versions, or replacement eligibility changed. |
| `portal_role_conflict` | 409 | `Portal role state changed` | The linked profile, expected role, eligibility, or role transition changed. |
| `department_conflict` | 409 | `Department state prevents this operation` | Duplicate name, cycle, excessive depth, rename conflict, or retained use. |
| `staffing_rule_conflict` | 409 | `Staffing rule state prevents this operation` | Duplicate branch, department, and category or a stale relationship. |

Malformed fields and hierarchy depth known from the request use `422 validation_failed`. A conflict
found only after a scoped locked read uses the table above. Inaccessible related IDs still use the
generic 404.

## Organization projections and operations

### Projections

| Projection | Fields |
| --- | --- |
| Company admin | `id`, `name`, `sector`, `nafisQuotaPercent`, `enableNafis`, `createdAt`, `updatedAt` |
| Safe employer | `companyName`, `branchName`, `branchContactEmail`, `branchAddress`, `workLocationType`, `freeZoneName`, and `logoUrl` |
| Branch admin | `id`, `name`, `molEmployerId`, `defaultBankRoutingCode`, `address`, `contactEmail`, `defaultSalaryDay`, `workLocationType`, `freeZoneName`, `logoUrl`, `enableStaffingRules`, `enableBiometricImport`, `createdAt`, and `updatedAt` |
| Branch safe | `id`, `name`, `address`, `contactEmail`, `workLocationType`, `freeZoneName`, and `logoUrl` |

The company projection never contains branch fields. Branch projections never repeat legal company
name, sector, Nafis percentage, or Nafis enablement. `defaultSalaryDay` is nullable because the
approved schema allows null. Empty text stays `""`; it does not become null.

### Routes

| Operation | Scope and contract |
| --- | --- |
| `GET /api/v1/company` | Admin tenant read. Returns Company admin. No branch header. |
| `PATCH /api/v1/company` | Admin tenant write of `name`, `sector`, `nafisQuotaPercent`, or `enableNafis`. Requires `expectedUpdatedAt`. Company create and delete remain provisioning-only. |
| `GET /api/v1/employer` | Manager or employee self-context read. Returns Safe employer derived from the profile company and linked branch. No caller company or branch ID. |
| `GET /api/v1/branches` | Admin receives the tenant's branches. Manager or employee receives one Branch safe row for the linked branch. Filters: `search`. Sort allowlist: `name`, `createdAt`; default `name`. |
| `POST /api/v1/branches` | Admin selector-free create. Writable fields are the Branch admin settings except IDs and timestamps. Requires an idempotency key under the recommendation below. |
| `GET /api/v1/branches/{branchId}` | Admin selected-branch detail. Staff do not use a path ID for employer context. |
| `PATCH /api/v1/branches/{branchId}` | Admin selected-branch update. Writable fields are `name`, `molEmployerId`, `defaultBankRoutingCode`, `address`, `contactEmail`, `defaultSalaryDay`, `workLocationType`, `freeZoneName`, `logoUrl`, `enableStaffingRules`, and `enableBiometricImport`. Requires `expectedUpdatedAt`. |
| `DELETE /api/v1/branches/{branchId}` | Admin selected-branch guarded delete with `expectedUpdatedAt` query parameter. Returns 204. Any employee, department, staffing rule, audit event, or other retained reference blocks it. |

Changing `defaultBankRoutingCode` does not rewrite draft payroll runs in Phase 7. The legacy
`cascadeBankRoutingCodeToDrafts` behavior belongs to Phase 9 and stays on the legacy payroll writer.

## Employee projections

### Admin list

The admin list contains `id`, `empNo`, `name`, `photoUrl`, `workEmail`, `jobTitle`, `department`,
`reportingManagerId`, `employmentStartDate`, `probationEndDate`, `employmentStatus`, `active`,
`basicSalary`, `housingAllowance`, `transportAllowance`, `otherAllowances`, `bankName`, and
`updatedAt`. Money fields are strings.

Filters are `search`, `employmentStatus`, `department`, `active`, and `reportingManagerId`. Search
covers name, employee number, work email, MOL ID, and labour card number. `reportingManagerId=null`
means no manager. Sort allowlist is `name`, `empNo`, `employmentStartDate`, `basicSalary`, `createdAt`,
and `updatedAt`; default is `name`. Nullable dates sort last in both directions.

### Admin detail

The admin detail contains every list field plus `molId`, `bankRoutingCode`, `iban`, `allowance`,
`personalEmail`, `phone`, `dateOfBirth`, `gender`, `maritalStatus`, `homeCountryAddress`,
`emergencyContactName`, `emergencyContactRelationship`, `emergencyContactPhone`,
`probationExtended`, `terminationDate`, `terminationReason`, `otherAllowancesLabel`,
`bankAccountHolder`, `nationality`, `visaType`, `visaNumber`, `visaExpiry`, `passportNumber`,
`passportExpiry`, `emiratesId`, `emiratesIdExpiry`, `labourCardNumber`, `labourCardExpiry`,
`sponsoringEntity`, `workLocationType`, `freeZoneName`, `nafisRegistrationNo`, `licenceAuthority`,
`licenceNumber`, `licenceExpiry`, and `createdAt`.

It excludes `companyId`, `branchId`, `shiftId`, identity-provider fields, `authUserId`, contract
history, documents, insurance, and arbitrary joined rows. The server owns scope even when the
frontend already knows an ID.

### Employee self

The self projection contains the admin detail fields needed to describe the employee's own current
record, but excludes `reportingManagerId`, `active`, internal scope IDs, and audit fields. It adds
`reportingManager` as either null or `{ id, name, jobTitle }`. Salary, bank, and government identity
fields are visible only to that employee. The only writable self fields are `phone`, `personalEmail`,
`emergencyContactName`, and `emergencyContactPhone`.

### Direct report

The manager projection contains `id`, `empNo`, `name`, `photoUrl`, `jobTitle`, `department`,
`employmentStartDate`, `probationEndDate`, and `employmentStatus`. It excludes salary, allowances,
bank data, government identifiers, home address, personal contact data, emergency contact data,
licence numbers, and portal role. The route joins the current one-level reporting relationship on
every request. There is no caller-supplied manager ID and no recursive team option.

### Job history

The admin-only projection contains `id`, `employeeId`, `changedAt`, `changedByAppUserId`,
`changeType`, `oldValue`, `newValue`, and `reason`. `changedByAppUserId` is nullable for retained
system or migrated history. `changeType` is exactly `title_change`, `department_change`,
`salary_change`, or `status_change`. The API never accepts a history row as client input.

`GET /api/v1/employees/{employeeId}/job-history` and
`GET /api/v1/employee-job-history` use cursor pagination. The branch collection filters are
`employeeId`, `changeType`, `changedFrom`, and `changedTo`. Sort allowlist is `changedAt`; default is
`-changedAt`. Equal timestamps sort by ascending `id`.

### Employee read routes

| Operation | Scope |
| --- | --- |
| `GET /api/v1/employees` | Admin selected branch. Returns admin list. |
| `GET /api/v1/employees/{employeeId}` | Admin selected branch. Returns admin detail. |
| `GET /api/v1/employees/self` | Eligible manager or employee. Returns self. |
| `GET /api/v1/employees/direct-reports` | Eligible manager only. Returns current one-level direct reports. Filters: `search`, `employmentStatus`. Sort allowlist: `name`, `empNo`, `employmentStartDate`; default `name`. |
| `GET /api/v1/employees/{employeeId}/portal-role` | Admin selected branch. Returns the portal-role projection below. |

## Employee writes and transactions

### Create and ordinary edit

Admin create derives company and branch, actor, ID, timestamps, and audit fields. It may accept the
admin-detail business fields except termination fields, `active`, contract fields, branch,
`shiftId`, and identity fields. Initial `employmentStatus` may be `active`, `probation`, or
`on_leave`, but not `terminated`. A supplied manager must be active, eligible, and in the same
branch. Work email is trimmed and lowercased before the existing tenant-wide uniqueness check.

`PATCH /api/v1/employees/{employeeId}` is an ordinary admin edit. It accepts `empNo`, `name`,
`molId`, bank fields, personal fields, emergency fields, employment start date, government and
licence fields, and employee-specific work-location fields. It rejects job title, department,
manager, salary and allowances, `active`, employment status, probation fields, termination fields,
contract fields, branch, shift, and portal role. Those values use named workflows or belong to a
later phase. The request requires `expectedUpdatedAt`.

`PATCH /api/v1/employees/self/contact` accepts only the four approved self-contact fields and
`expectedUpdatedAt`. Omission leaves a field unchanged. Explicit null is invalid because the target
columns are non-null; `""` clears an optional text value.

### CSV import

The recommendation is create-only. The target has no unique MOL ID or employee-number constraint,
so the legacy browser-side MOL-ID upsert cannot identify an existing employee safely without a
schema change. A create-only batch preserves the approved schema and prevents an import from
silently overwriting current pay or reporting data.

`POST /api/v1/employee-imports` accepts at most 500 rows and 1 MiB. The client parses CSV only to
show a preview. It sends strict JSON rows with `rowNumber`, `empNo`, `name`, `molId`, `bankName`,
`bankRoutingCode`, `iban`, `basicSalary`, and `allowance`. The server repeats all validation, derives
scope, and inserts all rows in one transaction. Any invalid row returns `422 validation_failed` with
bounded details keyed by `body.rows[index]`; no row commits. A duplicate normalized nonempty work
email conflicts, but the current CSV contract has no work-email column. MOL ID and employee number
are not treated as unique.

A later upsert proposal must first define a schema-backed identity key. Every update would then run
the same job, salary, department, status, and manager workflows as an individual change. It may not
use a browser merge or a bulk table upsert.

### Named history workflows

| Workflow | Employee fields | History |
| --- | --- | --- |
| Title change | `jobTitle` | One `title_change` row. |
| Department change | `department` | One `department_change` row. The new department must exist in the selected branch. Empty department is allowed only when the product owner approves unassigned employees. |
| Salary change | `basicSalary`, `allowance`, `housingAllowance`, `transportAllowance`, `otherAllowances`, `otherAllowancesLabel` | One `salary_change` row. `oldValue` and `newValue` are canonical compact JSON objects with every compensation field and two-decimal money strings. |
| Employment status change | `employmentStatus`, with workflow-owned `active`, `terminationDate`, and `terminationReason` | One `status_change` row. |
| Manager change | `reportingManagerId` | No job-history row because none of the four approved types describes reporting-line changes. The atomic `audit_events` row records action `employee_manager_changed`. |

Every named workflow locks the employee, checks `expectedUpdatedAt`, validates the current state,
updates the employee, appends any required history, and appends the approved safe audit event before
commit. The body never supplies actor, history text, scope, timestamps, or audit metadata.

| Route | Required body fields beyond `expectedUpdatedAt` |
| --- | --- |
| `POST /api/v1/employees/{employeeId}/title-change` | `jobTitle`, `reason` |
| `POST /api/v1/employees/{employeeId}/department-change` | `department`, `reason` |
| `POST /api/v1/employees/{employeeId}/salary-change` | Every compensation field listed above, plus `reason` |
| `POST /api/v1/employees/{employeeId}/status-change` | `employmentStatus`, `reason`, and complete `reportReassignments` when the target is a manager becoming ineligible |
| `POST /api/v1/employees/{employeeId}/manager-change` | Nullable `reportingManagerId`, `reason` |
| `POST /api/v1/employees/{employeeId}/probation-confirmation` | `reason` |
| `POST /api/v1/employees/{employeeId}/probation-extension` | `probationEndDate`, `reason` |
| `POST /api/v1/employees/{employeeId}/probation-termination` | `reason`, complete `reportReassignments` when required |
| `POST /api/v1/employees/{employeeId}/archive` | `reason`, complete `reportReassignments` when required |

Reasons are trimmed strings from 1 through 1,000 characters. A salary-change request supplies the
complete compensation group so its one history entry has an unambiguous before and after snapshot.

### Probation and archive mapping

| Action | Result | History and audit |
| --- | --- | --- |
| Confirm | `Probation` to `Active`; clears `probationEndDate`; keeps the record active | `status_change` from `Probation` to `Active`, plus `employee_probation_confirmed` audit. |
| Extend | Keeps status `Probation`; sets a later `probationEndDate`; sets `probationExtended=true` | No job-history row. Using `status_change` when status did not change would overload the approved type. Use `employee_probation_extended` audit with the changed field names and required reason. |
| Terminate during probation | `Probation` to `Terminated`; sets `active=false`, trusted business date, and required reason | `status_change` from `Probation` to `Terminated`, plus `employee_probation_terminated` audit. |
| Archive outside probation | Eligible non-terminated state to `Terminated`; sets `active=false`, trusted business date, and required reason | `status_change`, plus `employee_archived` audit. No hard delete. |

This mapping adds no job-history type and leaves contract renewal, conversion, and non-renewal to
Phase 11. The legacy `contract_converted`, `contract_renewed`, and `contract_not_renewed` labels are
invalid under the approved target check and must not move into Phase 7.

### Manager reassignment

Manager demotion, archive, or termination accepts `reportReassignments`, an array containing exactly
one entry for every current direct report. Each entry has `employeeId`, `newManagerId`, and
`expectedUpdatedAt`. The replacement must be another active, eligible manager in the same company
and branch. Null replacement, self-management, duplicate report IDs, cycles, missing reports, extra
reports, and cross-branch managers fail the whole transaction.

The service acquires relationship locks, then locks the affected employees in ascending UUID order.
It re-reads the complete current report set after locking. It applies every reassignment, changes the
manager state or role, appends safe audit events, and commits once. A concurrent report change or
incomplete array returns a workflow-specific conflict and changes nothing. The same transaction rule
must be reused if a later identity phase disables a manager account.

### Portal role

The admin projection is `{ employeeId, activated, role }`. `role` is `employee`, `manager`, or null.
`activated=false` and null role mean that no eligible linked profile exists. It does not expose the
Keycloak subject, issuer, email, profile company, app-user status, or app-user ID.

`PUT /api/v1/employees/{employeeId}/portal-role` accepts `role`, `expectedRole`, and, when demoting a
manager, the complete `reportReassignments` array. Only `employee` and `manager` are valid. The caller
cannot change their own role. The employee must have one same-company linked profile, active account,
active employee record, and eligible employment status. It never creates a profile or Keycloak
account. Role change, report reassignment, and `employee_portal_role_changed` audit commit together.

## Department contract

The projection is `id`, `name`, `parentId`, `headEmployeeId`, `color`, `description`, `sortOrder`, and
`createdAt`. Null parent and head are returned as null. A branch may have only one exact department
name under the approved database constraint.

`GET /api/v1/departments` is admin-only and selected-branch scoped. Filters are `search`, `parentId`,
and `headEmployeeId`. Sort allowlist is `sortOrder`, `name`, and `createdAt`; default is
`sortOrder,name`. Staff receive department labels through employee projections, not this route.

Admin create and update accept `name`, `parentId`, `headEmployeeId`, `color`, `description`, and
`sortOrder`. Parent and head must be in the selected branch. The service prevents self-parenting and
all cycles after locking the affected hierarchy. The supported depth is 20 levels. A change that
would exceed it fails validation. Head employees must be active and not terminated.

The table has no `updated_at`. Update and delete therefore require `expected`, containing the exact
previous `name`, `parentId`, `headEmployeeId`, `color`, `description`, and `sortOrder`. The service
locks the row and compares that snapshot. A mismatch returns `state_conflict` without a schema
change.

Delete returns 204 only when no child department, employee department label, department head use,
staffing rule, retained audit, or other reference remains. The server checks every guard in the same
transaction. Renaming a department must also update matching `employees.department` and
`department_staffing_rules.department` in one transaction, with `department_change` history for each
affected employee. Because this is a multi-row history-producing workflow, it uses an idempotency
key and deterministic lock order.

## Staffing-rule contract

The projection is `id`, `department`, `shiftCategory`, `minStaff`, `effectiveFrom`, and
`effectiveTo`. Categories are `morning`, `afternoon`, `night`, and `flexible`. `minStaff` is an
integer at least zero. Either date may be null; when both are present, `effectiveTo` is not before
`effectiveFrom`.

`GET /api/v1/department-staffing-rules` is admin-only and selected-branch scoped. Filters are
`department`, `shiftCategory`, and `effectiveOn`. Sort allowlist is `department`, `shiftCategory`,
`effectiveFrom`, and `effectiveTo`; default is `department,shiftCategory`. Null dates sort last.

Create and update accept the projection's mutable fields. Department must name an existing selected
branch department. The approved unique key is branch, department, and category. Create is not an
implicit upsert. A duplicate is a safe conflict. As with departments, update and delete use an exact
`expected` snapshot because the table has no `updated_at`. Delete returns 204. Phase 7 does not
evaluate rosters or staffing compliance.

## Concurrency summary

| Resource | Precondition |
| --- | --- |
| Company, branch, employee | Required `expectedUpdatedAt`, compared in the locked scoped update. |
| Department | Exact previous mutable snapshot in `expected`. |
| Staffing rule | Exact previous mutable snapshot in `expected`. |
| Portal role | `expectedRole`, plus complete locked report set on manager demotion. |
| Job history | Immutable. No update or delete. |

Successful responses return the authoritative new representation. A client that receives
`state_conflict` refreshes and asks the user to review the current state. It does not replay with a
new precondition automatically.

## Idempotency recommendation and schema stop

Require the Phase 6 `Idempotency-Key` contract for branch create, employee create, employee import,
department rename, title change, department change, salary change, status change, probation action,
archive, manager change, and portal-role change. These operations can create duplicate business rows
or append duplicate history and audit events after a lost response. Ordinary snapshot-protected
patches, self-contact update, simple department and staffing create, update, or delete do not require
the header.

The current backend parses the header but has no general idempotency record. The approved Phase 4
schema also has no table that can atomically reserve a key and replay the committed response as Phase
6 requires. Audit metadata cannot replace that record because it has no claim uniqueness or stored
response contract.

Approved decision `7A-D5` requires a separately reviewed schema-design amendment for the exact Phase
6 idempotency record before 7C, 7F, or 7G implements one of the listed mutations. The disposition is
approved, but the exact table, constraints, retention rules, and migration are not. The affected
implementation remains blocked until that design is approved. Phase 7A does not add the table.

## Cutover units and rollback

The draft records are in `docs/migration/phase-7/cutover-records`. They all remain in `preparation`,
with legacy Supabase as the read and write authority and every migration feature path frozen.

| Unit | Release part | Cutover rule | Rollback dependency |
| --- | --- | --- | --- |
| `phase7-organization-context` | 7B | Freeze the matching legacy organization reads after all migration company, employer, and branch consumers are ready. Migration reads then become authoritative. Legacy writes remain authoritative. | Roll back before any reader depends on migration-only response fields. |
| `phase7-organization-administration` | 7C | Freeze legacy company and branch writers first. Enable the migration writer only after the freeze check passes. | Freeze migration writes, restore legacy writes, then restore legacy reads if needed. |
| `phase7-employee-directory` | 7D | Switch list, detail, self, direct-report, and job-history consumers together. No migration employee write exists yet. | Restore every Phase 7 employee reader together. Later-domain consumers remain untouched. |
| `phase7-departments` | 7E | Freeze legacy department reads and writes, then switch both authorities together. | Roll back before employee writing depends on migration departments. |
| `phase7-staffing-rules` | 7E | Freeze legacy staffing reads and writes, then switch independently from departments once references validate. | Roll back independently only while the employee writer has no dependency. |
| `phase7-employee-administration` | 7F | Freeze `saveEmployee` and `saveEmployees` paths before enabling migration create, edit, or import. | Freeze migration writes before restoring legacy writes. Reads may stay only if the restored writer remains response-compatible. |
| `phase7-employee-lifecycle` | 7G | Freeze legacy archive, probation, job-history, manager, and portal-role writers before enabling the migration workflows. | Roll back this unit before employee administration, departments, organization writes, or reads. Never delete committed history or audit. |

The forward dependency order is organization context, organization administration, employee
directory, departments, staffing rules, employee administration, then employee lifecycle. Rollback
uses the reverse order. At every point `writableSystems` contains exactly one system. Dual-write is
prohibited, including background or best-effort history writes.

The synthetic refresh evidence in the draft records checks only the two-person Phase 6 identity map
against the record declaration. It proves no Phase 7 business data, API, database behavior, or
cutover. Each implementation part must replace its planned locators, run its feature verifier, and
record fresh synthetic evidence before authority changes.

## Approved decision register

| ID | Decision | Approval |
| --- | --- | --- |
| `7A-D1` | Keep legal fields on `companies` and operating fields on `branches` exactly as listed above. | Approved 2026-09-09 |
| `7A-D2` | Make CSV import create-only. Do not match existing employees by MOL ID until a separately approved unique identity exists. | Approved 2026-09-09 |
| `7A-D3` | Append one history row in the same transaction for title, department, salary, and status changes. Use audit only for manager and portal-role changes. | Approved 2026-09-09 |
| `7A-D4` | Map probation confirmation and termination to `status_change`. Record extension in audit only, without a new or overloaded job-history type. | Approved 2026-09-09 |
| `7A-D5` | Require idempotency for the listed non-repeatable mutations and require a separate exact schema amendment before implementation. | Disposition approved 2026-09-09 |
| `7A-D6` | Use `updatedAt` preconditions where available and exact locked snapshots for departments, staffing rules, and portal roles. | Approved 2026-09-09 |
| `7A-D7` | Require a complete per-report reassignment array for manager demotion, archive, or termination and commit it with the state change. | Approved 2026-09-09 |
| `7A-D8` | Use the seven cutover units and reverse rollback order above. Keep one writable system. | Approved 2026-09-09 |
| `7A-D9` | Use the routes, field projections, filters, sorts, null rules, and writable-field lists in this document. | Approved 2026-09-09 |

Phase 7A closes when every draft record validates, documentation checks pass, the path-routed GitHub
workflow passes, and the branch is clean and synchronized. Approval and validation are recorded in
`PART_7A_COMPLETION.md`.
