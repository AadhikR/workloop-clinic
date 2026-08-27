# Supabase Dependency Inventory

## Scope

This Phase 0 inventory covers every Supabase dependency found under `src/`:

- Client creation and environment configuration
- Auth operations and auth-state listeners
- Table reads, joins, filters, counts, inserts, updates, upserts, and deletes
- RPC calls and visible request/response assumptions
- Storage buckets, paths, uploads, removals, and signed URLs
- Direct Supabase calls in components
- Converters and returned shapes where visible
- Realtime usage or absence
- Dynamic and ambiguous contracts that require migration tests

The inventory found 24 modules that import or create the Supabase client:

- 1 client module
- 1 auth context
- 15 utility/data modules
- 7 employee components with direct calls

Role abbreviations:

| Abbreviation | Role |
| --- | --- |
| A | Admin or HR |
| M | Manager |
| E | Employee self-service |
| Any | Any authenticated caller; effective access depends on RLS |

Operation abbreviations:

| Abbreviation | Operation |
| --- | --- |
| R | Read |
| W | Write |
| S | Supabase Storage operation |
| Auth | Supabase Auth operation |

Most administrative rows are explicitly scoped with `user_id = session.user.id` or depend on an equivalent RLS policy. Unscoped reads are identified below.

## Client

### `src/lib/supabase.js`

- Imports `createClient` from `@supabase/supabase-js`.
- Reads `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- Throws during module initialization if either variable is absent.
- Exports `supabase = createClient(supabaseUrl, supabaseAnonKey)`.
- Uses default client options. There is no custom schema, auth persistence, fetch implementation, header, or Realtime configuration.

## Authentication

### `src/context/AuthContext.jsx`

#### `AuthProvider`

| Operation | Role | Mode | Supabase dependency | Return or state contract |
| --- | --- | --- | --- | --- |
| Auth-state subscription | Any | Auth | `supabase.auth.onAuthStateChange`; handles `INITIAL_SESSION` and `TOKEN_REFRESHED`; calls `subscription.unsubscribe()` on cleanup | Updates context `user`, `profile`, and initial `loading` state. This is an Auth listener, not Postgres Realtime. |
| Missing-profile recovery | Any | R/W | R `companies.select('id').limit(1).maybeSingle()`; may call `link_employee_account`; may W `user_profiles.upsert(..., { onConflict: 'user_id' })` | Resolves `{ role, companyUserId, employeeId }` or `null`. |
| `createCompany` | A | Auth/W | `auth.signUp`; `companies.insert({ user_id, name })`; `user_profiles.upsert` as admin | Sets context to the new Auth user and admin profile. No explicit return. |
| `signInAsAdmin` | A | Auth/R/W | `auth.signInWithPassword`; R `companies.select('id').limit(1).maybeSingle()`; possible `auth.signOut`; W `user_profiles.upsert` as admin | Sets context user/profile. Requires a visible company row. |
| `signInAsEmployee` | E/M | Auth/R/W | `auth.signInWithPassword`; `getProfile`; `link_employee_account`; possible `auth.signOut`; W `user_profiles.upsert` as employee | Reuses an existing employee/manager profile or creates an employee profile from RPC output. |
| `signUpAsEmployee` | E | Auth/W | `auth.signUp`; `link_employee_account`; possible `auth.signOut`; W `user_profiles.upsert` as employee | Creates and links the account but deliberately does not update context or auto-login. |
| `signOut` | Any | Auth | `supabase.auth.signOut()` | Throws the Auth error if present. |
| `resetPassword` | Any | Auth | `supabase.auth.resetPasswordForEmail(email, { redirectTo: window.location.origin })` | No data returned; maps Auth errors to user-facing errors. |

`mapAuthError` translates selected Supabase messages for invalid credentials, unconfirmed email, rate limiting, duplicate registration, and password length.

### `src/utils/profileStorage.js`

| Exported symbol | Role | Mode | Table, RPC, or bucket contract | Converter or returned shape |
| --- | --- | --- | --- | --- |
| `getProfile` | Any | R | `user_profiles.select('role, company_user_id, employee_id').maybeSingle()`; caller scoping relies on RLS | `{ role, companyUserId, employeeId }` or `null` |
| `createAdminProfile` | A | Auth/W | Optional `auth.getSession`; `user_profiles.insert({ user_id, role:'admin', company_user_id, employee_id:null })`; ignores `23505` | Always returns a synthetic admin profile when a user is available, including after other persistence errors |
| `linkEmployeeAccount` | E/M | RPC W | `link_employee_account()` | Raw RPC object; documented success shape is `{ success, already_linked, employee_id, company_user_id, employee_name }`, failure `{ success:false, error }` |
| `getMyEmployeeRecord` | E/M | Auth/R | `auth.getSession`; `employees.select('*').eq('auth_user_id', user.id).maybeSingle()` | Raw snake_case employee row or `null` |
| `getMyCompany` | E/M | R | Calls `getProfile`; `companies.select('*').eq('user_id', companyUserId).order('created_at').limit(1).maybeSingle()` | Raw company row or `null` |
| `getEmployeePortalRole` | A | RPC R | `admin_get_employee_portal_role({ p_employee_id })` | Raw scalar role or `null` |
| `setEmployeePortalRole` | A | RPC W | `admin_set_employee_portal_role({ p_employee_id, p_role })` | No data used |
| `getMyPayslips` | E | R | `payslips.select('*').order('period', descending)` | CamelCase payslips; parses `grossPay` and `netPay`; preserves `data_snapshot` as `snapshot` |
| `getMyDocuments` | E | R/S | `employee_documents.select('*').order('uploaded_at', descending)`; `employee-documents.createSignedUrl(storage_path, 3600)` per object | CamelCase documents with `signedUrl`; signed URL failures leave an empty URL |

## Core Data Module

### `src/utils/storage.js`

Private `getSessionUser` and `getUserId` use `supabase.auth.getSession()`. Converters return component-facing camelCase objects unless noted.

#### Companies and branches

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getCompanies` | A | R | `companies.select('*').order('created_at', ascending)` | `dbToCompany[]` |
| `getCompany` | A | R | Dynamic `companies.select('*')`; optional `.eq('id', id)`; `.limit(1).maybeSingle()` | `dbToCompany` or `null` |
| `saveCompany` | A | W | Update `companies` by ID, or insert with `.select().single()`; uses `companyToDb` | Update returns `undefined`; insert returns `dbToCompany` |
| `saveCompanyLogo` | A | W | `companies.update({ logo_url }).eq('id', companyId)` | `{ ok: true }`; the logo is stored in the table, not Storage |
| `cascadeBankRoutingCodeToDrafts` | A | W/R | `payroll_runs.update({ scr_bank_routing_code }).eq('company_id').eq('status','draft').eq('approval_status','draft').select('id')` | `{ count }` from updated rows |
| `createBranch` | A | W | `companies.insert(row).select().single()` | `dbToCompany` |
| `deleteBranch` | A | R/W | Count-only `employees.select('id', { count:'exact', head:true }).eq('company_id').eq('active',true)`; then `companies.delete().eq('id')` | No return; rejects deletion when active employees exist |

`dbToCompany` maps company identity, branch, MOL, bank, address, salary-day, work-location, logo, sector, Nafis, and feature-toggle fields. `companyToDb` only sends feature-toggle columns when the caller supplied them.

#### Employees and job history

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getEmployees` | A | R | `employees.select('*').order('created_at')`; optional `.or('company_id.eq.<id>,company_id.is.null')` | `dbToEmployee[]` |
| `saveEmployee` | A | W | UUID-like IDs use `employees.update`; otherwise `employees.insert`; both `.select().single()` | `dbToEmployee` |
| `saveEmployees` | A | W | Existing rows `employees.upsert(rows, { onConflict:'id' })`; new rows bulk `insert` | No return |
| `deleteEmployee` | A | W | `employees.delete().eq('id', id)` | No return |
| `archiveEmployee` | A | W | Updates `active=false`, `employment_status='Terminated'`, and `termination_date` | No return |
| `getJobHistory` | A | R | `employee_job_history.select('*').eq('employee_id').order('changed_at', descending)` | CamelCase history entries |
| `getAllJobHistory` | A | R | `employee_job_history.select('*').order('changed_at', descending)` | CamelCase history entries |
| `addJobHistoryEntry` | A | W | Inserts `employee_job_history` with caller identity and stringified old/new values | No return |

`dbToEmployee` maps WPS, personal, emergency-contact, job, employment, salary, Auth-link, company, UAE-compliance, and professional-licence fields. `employeeToDb` performs the reverse mapping and numeric/date normalization.

#### Payroll, payslips, WPS, and approvals

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getPayrolls` | A | R | R `payroll_runs.select('*')`, optional company filter; then R `payroll_entries.select('*').in('payroll_run_id', runIds)` | Payroll objects with `entries: dbToEntry[]` |
| `savePayroll` | A | W/RPC W | `payroll_runs.upsert(runRow, { onConflict:'id' })`; if entries exist, `replace_payroll_entries({ p_payroll_run_id, p_entries })` | No return |
| `savePayrolls` | A | W | Sequential calls to `savePayroll` | No return |
| `deletePayroll` | A | W | `payroll_runs.delete().eq('id', id)`; assumes entry cascade | No return |
| `createPayslipRecords` | A | W | `payslips.upsert(rows, { onConflict:'payroll_run_id,employee_id' })`; writes gross/net and entry snapshot | No return; errors are logged, not thrown |
| `saveWpsTracking` | A | W | Updates WPS status, timestamps, and reference on `payroll_runs` | No return |
| `saveComplianceOverride` | A | Auth/W | `auth.getSession`; inserts `compliance_overrides` with type, employee ID array, and reason | No return |
| `submitPayrollForApproval` | A | W | Updates `payroll_runs` to `pending_approval`; inserts `payroll_approval_log` action `submitted` | No return; calls are not atomic |
| `approvePayroll` | A/approver | W | Updates `payroll_runs` approval fields; inserts log action `approved` | No return; calls are not atomic |
| `rejectPayroll` | A/approver | W | Returns approval state to draft and records rejection fields; inserts log action `rejected` | No return; calls are not atomic |
| `recallPayrollApproval` | A | W | Returns approval state to draft; inserts log action `recalled` | No return; calls are not atomic |
| `getPayrollApprovalLog` | A | R | `payroll_approval_log.select('*').eq('payroll_run_id').order('created_at', descending)` | `{ id, action, performedBy, notes, createdAt }[]` |

`dbToEntry` parses numeric payroll fields, preserves JSON allowances/deductions, maps WPS fields, and treats `du_cost` as `leaveDeduction`. `entryToDb` performs the reverse mapping.

#### Employee documents and Storage

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getEmployeeDocuments` | A | R/S | `employee_documents.select('*').eq('employee_id').order('uploaded_at')`; signed URL from `employee-documents` for each path | `dbToDocument[]` with one-hour `signedUrl` |
| `getAllEmployeeDocuments` | A | R | `employee_documents.select('*').order('expiry_date')` | `dbToDocument[]`, without signed URLs |
| `uploadEmployeeDocument` | A | S/W/S | Upload to `employee-documents` at `<admin>/<employee>/<timestamp>_<name>`; insert `employee_documents.select().single()`; create one-hour signed URL | `dbToDocument` with `signedUrl` |
| `deleteEmployeeDocument` | A | S/W | Optional `employee-documents.remove([storagePath])`; then `employee_documents.delete().eq('id')` | No return |
| `verifyEmployeeDocument` | A | W | Updates `employee_documents` to `verified` | No return |
| `rejectEmployeeDocument` | A | W | Updates `employee_documents` to `rejected` with reason | No return |

`dbToDocument` maps document identity, type/number, file metadata, expiry, review status, submitter, rejection reason, and signed URL.

#### Insurance

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getInsurancePolicies` | A | R | `insurance_policies.select('*').order('created_at')` | `dbToInsurancePolicy[]` |
| `saveInsurancePolicy` | A | W | Insert/update `insurance_policies`, `.select().single()` | `dbToInsurancePolicy` |
| `deleteInsurancePolicy` | A | W | Delete `insurance_policies` by ID | No return |
| `getAllEmployeeInsurance` | A | R | `employee_insurance.select('*').order('expiry_date')` | `dbToEmployeeInsurance[]` |
| `getEmployeeInsurance` | A | R | `employee_insurance.select('*').eq('employee_id').maybeSingle()` | `dbToEmployeeInsurance` or `null` |
| `saveEmployeeInsurance` | A | W | Upsert on `user_id,employee_id`, `.select().single()` | `dbToEmployeeInsurance` |
| `getInsuranceDependants` | A | R | `insurance_dependants.select('*').eq('employee_id').order('created_at')` | `dbToInsuranceDependant[]` |
| `saveInsuranceDependant` | A | W | Insert/update `insurance_dependants`, `.select().single()` | `dbToInsuranceDependant` |
| `deleteInsuranceDependant` | A | W | Delete `insurance_dependants` by ID | No return |

#### Salary advances

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getAdvances` | A/E | R | Dynamic `salary_advances.select('*')`; optional employee filter | `dbToAdvance[]`; employee access depends on self-read RLS |
| `withdrawEmployeeAdvance` | E | RPC W | `employee_cancel_advance({ p_advance_id })` | Accepts boolean `true` or a legacy non-empty array as success |
| `saveAdvance` | A | W | Dynamic insert/update `salary_advances`, then `.select().single()`; retries without `repayment_start_month` when the error message names that column | `dbToAdvance` |
| `updateAdvanceBalance` | A | W | Updates `outstanding_balance` and derived status in `salary_advances` | No return |
| `getAdvanceRepayments` | A | R | `advance_repayments.select('*, payroll_runs(period)').eq('advance_id').order('paid_date', descending)` | `dbToAdvanceRepayment[]` |
| `saveAdvanceRepayment` | A | RPC W | `record_advance_repayment({ p_advance_id, p_payroll_run_id, p_amount, p_paid_date })` | Raw RPC result |

#### Nafis, offboarding, and contracts

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getNafisReports` | A | R | `nafis_reports.select('*').order('generated_at', descending)` | CamelCase report snapshots |
| `saveNafisReport` | A | W | Upsert `nafis_reports` on `user_id,period` | No return |
| `getOffboardingChecklist` | A | R | `offboarding_checklists.select('*').eq('employee_id').maybeSingle()` | `dbToChecklist` or `null` |
| `createOffboardingChecklist` | A | R/W | Upsert checklist on `user_id,employee_id`; read `offboarding_tasks`; read `offboarding_task_templates`; insert default/custom tasks if none exist | `dbToChecklist` |
| `getOffboardingTasks` | A | R | `offboarding_tasks.select('*').eq('checklist_id').order('sort_order')` | `dbToOffboardingTask[]` |
| `updateOffboardingTask` | A | W | Update task completion fields, `.select().single()` | `dbToOffboardingTask` |
| `addOffboardingTask` | A | R/W | Read highest `sort_order`; insert task with `.select().single()` | `dbToOffboardingTask` |
| `deleteOffboardingTask` | A | W | Delete `offboarding_tasks` by ID | No return |
| `saveOffboardingVisaStatus` | A | W | Update visa fields on `offboarding_checklists`, `.select().single()` | `dbToChecklist` |
| `completeOffboardingChecklist` | A | W | Update checklist status/timestamp, `.select().single()` | `dbToChecklist` |
| `getEmployeeContracts` | A | R | `employee_contracts.select('*').eq('employee_id').order('created_at', descending)` | `dbToContract[]` |
| `saveEmployeeContract` | A | W | Always inserts an `employee_contracts` lifecycle row, `.select().single()` | `dbToContract` |

## Attendance, Roster, and Biometrics

### `src/utils/attendanceStorage.js`

Private `getSessionUser` uses `supabase.auth.getSession()`.

#### Settings, shifts, and clock events

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getAttendanceSettings` | A | R | `attendance_settings.select('*').eq('user_id').limit(1).maybeSingle()` | `dbToAttendanceSettings` or `null` |
| `saveAttendanceSettings` | A | W | Update by ID or upsert on `user_id`; insert path `.select().single()` | Insert returns converted settings; update returns `undefined` |
| `getShifts` | A | R | Caller-owned active `shifts.select('*').order('name')` | `dbToShift[]` |
| `saveShift` | A | W | Insert/update `shifts`, `.select().single()` | `dbToShift` |
| `deleteShift` | A | W | Soft delete via `shifts.update({ is_active:false }).eq('id')` | No return |
| `getShiftForEmployee` | A/Any | R | `shift_assignments.select('*, shifts(*)')`; employee, effective-from, dynamic effective-to, order, and limit filters | Joined row converted through `dbToShift`, or `null` |
| `assignShift` | A | W | Insert `shift_assignments` | No return |
| `getClockEvents` | A/E | R | `clock_events.select('*')`; employee, UAE-day range, `is_superseded=false`, ascending time | `dbToClockEvent[]` |
| `recordClockEvent` | A/system | W | Insert `clock_events`, `.select().single()` | `dbToClockEvent` |
| `recordManualClockEvent` | A | W | Insert MANUAL `clock_events`, `.select().single()` | `dbToClockEvent` |

#### Attendance records, periods, and payroll integration

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getAttendanceRecords` | A/E | R | Dynamic `attendance_records.select('*')`; E path filters employee; A path first reads owned `employees.select('id')`, then `.in('employee_id', ids)`; optional date/status/period filters | `dbToAttendanceRecord[]` |
| `upsertAttendanceRecord` | A/system | W | Upsert `attendance_records` on `user_id,employee_id,date`, `.select().single()` | `dbToAttendanceRecord` |
| `computeAndSaveAttendance` | A/system | R/W | Calls `getClockEvents`, derives status locally from caller-provided employee/shift/settings/leave/holiday data, then calls `upsertAttendanceRecord` | `dbToAttendanceRecord` |
| `getAttendancePeriod` | A | R | Caller-owned `attendance_periods.select('*').eq('period').maybeSingle()` | Compact camelCase period or `null` |
| `getAttendancePeriods` | A | R | Caller-owned `attendance_periods.select('*').order('period', descending)` | Compact camelCase periods |
| `closeAttendancePeriod` | A | W | Upsert period on `user_id,period`; bulk update matching `attendance_records.period_closed=true` | No return; operations are not atomic |
| `getAttendancePayrollData` | A/payroll | R | Composes `getAttendancePeriod` and period-filtered `getAttendanceRecords` | `{ periodClosed, payrollReady, byEmployee }` |
| `getOvertimeFromRoster` | A/payroll | R | `roster_assignments.select('employee_id, planned_hours, actual_hours')`; month range; actual hours not null | Object keyed by employee ID with overtime/planned/actual totals |

#### Regularisation and audit

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getRegularisationRequests` | A | R | Caller-owned dynamic `regularisation_requests.select('*')`; optional employee/status filters | CamelCase request list |
| `submitRegularisationRequest` | A/direct | W | Insert `regularisation_requests`, `.select().single()` | Raw DB row |
| `approveRegularisationRequest` | A | R/W | Read selected request fields; update request `.select().single()`; upsert corrected `attendance_records` | Raw updated regularisation row; operations are not atomic |
| `rejectRegularisationRequest` | A | W | Update status, reason, and actor | No return |
| `addAttendanceAuditLog` | A/system | W | Insert `attendance_audit_log` | No return; insert result is not checked |

#### Rosters and shift swaps

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getRosterForMonth` | A | R | `roster_assignments.select('*, shifts(*)')`; month range; optional `.or('company_id.eq.<id>,company_id.is.null')` | `dbToRosterAssignment[]` |
| `saveRosterAssignment` | A | W | Upsert on `employee_id,date`; `.select('*, shifts(*)').single()` | `dbToRosterAssignment` |
| `deleteRosterAssignment` | A | W | Delete by employee and date | No return |
| `publishRoster` | A | W | Bulk update `published=true`; caller, month, and optional dynamic company/null filters | No return |
| `getShiftSwapRequests` | A | R | Dynamic `shift_swap_requests.select('*')`; optional status/company filters | `dbToShiftSwapRequest[]` |
| `updateShiftSwapRequest` | A | RPC W/R or W | Approval calls `admin_execute_shift_swap({ p_swap_id })`, then rereads the row. Rejection/cancellation directly updates the row. | `dbToShiftSwapRequest`; missing RPC produces a migration-specific error |
| `getMyRoster` | E | RPC R/R | Primary `employee_get_my_roster({ p_date_from, p_date_to })`; on error or empty result, reads own `employees.id`, then `roster_assignments.select(..., shifts!left(...))` | Normalized roster items with shift name/color/time/hours |
| `getMyColleagues` | E | RPC R | `employee_get_colleagues()` | `{ id, name, jobTitle }[]` |
| `requestShiftSwap` | E | RPC W | `employee_request_shift_swap({ p_target_employee_id, p_requester_date, p_target_date, p_reason })` | Raw object expected to contain `success` and optional `error` |

### `src/utils/biometricStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getBiometricMappings` | A | Auth/R | `auth.getSession`; caller-owned `biometric_mappings.select('*').order('badge_no')` | Mapped badge/device objects |
| `saveBiometricMapping` | A | Auth/W | Upsert `biometric_mappings` on `user_id,badge_no`, `.select().single()` | Mapped badge/device object |
| `deleteBiometricMapping` | A | W | Delete `biometric_mappings` by ID | No return |
| `parseBiometricCsv` | Local | None | No Supabase call | `{ badgeNo, eventType, eventTime }[]` |
| `importBiometricPunches` | A/system | Auth/R/W | Read caller-owned BIOMETRIC `clock_events` in computed range; client-side minute deduplication; bulk insert new events | `{ imported, skipped, errors }` |

## Leave Management

### `src/utils/leaveStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getLeaveSettings` | Any | R | Unscoped `leave_settings.select('*').limit(1).maybeSingle()`; depends on RLS | CamelCase settings or `null` |
| `saveLeaveSettings` | A | Auth/W | Update by ID or upsert on `user_id`, `.select().single()` on insert | Insert returns input plus ID; update returns `undefined` |
| `getLeaveTypes` | Any | R | Unscoped `leave_types.select('*').eq('is_active',true).order('sort_order')`; depends on RLS | `dbToLeaveType[]`, client-deduplicated by code |
| `seedDefaultLeaveTypes` | A | Auth/R/W | Check caller-owned leave type; bulk insert defaults | No return |
| `saveLeaveType` | A | Auth/R/W | Update existing; new type repeatedly queries caller/code until unique, then inserts `.select().single()` | `dbToLeaveType` |
| `deleteLeaveType` | A | Auth/W | Soft delete with `is_active=false` | No return |
| `uploadLeaveAttachment` | A/E | S | Upload to `employee-documents` under `<admin>/<employee>/leave/...`; create signed URL for 604800 seconds | Signed URL string or empty string |
| `getPublicHolidays` | Any | R | Dynamic unscoped `public_holidays.select('*')`; optional year filter; depends on RLS | `{ id, date, name, type, year }[]` |
| `seedPublicHolidays` | A | Auth/R/W | Check caller/year 2025; bulk insert 2025 and 2026 holidays | No return |
| `seedPublicHolidaysForYear` | A | Auth/R/W | Check caller/year; bulk insert supplied holidays | Boolean indicating whether rows were inserted |
| `savePublicHoliday` | A | Auth/W | Update by ID or insert `.select().single()` | Insert returns input plus ID; update returns `undefined` |
| `deletePublicHoliday` | A | W | Delete by ID | No return |
| `getLeaveRequests` | A/E | R | Dynamic unscoped `leave_requests.select('*')`; optional employee/status/type/year filters; depends on RLS | `dbToLeaveRequest[]` |
| `submitLeaveRequest` | A/direct | Auth/W | Insert `leave_requests.select().single()`; insert `leave_audit_log` | `dbToLeaveRequest` |
| `updateLeaveRequestStatus` | A/direct | Auth/R/W | Read current request; update request `.select().single()`; insert audit row | `dbToLeaveRequest` |
| `cancelLeaveRequest` | A/direct | R/W | Wrapper around `updateLeaveRequestStatus(..., 'Cancelled')` | `dbToLeaveRequest` |
| `getLeaveAuditLog` | A/Any | R | `leave_audit_log.select('*').eq('leave_request_id').order('created_at')` | CamelCase audit entries |
| `getLeaveQueueForManager` | M | R | Read direct reports from `employees`; parallel reads of `leave_requests` and current-year `leave_balances` using `.in(employee_id, ids)` | Converted requests enriched with probation and balance warnings |
| `approveLeaveAsManager` | M | RPC W | `manager_approve_leave({ p_request_id })` | No data used |
| `rejectLeaveAsManager` | M | RPC W | `manager_reject_leave({ p_request_id, p_reason })` | No data used |
| `getLeaveApprovalDelegates` | A | R | `leave_approval_delegates.select('*').order('from_date', descending)` | CamelCase delegates |
| `saveLeaveApprovalDelegate` | A | Auth/W | Insert/update `leave_approval_delegates`; insert `.select().single()` | Existing input or input plus DB ID/timestamp |
| `deleteLeaveApprovalDelegate` | A | W | Delete delegate by ID | No return |
| `getLeaveBalances` | A/E | R | `leave_balances.select('*').eq('employee_id').eq('leave_year')` | `dbToLeaveBalance[]` |
| `getAllLeaveBalances` | A | R | `leave_balances.select('*').eq('leave_year').order('employee_id')` | `dbToLeaveBalance[]` |
| `upsertLeaveBalance` | A | Auth/W | Upsert on `user_id,employee_id,leave_type_code,leave_year` | No return |
| `initialiseLeaveModule` | A | R/W | Calls leave-type and public-holiday seeders | No return; catches and logs failures |
| `recalculateAllBalances` | A | Auth/W | Computes rows locally and bulk upserts `leave_balances` on the composite conflict target | No return |
| `getApprovedLeavesForMonth` | A/Any | R | Approved `leave_requests` overlapping a month | `dbToLeaveRequest[]` |

`dbToLeaveRequest`, `dbToLeaveType`, and `dbToLeaveBalance` normalize snake_case fields and numeric values. Request conversion includes multi-level approval fields, leave-specific details, timestamps, and warnings.

## Appraisals and Training

### `src/utils/appraisalStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getAppraisalCycles` | A | Auth/R | Caller-owned `appraisal_cycles.select('*')` | `dbToCycle[]` |
| `saveAppraisalCycle` | A | Auth/W | Insert/update caller-owned cycle, `.select().single()` | `dbToCycle` |
| `deleteAppraisalCycle` | A | Auth/W | Delete caller-owned cycle | No return |
| `getAppraisalsForCycle` | A | R | `appraisals.select('*, appraisal_sections(*)').eq('cycle_id')` | `dbToAppraisal[]` with nested sections |
| `getMyAppraisals` | E/M | Auth/RPC R/R | `get_manager_employee_id`; fallback own `employees.id`; then appraisals joined to sections and cycles | Converted appraisals plus cycle name/range |
| `getMyTeamAppraisals` | M | RPC R/R | `get_manager_employee_id`; dynamic appraisals query joined to sections, cycles, and employees; optional `.neq('employee_id', selfId)` | Converted appraisals plus cycle and employee details |
| `managerRateSection` | M | R/W | Update one `appraisal_sections` row; read its parent and sibling ratings; update parent `appraisals` | No return; parent update result is not checked |
| `createAppraisalsForCycle` | A | Auth/R/W | Read existing appraisals; bulk insert missing rows; bulk insert default sections | `dbToAppraisal[]` |
| `saveAppraisalReview` | A/M | Auth/W | Sequentially update sections; update parent appraisal with joined sections | `dbToAppraisal` |
| `calibrateAppraisal` | A | Auth/W | Update caller-owned appraisal and return joined sections | `dbToAppraisal` |
| `deleteAppraisal` | A | Auth/W | Delete caller-owned appraisal | No return |

Converters use defensive scalar coercion. `dbToAppraisal` includes nested `dbToSection[]`.

### `src/utils/trainingStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `uploadCertificateFile` | A/M/E | Auth/S | Upload to `employee-documents` under `<uid>/certs/<employee>/...` | `{ storagePath, fileName }` |
| `getCertificateSignedUrl` | Any | S | `employee-documents.createSignedUrl(path, 3600)` | URL string or empty string |
| `getTrainingRecords` | A | R | Dynamic `training_records.select('*, employees(name)')`; optional employee filter | `dbToTraining[]` |
| `saveTrainingRecord` | A | Auth/W | Insert/update with employee join in returned selection | `dbToTraining` |
| `deleteTrainingRecord` | A | W | Delete by ID | No return |
| `getEmployeeTrainingRecords` | E | R | `training_records.select('*').eq('employee_id')` | `dbToTraining[]` without employee join |
| `getCertifications` | A | R | Dynamic `certifications.select('*, employees(name)')`; optional employee filter | `dbToCertification[]` |
| `getAllCertifications` | A | R | All certifications joined to employees, ordered by expiry | `dbToCertification[]` |
| `saveCertification` | A | Auth/W | Insert/update with employee join in returned selection | `dbToCertification` |
| `deleteCertification` | A | W | Delete by ID | No return |
| `getEmployeeCertifications` | E | R | Employee-filtered `certifications.select('*')` | `dbToCertification[]` without employee join |
| `getTeamTrainingRecords` | M | RPC R/R | `get_manager_employee_id`; query training joined to employees; optionally exclude self | `dbToTraining[]` |
| `getTeamCertifications` | M | RPC R/R | `get_manager_employee_id`; query certifications joined to employees; optionally exclude self | `dbToCertification[]` |
| `saveTeamTrainingRecord` | M | Auth/W | Insert/update team training with employee join in returned selection | `dbToTraining` |
| `deleteTeamTrainingRecord` | M | W | Delete team training by ID | No return |
| `saveTeamCertification` | M | Auth/W | Insert/update team certification with employee join in returned selection | `dbToCertification` |
| `deleteTeamCertification` | M | W | Delete team certification by ID | No return |
| `employeeSaveTrainingRecord` | E | Auth/W | Insert/update own training, `.select('*').single()` | `dbToTraining` without employee join |
| `employeeSaveCertification` | E | Auth/W | Insert/update own certification; forces `status='pending_review'` | `dbToCertification` without employee join |
| `getCmeRequirements` | A | R | Dynamic `cme_requirements.select('*, employees(name)')`; optional year filter | `dbToCmeReq[]` |
| `saveCmeRequirement` | A | Auth/W | Insert/update with employee join in returned selection | `dbToCmeReq` |
| `deleteCmeRequirement` | A | W | Delete by ID | No return |
| `getCmeTrainingRecords` | A | R | CME `training_records` with optional year range, joined to employees | `dbToTraining[]` |
| `getManagerDirectReports` | M | RPC R/R | `get_manager_employee_id`; active `employees.select('id, name, job_title').eq('reporting_manager_id')` | Raw selected rows |

## Organization and Operations

### `src/utils/departmentStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getDepartments` | A | R | `departments.select('*')`, ordered by sort order and name | `dbToDept[]` |
| `saveDepartment` | A | Auth/W | Insert or caller-scoped update, `.select().single()` | `dbToDept` |
| `deleteDepartment` | A | Auth/W | Caller-scoped delete by ID | No return |

### `src/utils/staffingStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getDeptStaffingRules` | A | Auth/R | Caller-owned `department_staffing_rules.select('*')` | `dbToRule[]` |
| `saveDeptStaffingRule` | A | Auth/W | Caller-scoped update or upsert on `user_id,department,shift_category` | No return |
| `deleteDeptStaffingRule` | A | Auth/W | Caller-scoped delete by ID | No return |

### `src/utils/assetStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getAssets` | A | Auth/R | Parallel caller-owned reads of `assets` and open `asset_assignments.select(..., employees(name))` | `dbToAsset[]` with merged `currentAssignment` |
| `saveAsset` | A | Auth/W | Insert/update caller-owned asset, `.select().single()` | `dbToAsset` |
| `deleteAsset` | A | Auth/R/W | Count-only open-assignment guard, then delete caller-owned asset | No return |
| `getAssetAssignments` | A | Auth/R | Dynamic caller-owned assignments query joined to employees and assets; optional asset/employee filters | `dbToAssignment[]` |
| `assignAsset` | A | Auth/W | Insert assignment, then update asset status to `assigned` | `dbToAssignment`; operations are not atomic |
| `returnAsset` | A | Auth/W | Close assignment, then update asset status to `available` | No return; operations are not atomic |
| `getEmployeeCurrentAssets` | E | R | Open employee-filtered assignments joined to asset details | Normalized current-asset list |

### `src/utils/incidentStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getIncidents` | A | R | Dynamic `incident_reports` query with aliased `reported_by` and `involved_emp` employee FK joins; optional company filter | `dbToIncident[]` |
| `saveIncident` | A | Auth/W | Insert/update incident; returns both aliased employee joins | `dbToIncident` |
| `deleteIncident` | A | W | Delete by ID | No return |

## Expenses, Letters, Notifications, and Tasks

### `src/utils/expenseStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getExpenseClaims` | A | Auth/R | Caller-owned `expense_claims.select('*, employees(name)')` | `dbToExpense[]` |
| `getApprovedUnpaidExpenses` | A | Auth/R | Caller-owned approved claims with null payroll run, joined to employees | `dbToExpense[]` |
| `approveExpenseClaim` | A | Auth/W | Caller-scoped status/actor update | No return |
| `rejectExpenseClaim` | A | Auth/W | Caller-scoped rejection update | No return |
| `markExpensesPaid` | A | Auth/W | Caller-scoped bulk update by claim ID list | No return |
| `deleteExpenseClaim` | A | Auth/W | Caller-scoped hard delete | No return; receipt object is not deleted |
| `deleteEmployeeExpense` | E | RPC W | `employee_delete_expense({ p_expense_id })` | Expects boolean `true` |
| `uploadExpenseReceipt` | A/Any | Auth/S | Upload to `expense-receipts` at `<uid>/<employee>/<timestamp>_<name>` | Storage path |
| `getExpenseReceiptUrl` | A/E | S | `expense-receipts.createSignedUrl(path, 3600)` | URL or `null` |
| `getExpenseQueueForManager` | M | RPC R | `manager_get_expense_queue()` | RPC rows passed through `dbToExpense` |
| `managerApproveExpense` | M | RPC W | `manager_approve_expense({ p_expense_id })` | Expects a truthy scalar |
| `managerRejectExpense` | M | RPC W | `manager_reject_expense({ p_expense_id, p_reason })` | Expects a truthy scalar |

### `src/utils/letterStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getLetterRequests` | A | R | Unscoped `letter_requests.select('*')`; depends on RLS; enriches from caller-supplied employees instead of a join | `dbToRequest[]` with employee fields overwritten from the supplied map |
| `getPendingLetterCount` | A | R | Count-only pending `letter_requests` query | Number |
| `completeLetterRequest` | A | W | Update status and completion timestamp | No return |
| `rejectLetterRequest` | A | W | Update rejection status/reason | No return |
| `getMyLetterRequests` | E | R | Unscoped `letter_requests.select('*')`; depends on self-read RLS | Reduced camelCase request list |

### `src/utils/notificationStorage.js`

| Exported symbol | Role | Mode | Contract | Return |
| --- | --- | --- | --- | --- |
| `getNotifications` | Any | R | Unscoped `notifications.select('*').order('created_at').limit(limit)`; depends on RLS | `dbToNotification[]` |
| `getUnreadCount` | Any | R | Count-only unread query | Number |
| `markNotificationRead` | Any | W | Update one notification `read_at`; depends on RLS | No return |
| `markAllNotificationsRead` | Any | W | Update all visible unread notifications | No return |
| `createNotification` | Any/system | Auth/W | Upsert on `recipient_user_id,type,related_entity_id` with `ignoreDuplicates:true`; recipient defaults to caller | No return; errors are logged |
| `createNotifications` | Any/system | Auth/W | Batch form of `createNotification`; dispatches browser event `workloop-notifications-updated` after success | No return |
| `generateExpiryNotifications` | A/system | W | Computes employee, document, insurance, probation, contract, certification, licence, and policy alerts from supplied data; calls `createNotifications` | No direct reads; no return |

### `src/utils/taskStorage.js`

| Exported symbol | Role | Mode | Supabase dependencies | Return |
| --- | --- | --- | --- | --- |
| `getAdminTasks` | A | Auth/R | `leave_requests`, `expense_claims`, `salary_advances`, `letter_requests`, `employee_documents`, `certifications`, `regularisation_requests`, `shift_swap_requests`, and `payroll_runs`; expiry/status reads from `certifications`, `employee_contracts`, `offboarding_checklists` with nested `offboarding_tasks`, and `appraisals`; most include `employees!left(name)` | `{ categories:[{ label, icon, items }] }`; items are normalized navigation summaries |
| `getManagerTasks` | M | Auth/RPC R/R | `manager_get_leave_queue`, `manager_get_expense_queue`, pending `appraisals` joined to employees, and `certifications` joined to employees | Same category/item shape |
| `getEmployeeTasks` | E | Auth/R | Own `employees` row by `auth_user_id`; employee-filtered `certifications`, `employee_documents`, `leave_requests`, `salary_advances`, `expense_claims`, `letter_requests`, and incomplete `attendance_records` | Same category/item shape |

The private task readers use `Promise.allSettled`; individual failed dependencies silently produce an empty category.

## Direct Component Calls

These components bypass utility data modules for at least one Supabase operation.

### `src/components/employee/EmpExpenses.jsx` - `EmpExpenses`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `loadClaims(employeeId)` | E | R | `expense_claims.select('*').eq('employee_id').order('created_at', descending)` | Manually maps claim ID, category, numeric amount, date, description, receipt URL, status, rejection reason, and timestamp |
| `handleSubmit` | E | RPC W | `employee_submit_expense({ p_category, p_amount, p_expense_date, p_description, p_receipt_url })` | Ignores data; checks error, then reloads claims |

Deletion delegates to `expenseStorage.deleteEmployeeExpense`.

### `src/components/employee/EmpLeave.jsx` - `EmpLeave`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `handleCancel` | E | RPC W | `employee_cancel_leave_request({ p_request_id })` | Expects `data.success` |
| `handleSubmit` | E | RPC W | `employee_submit_leave_request({ p_leave_type_id, p_leave_type_code, p_start_date, p_end_date, p_is_half_day, p_half_day_period, p_days_requested, p_reason, p_attachment_url, p_warnings })` | Expects `data.success` |

Reads and attachment upload otherwise use `leaveStorage` and `profileStorage`.

### `src/components/employee/EmpDocuments.jsx` - `EmpDocuments`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `handleSubmit` upload | E | S | `employee-documents.upload(<admin_uid>/<employee_id>/<timestamp>_<name>, file, { upsert:false })` | Checks upload error |
| `handleSubmit` metadata | E | RPC W | `employee_submit_document({ p_document_type, p_document_number, p_expiry_date, p_notes, p_storage_path, p_file_name, p_file_size })` | Ignores data; checks error |
| `handleSubmit` cleanup | E | S | On RPC failure, `employee-documents.remove([path])` | Cleanup failures are suppressed |

Document reads and signed URLs use `profileStorage.getMyDocuments`.

### `src/components/employee/EmpAttendance.jsx` - `EmpAttendance`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `loadData` today fallback | E | R | `clock_events.select('*')`; employee and UAE-day timestamp filters | Manually derives first clock-in, last clock-out, hours, and display status |
| `loadData` history fallback | E | R | `clock_events.select('*')`; employee and rolling timestamp range | Groups raw events by Dubai calendar date and derives display records |
| `submitRegularisation` | E | RPC W | `employee_submit_regularisation({ p_attendance_date, p_correct_clock_in, p_correct_clock_out, p_reason })` | Expects `data.success` |

Primary attendance reads use `attendanceStorage.getAttendanceRecords`.

### `src/components/employee/EmpAdvances.jsx` - `EmpAdvances`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `handleSubmit` | E | RPC W | `employee_request_advance({ p_amount, p_reason })` | Ignores data; checks error, then reloads advances |

Reads and withdrawal use `storage.getAdvances` and `storage.withdrawEmployeeAdvance`.

### `src/components/employee/EmpRequests.jsx` - `EmpRequests`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `handleSubmit` custom branch | E | RPC W | `employee_request_custom({ p_subject, p_details })` | Ignores data; checks error |
| `handleSubmit` letter branch | E | RPC W | `employee_request_letter({ p_letter_type, p_purpose })` | Ignores data; checks error |

### `src/components/employee/EmpProfile.jsx` - `EmpProfile`

| Component operation | Role | Mode | Contract | Return handling |
| --- | --- | --- | --- | --- |
| `handleSave` | E | RPC W | `employee_update_contact({ p_phone, p_personal_email, p_emergency_contact_name, p_emergency_contact_phone })` | Ignores data; checks error, then updates local state |

No other component under `src/` imports the Supabase client directly.

## Table Index

The source references 52 tables:

| Table | Primary source modules |
| --- | --- |
| `advance_repayments` | `src/utils/storage.js` |
| `appraisal_cycles` | `src/utils/appraisalStorage.js` |
| `appraisal_sections` | `src/utils/appraisalStorage.js` |
| `appraisals` | `src/utils/appraisalStorage.js`, `src/utils/taskStorage.js` |
| `asset_assignments` | `src/utils/assetStorage.js` |
| `assets` | `src/utils/assetStorage.js` |
| `attendance_audit_log` | `src/utils/attendanceStorage.js` |
| `attendance_periods` | `src/utils/attendanceStorage.js` |
| `attendance_records` | `src/utils/attendanceStorage.js`, `src/utils/taskStorage.js` |
| `attendance_settings` | `src/utils/attendanceStorage.js` |
| `biometric_mappings` | `src/utils/biometricStorage.js` |
| `certifications` | `src/utils/trainingStorage.js`, `src/utils/taskStorage.js` |
| `clock_events` | `src/utils/attendanceStorage.js`, `src/utils/biometricStorage.js`, `src/components/employee/EmpAttendance.jsx` |
| `cme_requirements` | `src/utils/trainingStorage.js` |
| `companies` | `src/context/AuthContext.jsx`, `src/utils/storage.js`, `src/utils/profileStorage.js` |
| `compliance_overrides` | `src/utils/storage.js` |
| `department_staffing_rules` | `src/utils/staffingStorage.js` |
| `departments` | `src/utils/departmentStorage.js` |
| `employee_contracts` | `src/utils/storage.js`, `src/utils/taskStorage.js` |
| `employee_documents` | `src/utils/storage.js`, `src/utils/profileStorage.js`, `src/utils/taskStorage.js` |
| `employee_insurance` | `src/utils/storage.js` |
| `employee_job_history` | `src/utils/storage.js` |
| `employees` | `src/utils/storage.js`, `src/utils/profileStorage.js`, `src/utils/attendanceStorage.js`, `src/utils/leaveStorage.js`, `src/utils/trainingStorage.js`, `src/utils/taskStorage.js` and joined modules |
| `expense_claims` | `src/utils/expenseStorage.js`, `src/utils/taskStorage.js`, `src/components/employee/EmpExpenses.jsx` |
| `insurance_dependants` | `src/utils/storage.js` |
| `insurance_policies` | `src/utils/storage.js` |
| `incident_reports` | `src/utils/incidentStorage.js` |
| `leave_approval_delegates` | `src/utils/leaveStorage.js` |
| `leave_audit_log` | `src/utils/leaveStorage.js` |
| `leave_balances` | `src/utils/leaveStorage.js` |
| `leave_requests` | `src/utils/leaveStorage.js`, `src/utils/taskStorage.js` |
| `leave_settings` | `src/utils/leaveStorage.js` |
| `leave_types` | `src/utils/leaveStorage.js` |
| `letter_requests` | `src/utils/letterStorage.js`, `src/utils/taskStorage.js` |
| `nafis_reports` | `src/utils/storage.js` |
| `notifications` | `src/utils/notificationStorage.js` |
| `offboarding_checklists` | `src/utils/storage.js`, `src/utils/taskStorage.js` |
| `offboarding_task_templates` | `src/utils/storage.js` |
| `offboarding_tasks` | `src/utils/storage.js`, `src/utils/taskStorage.js` |
| `payroll_approval_log` | `src/utils/storage.js` |
| `payroll_entries` | `src/utils/storage.js` |
| `payroll_runs` | `src/utils/storage.js`, `src/utils/taskStorage.js` |
| `payslips` | `src/utils/storage.js`, `src/utils/profileStorage.js` |
| `public_holidays` | `src/utils/leaveStorage.js` |
| `regularisation_requests` | `src/utils/attendanceStorage.js`, `src/utils/taskStorage.js` |
| `roster_assignments` | `src/utils/attendanceStorage.js` |
| `salary_advances` | `src/utils/storage.js`, `src/utils/taskStorage.js` |
| `shift_assignments` | `src/utils/attendanceStorage.js` |
| `shift_swap_requests` | `src/utils/attendanceStorage.js`, `src/utils/taskStorage.js` |
| `shifts` | `src/utils/attendanceStorage.js` |
| `training_records` | `src/utils/trainingStorage.js` |
| `user_profiles` | `src/context/AuthContext.jsx`, `src/utils/profileStorage.js` |

## RPC Index

The source references 27 RPCs:

| RPC | Callers | Likely role | Expected result |
| --- | --- | --- | --- |
| `admin_execute_shift_swap` | `src/utils/attendanceStorage.js` | A | Error-only handling; request row is reread afterward |
| `admin_get_employee_portal_role` | `src/utils/profileStorage.js` | A | Scalar role |
| `admin_set_employee_portal_role` | `src/utils/profileStorage.js` | A | No data used |
| `employee_cancel_advance` | `src/utils/storage.js` | E | Boolean `true` or legacy non-empty array |
| `employee_cancel_leave_request` | `src/components/employee/EmpLeave.jsx` | E | Object with `success` |
| `employee_delete_expense` | `src/utils/expenseStorage.js` | E | Boolean `true` |
| `employee_get_colleagues` | `src/utils/attendanceStorage.js` | E | Rows with `id`, `name`, `job_title` |
| `employee_get_my_roster` | `src/utils/attendanceStorage.js` | E | Roster rows with shift fields |
| `employee_request_advance` | `src/components/employee/EmpAdvances.jsx` | E | Data ignored |
| `employee_request_custom` | `src/components/employee/EmpRequests.jsx` | E | Data ignored |
| `employee_request_letter` | `src/components/employee/EmpRequests.jsx` | E | Data ignored |
| `employee_request_shift_swap` | `src/utils/attendanceStorage.js` | E | Object with `success` and optional `error` |
| `employee_submit_document` | `src/components/employee/EmpDocuments.jsx` | E | Data ignored |
| `employee_submit_expense` | `src/components/employee/EmpExpenses.jsx` | E | Data ignored |
| `employee_submit_leave_request` | `src/components/employee/EmpLeave.jsx` | E | Object with `success` |
| `employee_submit_regularisation` | `src/components/employee/EmpAttendance.jsx` | E | Object with `success` |
| `employee_update_contact` | `src/components/employee/EmpProfile.jsx` | E | Data ignored |
| `get_manager_employee_id` | `src/utils/appraisalStorage.js`, `src/utils/trainingStorage.js` | M | Scalar employee ID or null |
| `link_employee_account` | `src/utils/profileStorage.js`, indirectly `src/context/AuthContext.jsx` | E/M | Object with link status and IDs |
| `manager_approve_expense` | `src/utils/expenseStorage.js` | M | Truthy scalar |
| `manager_approve_leave` | `src/utils/leaveStorage.js` | M | Data ignored |
| `manager_get_expense_queue` | `src/utils/expenseStorage.js`, `src/utils/taskStorage.js` | M | Expense rows |
| `manager_get_leave_queue` | `src/utils/taskStorage.js` | M | Leave rows |
| `manager_reject_expense` | `src/utils/expenseStorage.js` | M | Truthy scalar |
| `manager_reject_leave` | `src/utils/leaveStorage.js` | M | Data ignored |
| `record_advance_repayment` | `src/utils/storage.js` | A | Raw result |
| `replace_payroll_entries` | `src/utils/storage.js` | A | Error-only handling |

## Storage Bucket Index

| Bucket | Operations | Callers and path conventions |
| --- | --- | --- |
| `employee-documents` | Upload, remove, signed URL | Admin documents: `<admin>/<employee>/<timestamp>_<name>` in `src/utils/storage.js`; employee document upload uses the same shape in `src/components/employee/EmpDocuments.jsx`; leave attachments use `<admin>/<employee>/leave/...` in `src/utils/leaveStorage.js`; certificates use `<uid>/certs/<employee>/...` in `src/utils/trainingStorage.js`; signed URLs are one hour except leave attachments, which are seven days |
| `expense-receipts` | Upload, signed URL | `<uid>/<employee>/<timestamp>_<name>` in `src/utils/expenseStorage.js`; signed URLs last one hour |

There are no bucket creation/listing, `getPublicUrl`, object copy/move, or direct download calls under `src/`.

## Realtime

There is no Postgres Realtime usage under `src/`.

- No `.channel()` calls
- No Realtime `.subscribe()` calls
- No `postgres_changes` listeners
- No broadcast or presence usage
- No `removeChannel` or `removeAllChannels` calls

`src/context/AuthContext.jsx` uses `supabase.auth.onAuthStateChange`. This is an Auth session listener, not a database Realtime subscription. Notifications, queues, attendance, and all other records refresh through explicit queries or browser-local events.

## Contracts Requiring Tests

### Dynamic PostgREST filters

1. `storage.getEmployees`, `attendanceStorage.getRosterForMonth`, `attendanceStorage.publishRoster`, and `attendanceStorage.getShiftSwapRequests` interpolate company IDs into `.or('company_id.eq.<id>,company_id.is.null')`.
2. Test valid UUIDs, missing IDs, legacy null-company rows, cross-company RLS, and malformed filter values.
3. `attendanceStorage.getShiftForEmployee` builds `effective_to.is.null,effective_to.gte.<date>` dynamically. Test ISO dates, null end dates, overlapping assignments, and deterministic newest-row selection.

### Query-builder behavior

1. `leaveStorage.getPublicHolidays` calls `query.eq('year', year)` without assigning the returned builder.
2. Test that the installed Supabase client applies the year filter rather than returning every visible year.

### RPC result shapes

1. Object-with-success assumptions: `link_employee_account`, `employee_submit_leave_request`, `employee_cancel_leave_request`, `employee_submit_regularisation`, and `employee_request_shift_swap`.
2. Boolean/scalar assumptions: `employee_delete_expense`, manager expense RPCs, and `admin_get_employee_portal_role`.
3. Version-dependent shape: `employee_cancel_advance` accepts boolean `true` or a non-empty array.
4. Raw or unvalidated results: `record_advance_repayment`, letter/custom requests, document submission, expense submission, advance request, and contact update.
5. Contract-test exact JSON/scalar/table return types, false values, empty arrays, and nulls against every deployed migration version.

### Roster fallback

1. `attendanceStorage.getMyRoster` treats both an RPC error and a successful empty result as reasons to run the direct-query fallback.
2. The RPC and fallback have different source and join shapes.
3. Test no-roster, missing RPC, blocked shifts join, null shift, unpublished rows, and employee RLS cases.

### Dynamic advance persistence

1. `storage.saveAdvance` chooses insert or update at runtime.
2. It retries without `repayment_start_month` based on error-message text.
3. Test current and legacy schemas, update ownership, genuine constraint errors that mention the column, and `.single()` return behavior.

### Relationship-dependent joins

1. Inferred joins such as `employees(name)`, `employees!left(...)`, `shifts(*)`, `payroll_runs(period)`, and nested `offboarding_tasks` depend on deployed foreign keys and PostgREST relationship discovery.
2. Incident joins depend on the exact FK names `incident_reports_reported_by_id_fkey` and `incident_reports_involved_emp_id_fkey`.
3. Contract-test each join under A, M, and E sessions, including nullable relationships and RLS-blocked related rows.

### Task query schema drift

1. `taskStorage` selects `employee_documents.doc_type` and `created_at`; the primary document modules use `document_type` and `uploaded_at`.
2. `taskStorage` selects `payroll_runs.month` and `year`; the primary payroll layer uses `period`.
3. `taskStorage` checks `eid_expiry`; the main employee converter uses `emirates_id_expiry`.
4. Test these selections against the deployed schema. They are likely stale contracts.

### RLS-only scoping

The following reads omit explicit tenant or recipient filters and depend on RLS:

- `leaveStorage.getLeaveSettings`
- `leaveStorage.getLeaveTypes`
- `leaveStorage.getPublicHolidays`
- `leaveStorage.getLeaveRequests`
- `letterStorage.getLetterRequests`
- `letterStorage.getMyLetterRequests`
- `notificationStorage.getNotifications`
- Several appraisal, training, asset, and employee self-service reads

Test cross-company isolation with admin, manager, and employee JWTs. UI filters are not tenancy controls.

### Multi-step writes and partial failure

The following operations are not atomic at the client layer:

- Asset assignment and return plus asset status update
- Attendance period close plus record locking
- Regularisation approval plus attendance upsert
- Leave submission/status update plus audit insert
- Payroll approval update plus approval-log insert
- Document object upload plus metadata insert
- Appraisal creation plus section seeding
- Employee document object removal plus metadata deletion

Test network interruption, RLS denial, retry, duplicate execution, and partial success. Verify whether RPC or database transaction replacements are required for migration parity.

### Ignored or weakly checked errors

1. `appraisalStorage.managerRateSection` does not inspect the final parent-appraisal update result.
2. Attendance and leave audit inserts, offboarding task seeding, and asset status follow-up updates are not always checked.
3. `profileStorage.createAdminProfile` returns a working admin profile after non-unique persistence failure.
4. Test RLS denial and transient failures so silent divergence is observable.

### Auth lifecycle

1. Test sign-up with email confirmation enabled. A returned Auth user may not have an active session, so immediate table writes and RPCs may lack an authenticated JWT.
2. Test `INITIAL_SESSION`, `TOKEN_REFRESHED`, rapid sign-in/sign-out, employee-to-manager role changes, and stale async profile resolution.
3. Test the PostgREST builder `.catch(...)` path used during employee sign-in recovery.

### Storage policies and paths

1. Employee document uploads use the owning admin UID as the first path segment, while certificate and leave paths use different subdirectory layouts.
2. Test upload, signed URL, cleanup, and deletion with admin and employee JWTs.
3. Confirm that employee policies permit writes into an admin-prefixed object path and reads of admin-uploaded objects.
4. Test metadata failure after upload and object-removal failure before metadata deletion.

### Biometric deduplication

1. `biometricStorage.importBiometricPunches` deduplicates client-side at minute granularity and is not transactional with insertion.
2. Test simultaneous imports, duplicates inside one upload, timezone-equivalent timestamps, and database uniqueness behavior.

### Converter and return consistency

1. Several reads return converted camelCase records, while `profileStorage.getMyEmployeeRecord`, `profileStorage.getMyCompany`, `attendanceStorage.submitRegularisationRequest`, and selected RPC wrappers return raw rows or values.
2. Some update paths return `undefined` while insert paths return a record, including company, attendance settings, leave settings, and public holiday saves.
3. Contract-test consumers before replacing these functions so raw/converted and insert/update asymmetries remain explicit.
