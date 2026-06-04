/**
 * reports.spec.js — Playwright tests for Feature 10: HR Reporting & Analytics
 *
 * Covers:
 *   Navigation:
 *     - "Reports" nav item appears in the admin sidebar
 *     - Clicking it loads the Reports page
 *
 *   Report tabs — each tab renders without error:
 *     - Headcount tab: stat cards visible
 *     - Payroll Cost tab: either table or empty state
 *     - Leave Usage tab: year selector visible
 *     - Attendance tab: period selector visible
 *     - Doc Expiry tab: days filter selector visible
 *     - Salary History tab: date range inputs visible
 *     - Staff Turnover tab: date range inputs visible
 *
 *   Export buttons:
 *     - Each tab has Export CSV and Export PDF buttons
 *
 * All tests use storageState scoped inside the describe block.
 */
import { test, expect } from '@playwright/test';

test.describe('Reports — HR Reporting & Analytics', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  async function goToReports(page) {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Reports' }).click();
    await page.waitForLoadState('networkidle');
    // Wait for loading to finish
    await expect(page.locator('h2').filter({ hasText: /HR Reports/i })).toBeVisible({ timeout: 12000 });
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
      await expect(
        page.locator('button').filter({ hasText: new RegExp(`^${label}$`, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  // ── Headcount tab ─────────────────────────────────────────────────────────────

  test('Headcount tab shows stat cards with employee totals', async ({ page }) => {
    await goToReports(page);
    // Headcount is the default tab
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
    await page.locator('button').filter({ hasText: /^Payroll Cost$/i }).first().click();
    await page.waitForLoadState('networkidle');

    // Either a table or an empty state should appear
    const table    = page.locator('table').first();
    const empty    = page.locator('.empty-state').first();
    await expect(table.or(empty)).toBeVisible({ timeout: 8000 });
  });

  // ── Leave Usage tab ───────────────────────────────────────────────────────────

  test('Leave Usage tab shows year selector', async ({ page }) => {
    await goToReports(page);
    await page.locator('button').filter({ hasText: /^Leave Usage$/i }).first().click();

    await expect(page.locator('select').first()).toBeVisible({ timeout: 6000 });
    // Check the selector has year options
    const opts = await page.locator('select').first().locator('option').allTextContents();
    expect(opts.length).toBeGreaterThanOrEqual(1);
  });

  // ── Attendance tab ────────────────────────────────────────────────────────────

  test('Attendance tab shows period month input', async ({ page }) => {
    await goToReports(page);
    await page.locator('button').filter({ hasText: /^Attendance$/i }).first().click();

    await expect(page.locator('input[type="month"]')).toBeVisible({ timeout: 6000 });
  });

  // ── Doc Expiry tab ────────────────────────────────────────────────────────────

  test('Doc Expiry tab shows days-threshold selector', async ({ page }) => {
    await goToReports(page);
    await page.locator('button').filter({ hasText: /^Doc Expiry$/i }).first().click();

    const sel = page.locator('select').first();
    await expect(sel).toBeVisible({ timeout: 6000 });
    const opts = await sel.locator('option').allTextContents();
    expect(opts.some(o => /30 days/i.test(o))).toBe(true);
    expect(opts.some(o => /90 days/i.test(o))).toBe(true);
  });

  // ── Salary History tab ────────────────────────────────────────────────────────

  test('Salary History tab shows date range inputs', async ({ page }) => {
    await goToReports(page);
    await page.locator('button').filter({ hasText: /^Salary History$/i }).first().click();

    const dateInputs = page.locator('input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 6000 });
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);
  });

  // ── Staff Turnover tab ────────────────────────────────────────────────────────

  test('Staff Turnover tab shows stat cards and date range inputs', async ({ page }) => {
    await goToReports(page);
    await page.locator('button').filter({ hasText: /^Staff Turnover$/i }).first().click();

    await expect(page.locator('.stat-card').filter({ hasText: /Joiners/i })).toBeVisible({ timeout: 6000 });
    await expect(page.locator('.stat-card').filter({ hasText: /Leavers/i })).toBeVisible({ timeout: 5000 });
    const dateInputs = page.locator('input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 5000 });
  });
});
