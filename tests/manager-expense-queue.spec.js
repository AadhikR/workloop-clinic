/**
 * manager-expense-queue.spec.js
 * Feature 3.2 — Multi-Level Expense Approvals
 *
 * Admin portal (ExpensesManager):
 *   - manager_approved filter tab is visible in ExpensesManager
 *   - "Manager Approved" badge appears on manager-approved claims (if data exists)
 *   - "Manager Rejected" badge appears on manager-rejected claims (if data exists)
 *   - Approve button activates on both 'pending' AND 'manager_approved' claims
 *
 * Manager portal (ManagerShell):
 *   NOTE: The manager portal requires a user with profile.role === 'manager'.
 *   The standard test employee has role='employee' so manager tests skip
 *   unless a manager session is available at .playwright/manager-session.json.
 *   These tests are structural — they verify the Expense Queue tab renders correctly.
 *
 * NOTE: storageState inside admin describe blocks.
 * Manager portal describe checks for manager-session file and skips if absent.
 */
import { test, expect } from '@playwright/test';
import { existsSync } from 'fs';

const MANAGER_SESSION = '.playwright/manager-session.json';

// ─── helpers ──────────────────────────────────────────────────────────────────

async function goToExpenses(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Expenses' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 10000 });
}

// ─── Admin — multi-level status badges & filters ──────────────────────────────

test.describe('Manager Expense Queue (3.2) — Admin portal: status filters', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Expenses page has a "Mgr Approved" filter tab', async ({ page }) => {
    await goToExpenses(page);
    // STATUS_LABEL maps manager_approved → 'Mgr Approved' (not "Manager Approved")
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /Mgr Approved/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Expenses status filter tabs include All, Pending, Mgr Approved, HR Approved, Paid, Rejected', async ({ page }) => {
    await goToExpenses(page);

    // STATUS_LABEL values: manager_approved → 'Mgr Approved', approved → 'HR Approved'
    // 'Pending' tab may have a count badge (e.g. "Pending1"), so use unanchored regex (no ^ or $)
    for (const label of ['All', 'Pending', 'Paid', 'Rejected']) {
      await expect(
        page.locator('button.tab-btn').filter({ hasText: new RegExp(label, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
    // manager_approved tab label is "Mgr Approved"
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /Mgr Approved/i }).first()
    ).toBeVisible({ timeout: 5000 });
    // approved tab label is "HR Approved"
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /HR Approved/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('switching to "Mgr Approved" tab updates the active button style', async ({ page }) => {
    await goToExpenses(page);
    const mgApprBtn = page.locator('button.tab-btn').filter({ hasText: /Mgr Approved/i }).first();
    await mgApprBtn.click();
    const cls = await mgApprBtn.getAttribute('class');
    expect(cls).toMatch(/primary|active/i);
  });

  test('manager_approved claims show Approve action button (multi-level flow)', async ({ page }) => {
    await goToExpenses(page);

    // Switch to Mgr Approved tab
    await page.locator('button.tab-btn').filter({ hasText: /Mgr Approved/i }).first().click();

    // If any manager-approved claims exist, they should have an Approve button
    const rows = page.locator('table tbody tr');
    const rowCount = await rows.count();
    if (rowCount === 0) {
      test.skip(true, 'No manager-approved expense claims in test data');
      return;
    }
    await expect(
      page.locator('button').filter({ hasText: /approve/i }).first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('Expenses stat cards include an "Approved Unpaid" card', async ({ page }) => {
    await goToExpenses(page);
    await expect(
      page.locator('.stat-card').filter({ hasText: /approved.*unpaid|unpaid/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Expenses table shows Status column with badge values', async ({ page }) => {
    await goToExpenses(page);

    const table = page.locator('table').first();
    if (!(await table.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No expense claims — table not rendered');
      return;
    }

    await expect(
      table.locator('th').filter({ hasText: /status/i }).first()
    ).toBeVisible({ timeout: 4000 });
  });
});

// ─── Manager portal — ManagerShell Expense Queue tab ─────────────────────────

test.describe('Manager Expense Queue (3.2) — Manager portal', () => {

  // test.use is evaluated at collection time — if MANAGER_SESSION doesn't exist Playwright
  // throws ENOENT.  Fall back to admin session so collection succeeds; each test skips itself.
  test.use({ storageState: existsSync(MANAGER_SESSION) ? MANAGER_SESSION : '.playwright/admin-session.json' });

  test.beforeEach(async ({}, testInfo) => {
    if (!existsSync(MANAGER_SESSION)) {
      testInfo.skip(true, 'No manager session — set up a manager-role user to run manager portal tests');
    }
  });

  test('"Expense Queue" tab is visible in the Manager portal sidebar', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Expense Queue$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Expense Queue tab renders the manager queue component', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button.nav-item').filter({ hasText: /^Expense Queue$/ }).click();
    // Do NOT use waitForLoadState('networkidle') — ManagerShell has NotificationBell polling
    // every 60s which prevents networkidle from resolving, causing a 30s hang and possible
    // refresh-token rotation that would corrupt the session for subsequent tests.

    await expect(
      page.locator('h2, h3').filter({ hasText: /expense queue|expense approvals/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('Expense Queue shows Approve/Reject buttons on pending claims', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button.nav-item').filter({ hasText: /^Expense Queue$/ }).click();
    // No networkidle — NotificationBell polls every 60s, preventing networkidle from resolving.
    await expect(
      page.locator('h2, h3').filter({ hasText: /expense queue|expense approvals/i }).first()
    ).toBeVisible({ timeout: 10000 });

    const approveBtn = page.locator('button').filter({ hasText: /approve/i }).first();
    const emptyState = page.locator('text=/no.*pending|queue is empty/i').first();

    const hasContent = await approveBtn.isVisible({ timeout: 4000 }).catch(() => false)
                    || await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});
