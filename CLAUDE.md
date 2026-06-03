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
npm test                        # Full test suite, headless
npm run test:ui                 # Playwright UI mode — visual step-by-step, best for debugging
npm run test:auth               # Auth flows only
npm run test:attendance         # Attendance flows only (most critical)
npm run test:employees          # Employee CRUD only
npm run test:payroll            # Payroll flows only
npm run test:report             # Open HTML report from last run

# Run only the Feature 1–6 spec files
npx playwright test emiratization documents insurance notifications advances multi-level-leave

# Run a single feature spec
npx playwright test emiratization          # Feature 1 — Emiratization / Nafis
npx playwright test documents             # Feature 2 — Document Storage
npx playwright test insurance             # Feature 3 — Medical Insurance
npx playwright test notifications         # Feature 4 — Notification System
npx playwright test advances              # Feature 5 — Salary Advances
npx playwright test multi-level-leave     # Feature 6 — Multi-Level Leave Approval

# Run tests matching a name pattern across all files
npx playwright test --grep "bell icon"
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

`global-setup.js` runs once before all tests: creates `test.admin@workloop-test.local` and `test.employee@workloop-test.local` auth users, seeds company/employee rows, then saves browser sessions to `.playwright/admin-session.json` and `.playwright/employee-session.json` so tests start pre-logged-in. `global-teardown.js` cleans test data from: attendance, payroll, nafis_reports, insurance_policies/dependants/employee_insurance, notifications, employee_documents, salary_advances (repayments cascade-delete), and leave_approval_delegates — labelled "Feature 1–6 test data".

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

**Strict mode — duplicate navigation buttons**: The Dashboard renders secondary buttons that duplicate sidebar nav labels (e.g., a "Company Settings" button inside the MOL Employer ID warning alert). `getByRole('button', { name: 'Company Settings' })` will match both and throw a strict mode violation. Always scope sidebar navigation clicks to `.sidebar-nav`:
```js
// ❌ Ambiguous — matches sidebar nav AND any inline alert/prompt buttons
await page.getByRole('button', { name: 'Company Settings' }).click();

// ✅ Scoped to sidebar only
await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
```
The same risk applies to any nav label that also appears as an inline link inside a page alert or prompt.

**`test.use({ storageState })` must be scoped inside describe blocks — never at file level — when a spec file mixes admin and employee tests**: A file-level `test.use` applies to ALL describe blocks, including employee ones that call `loginAsEmployee(page)`. With the admin session loaded, `page.goto('/')` lands on the admin shell and `loginAsEmployee` can't find the "Sign in as Employee" button (times out). Fix: place `test.use({ storageState: '.playwright/admin-session.json' })` **inside** each admin describe block; the employee describe has no `test.use` so pages start unauthenticated. See `advances.spec.js` and `notifications.spec.js` for the correct pattern.

**Stat card text collisions — avoid case-insensitive regex across card sub-labels**: `hasText: /Active Advances/i` matches ANY stat card whose full text content (label + value + sub-label) contains "active advances". If a sibling card's sub-label says "AED — active advances" it will match too (strict mode violation). Use case-sensitive regex (`/Active Advances/` without `i`), scope to `.stat-label`, or ensure sub-label text is distinct from other cards' labels.

**Tab buttons — avoid sidebar collisions**: `getByRole('button', { name: /settings/i })` matches BOTH the Leave module's "Settings" tab button AND the sidebar's "Company Settings" nav button. Always scope module tab clicks to `page.locator('button.tab-btn').filter({ hasText: /^Settings$/i })` (using the `.tab-btn` class) rather than `getByRole`. This pattern applies to any tab label that also appears as a sidebar nav item name.

**`<option>` elements are "hidden" in Playwright**: Playwright's `toBeVisible()` returns `false` for `<option>` elements because they are not directly rendered — only the `<select>` parent is visible. To assert that a `<select>` contains specific placeholder text, check the `<select>` element itself: `page.locator('select').filter({ has: page.locator('option').filter({ hasText: /placeholder/i }) })`. Never call `.toBeVisible()` directly on an `<option>` locator.

## Environment

Create `sif-app/.env` with:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## SQL Migrations

New DB schema changes live in `sql/` as numbered files (`001_emiratization.sql`, `002_document_storage.sql`, …). Run each file manually in **Supabase Dashboard → SQL Editor → New Query**. There is no automated migration runner — files are applied in order by number. Each file is idempotent (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).

When adding a new table, always include in the same migration file:
1. `CREATE TABLE IF NOT EXISTS`
2. `ALTER TABLE … ENABLE ROW LEVEL SECURITY`
3. `GRANT ALL ON TABLE … TO authenticated`
4. `CREATE POLICY` statements

After adding any new migration, also run:
```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
```
…to keep the test suite's service role in sync.

## Architecture

**Workloop** is a UAE HR/payroll SaaS. It generates **SIF files** (Salary Information File — UAE WPS/MOL bank format) and manages employees, payroll, leave, and attendance. There are two completely separate UIs sharing one Supabase project.

See `FEATURES_ROADMAP.md` for the 22-feature implementation plan and current completion status.

### Dual-portal structure

| Portal | Entry point | Who uses it |
|--------|-------------|-------------|
| Admin (HR) | `App.jsx` → `AppShell` | Company owner/HR; `profile.role === 'admin'` |
| Manager | `App.jsx` → `ManagerShell` | Managers; `profile.role === 'manager'` |
| Employee self-service | `App.jsx` → `EmployeeShell` | Linked employees; `profile.role === 'employee'` |

`App.jsx` `Root` checks `profile.role` in order: `'employee'` → `EmployeeShell`, `'manager'` → `ManagerShell`, otherwise → `AppShell`. Both shells use a fixed floating sidebar island (solid `#08122e`, `border-radius: 22px`, `top/left/bottom: var(--sidebar-gap)`) with an animated sliding pill for the active nav item driven by `useLayoutEffect` + `getBoundingClientRect`.

`App.jsx` `Root` component: if `loading=false`, `user` exists, but `profile` is still null after 8 seconds, shows an error screen with a "Sign out and try again" button instead of spinning forever.

### Auth flow

`AuthContext.jsx` manages four auth actions. All email inputs are normalised to lowercase before being passed to any auth function.

- **`createCompany`** — Admin sign-up; detects existing accounts via `identities.length === 0` (Supabase silently returns the existing user on duplicate sign-up).
- **`signInAsAdmin`** — Verifies a `companies` row exists (via RLS); writes `user_profiles`.
- **`signUpAsEmployee`** — Employee first-time registration; calls `link_employee_account()` RPC to match `LOWER(auth.email())` → `LOWER(employees.work_email)`, upserts `user_profiles`, then **returns without auto-logging in**. `AuthPage` shows a success banner and switches to the sign-in form; the employee signs in manually next.
- **`signInAsEmployee`** — Checks for existing `user_profiles` row first (idempotent re-login); accepts **both** `'employee'` and `'manager'` roles on re-login so managers aren't forced back through the link flow. Falls back to `link_employee_account()` only on first login.

**Critical**: `setLoading` is ONLY called inside the `INITIAL_SESSION` / `TOKEN_REFRESHED` handler in `AuthContext`. Auth action functions (`signInAsAdmin`, `signInAsEmployee`, etc.) must never call `setLoading(true)` — doing so unmounts `AuthPage` (React re-renders `Root` to show a global spinner), destroying all local component state including error/success banners.

**Profile recovery on INITIAL_SESSION**: If `getProfile()` returns null, the handler attempts auto-recovery — checks `companies` table (admin path: calls `createAdminProfile()`) or re-runs `linkEmployeeAccount()` (employee path) before falling back to null.

**Email case normalisation**: `AuthPage.jsx` calls `.toLowerCase()` on every email before any auth call. `employeeToDb` in `storage.js` also lowercases `work_email` on save. The `link_employee_account` RPC compares with `LOWER()` on both sides.

### Data layer

All DB access goes through utility modules — components never call `supabase` directly except for RPCs and auth operations in `AuthContext`.

| File | Scope |
|------|-------|
| `utils/storage.js` | Admin CRUD: companies, employees, payroll runs/entries, payslip records, employee documents, Nafis reports, insurance policies/assignments/dependants, salary advances/repayments |
| `utils/notificationStorage.js` | In-app notifications: `getNotifications`, `getUnreadCount`, `markNotificationRead`, `markAllNotificationsRead`, `createNotification`, `createNotifications` (batch), `generateExpiryNotifications` |
| `utils/profileStorage.js` | Role resolution (`user_profiles`), employee self-service data (own record, own payslips, own company); `getEmployeePortalRole(employeeId)`, `setEmployeePortalRole(employeeId, role)` |
| `utils/leaveStorage.js` | Leave types, requests, balances, public holidays, delegates; `getLeaveQueueForManager`, `approveLeaveAsManager`, `rejectLeaveAsManager`, `getLeaveApprovalDelegates`, `saveLeaveApprovalDelegate`, `deleteLeaveApprovalDelegate` |
| `utils/attendanceStorage.js` | Attendance records, clock events, shifts, regularisation |

**Shape converters**: `storage.js` has `dbToXxx` / `xxxToDb` functions that translate between snake_case DB columns and camelCase JS objects. All components consume camelCase objects. `dbToDocument`, `dbToInsurancePolicy`, `dbToEmployeeInsurance`, `dbToInsuranceDependant`, `dbToAdvance`, and `dbToAdvanceRepayment` are all module-private converters (not exported). `dbToLeaveRequest` in `leaveStorage.js` now also maps Feature 6 fields: `managerApprovedAt`, `managerApprovedBy`, `managerRejectionReason`, `substituteEmployeeId`, `approvalLevelRequired`, `approvalComment`.

**`authUserId` in dbToEmployee**: `dbToEmployee` now maps `row.auth_user_id → emp.authUserId`. This field is `null` until the employee registers on the employee portal. It is used by `LeaveManager` and `PayrollEditor` to target notifications at the correct employee auth account.

**Column repurpose**: `payroll_entries.du_cost` stores `leaveDeduction` (per-employee leave deduction in a payroll run) — there was no schema migration; this column was repurposed in-place.

### Supabase schema (key tables)

- `companies` — one row per admin user (`user_id = auth.uid()`). New columns: `sector TEXT`, `nafis_quota_percent DECIMAL(5,2)` (Emiratization tracking).
- `employees` — all employees for a company; `auth_user_id` set when employee links their account; `user_id` = the admin's UUID; `work_email` is always stored lowercase. Several columns are NOT NULL (including `mol_id`, `emp_no`, `name`, `bank_name`, `bank_routing_code`, `iban`) — always pass `''` as default, never omit them in raw inserts. New column: `nafis_registration_no TEXT` (UAE nationals only).
- `user_profiles` — `role` ('admin'|'employee'|'manager'), `company_user_id`, `employee_id`; RLS restricts each user to their own row. Admins can change an employee's role to 'manager' via `admin_set_employee_portal_role` RPC (requires the employee to have activated their portal first)
- `payroll_runs` + `payroll_entries` — payroll run header + one row per employee
- `payslips` — snapshot of each employee's pay per period; created when admin downloads SIF (`createPayslipRecords`)
- `leave_types`, `leave_requests`, `leave_balances`, `public_holidays`
- `clock_events` — raw clock-in/out events; `user_id` = admin's UUID (even for self-service entries via RPC); `event_type` stored as uppercase `CLOCK_IN` / `CLOCK_OUT`
- `attendance_records` — derived daily record; columns: `clock_in_time`, `clock_out_time`, `total_hours` (not `clock_in`, `clock_out`, `hours_worked`); `status` must be uppercase (e.g. `'PRESENT'`) — the JS constants in `attendanceEngine.js` (`ATTENDANCE_STATUS.PRESENT = 'PRESENT'`) are all uppercase and the DB values must match exactly
- `attendance_periods` — one row per `(user_id, period YYYY-MM)`; closed by admin before payroll run
- `employee_job_history` — audit log of salary/title/department/status changes; written on every employee save
- `nafis_reports` — one snapshot per `(user_id, period YYYY-MM)`; upserted by `saveNafisReport()`. Stores headcount, Emirati count, ratio, compliance flag, and a JSON snapshot of UAE national employees at time of generation.
- `employee_documents` — one row per uploaded file per employee. Key columns: `document_type`, `file_name`, `file_size`, `storage_path` (path within the `employee-documents` Supabase Storage bucket), `expiry_date`, `notes`. The `storage_path` is used to generate signed URLs and to delete from Storage on record delete.
- `insurance_policies` — company-level insurance plan records (insurer name, policy number, tier, annual premium, renewal date, broker). One admin can have multiple policies.
- `employee_insurance` — one coverage record per employee (`UNIQUE (user_id, employee_id)`); links to a policy, stores member ID, card number, effective/expiry dates. Upserted via `saveEmployeeInsurance()` using `onConflict: 'user_id,employee_id'`.
- `insurance_dependants` — family members covered under an employee's policy (name, relationship, DOB, card number). No uniqueness constraint — multiple rows per employee allowed.
- `notifications` — in-app notifications with `UNIQUE (recipient_user_id, type, related_entity_id)` for deduplication. `user_id` = who created it (admin), `recipient_user_id` = who sees it (admin or employee). Four separate RLS policies: SELECT/INSERT/UPDATE/DELETE with different conditions (see `sql/004_notifications.sql`). Expiry alerts embed a threshold suffix in `related_entity_id` (e.g. `{employeeId}_visa_30d`) so 60-day and 30-day alerts are separate rows.
- `salary_advances` — one row per advance/loan disbursement. `status` is `'pending'` (employee self-request awaiting approval) | `'active'` (approved, repayments ongoing) | `'settled'` (fully repaid) | `'cancelled'` (rejected or voided). Admin-created advances start as `'active'`; employee-requested advances start as `'pending'` via the `employee_request_advance` RPC. Stores `repayment_months`, `monthly_deduction` (= amount ÷ months), and `outstanding_balance` (decremented on each repayment).
- `advance_repayments` — one row per monthly deduction; linked to `salary_advances` (CASCADE delete) and optionally to `payroll_runs`. Written by `saveAdvanceRepayment()` which also calls `updateAdvanceBalance()` to decrement the parent advance and auto-transition to `'settled'` when balance hits zero.
- `leave_requests` — extended with Feature 6 columns: `manager_approved_at`, `manager_approved_by TEXT`, `manager_rejection_reason TEXT`, `substitute_employee_id UUID`, `approval_level_required INT DEFAULT 1`, `approval_comment TEXT`. Status values now include `'ManagerApproved'` (manager pre-approved, awaiting HR final sign-off) and `'ManagerRejected'` (manager rejected — final). No CHECK constraint on status — the column is free TEXT.
- `leave_approval_delegates` — admin configures a deputy approver when a manager is on leave. `approver_employee_id` = the absent manager, `delegate_employee_id` = the colleague covering them, `from_date`/`to_date` = coverage window. Both manager and delegate can read their own rows via `leave_approval_delegates_actor_read` policy.

### Supabase Storage

One private bucket: **`employee-documents`**. Files are stored at path `{admin_user_id}/{employee_id}/{timestamp}_{sanitised_filename}`. The path prefix `{admin_user_id}` is enforced by Storage RLS policies so admins can only access their own files.

**Signed URLs**: `getEmployeeDocuments()` calls `createSignedUrl(path, 3600)` for each document after fetching the DB rows — URLs expire after 1 hour. `uploadEmployeeDocument()` also generates a signed URL immediately after upload so the new document is usable without a second load call. Never store public URLs for this bucket — it is private.

**Bucket must be created manually** in Supabase Dashboard → Storage before the Documents tab will work. See `sql/002_document_storage.sql` for the required Storage RLS policy expressions.

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

**Admin tables** (`companies`, `employees`, `payroll_*`, `payslips`, `leave_*`, `clock_events`, `attendance_records`, `attendance_periods`, `employee_job_history`, `nafis_reports`, `employee_documents`, `insurance_policies`, `employee_insurance`, `insurance_dependants`, `leave_approval_delegates`) use `FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`.

**Employee self-service** crosses the RLS boundary via `SECURITY DEFINER` RPCs and dedicated SELECT policies:

| Table | Employee policy |
|-------|----------------|
| `employees` | `auth_user_id = auth.uid()` |
| `payslips` | `employee_id` matched via linked employee |
| `leave_requests`, `leave_balances` | `employee_id` matched via linked employee |
| `clock_events` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `attendance_records` | same pattern as clock_events |
| `employee_documents` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `employee_insurance` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `salary_advances` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `advance_repayments` | `advance_id IN (SELECT sa.id FROM salary_advances sa JOIN employees e ON e.id = sa.employee_id WHERE e.auth_user_id = auth.uid())` |
| `leave_approval_delegates` | `approver_employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid()) OR delegate_employee_id IN (...)` |

**Notifications RLS** is split across four separate policies (not a single `FOR ALL`): SELECT and UPDATE use `recipient_user_id = auth.uid()`; INSERT uses `user_id = auth.uid()` (admin creates for anyone); DELETE uses `user_id = auth.uid()` (admin deletes their own). This lets the employee portal read and mark-read its own notifications without being able to insert or delete.

### Employee self-service RPCs (SECURITY DEFINER)

These must exist in Supabase. All look up the caller's employee via `employees.auth_user_id = auth.uid()`. All require `GRANT EXECUTE ON FUNCTION <name> TO authenticated`.

| RPC | What it does |
|-----|-------------|
| `link_employee_account()` | Links employee email → auth user; compares `LOWER(work_email) = LOWER(auth.email())` |
| `employee_submit_leave_request(...)` | Validates + inserts leave request |
| `employee_cancel_leave_request(p_request_id)` | Cancels a pending request |
| `employee_record_clock_event(p_event_type, p_notes)` | Inserts clock event with admin's `user_id`; upserts `attendance_records`. Normalises `p_event_type` with `UPPER()` internally. Uses SELECT + INSERT/UPDATE (not `ON CONFLICT`) to avoid dependency on a named unique index. Stores `status = 'PRESENT'` (uppercase) to match `ATTENDANCE_STATUS.PRESENT`. |
| `employee_submit_regularisation(...)` | Submits an attendance correction request |
| `employee_request_advance(p_amount, p_reason)` | Creates a `'pending'` salary advance for the linked employee; returns the new advance UUID. Admin must approve (set to `'active'`) before repayments begin. |
| `manager_approve_leave(p_request_id)` | Manager approves a direct report's leave. If `approval_level_required ≤ 1` → status becomes `'Approved'` immediately. If 2-level → status becomes `'ManagerApproved'` (awaits HR final sign-off). Verifies caller is the reporting manager or an active delegate. |
| `manager_reject_leave(p_request_id, p_reason)` | Manager rejects a `'Pending'` or `'ManagerApproved'` request. Sets status to `'ManagerRejected'`. |
| `admin_set_employee_portal_role(p_employee_id, p_role)` | Admin sets an employee's portal role to `'employee'` or `'manager'`. Requires the employee to have activated their portal (user_profiles row must exist). |
| `admin_get_employee_portal_role(p_employee_id)` | Returns current portal role string for an employee, or NULL if not activated. |

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

**EmployeeModal tab layout**: The modal has **six tabs for existing employees**, four for new employees (Documents and Insurance tabs are hidden when `employee?.id` is absent):
- Personal — name (`placeholder="e.g. John Smith"`), contact info, emergency contact
- Job & Contract — title, department, reporting manager, shift, dates
- Salary & Bank — MOL ID, salary breakdown, bank details. Basic salary: `placeholder="e.g. 5000"`
- UAE Compliance — nationality, visa, passport, Emirates ID, labour card, Nafis registration number (enabled only when `nationality === 'United Arab Emirates'`)
- Documents *(existing employees only)* — file upload form (type, expiry, notes, file picker) + document list with signed-URL links, expiry status badges, and delete.
- Insurance *(existing employees only)* — coverage assignment (policy selector, member ID, card number, effective/expiry dates) with its own "Assign/Update Coverage" button, plus dependants add/delete table.

The **Save button is hidden** on both the Documents and Insurance tabs — each section has its own dedicated save action. This is enforced via `tab !== 'documents' && tab !== 'insurance'` in the modal footer.

**Emiratization compliance**: `Dashboard.jsx` computes `emiratiEmps` by filtering active employees where `nationality === 'United Arab Emirates'`. The required ratio comes from `company.nafisQuotaPercent` (set in Company Settings). `NafisReportModal.jsx` generates a full compliance report with CSV export and DB snapshot save via `saveNafisReport()`. The `nafis_reports` table has a `UNIQUE (user_id, period)` constraint — `saveNafisReport` upserts by period.

**Company Settings sector auto-fill**: When the admin selects an industry sector in Company Settings, the `nafisQuotaPercent` field is automatically pre-filled with that sector's default quota (defined in the `SECTORS` constant in `CompanySettings.jsx`). The admin can then override it manually.

**Document signed URL expiry**: Signed URLs from `getEmployeeDocuments()` expire after 1 hour. If a user leaves the Documents tab open for a long time and then clicks a link, it may 403. Regenerate by switching away from the tab and back — the `useEffect` in `EmployeeModal` re-fetches documents whenever `tab === 'documents'` changes.

**Insurance policies in Company Settings**: The Insurance Policies card manages `insurance_policies` rows independently of the main company save button — it has its own `handleSavePolicy` / `handleDeletePolicy` handlers with local state. The `policyRenewalStatus()` helper (module-level in `CompanySettings.jsx`, not exported) computes the badge class (green/amber/red) from `renewalDate`.

**Employee Insurance tab load**: When the Insurance tab becomes active, a `useEffect` in `EmployeeModal` fires a `Promise.all([getInsurancePolicies(), getEmployeeInsurance(employee.id), getInsuranceDependants(employee.id)])` — three parallel queries. The coverage form is pre-populated from the existing `employee_insurance` row if one exists. `saveEmployeeInsurance` upserts on `user_id,employee_id` so it always produces exactly one record per employee.

**Notification bell**: `NotificationBell.jsx` is a single shared component used in both `AppShell` (admin sidebar) and `EmployeeShell` (employee sidebar). It renders `<button title="Notifications">` — use this selector in tests. The panel opens as a `position: fixed` right-side drawer (right: 12px, top: 12px, bottom: 12px, width: 380px). The bell polls `getUnreadCount()` every 60 seconds via `setInterval` in a `useEffect`; the full list is only fetched when the panel opens. Clicking a notification calls `markNotificationRead(id)` — the row's `read_at` is set to the current timestamp.

**Notification deduplication**: `createNotifications()` uses `upsert` with `onConflict: 'recipient_user_id,type,related_entity_id'` and `ignoreDuplicates: true` — this generates `ON CONFLICT DO NOTHING`. The `related_entity_id` for expiry alerts embeds a threshold band (e.g. `{empId}_visa_60d`, `{empId}_visa_30d`) so a separate notification is created at each threshold even though the same document expiry is being tracked.

**`generateExpiryNotifications`** is called once at the end of the Dashboard's `Promise.all` data load (not in a `useEffect`) — it runs async after `setLoading(false)` and silently ignores errors so a missing notifications table never breaks the Dashboard. It generates document, insurance, and policy renewal notifications for the admin (recipient = admin uid).

**Notification hooks in feature code**: `LeaveManager.handleApproval` creates a `leave_approved`/`leave_rejected` notification targeted at `emp.authUserId` — only fires if the employee has linked their portal account. `PayrollEditor.handleSubmitPayroll` batch-creates `payslip_available` notifications for all linked employees after `createPayslipRecords`. Both calls use `.catch(() => {})` to silently ignore failures if the notifications table doesn't exist yet.

**AdvancesManager (admin)**: Standalone page, nav item "Advances" sits between "Payroll Module" and "Leave" in `NAV_ITEMS`. Loads all advances + employees on mount. Approve/reject pending requests by calling `saveAdvance({ ...adv, status: 'active'/'cancelled' })`; settle/cancel active advances the same way. Repayment history per advance fetched lazily via `getAdvanceRepayments(advanceId)` when the row is expanded. `saveAdvance()` auto-computes `monthly_deduction = amount / repayment_months` if `monthlyDeduction` is not explicitly passed.

**EmpAdvances (employee self-service)**: Tab "Advances" sits between "Payslips" and "Profile" in `EmployeeShell` TABS. Calls `getAdvances(emp.id)` (reads via employee self-read RLS policy, not admin scope). Advance request form calls `supabase.rpc('employee_request_advance', { p_amount, p_reason })` directly — the RPC resolves the employee from `auth.uid()`. Active advances show a progress bar: `(amount - outstandingBalance) / amount * 100`.

**PayrollEditor advance info panel**: A `useEffect` loads all `active` advances via `getAdvances()` (no employeeId filter) and groups them by `employeeId` into `advanceData` state. The info panel renders only when `Object.keys(advanceData).length > 0` — it's purely informational; deductions must still be applied manually via the AllowDeductPanel. Silently swallows errors (table may not exist yet — `.catch(() => {})`).

**ManagerShell (Feature 6)**: Portal shell for `profile.role === 'manager'` users. Same visual design as `EmployeeShell`. Tabs: Leave Queue (`ManagerLeaveQueue`), My Leave (reuses `EmpLeave`), Attendance (`EmpAttendance`), Payslips (`EmpPayslips`), Profile (`EmpProfile`). Sidebar footer shows "Manager Portal" sub-label. Managers sign in via the Employee portal sign-in form — the `signInAsEmployee` flow recognises the existing 'manager' role on re-login.

**ManagerLeaveQueue (Feature 6)**: Loaded in `ManagerShell`. On mount, calls `getMyEmployeeRecord()` to get the manager's employee ID, then `getLeaveQueueForManager(emp.id)` to fetch pending/history from direct reports. Approve calls `approveLeaveAsManager(id)` (RPC); reject opens an inline modal requiring a reason, then calls `rejectLeaveAsManager(id, reason)`. History section (ManagerApproved/ManagerRejected) toggles via a ChevronDown/Up button.

**LeaveManager multi-level support (Feature 6)**:
- `pendingRequests` count now includes `'ManagerApproved'` (pre-approved by manager, awaiting HR) as well as `'Pending'`.
- In the Requests table, `'ManagerApproved'` status shows a "Final OK" + reject button pair for HR to give final sign-off via `updateLeaveRequestStatus`.
- The `approvedBy` cell conditionally shows "Mgr: {managerApprovedBy}" for ManagerApproved, and "Mgr rejected" (red) for ManagerRejected.
- Settings tab has an "Approval Delegation" card for admin to configure `leave_approval_delegates` rows (add by filling approver + delegate + date range; delete via trash icon). `getLeaveApprovalDelegates()` is loaded in `loadAll()` via `Promise.all` with `.catch(() => [])` so a missing table silently produces empty state.
- `leaveEngine.LEAVE_STATUS_COLORS` now includes `ManagerApproved: 'badge-blue'` and `ManagerRejected: 'badge-red'`.

**EmployeeModal Portal Role control (Feature 6)**: In the Job & Contract tab, a "Portal Role" `<select>` dropdown appears **only** when `employee?.id && employee?.authUserId` (existing employee with activated portal). Options: Employee / Manager. Changing the select immediately calls `setEmployeePortalRole(employee.id, newRole)` (RPC call — not part of the main Save flow). Current role is loaded via `getEmployeePortalRole(employee.id)` in a `useEffect` that fires when `tab === 'job' && employee?.authUserId` changes. Success/error feedback shown inline via `portalRoleOk` / `portalRoleErr` state.

**EndOfServiceScreen advance auto-load**: A `useEffect` fires on `employee.id` and calls `getAdvances(employee.id)`, sums `outstandingBalance` across all `active` advances, and pre-populates the "Outstanding Salary Advances" input. The field hint changes to "Auto-loaded from Advances module. Edit to override." once loaded (`advancesLoaded` state). The field remains editable so the admin can manually correct the figure.

### Business logic utilities

- **`utils/sifGenerator.js`** — Generates the UAE WPS SIF file format (SCR header + EDR per employee). Amounts are integer AED (not fils). Filename format: `{MOL_ID}{YYMMDD}{HHMMSS}.sif`. **Line endings must be `\r\n` (CRLF)** — banks reject files with LF-only endings (all lines appear as one row). `generateSIF()` uses `lines.join('\r\n')`. `parseSIFPreview()` uses `/\r?\n/` to tolerate both. The download Blob must use `type: 'application/octet-stream'` with a `Uint8Array` (via `TextEncoder`) — `text/plain` allows macOS browsers to strip the `\r` on download, reintroducing the same parse failure even after correct generation.
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
