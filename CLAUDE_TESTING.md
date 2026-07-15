# CLAUDE_TESTING.md

Playwright E2E testing patterns for Workloop Clinic HRMS. Referenced from CLAUDE.md — read this file when writing or debugging tests.

## Test suite setup

Copy `.env.test.example` → `.env.test` and fill in:
- `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — same as `.env`
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase Dashboard → Project Settings → API → `service_role` key
- `TEST_MANAGER_EMAIL` / `TEST_MANAGER_PASSWORD` / `TEST_MANAGER_NAME` — manager test account (defaults in `.env.test.example`; auto-created by global-setup)

First-time setup — run in Supabase SQL Editor:
```sql
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
```

**Required migration**: `sql/034_manager_role.sql` must be applied before `manager-portal.spec.js` or `cross-profile.spec.js`.

### Global setup/teardown

`global-setup.js` creates three test users (`test.admin@workloop-test.local`, `test.employee@workloop-test.local`, `test.manager@workloop-test.local`), seeds company/employee rows, links portal accounts, seeds deterministic test data, then saves browser sessions to `.playwright/admin-session.json`, `.playwright/employee-session.json`, `.playwright/manager-session.json`. Also writes `.playwright/env.json` with seeded IDs for teardown. `global-teardown.js` cleans all feature tables.

**Manager session deduplication**: After saving all sessions, global-setup must use delete-then-insert (not upsert) to leave exactly ONE `user_profiles` row for the manager:
```js
await db.from('user_profiles').delete().eq('user_id', mgrUser.id);
await db.from('user_profiles').insert(
  { user_id: mgrUser.id, role: 'manager', company_user_id: adminUser.id, employee_id: managerEmpId }
);
```
This must run AFTER `browser.close()`.

## Critical auth rule

**NEVER use `supabase.auth.getUser()` in storage utility functions** — use `supabase.auth.getSession()` instead. `getUser()` triggers refresh-token rotation. Shared `storageState` files mean subsequent tests hold a stale RT → 401 → `SIGNED_OUT` → app unmounts to login page, cascading failures.

Each storage file has a private `getSessionUser()` helper. `AuthContext.jsx` is the ONLY place that should call `getUser()`.

**Symptom**: screenshot shows Workloop login page mid-test → `SIGNED_OUT` fired. Search `src/` for `supabase.auth.getUser` — none should exist outside `AuthContext`.

## Shell selectors

- Admin shell: `.sidebar-logo`. Employee shell: `.emp-sidebar-logo`. Never cross them.
- Auth submit: always `locator('button[type="submit"]')` — never `getByRole('button', { name: /^sign in$/i })`.
- Managers sign in through the Employee / Manager form.

## Loading and waiting

**Never wait for loading spinners to hide — wait for the target element directly:**
```js
// ❌ Races React render
await expect(page.locator('text=Loading attendance module')).toBeHidden({ timeout: 20000 });
// ✅ Playwright retries until element exists
await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 20000 });
```

**`waitForLoadState('networkidle')` hangs** — three components poll:
- `AttendanceManager`: every 30s
- `ManagerShell`/`EmployeeShell`: `NotificationBell` every 60s

Use `'domcontentloaded'` for lightweight tab-transition waits, always followed by a specific element assertion.

**React 18 batching**: loading spinners may never paint. Don't assert spinner visibility — assert end state only.

## Playwright API gotchas

| Trap | Fix |
|------|-----|
| `isVisible()` is non-waiting | Use `expect(loc).toBeVisible({ timeout: N })` or `.waitFor()` |
| `isVisible()` returns `true` for disabled buttons | Use `isEnabled()` for conditional branching |
| `.first().or()` is invalid | Call `.first()` AFTER `.or()`, never before |
| `page.locator('.foo, text=/bar/i')` is invalid CSS | Use `.or()`: `page.locator('.foo').or(page.getByText(/bar/i))` |
| `option[value!=""]` is not valid CSS | Use `locator('option').count()` |
| `toBeVisible()` returns `false` for `<option>` elements | Check the `<select>` parent instead |
| `canClockIn` never resets after clock-out | Handle "already clocked in today" with skip, not retry |

## Selector patterns by component

### Navigation — scope to avoid duplicates

**Sidebar nav**: Dashboard renders inline buttons that duplicate sidebar labels. Always scope:
```js
await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
```

**Employee/Manager portal nav** — two render sites (sidebar + mobile bottom bar):
```js
// ✅ Desktop sidebar only
await page.locator('button.nav-item').filter({ hasText: /^Attendance$/ }).click();
// ❌ Matches both → strict-mode violation
await page.getByRole('button', { name: 'Attendance' }).click();
```

After `page.reload()`, employee portal resets to `home` tab — re-navigate after reload.

**Tab buttons**: `getByRole('button', { name: /settings/i })` matches Leave's "Settings" tab AND sidebar "Company Settings". Scope to `button.tab-btn`:
```js
page.locator('button.tab-btn').filter({ hasText: /^Settings$/i });
```

### Tab buttons with icons

Buttons with `<Icon aria-hidden /> {label}` have leading space in `textContent`. Use `getByRole` scoped to a container:
```js
page.locator('.page-body').getByRole('button', { name: 'Payroll Cost', exact: true });
```

### Filter chips with count suffix

`"Available (2)"` — anchored regex `/^Available$/i` fails. Use substring `hasText`:
```js
page.locator('button.tab-btn').filter({ hasText: 'Available' });
```

Same for `AppraisalManager` Reviews tab with badge count.

### Stat card text collisions

`hasText: /Active Advances/i` may match sibling cards' sub-labels. Use case-sensitive regex, scope to `.stat-label`, or ensure distinct text.

### `test.use({ storageState })` scoping

When a spec file mixes admin and employee tests, place `test.use({ storageState })` INSIDE each admin `describe` block — never at file level. See `advances.spec.js` for the pattern.

### Icon-only buttons

Use `title` attribute: `button[title="Edit asset"]`, `button[title="Delete employee"]`, `button[title="Probation actions"]`.

### Buttons/inputs without explicit type attributes

`button[type="submit"]` requires the attribute to be explicitly present. Target by text content instead.
Same for `input[type="text"]` — target by `placeholder` or exclusion selectors.

### Form-specific selectors

| Component | Trap | Correct selector |
|-----------|------|-----------------|
| `EmpLeave` form | Inline, not a modal | `.emp-card select`, `.emp-card input[type="date"]`, `.emp-card button[type="submit"]` |
| `EmpProfile` | Inputs only in edit mode | Click "Edit" button first |
| `bankName` | Free-text input, not `<select>` | `input[placeholder*="ENBD"]` |
| File upload | `input[type="file"]` is `display:none` | Check `.modal` `getByText(/Click to choose file/i)` |
| Offboarding tasks | Lucide icons, not checkboxes | `button[title="Remove task"]` or empty-state text |

### Modal selectors

- `.modal-overlay` vs `.modal-backdrop`: both exist. `.modal` works in both cases.
- Multiple Cancel buttons in layered modals: use `.first()` for the innermost one.

### Data-conditional tables

Always skip-guard before asserting `th`:
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

### Component-specific notes

- **EmployeeManager archive**: row disappears from Employee List, reappears in "Terminated Employees" tab (3rd tab, `UserX` icon).
- **EmployeeManager Document Expiry tab**: pass `allDocs={allDocs}` prop — omitting it hides uploaded-doc group.
- **Notification panel**: don't use `[style*="border-bottom"]` for rows — header matches too. Identify rows by emoji prefix: `/📄|⚠️|🏥|🔄|✅|❌|📝|💰|🔔/`.
- **CompanySettings h2**: text is "Company / Employer Settings" — use `/employer settings/i`.
- **EmployeeShell sidebar footer**: shows name + job title, NOT email. Check Sign Out button instead.
- **Leave module**: "Approval Chain" is a `<label>`, not `<h3>`. `getLeaveApprovalDelegates()` may 500 if table missing.
- **`getMyCompany()` with multiple branches**: already uses `.order().limit(1)` before `.maybeSingle()`.
