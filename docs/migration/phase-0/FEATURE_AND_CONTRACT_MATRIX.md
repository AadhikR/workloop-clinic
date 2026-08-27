# Phase 0 feature and frontend contract matrix

## Purpose

This document records the behavior that a backend migration must preserve. It covers every visible shared, admin, manager, and employee portal feature, the frontend modules that implement it, persisted data, access rules, request and response shapes, status values, file handling, and known contract inconsistencies.

All paths are repository-relative. Supabase is the current backend. The browser calls its Auth, PostgREST, RPC, and Storage APIs directly. There is no application server between React and Supabase.

## Runtime model

| Concern | Current contract |
|---|---|
| Entry | `src/main.jsx` mounts `src/App.jsx`. |
| Authentication | `src/context/AuthContext.jsx` restores the Supabase session and loads `user_profiles`. |
| Role selection | `user_profiles.role` selects admin, manager, or employee. Unknown non-employee roles fall through to admin. |
| Admin shell | `src/App.jsx` renders `CompanyProvider` and the admin navigation. |
| Manager shell | `src/components/ManagerShell.jsx` adds direct-report queues to employee self-service. |
| Employee shell | `src/components/employee/EmployeeShell.jsx` renders personal self-service. |
| Navigation | React state, not URLs. Refresh returns to the shell's default page. Browser Back and Forward do not change feature pages. |
| Data cache | Screen-local React state. Screens fetch on mount and after mutations. There is no shared query cache. |
| Live updates | No Supabase Realtime. Attendance polls every 30 seconds. Notifications poll and listen for the local `workloop-notifications-updated` event. |
| Offline behavior | `src/components/OfflineBanner.jsx` reports connectivity loss. Mutations are not queued. |
| Security boundary | Portal visibility is not security. RLS and protected RPCs must reject unauthorized requests. |
| Browser storage | Supabase session plus sidebar keys `sidebar-collapsed`, `mgr-sidebar-collapsed`, and `emp-sidebar-collapsed`. |

## Role capability summary

| Data or workflow | Admin | Manager | Employee |
|---|---|---|---|
| Company and branches | Full CRUD on owned rows | Read employer context | Read employer context |
| Employee records | Full CRUD on owned staff | Read self and direct reports | Read self; edit approved contact fields through RPC |
| Payroll | Full run, approval, WPS, SIF, and payslip workflow | No team payroll UI | Read own payslip snapshots |
| Leave | Configure, submit for staff, approve, reject, report | Act on direct reports or delegated queue; use own leave | Read, submit, and cancel own requests |
| Expenses | Final approval, rejection, deletion, payroll reimbursement | Pre-approve or reject direct reports | Submit, read, and delete own allowed states |
| Attendance | Configure, compute, correct, approve OT, close period | Personal attendance only | Personal attendance and correction requests |
| Roster | Configure, assign, publish, approve swaps | Personal published schedule and swaps | Personal published schedule and swaps |
| Assets | Full CRUD and assignment | Read own assigned assets on Home | Read own assigned assets on Home |
| Training | Full CRUD, certifications, and CME | CRUD for direct reports and self-service for self | Own training and certification self-service |
| Appraisals | Cycle CRUD, review, calibration | Rate direct reports; read own | Read own |
| Documents | Full metadata and file management | Own documents through employee features | Own metadata and files; submit for verification |
| Incidents | Full visible module | No visible module | No visible module |
| HR requests | Complete, reject, and print | Submit and read own | Submit and read own |
| Notifications and tasks | Own recipient feed and admin tasks | Own feed and manager tasks | Own feed and employee tasks |

## Shared features

| Feature | Components | Utilities and rules | Persisted entities | Important workflow | Request and response contract |
|---|---|---|---|---|---|
| Landing and authentication | `src/App.jsx`; `src/components/LandingPage.jsx`; `src/components/AuthPage.jsx`; `src/context/AuthContext.jsx` | `src/utils/profileStorage.js`; `src/utils/uaeValidators.js`; `src/lib/supabase.js` | Supabase `auth.users`; `user_profiles`; `employees`; `companies` | Sign up company admin, admin sign-in, employee sign-in, password reset, restore session, resolve profile, auto-link employee by work email, sign out | `getProfile()` returns `{ role, companyUserId, employeeId }`. `link_employee_account` returns `{ success, already_linked?, employee_id?, company_user_id?, employee_name?, error? }`. |
| Role shell and navigation | `src/App.jsx`; `src/components/ManagerShell.jsx`; `src/components/employee/EmployeeShell.jsx` | `src/context/AuthContext.jsx`; `src/context/CompanyContext.jsx` for admin | `user_profiles`; browser local storage | Resolve role, display role-specific navigation, collapse sidebar, sign out | Profile DB fields are `role`, `company_user_id`, and `employee_id`; the context exposes camelCase fields. |
| Branch switcher | `src/App.jsx`; `src/context/CompanyContext.jsx` | Company functions in `src/utils/storage.js` | `companies`; deletion checks `employees` | List owner rows, choose active branch, create from a template, clear the new branch MOL ID, auto-switch, block deletion while active staff remain | Company UI uses `branchName`; DB uses `branch_name`. `createBranch(name, templateCompany)` returns a converted company. |
| Notification bell | `src/components/NotificationBell.jsx`; all three shells | `src/utils/notificationStorage.js` | `notifications` | Load newest notifications, count unread, mark one or all read, poll, refresh after local batch creation | UI notification is `{ id, type, title, body, relatedEntityType, relatedEntityId, readAt, createdAt }`. Dedup key is `(recipient_user_id, type, related_entity_id)`. |
| Generated notifications | Admin Dashboard; Leave Manager; Payroll Editor; Roster Manager | `generateExpiryNotifications`, `createNotification`, `createNotifications` in `src/utils/notificationStorage.js` | `notifications` plus source records | Generate expiry alerts for admin; notify linked employees of leave decisions, payslips, and roster publication | Producers pass `{ recipientUserId?, type, title, body?, relatedEntityType?, relatedEntityId? }`. Missing recipient defaults to caller. |
| Task center | `src/components/TasksPanel.jsx` | `src/utils/taskStorage.js` | Read-only aggregation across leave, expenses, advances, requests, documents, certifications, attendance, rosters, payroll, contracts, offboarding, and appraisals | Load role-specific categories, show urgency, navigate by `entity` | Returns `{ categories: [{ label, icon, items: [{ id, entity, entityId, title, subtitle, urgency, createdAt? }] }] }`. Urgency is `action`, `expired`, `urgent`, `warning`, or `info`. |
| Error and network states | `src/components/ErrorBoundary.jsx`; `src/components/LoadError.jsx`; `src/components/OfflineBanner.jsx` | None | None | Catch render errors, show retry state, report offline status | No persisted contract. |

## Admin feature matrix

| Feature | Components | Utilities and business rules | Persisted entities | Important workflow | Permissions and data contract |
|---|---|---|---|---|---|
| Dashboard | `src/components/Dashboard.jsx`; `src/components/NafisReportModal.jsx` | `storage.js`; `trainingStorage.js`; `notificationStorage.js`; `letterStorage.js`; `appraisalStorage.js`; `payrollCalculator.js` in `src/utils` | `companies`; `employees`; payroll tables; documents; insurance; certifications; requests; appraisals; `notifications`; `nafis_reports` | Setup checklist, employee and payroll KPIs, expiry cards, pending request and appraisal cards, Nafis result, payroll trend, recent runs, feature navigation | Admin owner read. Employees and payroll use `activeCompanyId`; several supporting reads remain owner-wide. Calculated payroll totals are preferred over stored totals. |
| Clinical dashboard | `src/components/ClinicalDashboard.jsx` | `src/utils/storage.js`; `attendanceStorage.js`; `leaveStorage.js`; `departmentStorage.js`; `staffingStorage.js`; `uaeValidators.js` | `employees`; `employee_documents`; `roster_assignments`; `attendance_records`; `leave_requests`; `departments`; staffing rules | Drill into headcount, credential compliance, expiring or expired credentials, roster coverage, probation, joiners, birthdays, leave, on-duty staff, pending leave, staffing gaps, and department counts | Admin read. Credential state is `valid`, `expiring`, `expired`, or missing. Owner-wide records are often filtered in memory against branch employee IDs. |
| Company settings | `src/components/CompanySettings.jsx` | Company and insurance functions in `src/utils/storage.js`; `src/utils/logoUpload.js`; `src/utils/uaeValidators.js` | `companies`; `insurance_policies` | Edit employer identity, logo, salary day, WPS route, jurisdiction, sector, feature toggles, Nafis quota, and insurance policies | Owner full CRUD. Company and policy converters return camelCase UI objects. Logo is stored in `logo_url`, currently as URL or data URL. |
| Employee master | `src/components/EmployeeManager.jsx`; `src/components/EmployeeModal.jsx` | `src/utils/storage.js`; `csvImport.js`; `uaeValidators.js`; `profileStorage.js`; `departmentStorage.js`; `attendanceStorage.js` | `employees`; job history; documents; insurance; contracts; `user_profiles` | Search, filter, add, edit, CSV import, archive, terminated list, expiry list, probation action, job history, portal role | Admin full owner CRUD. `archiveEmployee` writes `active=false`, `employment_status='Terminated'`, and today's termination date. Portal role RPC accepts `employee` or `manager`. |
| Employee detail tabs | `src/components/EmployeeModal.jsx` | Same modules as Employee master; `src/utils/gratuityCalculator.js`; `safePrint.js` | Employee and child entities | Personal; Job and Contract; Salary and Bank; UAE Compliance; Documents; Insurance; Contracts | Child tabs are available only after an employee exists. UI employee shape is camelCase. |
| Documents and files | Employee detail Documents tab | Document functions in `src/utils/storage.js` | `employee_documents`; Storage bucket `employee-documents` | Upload, create metadata, issue one-hour signed URL, verify employee submission, reject with reason, delete object and metadata | Admin owner access. UI document is `{ id, employeeId, documentType, documentNumber, fileName, fileSize, storagePath, expiryDate, notes, uploadedAt, status, submittedBy, rejectionReason, signedUrl }`. |
| Insurance | Company Settings; Employee detail Insurance tab | Insurance functions in `src/utils/storage.js` | `insurance_policies`; `employee_insurance`; `insurance_dependants` | Policy CRUD, employee assignment, coverage dates, card/member data, dependant CRUD | Admin write. Employee self-read policies exist for own coverage. Money is parsed to numbers by converters. |
| Contracts and probation | Employee Manager; Employee detail Contracts tab | Contract and history functions in `src/utils/storage.js`; validators | `employees`; `employee_contracts`; `employee_job_history` | Confirm, extend, or terminate probation; add contract lifecycle event; renew, convert, or not renew | Contract action is `new`, `renewed`, `converted`, or `not_renewed`. Employment status is `Active`, `Probation`, `On Leave`, or `Terminated`. |
| Offboarding and EOS | `src/components/OffboardingModal.jsx`; `src/components/EndOfServiceScreen.jsx` | Offboarding functions in `src/utils/storage.js`; `src/utils/gratuityCalculator.js`; `leaveEngine.js`; `safePrint.js` | `offboarding_checklists`; `offboarding_tasks`; templates; `salary_advances`; employee data | Seed checklist, toggle and add tasks, track visa cancellation, print NOC and experience letter, calculate settlement, complete checklist | Admin only. Checklist is `in_progress` or `completed`. Visa cancellation is `not_started`, `initiated`, `submitted_gdrfa`, or `cancelled`. |
| Departments | `src/components/DepartmentManager.jsx` | `src/utils/departmentStorage.js`; `staffingStorage.js`; employee reads from `storage.js` | `departments`; `department_staffing_rules`; `employees` | CRUD hierarchy, assign head, render org tree, configure minimum staffing by department and shift category | Owner full CRUD. Department UI is `{ id, name, parentId, headEmployeeId, color, description, sortOrder, createdAt }`. Rule UI is `{ id, department, shiftCategory, minStaff, effectiveFrom, effectiveTo }`. |
| HR requests | `src/components/LetterRequestsManager.jsx` | `src/utils/letterStorage.js`; `letterTemplates.js`; `requestUtils.js` | `letter_requests`; `employees` | Filter letter/custom requests, print letter, complete, reject with reason | Admin read/update. UI request is `{ id, employeeId, employeeName, jobTitle, department, basicSalary, allowance, joinDate, requestKind, letterType, purpose, status, notes, rejectionReason, requestedAt, completedAt }`. |
| Payroll list | `src/components/PayrollManager.jsx`; `src/components/PayrollList.jsx` | Payroll functions in `src/utils/storage.js`; `src/utils/payrollCalculator.js`; `sifGenerator.js` | `payroll_runs`; `payroll_entries`; `employees`; `companies` | Create one run per period, populate active staff, repeat latest run, carry recurring manual items only, open, delete | Owner full CRUD, branch filter through `company_id`. New run shape is `{ id, companyId, period, paymentDate, sequenceNo, scrBankRoutingCode, description, status:'draft', entries, createdAt }`. |
| Payroll editor | `src/components/PayrollEditor.jsx`; `src/components/AllowDeductPanel.jsx` | `payrollCalculator.js`; `payrollValidation.js`; `leaveEngine.js`; `leaveStorage.js`; `attendanceEngine.js`; `attendanceStorage.js`; `advanceSchedule.js`; `expenseStorage.js`; `csvImport.js` | Payroll plus leave, attendance, roster, advance, repayment, and expense entities | Debounced save, fixed and variable pay, recurring and one-time items, exclusions, CSV import, comparison, validation, automatic adjustments | Entry shape is documented below. Pending approval, approved, and generated runs lock editing. |
| Payroll approval | Payroll Editor | Approval functions in `src/utils/storage.js` | `payroll_runs`; `payroll_approval_log` | Submit, recall, approve, reject with mandatory reason, then generate | Visible to the same admin. Status is `draft`, `pending_approval`, or `approved`. Rejection returns to `draft` and retains the reason. |
| Payroll finalization | Payroll Editor | Payslip, advance, expense, notification, and payroll utilities | `payroll_runs`; entries; `payslips`; `advance_repayments`; `salary_advances`; `expense_claims`; `notifications` | Refresh advances, save generated run, record installments, create snapshots, notify linked staff, mark applied expenses paid | Final status is `generated`. Payslip snapshot is the full payroll entry JSON. Repayment RPC is intended to be idempotent per advance and run. |
| SIF and WPS | Payroll Editor; `src/components/SIFPreviewModal.jsx` | `src/utils/sifGenerator.js`; `sifCompliance.js`; `payrollValidation.js` | WPS fields on payroll runs and entries | Validate, preview, download SIF, mark bank state, mark each employee paid/rejected, download corrected SIF | Run WPS state is `draft`, `sif_generated`, `submitted`, `confirmed`, `partial_rejection`, or `failed`. Entry state is `pending`, `paid`, or `rejected`. SIF uses CRLF. |
| Advances | `src/components/AdvancesManager.jsx` | Advance functions in `src/utils/storage.js`; `src/utils/advanceSchedule.js`; validators | `salary_advances`; `advance_repayments`; payroll runs | Create, approve pending request, reject/cancel, edit schedule, settle, inspect progress and history | UI advance is `{ id, employeeId, amount, disbursedDate, repaymentStartMonth, reason, repaymentMonths, monthlyDeduction, outstandingBalance, status, rejectionReason, createdAt }`. |
| Expenses | `src/components/ExpensesManager.jsx` | `src/utils/expenseStorage.js`; validators | `expense_claims`; Storage bucket `expense-receipts` | Filter, inspect receipt, approve, reject, delete, hand approved unpaid claims to payroll | Admin functions explicitly filter `user_id=auth.uid()`. Expense shape is documented below. |
| Leave | `src/components/LeaveManager.jsx`; `src/components/LeaveRequestModal.jsx` | `src/utils/leaveStorage.js`; `leaveEngine.js`; `notificationStorage.js`; validators | Leave settings, types, holidays, requests, balances, audit, delegates, notifications | Overview, submit for staff, approve/reject, calendar, recalculate balances, CSV, type CRUD, holidays, Ramadan, carry-forward, approval chain, delegates | Owner access. Leave statuses are title case and documented below. Employee decision notification uses linked `authUserId`. |
| Attendance | `src/components/AttendanceManager.jsx`; `src/components/BiometricImport.jsx` | `src/utils/attendanceStorage.js`; `attendanceEngine.js`; `biometricStorage.js`; leave integration | Attendance settings, shifts, assignments, events, records, periods, corrections, audit, biometric mappings | Daily dashboard, manual event, compute records, resolve absence, approve OT, approve/reject correction, monthly report, CSV, period close, settings | Owner access. Period close is blocked by unresolved missing clock-outs or unexplained absences. Attendance record shape is documented below. |
| Roster | `src/components/RosterManager.jsx` | `src/utils/attendanceStorage.js`; `staffingStorage.js`; `leaveStorage.js`; `notificationStorage.js`; `storage.js` | `shifts`; `roster_assignments`; `shift_swap_requests`; staffing rules; `compliance_overrides`; leave; notifications | Shift templates, monthly grid, department filter, leave conflict warning, staffing gate, override, publish, CSV, swap decision | Roster and swap queries accept `companyId`. Approval RPC atomically exchanges roster assignments. |
| Assets | `src/components/AssetsManager.jsx` | `src/utils/assetStorage.js`; validators | `assets`; `asset_assignments` | CRUD, assign, return, history, status filter, block deletion while assigned | Owner write. Employee self-read is supported. Asset state is `available`, `assigned`, `under_repair`, `retired`, or `lost`. |
| Training and CME | `src/components/TrainingManager.jsx` | `src/utils/trainingStorage.js`; validators | `training_records`; `certifications`; `cme_requirements`; `employee-documents` bucket | Training CRUD, certification CRUD, file upload or URL, expiry tracking, CME target and achieved hours | Owner full CRUD. Training and certification shapes are documented below. |
| Appraisals | `src/components/AppraisalManager.jsx` | `src/utils/appraisalStorage.js` | `appraisal_cycles`; `appraisals`; `appraisal_sections` | Cycle CRUD, generate missing appraisals, rate sections, save review, calibrate, close, delete | Owner full CRUD. Weighted average rounds to one decimal. |
| Incidents | `src/components/IncidentManager.jsx` | `src/utils/incidentStorage.js`; `departmentStorage.js`; validators | `incident_reports`; joined `employees` | Create, edit, filter, investigate, close, delete | Query accepts `companyId`. Closing fills `closed_date` when missing. Incident shape and statuses are below. |
| Reports and exports | `src/components/Reports.jsx` | `src/utils/reportUtils.js`; source storage modules; `gratuityCalculator.js` | Read-only aggregation over most domain tables | Headcount, payroll cost, leave usage, attendance, OT, document expiry, salary history, turnover, staffing, WPS, Emiratization, EOS liability, leave balance; CSV and PDF | Branch employees and payroll load directly. Other owner-wide records are filtered in memory by branch employee IDs where implemented. Report builders consume camelCase domain objects. |

## Manager feature matrix

Managers receive the employee self-service features listed in the next section plus these team features.

| Feature | Components | Utilities and rules | Entities | Workflow and permissions | Contract |
|---|---|---|---|---|---|
| Manager Home | `src/components/employee/EmpHome.jsx` | Profile, leave, attendance, payroll, and asset utilities | Own employee, leave, attendance, payslip, asset records | Same as Employee Home | Mixes raw employee row data with converted domain objects. |
| Leave Queue | `src/components/manager/ManagerLeaveQueue.jsx` | `src/utils/leaveStorage.js`; `leaveEngine.js`; `profileStorage.js`; `storage.js` | `employees`; `leave_requests`; `leave_balances` | Read direct reports; show probation and balance warnings; approve or reject through protected RPC. Delegates may act during the configured dates | One-level approval becomes `Approved`. Two-level approval becomes `ManagerApproved`. Rejection becomes `ManagerRejected`. |
| Expense Queue | `src/components/manager/ManagerExpenseQueue.jsx` | `src/utils/expenseStorage.js`; validators | `expense_claims`; `employees` | `manager_get_expense_queue`; pre-approve pending claim; reject pending or manager-approved claim | Queue may include RPC field `employee_name`. `dbToExpense` also accepts an `employees` join. |
| Team Appraisals | `src/components/manager/ManagerAppraisals.jsx` | `src/utils/appraisalStorage.js` | Appraisal tables; direct-report employees | Read direct reports, exclude self from team list, rate sections, update parent status; show own appraisal separately | Section mutation is `{ rating, comments }`. When all sections are rated, parent becomes `reviewed`. |
| Team Training | `src/components/manager/ManagerTraining.jsx` | `src/utils/trainingStorage.js` | Training, certifications, employees, files | Read and CRUD direct-report records under manager RLS policies | Uses the same camelCase training and certification contracts as admin. |
| Personal features | Employee components | Employee utilities | Own records | My Leave, Schedule, My Attendance, Payslips, Advances, Expenses, Training, Documents, Requests, Profile, Tasks | Same as employee contracts below. |

## Employee feature matrix

| Feature | Components | Utilities and rules | Entities | Important workflow | Permission and request contract |
|---|---|---|---|---|---|
| Home | `src/components/employee/EmpHome.jsx` | `profileStorage.js`; `leaveStorage.js`; `leaveEngine.js`; `attendanceStorage.js`; `attendanceEngine.js`; `assetStorage.js` | Employee, leave, attendance, payslip, asset tables | Greeting, leave balance, today's attendance, latest payslip, assigned assets, shortcuts | Self-read. Employee identity is a raw snake_case row. Other data is mainly converted. |
| Leave | `src/components/employee/EmpLeave.jsx` | `leaveEngine.js`; `leaveStorage.js`; `profileStorage.js` | Leave tables; `employee-documents` bucket for attachment | Read balances and calendar, validate, submit, refresh, cancel own pending request | Submit RPC parameters are `p_leave_type_id`, `p_leave_type_code`, `p_start_date`, `p_end_date`, `p_is_half_day`, `p_half_day_period`, `p_days_requested`, `p_reason`, `p_attachment_url`, `p_warnings`. Submit and cancel responses must include `{ success }`. |
| Schedule | `src/components/employee/EmpSchedule.jsx` | `src/utils/attendanceStorage.js` | Roster, swaps, shifts, employees | Read published roster, load same-company colleagues, request shift swap | `employee_get_my_roster(p_date_from,p_date_to)` returns snake_case rows converted to `{ id, shiftId, date, published, notes, shiftName, shiftColor, startTime, endTime, expectedHours }`. Swap RPC returns `{ success, error? }`. |
| Attendance | `src/components/employee/EmpAttendance.jsx` | `attendanceStorage.js`; `attendanceEngine.js` | `attendance_records`; `clock_events`; `regularisation_requests` | Read today and recent history, fall back to raw own clock events, submit correction | `employee_submit_regularisation` takes `p_attendance_date`, ISO `p_correct_clock_in`, ISO `p_correct_clock_out`, and `p_reason`; response needs `{ success }`. There is no visible clock-in or clock-out button. |
| Payslips | `src/components/employee/EmpPayslips.jsx` | `profileStorage.js`; `payslipGenerator.js`; `payrollCalculator.js`; company read in `storage.js` | `payslips`; `employees`; `companies` | List newest first, inspect totals, download PDF | UI payslip is `{ id, payrollRunId, employeeId, period, paymentDate, grossPay, netPay, snapshot, issuedAt }`. Snapshot must remain a payroll-entry-compatible object. |
| Advances | `src/components/employee/EmpAdvances.jsx` | Advance functions in `storage.js`; validators | `salary_advances`; repayments | Read active, pending, and history; request up to one basic salary; withdraw pending | Request RPC is `{ p_amount, p_reason }`. Cancel RPC is `{ p_advance_id }`; frontend accepts boolean `true` or a legacy nonempty row array. |
| Expenses | `src/components/employee/EmpExpenses.jsx` | `expenseStorage.js`; validators | `expense_claims` | Submit past or current expense, group statuses, delete own pending or rejected claim | Submit RPC is `{ p_category, p_amount, p_expense_date, p_description, p_receipt_url }`. UI ceiling is AED 100,000. Delete RPC receives `p_expense_id` and must return `true`. |
| Training | `src/components/employee/EmpTraining.jsx` | `trainingStorage.js` | Training, certifications, file bucket | Read and self-enroll in training; submit certification with file for review | Employee certification writes force `status='pending_review'`. Training defaults to `planned`. |
| Appraisals | `src/components/employee/EmpAppraisal.jsx` | `appraisalStorage.js` | Appraisal tables | Read own cycles, sections, ratings, comments, development plan | Self-read only. Response adds `cycleName`, `reviewFrom`, and `reviewTo` to converted appraisal. |
| Documents | `src/components/employee/EmpDocuments.jsx` | `profileStorage.js`; validators | `employee_documents`; file bucket | Read signed URLs, inspect review state, validate number and expiry, upload, create metadata through RPC | RPC fields are `p_document_type`, `p_document_number`, `p_expiry_date`, `p_notes`, `p_storage_path`, `p_file_name`, `p_file_size`. UI accepts PDF, JPG, and PNG up to 10 MB. |
| Requests | `src/components/employee/EmpRequests.jsx` | `letterStorage.js`; `letterTemplates.js`; `requestUtils.js` | `letter_requests` | Submit letter or custom request, track state, print completed letter | Letter RPC is `{ p_letter_type, p_purpose }`. Custom RPC is `{ p_subject, p_details }`. Subject length is 3 to 120; details length is 5 to 2,000. |
| Profile | `src/components/employee/EmpProfile.jsx` | `profileStorage.js`; validators | `employees` | Read HR profile and expiries; edit personal email, phone, emergency name and phone | `employee_update_contact` takes `p_phone`, `p_personal_email`, `p_emergency_contact_name`, and `p_emergency_contact_phone`. Component consumes raw snake_case. |
| Tasks | `src/components/TasksPanel.jsx` | `taskStorage.js` | Multiple self-read tables | Show expiries, rejected submissions, missing clock-outs, and pending requests | Same category contract as Shared Task Center. |

## Canonical UI shapes and converters

### Company

Converter pair: `dbToCompany` and `companyToDb` in `src/utils/storage.js`.

```js
{
  id, name, branchName, molEmployerId, defaultBankRoutingCode,
  address, contactEmail, defaultSalaryDay, workLocationType,
  freeZoneName, logoUrl, sector, nafisQuotaPercent,
  enableNafis, enableStaffingRules, enableBiometricImport
}
```

Important DB mappings include `branch_name`, `mol_employer_id`, `default_bank_routing_code`, `contact_email`, `default_salary_day`, `work_location_type`, `free_zone_name`, `logo_url`, `nafis_quota_percent`, and `enable_*`.

### Employee

Converter pair: `dbToEmployee` and `employeeToDb` in `src/utils/storage.js`.

```js
{
  id, empNo, name, molId, bankName, bankRoutingCode, iban,
  basicSalary, allowance, active, companyId, authUserId,
  personalEmail, workEmail, phone, dateOfBirth, gender, maritalStatus,
  homeCountryAddress, photoUrl,
  emergencyContactName, emergencyContactRelationship, emergencyContactPhone,
  jobTitle, department, reportingManagerId,
  startDate, employmentStartDate, probationEndDate, probationExtended,
  contractType, contractEndDate, employmentStatus, terminationDate, terminationReason,
  housingAllowance, transportAllowance, otherAllowances, otherAllowancesLabel,
  bankAccountHolder, nationality, visaType, visaNumber, visaExpiry,
  passportNumber, passportExpiry, emiratesId, emiratesIdExpiry,
  labourCardNumber, labourCardExpiry, sponsoringEntity,
  workLocationType, freeZoneName, nafisRegistrationNo,
  licenceAuthority, licenceNumber, licenceExpiry
}
```

`getMyEmployeeRecord()` in `src/utils/profileStorage.js` deliberately returns the raw DB row instead. Employee components therefore use fields such as `basic_salary`, `employment_status`, `employment_start_date`, and `personal_email`.

### Payroll run and entry

Run conversion and entry conversion are in `src/utils/storage.js`.

```js
// Run
{
  id, companyId, period, paymentDate, sequenceNo, scrBankRoutingCode,
  description, status, runBy, totalDisbursed, employeeCount, createdAt,
  wpsStatus, wpsSubmittedAt, wpsConfirmedAt, wpsReferenceNo,
  approvalStatus, submittedForApprovalAt, submittedBy,
  approvedBy, approvedAt, rejectionReason, rejectedAt,
  entries
}

// Entry
{
  id?, employeeId, basicSalary, housingAllowance, transportAllowance,
  allowance, increment, bonus, otherPay, leaveDeduction, duCost,
  variableAllowance, additionalAllowances, deductions, excluded,
  wpsPaymentStatus, wpsRejectionReason
}
```

Each named adjustment is `{ label, amount, recurrence, source, ...metadata }`. `recurrence` is `one_time` or `recurring`. `source` is `manual` or `automatic`.

`src/utils/payrollCalculator.js` is canonical:

```text
fixedEarnings = basicSalary + housingAllowance + transportAllowance + allowance
variableEarnings = increment + bonus + otherPay + sum(additionalAllowances)
grossEarnings = fixedEarnings + variableEarnings
totalDeductions = sum(deductions) + leaveDeduction + duCost
netPay = grossEarnings - totalDeductions
wpsVariableAmount = netPay - basicSalary
```

### Leave

Converters in `src/utils/leaveStorage.js` are `dbToLeaveType`, `dbToLeaveRequest`, and `dbToLeaveBalance`.

```js
// Request
{
  id, employeeId, leaveTypeId, leaveTypeCode, startDate, endDate,
  isHalfDay, halfDayPeriod, daysRequested, status, reason, attachmentUrl,
  rejectionReason, approvedBy, approvedAt,
  managerApprovedAt, managerApprovedBy, managerRejectionReason,
  substituteEmployeeId, approvalLevelRequired, approvalComment,
  relationship, deceasedName, dateOfDeath, childBirthDate, childName,
  expectedDueDate, institutionName, examDates,
  submittedAt, createdAt, warnings
}

// Balance
{
  id, employeeId, leaveTypeId, leaveTypeCode, leaveYear,
  entitledDays, accruedDays, usedDays, pendingDays, carriedForward,
  remaining, sickFullPayUsed, sickHalfPayUsed, sickUnpaidUsed,
  hajjTaken, updatedAt
}
```

### Attendance, roster, and corrections

Converters in `src/utils/attendanceStorage.js` include `dbToAttendanceSettings`, `dbToShift`, `dbToClockEvent`, `dbToAttendanceRecord`, `dbToRosterAssignment`, and `dbToShiftSwapRequest`.

```js
// Attendance record
{
  id, employeeId, date, shiftId, clockInTime, clockOutTime, totalHours,
  status, lateMinutes, earlyDepartureMinutes, overtimeHours, overtimeType,
  overtimeAmount, overtimeApprovedBy, overtimeApproved,
  workedOnRestDay, restDaySubstitute, missingClockOut, isRamadanDay,
  absenceDeduction, lateDeduction, periodClosed,
  resolvedBy, resolutionType, resolutionNotes, updatedAt
}

// Roster assignment
{
  id, employeeId, shiftId, date, published, notes,
  plannedHours, actualHours, coHours, shift, createdAt
}

// Shift swap
{
  id, requesterEmployeeId, targetEmployeeId, requesterDate, targetDate,
  reason, status, adminApprovedAt, adminApprovedBy,
  rejectionReason, createdAt
}
```

### Expense

`dbToExpense` is in `src/utils/expenseStorage.js`.

```js
{
  id, userId, employeeId, employeeName, category, amount, expenseDate,
  description, receiptUrl, status, rejectionReason, payrollRunId,
  approvedBy, approvedAt, managerApprovedAt, managerApprovedBy,
  managerRejectionReason, createdAt
}
```

### Assets

`dbToAsset` and `dbToAssignment` are in `src/utils/assetStorage.js`.

```js
// Asset
{
  id, userId, name, assetCode, category, brand, model, serialNumber,
  purchaseDate, purchaseCost, status, notes, createdAt, currentAssignment
}

// Assignment
{
  id, userId, assetId, employeeId, employeeName, assetName, assetCode,
  assignedDate, returnDate, conditionAtHandover, conditionAtReturn,
  notes, assignedBy, createdAt
}
```

### Training and certifications

Converters `dbToTraining`, `dbToCertification`, and `dbToCmeReq` are in `src/utils/trainingStorage.js`.

```js
// Training
{
  id, employeeId, employeeName, trainingTitle, trainingType, provider,
  startDate, endDate, durationHours, cost, status, score, passed,
  certificateUrl, storagePath, fileName, notes, isCme, createdAt
}

// Certification
{
  id, employeeId, employeeName, certificationName, issuingBody,
  certificateNo, issuedDate, expiryDate, certificateUrl,
  storagePath, fileName, notes, status, createdAt
}

// CME target
{ id, employeeId, employeeName, year, requiredHours, notes }
```

### Appraisals

Converters `dbToCycle`, `dbToAppraisal`, and `dbToSection` are in `src/utils/appraisalStorage.js`.

```js
{
  id, userId, cycleId, employeeId, overallRating, selfRating, status,
  reviewerComments, developmentPlan, reviewedAt, reviewedBy,
  createdAt, updatedAt,
  sections: [{ id, appraisalId, sectionName, weight, rating,
               selfRating, comments, sortOrder }]
}
```

### Incidents

`dbToIncident` is in `src/utils/incidentStorage.js`.

```js
{
  id, companyId, incidentDate, incidentTime, location, department,
  incidentType, severity, description,
  reportedById, reportedByName, involvedEmpId, involvedEmpName,
  immediateAction, rootCause, correctiveAction,
  status, closedDate, closedBy, notes, createdAt
}
```

### Notifications and requests

`dbToNotification` is in `src/utils/notificationStorage.js`. `dbToRequest` is in `src/utils/letterStorage.js`.

```js
// Notification
{ id, type, title, body, relatedEntityType, relatedEntityId, readAt, createdAt }

// HR request
{
  id, employeeId, employeeName, jobTitle, department,
  basicSalary, allowance, joinDate, requestKind, letterType,
  purpose, status, notes, rejectionReason, requestedAt, completedAt
}
```

## Status catalogue

| Domain | Exact values |
|---|---|
| Portal role | `admin`, `manager`, `employee` |
| Employment | `Active`, `Probation`, `On Leave`, `Terminated` |
| Payroll run | `draft`, `generated` |
| Payroll approval | `draft`, `pending_approval`, `approved` |
| WPS run | `draft`, `sif_generated`, `submitted`, `confirmed`, `partial_rejection`, `failed` |
| WPS entry | `pending`, `paid`, `rejected` |
| Advance | `pending`, `active`, `settled`, `cancelled` |
| Expense | `pending`, `manager_approved`, `manager_rejected`, `approved`, `paid`, `rejected` |
| Leave | `Pending`, `ManagerApproved`, `ManagerRejected`, `Approved`, `Rejected`, `Cancelled` |
| Attendance | `PRESENT`, `ABSENT`, `ON_LEAVE`, `PUBLIC_HOLIDAY`, `WEEKEND`, `LATE`, `EARLY_DEPARTURE`, `HALF_DAY`, `OVERTIME`, `UNEXPLAINED_ABSENCE`, `PRESENT_REMOTE`, `MISSING_CLOCK_OUT` |
| Attendance resolution | empty string, `LEAVE_LINKED`, `UNAUTHORISED`, `WFH` |
| Correction | `Pending`, `Approved`, `Rejected` |
| Attendance period | `open`, `closed` |
| Swap | `pending`, `approved`, `rejected`, plus cancellation where produced by workflow |
| Asset | `available`, `assigned`, `under_repair`, `retired`, `lost` |
| Training | `planned`, `in_progress`, `completed`, `cancelled` |
| Certification | `verified`, `pending_review`, `rejected` |
| Appraisal cycle | `draft`, `active`, `closed`; Dashboard also recognizes `open` |
| Appraisal | `pending`, `reviewed`, `calibrated` |
| Request kind | `letter`, `custom` |
| HR request | `pending`, `completed`, `rejected` |
| Document | `pending_verification`, `verified`, `rejected` |
| Incident | `open`, `investigating`, `closed` |
| Incident severity | `low`, `moderate`, `high`, `critical` |
| Offboarding | `in_progress`, `completed` |
| Visa cancellation | `not_started`, `initiated`, `submitted_gdrfa`, `cancelled` |
| Contract action | `new`, `renewed`, `converted`, `not_renewed` |

## File contracts

| Purpose | Bucket and path | Metadata | Access behavior |
|---|---|---|---|
| HR employee document | `employee-documents/{adminUid}/{employeeId}/{timestamp}_{safeName}` | `employee_documents` | Admin upload. One-hour signed URL. Delete object and row. |
| Employee document | Same employee folder | `employee_documents` through `employee_submit_document` | Employee may upload and read only their own owner/employee folder. |
| Leave attachment | `employee-documents/{adminUid}/{employeeId}/leave/{timestamp}_{safeName}` | URL on `leave_requests` | Seven-day signed URL is returned at upload. |
| Training or certification | `employee-documents/{callerUid}/certs/{employeeId}/{timestamp}_{safeName}` | Storage fields on training or certification | One-hour signed URL. Manager path needs an isolation test because caller UID is the manager, not the owning admin. |
| Expense receipt | `expense-receipts/{callerUid}/{employeeId}/{timestamp}_{safeName}` | `receipt_url` on `expense_claims` | One-hour signed URL helper. Some employee forms accept a URL instead of uploading. |
| Payslip | Generated in browser | `payslips.data_snapshot` | PDF generated by `src/utils/payslipGenerator.js`. Bulk export uses ZIP. |
| SIF | Generated in browser | Payroll run and entry fields | Raw octet-stream download. EDR rows followed by SCR. CRLF line endings. |
| Reports | Generated in browser | None | CSV through PapaParse or local builders; PDF through jsPDF. |

## Business rules that must remain stable

| Domain | Rule |
|---|---|
| Payroll | Money is rounded to two decimals. Excluded entries do not affect totals. A legacy entry with no detailed values may use `variableAllowance` as its signed variable amount. |
| Payroll integrations | Approved leave may add leave deduction. Attendance may add unauthorized absence, approved OT, and late deductions. Published roster actual hours may add OT. Approved expenses may add reimbursement. Active scheduled advances may add repayment. |
| Advance capacity | Scheduled repayment cannot exceed remaining WPS variable capacity. Repayment starts at `repaymentStartMonth` or the disbursement month. |
| SIF | EDR basic and variable values are rounded to integer AED. SCR total is the sum of emitted integer EDR values. File lines use CRLF. Filename is 13-char employer ID plus YYMMDD plus HHMMSS and `.sif`. |
| Leave | Day count is working or calendar based on type. Half day is 0.5. Validation checks overlap, notice, balance, gender, service, probation, attachment, once-per-career, and type-specific fields. |
| Sick leave | First 15 used days are full pay, next 30 half pay, remaining days unpaid. |
| Attendance priority | Weekend, public holiday, approved leave, missing clock-out, worked day, then absence. Clock-in on a rest day falls through to worked-day logic. |
| Attendance OT | Hourly rate is `(monthly basic * 12) / (52 * weekly hours)`. Standard and night use 1.25, rest day without substitute 1.5, rest day with substitute 1.0. Premiums do not stack. |
| Absence | Unauthorized deduction is `(monthly basic / 30) * days`. Seven consecutive unexplained working days raise a flag but do not auto-terminate. |
| Period close | Block while unresolved missing clock-outs or unexplained absences remain. Close sets `payroll_ready=true` and marks period records closed. |
| Roster publish | Approved and manager-approved leave conflicts are surfaced. Staffing shortfalls require correction or a recorded compliance override. Publication notifies linked employees. |
| Gratuity | Under one year gets zero. First five years use 21 days per year. Service beyond five uses 30 days per year for the excess period. Cap is 24 months of basic salary. Current code also applies legacy resignation reduction factors. |
| Emiratization | Under 20 active staff is not mandatory. Headcount 20 to 49 requires two UAE nationals. Headcount 50 or more uses `ceil(quotaPercent * headcount)`. Reported monthly fine is AED 9,000 per missing UAE national. |
| Appraisal | Default weights are 2.0, 2.0, 1.5, 1.0, and 1.0. Overall result is weighted mean rounded to one decimal. Full section completion changes status to `reviewed`. |
| Documents | Employee upload requires document number. Clinical licence number is 3 to 30 allowed characters. Employee submission cannot have a past expiry date. |

## Known contract inconsistencies and migration traps

| Issue | Current behavior and risk |
|---|---|
| Raw versus converted employee | `getEmployees()` returns camelCase. `getMyEmployeeRecord()` returns a raw snake_case row. Converting one without updating all consumers breaks employee and manager screens. |
| Wrong employee branch company | `getMyCompany()` selects the first company owned by `company_user_id`; it does not use `employees.company_id`. Staff in a later branch may see the first branch name or settings. |
| Branch rows are company rows | The schema has no parent company plus branch table. One admin owns several `companies` records distinguished by `branch_name`. |
| Incomplete branch scope | Employees, payroll, roster, swaps, and incidents accept explicit branch scope. Leave, attendance, expenses, assets, training, insurance, departments, appraisals, and notifications are mainly owner scoped. Some screens repair this in memory; others can show another branch. |
| Legacy null company IDs | Employee and roster branch filters include `company_id IS NULL`. A legacy row can appear under every branch. |
| Task document column | `src/utils/taskStorage.js` selects `employee_documents.doc_type`; the schema and converters use `document_type`. |
| Task expiry column | Task logic checks `eid_expiry`; the employee schema uses `emirates_id_expiry`. |
| Task payroll columns | Task logic selects `payroll_runs.month` and `year`; payroll persists one `period` string. Promise settlement hides the query failure and removes the category. |
| Letter join date | `src/utils/letterStorage.js` reads joined `join_date` and converted `joinDate`; employee data uses `employment_start_date` and `employmentStartDate`. Generated letters may omit start date. |
| Mixed status casing | Leave and correction states are title case, attendance states uppercase, most other states lowercase. Do not normalize globally without data migration and consumer changes. |
| Repurposed payroll column | `payroll_entries.du_cost` persists `leaveDeduction`. In-memory `duCost` is still treated as another direct deduction. Old consumers can collide with leave deductions. |
| Derived variable allowance | `payroll_entries.variable_allowance` is the WPS non-basic transfer amount after earnings and deductions, not the employee profile's allowance. |
| Mixed date types | `payroll_runs.payment_date` is text. Most business dates are SQL `date`; audit fields are `timestamptz`. Employee correction code sends ISO datetimes even though the base attendance schema describes correction fields as `time`. |
| Employee company response | `getMyCompany()` returns a raw company row, while admin company functions return camelCase. Shells only use `.name`, which masks the difference. |
| RPC response drift | Employee cancel advance accepts boolean `true` and an older nonempty array. Preserve that tolerance until all environments are known to run migration 051. |
| Task failures are silent | `Promise.allSettled()` turns denied or invalid task queries into absent categories. Migration tests must inspect category completeness, not only page load. |
| Payroll separation of duties | The same admin UI can submit, recall, approve, reject, and generate a payroll. There is no frontend approver role. |
| Manager file path owner | Manager training upload prefixes storage with manager auth UID. Existing employee-folder policies generally expect admin owner UID. |
| Report scoping | Reports often fetch owner-wide data and filter by branch employee IDs in memory. A new API should scope server-side while preserving report output. |
| No optimistic lock use | Several tables have `updated_at`, but frontend updates do not compare it. Last write wins. |

## Backend replacement acceptance rules

1. Preserve exact status values until a coordinated data and frontend migration changes them.
2. Return camelCase from the new application API, except while raw employee consumers still exist or after those consumers change in the same release.
3. Enforce tenant, branch, employee ownership, and reporting relationships on the server. Client filters do not count as authorization.
4. Keep RPC workflows atomic where they currently protect multi-row changes, especially payroll entry replacement, repayment recording, and shift swap execution.
5. Preserve file path ownership, private access, signed URL expiry, file size limits, and orphan cleanup behavior.
6. Recompute and compare financial results against `docs/migration/phase-0/SYNTHETIC_TEST_DATA.md` before cutover.
7. Test every task category. A successful HTTP response with missing categories is not sufficient.
8. Verify branch behavior independently from tenant behavior. Both boundaries matter.
