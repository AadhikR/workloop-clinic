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

# Testing (Playwright E2E — requires dev server running in a separate terminal)
npm test              # Full test suite, headless
npm run test:ui       # Playwright UI mode — visual step-by-step, best for debugging
npm run test:auth     # Auth flows only
npm run test:attendance  # Attendance flows only (most critical)
npm run test:employees   # Employee CRUD only
npm run test:payroll     # Payroll flows only
npm run test:report   # Open HTML report from last run
```

### Test suite setup

Copy `.env.test.example` → `.env.test` and fill in:
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — same as `.env`
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase Dashboard → Project Settings → API → `service_role` key

The service role key is used only in `tests/global-setup.js` (Node.js, never the browser) to create test users and seed data. Before running tests for the first time, also run this in Supabase SQL Editor to grant the service role access to all tables:

```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

`global-setup.js` runs once before all tests: creates `test.admin@workloop-test.local` and `test.employee@workloop-test.local` auth users, seeds company/employee rows, then saves browser sessions to `.playwright/admin-session.json` and `.playwright/employee-session.json` so tests start pre-logged-in. `global-teardown.js` cleans attendance and payroll test data afterward.

Test files in `tests/` use `storageState` to load saved sessions. Attendance tests open two browser contexts simultaneously (admin + employee) to verify cross-portal clock-in visibility.

### Playwright selector patterns (hard-won)

**Shell selectors**: Admin shell renders `<div className="sidebar-logo">` → use `.sidebar-logo`. Employee shell renders `<div className="emp-sidebar-logo">` → use `.emp-sidebar-logo`. Never use `.sidebar-logo` for an employee-session page.

**Auth submit buttons**: The auth page buttons say "Sign in as Admin" / "Sign in as Employee" (not "Sign in"). Always use `locator('button[type="submit"]')` for form submission — never `getByRole('button', { name: /^sign in$/i })`.

**Components with loading guards**: Several components start with `useState(true)` and render ONLY a spinner until data loads:
- `AttendanceManager`: `if (loading) return <div>Loading attendance module…</div>` — stat cards, Refresh button, Close Period button, and ALL page content are absent from the DOM while loading.
- `EmpLeave`: `if (loading) return <div>Loading…</div>`

**Critical test pattern**: Do NOT chain `waitFor(text, {state:'hidden'})` then check for content — this races React. If Playwright evaluates the `hidden` check before React has rendered the component at all, the text was never there so `hidden` is immediately true, but the content isn't there either. Instead, wait directly for the target element you care about:
```js
// Wrong — races React render:
await expect(page.locator('text=Loading attendance module')).toBeHidden({ timeout: 20000 });
await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 5000 }); // can fail

// Correct — Playwright retries until element exists:
await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 20000 });
```

**EmpLeave form is inline, not a modal**: Clicking "Apply" in the employee Leave page sets `showForm=true`, revealing a form inside `div.emp-card` (not a `div.modal`). Selectors: `.emp-card select` for leave type, `.emp-card input[type="date"]` for dates, `.emp-card button[type="submit"]` to submit. On success `showToast('success', …)` renders `<div className="alert alert-success">` and `setShowForm(false)` hides the form.

**EmployeeManager archive**: The "delete" icon button in each row has `title="Delete employee"` (no text). Clicking it opens a confirmation dialog with an "Archive Employee" button. After archiving, the employee's `employmentStatus` becomes `'Terminated'` but they remain visible in the default "All Statuses" view — they do NOT disappear. Test for the "Terminated" badge on the row, not for row absence.

**`supabase.auth.getUser()` race**: This call validates the JWT server-side. In Playwright tests, the sidebar may be visible (React auth state is set) while `getUser()` still returns null — a brief window during Supabase's auth initialization. Components that call `getUser()` on mount (e.g., `initialiseLeaveModule`) may throw "Not authenticated" and log to console even though the UI loads correctly. Console-error tests should filter `Failed to load resource` lines or target specific JS runtime errors rather than expecting zero console output.

**Refresh token rotation across shared storageState**: Supabase rotates refresh tokens on every use. When multiple `test.describe` blocks all load the SAME `storageState` file (e.g. `admin-session.json`), the first block to run rotates the refresh token; later blocks load the stale RT from disk and get `SIGNED_OUT` when their access token expires. Symptom: tests see the sidebar briefly (INITIAL_SESSION fires with the still-valid JWT), then the page switches to the login page once a real API call returns 401. Fix: the LAST describe block that uses that storageState should drop `test.use({ storageState })` entirely and call `loginAsAdmin(page)` (or equivalent) in `beforeEach` to create a guaranteed-fresh session.

**`locator.isVisible()` is non-waiting**: Playwright's `isVisible()` returns `false` immediately if the element is not in the DOM — it does NOT retry or wait. Calling it right after `page.goto()` will return `false` while the app is still on its initial loading spinner. Use `.waitFor()` or `expect(locator).toBeVisible({ timeout: N })` when you need to wait for the element to appear.

**Combined CSS + Playwright text selector is invalid**: `page.locator('.foo, text=/bar/i')` — Playwright treats the whole string as CSS and rejects the `text=` part. Use `.or()`: `page.locator('.foo').or(page.getByText(/bar/i))`.

**`option[value!=""]` is not valid CSS**: jQuery inequality attribute selector. Use `locator('option').count()` and treat a count of `<= 1` as "only the placeholder exists".

**React 18 batching of transient loading states**: When data loads very quickly, React 18 may batch `setLoading(true)` and `setLoading(false)` in the same microtask, so the loading spinner is never painted to the DOM. Do not write tests that assert the spinner IS visible — assert only the end state (e.g., stat cards visible after load). The month-change and Refresh-click tests are the specific cases where this applies in this codebase.

## Environment

Create `sif-app/.env` with:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## Architecture

**Workloop** is a UAE HR/payroll SaaS. It generates **SIF files** (Salary Information File — UAE WPS/MOL bank format) and manages employees, payroll, leave, and attendance. There are two completely separate UIs sharing one Supabase project.

### Dual-portal structure

| Portal | Entry point | Who uses it |
|--------|-------------|-------------|
| Admin (HR) | `App.jsx` → `AppShell` | Company owner/HR; `profile.role === 'admin'` |
| Employee self-service | `App.jsx` → `EmployeeShell` | Linked employees; `profile.role === 'employee'` |

`App.jsx` renders either `AppShell` or `EmployeeShell` based on `profile.role` from `AuthContext`. Both shells use a fixed floating sidebar island (solid `#08122e`, `border-radius: 22px`, `top/left/bottom: var(--sidebar-gap)`) with an animated sliding pill for the active nav item driven by `useLayoutEffect` + `getBoundingClientRect`.

`App.jsx` `Root` component: if `loading=false`, `user` exists, but `profile` is still null after 8 seconds, shows an error screen with a "Sign out and try again" button instead of spinning forever.

### Auth flow

`AuthContext.jsx` manages four auth actions. All email inputs are normalised to lowercase before being passed to any auth function.

- **`createCompany`** — Admin sign-up; detects existing accounts via `identities.length === 0` (Supabase silently returns the existing user on duplicate sign-up).
- **`signInAsAdmin`** — Verifies a `companies` row exists (via RLS); writes `user_profiles`.
- **`signUpAsEmployee`** — Employee first-time registration; calls `link_employee_account()` RPC to match `LOWER(auth.email())` → `LOWER(employees.work_email)`, upserts `user_profiles`, then **returns without auto-logging in**. `AuthPage` shows a success banner and switches to the sign-in form; the employee signs in manually next.
- **`signInAsEmployee`** — Checks for existing `user_profiles` row first (idempotent re-login); falls back to `link_employee_account()` only on first login.

**Critical**: `setLoading` is ONLY called inside the `INITIAL_SESSION` / `TOKEN_REFRESHED` handler in `AuthContext`. Auth action functions (`signInAsAdmin`, `signInAsEmployee`, etc.) must never call `setLoading(true)` — doing so unmounts `AuthPage` (React re-renders `Root` to show a global spinner), destroying all local component state including error/success banners.

**Profile recovery on INITIAL_SESSION**: If `getProfile()` returns null, the handler attempts auto-recovery — checks `companies` table (admin path: calls `createAdminProfile()`) or re-runs `linkEmployeeAccount()` (employee path) before falling back to null.

**Email case normalisation**: `AuthPage.jsx` calls `.toLowerCase()` on every email before any auth call. `employeeToDb` in `storage.js` also lowercases `work_email` on save. The `link_employee_account` RPC compares with `LOWER()` on both sides.

### Data layer

All DB access goes through utility modules — components never call `supabase` directly except for RPCs and auth operations in `AuthContext`.

| File | Scope |
|------|-------|
| `utils/storage.js` | Admin CRUD: companies, employees, payroll runs/entries, payslip record creation |
| `utils/profileStorage.js` | Role resolution (`user_profiles`), employee self-service data (own record, own payslips, own company) |
| `utils/leaveStorage.js` | Leave types, requests, balances, public holidays |
| `utils/attendanceStorage.js` | Attendance records, clock events, shifts, regularisation |

**Shape converters**: `storage.js` has `dbToXxx` / `xxxToDb` functions that translate between snake_case DB columns and camelCase JS objects. All components consume camelCase objects.

**Column repurpose**: `payroll_entries.du_cost` stores `leaveDeduction` (per-employee leave deduction in a payroll run) — there was no schema migration; this column was repurposed in-place.

### Supabase schema (key tables)

- `companies` — one row per admin user (`user_id = auth.uid()`)
- `employees` — all employees for a company; `auth_user_id` set when employee links their account; `user_id` = the admin's UUID; `work_email` is always stored lowercase. Several columns are NOT NULL (including `mol_id`, `emp_no`, `name`, `bank_name`, `bank_routing_code`, `iban`) — always pass `''` as default, never omit them in raw inserts
- `user_profiles` — `role` ('admin'|'employee'), `company_user_id`, `employee_id`; RLS restricts each user to their own row
- `payroll_runs` + `payroll_entries` — payroll run header + one row per employee
- `payslips` — snapshot of each employee's pay per period; created when admin downloads SIF (`createPayslipRecords`)
- `leave_types`, `leave_requests`, `leave_balances`, `public_holidays`
- `clock_events` — raw clock-in/out events; `user_id` = admin's UUID (even for self-service entries via RPC); `event_type` stored as uppercase `CLOCK_IN` / `CLOCK_OUT`
- `attendance_records` — derived daily record; columns: `clock_in_time`, `clock_out_time`, `total_hours` (not `clock_in`, `clock_out`, `hours_worked`); `status` must be uppercase (e.g. `'PRESENT'`) — the JS constants in `attendanceEngine.js` (`ATTENDANCE_STATUS.PRESENT = 'PRESENT'`) are all uppercase and the DB values must match exactly
- `attendance_periods` — one row per `(user_id, period YYYY-MM)`; closed by admin before payroll run
- `employee_job_history` — audit log of salary/title/department/status changes; written on every employee save

### Supabase table permissions — critical

Tables created manually via SQL (not the Supabase UI) do **not** get automatic `GRANT` to the `authenticated` role. You must run both:

```sql
GRANT ALL ON TABLE tablename TO authenticated;   -- required or "permission denied" is thrown
ALTER TABLE tablename ENABLE ROW LEVEL SECURITY; -- then add RLS policies
```

**Diagnosing permission errors:**
- `"permission denied for table X"` → missing `GRANT` — the role cannot even reach the table
- Empty results with no error → `GRANT` exists but missing/wrong RLS policy
- `getAttendanceRecords` and similar functions swallow errors and return `[]`, so a missing GRANT silently produces empty data in the UI

### RLS model

**Admin tables** (`companies`, `employees`, `payroll_*`, `payslips`, `leave_*`, `clock_events`, `attendance_records`, `attendance_periods`, `employee_job_history`) use `FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`.

**Employee self-service** crosses the RLS boundary via `SECURITY DEFINER` RPCs and dedicated SELECT policies:

| Table | Employee policy |
|-------|----------------|
| `employees` | `auth_user_id = auth.uid()` |
| `payslips` | `employee_id` matched via linked employee |
| `leave_requests`, `leave_balances` | `employee_id` matched via linked employee |
| `clock_events` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `attendance_records` | same pattern as clock_events |

### Employee self-service RPCs (SECURITY DEFINER)

These must exist in Supabase. All look up the caller's employee via `employees.auth_user_id = auth.uid()`. All require `GRANT EXECUTE ON FUNCTION <name> TO authenticated`.

| RPC | What it does |
|-----|-------------|
| `link_employee_account()` | Links employee email → auth user; compares `LOWER(work_email) = LOWER(auth.email())` |
| `employee_submit_leave_request(...)` | Validates + inserts leave request |
| `employee_cancel_leave_request(p_request_id)` | Cancels a pending request |
| `employee_record_clock_event(p_event_type, p_notes)` | Inserts clock event with admin's `user_id`; upserts `attendance_records`. Normalises `p_event_type` with `UPPER()` internally. Uses SELECT + INSERT/UPDATE (not `ON CONFLICT`) to avoid dependency on a named unique index. Stores `status = 'PRESENT'` (uppercase) to match `ATTENDANCE_STATUS.PRESENT`. |
| `employee_submit_regularisation(...)` | Submits an attendance correction request |

### Key behavioral patterns

**Payroll locking**: `payroll_runs.status === 'generated'` → `isLocked = true` in `PayrollEditor`. All salary inputs, deduction fields, and action buttons are disabled. The lock banner is shown and the Submit/Save buttons are hidden.

**Soft-delete employees**: `archiveEmployee()` in `storage.js` sets `active = false, employment_status = 'Terminated'` — never hard-deletes.

**Auto job history**: `handleSaveEmployee` in `EmployeeManager` diffs `basicSalary`, `jobTitle`, `department`, `employmentStatus` before and after save, then calls `addJobHistoryEntry` for each changed field. Wrapped in its own `try/catch` so a missing RLS policy silently warns instead of blocking the save.

**Leave balance fallback**: `EmpLeave` and `EmpHome` compute balances locally when the DB `leave_balances` table is empty (admin never opened the Leave module). Falls back first to DB leave types, then to `DEFAULT_LEAVE_TYPES` from `leaveEngine.js`. `calculateAnnualLeaveAccrual` from `leaveEngine.js` computes accrued days from hire date.

**Attendance clock optimistic update**: `EmpAttendance.clock()` applies a local state update *before* awaiting the RPC, so the Clock Out button enables immediately after Clock In. State is reverted only if both the RPC and the direct-insert fallback fail.

**`EmpAttendance.loadData` — today and history are handled independently**: Today's record and history (past days) each have their own `attendance_records` query and their own `clock_events` fallback. They must never share a single `if (todayRecs.length > 0 || histRecs.length > 0)` branch — if they did, an empty `todayRecs` (record not yet written) combined with a non-empty `histRecs` (employee has past records) would run `setTodayRec(todayRecs[0] ?? null)` and wipe the optimistic clock-in state, showing "Not started" right after a successful clock-in.

**Attendance admin query**: `getAttendanceRecords` admin path queries by `employee_id IN (SELECT id FROM employees WHERE user_id = auth.uid())` rather than `user_id = auth.uid()`. This is more robust — it finds records regardless of what `user_id` the RPC wrote, and survives the fallback insert path.

**Attendance auto-poll**: `AttendanceManager` polls `loadAll(true)` every 30 seconds silently (no loading flash — the `silent` flag skips `setLoading(true)`). Manual Refresh button calls `loadAll()` (no argument) via `onClick={() => loadAll()}` — **never** `onClick={loadAll}` directly, which would pass the React synthetic event as the first argument, making `silent` truthy and silently suppressing the loading indicator. Month change triggers a full reload with loading screen.

**Missing clock-out derived dynamically**: `AttendanceManager` computes `missingClockOut` as `records.filter(r => r.clockInTime && !r.clockOutTime && r.date < todayStr)`. The DB field `r.missingClockOut` is never set by the employee RPC, so relying on it always returns an empty list.

**Dashboard `getMonthName`**: Must be declared *before* the `trendRuns` computation that calls it. Declaring it after with `const` causes a temporal dead zone crash once payroll data loads (the early `if (loading) return` hides the bug on first render).

**Photo upload removed**: `EmployeeModal` has no photo upload UI. The `photoUrl` field is preserved in the DB shape (`employeeToDb` still maps it) so existing data is not lost, but the UI to change it has been removed.

**EmployeeModal tab layout**: The modal has four tabs — Personal, Job & Contract, Salary & Bank, UAE Compliance. Key field locations:
- Name: Personal tab, `placeholder="e.g. John Smith"` (not "Full name")
- Work email: Personal tab, `placeholder="work@company.com"` (personal email is `placeholder="personal@email.com"`)
- Basic salary: **Salary & Bank tab**, `placeholder="e.g. 5000"` — must switch tabs to reach it
- Save button: `.modal-footer .btn-primary` (text varies: "Add Employee" for new, "Save Changes" for edit)

### Business logic utilities

- **`utils/sifGenerator.js`** — Generates the UAE WPS SIF file format (SCR header + EDR per employee). Amounts are integer AED (not fils). Filename format: `{MOL_ID}{YYMMDD}{seq}.sif`.
- **`utils/payslipGenerator.js`** — jsPDF payslip PDF. `generatePayslipPDF` is async (loads company logo). Always call `downloadPayslip(company, emp, run, entry)` from components, not `generatePayslipPDF` directly.
- **`utils/leaveEngine.js`** — UAE Federal Labour Law No. 33 of 2021 leave rules. Exports `DEFAULT_LEAVE_TYPES` (seed data), `calculateAnnualLeaveAccrual`, `countLeaveDays`, `validateLeaveRequest`.
- **`utils/gratuityCalculator.js`** — End-of-service gratuity per UAE law.
- **`utils/attendanceEngine.js`** — `ATTENDANCE_STATUS`, `STATUS_LABELS`, `STATUS_COLORS` constants + `deriveAttendanceStatus`.
- **`utils/uaeValidators.js`** — UAE-specific field validation (IBAN, Emirates ID, MOL ID) + formatters.

### Styling

Single CSS file: `src/index.css`. Solid-colour design system (glass/blur was removed):
- Body background: `#EEF2F7` with subtle blue/cyan radial gradients
- Cards/modals: `#ffffff`; form inputs: `#f8fafc`; table headers: `#e2e8f0`
- Sidebars: solid `#08122e` (no backdrop-filter)
- `--primary: #2563EB`, `--accent: #06B6D4`
- `--sidebar-gap: 12px` controls the floating island spacing on all sides
- Nav pill: `linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)` with spring animation (`cubic-bezier(0.34, 1.3, 0.64, 1)`)

Admin shell uses `.page-header` / `.page-body` / `.card` classes. Employee portal uses `.emp-page-header` / `.emp-page-body` / `.emp-card` parallels.
