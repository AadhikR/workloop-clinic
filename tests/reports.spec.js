/**
 * reports.spec.js — Playwright tests for Feature 10: HR Reporting & Analytics
 *
 * Selector pattern for tab buttons:
 *   The tab buttons render as <button><Icon aria-hidden /> Label</button>.
 *   The raw textContent is " Label" (leading space from SVG sibling), so
 *   /^Label$/i anchored-regex selectors fail.  Instead we use:
 *     page.locator('.page-body').getByRole('button', { name: label })
 *   which uses the WAI-ARIA accessible name — excludes aria-hidden SVGs,
 *   normalises whitespace — and is scoped to .page-body to avoid matching
 *   sidebar nav buttons (e.g. sidebar "Attendance" vs tab "Attendance").
 */
import { test, expect } from '@playwright/test';

test.describe('Reports — HR Reporting & Analytics', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  async function goToReports(page) {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Reports' }).click();
    await page.waitForLoadState('networkidle');
    // Wait for data load — h2 only renders after loading === false
    await expect(page.locator('h2').filter({ hasText: /HR Reports/i })).toBeVisible({ timeout: 12000 });
  }

  // Helper: click a Reports tab button scoped to .page-body
  async function clickTab(page, label) {
    await page.locator('.page-body').getByRole('button', { name: label, exact: true }).click();
    await page.waitForTimeout(300); // let React re-render the tab content
  }

  // ── Navigation ───────────────────────────────────────────────────────────────

  test('"Reports" nav item is visible in the admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Reports' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Reports page loads and shows 7 tab buttons', async ({ page }) => {
    await goToReports(page);

    const tabLabels = ['Headcount', 'Payroll Cost', 'Leave Usage', 'Attendance', 'Doc Expiry', 'Salary History', 'Staff Turnover'];
    for (const label of tabLabels) {
      // Scoped to .page-body to avoid matching sidebar nav buttons
      await expect(
        page.locator('.page-body').getByRole('button', { name: label, exact: true })
      ).toBeVisible({ timeout: 6000 });
    }
  });

  // ── Headcount tab (default — no click needed) ─────────────────────────────

  test('Headcount tab shows stat cards with employee totals', async ({ page }) => {
    await goToReports(page);
    await expect(
      page.locator('.stat-card').filter({ hasText: /Total Active Employees/i })
    ).toBeVisible({ timeout: 8000 });
    await expect(
      page.locator('.stat-card').filter({ hasText: /Departments/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('Headcount tab has Export CSV and Export PDF buttons', async ({ page }) => {
    await goToReports(page);
    await expect(page.locator('button').filter({ hasText: /Export CSV/i }).first()).toBeVisible({ timeout: 6000 });
    await expect(page.locator('button').filter({ hasText: /Export PDF/i }).first()).toBeVisible({ timeout: 5000 });
  });

  // ── Payroll Cost tab ──────────────────────────────────────────────────────────

  test('Payroll Cost tab renders without error', async ({ page }) => {
    await goToReports(page);
    await clickTab(page, 'Payroll Cost');

    // Either a table (if payrolls exist) or an empty state should appear
    const table = page.locator('.card table').first();
    const empty = page.locator('.empty-state').first();
    await expect(table.or(empty).first()).toBeVisible({ timeout: 8000 });
  });

  // ── Leave Usage tab ───────────────────────────────────────────────────────────

  test('Leave Usage tab shows year selector', async ({ page }) => {
    await goToReports(page);
    await clickTab(page, 'Leave Usage');

    // The year <select> is the first select in .page-body after switching tab
    const sel = page.locator('.page-body select').first();
    await expect(sel).toBeVisible({ timeout: 6000 });
    const opts = await sel.locator('option').allTextContents();
    expect(opts.length).toBeGreaterThanOrEqual(1);
  });

  // ── Attendance tab ────────────────────────────────────────────────────────────

  test('Attendance tab shows period month input', async ({ page }) => {
    await goToReports(page);
    // Use scoped clickTab to avoid clicking the sidebar "Attendance" nav button
    await clickTab(page, 'Attendance');

    await expect(page.locator('input[type="month"]')).toBeVisible({ timeout: 6000 });
  });

  // ── Doc Expiry tab ────────────────────────────────────────────────────────────

  test('Doc Expiry tab shows days-threshold selector', async ({ page }) => {
    await goToReports(page);
    await clickTab(page, 'Doc Expiry');

    const sel = page.locator('.page-body select').first();
    await expect(sel).toBeVisible({ timeout: 6000 });
    const opts = await sel.locator('option').allTextContents();
    expect(opts.some(o => /30 days/i.test(o))).toBe(true);
    expect(opts.some(o => /90 days/i.test(o))).toBe(true);
  });

  // ── Salary History tab ────────────────────────────────────────────────────────

  test('Salary History tab shows date range inputs', async ({ page }) => {
    await goToReports(page);
    await clickTab(page, 'Salary History');

    const dateInputs = page.locator('.page-body input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 6000 });
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);
  });

  // ── Staff Turnover tab ────────────────────────────────────────────────────────

  test('Staff Turnover tab shows stat cards and date range inputs', async ({ page }) => {
    await goToReports(page);
    await clickTab(page, 'Staff Turnover');

    await expect(page.locator('.stat-card').filter({ has: page.locator('.stat-label', { hasText: /^Joiners$/i }) })).toBeVisible({ timeout: 6000 });
    // Use .stat-label scope to avoid matching "Avg. Tenure (Leavers)" card
    await expect(page.locator('.stat-card').filter({ has: page.locator('.stat-label', { hasText: /^Leavers$/i }) })).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.page-body input[type="date"]').first()).toBeVisible({ timeout: 5000 });
  });
});
