# Workloop — Missing Features Roadmap
# UAE SME HRMS Gap Analysis & Implementation Guide

Each feature below includes: what it is, how to build it inside the existing app architecture, and what DB tables / connections / external integrations are needed.

---

## CRITICAL PRIORITY

---

### 1. ✓ COMPLETED — Emiratization / Nafis Compliance Tracking

**What it is:**
UAE Cabinet Resolution No. 27 of 2023 mandates Emiratization quotas in the private sector. Companies must hire a set percentage of UAE nationals. Non-compliance carries fines of AED 6,000 per month per unfilled Emirati slot.

**What to build:**
- Emiratization dashboard panel on the main Dashboard showing: total headcount, UAE national count, current ratio %, required ratio % (configurable per company sector), compliance status (green/amber/red)
- Alert banner when ratio drops below the required threshold
- Nafis registration number field on the employee form (UAE Compliance tab)
- Nafis monthly contribution report (exportable)
- Sector selector in Company Settings to set the legally required % for that industry

**Connections needed:**
- `companies` table: add `sector`, `nafis_quota_percent` columns
- `employees` table: add `nafis_registration_no` column (already has `nationality`)
- New `nafis_reports` table: `(id, user_id, period, total_headcount, emirati_count, ratio_percent, compliant, generated_at)`
- Dashboard component reads `employees` table, filters `nationality = 'UAE'` or `nationality = 'Emirati'`, computes ratio live
- No external API available yet — data entry only; report is PDF/CSV export

---

### 2. Document Storage & Upload

**What it is:**
The system tracks expiry dates but stores no actual documents. UAE PRO (Public Relations Officer) work requires the physical visa copy, passport scan, Emirates ID copy, and labour card to be accessible per employee.

**What to build:**
- Document vault tab on the employee profile (new 5th tab in EmployeeModal)
- Upload UI for each document type: Visa, Passport, Emirates ID, Labour Card, Work Permit, Medical Fitness Certificate
- Document list showing: file name, upload date, expiry date, status (valid / expiring / expired)
- Dedicated Documents section accessible from the main nav or EmployeeManager
- Bulk expiry export (CSV of all documents expiring within N days)

**Connections needed:**
- Supabase Storage bucket: `employee-documents` (create via Supabase dashboard)
- New `employee_documents` table: `(id, user_id, employee_id, document_type, file_name, file_url, uploaded_at, expiry_date, notes)`
- RLS: `user_id = auth.uid()` for admin; employee SELECT policy via `auth_user_id`
- `storage.js`: add `uploadEmployeeDocument(employeeId, file, type, expiryDate)` and `getEmployeeDocuments(employeeId)`
- Dashboard expiry panel links directly to the specific employee's document vault
- Max file size: 10MB per document. Accepted types: PDF, JPG, PNG

---

### 3. Medical Insurance Tracking

**What it is:**
Dubai Law No. 11 of 2013 and Abu Dhabi Circular No. 23/2014 mandate employer-provided health insurance for all employees in the UAE. This is actively enforced with fines.

**What to build:**
- Insurance tab or panel within Company Settings for policy-level info (insurer name, policy number, coverage tier names, renewal date, broker contact)
- Per-employee insurance assignment: which policy/tier they are on, their insurance card number, member ID, effective date
- Dependant tracking per employee: name, relationship, DOB, insurance card number
- Insurance expiry alert on the dashboard (separate from visa/passport alerts)
- Insurance status column in EmployeeManager table

**Connections needed:**
- New `insurance_policies` table: `(id, user_id, insurer_name, policy_number, tier_name, annual_premium, renewal_date, broker_name, broker_contact, notes)`
- New `employee_insurance` table: `(id, user_id, employee_id, policy_id, member_id, card_number, effective_date, expiry_date, tier_name)`
- New `insurance_dependants` table: `(id, user_id, employee_id, name, relationship, date_of_birth, card_number)`
- `employees` table: add `insurance_policy_id` foreign key
- `storage.js`: add `getInsurancePolicies()`, `saveInsurancePolicy()`, `getEmployeeInsurance(employeeId)`, `saveEmployeeInsurance()`
- Dashboard reads `insurance_policies.renewal_date` and `employee_insurance.expiry_date` for alerts

---

## HIGH PRIORITY

---

### 4. Notification System

**What it is:**
The entire app is silent — no proactive alerts reach anyone when the browser tab is closed. Leave approvals, payslip availability, and document expirations go unannounced.

**What to build:**
- In-app notification center: bell icon in the sidebar header, dropdown panel with unread count badge
- Notification types: leave approved/rejected, payslip available, document expiring (30/14/7 days), probation ending, contract expiring, WPS deadline approaching
- Email notifications via Supabase Edge Functions calling a transactional email provider (Resend or Sendgrid)
- Notification preferences per user: which events trigger email vs in-app only
- Mark as read / mark all read

**Connections needed:**
- New `notifications` table: `(id, user_id, recipient_user_id, type, title, body, related_entity_type, related_entity_id, read_at, created_at)`
- RLS: `recipient_user_id = auth.uid()`
- Supabase Edge Function `send-notification`: called after any relevant action (leave status change, payroll lock, document expiry sweep)
- Email provider: Resend (resend.com) — add `RESEND_API_KEY` to Supabase Edge Function secrets
- Scheduled nightly Edge Function: scans document expiry dates, probation end dates, contract end dates and fires notifications
- `notificationStorage.js`: `getNotifications()`, `markRead(id)`, `markAllRead()`
- Sidebar component updated to poll `notifications` every 60 seconds or use Supabase Realtime subscription

---

### 5. Salary Advance & Loan Management

**What it is:**
Salary advances are common in UAE SMEs, especially for blue-collar and mid-level staff. The End-of-Service screen already deducts outstanding advances but there is no module to create or track them.

**What to build:**
- Salary Advances module (new nav item or sub-section under Payroll)
- Admin can create an advance: employee, amount, date disbursed, repayment schedule (lump sum or installments), reason
- Employee self-service: submit advance request with reason and amount
- Admin approve/reject advance requests
- Active advances listed per employee with outstanding balance
- Payroll integration: advance repayment installments automatically appear as deduction line items in the monthly payroll entry
- End-of-Service screen reads outstanding balance automatically (currently manual entry)

**Connections needed:**
- New `salary_advances` table: `(id, user_id, employee_id, amount, disbursed_date, reason, repayment_months, monthly_deduction, outstanding_balance, status ['active','settled','cancelled'], created_at)`
- New `advance_repayments` table: `(id, advance_id, payroll_run_id, amount, paid_date)`
- `payroll_entries` table: advance repayment appears as a row in `deductions` JSONB column (already supported)
- `storage.js`: add `getAdvances(employeeId?)`, `saveAdvance()`, `updateAdvanceBalance()`
- `PayrollEditor`: reads active advances for each employee and pre-fills the deduction
- Employee self-service: new "Advances" tab in EmployeeShell with request form
- Supabase RPC `employee_request_advance(p_amount, p_reason)` for employee-side submission

---

### 6. Multi-Level Leave Approval Workflow

**What it is:**
All leave currently routes directly to HR admin. UAE SMEs need line manager first-level approval before HR sees the request.

**What to build:**
- Leave approval chain: Employee submits → Line Manager approves/rejects → HR Admin final approval (configurable: 1-level or 2-level per company)
- Manager role: a new role value `'manager'` in `user_profiles.role`; managers see only their direct reports' leave queue
- Leave queue in employee portal for managers (new tab in EmployeeShell)
- Leave clash detection: warn when approving if another team member is already on leave on overlapping dates
- Substitute assignment: field on leave request for who covers the employee's duties
- Leave approval comments/reason on rejection
- Delegation: admin can assign a deputy approver when the main approver is on leave

**Connections needed:**
- `user_profiles` table: add `role = 'manager'` as valid value
- `employees` table: `reporting_manager_id` already exists — wire it to approval routing
- `leave_requests` table: add `manager_approved_at`, `manager_approved_by`, `manager_rejection_reason`, `substitute_employee_id`, `approval_level_required` columns
- New `leave_approval_delegates` table: `(id, user_id, approver_employee_id, delegate_employee_id, from_date, to_date)`
- `leaveStorage.js`: add `getLeaveQueueForManager(managerEmployeeId)`, `approveLeaveAsManager()`, `rejectLeaveAsManager()`
- Supabase RPC `manager_approve_leave(p_request_id)` — SECURITY DEFINER, verifies caller is the reporting manager
- App.jsx: add `'manager'` shell route (between admin shell and employee shell)

---

### 7. Leave Calendar & Team Planner

**What it is:**
There is no visual calendar showing who is on leave on which dates. HR and managers cannot plan around leave coverage.

**What to build:**
- Monthly calendar view in the Leave module (admin side) showing all employees' approved leave as color-coded blocks
- Filter by department or team
- Employee self-service: personal leave calendar showing their own approved/pending/rejected leaves
- Leave clash indicator: when submitting a new leave request, show how many team members are already on leave in that period
- Public holidays overlaid on the calendar (already have UAE_PUBLIC_HOLIDAYS_2025/2026 in leaveEngine.js)
- Mini calendar widget on the Leave dashboard

**Connections needed:**
- No new tables needed — reads from `leave_requests` (status = 'Approved') and `public_holidays`
- New `LeaveCalendar.jsx` component
- New `LeaveCalendarView.jsx` for the admin full-page calendar
- `leaveStorage.js`: add `getApprovedLeavesForMonth(year, month)` — returns all approved leaves with employee names, dates, colors
- `LeaveManager.jsx`: add a "Calendar" tab alongside the existing list view
- `EmpLeave.jsx`: add a mini calendar showing the employee's own leave history

---

### 8. Shift Scheduling & Roster

**What it is:**
Attendance tracking exists but shift configuration is minimal. Retail, hospitality, healthcare, and logistics SMEs need visual roster management.

**What to build:**
- Shift templates: admin defines named shifts (e.g., "Morning 7:00–15:00", "Night 22:00–06:00") with start/end time, break minutes, expected hours, grace periods
- Weekly/monthly roster grid: assign shifts to employees for each day
- Roster publish: admin publishes the roster; employees can see their upcoming schedule
- Shift swap requests: employee requests to swap a shift with a colleague; admin approves
- Absence/late detection automatically compares actual clock-in against the assigned shift (already in `attendanceEngine.js` — just needs the shift data to flow from the roster)
- Roster export to PDF/CSV

**Connections needed:**
- New `shift_templates` table: `(id, user_id, name, start_time, end_time, break_minutes, expected_hours, late_grace_minutes, early_departure_grace_minutes, color)`
- New `roster_assignments` table: `(id, user_id, employee_id, shift_template_id, date, published)`
- New `shift_swap_requests` table: `(id, user_id, requester_employee_id, target_employee_id, date, status, admin_approved_at)`
- `attendanceEngine.js` `deriveAttendanceStatus()`: already accepts a `shift` param — roster feeds the correct shift object per employee per day
- `attendanceStorage.js`: add `getRosterForMonth(year, month)`, `saveRosterAssignment()`, `publishRoster()`
- New `RosterManager.jsx` component (new nav item under Attendance)
- Employee portal: new "Schedule" tab in EmployeeShell showing their upcoming roster

---

### 9. WPS Payment Confirmation & Reconciliation

**What it is:**
The app generates SIF files and the workflow ends there. There is no tracking of whether the bank processed the payment or if any rejections came back from the WPS system.

**What to build:**
- Payment status field on each payroll run: Draft → SIF Generated → Submitted to Bank → Confirmed / Partially Rejected / Failed
- Manual status update by admin after receiving bank confirmation
- Rejection handling: admin can mark individual employees' payments as rejected, with rejection reason, and generate a corrected SIF for those employees only
- WPS confirmation date field (actual date bank confirmed payment — may differ from scheduled payment date)
- WPS compliance tracker: shows months where payment was confirmed on time vs late vs missing

**Connections needed:**
- `payroll_runs` table: add `wps_status` ('draft'|'sif_generated'|'submitted'|'confirmed'|'partial_rejection'|'failed'), `wps_submitted_at`, `wps_confirmed_at`, `wps_reference_no`
- `payroll_entries` table: add `wps_payment_status` ('pending'|'paid'|'rejected'), `wps_rejection_reason`
- `PayrollEditor.jsx`: add "Update WPS Status" panel after SIF is generated
- New `generateCorrectedSIF(payroll, rejectedEmployeeIds)` in `sifGenerator.js`
- Dashboard: WPS compliance history chart showing confirmed on-time vs late vs unconfirmed by month

---

### 10. HR Reporting & Analytics

**What it is:**
The dashboard has basic stat cards and a payroll trend chart, but no exportable reports. HR teams need structured reports for management, audits, and MOHRE inspections.

**What to build:**
Reports module (new nav section) with the following reports, each exportable to CSV and PDF:

- **Headcount Report**: total employees by department, nationality, employment type, gender
- **Payroll Cost Report**: total cost by department, period-over-period comparison, basic vs allowances breakdown
- **Overtime Report**: hours and cost per employee per period
- **Leave Utilization Report**: days taken vs entitlement per employee, leave type breakdown
- **Attendance Summary**: present / absent / late / early departure days per employee for a period
- **Document Expiry Report**: all expiring documents with employee name, type, expiry date (filterable by days remaining)
- **Salary Movement History**: all salary changes for all employees over a date range (from `employee_job_history`)
- **Staff Turnover Report**: joiners and leavers per period, average tenure

**Connections needed:**
- No new tables needed — all data exists in: `employees`, `payroll_runs`, `payroll_entries`, `leave_requests`, `attendance_records`, `employee_job_history`
- New `Reports.jsx` component (new nav item)
- `reportUtils.js`: aggregation functions for each report type
- CSV export: use `papaparse` (already a dependency via csvImport.js) to unparse data to CSV blob download
- PDF export: use existing `jsPDF` dependency (already used in `payslipGenerator.js`)
- Date range picker component (reusable across reports)

---

## MEDIUM PRIORITY

---

### 11. Probation Period Management

**What it is:**
`probationEndDate` exists on employees but is completely inert. UAE law allows 14-day notice termination during probation — and HR needs to act when probation ends.

**What to build:**
- Probation alert: employees within 14 days of probation end appear on a dashboard panel
- Probation action: admin can "Confirm" (moves to Active) or "Extend" (sets new probation end date) or "Terminate" (opens End-of-Service flow with 14-day notice rule)
- Probation status badge on EmployeeManager table
- Email notification to admin 14 days before probation ends (via notification system — Feature 4)
- Probation period tracker: shows days remaining in probation on the employee profile

**Connections needed:**
- `employees` table: `probation_end_date` already exists; add `probation_extended` boolean
- `employee_job_history`: probation confirmation/extension logged as a change event (already supported)
- `Dashboard.jsx`: add probation alert card (reads `employees` where `probation_end_date` within 14 days and `employment_status = 'Probation'`)
- `EmployeeManager.jsx`: probation action buttons in the row actions or employee detail view
- Notification system (Feature 4): nightly sweep fires alert at 14 days before `probation_end_date`

---

### 12. Contract Renewal Management

**What it is:**
`contractEndDate` and `contractType` (Limited/Unlimited) exist but are unused beyond data storage. UAE law requires 30-day notice before a limited contract expires.

**What to build:**
- Contract expiry alert on dashboard (similar to document expiry — 60 and 30 day thresholds)
- Contract renewal action: admin can "Renew" (sets new end date, logs to job history), "Convert to Unlimited", or "Not Renew" (triggers offboarding)
- Contract alert in the notification system (Feature 4)
- Contract timeline on employee profile showing past contracts and renewals
- Offer letter / contract amendment letter generation (printable HTML template)

**Connections needed:**
- `employees` table: `contract_end_date` already exists
- New `employee_contracts` table: `(id, user_id, employee_id, contract_type, start_date, end_date, renewed_at, renewed_by, notes)` — tracks full contract history
- `employee_job_history`: contract renewal logged as change event
- `Dashboard.jsx`: add contract expiry warning section
- Notification system (Feature 4): nightly sweep fires at 60, 30, 14, 7 days before `contract_end_date`
- Letter generator: a printable HTML window (same pattern as `printSettlement()` in `EndOfServiceScreen.jsx`)

---

### 13. Offboarding Workflow & Clearance

**What it is:**
The end-of-service calculator is excellent but there is no structured process around it: no clearance checklist, no NOC letter, no visa cancellation tracking.

**What to build:**
- Offboarding flow triggered when employee is set to "Terminated": multi-step checklist wizard
- Clearance checklist: configurable tasks (Return laptop, Revoke system access, Return access card, Final salary payment, Gratuity transferred, Visa cancellation initiated, NOC issued, Exit interview completed)
- Each checklist item can be marked complete with a date and responsible person
- NOC (No Objection Certificate) letter generator — printable HTML template
- Experience letter generator — printable HTML template
- Visa cancellation status tracking: initiated / submitted to GDRFA / cancelled
- Final settlement: links directly to End-of-Service calculator (already exists)

**Connections needed:**
- New `offboarding_checklists` table: `(id, user_id, employee_id, created_at, completed_at, status)`
- New `offboarding_tasks` table: `(id, checklist_id, task_name, completed, completed_at, completed_by, notes)`
- New `offboarding_task_templates` table: `(id, user_id, task_name, default_order)` — admin configures the default checklist
- `EmployeeManager.jsx`: "Begin Offboarding" button appears when `employment_status = 'Terminated'`
- New `OffboardingWizard.jsx` component
- Letter generators: `nocLetterGenerator.js`, `experienceLetterGenerator.js` (printable HTML windows, same pattern as `EndOfServiceScreen.jsx`)
- `employees` table: add `visa_cancellation_status`, `visa_cancellation_date`

---

### 14. Expense Claims & Reimbursements

**What it is:**
No mechanism exists for employees to submit out-of-pocket expenses for reimbursement, or for admins to approve and process them through payroll.

**What to build:**
- Employee self-service: submit expense claim with category, amount (AED), date, description, receipt photo upload
- Expense categories: Travel, Accommodation, Meals, Fuel, Telecommunications, Office Supplies, Other
- Admin approval queue: approve / reject with comments
- Approved expenses appear as a reimbursement line item in the employee's next payroll entry
- Expense report per employee per period (exportable)
- Monthly expense summary for the company

**Connections needed:**
- New `expense_claims` table: `(id, user_id, employee_id, category, amount, expense_date, description, receipt_url, status ['pending','approved','rejected','paid'], submitted_at, reviewed_at, reviewed_by, rejection_reason, payroll_run_id)`
- Supabase Storage bucket: `expense-receipts`
- `payroll_entries` table: approved expenses appear in the `deductions` JSONB column as type `'reimbursement'` (earning, not deduction — use same structure)
- `expenseStorage.js`: `getExpenseClaims()`, `saveExpenseClaim()`, `approveExpense()`, `rejectExpense()`
- Employee portal: new "Expenses" tab in EmployeeShell
- Supabase RPC `employee_submit_expense(p_category, p_amount, p_date, p_description, p_receipt_url)` — SECURITY DEFINER
- Admin: new Expenses sub-section under Payroll module or standalone nav item

---

### 15. GPS / Geo-fenced Attendance

**What it is:**
Clock-in/out is browser-based with no location verification. Standard feature in UAE HRMSs (Bayzat, HReasily, Mena). Important for field staff, construction, and multi-site companies.

**What to build:**
- On employee clock-in: capture GPS coordinates via browser `navigator.geolocation` API
- Admin defines work locations with allowed radius (e.g., Office: 25.2048°N, 55.2708°E, radius 200m)
- Clock-in is flagged "Outside Geofence" if employee clocks in from outside the allowed radius
- Admin can view clock-in location on a map (Google Maps embed or a simple coordinate display)
- Geofence violation report
- Option to block clock-in from outside geofence (configurable — strict mode vs warn-only)

**Connections needed:**
- `clock_events` table: add `latitude`, `longitude`, `geofence_status` ('inside'|'outside'|'not_configured') columns
- New `work_locations` table: `(id, user_id, name, latitude, longitude, radius_meters, is_active)`
- `attendanceStorage.js`: update `clockIn/clockOut` to accept lat/lng
- Supabase RPC `employee_record_clock_event()`: add `p_latitude`, `p_longitude` parameters; compute geofence status server-side
- `EmpAttendance.jsx`: request browser geolocation before calling the RPC
- `AttendanceManager.jsx`: show geofence status icon on each clock event row
- Company Settings: add Work Locations management section

---

### 16. Asset Management

**What it is:**
No tracking of company assets assigned to employees. On termination, there is no structured asset return process.

**What to build:**
- Asset registry: admin adds company assets (Laptop, Phone, Car, Fuel Card, Access Card, Uniform) with serial number, value, purchase date
- Asset assignment to an employee with assignment date and notes
- Asset return on offboarding: linked to offboarding checklist (Feature 13)
- Employee self-service: view their assigned assets
- Asset status: Available / Assigned / Under Repair / Disposed

**Connections needed:**
- New `company_assets` table: `(id, user_id, asset_type, name, serial_number, purchase_value, purchase_date, status, notes)`
- New `asset_assignments` table: `(id, user_id, asset_id, employee_id, assigned_at, assigned_by, returned_at, returned_to, condition_on_return, notes)`
- `offboarding_tasks` (Feature 13): auto-creates asset return tasks for each asset assigned to the leaving employee
- New `AssetManager.jsx` component (sub-section under Employees or standalone nav)
- Employee portal: "My Assets" tab in EmployeeShell

---

### 17. Payroll Approval (Maker-Checker)

**What it is:**
Payroll is currently created and locked by the same HR admin. SMEs with internal controls (finance manager or owner approval) need a separate approval step before the SIF is generated.

**What to build:**
- Payroll run status: Draft → Submitted for Approval → Approved → SIF Generated
- Admin submits payroll for approval; a designated approver (another admin-role user) sees it in their queue
- Approver can review the payroll details, then Approve or Request Changes
- The SIF "Download" button is only available after approval
- Approval audit trail: who approved, when, any comments — stored on the payroll run
- Option to bypass approval in Company Settings (for solo-admin companies)

**Connections needed:**
- `payroll_runs` table: add `approval_status` ('not_required'|'pending_approval'|'approved'|'changes_requested'), `submitted_for_approval_at`, `approved_by`, `approved_at`, `approval_comments`
- `companies` table: add `payroll_approval_required` boolean, `payroll_approver_user_id`
- `PayrollEditor.jsx`: replace direct "Generate SIF" with "Submit for Approval" when the company setting is enabled; show approval status banner
- `PayrollList.jsx`: "Pending Approval" queue for the approver user
- `payrollStorage.js`: add `submitPayrollForApproval()`, `approvePayroll()`, `requestPayrollChanges()`
- Notification system (Feature 4): notify approver when payroll is submitted; notify admin when approved/changes requested

---

### 18. Organizational Chart

**What it is:**
`reporting_manager_id` exists on every employee record but is never rendered. No hierarchy is visible in the app.

**What to build:**
- Visual org chart in the Employees module (toggle between list view and org chart view)
- Tree layout: CEO/Owner at top, managers below, their reports below them
- Each node shows: employee photo (if available), name, job title, department
- Clickable nodes that open the employee's detail view
- Department filter to show sub-trees
- Export org chart as PNG or PDF
- Org chart used by leave approval routing (Feature 6) to automatically find the reporting manager

**Connections needed:**
- No new tables needed — reads `employees.reporting_manager_id` recursively
- New `OrgChart.jsx` component using a tree-layout algorithm (D3.js or a lightweight alternative like `react-organizational-chart`)
- `EmployeeManager.jsx`: add "Org Chart" view toggle button
- `leaveStorage.js` (for Feature 6): `getReportingManager(employeeId)` — traverses `reporting_manager_id` chain

---

## LOW PRIORITY

---

### 19. Training & Certification Records

**What it is:**
No training history or professional certification tracking exists. Required for construction, healthcare, oil & gas, and other regulated UAE industries.

**What to build:**
- Training records per employee: course name, provider, date, duration, result (passed/failed), certificate URL
- Certification tracking with expiry dates: First Aid, Safety Officer, OSHA, DHA license, etc.
- Training requests from employees (need approval)
- Expiry alerts for certifications (integrates with notification system — Feature 4)
- Company-wide training report: who completed what, upcoming expirations

**Connections needed:**
- New `training_records` table: `(id, user_id, employee_id, training_name, provider, training_date, duration_hours, result, cost, certificate_url, notes)`
- New `certifications` table: `(id, user_id, employee_id, name, issuing_body, issue_date, expiry_date, certificate_url)`
- New `training_requests` table: `(id, user_id, employee_id, training_name, provider, requested_date, reason, status, approved_by)`
- Supabase Storage bucket: `certificates` (for certificate PDF uploads)
- New `TrainingManager.jsx` component (new nav item)
- Employee portal: "Training" tab in EmployeeShell
- Notification system (Feature 4): certification expiry alerts (90/30/7 days)

---

### 20. DEWS / GPSSA Alternative EOSB Schemes

**What it is:**
The gratuity calculator covers mainland MOHRE rules only. DIFC-registered companies must use DEWS (Digital Employee Workplace Savings). UAE nationals may be covered by GPSSA pension contributions.

**What to build:**
- Company Settings: select applicable EOSB scheme — MOHRE Gratuity (default), DEWS (DIFC), ADGM Qualifying Scheme, GPSSA (UAE nationals)
- DEWS: calculate monthly employer contribution (5.83% of basic for < 5 years, 8.33% for > 5 years), generate DEWS contribution report per period
- GPSSA: flag UAE national employees, calculate employer contribution (15% of basic), generate monthly GPSSA report
- End-of-Service screen: shows the correct scheme based on company type and employee nationality

**Connections needed:**
- `companies` table: add `eosb_scheme` ('mohre'|'dews'|'gpssa'|'adgm')
- `employees` table: add `gpssa_member_no` for UAE nationals enrolled in GPSSA
- New `dews_contributions` table: `(id, user_id, employee_id, payroll_run_id, period, contribution_rate_percent, amount)`
- `gratuityCalculator.js`: add `calculateDEWSContribution(basicSalary, yearsOfService)` and `calculateGPSSAContribution(basicSalary)`
- `EndOfServiceScreen.jsx`: branch logic based on `company.eobsScheme` and `employee.nationality`
- New `DeWSReport.jsx` component for generating DEWS monthly CSV submission file

---

### 21. Multi-Company / Branch Support

**What it is:**
One Supabase account equals one company. SMEs that grow, have subsidiaries, or manage multiple entities (e.g., a group holding company) cannot consolidate.

**What to build:**
- Company switcher in the sidebar: admin can create or join multiple company accounts
- Consolidated dashboard: headcount and payroll totals across all entities
- Inter-company employee transfer: move an employee from one entity to another (creates a new employment record, closes the old one with end-of-service settlement)
- Separate SIF files per company (already happens naturally since each company has its own MOL employer ID)
- Consolidated reports across entities

**Connections needed:**
- `user_profiles` table: add `accessible_company_ids` (UUID array) to allow one user to access multiple companies
- New `company_memberships` table: `(id, user_id, company_id, role)` — replaces the current single-company assumption
- `AuthContext.jsx`: add `switchCompany(companyId)` action; stores `activeCompanyId` in context
- All `storage.js` queries currently filter by `user_id = auth.uid()` — add a `companyId` parameter or a session-level company context
- New `ConsolidatedDashboard.jsx` for cross-company view
- This is a significant architectural change — all RLS policies would need to be updated

---

### 22. Arabic Language & RTL Support

**What it is:**
The entire app and all generated documents are English-only. UAE law requires Arabic as the primary language of employment contracts. Payslips and settlement letters for Arabic-speaking employees benefit from dual-language output.

**What to build:**
- i18n framework: integrate `react-i18next` for UI string translations
- Arabic translation file for all UI labels, buttons, error messages
- RTL layout toggle: the CSS layout uses flexbox — add `dir="rtl"` to the `<html>` element and test all components
- Bilingual payslips: employee name in both English and Arabic (add `name_arabic` field on employee)
- Bilingual settlement letter: English on left column, Arabic on right column
- Language preference stored per user in `user_profiles`

**Connections needed:**
- `employees` table: add `name_arabic` column
- `user_profiles` table: add `language_preference` ('en'|'ar')
- Install `react-i18next` and `i18next` packages
- `src/i18n/en.json` and `src/i18n/ar.json` translation files
- `index.css`: add `.rtl` class with mirrored margin/padding utilities and test all layout components
- `payslipGenerator.js`: add Arabic name and bilingual header rendering
- Language toggle button in the sidebar footer (next to sign-out)

---

## INTEGRATION TARGETS (Cross-cutting)

These are external systems that multiple features above connect to:

### A. Supabase Edge Functions

Required by: Notifications (Feature 4), scheduled document/probation/contract expiry sweeps
- Create `supabase/functions/send-notification/index.ts`
- Create `supabase/functions/nightly-expiry-sweep/index.ts` (called by Supabase cron)
- Secret: `RESEND_API_KEY` for email delivery

### B. Supabase Storage

Required by: Document Upload (Feature 2), Expense Receipts (Feature 14), Training Certificates (Feature 19)
- Buckets: `employee-documents`, `expense-receipts`, `certificates`
- Storage RLS: `user_id = auth.uid()` on bucket policies
- Run in Supabase dashboard: Storage → Create bucket → Set public/private policy

### C. Supabase Realtime

Required by: Notifications bell (Feature 4), live attendance poll (already partially exists)
- `supabase.channel('notifications').on('postgres_changes', ...)` subscription in the sidebar component

### D. Google Maps / Mapbox

Required by: GPS Geo-fencing (Feature 15)
- Option 1: Google Maps JavaScript API — embed map for location display in AttendanceManager
- Option 2: Mapbox GL JS (lighter, cheaper) for location visualization
- Geofence math (Haversine formula) can be computed client-side — no API call needed for validation

### E. Email Provider (Resend or SendGrid)

Required by: Notifications (Feature 4)
- Resend is recommended — simple REST API, good Supabase Edge Function compatibility
- Add `RESEND_API_KEY` to Supabase project secrets
- From address: `noreply@workloop.app` (or company domain via DNS setup)

---

## SUMMARY TABLE

| # | Feature | Priority | New Tables | External Service |
|---|---------|----------|------------|-----------------|
| 1 | Emiratization / Nafis Tracking | Critical | nafis_reports | None |
| 2 | Document Storage & Upload | Critical | employee_documents | Supabase Storage |
| 3 | Medical Insurance Tracking | Critical | insurance_policies, employee_insurance, insurance_dependants | None |
| 4 | Notification System | High | notifications | Supabase Edge Functions, Resend |
| 5 | Salary Advance & Loan Management | High | salary_advances, advance_repayments | None |
| 6 | Multi-Level Leave Approval | High | leave_approval_delegates | None |
| 7 | Leave Calendar & Team Planner | High | None | None |
| 8 | Shift Scheduling & Roster | High | shift_templates, roster_assignments, shift_swap_requests | None |
| 9 | WPS Payment Confirmation | High | None (alter payroll_runs, payroll_entries) | None |
| 10 | HR Reporting & Analytics | High | None | None |
| 11 | Probation Period Management | Medium | None (alter employees) | Notification System (#4) |
| 12 | Contract Renewal Management | Medium | employee_contracts | Notification System (#4) |
| 13 | Offboarding Workflow | Medium | offboarding_checklists, offboarding_tasks, offboarding_task_templates | None |
| 14 | Expense Claims | Medium | expense_claims | Supabase Storage |
| 15 | GPS / Geo-fenced Attendance | Medium | work_locations (alter clock_events) | Google Maps / Mapbox |
| 16 | Asset Management | Medium | company_assets, asset_assignments | None |
| 17 | Payroll Approval (Maker-Checker) | Medium | None (alter payroll_runs, companies) | Notification System (#4) |
| 18 | Organizational Chart | Medium | None | react-organizational-chart |
| 19 | Training & Certification Records | Low | training_records, certifications, training_requests | Supabase Storage |
| 20 | DEWS / GPSSA Schemes | Low | dews_contributions (alter companies, employees) | None |
| 21 | Multi-Company / Branch Support | Low | company_memberships | None (architecture change) |
| 22 | Arabic Language & RTL | Low | None (alter employees, user_profiles) | react-i18next |
