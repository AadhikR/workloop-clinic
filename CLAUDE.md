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

# Testing (Playwright E2E — dev server auto-starts via playwright.config.js webServer block; reuses existing if already running)
npm test                        # Full test suite, headless
npm run test:ui                 # Playwright UI mode — visual step-by-step, best for debugging
npm run test:auth               # Auth flows only
npm run test:attendance         # Attendance flows only (most critical)
npm run test:employees          # Employee CRUD only
npm run test:payroll            # Payroll flows only
npm run test:report             # Open HTML report from last run

# Run all feature specs (1–21, skipping 15/18/20/22)
npx playwright test emiratization documents insurance notifications advances multi-level-leave leave-calendar shift-roster wps reports probation contracts offboarding expenses assets payroll-approval training multi-company employee-portal

# Run a single feature spec
npx playwright test emiratization          # Feature 1 — Emiratization / Nafis
npx playwright test documents             # Feature 2 — Document Storage
npx playwright test insurance             # Feature 3 — Medical Insurance
npx playwright test notifications         # Feature 4 — Notification System
npx playwright test advances              # Feature 5 — Salary Advances
npx playwright test multi-level-leave     # Feature 6 — Multi-Level Leave Approval
npx playwright test leave-calendar        # Feature 7 — Leave Calendar & Team Planner
npx playwright test shift-roster          # Feature 8 — Shift Scheduling & Roster
npx playwright test wps                   # Feature 9 — WPS Payment Confirmation
npx playwright test reports               # Feature 10 — HR Reports & Analytics
npx playwright test probation             # Feature 11 — Probation Period Management
npx playwright test contracts             # Feature 12 — Contract Renewal Management
npx playwright test offboarding           # Feature 13 — Offboarding Workflow
npx playwright test expenses              # Feature 14 — Expense Claims & Reimbursements
npx playwright test assets                # Feature 16 — Asset Management
npx playwright test payroll-approval      # Feature 17 — Payroll Approval (Maker-Checker)
npx playwright test training              # Feature 19 — Training & Certification Records
npx playwright test multi-company        # Feature 21 — Multi-Company / Branch Support
npx playwright test employee-portal     # Employee portal — all 12 tabs comprehensive
npx playwright test payroll             # Payroll — full coverage (list, editor, SIF, repeat)
npx playwright test leave               # Leave — full coverage (overview, requests, balances, settings)

# Clinic HRMS feature specs (1.1–7.2)
npx playwright test clinical-credentials        # Features 1.1 + 1.2 — Clinical creds & self-upload
npx playwright test letter-requests             # Feature 1.3 — Letter & Certificate Requests
npx playwright test clinical-rota               # Features 2.1 + 2.2 — Clinical duty rota & biometric import
npx playwright test probation-leave-rules       # Features 2.3 + 2.4 — Probation leave & attachments
npx playwright test departments                 # Feature 3.1 — Department hierarchy & staffing rules tab
npx playwright test manager-expense-queue       # Feature 3.2 — Multi-level expense approvals
npx playwright test clinical-dashboard          # Feature 4.1 — Clinical HR Dashboard (11 KPI cards)
npx playwright test salary-compliance           # Feature 5.1 — MoHRE salary distribution thresholds
npx playwright test appraisals                  # Feature 6.1 — Appraisal module
npx playwright test professional-licences       # Features 7.1 + 7.2 — Licences, SIF gate, staffing compliance

# Run all clinic specs together
npx playwright test clinical-credentials letter-requests clinical-rota probation-leave-rules departments manager-expense-queue clinical-dashboard salary-compliance appraisals professional-licences

# Additional coverage specs (auth, isolation, company settings, cross-portal workflows)
npx playwright test auth                # Auth flows (email case, sign-in/out, session persistence)
npx playwright test isolation           # Cross-profile data isolation and RLS enforcement
npx playwright test company-settings    # Company Settings page and branch switcher (Feature 21)
npx playwright test cross-profile       # Cross-portal workflows (all 3 sessions): leave/expense/advance/payroll/letter/doc/clinical
npx playwright test manager-portal      # Manager Portal all 8 tabs (requires sql/034_manager_role.sql)

# Run tests matching a name pattern across all files
npx playwright test --grep "bell icon"
```

### Test suite setup

Copy `.env.test.example` → `.env.test` and fill in:
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — same as `.env`
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase Dashboard → Project Settings → API → `service_role` key
- `TEST_MANAGER_EMAIL` / `TEST_MANAGER_PASSWORD` / `TEST_MANAGER_NAME` — manager test account (defaults already in `.env.test.example`; account is auto-created by global-setup)

The service role key is used only in `tests/global-setup.js` (Node.js, never the browser) to create test users and seed data. Before running tests for the first time, also run this in Supabase SQL Editor to grant the service role access to all tables:

```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

**Required migration for manager portal tests**: `sql/034_manager_role.sql` must be applied before running `manager-portal.spec.js` or `cross-profile.spec.js`. Without it, the `user_profiles_role_check` constraint rejects `role='manager'`, causing `ManagerShell` to silently never render. The spec's `beforeEach` guard detects this and skips with the message: `"apply sql/034_manager_role.sql in Supabase SQL Editor"`.

`global-setup.js` runs once before all tests: creates three test users (`test.admin@workloop-test.local`, `test.employee@workloop-test.local`, `test.manager@workloop-test.local`), seeds company/employee rows, links portal accounts, sets `test.employee`'s `reporting_manager_id` → test manager (enables queue tests), seeds deterministic test data (leave types/requests, expense claims, advances, assets, training, certifications, insurance policy, letter request, draft payroll run), then saves three browser sessions: `.playwright/admin-session.json`, `.playwright/employee-session.json`, `.playwright/manager-session.json`. Also writes `.playwright/env.json` with all seeded IDs for teardown. `global-teardown.js` cleans test data from all feature tables: attendance, payroll (runs/entries/payslips/approval_log), nafis_reports, insurance, notifications, employee_documents, salary_advances, employee_contracts, offboarding_checklists (tasks cascade), expense_claims, asset_assignments + assets, training_records, certifications, and extra company branches (Feature 21 — keeps only the primary branch).

Test files in `tests/` use `storageState` to load saved sessions. Attendance tests open two browser contexts simultaneously (admin + employee) to verify cross-portal clock-in visibility.

**Manager session and `user_profiles` deduplication**: During the manager browser login in `global-setup.js`, `signInAsEmployee`'s `linkEmployeeAccount()` call inserts a new `user_profiles` row with `role='employee'`. If a row already existed (from a prior service-role upsert), you now have **two rows** for the same `user_id`. When the test loads the saved session, `getProfile()` calls `.maybeSingle()` → PGRST116 (multiple rows) → returns null → auto-recovery runs `linkEmployeeAccount()` again → inserts yet another `role='employee'` row → ManagerShell never renders. Fix: in global-setup, after saving all sessions, use **delete-then-insert** (not upsert) to leave exactly ONE `user_profiles` row for the manager:
```js
await db.from('user_profiles').delete().eq('user_id', mgrUser.id);
await db.from('user_profiles').insert(
  { user_id: mgrUser.id, role: 'manager', company_user_id: adminUser.id, employee_id: managerEmpId }
);
```
This must run AFTER `browser.close()` so it takes effect after the browser session file is saved.

### Playwright selector patterns (hard-won)

**Shell selectors**: Admin shell renders `<div className="sidebar-logo">` → use `.sidebar-logo`. Employee shell renders `<div className="emp-sidebar-logo">` → use `.emp-sidebar-logo`. Never use `.sidebar-logo` for an employee-session page.

**Auth submit buttons**: The auth page buttons say "Sign in as Admin" / "Sign in as Employee / Manager" (not "Sign in"). Always use `locator('button[type="submit"]')` for form submission — never `getByRole('button', { name: /^sign in$/i })`. Managers sign in through the Employee / Manager form — there is no separate manager sign-in button.

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

**EmployeeManager archive**: The "delete" icon button in each row has `title="Delete employee"` (no text). Clicking it opens a confirmation dialog with an "Archive Employee" button. After archiving, the employee's `employmentStatus` becomes `'Terminated'` and the row **disappears** from the main Employee List (and from the status filter, which no longer offers a "Terminated" option) — it reappears under the separate **"Terminated Employees"** tab (third tab, alongside Employee List / Document Expiry; `UserX` icon). The "Terminated" stat card and the tab button both navigate there. Test for row *absence* in the Employee List tab and row *presence with a Terminated badge* in the Terminated Employees tab — not for the row staying in place. Shared row rendering uses `renderEmployeeRow(emp)` to avoid JSX duplication.

**EmployeeManager Document Expiry tab**: `DocumentExpiryPanel` accepts an `allDocs` prop (from `getAllEmployeeDocuments()`, fetched in parallel on mount alongside employees). The panel shows four groups: Visa, Emirates ID, Passport, Labour Card (employee-level fields) PLUS an **"Uploaded Documents"** group — any `employee_documents` row with `expiryDate` within 90 days (clinical types) or 60 days (other). Pass `allDocs={allDocs}` when rendering the panel; omitting it or passing `[]` silently hides the uploaded-doc group.

**NEVER use `supabase.auth.getUser()` in storage utility functions** — use `supabase.auth.getSession()` instead. `getUser()` makes a server-side JWT validation round-trip. In a full Playwright test run, this call triggers a Supabase refresh-token rotation. Because all test contexts share the same `storageState` file, subsequent test pages hold a stale RT; when any function later calls `getUser()`, Supabase returns 401 → fires `SIGNED_OUT` → the entire React app unmounts to the login page, cascading failures across every admin test that follows. The correct pattern throughout all `utils/*.js` files:
```js
// ✅ Reads local session — no server round-trip, no token rotation
const { data: { session } } = await supabase.auth.getSession();
const user = session?.user ?? null;
if (!user) throw new Error('Not authenticated');

// ❌ Server-side validation — rotates RT, causes SIGNED_OUT cascade in tests
const { data: { user } } = await supabase.auth.getUser();
```
Each storage file already has a private `getSessionUser()` helper that wraps this pattern. Use it for any new write function that needs the user's ID.

**`supabase.auth.getUser()` in AuthContext is the ONLY acceptable usage** — `AuthContext.jsx` is the single place that should call `getUser()`, because it runs before any storageState is involved (it authenticates directly with credentials). All other code must use `getSession()`.

**Refresh token rotation — symptom and proof**: In tests, the symptom is a screenshot showing the Workloop login page mid-test. This means `SIGNED_OUT` fired. Cause: a prior test (in any spec file) called `getUser()`, rotating the RT stored in the shared `.playwright/admin-session.json`. The fix is already applied — all storage utils use `getSession()`. If you see this symptom again, search `src/` for `supabase.auth.getUser` (none should exist outside `AuthContext`) and replace with `getSession()`.

**`locator.isVisible()` is non-waiting**: Playwright's `isVisible()` returns `false` immediately if the element is not in the DOM — it does NOT retry or wait. Calling it right after `page.goto()` will return `false` while the app is still on its initial loading spinner. Use `.waitFor()` or `expect(locator).toBeVisible({ timeout: N })` when you need to wait for the element to appear.

**`isVisible()` returns `true` for disabled buttons — use `isEnabled()` for conditional branching**: Playwright's `isVisible()` returns `true` for buttons that are in the DOM but have the `disabled` attribute. In `EmpAttendance`, the Clock In and Clock Out buttons are always rendered — they are never hidden, only `disabled={!canClockIn}` / `disabled={!canClockOut}`. Using `isVisible()` to decide whether to click the button will return `true` even when the button is disabled, causing the click to silently do nothing and subsequent assertions to time out. Use `isEnabled()` instead:
```js
// ❌ WRONG — returns true for disabled buttons
if (!(await clockInBtn.isVisible({ timeout: 3000 }).catch(() => false))) { ... }

// ✅ CORRECT — returns false for disabled buttons
if (!(await clockInBtn.isEnabled({ timeout: 3000 }).catch(() => false))) { ... }
```
**Corollary — `canClockIn` never resets after clock-out**: `EmpAttendance` computes `const canClockIn = !todayRec?.clockInTime`. Once an employee clocks in today, `clockInTime` is set permanently for the day. Clocking out does NOT reset it. Tests that need a fresh clock-in must handle the "already clocked in today" case with a graceful return/skip, not try to force a second clock-in.

**`waitForLoadState('networkidle')` hangs when components poll**: Three parts of the app have persistent polling that prevents networkidle from ever resolving:
- `AttendanceManager` (admin): polls `loadAll(true)` every 30 seconds
- `ManagerShell`: `NotificationBell` polls `getUnreadCount()` every 60 seconds
- `EmployeeShell`: `NotificationBell` polls `getUnreadCount()` every 60 seconds

Any test that calls `await page.waitForLoadState('networkidle')` after navigating to these portals will hang until the test timeout. Replace with a direct wait for the specific element you care about:
```js
// ❌ Hangs — AttendanceManager polls every 30s, networkidle never fires
await adminPage.waitForLoadState('networkidle');
await expect(adminPage.locator('.stat-card').first()).toBeVisible({ timeout: 5000 });

// ✅ Wait for the element directly
await expect(adminPage.locator('.stat-card').first()).toBeVisible({ timeout: 25000 });

// ❌ Hangs — ManagerShell NotificationBell polls every 60s
await page.waitForLoadState('networkidle');

// ✅ Wait for specific manager portal heading
await expect(page.locator('h2, h3').filter({ hasText: /expense queue/i })).toBeVisible({ timeout: 10000 });
```

**`waitForLoadState('domcontentloaded')` as a lightweight tab-transition wait**: When you just need a tab click to be processed (and don't want to hang on `networkidle` due to polling), use `'domcontentloaded'` as the lightest option. It does NOT guarantee data has loaded — always follow it with a specific element assertion. Useful in `ManagerShell` and `EmployeeShell` tab navigation:
```js
await page.locator('button.nav-item').filter({ hasText: /^Expense Queue$/ }).click();
await page.waitForLoadState('domcontentloaded'); // ensures click was processed
await expect(page.locator('.emp-card').first()).toBeVisible({ timeout: 10000 }); // waits for data
```

**Combined CSS + Playwright text selector is invalid**: `page.locator('.foo, text=/bar/i')` — Playwright treats the whole string as CSS and rejects the `text=` part. Use `.or()`: `page.locator('.foo').or(page.getByText(/bar/i))`.

**`.first().or()` is an invalid chain — call `.first()` AFTER `.or()`, never before**: Calling `.or()` on a locator that already has `.first()` applied causes immediate test failures (strict-mode violations or silent empty resolution). This is a subtle error because the code looks reasonable:
```js
// ❌ WRONG — .or() on a .first() locator fails
const row   = page.locator('.card').filter({ hasText: /foo/i }).first();
const empty = page.locator('.empty-state').first();
await expect(row.or(empty)).first().toBeVisible({ timeout: 8000 });

// ✅ CORRECT — .first() comes last, after the union is formed
const row   = page.locator('.card').filter({ hasText: /foo/i });
const empty = page.locator('.empty-state');
await expect(row.or(empty).first()).toBeVisible({ timeout: 8000 });
```
Never store a `.first()` result in a variable if you plan to call `.or()` on it later.

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

**Employee portal navigation — use `.nav-item` not `getByRole`**: `EmployeeShell` and `ManagerShell` render tab buttons in TWO places: the desktop sidebar (`button.nav-item`) and the mobile bottom bar (`button.emp-tab-btn`). `getByRole('button', { name: 'Attendance' })` matches both and throws a Playwright strict-mode violation. Always scope employee portal navigation to the sidebar class:
```js
// ✅ Desktop sidebar only
await page.locator('button.nav-item').filter({ hasText: /^Attendance$/ }).click();

// ❌ Matches sidebar + mobile bottom bar → strict-mode violation
await page.getByRole('button', { name: 'Attendance' }).click();
```
After a `page.reload()` the employee portal resets to the `home` tab (initial React state). If a test navigates to a tab, reloads, and then checks content in that tab — it must navigate back to the tab after reload.

**Tab buttons with icons — use `getByRole` not `hasText` regex with anchors**: Buttons that render `<Icon aria-hidden="true" /> {label}` have a raw `textContent` of `" Label"` (leading space from the JSX text node). The regex `/^Label$/i` requires the string to start with the label character, so it never matches. Use `getByRole('button', { name: label, exact: true })` instead — it computes the WAI-ARIA accessible name which excludes `aria-hidden` SVGs and normalises whitespace. Always scope to a container (e.g. `.page-body`) to avoid matching same-named sidebar nav buttons:
```js
// ✅ Accessible name — excludes aria-hidden icon, normalised text
page.locator('.page-body').getByRole('button', { name: 'Payroll Cost', exact: true }).click();

// ❌ Raw textContent has leading space — /^Payroll Cost$/i never matches
page.locator('button').filter({ hasText: /^Payroll Cost$/i }).first().click();
```
This pattern is used in `reports.spec.js` for all Reports tab buttons. The same issue applies anywhere buttons contain a Lucide icon + text without a wrapping span.

**`<option>` elements are "hidden" in Playwright**: Playwright's `toBeVisible()` returns `false` for `<option>` elements because they are not directly rendered — only the `<select>` parent is visible. To assert that a `<select>` contains specific placeholder text, check the `<select>` element itself: `page.locator('select').filter({ has: page.locator('option').filter({ hasText: /placeholder/i }) })`. Never call `.toBeVisible()` directly on an `<option>` locator.

**Filter chips with count suffix — use substring `hasText`, not anchored regex**: AssetsManager filter chips render as `"Available (2)"` (status label + live count). The regex `/^Available$/i` never matches. Use `page.locator('button.tab-btn').filter({ hasText: 'Available' })` — Playwright's string `hasText` does a substring match. Always scope to `button.tab-btn` (the chip class) to avoid matching unrelated buttons that also contain "Available" in their text.

**`AppraisalManager` Reviews tab renders a numeric badge — breaks exact-name assertions**: When appraisals are seeded, the Reviews tab button renders as `Reviews <span>N</span>`, making its accessible name "Reviews N" (e.g. "Reviews 1"). `getByRole('button', { name: 'Reviews', exact: true })` fails. Use substring `hasText` scoped to `button.tab-btn`: `page.locator('.page-body button.tab-btn').filter({ hasText: 'Reviews' })`. The same pattern applies to any tab that appends a count badge when data is seeded.

**`EmpProfile` renders form inputs only in edit mode**: `EmpProfile` hides all form inputs and the Save button behind an `{editing && ...}` conditional — the Edit button toggles `editing = true`. Tests that assert inputs or the Save button must click the "Edit" button first; otherwise all inputs and the save button are absent from the DOM.

**`modal-overlay` vs `modal-backdrop`**: Some components (AssetsManager, OffboardingModal) wrap their modals in `<div className="modal-overlay">` rather than `<div className="modal-backdrop">`. In both cases the inner modal uses `<div className="modal">` so `page.locator('.modal')` still works for asserting content. Only the backdrop selector matters when testing click-outside-to-close behaviour.

**Icon-only buttons use `title` attributes, not accessible text**: Action buttons that render only a Lucide icon (Pencil, Trash2, etc.) have no text content, so `getByRole('button', { name: /edit/i })` won't match them. Use the `title` attribute selector instead: `button[title="Edit asset"]`, `button[title="Delete asset"]`, `button[title="Probation actions"]`, `button[title="Delete employee"]`. Always check the component source for the exact `title` string.

**Submit buttons without `type="submit"` don't match `input[type="submit"]` or `button[type="submit"]`**: Many submit buttons use `onClick={handler}` with no explicit `type` attribute (defaulting to `"button"`, not `"submit"`). The CSS selector `button[type="submit"]` requires the attribute to be **explicitly present** in the HTML — it does NOT match buttons that merely default to the submit type. Target these by text content: `page.locator('button').filter({ hasText: 'Submit Claim' })`.

**Inputs without explicit `type="text"` don't match `input[type="text"]`**: Same rule as above — CSS attribute selectors require the attribute to be explicitly set. A bare `<input className="form-control" value={...} />` (no type prop) renders as a text input in browsers but is NOT matched by `input[type="text"]` in Playwright selectors. Target by placeholder instead: `page.locator('input[placeholder*="Fire Safety"]')` or `input:not([type="date"]):not([type="number"])`.

**Multiple Cancel buttons in layered modal content — use `.first()` for the innermost one**: When a modal has an inline confirmation form (e.g. contract action, payroll rejection), two Cancel buttons exist simultaneously: `[0]` = the inline form's Cancel (inside `modal-body`), `[1]` = the modal footer's Cancel (closes the entire modal). Always use `.first()` to dismiss only the inline form. Clicking `.nth(1)` closes the whole modal, which then causes subsequent assertions on modal content to fail with "element(s) not found".

**Data-conditional tables — always skip-guard before asserting `th`**: `PayrollList`, `LeaveManager` requests, and the WPS column only render a `<table>` when rows exist — the empty state is a `<div className="empty-state">` with no `<th>` at all. Never write `expect(page.locator('th').filter(...)).toBeVisible()` without first checking the table exists:
```js
const table = page.locator('.card')
  .filter({ has: page.locator('h3').filter({ hasText: /Payroll History/i }) })
  .locator('table').first();
if (!(await table.isVisible({ timeout: 8000 }).catch(() => false))) {
  test.skip(true, 'No runs yet');
  return;
}
await expect(table.locator('th').filter({ hasText: /Period/i }).first()).toBeVisible();
```
Scope the `th` locator **to the table**, not `page` — scoping avoids matching header rows from other visible tables.

**`input[type="file"]` is always `display:none`** — file upload inputs are hidden and triggered via a visible click-area div. `expect(page.locator('input[type="file"]')).toBeVisible()` always fails. Check the visible drop-zone text instead: `page.locator('.modal').getByText(/Click to choose file/i)`.

**`bankName` is a free-text input, not a `<select>`** — `EmployeeModal` Salary tab renders Bank Name as `<input placeholder="e.g. ENBD, FAB, ADCB">`. There is no bank `<select>` with options. Target with `input[placeholder*="ENBD"]`.

**Offboarding tasks use Lucide SVG icons, not `<input type="checkbox">`** — `OffboardingModal` renders each task as a `<div onClick>` row containing a `<CheckSquare>` or `<Square>` Lucide icon. There are no checkbox inputs. Check for `button[title="Remove task"]` (present on each task row) or the `"No tasks yet."` empty-state text inside the Clearance Checklist card.

**Notification panel header also has `borderBottom` — don't use `[style*="border-bottom"]` for rows**: The panel header div has `borderBottom: '1px solid var(--gray-100)'` in its inline style; so does every notification row. The selector `[style*="border-bottom"]` matches the header too and causes a strict-mode violation with `.or()`. Identify notification rows by their emoji prefix instead:
```js
const emptyState = page.locator('text=No notifications yet').first();
const notifItem  = page.locator('div').filter({ hasText: /📄|⚠️|🏥|🔄|✅|❌|📝|💰|🔔/ }).first();
await expect(emptyState.or(notifItem)).toBeVisible({ timeout: 8000 });
```

**CompanySettings h2 is "Company / Employer Settings"** — the slash makes `/company settings/i` fail as a substring match. Use `/employer settings/i` or `/company.*employer/i`.

**Leave module structural notes for tests**:
- "Approval Chain" is a `<label>` inside a form group, NOT an `<h3>`. The `<h3>` in the Settings tab is "Leave Configuration".
- "Leave Types" has no `<h3>` in the Settings tab — it is only a stat card (`<div className="stat-label">Leave Types</div>`) on the Overview tab.
- `getLeaveApprovalDelegates()` may return HTTP 500 if the `leave_approval_delegates` table hasn't been created yet. Filter `"Failed to load resource"` / `"500"` from console-error assertions in Leave module tests.

**EmployeeShell sidebar shows name + job title, NOT email** — the sidebar footer renders `emp.name` (bold) and `emp.jobTitle` (or "Employee"). There is no email address displayed. Do not check for `text=@` in the employee sidebar. Check for the always-present Sign Out button: `page.locator('.emp-sidebar').getByRole('button', { name: /sign out/i })`.

**`getMyCompany()` must not use bare `.maybeSingle()` when multiple branches exist** — `profileStorage.getMyCompany()` queries `companies` filtered by `user_id`. Since Feature 21 allows multiple company rows per admin (branches), a bare `.maybeSingle()` throws `PGRST116` ("multiple rows returned"). The function already applies `.order('created_at', { ascending: true }).limit(1)` before `.maybeSingle()`. Any future utility that fetches a single company by `user_id` must do the same.

## Environment

Create `sif-app/.env` with:
```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

## SQL Migrations

New DB schema changes live in `sql/` as numbered files (`001_emiratization.sql`, `002_document_storage.sql`, …). Run each file manually in **Supabase Dashboard → SQL Editor → New Query**. There is no automated migration runner — files are applied in order by number. Each file is idempotent (`IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).

Clinic-specific migrations to run in order (if not already applied):
- `sql/024_employee_self_upload.sql` — adds `document_number`, `status`, `rejection_reason`, `submitted_by` columns to `employee_documents`; creates `employee_submit_document` SECURITY DEFINER RPC; adds Storage INSERT/SELECT policies for employee uploads.
- `sql/025_letter_requests.sql` — creates `letter_requests` table + RLS + `employee_request_letter` RPC.
- `sql/026_clinical_duty_rota.sql` — adds `code` + `shift_category` to `shifts`; adds `planned_hours`, `actual_hours`, `co_hours` to `roster_assignments`; back-fills `planned_hours` from linked shift templates.
- `sql/027_biometric_integration.sql` — creates `biometric_mappings` table + RLS + `biometric_mappings_admin` policy.
- `sql/028_probation_leave_rules.sql` — adds `probation_eligible BOOLEAN DEFAULT true` and `requires_attachment BOOLEAN DEFAULT false` to `leave_types`; seeds `ANNUAL`, `HAJJ`, `STUDY` as `probation_eligible = false`.
- `sql/029_department_hierarchy.sql` — creates `departments` table (self-referencing `parent_id`, `head_employee_id`, `color`, `description`, `sort_order`) + RLS + `UNIQUE (user_id, name)` constraint.
- `sql/030_expense_manager_approval.sql` — adds `manager_approved_at`, `manager_approved_by`, `manager_rejection_reason` to `expense_claims`; creates three SECURITY DEFINER RPCs: `manager_get_expense_queue()`, `manager_approve_expense(UUID)`, `manager_reject_expense(UUID, TEXT)`.
- `sql/031_appraisal_module.sql` — creates `appraisal_cycles`, `appraisals`, `appraisal_sections` tables + RLS + admin policies. Employee self-read policy on `appraisals` and `appraisal_sections`.
- `sql/032_roster_compliance.sql` — pre-cursor to staffing rules; superseded by 033 for the staffing rules table.
- `sql/033_clinical_gaps.sql` — adds `licence_authority`, `licence_number`, `licence_expiry` to `employees`; creates `compliance_overrides` table + admin RLS; creates `department_staffing_rules` table + admin RLS; adds four manager-portal RLS policies on `appraisals`, `appraisal_sections`, `appraisal_cycles` for direct-reports access via `reporting_manager_id` chain.
- `sql/034_manager_role.sql` — **required for ManagerShell to work**: drops and recreates `user_profiles_role_check` to include `'manager'`; updates `admin_set_employee_portal_role` RPC to accept `'manager'`; grants `user_profiles` to `service_role` (required for E2E test manager session setup). Without this migration, `role='manager'` inserts fail silently and `ManagerShell` never renders.
- `sql/035_manager_employee_read.sql` — adds `employees_manager_read` SELECT policy so managers can read their direct reports' employee records (required for `ManagerAppraisals` name resolution and any future manager feature that needs employee details). Uses a `SECURITY DEFINER` helper `get_manager_employee_id()` to avoid infinite RLS recursion — **never** write a plain self-referencing subquery on `employees` inside an `employees` RLS policy; it causes `"infinite recursion detected in policy for relation employees"` for every query on that table.

**Legacy pending migration**: `sql/021_multi_company.sql` adds `branch_name` to `companies`, `company_id FK` to `employees`/`payroll_runs`, and drops the unique constraint on `companies.user_id`. If employees show `company_id = NULL` in the multi-company tests, this migration has not been applied yet.

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

**Workloop** is a UAE HR/payroll SaaS. It generates **SIF files** (Salary Information File — UAE WPS/MOL bank format) and manages employees, payroll, leave, and attendance. There are three completely separate UIs sharing one Supabase project.

See `FEATURES_ROADMAP.md` for the original 22-feature plan. **All original planned features are complete**: 1–14, 16, 17, 19, 21 (Emiratization, Document Storage, Insurance, Notifications, Advances, Multi-Level Leave, Leave Calendar, Shift Roster, WPS Tracking, Reports, Probation, Contract Renewal, Offboarding, Expense Claims, Asset Management, Payroll Approval, Training & Certifications, Multi-Company / Branch Support). Features 15, 18, 20, 22 were skipped.

This fork is being extended into a **UAE clinic/hospital HRMS**. Clinic-specific features are implemented sequentially and tracked in `Workloop_Clinic_HRMS_Feature_List.pdf`:
- **1.1 Clinical Credentials** (done) — `DOC_GROUPS` / `CLINICAL_DOC_TYPES` in `EmployeeModal.jsx`; clinical docs expire amber at 90d vs 60d; `clinical_credential_expiry` notifications at 90/30/14d.
- **1.2 Employee Self-Upload** (done) — `employee_submit_document` RPC; `document_number`, `status`, `rejection_reason`, `submitted_by` columns on `employee_documents`; admin verify/reject workflow; `EmpDocuments.jsx` portal tab.
- **1.3 Letter & Certificate Requests** (done) — `letter_requests` table; `employee_request_letter` RPC; `LetterRequestsManager.jsx` admin page (nav item `'letters'`); `EmpRequests.jsx` portal tab; 7 HTML letter templates in `letterTemplates.js`.
- **2.1 Clinical Duty Rota** (done) — `code` + `shift_category` on `shifts`; `planned_hours`/`actual_hours`/`co_hours` on `roster_assignments`; compact code-badge grid cells; per-employee totals column; Morning/Afternoon/Night/Unassigned footer rows; CSV export in Dubai Medical University Hospital format; mid-month joiner greying.
- **2.2 Biometric / Punching Machine Integration** (done) — `biometric_mappings` table (`sql/027`); `biometricStorage.js` with `getBiometricMappings`, `saveBiometricMapping`, `deleteBiometricMapping`, `parseBiometricCsv`, `importBiometricPunches`; `BiometricImport.jsx` tab in `AttendanceManager` (Biometric Import tab). CSV parser auto-detects ZKTeco Report, ZKTeco Simple, and Generic formats. Deduplication at minute-level: `${employee_id}_${event_type}_${eventTime[0:16]}` prevents re-importing the same punch.
- **2.3 Probation-Aware Leave Rules** (done) — `probation_eligible BOOLEAN DEFAULT true` column on `leave_types` (`sql/028`); `saveLeaveType()` in `leaveStorage.js` to toggle the flag; `validateLeaveRequest` blocks probation employees from ineligible leave types; `LeaveManager` Settings tab has "Probation Leave Eligibility" card with per-type toggle; `EmpLeave` shows amber banner listing restricted types and filters `availableTypes` for the dropdown.
- **2.4 Leave Document Attachments** (done) — `requires_attachment BOOLEAN DEFAULT false` on `leave_types` (same `sql/028`); `uploadLeaveAttachment(adminUserId, employeeId, file)` in `leaveStorage.js` reuses the existing `employee-documents` Storage bucket under `leave/` subfolder (7-day signed URLs); `validateLeaveRequest` blocks submission if `requiresAttachment && !attachmentUrl`; `ATTACHMENT_HINTS` constant in `leaveEngine.js` maps leave type codes to document descriptions; `EmpLeave` shows file upload UI (with hint text) when the selected type requires an attachment; admin sees `📎` link in the Requests table.
- **3.1 Department Hierarchy & Org Tree** (done) — `departments` table (`sql/029`) with self-referencing `parent_id`; `departmentStorage.js` (`getDepartments`, `saveDepartment`, `deleteDepartment`); `DepartmentManager.jsx` (nav item `'departments'`, **GitBranch icon, between Employees and Letter Requests** in `NAV_ITEMS`) — three tabs: Departments (indented tree table with `└` prefix, inline add/edit, color swatches, delete flash-guard) + Org Chart (recursive `OrgNode` component with expand/collapse, recursive search, dept filter) + Staffing Rules (min-staff rules per dept × shift category). `EmployeeModal` Job tab department input uses `<datalist>` autocomplete from `getDepartments()` — free-text still works for informal department names.
- **3.2 Multi-Level Expense Approvals** (done) — adds `manager_approved_at`, `manager_approved_by`, `manager_rejection_reason` columns to `expense_claims` (`sql/030`); three SECURITY DEFINER RPCs: `manager_get_expense_queue`, `manager_approve_expense`, `manager_reject_expense`; new `getExpenseQueueForManager`, `managerApproveExpense`, `managerRejectExpense` in `expenseStorage.js`; `ManagerExpenseQueue.jsx` added to `ManagerShell` as "Expense Queue" tab; `ExpensesManager` updated with `manager_approved`/`manager_rejected` status badges and filter tab. Status flow: `pending` → `manager_approved` (manager pre-approves) → `approved` (HR final) → `paid`; or `manager_rejected` at any pre-paid point.
- **4.1 Clinical HR Dashboard** (done) — `ClinicalDashboard.jsx` (nav item `'clinical-dashboard'`, Activity icon, second position after Dashboard); **11 clickable KPI cards** with drill-down expansion panels: Active Staff / Credential Compliance / Licences Expiring ≤90d / Expired Credentials / Today's Roster Coverage / On Probation / New Joiners This Month / Birthdays This Month / On Leave Today / Pending Leave Requests / Staff On Duty Now. Department Headcount table with per-dept compliance % and coverage progress bar. Uses `CLINICAL_DOC_TYPES` (imported from `EmployeeModal.jsx`) to filter clinical documents. Data sources: `getEmployees`, `getAllEmployeeDocuments`, `getRosterForMonth`, `getDepartments`, `getLeaveRequests({ status: 'Approved' })`, `getAttendanceRecords({ dateFrom, dateTo })` (today only).
- **5.1 Salary Distribution Compliance** (done) — MoHRE salary distribution thresholds corrected in `EmployeeModal.jsx` Salary tab: Basic ≥60% (was ≥50%) = compliant green; 50–60% = warn amber; <50% = error red. Housing ≤25% (was ≤30%). Transport ≤10% (was ≤15%).
- **6.1 Appraisal Module** (done) — `sql/031_appraisal_module.sql` creates `appraisal_cycles`, `appraisals`, `appraisal_sections` tables. `appraisalStorage.js` exports: `getAppraisalCycles`, `saveAppraisalCycle`, `deleteAppraisalCycle`, `getAppraisalsForCycle`, `getMyAppraisals`, `getMyTeamAppraisals` (manager RLS), `createAppraisalsForCycle`, `saveAppraisalReview`, `calibrateAppraisal`, `managerRateSection`. `AppraisalManager.jsx` (nav item `'appraisals'`, ClipboardList icon, between Training and Roster) — admin creates cycles, assigns staff, reviews ratings, calibrates scores. `EmpAppraisal.jsx` (employee portal "Appraisals" tab, 9th of 12 — between Training and Documents) — read-only expandable rows with star display. `ManagerAppraisals.jsx` (ManagerShell "Appraisals" tab, 3rd after Expense Queue) — interactive `StarRating` per section, locked when `status === 'calibrated'`. Manager access via `appraisals_manager_read` / `appraisal_sections_manager_update` RLS policies (migration 033). Dashboard shows blue alert for pending appraisals in active cycles. **Critical workflow**: just setting `reporting_manager_id` on an employee is not enough — the admin must also go to Appraisals → open cycle → Reviews tab → Assign Staff to create appraisal rows for those employees; only then will the manager see them. **Self-appraisal exclusion**: `getMyTeamAppraisals()` calls `supabase.rpc('get_manager_employee_id')` and filters `neq('employee_id', selfId)` to prevent the manager's own appraisal (visible via employee self-read policy) from leaking into the Team Appraisals view. **Section name field**: `dbToSection()` converts `section_name` → `sectionName` (camelCase); components must read `s.sectionName`, never `s.section_name`.
- **7.1 Professional Licence Tracking** (done) — `sql/033_clinical_gaps.sql` adds `licence_authority TEXT NOT NULL DEFAULT 'None'`, `licence_number TEXT`, `licence_expiry DATE` to `employees`; `storage.js` maps these to `licenceAuthority`/`licenceNumber`/`licenceExpiry` in `dbToEmployee`/`employeeToDb`. `EmployeeModal.jsx` UAE Compliance tab has "Professional Licence" section: authority `<select>` (None/DHA/DOH/MOH/HAAD/DHCC/Other), Licence Number input (disabled when None), Expiry date with inline valid/expiring/expired badge. **Hard block on SIF download** in `PayrollEditor.jsx`: `handleDownload()` checks all three compliance dimensions — expired professional licence (`licenceAuthority !== 'None' && licenceExpiry < today`), expired Emirates ID (`emiratesIdExpiry < today`), and expired Visa (`visaExpiry < today`) — collects all into a `violations` array `[{ emp, type, expiry }]`, then shows the `licenceGate` modal (heading "Expired Compliance Documents") listing each violation with override reason textarea (≥10 chars required); on override, calls `saveComplianceOverride({ overrideType: 'payroll_sif', employeeIds, reason })`. `compliance_overrides` table (migration 033) stores all override audit records. `notificationStorage.js` fires `clinical_licence_expiry` notifications at 60d/30d/14d using `${emp.id}_licence_${thr}d` deduplication key.
- **7.2 Minimum Staffing Rules** (done) — `sql/033_clinical_gaps.sql` creates `department_staffing_rules` table with `UNIQUE (user_id, department, shift_category)`. `staffingStorage.js` exports `getDeptStaffingRules`, `saveDeptStaffingRule`, `deleteDeptStaffingRule`. `DepartmentManager.jsx` gains a 3rd "Staffing Rules" tab (ShieldCheck icon) with inline add/edit form (department datalist, shift category select, min staff number) and delete buttons. **Hard block on roster publish** in `RosterManager.jsx`: `handlePublish()` loads staffing rules, computes per-day department × shift_category headcounts from `rosterData`, finds violations (count < minStaff), shows `publishGate` modal listing violations table with override reason textarea (≥10 chars required); `doPublish(overrideReason)` calls `saveComplianceOverride({ overrideType: 'roster_publish' })` before publishing. `CATEGORY_LABELS` constant added in `RosterManager.jsx`. **Staffing Compliance tab** added to `Reports.jsx` (8th tab, ShieldCheck icon): month picker fetches roster via `getRosterForMonth`, renders per-rule heatmap of 28×28px green/red day cells showing actual staff count.

### Three-portal structure

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
| `utils/storage.js` | Admin CRUD: companies, employees, payroll runs/entries, payslip records, employee documents, Nafis reports, insurance policies/assignments/dependants, salary advances/repayments, employee contracts (`getEmployeeContracts`, `saveEmployeeContract`), offboarding checklists/tasks (`getOffboardingChecklist`, `createOffboardingChecklist`, `getOffboardingTasks`, `updateOffboardingTask`, `addOffboardingTask`, `deleteOffboardingTask`, `saveOffboardingVisaStatus`, `completeOffboardingChecklist`), payroll approval (`submitPayrollForApproval`, `approvePayroll`, `rejectPayroll`, `recallPayrollApproval`, `getPayrollApprovalLog`) |
| `utils/expenseStorage.js` | Expense claims (Feature 14): `getExpenseClaims`, `getApprovedUnpaidExpenses`, `approveExpenseClaim`, `rejectExpenseClaim`, `markExpensesPaid`, `deleteExpenseClaim`, `uploadExpenseReceipt`, `getExpenseReceiptUrl` |
| `utils/assetStorage.js` | Asset management (Feature 16): `getAssets`, `saveAsset`, `deleteAsset`, `getAssetAssignments`, `assignAsset`, `returnAsset`, `getEmployeeCurrentAssets` |
| `utils/trainingStorage.js` | Training & certifications (Feature 19): `getTrainingRecords`, `saveTrainingRecord`, `deleteTrainingRecord`, `getEmployeeTrainingRecords`, `getCertifications`, `getAllCertifications`, `saveCertification`, `deleteCertification`, `getEmployeeCertifications` |
| `utils/notificationStorage.js` | In-app notifications: `getNotifications`, `getUnreadCount`, `markNotificationRead`, `markAllNotificationsRead`, `createNotification`, `createNotifications` (batch), `generateExpiryNotifications` |
| `utils/profileStorage.js` | Role resolution (`user_profiles`), employee self-service data (own record, own payslips, own company); `getEmployeePortalRole(employeeId)`, `setEmployeePortalRole(employeeId, role)` |
| `utils/leaveStorage.js` | Leave types, requests, balances, public holidays, delegates; `getLeaveQueueForManager`, `approveLeaveAsManager`, `rejectLeaveAsManager`, `getLeaveApprovalDelegates`, `saveLeaveApprovalDelegate`, `deleteLeaveApprovalDelegate` |
| `utils/attendanceStorage.js` | Attendance records, clock events, shifts, regularisation; Feature 8 roster: `getRosterForMonth`, `saveRosterAssignment`, `deleteRosterAssignment`, `publishRoster`, `getShiftSwapRequests`, `updateShiftSwapRequest`; employee self-service: `getMyRoster`, `getMyColleagues`, `requestShiftSwap` |
| `utils/letterStorage.js` | Letter request CRUD: `getLetterRequests`, `getPendingLetterCount`, `completeLetterRequest`, `rejectLetterRequest`, `getMyLetterRequests` (employee self-read) |
| `utils/letterTemplates.js` | HTML letter templates for 7 types (Salary Certificate — Bank/Embassy/Personal, NOC, Experience Letter, Employment Certificate, Salary Transfer Letter). `generateLetterHTML(req, company)` + `printLetter(req, company)` (window.open + document.write + print). `LETTER_TYPES` array is exported and used in both admin and employee portal components to keep the list in sync. |
| `utils/departmentStorage.js` | Department hierarchy CRUD (Feature 3.1): `getDepartments`, `saveDepartment`, `deleteDepartment`. All RLS-scoped to `user_id`. `dbToDept` maps to `{id, name, parentId, headEmployeeId, color, description, sortOrder}`. |
| `utils/biometricStorage.js` | Biometric device integration (Feature 2.2): `getBiometricMappings`, `saveBiometricMapping`, `deleteBiometricMapping`, `parseBiometricCsv` (auto-detects ZKTeco/Generic CSV formats), `importBiometricPunches` (deduplicates at minute-level and calls `employee_record_clock_event` RPC for each new punch). |
| `utils/appraisalStorage.js` | Appraisal module (Clinic 6.1): `getAppraisalCycles`, `saveAppraisalCycle`, `deleteAppraisalCycle`, `getAppraisalsForCycle`, `getMyAppraisals` (employee self-read), `getMyTeamAppraisals` (manager RLS — direct reports only), `createAppraisalsForCycle` (seeds default sections), `saveAppraisalReview` (updates sections + computes weighted overall rating), `calibrateAppraisal`, `managerRateSection`. Imports from `'../lib/supabase'` (shared client). `RATING_LABELS` and `DEFAULT_SECTIONS` exported. |
| `utils/staffingStorage.js` | Minimum staffing rules (Clinic 7.2): `getDeptStaffingRules`, `saveDeptStaffingRule` (upserts on `user_id,department,shift_category`), `deleteDeptStaffingRule`. `dbToRule` maps to `{id, department, shiftCategory, minStaff, effectiveFrom, effectiveTo}`. Imports from `'../lib/supabase'`. |

**Shape converters**: `storage.js` has `dbToXxx` / `xxxToDb` functions that translate between snake_case DB columns and camelCase JS objects. All components consume camelCase objects. `dbToDocument`, `dbToInsurancePolicy`, `dbToEmployeeInsurance`, `dbToInsuranceDependant`, `dbToAdvance`, and `dbToAdvanceRepayment` are all module-private converters (not exported). `dbToLeaveRequest` in `leaveStorage.js` now also maps Feature 6 fields: `managerApprovedAt`, `managerApprovedBy`, `managerRejectionReason`, `substituteEmployeeId`, `approvalLevelRequired`, `approvalComment`.

**`authUserId` in dbToEmployee**: `dbToEmployee` now maps `row.auth_user_id → emp.authUserId`. This field is `null` until the employee registers on the employee portal. It is used by `LeaveManager` and `PayrollEditor` to target notifications at the correct employee auth account.

**Column repurpose**: `payroll_entries.du_cost` stores `leaveDeduction` (per-employee leave deduction in a payroll run) — there was no schema migration; this column was repurposed in-place.

### Supabase schema (key tables)

- `companies` — one row per admin user (`user_id = auth.uid()`). New columns: `sector TEXT`, `nafis_quota_percent DECIMAL(5,2)` (Emiratization tracking).
- `employees` — all employees for a company; `auth_user_id` set when employee links their account; `user_id` = the admin's UUID; `work_email` is always stored lowercase. Several columns are NOT NULL (including `mol_id`, `emp_no`, `name`, `bank_name`, `bank_routing_code`, `iban`) — always pass `''` as default, never omit them in raw inserts. New columns: `nafis_registration_no TEXT` (UAE nationals only); `probation_extended BOOLEAN DEFAULT false` (set to true when admin extends the probation period); `licence_authority TEXT NOT NULL DEFAULT 'None'` (values: None/DHA/DOH/MOH/HAAD/DHCC/Other); `licence_number TEXT NOT NULL DEFAULT ''`; `licence_expiry DATE` (nullable). Migration: `sql/033_clinical_gaps.sql`.
- `user_profiles` — `role` ('admin'|'employee'|'manager'), `company_user_id`, `employee_id`; RLS restricts each user to their own row. Admins can change an employee's role to 'manager' via `admin_set_employee_portal_role` RPC (requires the employee to have activated their portal first)
- `payroll_runs` + `payroll_entries` — payroll run header + one row per employee. Feature 17 added approval columns: `approval_status` (`'draft'`|`'pending_approval'`|`'approved'`), `submitted_for_approval_at`, `submitted_by`, `approved_by`, `approved_at`, `rejection_reason`, `rejected_at`. After final generation `payroll_runs.status` becomes `'generated'` (irreversible; separate from `approval_status`).
- `payslips` — snapshot of each employee's pay per period; created when admin downloads SIF (`createPayslipRecords`)
- `leave_types`, `leave_requests`, `leave_balances`, `public_holidays`
- `clock_events` — raw clock-in/out events; `user_id` = admin's UUID (even for self-service entries via RPC); `event_type` stored as uppercase `CLOCK_IN` / `CLOCK_OUT`
- `attendance_records` — derived daily record; columns: `clock_in_time`, `clock_out_time`, `total_hours` (not `clock_in`, `clock_out`, `hours_worked`); `status` must be uppercase (e.g. `'PRESENT'`) — the JS constants in `attendanceEngine.js` (`ATTENDANCE_STATUS.PRESENT = 'PRESENT'`) are all uppercase and the DB values must match exactly
- `attendance_periods` — one row per `(user_id, period YYYY-MM)`; closed by admin before payroll run
- `employee_job_history` — audit log of salary/title/department/status changes; written on every employee save
- `nafis_reports` — one snapshot per `(user_id, period YYYY-MM)`; upserted by `saveNafisReport()`. Stores headcount, Emirati count, ratio, compliance flag, and a JSON snapshot of UAE national employees at time of generation.
- `employee_documents` — one row per uploaded file per employee. Key columns: `document_type`, `document_number`, `file_name`, `file_size`, `storage_path` (path within the `employee-documents` Supabase Storage bucket), `expiry_date`, `notes`, `status` (`'pending'`|`'verified'`|`'rejected'`), `rejection_reason`, `submitted_by` (`'admin'`|`'employee'`). The `storage_path` is used to generate signed URLs and to delete from Storage on record delete. Admin can verify (`verifyEmployeeDocument(id)`) or reject (`rejectEmployeeDocument(id, reason)`) employee-submitted documents; status badge shown in the Documents tab. `getAllEmployeeDocuments()` fetches without signed URLs (for Reports module use). Clinical credential types (DHA Licence, DOH/MOH Licence, BLS/ACLS/PALS/NRP/CME Certificate) are defined in `CLINICAL_DOC_TYPES` Set (exported from `EmployeeModal.jsx`) — these show a cyan "Clinical" badge and use a 90-day expiry warning threshold instead of 60 days.
- `insurance_policies` — company-level insurance plan records (insurer name, policy number, tier, annual premium, renewal date, broker). One admin can have multiple policies.
- `employee_insurance` — one coverage record per employee (`UNIQUE (user_id, employee_id)`); links to a policy, stores member ID, card number, effective/expiry dates. Upserted via `saveEmployeeInsurance()` using `onConflict: 'user_id,employee_id'`.
- `insurance_dependants` — family members covered under an employee's policy (name, relationship, DOB, card number). No uniqueness constraint — multiple rows per employee allowed.
- `notifications` — in-app notifications with `UNIQUE (recipient_user_id, type, related_entity_id)` for deduplication. `user_id` = who created it (admin), `recipient_user_id` = who sees it (admin or employee). Four separate RLS policies: SELECT/INSERT/UPDATE/DELETE with different conditions (see `sql/004_notifications.sql`). Expiry alerts embed a threshold suffix in `related_entity_id` (e.g. `{employeeId}_visa_30d`) so 60-day and 30-day alerts are separate rows.
- `salary_advances` — one row per advance/loan disbursement. `status` is `'pending'` (employee self-request awaiting approval) | `'active'` (approved, repayments ongoing) | `'settled'` (fully repaid) | `'cancelled'` (rejected or voided). Admin-created advances start as `'active'`; employee-requested advances start as `'pending'` via the `employee_request_advance` RPC. Stores `repayment_months`, `monthly_deduction` (= amount ÷ months), and `outstanding_balance` (decremented on each repayment).
- `advance_repayments` — one row per monthly deduction; linked to `salary_advances` (CASCADE delete) and optionally to `payroll_runs`. Written by `saveAdvanceRepayment()` which also calls `updateAdvanceBalance()` to decrement the parent advance and auto-transition to `'settled'` when balance hits zero.
- `leave_requests` — extended with Feature 6 columns: `manager_approved_at`, `manager_approved_by TEXT`, `manager_rejection_reason TEXT`, `substitute_employee_id UUID`, `approval_level_required INT DEFAULT 1`, `approval_comment TEXT`. Status values now include `'ManagerApproved'` (manager pre-approved, awaiting HR final sign-off) and `'ManagerRejected'` (manager rejected — final). No CHECK constraint on status — the column is free TEXT.
- `leave_approval_delegates` — admin configures a deputy approver when a manager is on leave. `approver_employee_id` = the absent manager, `delegate_employee_id` = the colleague covering them, `from_date`/`to_date` = coverage window. Both manager and delegate can read their own rows via `leave_approval_delegates_actor_read` policy.
- `roster_assignments` — one shift per employee per calendar day (`UNIQUE (employee_id, date)`). `published BOOLEAN` controls whether the employee portal can see the row. Clinical rota columns added in migration 026: `planned_hours DECIMAL(4,2)` (auto-filled from the linked shift's `expected_hours` on save), `actual_hours DECIMAL(4,2)`, `co_hours DECIMAL(4,2) DEFAULT 0`. Admin has full access via `user_id = auth.uid()`; employees read only their own `published = true` rows via `roster_assignments_employee_read`. `shift_id` FK → `shifts` (gained `color TEXT` in migration 007, `code TEXT` and `shift_category TEXT DEFAULT 'morning'` in migration 026).
- `shift_swap_requests` — employee-initiated swap between two employees for a specific date. `status` CHECK `('pending'|'approved'|'rejected'|'cancelled')`. Both the `requester_employee_id` and `target_employee_id` can SELECT their own rows via `shift_swap_requests_employee_read` policy. Admin has full access.
- `employee_contracts` — contract lifecycle history (Feature 12). One **insert-only** row per action; never updated. `action` values: `'new'` | `'renewed'` | `'converted'` | `'not_renewed'`. `UNIQUE` constraint: none — multiple rows per employee expected. Stores `contract_type`, `start_date`, `end_date`, `renewed_by` (admin email), `notes`.
- `offboarding_checklists` — one row per terminated employee offboarding (Feature 13). `UNIQUE (user_id, employee_id)` prevents duplicates. Stores `status` (`'in_progress'`|`'completed'`), `visa_cancellation_status` (`'not_started'`|`'initiated'`|`'submitted_gdrfa'`|`'cancelled'`), `visa_cancellation_date`, `completed_at`.
- `offboarding_tasks` — individual clearance items for a checklist (CASCADE delete with checklist). Columns: `task_name`, `completed BOOLEAN`, `completed_at`, `completed_by`, `notes`, `sort_order`. Seeded from `offboarding_task_templates` on checklist creation, or from 9 hardcoded defaults if no templates exist.
- `offboarding_task_templates` — admin-configurable reusable default task list. If rows exist for the admin's `user_id`, they override the hardcoded defaults when `createOffboardingChecklist()` seeds a new checklist.
- `letter_requests` — employee HR letter requests (clinic Feature 1.3). Columns: `user_id` (admin), `employee_id`, `letter_type`, `purpose`, `status` (`'pending'`|`'completed'`|`'rejected'`), `notes`, `rejection_reason`, `requested_at`, `completed_at`. Admin full-access policy; employee self-read policy. Inserted via `employee_request_letter` RPC (SECURITY DEFINER). Admin action: `completeLetterRequest(id)` prints + marks done; `rejectLetterRequest(id, reason)` rejects. Dashboard shows amber alert badge when `pendingLetters > 0` (loaded via `getPendingLetterCount()`). Nav item `'letters'` (between Employees and Payroll in `App.jsx`).
- `expense_claims` — employee expense reimbursements (Feature 14).
- `assets` — company asset registry (Feature 16). `status`: `'available'` | `'assigned'` | `'under_repair'` | `'retired'` | `'lost'`. `category`: laptop | phone | tablet | vehicle | furniture | equipment | other. Admin full CRUD; employees read assets assigned to them via `asset_assignments` sub-select. Status is automatically managed by `assignAsset()` (→ `'assigned'`) and `returnAsset()` (→ `'available'`) — never set manually to `'assigned'` from the Edit modal. `ASSET_CATEGORIES` constant exported from `AssetsManager.jsx`.
- `asset_assignments` — assignment history (Feature 16). Append-only: one INSERT per assignment, `return_date IS NULL` means currently held. `condition_at_handover` / `condition_at_return`: `'new'` | `'good'` | `'fair'` | `'poor'`. `deleteAsset()` guards against deleting assets with an open assignment. Employee self-read policy: `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())`.
- `payroll_approval_log` — audit trail for Feature 17. One row per approval action (`'submitted'` | `'approved'` | `'rejected'` | `'recalled'`). Columns: `payroll_run_id`, `action`, `performed_by` (email), `notes`, `created_at`. Written by the four approval functions in `storage.js`; never updated or deleted. Admin-only RLS (`user_id = auth.uid()`).
- `training_records` — training/course history per employee (Feature 19). `training_type`: `'internal'` | `'external'` | `'online'` | `'conference'`. `status`: `'planned'` | `'in_progress'` | `'completed'` | `'cancelled'`. Optional fields: `score`, `passed BOOLEAN`, `certificate_url`, `duration_hours`, `cost`. Admin full CRUD; employee self-read policy. `TRAINING_TYPES` and `TRAINING_STATUSES` constants exported from `TrainingManager.jsx`.
- `certifications` — professional certification registry per employee (Feature 19). Key fields: `certification_name`, `issuing_body`, `certificate_no`, `issued_date`, `expiry_date` (NULL = no expiry / lifetime cert), `certificate_url`. Admin full CRUD; employee self-read policy. Expiry status (`expired` / `expiring_30d` / `expiring_60d` / `active` / `no_expiry`) is computed dynamically by `certExpiryInfo()` in `TrainingManager.jsx` — not stored in DB. Dashboard loads all certs via `getAllCertifications()` for the 60-day cert expiry alert. `generateExpiryNotifications` now accepts a 5th param `allCertifications = []` and fires `cert_expiry` notifications at 14d / 30d / 60d thresholds.
- `appraisal_cycles` — one cycle per review period per admin. Columns: `name`, `review_from`, `review_to`, `status` (`'draft'`|`'open'`|`'active'`|`'closed'`). Admin RLS only. Manager can SELECT active cycles via `appraisal_cycles_manager_read` policy (migration 033).
- `appraisals` — one row per employee per cycle. `status`: `'pending'` | `'self_reviewed'` | `'reviewed'` | `'calibrated'`. Stores `overall_rating` (weighted average computed by `saveAppraisalReview`), `self_rating`, `reviewer_comments`, `development_plan`, `reviewed_by`, `reviewed_at`. Admin RLS + `appraisals_manager_read` policy for direct reports (via `employees.reporting_manager_id`).
- `appraisal_sections` — per-section ratings for each appraisal. Columns: `section_name`, `weight DECIMAL`, `rating INT`, `self_rating INT`, `comments`, `sort_order`. Seeded from `DEFAULT_SECTIONS` on appraisal creation. Admin RLS + `appraisal_sections_manager_update` policy allows manager to update `rating`/`comments` on their direct reports' sections.
- `compliance_overrides` — audit log of HR overrides (Clinic 7.1/7.2). Columns: `user_id`, `override_type` (`'payroll_sif'`|`'roster_publish'`), `employee_ids UUID[]`, `reason TEXT`, `created_at`. Admin-only RLS. Written by `saveComplianceOverride()` in `storage.js` when HR downloads SIF with expired staff licences or publishes roster below minimum staffing.
- `department_staffing_rules` — minimum headcount rules per department × shift category (Clinic 7.2). Columns: `user_id`, `department TEXT`, `shift_category TEXT` (`'morning'`|`'afternoon'`|`'night'`|`'flexible'`), `min_staff INT DEFAULT 1`, `effective_from DATE`, `effective_to DATE`. `UNIQUE (user_id, department, shift_category)`. Admin-only RLS.

### Supabase Storage

One private bucket: **`employee-documents`**. Files are stored at path `{admin_user_id}/{employee_id}/{timestamp}_{sanitised_filename}`. The path prefix `{admin_user_id}` is enforced by Storage RLS policies so admins can only access their own files.

**Signed URLs**: `getEmployeeDocuments()` calls `createSignedUrl(path, 3600)` for each document after fetching the DB rows — URLs expire after 1 hour. `uploadEmployeeDocument(employeeId, file, documentType, expiryDate, notes, documentNumber)` also generates a signed URL immediately after upload so the new document is usable without a second load call. The 6th `documentNumber` parameter (passport number, licence number, etc.) is stored in `employee_documents.document_number` — always pass it, default to `''` if not applicable. Never store public URLs for this bucket — it is private.

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

**Admin tables** (`companies`, `employees`, `payroll_*`, `payslips`, `leave_*`, `clock_events`, `attendance_records`, `attendance_periods`, `employee_job_history`, `nafis_reports`, `employee_documents`, `insurance_policies`, `employee_insurance`, `insurance_dependants`, `leave_approval_delegates`, `employee_contracts`, `offboarding_checklists`, `offboarding_tasks`, `offboarding_task_templates`, `expense_claims`, `assets`, `asset_assignments`, `payroll_approval_log`, `training_records`, `certifications`, `letter_requests`, `appraisal_cycles`, `appraisals`, `appraisal_sections`, `compliance_overrides`, `department_staffing_rules`) use `FOR ALL USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())`.

**Manager portal policies** (added in migration 033 — access via `employees.reporting_manager_id` chain): `appraisals_manager_read` (SELECT on appraisals where employee_id IN direct reports); `appraisal_sections_manager_read` (SELECT on sections); `appraisal_sections_manager_update` (UPDATE on sections — only `rating` and `comments` columns); `appraisal_cycles_manager_read` (SELECT on cycles where `status IN ('open','active')`). These allow managers to read and score their direct reports' appraisals without admin-level access.

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
| `roster_assignments` | `published = true AND employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` |
| `shift_swap_requests` | requester or target employee: `requester_employee_id IN (...) OR target_employee_id IN (...)` |
| `expense_claims` | employee reads own claims: `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` — INSERT only via `employee_submit_expense` RPC |
| `assets` | `id IN (SELECT asset_id FROM asset_assignments WHERE employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid()))` — employees see assets ever assigned to them |
| `asset_assignments` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` — employees see their own assignment history |
| `training_records` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` — employees see their own training history |
| `certifications` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` — employees see their own certifications |
| `letter_requests` | `employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid())` — employees see their own requests; INSERT only via `employee_request_letter` RPC |

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
| `employee_get_my_roster(p_date_from, p_date_to)` | Returns published roster assignments for the calling employee in the given date range, joined with the shift template (name, color, start/end times, expected hours). |
| `employee_request_shift_swap(p_requester_date, p_target_employee_id, p_target_date, p_reason)` | Creates a `'pending'` shift swap request between two employees. Resolves the requester from `auth.uid()`. |
| `employee_submit_expense(p_category, p_amount, p_expense_date, p_description, p_receipt_url)` | Inserts an `expense_claims` row for the calling employee. Resolves `employee_id` and admin `user_id` from `auth.uid()` → `employees.auth_user_id`. Returns the new claim UUID. |
| `employee_submit_document(p_document_type, p_document_number, p_expiry_date, p_notes, p_storage_path, p_file_name, p_file_size)` | Inserts an `employee_documents` row with `status='pending'` and `submitted_by='employee'`. Resolves employee_id and admin user_id from auth.uid(). Called by `EmpDocuments.jsx` after a successful Storage upload; if the RPC fails, the component removes the orphan file from Storage. |
| `employee_request_letter(p_letter_type TEXT, p_purpose TEXT)` | Inserts a `letter_requests` row with `status='pending'`. Resolves employee_id and admin user_id from auth.uid(). Called directly from `EmpRequests.jsx`. |

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

**EmployeeModal mandatory validation** — `validate()` enforces these fields as truly required (not just format-checked when present): **Name**, **Employee No** (must be unique), **Work Email** (must be unique), **MOL ID** (≥10 digits, must be unique), **Bank Name**, **Bank Routing Code**, **IBAN**, and **Basic Salary** (must be > 0). Each shows an inline error span next to the field and an asterisk on the tab label. The **Reporting Manager** dropdown excludes the employee being edited and all Terminated employees.

**EmployeeModal tab layout**: The modal has **seven tabs for existing employees**, four for new employees (Documents, Insurance, and Contracts tabs are hidden when `employee?.id` is absent):
- Personal — name (`placeholder="e.g. John Smith"`), contact info, emergency contact
- Job & Contract — title, department, reporting manager, shift, dates
- Salary & Bank — MOL ID, salary breakdown, bank details. Basic salary: `placeholder="e.g. 5000"`
- UAE Compliance — nationality, visa, passport, Emirates ID, labour card, Nafis registration number (enabled only when `nationality === 'United Arab Emirates'`)
- Documents *(existing employees only)* — file upload form with grouped `<optgroup>` selector (from `DOC_GROUPS` exported by `EmployeeModal.jsx`; groups: UAE Residency & Work, Clinical Credentials, General), document number field, expiry, notes, file picker. Document list shows signed-URL links, expiry status badges (clinical types use 90d amber threshold), a cyan "Clinical" badge + "Self-submitted" label for employee-uploaded docs, a Review Status column (`Pending Review / Verified / Rejected`), and ✓/✗ action buttons that call `verifyEmployeeDocument(id)` / `rejectEmployeeDocument(id, reason)` (admin only). `CLINICAL_DOC_TYPES` Set and `DOC_GROUPS` array are both exported from `EmployeeModal.jsx` and imported by `EmpDocuments.jsx` and `notificationStorage.js`.
- Insurance *(existing employees only)* — coverage assignment (policy selector, member ID, card number, effective/expiry dates) with its own "Assign/Update Coverage" button, plus dependants add/delete table.
- Contracts *(existing employees only)* — current contract status card (type badge, end date countdown, start date), action buttons (Renew / Convert to Unlimited / Not Renewing for Limited; Convert to Limited for Unlimited), inline confirmation forms, contract history table, and "Print Letter" button. Each action calls `saveEmployeeContract()` + `saveEmployee()` + `addJobHistoryEntry()` directly — does **not** call `onSave`, so the modal stays open. (Feature 12)

The **Save button is hidden** on Documents, Insurance, and Contracts tabs — enforced via `tab !== 'documents' && tab !== 'insurance' && tab !== 'contracts'` in the modal footer.

**Emiratization compliance**: `Dashboard.jsx` computes `emiratiEmps` by filtering active employees where `nationality === 'United Arab Emirates'`. The required ratio comes from `company.nafisQuotaPercent` (set in Company Settings). `NafisReportModal.jsx` generates a full compliance report with CSV export and DB snapshot save via `saveNafisReport()`. The `nafis_reports` table has a `UNIQUE (user_id, period)` constraint — `saveNafisReport` upserts by period.

**Company Settings sector auto-fill**: When the admin selects an industry sector in Company Settings, the `nafisQuotaPercent` field is automatically pre-filled with that sector's default quota (defined in the `SECTORS` constant in `CompanySettings.jsx`). The admin can then override it manually.

**Document signed URL expiry**: Signed URLs from `getEmployeeDocuments()` expire after 1 hour. If a user leaves the Documents tab open for a long time and then clicks a link, it may 403. Regenerate by switching away from the tab and back — the `useEffect` in `EmployeeModal` re-fetches documents whenever `tab === 'documents'` changes.

**Insurance policies in Company Settings**: The Insurance Policies card manages `insurance_policies` rows independently of the main company save button — it has its own `handleSavePolicy` / `handleDeletePolicy` handlers with local state. The `policyRenewalStatus()` helper (module-level in `CompanySettings.jsx`, not exported) computes the badge class (green/amber/red) from `renewalDate`.

**Employee Insurance tab load**: When the Insurance tab becomes active, a `useEffect` in `EmployeeModal` fires a `Promise.all([getInsurancePolicies(), getEmployeeInsurance(employee.id), getInsuranceDependants(employee.id)])` — three parallel queries. The coverage form is pre-populated from the existing `employee_insurance` row if one exists. `saveEmployeeInsurance` upserts on `user_id,employee_id` so it always produces exactly one record per employee.

**Notification bell**: `NotificationBell.jsx` is a single shared component used in both `AppShell` (admin sidebar) and `EmployeeShell` (employee sidebar). It renders `<button title="Notifications">` — use this selector in tests. The panel opens as a `position: fixed` right-side drawer (right: 12px, top: 12px, bottom: 12px, width: 380px). The bell polls `getUnreadCount()` every 60 seconds via `setInterval` in a `useEffect`; the full list is only fetched when the panel opens. Clicking a notification calls `markNotificationRead(id)` — the row's `read_at` is set to the current timestamp.

**Notification deduplication**: `createNotifications()` uses `upsert` with `onConflict: 'recipient_user_id,type,related_entity_id'` and `ignoreDuplicates: true` — this generates `ON CONFLICT DO NOTHING`. The `related_entity_id` for expiry alerts embeds a threshold band (e.g. `{empId}_visa_60d`, `{empId}_visa_30d`) so a separate notification is created at each threshold even though the same document expiry is being tracked.

**`generateExpiryNotifications`** is called once at the end of the Dashboard's `Promise.all` data load — runs async after `setLoading(false)`, silently swallows errors. Signature: `generateExpiryNotifications(employees, _company, insurancePolicies, allEmpInsurance, allCertifications = [], allEmployeeDocs = [])`. Generates: (1) employee-level field expiry alerts (visa/passport/Emirates ID/labour card) at 60d/30d/14d; (2) `clinical_credential_expiry` alerts at 90d/30d/14d for DHA/DOH/MOH Licence, BLS/ACLS/PALS/NRP/CME docs (defined in module-private `CLINICAL_DOC_TYPES` within `notificationStorage.js`); (3) `document_expiry` alerts for **non-clinical uploaded documents** (passport scans, Medical Fitness Certificates, etc.) at 60d/30d/14d — uses `{doc.id}_doc_{thr}d` as `relatedEntityId`; (4) insurance coverage expiry alerts; (5) `probation_ending` alerts; (6) `contract_expiry` alerts; (7) `cert_expiry` alerts for certifications; (8) `clinical_licence_expiry` alerts for professional licence fields. All use ON CONFLICT DO NOTHING deduplication.

**Notification hooks in feature code**: `LeaveManager.handleApproval` creates a `leave_approved`/`leave_rejected` notification targeted at `emp.authUserId` — only fires if the employee has linked their portal account. `PayrollEditor.handleSubmitPayroll` batch-creates `payslip_available` notifications for all linked employees after `createPayslipRecords`. Both calls use `.catch(() => {})` to silently ignore failures if the notifications table doesn't exist yet.

**AdvancesManager (admin)**: Standalone page, nav item "Advances" sits between "Payroll Module" and "Leave" in `NAV_ITEMS`. Loads all advances + employees on mount. Approve/reject pending requests by calling `saveAdvance({ ...adv, status: 'active'/'cancelled' })`; settle/cancel active advances the same way. Repayment history per advance fetched lazily via `getAdvanceRepayments(advanceId)` when the row is expanded. `saveAdvance()` auto-computes `monthly_deduction = amount / repayment_months` if `monthlyDeduction` is not explicitly passed.

**EmpAdvances (employee self-service)**: Tab "Advances" sits between "Payslips" and "Expenses" in `EmployeeShell` TABS. Calls `getAdvances(emp.id)` (reads via employee self-read RLS policy, not admin scope). Advance request form calls `supabase.rpc('employee_request_advance', { p_amount, p_reason })` directly — the RPC resolves the employee from `auth.uid()`. Active advances show a progress bar: `(amount - outstandingBalance) / amount * 100`. The full TABS order in `EmployeeShell` is (12 tabs): **Home, Leave, Schedule, Attendance, Payslips, Advances, Expenses, Training, Appraisals, Documents, Requests, Profile**. Appraisals (`EmpAppraisal.jsx`) — read-only view of own appraisal cycles with star ratings and development plan. Documents (`EmpDocuments.jsx`) — employee self-upload with verify/reject workflow. Requests (`EmpRequests.jsx`) — letter request form + history.

**PayrollEditor advance info panel**: A `useEffect` loads all `active` advances via `getAdvances()` (no employeeId filter) and groups them by `employeeId` into `advanceData` state. The info panel renders only when `Object.keys(advanceData).length > 0` — it's purely informational; deductions must still be applied manually via the AllowDeductPanel. Silently swallows errors (table may not exist yet — `.catch(() => {})`).

**ManagerShell (Feature 6 + Clinic 3.2 + Clinic 6.1)**: Portal shell for `profile.role === 'manager'` users. Same visual design as `EmployeeShell`. Tabs (8): Leave Queue (`ManagerLeaveQueue`), **Expense Queue** (`ManagerExpenseQueue`), **Appraisals** (`ManagerAppraisals`), My Leave (reuses `EmpLeave`), Schedule (`EmpSchedule`), Attendance (`EmpAttendance`), Payslips (`EmpPayslips`), Profile (`EmpProfile`). Sidebar footer shows "Manager Portal" sub-label. Managers sign in via the Employee portal sign-in form — the `signInAsEmployee` flow recognises the existing 'manager' role on re-login.

**ManagerLeaveQueue (Feature 6)**: Loaded in `ManagerShell`. On mount, calls `getMyEmployeeRecord()` to get the manager's employee ID, then `getLeaveQueueForManager(emp.id)` to fetch pending/history from direct reports. Approve calls `approveLeaveAsManager(id)` (RPC); reject opens an inline modal requiring a reason, then calls `rejectLeaveAsManager(id, reason)`. History section (ManagerApproved/ManagerRejected) toggles via a ChevronDown/Up button.

**LeaveManager multi-level support (Feature 6)**:
- `pendingRequests` count now includes `'ManagerApproved'` (pre-approved by manager, awaiting HR) as well as `'Pending'`.
- In the Requests table, `'ManagerApproved'` status shows a "Final OK" + reject button pair for HR to give final sign-off via `updateLeaveRequestStatus`.
- The `approvedBy` cell conditionally shows "Mgr: {managerApprovedBy}" for ManagerApproved, and "Mgr rejected" (red) for ManagerRejected.
- Settings tab has an "Approval Delegation" card for admin to configure `leave_approval_delegates` rows (add by filling approver + delegate + date range; delete via trash icon). `getLeaveApprovalDelegates()` is loaded in `loadAll()` via `Promise.all` with `.catch(() => [])` so a missing table silently produces empty state.
- `leaveEngine.LEAVE_STATUS_COLORS` now includes `ManagerApproved: 'badge-blue'` and `ManagerRejected: 'badge-red'`.

**EmployeeModal Portal Role control (Feature 6)**: In the Job & Contract tab, a "Portal Role" `<select>` dropdown appears **only** when `employee?.id && employee?.authUserId` (existing employee with activated portal). Options: Employee / Manager. Changing the select immediately calls `setEmployeePortalRole(employee.id, newRole)` (RPC call — not part of the main Save flow). Current role is loaded via `getEmployeePortalRole(employee.id)` in a `useEffect` that fires when `tab === 'job' && employee?.authUserId` changes. Success/error feedback shown inline via `portalRoleOk` / `portalRoleErr` state.

**EndOfServiceScreen advance auto-load**: A `useEffect` fires on `employee.id` and calls `getAdvances(employee.id)`, sums `outstandingBalance` across all `active` advances, and pre-populates the "Outstanding Salary Advances" input. The field hint changes to "Auto-loaded from Advances module. Edit to override." once loaded (`advancesLoaded` state). The field remains editable so the admin can manually correct the figure.

**Probation Period Management (Feature 11)**: `EmployeeManager` shows a blue `UserCheck` icon button in the row actions for any employee with `employmentStatus === 'Probation'`. Clicking it opens `ProbationModal` (defined in `EmployeeManager.jsx`) with three modes: **Confirm Active** (sets status Active, clears `probationEndDate`, logs `probation_confirmed` job history), **Extend** (date picker → sets `probationExtended: true`, logs `probation_extended`), **Terminate** (shows UAE 14-day notice warning, calls `archiveEmployee`, logs `probation_terminated`). Modal shows days remaining/overdue from current end date. `Dashboard.jsx` computes `probationEnding` — employees in Probation status with `probationEndDate ≤ 14 days away` — and shows an amber alert card with a "Manage in Employees" link. `generateExpiryNotifications` in `notificationStorage.js` creates `probation_ending` in-app notifications at 14d and 7d thresholds using the same `ON CONFLICT DO NOTHING` deduplication pattern as other expiry alerts.

**Contract Renewal Management (Feature 12)**: `Dashboard.jsx` computes `contractExpiring` — active `Limited`-contract employees with `contractEndDate ≤ 60 days` — and shows an amber alert. `generateExpiryNotifications` also fires `contract_expiry` in-app notifications at 60d/30d/14d/7d thresholds using the `{empId}_contract_{thr}d` related_entity_id pattern. Contract actions in the EmployeeModal Contracts tab call `saveEmployee()` directly (bypassing `onSave`), then update local `form` state so the user sees the change without closing the modal. The `employee_contracts` table is **append-only** — each lifecycle action adds a new row; nothing is ever updated or deleted.

**Payroll Approval — Maker-Checker (Feature 17)**: Adds a mandatory review step before payroll can be generated. `approval_status` flow on `payroll_runs`: `'draft'` → `'pending_approval'` (Submit for Approval) → `'approved'` (Approve) → then `status = 'generated'` (Generate Payroll). Rejection returns `approval_status` to `'draft'` and stores `rejection_reason`. Recall returns from `pending_approval` back to `draft`. Four new functions in `storage.js`: `submitPayrollForApproval`, `approvePayroll`, `rejectPayroll`, `recallPayrollApproval`. `getPayrollApprovalLog(payrollRunId)` returns the full audit trail from `payroll_approval_log`. **PayrollEditor** introduces `approvalLocked` (true when `pending_approval` or `approved`) and `editingLocked` (true when `approvalLocked || isLocked`) — all input `disabled` props use `editingLocked`. The header button set is conditional: draft shows "Submit for Approval"; pending shows "Recall" + "Reject" + "✓ Approve"; approved shows "Generate Payroll" (the existing `handleSubmitPayroll` flow unchanged). Status banners are injected below the existing lock banner: amber rejection notice (shown on draft with a stored reason), blue pending notice with inline reject-reason form, green approved notice. **PayrollList** gains an "Approval" column. **Dashboard** shows a blue info alert for any payrolls in `pending_approval` state.

**Asset Management (Feature 16)**: `AssetsManager.jsx` (admin) sits at nav item "Assets" between "Roster" and "Reports" in `App.jsx`. Two tabs: **Assets** (filterable table with Assign/Return/Edit/Delete actions) and **Assignment History** (full log). `getAssets()` runs two parallel queries (assets + open assignments) then merges in JS — avoids complex Supabase JOIN syntax. Status transitions are managed exclusively by `assignAsset()` (→ `'assigned'`) and `returnAsset()` (→ `'available'`); the Edit modal explicitly excludes `'assigned'` from the status dropdown so it can't be set manually. `deleteAsset()` checks for an open assignment before deleting and throws if one exists. Employee portal: `getEmployeeCurrentAssets(employeeId)` uses the `asset_assignments_employee_read` RLS policy (no admin scope). Results rendered as a "My Assigned Assets" card in `EmpHome.jsx` — loaded via the existing `Promise.all` with `.catch(() => [])` so a missing table silently produces no card. `ASSET_CATEGORIES` is exported from `AssetsManager.jsx` (no separate constants file needed — only used in two places).

**Multi-Company / Branch Support (Feature 21)**: One admin login manages multiple company entities/branches. `CompanyContext.jsx` (`src/context/CompanyContext.jsx`) provides `companies[]`, `activeCompany`, `activeCompanyId`, `setActiveCompanyId`, `createBranch`, `deleteBranch`, and `refreshCompanies`. `CompanyProvider` wraps only `AppShell` (employees/managers don't need it). AppShell sidebar shows a branch switcher button in the `sidebar-logo` area — clicking it opens a dropdown listing all branches with a checkmark on the active one, X delete buttons for non-active branches, and an "Add Branch" link. "Add Branch" opens a modal; submitting creates the branch and auto-navigates to Company Settings. Branch deletion is guarded — `deleteBranch(id)` checks for active employees before deleting. The `companies` table gained a `branch_name TEXT` column (the short switcher label); the unique constraint on `user_id` was dropped to allow multiple rows per admin. `employees` and `payroll_runs` gained a `company_id UUID FK`. `getEmployees(companyId?)` and `getPayrolls(companyId?)` accept an optional `companyId` filter; omitting it returns all (backward-compatible for non-context components). `Dashboard`, `EmployeeManager`, `PayrollManager`, and `PayrollList` call `useCompany()` and add `activeCompanyId` to their `useEffect` deps so data reloads when the user switches branches. `CompanySettings` loads the correct branch via `getCompany(activeCompanyId)` and calls `refreshCompanies()` after saving so the sidebar switcher label updates. New employees are tagged with `companyId: activeCompanyId` on insert. New payroll runs include `companyId: activeCompanyId`. Storage functions: `getCompanies()`, `createBranch(name, templateCompany)`, `deleteBranch(id)` added to `storage.js`. `dbToCompany` / `companyToDb` include `branchName` ↔ `branch_name`. `dbToEmployee` / `employeeToDb` include `companyId` ↔ `company_id`. `getPayrolls` run mapping includes `companyId`. `savePayroll` `runRow` includes `company_id`.

**Training & Certification Records (Feature 19)**: `TrainingManager.jsx` (admin) sits at nav item "Training" between "Assets" and "Roster" in `App.jsx`. Two tabs: **Training Records** (CRUD table with type/status filters per employee) and **Certifications** (expiry-aware registry with expired/expiring-soon filters). `EmpTraining.jsx` is the "Training" tab in `EmployeeShell` (8th of 11 tabs, between Expenses and Documents). Employee portal is read-only — admin manages all records. Certification expiry status (`expired` / `Xd — Expiring` / `Xd — Due Soon` / `Active` / `No Expiry`) is computed dynamically by `certExpiryInfo(expiryDate)` exported from `TrainingManager.jsx`. Dashboard loads all certifications via `getAllCertifications().catch(() => [])` as a 6th item in the `Promise.all` and shows an amber alert for certs expiring within 60 days, linking to `onNavigate('training')`. `generateExpiryNotifications` in `notificationStorage.js` now accepts a 5th optional parameter `allCertifications = []` and fires `cert_expiry` notifications at 14d/30d/60d thresholds (same deduplication pattern as other expiry alerts — `{certId}_{thr}d` as `relatedEntityId`). No RPCs needed — admin creates/updates via `saveTrainingRecord` / `saveCertification`; employees read via the employee self-read RLS policies.

**Expense Claims & Reimbursements (Feature 14 + Clinic 3.2)**: `ExpensesManager.jsx` (admin) sits at nav item "Expenses" between "Advances" and "Leave" in `App.jsx`. `EmpExpenses.jsx` (employee self-service) is the "Expenses" tab in `EmployeeShell`, between "Advances" and "Profile". Employees submit via `supabase.rpc('employee_submit_expense', {...})` directly in `EmpExpenses.jsx` — no wrapper function needed. `EXPENSE_CATEGORIES` (the category label map) is exported from `ExpensesManager.jsx` and imported by `EmpExpenses.jsx` and `ManagerExpenseQueue.jsx` to keep labels in sync. `PayrollEditor` loads `getApprovedUnpaidExpenses()` on mount and calls `markExpensesPaid(ids, payroll.id)` on payroll submission. Status flow (clinic multi-level): `pending` → `manager_approved` (manager pre-approves via `ManagerExpenseQueue`) → `approved` (HR final sign-off) → `paid`; or `manager_rejected` / `rejected` at any pre-paid stage. `ExpensesManager` Approve button activates on both `pending` AND `manager_approved` claims; filter tabs include `manager_approved`. Manager functions cross the RLS boundary via three SECURITY DEFINER RPCs (see `sql/030`). Admin provides a mandatory `rejection_reason` via an inline form row. Receipt is a free-text URL field — no binary upload required.

**Offboarding Workflow (Feature 13)**: `EmployeeManager` shows an indigo `ClipboardList` icon button in row actions for any `Terminated` employee. `OffboardingModal.jsx` auto-creates (or loads) the `offboarding_checklists` row on mount, seeds default tasks from `offboarding_task_templates` (or the hardcoded 9-task list if none exist), then loads all tasks. Task toggling is **optimistic** — local state updates immediately, DB write happens async, state reverts on failure. The EOS calculator is layered on top by replacing the modal's return value: `if (showEOS) return <EndOfServiceScreen employee={employee} onClose={() => setShowEOS(false)} />` — this is the only modal-within-modal pattern in the codebase. NOC and Experience letters open via `window.open('', '_blank')` then `win.document.write(html); win.print()` — the same approach used by `EndOfServiceScreen.printSettlement`.

**LeaveManager Calendar tab (Feature 7)**: `LeaveManager` has a third "Calendar" tab (after Requests and Balances/Settings). It renders a monthly grid showing all approved leave colour-coded by leave type. State: `calendarMonth` (Date), `calendarDeptFilter` (string). Navigation uses chevron buttons to step months; a department `<select>` filters which employees appear. A print button calls `window.print()` against a `#calendar-print-area` div. Data comes from the same `requests` array already loaded by `loadAll()` — no extra fetch. `getApprovedLeavesForMonth(year, month)` in `leaveStorage.js` is available but the Calendar tab reads from in-memory state, not a fresh query.

**RosterManager (Feature 8 + Clinic 2.1)**: Standalone page, nav item "Roster" sits after "Attendance" in `NAV_ITEMS`. Three tabs:
- **Templates** — CRUD for `shifts` table rows. Now includes **Short Code** (e.g. D, N, M — max 3 chars, stored in `shifts.code`) and **Category** (morning/afternoon/night/flexible, stored in `shifts.shift_category`) fields. `SHIFT_CATEGORIES` and `CATEGORY_COLORS` constants in `RosterManager.jsx`. `autoExpectedHours()` pre-computes hours from start/end times.
- **Roster** — Monthly grid (clinical duty rota style): cells are compact (38px) showing the shift **code badge** coloured by the shift's colour instead of a full-name dropdown. Options in the `<select>` show just the code (2-3 chars); tooltip shows full name + times. Right edge: **Total Hrs** column showing planned hours sum per employee. Bottom: **summary footer rows** — ☀ Morning / 🌤 Afternoon / 🌙 Night / ○ Unassigned count per day. Cells before an employee's `joiningDate` are greyed out and show "–". **Export CSV** button (next to Publish) downloads a Dubai Medical University Hospital–format duty rota CSV with day-by-day codes, M/A/N/O totals, and planned hours per employee. `saveRosterAssignment()` now accepts `plannedHours` and stores it in `roster_assignments.planned_hours`. "Publish Roster" bulk-sets `published = true`.
- **Swaps** — Shows all `shift_swap_requests` for the company. Admin approves or rejects (with optional reason) via `updateShiftSwapRequest(id, status, rejectionReason)`.

**Reports module (Feature 10)**: Standalone page, nav item "Reports" (last in `NAV_ITEMS`). Seven tabs: Headcount, Payroll Cost, Leave Usage, Attendance, Doc Expiry, Salary History, Staff Turnover. All data loaded in one `Promise.all` on mount (`getEmployees`, `getPayrolls`, `getLeaveRequests({ status:'Approved' })`, `getAttendanceRecords()`, `getAllEmployeeDocuments()`, `getAllJobHistory()`). Each tab is a pure React component receiving the already-loaded data as props — no additional fetches. All aggregation logic lives in `utils/reportUtils.js` (synchronous pure functions). Every tab has Export CSV (via `Papa.unparse`) and Export PDF (via `jsPDF` auto-table) buttons. Two new storage functions: `getAllEmployeeDocuments()` (no signed URLs — for reports only) and `getAllJobHistory()` (all employees' salary change events).

**WPS Payment Tracking (Feature 9)**: After a payroll run is finalised (`status === 'generated'`), a "WPS Payment Tracking" card appears in `PayrollEditor`. WPS workflow: `draft` → `sif_generated` (auto on SIF download) → `submitted` → `confirmed` / `partial_rejection` / `failed`. Admin fills in WPS Reference No, submission date, confirmation date, and per-employee payment status (`pending` / `paid` / `rejected`). "Save WPS Status" calls `saveWpsTracking(payrollId, { wpsStatus, ... })` to update `payroll_runs` without re-saving all entries. When any entry is `rejected`, a "Download Corrected SIF" button calls `generateCorrectedSIF(company, employees, payroll, rejectedEmployeeIds)` — produces a SIF containing only the rejected employees. `PayrollList` and `Dashboard` both show a WPS status badge column on generated payroll runs. Schema: `payroll_runs` gains `wps_status TEXT DEFAULT 'draft'`, `wps_submitted_at`, `wps_confirmed_at`, `wps_reference_no`; `payroll_entries` gains `wps_payment_status TEXT DEFAULT 'pending'`, `wps_rejection_reason`.

**EmpSchedule (Feature 8)**: "Schedule" tab in both `EmployeeShell` and `ManagerShell`. Calls `getMyRoster(dateFrom, dateTo)` (wraps `employee_get_my_roster` RPC) to load the current month's published assignments. Each assignment shows shift name, color pill, date, start/end times. A "Request Swap" button on any upcoming assignment opens `SwapModal`, which calls `requestShiftSwap({ requesterDate, targetEmployeeId, targetDate, reason })` — the RPC resolves the requester from `auth.uid()`. Colleagues list for the swap target selector comes from `getMyColleagues()` (reads `employees` via the employee self-read policy).

**Leave type flags — `probation_eligible` and `requires_attachment`** (Clinic 2.3 / 2.4): `leave_types` table has two boolean columns added in `sql/028`. `probation_eligible DEFAULT true` — when false, `validateLeaveRequest` in `leaveEngine.js` blocks employees whose `employmentStatus === 'Probation'` from requesting that type; `EmpLeave` filters the dropdown to `availableTypes` only. `requires_attachment DEFAULT false` — when true, `validateLeaveRequest` blocks submission if `request.attachmentUrl` is falsy; `EmpLeave` shows a file upload UI with a hint from `ATTACHMENT_HINTS` (exported from `leaveEngine.js`). `saveLeaveType(leaveType)` in `leaveStorage.js` patches either flag by id. Both flags are toggled from the "Probation Leave Eligibility" card in `LeaveManager` Settings tab using optimistic updates.

**Leave document attachments** (Clinic 2.4): `uploadLeaveAttachment(adminUserId, employeeId, file)` in `leaveStorage.js` uploads to the existing `employee-documents` Supabase Storage bucket under path `{adminUserId}/{employeeId}/leave/{timestamp}_{safeName}`. Returns a 7-day signed URL (604800s). Reuses the bucket's existing RLS policies — no new bucket needed. `EmpLeave` stores the signed URL in `attachmentUrl` state; passes it as `p_attachment_url` to the `employee_submit_leave_request` RPC. The attachment link shows in the admin Requests table as `📎`.

**Department autocomplete in EmployeeModal** (Clinic 3.1): The Job & Contract tab's Department field uses `<input list="dept-suggestions">` + `<datalist>` fed from `getDepartments()`. This preserves free-text entry (backward-compatible with existing string department names) while offering autocomplete from formal `departments` rows. `DepartmentManager.jsx` manages the `departments` table via two tabs: Departments (indented tree with `└` prefix at `level > 0`, `flattenTree()` recursive helper) and Org Chart (recursive `OrgNode` component). Employees whose `reportingManagerId` doesn't match any active employee appear in an orphan warning note.

**Clinical Dashboard drill-down pattern** (Clinic 4.1): `ClinicalDashboard.jsx` keeps `drill` state — the id of the active KPI card. Clicking a card calls `toggle(id)` which sets `drill` to that id or `null` if already active. Each drill-down panel renders a `<DrillTable>` beneath the stats grid using the `metrics` useMemo object — no extra fetches on click. `metrics` is computed once from the four data sources loaded on mount. The `CLINICAL_DOC_TYPES` Set is imported from `EmployeeModal.jsx` (the single source of truth for which document types count as clinical credentials).

**Biometric import deduplication** (Clinic 2.2): `importBiometricPunches` in `biometricStorage.js` fetches existing clock events for the import date range, builds a `Set` of `${employee_id}_${event_type}_${eventTime.slice(0,16)}` keys, and skips any punch whose key already exists. Only new punches are submitted via the `employee_record_clock_event` RPC. Unmatched badge numbers (no mapping row) accumulate in `unmatched[]` and are returned to the UI for the admin to map. The `BiometricImport` component's "Unmatched Badges" pills pre-fill the mapping form on click.

### Business logic utilities

- **`utils/sifGenerator.js`** — Generates the UAE WPS SIF file format (SCR header + EDR per employee). Amounts are integer AED (not fils). Filename format: `{MOL_ID}{YYMMDD}{HHMMSS}.sif`. **Line endings must be `\r\n` (CRLF)** — banks reject files with LF-only endings (all lines appear as one row). `generateSIF()` uses `lines.join('\r\n')`. `parseSIFPreview()` uses `/\r?\n/` to tolerate both. The download Blob must use `type: 'application/octet-stream'` with a `Uint8Array` (via `TextEncoder`) — `text/plain` allows macOS browsers to strip the `\r` on download, reintroducing the same parse failure even after correct generation.
- **`utils/payslipGenerator.js`** — jsPDF payslip PDF. `generatePayslipPDF` is async (loads company logo). Always call `downloadPayslip(company, emp, run, entry)` from components, not `generatePayslipPDF` directly.
- **`utils/leaveEngine.js`** — UAE Federal Labour Law No. 33 of 2021 leave rules. Exports `DEFAULT_LEAVE_TYPES` (seed data), `calculateAnnualLeaveAccrual`, `countLeaveDays`, `validateLeaveRequest`.
- **`utils/gratuityCalculator.js`** — End-of-service gratuity per UAE law.
- **`utils/attendanceEngine.js`** — `ATTENDANCE_STATUS`, `STATUS_LABELS`, `STATUS_COLORS` constants + `deriveAttendanceStatus`.
- **`utils/uaeValidators.js`** — UAE-specific field validation (IBAN, Emirates ID, MOL ID) + formatters. **`formatDateUAE(dateStr): string`** is the project-wide date display formatter — always use it for any date rendered to the user (DD/MM/YYYY). Never use `.toLocaleDateString()` or raw ISO strings in the UI. `daysUntil(dateStr)` computes calendar days from today (negative = past).
- **`utils/csvImport.js`** — `parseCSV(fileContent)` + `readFileAsText(file)`. Header-name-based column matching via `buildHeaderIndex()` + `HEADER_ALIASES` map — no longer relies on fixed column offsets. `cleanId(val)` strips Excel `="value"` text-formula guards that appear when the CSV was previously exported with the `csvIdCell()` helper (prevents scientific-notation mangling of long digit strings). Used by `EmployeeManager` (bulk import employees) and `PayrollEditor` (import payroll entries from CSV). Rows where the resolved MOL ID is not ≥10 digits are skipped. Outbound export uses `csvCell()` / `csvIdCell()` helpers to prevent Excel from mangling MOL IDs and IBANs.
- **`utils/featureFlags.js`** — `getAdvancedFeatures` / `setAdvancedFeatures` / `useAdvancedFeatures` — localStorage toggle (`'workloop-advanced-features'`) for a simplified SME view. **Not currently imported anywhere** — this is dead code and safe to delete if the feature is abandoned.

### Styling

Single CSS file: `src/index.css`. Solid-colour design system (glass/blur was removed):
- Body background: `#EEF2F7` with subtle blue/cyan radial gradients
- Cards/modals: `#ffffff`; form inputs: `#f8fafc`; table headers: `#e2e8f0`
- Sidebars: solid `#08122e` (no backdrop-filter)
- `--primary: #2563EB`, `--accent: #06B6D4`
- `--sidebar-gap: 12px` controls the floating island spacing on all sides
- Nav pill: `linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)` with spring animation (`cubic-bezier(0.34, 1.3, 0.64, 1)`)

Admin shell uses `.page-header` / `.page-body` / `.card` classes. Employee portal uses `.emp-page-header` / `.emp-page-body` / `.emp-card` parallels.

**`.emp-card` inner structure**: `.emp-card` has no default padding — content will touch the border unless the first child sets its own padding via inline style OR the component uses `.emp-card-header` / `.emp-card-body` helper classes (defined in `index.css`). `.emp-card-header` gives `14px 18px` padding + a bottom border; `.emp-card-body` gives `16px 18px`. Accordion-style cards (appraisals, expense queue) set `style={{ padding: 0 }}` on the outer card and manage padding themselves per-row.

---

## Manual Testing Workflow

The project is being manually tested across all features and portals using a structured 12-day checklist in **`MANUAL_TEST_CHECKLIST.md`**. This section explains how to work with that checklist when the user asks for help.

### 12-Day Schedule

| Day | Area | Portal |
|-----|------|--------|
| 1 | Admin Auth · Dashboard · Clinical Dashboard | Admin |
| 2 | Company Settings · Employees (basic CRUD, 4 tabs) | Admin |
| 3 | Employees (advanced: Documents · Insurance · Contracts · Probation · Offboarding) | Admin |
| 4 | Departments · Letter Requests | Admin |
| 5 | Payroll (full cycle: create → approve → SIF → WPS) | Admin |
| 6 | Advances · Expenses | Admin |
| 7 | Leave (all 5 tabs) | Admin |
| 8 | Attendance · Biometric Import · Assets | Admin |
| 9 | Training · Appraisals | Admin |
| 10 | Roster · Reports (all 8 tabs) | Admin |
| 11 | Manager Portal (all 8 tabs) | Manager |
| 12 | Employee Portal (all 12 tabs) · Cross-portal flows · Edge cases | Employee |

### Checklist item format

Each task in the checklist follows this exact structure:

```
### [ID] · [Short description] - [status]
- **Profile**: which portal / who to be signed in as
- **Setup**: prerequisites that must be true before starting
- **Steps**: numbered actions the tester performs
- **Pass**: what correct behaviour looks like
- **Bug**: blank if no issue; user fills in what went wrong during testing
  - **Fixed**: added by Claude after fixing — what was changed and why
```

**Status suffixes** appended to the heading by the user during testing:
- *(blank)* — not yet tested
- `- completed` — all steps passed, no issue
- `- partial` — partially working; bug noted under **Bug**
- `- bug` — fails; bug noted under **Bug**

**⏭ DEFER** items cannot be tested on the current day because their prerequisite data is created on a later day. They are skipped and revisited when that day is reached.

### When the user asks for daily instructions

The user requests detailed instructions **one day at a time**. When asked for Day N's instructions:
- Read the existing `MANUAL_TEST_CHECKLIST.md` in full — not just Day N's section
- **Include deferred items**: scan all previous days (Days 1 through N-1) for any item marked **⏭ DEFER to Day N**. List those at the top of the day's output under a heading like `## Deferred from earlier days` before the regular Day N tasks. Expand them to full **Profile · Setup · Steps · Pass · Bug** format just like the other tasks.
- Rewrite or expand each task for Day N to have full **Profile · Setup · Steps · Pass · Bug** fields
- Steps must be explicit enough to follow cold: which button to click, which form field to fill, what value to type, what modal/confirmation to look for
- Where a task depends on earlier tasks having been completed (e.g. an employee must exist), state the prerequisite in **Setup** and reference the task ID that creates it (e.g. "Employee from E-2 must exist")
- Mark items that still cannot be tested as **⏭ DEFER to Day X** with a reason
- **Do not generate instructions for days the user hasn't asked for**

### Bug-fixing rules

When the user reports a bug (either from the checklist or directly):

1. **Find the root cause, not the symptom.** Read the relevant component(s), utility functions, and any SQL/RLS involved before writing a fix.
2. **Fix the whole class of problem, not just the one instance.** Ask: does this same bug occur in other components, other queries, or other similar data flows? If yes, fix all of them in the same change.
   - Example: a PostgREST implicit INNER JOIN silently dropping rows → fix every query in `letterStorage.js` that embeds the same join pattern, not just the one that surfaced the bug.
   - Example: CSV-imported employees missing `companyId` → fix the import code AND the query that filters by `companyId` so both past (null) and new records work, not just the one broken screen.
3. **Never patch around the symptom** (e.g. hardcoding a fallback value, suppressing an error, adding a special case). Fix the underlying data flow or logic.
4. **After fixing, run `npm run build`** to confirm no new TypeScript/lint errors before reporting the fix as done.
5. **Update the checklist** — add a `- **Fixed**: [one-line explanation of what was changed and why]` line under the **Bug** field for that item in `MANUAL_TEST_CHECKLIST.md`.

### Common patterns found during Day 1 testing

These were real bugs discovered and fixed during Day 1 — record them here so future sessions don't re-investigate the same root causes:

- **PostgREST implicit INNER JOIN drops rows**: When a Supabase query embeds a related table (e.g. `employees(name, ...)`) and the embedded table's row is blocked by RLS or missing, PostgREST silently excludes the parent row. Fix: either use `!left` hint to force a LEFT JOIN, or (more reliably) do the lookup as a separate query and merge client-side. See `letterStorage.getLetterRequests()` for the two-query pattern.
- **CSV import not stamping `companyId`**: Employees imported via CSV had `company_id = null`, so `getEmployees(activeCompanyId)` filtered them out (exact UUID match). Fix: (a) stamp `companyId: activeCompanyId` in `handleCSVImport`; (b) use `.or('company_id.eq.X,company_id.is.null')` in `getEmployees` for backward compatibility with pre-migration rows.
- **Dashboard section hidden when data is empty**: Sections guarded by `{data.length >= 2 && (...)}` show nothing rather than an empty state. Fix: always render the section card; show a helpful empty state with a navigation link instead of hiding the entire block.
- **Notification bell badge lags 60 seconds**: `NotificationBell` polls `getUnreadCount()` every 60s. When `generateExpiryNotifications` creates new rows immediately on Dashboard load, the badge doesn't update until the next poll. Fix: `createNotifications()` dispatches `window.dispatchEvent(new Event('workloop-notifications-updated'))` after the upsert; the bell listens for this event and calls `refreshCount()` immediately.
