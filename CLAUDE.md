# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Development
npm run dev           # Start Vite dev server (localhost:5173)
npm run build         # Standard Vite build
npm run build:dist    # Single-file bundle for offline distribution (vite.singlefile.config.js + fix-dist.js)
npm run lint          # ESLint
npm run preview       # Preview the production build

# Testing (Playwright E2E — dev server auto-starts via playwright.config.js webServer block)
npm test                        # Full test suite, headless
npm run test:ui                 # Playwright UI mode (best for debugging)
npm run test:auth               # Auth flows only
npm run test:attendance         # Attendance flows only
npm run test:employees          # Employee CRUD only
npm run test:payroll            # Payroll flows only
npm run test:report             # Open HTML report from last run

# Run a single feature spec
npx playwright test emiratization          # Feature 1 — Emiratization / Nafis
npx playwright test documents             # Feature 2 — Document Storage
npx playwright test insurance             # Feature 3 — Medical Insurance
npx playwright test notifications         # Feature 4 — Notification System
npx playwright test advances              # Feature 5 — Salary Advances
npx playwright test multi-level-leave     # Feature 6 — Multi-Level Leave Approval
npx playwright test leave-calendar        # Feature 7 — Leave Calendar
npx playwright test shift-roster          # Feature 8 — Shift Scheduling
npx playwright test wps                   # Feature 9 — WPS Payment
npx playwright test reports               # Feature 10 — Reports
npx playwright test probation             # Feature 11 — Probation
npx playwright test contracts             # Feature 12 — Contract Renewal
npx playwright test offboarding           # Feature 13 — Offboarding
npx playwright test expenses              # Feature 14 — Expense Claims
npx playwright test assets                # Feature 16 — Asset Management
npx playwright test payroll-approval      # Feature 17 — Payroll Approval
npx playwright test training              # Feature 19 — Training & Certifications
npx playwright test multi-company         # Feature 21 — Multi-Company
npx playwright test employee-portal       # Employee portal — all 12 tabs
npx playwright test payroll               # Payroll — full coverage
npx playwright test leave                 # Leave — full coverage

# Clinic HRMS feature specs
npx playwright test clinical-credentials        # 1.1 + 1.2
npx playwright test letter-requests             # 1.3
npx playwright test clinical-rota               # 2.1 + 2.2
npx playwright test probation-leave-rules       # 2.3 + 2.4
npx playwright test departments                 # 3.1
npx playwright test manager-expense-queue       # 3.2
npx playwright test clinical-dashboard          # 4.1
npx playwright test salary-compliance           # 5.1
npx playwright test appraisals                  # 6.1
npx playwright test professional-licences       # 7.1 + 7.2

# Additional specs
npx playwright test auth isolation company-settings cross-profile manager-portal
npx playwright test --grep "bell icon"   # Name pattern search
```

For Playwright test-writing patterns and selector gotchas, see **[CLAUDE_TESTING.md](CLAUDE_TESTING.md)**.

## Environment

Create `.env` with:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Architecture

**Workloop** is a UAE HR/payroll SaaS generating SIF files (UAE WPS/MOL bank format). Extended into a **UAE clinic/hospital HRMS**. React + Vite frontend, Supabase (PostgreSQL + RLS) backend. All features tracked in `FEATURES_ROADMAP.md` (original 22) and `Workloop_Clinic_HRMS_Feature_List.pdf` (clinic extensions 1.1–7.2).

### Three-portal structure

| Portal | Shell | Role | Entry |
|--------|-------|------|-------|
| Admin (HR) | `AppShell` | `'admin'` | Company owner/HR |
| Manager | `ManagerShell` | `'manager'` | Direct-report managers |
| Employee | `EmployeeShell` | `'employee'` | Linked employees |

`App.jsx` `Root` checks `profile.role` in order: `'employee'` → `EmployeeShell`, `'manager'` → `ManagerShell`, otherwise → `AppShell`. If `profile` is null after 8 seconds with a valid `user`, shows error screen with "Sign out and try again".

Both non-admin shells use floating sidebar island (solid `#08122e`, `border-radius: 22px`) with animated sliding pill driven by `useLayoutEffect` + `getBoundingClientRect`. Sidebars are collapsible — state persists via localStorage (`emp-sidebar-collapsed` / `mgr-sidebar-collapsed`), pill re-measured on toggle via delayed `setTimeout(measurePill, 300)`.

**EmployeeShell tabs** (13): Home, Leave, Schedule, Attendance, Payslips, Advances, Expenses, Training, Appraisals, Documents, Requests, Profile, Tasks (divider above).

**ManagerShell tabs** (15): Home, Leave Queue, Expense Queue, Appraisals (includes "My Appraisals" sub-view toggle), Training (includes "My Training" sub-view toggle) + 9 employee tabs (with separate IDs: `my-expenses` vs `expenses` for queue), Tasks (divider above). Home is the default tab. Managers sign in via the Employee portal form.

### Auth flow

`AuthContext.jsx` manages four auth actions. All emails normalised to lowercase.

- **`createCompany`** — Admin sign-up; detects existing accounts via `identities.length === 0`.
- **`signInAsAdmin`** — Verifies `companies` row exists; writes `user_profiles`.
- **`signUpAsEmployee`** — Calls `link_employee_account()` RPC; returns without auto-login. Shows success banner; employee signs in manually.
- **`signInAsEmployee`** — Checks existing `user_profiles` first (accepts both `'employee'` and `'manager'` roles on re-login). Falls back to `link_employee_account()` only on first login.

**Critical rules:**
- `setLoading` is ONLY called inside the `INITIAL_SESSION` / `TOKEN_REFRESHED` handler. Auth action functions must never call `setLoading(true)` — doing so unmounts `AuthPage`, destroying error/success banners.
- Profile recovery on `INITIAL_SESSION`: if `getProfile()` returns null, attempts auto-recovery via `companies` check (admin) or `linkEmployeeAccount()` (employee).
- **NEVER use `supabase.auth.getUser()` in storage utility functions** — use `supabase.auth.getSession()` instead. `getUser()` rotates refresh tokens, causing cascading `SIGNED_OUT` events in tests. `AuthContext.jsx` is the ONLY acceptable usage. Each storage file has a `getSessionUser()` helper.

### Data layer

All DB access goes through `src/utils/` modules — components never call `supabase` directly except for RPCs in `AuthContext`.

| File | Scope |
|------|-------|
| `storage.js` | Admin CRUD: companies, employees, payroll, payslips, documents, Nafis, insurance, advances/repayments, contracts, offboarding, payroll approval, compliance overrides |
| `expenseStorage.js` | Expense claims + manager queue RPCs |
| `assetStorage.js` | Assets + assignments |
| `trainingStorage.js` | Training records + certifications (admin, manager team, employee/manager self-service via `employeeSaveCertification`) |
| `taskStorage.js` | Tasks module — aggregates pending/actionable items: `getAdminTasks()`, `getManagerTasks()`, `getEmployeeTasks()` |
| `notificationStorage.js` | Notifications + `generateExpiryNotifications` |
| `profileStorage.js` | Role resolution, employee self-service data |
| `leaveStorage.js` | Leave types/requests/balances/holidays/delegates + manager queue |
| `attendanceStorage.js` | Attendance, clock events, shifts, roster, shift swaps |
| `letterStorage.js` | Letter requests |
| `letterTemplates.js` | 7 HTML letter templates + `printLetter()` |
| `departmentStorage.js` | Department hierarchy |
| `biometricStorage.js` | Biometric device mappings + CSV import |
| `appraisalStorage.js` | Appraisal cycles/sections + manager rating |
| `staffingStorage.js` | Department staffing rules |

**Shape converters**: `dbToXxx` / `xxxToDb` translate between snake_case DB and camelCase JS. All components consume camelCase.

**Critical field name traps:**
- Leave requests: `daysRequested` (not `days`/`leaveDays`), `leaveTypeCode` (not `leaveType`)
- Roster assignments: `shiftCategory` lives at `r.shift.shiftCategory` (nested), NOT `r.shiftCategory`
- Job history: `changeType` values are `'salary_change'`, `'title_change'`, `'department_change'`, `'status_change'` (with `_change` suffix)
- `dbToSection()`: `section_name` → `sectionName` (camelCase); use `s.sectionName`, never `s.section_name`
- `authUserId` in `dbToEmployee`: null until employee registers portal; used to target notifications
- `payroll_entries.du_cost` stores `leaveDeduction` (repurposed column, no migration)

### Business logic utilities

- **`sifGenerator.js`** — UAE WPS SIF format. Amounts are integer AED. **Line endings must be `\r\n` (CRLF)** — banks reject LF-only. Download Blob uses `Uint8Array` via `TextEncoder` (not `text/plain`).
- **`payslipGenerator.js`** — jsPDF payslip. Always call `downloadPayslip()` from components, not `generatePayslipPDF` directly.
- **`leaveEngine.js`** — UAE Labour Law leave rules. `DEFAULT_LEAVE_TYPES` seeds ANNUAL, HAJJ, STUDY as `probationEligible: false`.
- **`gratuityCalculator.js`** — End-of-service gratuity per UAE law.
- **`attendanceEngine.js`** — `ATTENDANCE_STATUS` constants (all uppercase). **`isPast` uses `<` not `<=`** — today is NOT past.
- **`uaeValidators.js`** — **`formatDateUAE(dateStr)`** is the project-wide date formatter (DD/MM/YYYY). Always use it — never `toLocaleDateString()` or raw ISO strings.
- **`csvImport.js`** — Header-name-based matching via `HEADER_ALIASES`. `cleanId()` strips Excel formula guards. Rows with MOL ID < 10 digits are skipped. Export uses `csvIdCell()` to prevent Excel mangling.

### Key behavioral patterns

**Payroll locking**: `status === 'generated'` → `isLocked = true`. All inputs disabled.

**Payroll approval flow**: `draft` → `pending_approval` → `approved` → `generated`. Rejection returns to `draft`. `approvalLocked` = pending or approved; `editingLocked` = `approvalLocked || isLocked`.

**Soft-delete employees**: `archiveEmployee()` sets `active = false, employment_status = 'Terminated', termination_date = today`. Must set `termination_date` — `buildTurnoverReport` depends on it.

**Auto job history**: `handleSaveEmployee` diffs salary/title/department/status and calls `addJobHistoryEntry` for each change. Wrapped in try/catch (missing RLS warns silently).

**Leave balance fallback**: `EmpLeave`/`EmpHome` compute locally when DB `leave_balances` is empty. Falls back to DB leave types, then `DEFAULT_LEAVE_TYPES`.

**Leave multi-level approval**: `pendingRequests` includes both `'Pending'` and `'ManagerApproved'`. Status flow: Pending → ManagerApproved → Approved (HR final); or ManagerRejected (final). `LEAVE_STATUS_COLORS` includes both.

**Weekend definition**: `'sat-sun'` (UAE government/healthcare standard since Jan 2022).

**Attendance clock optimistic update**: `EmpAttendance.clock()` updates state before awaiting RPC. Today's record and history are handled independently — never share a combined branch.

**Attendance auto-poll**: `AttendanceManager` polls every 30s silently. Manual Refresh via `onClick={() => loadAll()}` — never `onClick={loadAll}` (passes event as `silent` arg).

**Missing clock-out**: computed dynamically as `records.filter(r => r.clockInTime && !r.clockOutTime && r.date < todayStr)`. DB field `r.missingClockOut` is never set.

**Notification deduplication**: `createNotifications()` uses `ON CONFLICT DO NOTHING` on `(recipient_user_id, type, related_entity_id)`. Expiry alerts embed threshold in entity ID (e.g. `{empId}_visa_30d`). After upsert, dispatches `workloop-notifications-updated` event for immediate bell refresh.

**`generateExpiryNotifications`** runs async after Dashboard load. Signature: `(employees, _company, insurancePolicies, allEmpInsurance, allCertifications = [], allEmployeeDocs = [])`. Generates 8 types: visa/passport/EID/labour card, clinical credentials (90/30/14d), uploaded docs (60/30/14d), insurance, probation, contracts, certifications, professional licences.

**SIF compliance gate** (Clinic 7.1): `handleDownload()` checks three dimensions — expired licence, Emirates ID, Visa — shows override modal requiring ≥10 char reason before download.

**Roster publish gate** (Clinic 7.2): `handlePublish()` checks staffing rules violations before publish, shows override modal.

**Employee contracts are append-only**: each action inserts a new row. Nothing is ever updated or deleted.

**Offboarding task toggling is optimistic**: local state updates immediately, reverts on DB failure. EOS calculator overlays via `if (showEOS) return <EndOfServiceScreen />`.

**Reject/cancel uses inline reason forms** — never `window.confirm()`. Pattern: `rejectingId` state controls which row shows the form.

**Multi-company**: `CompanyContext.jsx` provides `activeCompanyId`. `CompanyProvider` wraps only `AppShell`. `getEmployees(companyId?)` / `getPayrolls(companyId?)` filter by company. `getEmployees` uses `.or('company_id.eq.X,company_id.is.null')` for backward compat.

**Appraisal workflow**: Setting `reporting_manager_id` alone is not enough — admin must Assign Staff in Appraisals → cycle → Reviews tab to create appraisal rows. `getMyTeamAppraisals()` filters out manager's own appraisal via `neq('employee_id', selfId)`. `getMyAppraisals()` filters to only the caller's own appraisal via `eq('employee_id', selfId)` — never omit this filter or manager RLS leaks team appraisals into "My Appraisals". ManagerAppraisals has a "Team Appraisals" / "My Appraisals" sub-view toggle — team view is interactive (star rating) only for `pending` status, own view is read-only. Both `reviewed` and `calibrated` statuses lock the Save button and inputs. Saving shows a finality warning before submitting ratings to HR for calibration.

**Training workflow**: Three access levels — admin (full CRUD via `user_id` RLS), manager (team CRUD via `reporting_manager_id` chain, migration 040), employee (self-enrollment via insert/update policies). `ManagerTraining` has "Team Training" / "My Training" sub-view toggle (same pattern as appraisals). `getTeamTrainingRecords()` excludes manager's own records via `neq('employee_id', selfId)`. Employees and managers can create/edit own training records (`employeeSaveTrainingRecord`) and certifications (`employeeSaveCertification`, migration 042). Self-submitted certs start as `status: 'pending_review'`; admin verifies/rejects in TrainingManager.

**Tasks module**: `TasksPanel.jsx` shared across all three portals. Receives `role` prop and `navigateTo` callback. Aggregates pending approvals + expiry alerts from all modules via `taskStorage.js`. Each task item navigates to the relevant module on click. Auto-refreshes every 60s. Sidebar nav items with `divider: true` render a separator line above them.

**Sidebar nav divider pattern**: Nav items can have `divider: true` — the nav loop wraps each item in a `<div>` and renders a border-top divider before divider items. The `measurePill()` function uses `querySelector('.nav-item.active')` which still finds the button inside the wrapper `<div>`.

**Recursive component prop forwarding**: Every prop used inside a recursive component body must be forwarded to child calls. Omitting any prop causes silent crashes in subtrees (e.g. `OrgNode` with `depts`).

**`seedDefaultLeaveTypes()` has a module-level `_seedingTypes` lock** to prevent double-seeding from React 18 StrictMode.

**`getMyCompany()` with multiple branches**: uses `.order('created_at').limit(1)` before `.maybeSingle()`. Any future utility fetching a single company by `user_id` must do the same.

**Dashboard `getMonthName`**: Must be declared before `trendRuns` computation (temporal dead zone).

### EmployeeModal

Seven tabs for existing employees, four for new (Documents, Insurance, Contracts hidden without `employee?.id`). Save button hidden on Documents/Insurance/Contracts tabs.

**Mandatory validation**: Name, Employee No (unique), Work Email (unique), MOL ID (≥10 digits, unique), Bank Name, Bank Routing Code, IBAN, Basic Salary (> 0).

**Portal Role control**: Job tab `<select>` appears only when `employee?.id && employee?.authUserId`. Calls `setEmployeePortalRole()` RPC directly on change.

**Department dropdown**: `<select>` from `getDepartments()` — free-text entry not allowed.

**Documents tab**: grouped `<optgroup>` from `DOC_GROUPS` (exported). `CLINICAL_DOC_TYPES` Set exported — clinical docs use 90d amber threshold vs 60d. Employee-submitted docs show verify/reject buttons.

**Contracts tab**: actions call `saveEmployeeContract()` + `saveEmployee()` directly (bypass `onSave`, modal stays open). Append-only history.

## SQL Migrations

Files in `sql/` numbered sequentially. Run manually in Supabase SQL Editor. All idempotent.

When adding a new table, always include: `CREATE TABLE IF NOT EXISTS`, `ALTER TABLE … ENABLE ROW LEVEL SECURITY`, `GRANT ALL ON TABLE … TO authenticated`, `CREATE POLICY` statements. Then run:
```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
```

### Critical migrations

- **034** — Required for ManagerShell: adds `'manager'` to `user_profiles_role_check`. Without it, manager role inserts fail silently.
- **035** — `employees_manager_read` policy. Uses `get_manager_employee_id()` SECURITY DEFINER helper — **never** write self-referencing subqueries on `employees` inside `employees` RLS policies (causes infinite recursion).
- **037** — Required for ManagerLeaveQueue: adds leave/balance/type read policies for managers.
- **038** — Required for manager appraisal rating to update status.
- **039** — `shifts_authenticated_read` policy. Required for employee/manager roster view fallback (direct query on `roster_assignments` with embedded `shifts` join). Without it, shift names/times show as "—".
- **040** — Manager CRUD policies on `training_records` and `certifications` for direct reports. Also adds employee self-insert/update on `training_records` for self-enrollment.
- **042** — Certification self-service: adds `status` column to `certifications` (default `'verified'`), plus employee INSERT/UPDATE policies for self-submitted certs (`status: 'pending_review'`).
- **043** — Employee portal fixes: storage INSERT/SELECT policies for employee document upload/download, plus `employees_self_update_contact` UPDATE policy for profile editing.

### RLS model

**Admin tables**: `FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`.

**Employee self-service**: crosses RLS via SECURITY DEFINER RPCs + dedicated SELECT policies using `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())`.

**Manager policies** (migration 033): access direct reports via `employees.reporting_manager_id` chain.

**Notifications RLS**: split across four policies — SELECT/UPDATE use `recipient_user_id`, INSERT/DELETE use `user_id`.

**Permission errors**: `"permission denied"` = missing GRANT. Empty results (no error) = missing RLS policy. Many functions swallow errors and return `[]`.

### Key tables — non-obvious columns

- `employees`: NOT NULL columns include `mol_id`, `emp_no`, `name`, `bank_name`, `bank_routing_code`, `iban` — always pass `''` default. `work_email` stored lowercase.
- `clock_events`: `event_type` stored as uppercase `CLOCK_IN`/`CLOCK_OUT`.
- `attendance_records`: columns are `clock_in_time`, `clock_out_time`, `total_hours` (not `clock_in`, `clock_out`, `hours_worked`). Status must be uppercase.
- `leave_requests`: status is free TEXT (no CHECK), includes `'ManagerApproved'` / `'ManagerRejected'`.
- `salary_advances`: `status` is `'pending'` | `'active'` | `'settled'` | `'cancelled'`. Admin-created start as `'active'`; employee-requested start as `'pending'`.
- `assets`: status managed by `assignAsset()`/`returnAsset()` only — never set `'assigned'` manually.
- `roster_assignments`: `published BOOLEAN` gates employee portal visibility. `shift_id` FK → `shifts` with nested data.
- `certifications`: `status` is `'verified'` (default) | `'pending_review'` | `'rejected'`. Self-submitted certs start as `'pending_review'`.

### Supabase Storage

One private bucket: `employee-documents`. Path: `{admin_user_id}/{employee_id}/{timestamp}_{filename}`. Signed URLs expire after 1 hour. Leave attachments stored under `leave/` subfolder (7-day URLs). Bucket must be created manually in Supabase Dashboard.

### Employee self-service RPCs

All resolve caller via `employees.auth_user_id = auth.uid()`. Key RPCs: `link_employee_account`, `employee_record_clock_event` (normalises event type with `UPPER()`), `employee_submit_leave_request`, `employee_request_advance`, `employee_submit_expense`, `employee_submit_document`, `employee_request_letter`, `employee_get_my_roster`, `employee_request_shift_swap`, `manager_approve_leave`, `manager_reject_leave`, `admin_set_employee_portal_role`.

## Styling

Single CSS file: `src/index.css`. `--primary: #2563EB`, `--accent: #06B6D4`. Sidebars: solid `#08122e`.

Admin: `.page-header` / `.page-body` / `.card`. Employee: `.emp-page-header` / `.emp-page-body` / `.emp-card`.

`.emp-card` has no default padding — use `.emp-card-header` (14px 18px + border) / `.emp-card-body` (16px 18px).

**Light-background components** (notification panel, tasks panel, page content): use slate-scale hex colors (`#0f172a` headings, `#1e293b` titles, `#64748b` body, `#94a3b8` muted). Never use `rgba(255,255,255,...)` colors — those are for the dark sidebar only. `NotificationBell` panel uses lucide-react icons (not emoji) with tinted icon containers.

## Manual Testing Workflow

Structured 13-day checklist in `MANUAL_TEST_CHECKLIST.md`. Condensed remaining-items file: `REMAINING_TESTS.md` (2-session split of Days 11–13).

| Day | Area | Portal |
|-----|------|--------|
| 1 | Auth · Dashboard · Clinical Dashboard | Admin |
| 2 | Company Settings · Employees (basic) | Admin |
| 3 | Employees (advanced: Docs · Insurance · Contracts · Probation · Offboarding) | Admin |
| 4 | Departments · Letter Requests | Admin |
| 5 | Payroll (create → approve → SIF → WPS) | Admin |
| 6 | Advances · Expenses | Admin |
| 7 | Leave (all 5 tabs) | Admin |
| 8 | Attendance · Biometric Import · Assets | Admin |
| 9 | Training · Appraisals | Admin |
| 10 | Roster · Reports (all 8 tabs) | Admin |
| 11 | Manager Portal (queue tabs · auth · appraisals · home · leave · schedule · attendance) | Manager |
| 12 | Manager Portal (remaining) · Employee Auth · Employee tabs E-1–E-7 | Manager → Employee |
| 13 | Employee tabs E-8–E-12 · Cross-portal flows · Edge cases | Employee + Cross-portal |

### Checklist format

```
### [ID] · [Short description] - [status]
- **Profile**: portal / sign-in
- **Setup**: prerequisites
- **Steps**: numbered actions
- **Pass**: expected behaviour
- **Bug**: what went wrong
  - **Fixed**: what was changed
```

Status: blank (untested), `completed`, `partial`, `bug`. **⏭ DEFER** items revisited on their target day.

### When asked for Day N instructions

- Read full `MANUAL_TEST_CHECKLIST.md`
- Include deferred items from Days 1–(N-1) at the top
- Expand each task to full Profile/Setup/Steps/Pass/Bug format
- Steps must be explicit enough to follow cold
- Reference prerequisite task IDs in Setup

### Bug-fixing rules

1. Find root cause, not symptom
2. Fix the whole class of problem (grep for same pattern elsewhere)
3. Never patch around symptoms
4. Run `npm run build` after fixing
5. Update checklist with `**Fixed**: [explanation]`

### Known bug patterns (already fixed — don't re-investigate)

- **PostgREST implicit INNER JOIN**: embedded related tables drop parent rows when RLS blocks child. Fix: `!left` hint or separate query + client-side merge.
- **CSV import missing `companyId`**: stamp `companyId: activeCompanyId` in import; use `.or('company_id.eq.X,company_id.is.null')` in queries.
- **Recursive component missing props**: grep for all recursive self-calls when adding a prop.
- **Local `formatDate` helpers**: always use `formatDateUAE()` from `uaeValidators.js`.
- **`regularisationRequest` approval must patch `attendance_records`** with corrected clock times.
- **React 18 StrictMode double-seeding**: use module-level lock flag.
- **Report builder field names**: must match `dbToXxx` converters exactly — check the converter, don't guess.
- **`getLeaveRequests()` for reports**: call unfiltered — status filtering in report builders.
- **Roster `shiftCategory` is nested**: access via `r.shift?.shiftCategory`, not `r.shiftCategory`.
- **`getMyRoster()` fallback**: RPC `employee_get_my_roster` is primary (SECURITY DEFINER, bypasses RLS). Falls back to direct query on `roster_assignments` with `shifts!left(...)` join when RPC returns empty. Requires migration 039 for shift data visibility.
- **`getMyAppraisals()` must filter by `employee_id`**: manager RLS exposes both own and team appraisals. Without `eq('employee_id', selfId)`, "My Appraisals" leaks team data.
- **Attendance history `RECENT_DAYS`**: set to 30 days in `EmpAttendance`. Lower values (e.g. 14) make history appear empty for infrequent clockers.
