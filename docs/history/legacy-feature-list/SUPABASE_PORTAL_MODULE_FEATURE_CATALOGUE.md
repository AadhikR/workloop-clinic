# Supabase portal module and feature catalogue

## Reference and document status

This catalogue describes the last Supabase reference application on GitHub. It does not describe the current FastAPI and Keycloak application.

| Item | Value |
| --- | --- |
| Repository | `AadhikR/workloop-clinic` |
| Reference branch | `main` |
| Reference commit | `b079236dad08ccf8e151b733f072a8dd297aae5d` |
| Commit date | 2026-08-25 |
| Commit subject | `feat: expand HR workflows, reports, and landing experience` |
| GitHub verification | The remote `main` ref matched this commit when this catalogue was prepared on 2026-10-03. |
| Primary evidence | React source under `src/`, Supabase data modules under `src/utils/`, and the Phase 0 dependency and contract inventories |
| Secondary evidence | `docs/history/legacy-feature-list/Workloop_Clinic_HRMS_Feature_List.pdf` |

The fixed GitHub source is available at [commit b079236d](https://github.com/AadhikR/workloop-clinic/tree/b079236dad08ccf8e151b733f072a8dd297aae5d).

For the corresponding layout, styling, responsive behavior, and interaction contract, see
[`SUPABASE_UI_PARITY_SPECIFICATION.md`](./SUPABASE_UI_PARITY_SPECIFICATION.md).

## What counts as a feature

The catalogue uses three evidence labels.

- **Implemented** means the reference source has a visible screen or action and the corresponding Supabase read or write path.
- **Partial** means a useful part exists, but the source lacks part of the intended workflow or relies on a weaker substitute.
- **Specification only** means the retired feature PDF describes the idea, but the reference source does not prove that it works.

The retired PDF is a gap analysis and implementation guide. Its `NEW` and `EXTEND` labels are not proof of implementation. This distinction matters most for email delivery, biometric device integration, letter approval routing, appraisal self-assessment, and locum payroll.

## Application model

The Supabase version is a client-side React application. The browser talks directly to Supabase Auth, PostgREST, RPCs, and Storage. There is no application server between the browser and Supabase.

- `src/main.jsx` mounts `src/App.jsx`.
- `src/context/AuthContext.jsx` restores the Supabase session, resolves the user's `user_profiles` row, and selects the administrator, manager, or employee portal.
- Administrator navigation uses React state. Manager and employee navigation also use React state. A page refresh returns the user to the portal's default module, and browser Back or Forward does not move between modules.
- Screen data lives in local React state. Screens reload after writes. There is no shared query cache.
- Attendance polls every 30 seconds. Notifications poll and also listen for the local `workloop-notifications-updated` browser event. The application does not use Supabase Realtime subscriptions.
- The browser stores the Supabase session and each portal's sidebar-collapse preference.
- Row Level Security and protected RPCs are the real authorization boundary. Hiding a module in the portal is not authorization.

## Portal inventory

| Portal | Navigation modules | Notes |
| --- | ---: | --- |
| Administrator | 18 | Full HR, payroll, compliance, and reporting workspace. |
| Manager | 15 | Three team modules plus employee self-service modules. Manager Training has separate team and personal views. |
| Employee | 13 | Personal HR self-service only. |
| Shared | 7 functional areas | Landing and auth, shell behavior, branch context, notifications, tasks, errors, and offline state. |

## Shared modules

### Landing and authentication

Source: `src/App.jsx`, `src/components/LandingPage.jsx`, `src/components/AuthPage.jsx`, `src/context/AuthContext.jsx`, `src/utils/profileStorage.js`.

Implemented features:

- Public landing page and role-aware sign-in entry.
- Company administrator registration. Registration creates a Supabase Auth user, a company row, and an administrator `user_profiles` row.
- Separate administrator and employee sign-in paths.
- Employee registration followed by automatic employee matching through the `link_employee_account` RPC. Matching uses the employee's work email and creates the portal link.
- Existing-session restoration through the Supabase auth-state listener.
- Recovery for users who have an Auth account but no profile row.
- Password-reset email request with a redirect back to the application origin.
- Sign-out through Supabase Auth.
- User-facing translations for invalid credentials, unconfirmed email, rate limiting, duplicate registration, and short passwords.

Access and data behavior:

- Supabase `auth.users` owns login credentials.
- `user_profiles.role` selects `admin`, `manager`, or `employee`.
- Profiles carry `company_user_id` and, for staff accounts, `employee_id`.
- An administrator login must be able to read at least one company owned by that user.
- An employee or manager account must resolve to an employee record with the correct `auth_user_id`.

### Portal shells and navigation

Source: `src/App.jsx`, `src/components/ManagerShell.jsx`, `src/components/employee/EmployeeShell.jsx`.

Implemented features:

- Role-specific navigation and module loading.
- Collapsible desktop sidebar with a saved preference per portal.
- Mobile bottom navigation for manager and employee portals.
- Signed-in identity card, company name, role label, notification bell, and sign-out action.
- Lazy loading for administrator modules and a loading indicator while a module bundle loads.
- Default-page fallback when a module ID is unknown.

Important behavior:

- Navigation changes component state, not the URL.
- The employee and manager shells load the current employee and employer records at startup.
- The manager shell reuses employee modules for personal actions. Team actions are separate modules.

### Branch switcher

Source: `src/App.jsx`, `src/context/CompanyContext.jsx`, and company functions in `src/utils/storage.js`.

Implemented features:

- List all company rows owned by the administrator.
- Select an active branch for the current tab.
- Create a branch by copying the active company as a template.
- Clear the copied MOL employer ID so the new branch must be configured.
- Switch automatically to the new branch and open Company Settings.
- Delete an inactive branch after confirmation.
- Block branch deletion while active employees remain assigned to it.

Limitation:

- A branch is another row in `companies`; there is no separate parent-company and branch model.
- Several legacy domains are owner-scoped instead of branch-scoped. Some screens repair this by filtering against branch employee IDs in the browser.

### Notifications

Source: `src/components/NotificationBell.jsx` and `src/utils/notificationStorage.js`.

Implemented features:

- Load the newest notifications for the signed-in user.
- Display unread count and a notification inbox.
- Mark one notification read or mark all read.
- Poll for new notifications.
- Refresh immediately after local batch notification creation.
- Generate administrator expiry alerts.
- Notify linked employees about leave decisions, payslip creation, and roster publication.
- Deduplicate generated notices by recipient, type, and related entity ID.

Limitation:

- The source proves in-app notifications. It does not prove the expiry and HR-request email functions proposed by the retired PDF.

### Tasks

Source: `src/components/TasksPanel.jsx` and `src/utils/taskStorage.js`.

Implemented features:

- Load role-specific task categories.
- Expand and collapse categories.
- Show action, expired, urgent, warning, and information urgency levels.
- Open the related portal module when the user selects a task.
- Aggregate work from leave, expenses, advances, HR requests, employee documents, certifications, attendance, rosters, payroll, contracts, offboarding, and appraisals.

Known weakness:

- The loader uses `Promise.allSettled()`. A denied or invalid category query disappears from the result rather than failing the whole panel.
- Three task queries use legacy column names that do not match the final Supabase schema: `doc_type`, `eid_expiry`, and payroll `month` and `year`. Those categories can silently vanish.

### Error and offline handling

Source: `src/components/ErrorBoundary.jsx`, `src/components/LoadError.jsx`, and `src/components/OfflineBanner.jsx`.

Implemented features:

- Catch render failures and show a recovery screen.
- Show module-level load errors with retry actions.
- Show browser connectivity loss.

Limitation:

- The application does not queue writes while offline.

## Administrator portal

### Administrator module index

| Module | Main purpose | Write access |
| --- | --- | --- |
| Dashboard | Operational and compliance overview | Generates expiry notifications and Nafis snapshots |
| Clinical Dashboard | Clinic staffing and credential overview | Read-only |
| Company Settings | Employer, branch, WPS, jurisdiction, feature, and insurance configuration | Full |
| Employees | Employee master data and lifecycle | Full |
| Departments | Department hierarchy and staffing rules | Full |
| Requests | HR letter and custom request queue | Complete or reject |
| Payroll Module | Payroll runs, approval, WPS, payslips, and automatic adjustments | Full |
| Advances | Salary advance administration | Full |
| Expenses | Expense claim administration | Full |
| Leave | Leave policy, balances, requests, and approvals | Full |
| Attendance | Time records, corrections, overtime, periods, and biometric import | Full |
| Assets | Asset register and assignments | Full |
| Training | Training, certifications, and CME | Full |
| Appraisals | Review cycles and ratings | Full |
| Roster | Shift templates, monthly roster, swaps, and publication | Full |
| Incidents | Workplace incident register | Full |
| Reports | Thirteen report families with CSV and PDF export | Read-only |
| Tasks | Administrator work queue | Read-only navigation |

### Dashboard

Source: `src/components/Dashboard.jsx` and `src/components/NafisReportModal.jsx`.

Implemented features:

- Setup checklist for company settings, employees, and the first generated payroll.
- Active employee headcount and joiners-this-month context.
- Payroll summary based on calculated payroll entries, not only stored totals.
- Payroll cost trend and recent payroll runs.
- WPS payment deadline warning and pending payroll approval alert.
- Expiry warnings for visas, passports, Emirates IDs, labour cards, uploaded employee documents, clinical certifications, employee insurance, and insurance policies.
- Alerts for probation ending and limited contracts expiring.
- Pending HR request and appraisal counts with links to the relevant modules.
- Emiratization calculation using the under-20, 20-to-49, and percentage quota tiers.
- Estimated Nafis shortfall and AED 9,000 monthly fine per missing UAE national.
- Nafis report modal and stored report snapshots.
- Feature navigation from cards and warning panels.

Access and scoping:

- Employees and payroll runs use the active branch ID.
- Several supporting reads are owner-wide. The dashboard can therefore combine branch data with owner-wide insurance, document, certification, or request data.

### Clinical Dashboard

Source: `src/components/ClinicalDashboard.jsx`.

Implemented features:

- Twelve drill-down cards: active staff, credential compliance, licences expiring within 90 days, expired credentials, today's roster coverage, probation, new joiners, birthdays, staff on leave, pending leave, staff on duty, and staffing-ratio failures.
- Credential classification as valid, expiring, expired, or missing.
- Clinical credential types shared with the Employee Documents module.
- Department headcount table.
- Roster and attendance checks for the current day.
- Staffing-rule analysis when staffing rules are enabled for the company.
- Expandable detail panels for each KPI rather than a single summary number.

Limitations:

- Drill-down stays inside the dashboard. The PDF proposed navigation to pre-filtered target modules, but the source uses local expansion panels.
- Owner-wide source rows are often filtered in memory against employees in the active branch.

### Company Settings

Source: `src/components/CompanySettings.jsx`.

Implemented features:

- Employer name, branch label, 13-digit MOL employer ID, default bank routing code, contact email, and address.
- Default salary payment day.
- Company logo upload, resizing, preview, replacement, and removal. The logo is stored as `logo_url`, which may be a URL or data URL.
- Mainland or Free Zone selection and a named free-zone list.
- Feature switches for Nafis, staffing rules, and biometric CSV import.
- Industry sector and required Emiratization percentage.
- Medical insurance policy register with insurer, policy number, tier, annual premium, renewal date, broker, contact, and notes.
- Policy renewal warnings and policy edit or delete actions.
- WPS and SIF record-format reference.
- Optional cascade of a changed bank routing code to draft payroll runs.

Access and scoping:

- The administrator can edit owned company rows and insurance policies.
- The active company row supplies settings to the other administrator modules.

### Employees

Source: `src/components/EmployeeManager.jsx`, `src/components/EmployeeModal.jsx`, `src/components/OffboardingModal.jsx`, and `src/components/EndOfServiceScreen.jsx`.

Implemented list and import features:

- Active, document-expiry, and terminated views.
- Search by employee name, MOL ID, or department.
- Employee counts and direct navigation to terminated or expiry views.
- CSV template download, CSV validation, bulk import, and CSV export.
- Add, edit, archive, and inspect employees.
- Job-history timeline.
- Portal role assignment as employee or manager.
- Expiry warnings for core UAE identity documents and uploaded documents.

Employee record tabs:

- Personal: employee number, name, birth date, gender, marital status, personal and work email, UAE phone, home-country address, photo URL, and emergency contact details.
- Job and Contract: title, department, reporting manager, default shift, start dates, probation dates, contract type and end date, employment state, and termination details.
- Salary and Bank: basic, housing, transport, other allowance, allowance label, MOL employee ID, bank, routing code, IBAN, and account-holder name.
- UAE Compliance: nationality, visa, passport, Emirates ID, labour card, sponsor, work location, Nafis registration, and professional licence authority, number, and expiry.
- Documents: HR upload, metadata, signed download URL, employee-submission review, verification, rejection with reason, and deletion.
- Insurance: policy assignment, coverage dates, member and card numbers, coverage tier, notes, and dependants.
- Contracts: lifecycle history, renewal, conversion to unlimited, non-renewal, and printable amendment or renewal letter.

Probation and lifecycle features:

- Confirm probation.
- Extend probation to a selected date.
- Terminate during probation.
- Archive an employee by setting `active=false`, employment status to `Terminated`, and the termination date to today.
- Start an offboarding checklist from stored task templates.
- Add, complete, or remove offboarding tasks.
- Track visa cancellation as not started, initiated, submitted to GDRFA, or cancelled.
- Print a no-objection certificate and experience letter.
- Calculate and print end-of-service settlement with final-month salary, gratuity, leave encashment, and outstanding salary advances.

Important rules:

- Employee validation covers UAE phone, email, IBAN, Emirates ID, MOL ID, routing code, visa, passport, and date ranges.
- Gratuity is zero below one year, uses 21 days per year for the first five years, 30 days per year after five years, and caps at 24 months of basic salary. The source also retains legacy resignation reduction factors.
- Child tabs such as documents, insurance, and contracts appear only after the employee record exists.

### Departments

Source: `src/components/DepartmentManager.jsx`.

Implemented features:

- Create, edit, and delete departments.
- Parent-child hierarchy, department color, description, sort order, and department head assignment.
- Department list and collapsible organization chart.
- Expand all, collapse all, and reload employee data.
- Show employees under each department and reporting manager in the organization chart.
- Configure minimum staffing for a department and shift category.
- Staffing rule effective dates and minimum headcount.
- Edit and delete staffing rules.

Access and data:

- Uses `departments`, `department_staffing_rules`, and `employees`.
- Department heads and reporting managers feed later approval and organization views, but the final source does not route every request type through a department head.

### Requests

Source: `src/components/LetterRequestsManager.jsx` and `src/utils/letterTemplates.js`.

Implemented features:

- Pending, completed, rejected, and all-request filters.
- Combined queue for standard HR letters and custom requests.
- Employee, request type, purpose or details, request date, and current state.
- Complete a request.
- Reject with a reason shown to the employee.
- Print completed standard letters using company and employee data.
- Standard types include salary certificate, NOC, experience letter, employment certificate, and salary transfer letter.

Partial behavior:

- The source has manager approval for leave and expenses, but no manager letter queue. The PDF's department-head approval for letters is not complete.
- The source proves in-app queue behavior. It does not prove email delivery to HR.

### Payroll Module

Source: `src/components/PayrollManager.jsx`, `src/components/PayrollList.jsx`, `src/components/PayrollEditor.jsx`, `src/components/AllowDeductPanel.jsx`, and `src/components/SIFPreviewModal.jsx`.

Payroll-run features:

- List runs for the active branch.
- Create one payroll run for a selected period.
- Populate active employees when the run is created.
- Repeat the latest run into a new period.
- Carry recurring manual adjustments while dropping one-time items.
- Set payment date, sequence number, bank routing code, and description.
- Open or delete a run.

Payroll editing:

- Edit fixed salary and variable items per employee.
- Add named allowances and deductions as one-time or recurring items.
- Exclude an employee from the run.
- Search employees and filter entries that need review.
- Debounced save plus explicit Save Draft and Retry Save actions.
- CSV import.
- Compare run values with defaults.
- Employee detail drawer with earnings and deductions.
- Validation panel that links directly to the affected run or employee entry.
- Lock editing after submission, approval, or generation.

Automatic payroll inputs:

- Approved leave deductions.
- Unauthorized absence and late deductions from attendance.
- Approved attendance overtime.
- Roster actual-hours overtime.
- Scheduled salary-advance repayments.
- Approved unpaid expense reimbursement.
- Apply or undo individual automatic items, or apply all pending adjustments.

Approval and generation:

- Submit a draft for approval.
- Recall a pending submission.
- Approve or reject with a mandatory reason.
- Generate a final payroll only after validation and approval.
- Create employee payslip snapshots.
- Create employee notifications.
- Record advance repayments and reduce outstanding balances.
- Mark applied expense claims paid.

WPS and SIF:

- Validate MOL IDs, routing codes, IBANs, dates, employee counts, and monetary totals.
- Preview the EDR and SCR records.
- Download a CRLF SIF file with the UAE naming convention.
- Track run states as draft, SIF generated, submitted, confirmed, partial rejection, or failed.
- Mark each employee payment paid or rejected and record a rejection reason.
- Download a corrected SIF for rejected employees.
- Download one payslip or a ZIP of all payslips.

Important rules and limitations:

- Net pay equals fixed earnings plus variable earnings minus deductions.
- WPS variable amount equals net pay minus basic salary.
- Money rounds to two decimals. SIF basic and variable values round to integer AED.
- The same administrator UI can submit, approve, reject, and generate payroll. The source does not enforce separation of duties in the interface.
- Payroll approval updates and audit-log inserts are separate writes, not one transaction.
- The retired PDF proposed locum runs and FTE-based accrual. The source does not prove a complete locum payroll workflow.

### Advances

Source: `src/components/AdvancesManager.jsx`.

Implemented features:

- Create an advance for an employee with amount, disbursement date, repayment start month, reason, repayment months, and monthly deduction.
- Filter pending, active, settled, and cancelled advances.
- Approve a pending employee request.
- Reject with a reason.
- Cancel an advance.
- Edit the repayment schedule.
- Mark an advance settled.
- Expand a record to inspect repayment progress and payroll-linked repayment history.
- Calculate outstanding balance and monthly schedule.
- Feed due installments into payroll and record payments idempotently by advance and payroll run.

### Expenses

Source: `src/components/ExpensesManager.jsx`.

Implemented features:

- Filter expense claims by state.
- Inspect employee, category, amount, date, description, and receipt link.
- Approve a pending claim directly when manager approval is not required.
- Final-approve a manager-approved claim.
- Reject with a reason.
- Delete an allowed claim after confirmation.
- Pass approved and unpaid claims into payroll for reimbursement.

Status flow:

- `pending`
- `manager_approved` or `manager_rejected`
- `approved`
- `paid`
- `rejected`

Limitation:

- Administrator functions explicitly filter by the administrator's Supabase user ID. Branch isolation is not consistently represented in this domain.

### Leave

Source: `src/components/LeaveManager.jsx` and `src/components/LeaveRequestModal.jsx`.

Implemented features:

- Overview of staff on leave today and pending approvals.
- Request list with filters and expandable details.
- Administrator submission on behalf of an employee.
- Approve, reject with a reason, or cancel.
- Manager-approved and manager-rejected states for two-level approval.
- Calendar view and printable calendar.
- Employee balances by leave type and year.
- Recalculate balances and export balances to CSV.
- Configure working days, weekend rules, Ramadan behavior, carry-forward, approval levels, and accrual behavior.
- Create, edit, and delete leave types.
- Configure probation eligibility and mandatory document rules per leave type.
- Configure public holidays.
- Configure approval delegates for manager absence.
- Type-specific request fields for bereavement, maternity, parental, and study leave.
- Attachment support for leave types that require evidence.

Important rules:

- Leave can count working days or calendar days.
- A half day is 0.5.
- Validation checks overlap, notice, balance, gender, service, probation, attachment, once-per-career limits, and type-specific inputs.
- Sick leave uses 15 full-pay days, 30 half-pay days, then unpaid days.
- Probation eligibility is configurable rather than hardcoded.

### Attendance

Source: `src/components/AttendanceManager.jsx` and `src/components/BiometricImport.jsx`.

Implemented tabs and actions:

- Dashboard with current-month counts and late arrivals today.
- Manual clock-event entry with employee, event type, time, source note, and reason.
- Attendance records with month selection and CSV export.
- Unexplained-absence queue with unauthorized and work-from-home resolutions.
- Overtime queue with approval.
- Attendance correction queue with approve or reject actions.
- Monthly summary report and CSV export.
- Attendance settings and shift templates.
- Period close.
- Conditional biometric import tab when the company enables biometric import.

Biometric CSV features:

- Upload or drag and drop a punch file.
- Parse punches and show validation errors.
- Map device badge numbers to employees and an optional device label.
- Save and delete badge mappings.
- Import valid punches with duplicate protection.

Important rules:

- Status priority is weekend, public holiday, approved leave, missing clock-out, worked day, then absence.
- Overtime hourly rate is `(monthly basic * 12) / (52 * weekly hours)`.
- Standard and night overtime use 1.25. Rest-day overtime uses 1.5 without a substitute day and 1.0 with a substitute day.
- Unauthorized absence deduction is monthly basic divided by 30 for each day.
- Closing a period is blocked while missing clock-outs or unexplained absences remain.

Partial behavior:

- The source has biometric CSV import and mappings. It does not contain the scheduled device polling, webhook receiver, device table, or vendor API integration proposed in the retired PDF.
- Period creation and record closing are separate writes, not one transaction.

### Assets

Source: `src/components/AssetsManager.jsx`.

Implemented features:

- Asset register with name, code, category, brand, model, serial number, purchase date, purchase cost, state, and notes.
- Summary cards for total, available, assigned, and under-repair assets.
- Asset and assignment-history tabs.
- Filter by asset state.
- Create, edit, and delete assets.
- Assign an asset to an employee with handover date, condition, and notes.
- Return an asset with return date, return condition, and notes.
- Block deletion while an active assignment exists.
- Preserve assignment history after return.

Asset states are available, assigned, under repair, retired, and lost.

### Training

Source: `src/components/TrainingManager.jsx`.

Implemented features:

- Training, certifications, and CME tabs.
- Training create, edit, and delete actions.
- Internal, external, online, and conference training types.
- Planned, in-progress, completed, and cancelled states.
- Provider, dates, duration, cost, score, pass result, notes, and CME flag.
- Certificate upload or external URL.
- Certification create, edit, and delete actions.
- Certification number, issuer, issue date, expiry date, notes, and file.
- Certification review as verified or rejected.
- Expiry filters for active, due soon, and expired certifications.
- CME target by employee and year.
- Compare required and achieved CME hours.

File behavior:

- Training and certification files use the private `employee-documents` bucket and signed URLs.

### Appraisals

Source: `src/components/AppraisalManager.jsx`.

Implemented features:

- Create, edit, and delete appraisal cycles.
- Review period and cycle state.
- Generate missing appraisals for employees in the selected cycle.
- Cycle summary for total, reviewed, pending, and average rating.
- Section ratings on a one-to-five scale.
- Section comments, reviewer summary, and development plan.
- Weighted overall rating rounded to one decimal.
- Review, calibration, and cycle-close behavior.
- Delete an appraisal.

Partial behavior:

- Employees can read appraisals, but the employee module has no self-rating form. The PDF's self-assessment workflow is not complete.
- The source uses fixed default sections and weights rather than the full template builder proposed by the PDF.

### Roster

Source: `src/components/RosterManager.jsx`.

Implemented features:

- Shift-template create, edit, and soft-delete actions.
- Short shift code, name, category, start and end times, expected hours, color, and rest-day flag.
- Monthly roster grid with previous and next month controls.
- Department filtering.
- Assign or remove a shift for each employee and date.
- Planned, actual, and compensatory-off hours.
- Leave-conflict warnings.
- CSV export in a clinical duty-rota format.
- Per-day morning, afternoon, night, and off counts.
- Minimum-staffing validation by department and shift category.
- Block publication on staffing failure unless the administrator records an override reason of at least ten characters.
- Professional-licence status badges in the monthly grid.
- Publish a month and notify linked employees.
- Pending shift-swap queue with approve or reject actions.
- Atomic approved-swap execution through `admin_execute_shift_swap`.

Limitation:

- The grid supports CSV export. The source does not prove the matching CSV roster import proposed by the PDF.

### Incidents

Source: `src/components/IncidentManager.jsx`.

Implemented features:

- Create, edit, filter, and delete incident reports.
- Incident date, time, location, department, type, severity, description, reporter, involved employee, and immediate action.
- Root-cause analysis, corrective action, status, closed date, closer, and notes.
- Open, investigating, and closed states.
- Low, moderate, high, and critical severity.
- Automatic closed date when an incident moves to closed without a date.
- Active-branch query through `company_id`.

### Reports

Source: `src/components/Reports.jsx` and `src/utils/reportUtils.js`.

The module contains thirteen report families:

1. Headcount by employment state, department, nationality, contract type, and gender.
2. Payroll cost by period and department.
3. Leave usage by employee, department, request count, days, and leave type.
4. Attendance summary by employee and period.
5. Overtime hours and amounts.
6. Employee document expiry by threshold and source.
7. Salary movement history.
8. Staff turnover with joiners and leavers.
9. Staffing compliance against department minimums.
10. WPS submission compliance.
11. Emiratization and Nafis compliance.
12. End-of-service liability.
13. Leave balances.

Implemented features:

- Filter by report-specific dates, period, year, threshold, or organization fields.
- Summary cards and detail tables.
- CSV export for every major report family.
- PDF export for every major report family except the turnover screen, which exports separate joiner and leaver CSV files.
- Feature-switch filtering for staffing and Nafis reports.

Scoping limitation:

- Employees and payroll load by active branch. Several other domains load owner-wide and are filtered in memory. Server-side branch enforcement was incomplete in the Supabase version.

### Tasks

The administrator Tasks module uses the shared task center. Its categories cover pending leave, expense claims, salary advances, HR requests, document verification, certification review, attendance corrections, shift swaps, payroll approval, document and certification expiry, probation, contract expiry, offboarding, and appraisal review.

## Manager portal

Managers receive employee self-service for their own records. They also receive Leave Queue, Expense Queue, Team Appraisals, and a manager version of Training.

### Home

The manager Home module reuses `src/components/employee/EmpHome.jsx`.

Features:

- Personal greeting and employment summary.
- Own annual-leave balance and pending leave count.
- Today's attendance state and punch times.
- Latest payslip period and net amount.
- Current assigned assets.
- Expiry warnings for visa, passport, Emirates ID, and labour card.
- Shortcuts to personal attendance, leave, and payslips.

It is a personal dashboard. It does not contain team headcount or team KPI cards.

### Leave Queue

Source: `src/components/manager/ManagerLeaveQueue.jsx`.

Implemented features:

- Load pending requests for direct reports through a protected manager query.
- Include delegated approvals during configured delegate dates.
- Show employee, dates, day count, type, reason, balance, probation state, and warnings.
- Expand request details.
- Approve a request.
- Reject with a mandatory reason.
- Refresh the queue.
- Show or hide processed history.

Status behavior:

- A one-level request becomes `Approved` after manager action.
- A two-level request becomes `ManagerApproved` and waits for HR.
- Manager rejection becomes `ManagerRejected`.

### Expense Queue

Source: `src/components/manager/ManagerExpenseQueue.jsx`.

Implemented features:

- Load expense claims for direct reports through `manager_get_expense_queue`.
- Filter pending, manager-approved, manager-rejected, and all claims.
- Review category, amount, date, description, and receipt.
- Pre-approve a pending claim for HR review.
- Reject a pending or manager-approved claim with a reason.
- Refresh the queue.

### Appraisals

Source: `src/components/manager/ManagerAppraisals.jsx`.

Implemented features:

- Team and My Appraisals views.
- Team list excludes the manager's own employee record.
- Expand an appraisal by employee and cycle.
- Rate each section from one to five.
- Add section comments.
- Save after confirmation.
- Mark the parent appraisal reviewed when every section has a rating.
- Read the manager's own completed or pending appraisal separately.

### My Leave

The manager reuses the employee Leave module for personal requests. It includes balances, request history, calendar, validation, attachment upload, submission, and cancellation of a pending request.

### Schedule

The manager reuses the employee Schedule module for their own published shifts and shift-swap requests.

### My Attendance

The manager reuses the employee Attendance module for personal attendance history and correction requests. There are no manager time-entry controls in this module.

### Payslips

The manager reuses the employee Payslips module for personal pay only. Team payroll is not visible.

### Advances

The manager reuses the employee Advances module for personal advance requests and history. Managers cannot approve advances from this portal.

### Expenses

The manager reuses the employee Expenses module for personal claims. The separate Expense Queue handles team claims.

### Training

Source: `src/components/manager/ManagerTraining.jsx`.

Implemented team features:

- Switch between Team and My Training.
- Team Training and Certifications tabs.
- Create, edit, and delete direct-report training records.
- Create, edit, and delete direct-report certification records.
- Filter training by state.
- Upload certificate files or save external URLs.
- Open signed file links.

Implemented personal features:

- Add and edit the manager's own training records.
- Submit and edit the manager's own certifications.
- View counts for total training, completed training, and certifications.
- View certification expiry states.

Known file-path risk:

- Manager uploads use the manager's Auth user ID in the storage path. Legacy employee-folder policies generally expect the owning administrator's user ID, so this path required an isolation test.

### Documents

The manager reuses the employee Documents module for personal document submission and review status. Managers cannot review team documents here.

### Requests

The manager reuses the employee Requests module for personal standard letters and custom HR requests. Managers do not receive a team letter-approval queue.

### Profile

The manager reuses the employee Profile module. Editable fields are limited to personal email, phone, emergency contact name, and emergency contact phone.

### Tasks

The manager task center combines personal tasks with team leave, team expense, appraisal, and certification work that the task data module can resolve.

## Employee portal

### Home

Source: `src/components/employee/EmpHome.jsx`.

Implemented features:

- Time-based greeting with the employee's name.
- Employment status.
- Annual-leave balance, including calculated accrual when stored balance is missing.
- Pending leave count and shortcut to Leave.
- Today's attendance status and punch times with a shortcut to Attendance.
- Latest payslip period and net amount with a shortcut to Payslips.
- Current assigned assets.
- Visa, passport, Emirates ID, and labour-card expiry warnings.

### Leave

Source: `src/components/employee/EmpLeave.jsx`.

Implemented features:

- Requests, Balances, and Calendar tabs.
- View current and past requests with expandable details.
- View leave balance by type.
- View approved leave in a monthly calendar.
- Submit a full-day or half-day request.
- Calculate requested days before submission.
- Filter or block leave types during probation.
- Enforce balance, overlap, notice, gender, service, once-per-career, and type-specific rules.
- Capture bereavement relationship and deceased name.
- Capture maternity or parental child and due-date details.
- Capture study institution and exam dates.
- Require an attachment for configured leave types.
- Upload the attachment to private Storage.
- Cancel a pending request.

### Schedule

Source: `src/components/employee/EmpSchedule.jsx`.

Implemented features:

- Monthly view of published shifts only.
- Previous and next month navigation.
- Shift name, color, start and end time, and expected hours.
- Empty state when no shifts are published.
- Load same-company colleagues eligible for a swap.
- Request a swap with target employee, own date, target date, and reason.
- Show request success or failure.

### Attendance

Source: `src/components/employee/EmpAttendance.jsx`.

Implemented features:

- Today's attendance state, clock-in, clock-out, total hours, lateness, early departure, and overtime.
- Recent personal attendance history.
- Fallback to raw own clock events when a computed attendance row is absent.
- Submit a correction with attendance date, corrected clock-in, corrected clock-out, and reason.
- Show the current correction-request state.

Important behavior:

- The employee portal does not show manual Clock In or Clock Out buttons. Attendance is read-only apart from correction requests.

### Payslips

Source: `src/components/employee/EmpPayslips.jsx`.

Implemented features:

- List issued payslips newest first.
- Expand a payslip to inspect fixed earnings, variable earnings, named allowances, deductions, gross pay, and net pay.
- Display period and payment date.
- Generate and download a PDF using the stored payroll-entry snapshot and company branding.

### Advances

Source: `src/components/employee/EmpAdvances.jsx`.

Implemented features:

- Submit an advance amount and reason.
- Validate positive amount and cap the request at one basic monthly salary.
- View pending requests.
- View active advances with repayment schedule, monthly deduction, and outstanding balance.
- View settled, cancelled, and rejected history.
- Withdraw a pending request.

### Expenses

Source: `src/components/employee/EmpExpenses.jsx`.

Implemented features:

- Submit category, amount, expense date, description, and receipt URL.
- Validate amount up to AED 100,000 and prevent a future expense date.
- Group claims by pending, manager-approved, manager-rejected, approved, paid, and rejected states.
- Show manager or HR rejection reason.
- Delete a pending or rejected own claim.

Partial behavior:

- The employee form stores a receipt URL. It does not upload a receipt file from this screen, even though the storage utility supports the private `expense-receipts` bucket.

### Training

Source: `src/components/employee/EmpTraining.jsx`.

Implemented features:

- Summary counts for training and certifications.
- View training history and completion state.
- Add or edit own training with type, provider, dates, duration, status, score, pass state, CME flag, notes, and certificate.
- View own certifications and expiry state.
- Submit or edit a certification with issuer, number, dates, notes, and certificate.
- Upload a file or provide a URL.
- Open signed certificate links.
- Employee certification submissions always enter `pending_review`.

### Appraisals

Source: `src/components/employee/EmpAppraisal.jsx`.

Implemented features:

- List the employee's appraisal cycles.
- Expand a record to view section ratings and comments.
- View overall rating, reviewer comments, development plan, and review dates.

Partial behavior:

- This module is read-only. The self-assessment form described in the retired PDF is absent.

### Documents

Source: `src/components/employee/EmpDocuments.jsx`.

Implemented features:

- View personal documents and signed download links.
- Show pending review, verified, or rejected state.
- Show rejection reason.
- Submit a document type, number, expiry date, notes, and file.
- Support UAE identity documents and clinical credentials such as BLS, ACLS, PALS, NRP, CME, DHA, DOH, and MOH licences.
- Validate Emirates ID format when that document type is selected.
- Reject a past expiry date.
- Accept PDF, JPG, and PNG files up to 10 MB.
- Upload to a private employee folder and create metadata through `employee_submit_document`.

### Requests

Source: `src/components/employee/EmpRequests.jsx`.

Implemented features:

- Submit a standard HR letter with letter type and purpose.
- Submit a custom request with a subject of 3 to 120 characters and details of 5 to 2,000 characters.
- View pending, ready, and rejected requests.
- View HR rejection reason.
- Print a completed standard letter using the employee and company record.

### Profile

Source: `src/components/employee/EmpProfile.jsx`.

Implemented features:

- View personal, job, salary, bank, UAE compliance, and employment details held by HR.
- View expiry status for visa, passport, Emirates ID, and labour card.
- Edit personal email, UAE phone, emergency contact name, and emergency contact phone.
- Validate email and phone before saving.
- Sign out from the profile screen.

### Tasks

The employee task center can show document and certification expiry, rejected documents or certifications, missing clock-out, pending leave, pending advances, pending expenses, and pending HR requests. Selecting an item opens the related employee module.

## Cross-portal workflow map

| Workflow | Employee | Manager | Administrator |
| --- | --- | --- | --- |
| Leave | Submit, attach evidence, cancel pending, view balance and calendar | Same personal actions plus approve or reject direct-report requests | Configure policy, submit for staff, approve, reject, cancel, recalculate balances, manage delegates |
| Expenses | Submit, view, delete allowed states | Same personal actions plus pre-approve or reject team claims | Final approve, reject, delete, and reimburse through payroll |
| Appraisals | Read own result | Rate direct reports and read own result | Create cycles, generate records, review, calibrate, close |
| Training | Maintain own training and submit certifications | Maintain own records and direct-report records | Full training, certification review, and CME administration |
| Documents | Submit and track own documents | Same personal behavior | Upload, verify, reject, delete, and review expiries |
| Roster | View published shifts and request swaps | Same personal behavior | Build, validate, publish, and decide swaps |
| Attendance | View own record and request corrections | Same personal behavior | Configure, import, compute, correct, approve overtime, and close periods |
| Payroll | View and download own payslips | View and download own payslips | Build, validate, approve, generate, create SIF, and track WPS |
| Advances | Request and withdraw pending | Same personal behavior | Create, approve, reject, reschedule, settle, and integrate with payroll |
| HR requests | Submit and print completed own letters | Same personal behavior | Complete, reject, and print |

## Retired PDF comparison

The retired 15-page feature specification mixes existing behavior, requested extensions, and new ideas. The table below records what the GitHub source actually proves at the reference commit.

| PDF feature | Code result | Evidence and boundary |
| --- | --- | --- |
| Clinical credential tracking | Implemented | Clinical document types, expiry state, dashboards, notifications, employee and HR document modules |
| Employee self-service document upload | Implemented | `EmpDocuments.jsx` plus Storage upload and protected RPC |
| Letter and certificate requests | Implemented, email partial | Employee and HR queues exist; email Edge Function is not proved |
| Clinical duty rota | Implemented, import partial | Shift codes, categories, hours, staffing counts, CSV export, publication; matching roster CSV import is not proved |
| Biometric integration | Partial | CSV punch import and badge mapping exist; device API polling, webhook, and device configuration do not |
| Probation-aware leave | Implemented | Configurable type eligibility and probation validation exist |
| Leave attachments | Implemented | Type configuration, employee upload, and HR review link exist |
| Department hierarchy | Implemented | Department CRUD, parent hierarchy, heads, organization chart, staffing rules |
| Multi-level approval for every request | Partial | Leave and expenses have manager paths; letters do not have a manager queue |
| Clinical dashboard drill-down | Implemented with different interaction | KPI panels expand inside the dashboard rather than navigating to pre-filtered modules |
| Contract-type salary distribution | Partial | Payroll validation exists; full locum run and FTE behavior are not proved |
| Overtime to payroll | Implemented | Attendance and roster overtime feed automatic payroll items |
| Employee evaluation and appraisal | Partial | Admin and manager ratings plus employee read-only results exist; employee self-assessment and full template builder do not |
| Professional licence compliance gate | Partial | Employee licence fields, payroll warnings, and roster status badges exist. The source does not block payroll generation or roster publication for an expired licence. |
| Shift minimum staffing | Implemented | Department rules, roster publication gate, override log, dashboard, and report |

## Important limits in the Supabase version

These are observed source behaviors, not migration assumptions.

- Staff company lookup returns the first company owned by `company_user_id`; it does not select `employees.company_id`. Staff attached to a later branch can receive the wrong company name or settings.
- Several domains are tenant-scoped rather than branch-scoped. Reports and dashboards sometimes filter owner-wide rows in the browser.
- Employee components consume a raw snake_case employee row, while administrator storage functions return camelCase. A shared change to either shape can break one portal.
- Legacy employees or roster rows with a null company ID can appear under more than one branch.
- Payroll stores leave deduction in the legacy `du_cost` column while in-memory code still treats `duCost` as a separate direct deduction.
- The payroll `variable_allowance` column is the WPS non-basic transfer amount, not the employee profile allowance.
- Several multi-write workflows are not atomic, including payroll approval logging, attendance period close, and some correction actions.
- There is no optimistic concurrency check. The last successful update wins.
- Report authorization depends on RLS plus client filtering. Client filtering alone is not a security control.
- The same administrator can prepare, approve, reject, and generate payroll.
- Task query failures can silently remove categories.
- The application has no true URL routing between modules.

## Source index

The detailed catalogue was checked against these repository records:

- `docs/migration/phase-0/FEATURE_AND_CONTRACT_MATRIX.md`
- `docs/migration/phase-0/SUPABASE_DEPENDENCY_INVENTORY.md`
- `docs/migration/phase-0/SQL_SCHEMA_INVENTORY.md`
- `docs/history/legacy-feature-list/Workloop_Clinic_HRMS_Feature_List.pdf`
- Supabase-era portal shells and components at commit `b079236dad08ccf8e151b733f072a8dd297aae5d`
- Supabase-era data and business-rule modules under `src/utils/` at the same commit

The Phase 0 matrices remain the low-level contract reference. This document is the reader-facing module catalogue.
