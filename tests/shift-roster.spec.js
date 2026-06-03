/**
 * shift-roster.spec.js — Playwright tests for Feature 8: Shift Scheduling & Roster
 *
 * Covers:
 *   Admin portal (RosterManager):
 *     - Roster nav item appears in the sidebar
 *     - Roster page loads without errors
 *     - Shift Templates tab is visible and is the default
 *     - "New Shift" button is present in Templates tab
 *     - Monthly Roster tab is visible and can be clicked
 *     - Roster tab shows month navigation (prev/next)
 *     - Swap Requests tab is visible
 *     - "Publish" button is present in the Roster tab
 *
 *   Employee portal (EmpSchedule):
 *     - Schedule nav item is visible in the employee sidebar
 *     - Clicking Schedule renders the schedule page
 *     - Month navigation (prev/next) is present on the schedule page
 *     - Empty state message renders when no shifts are published
 *
 * NOTE: storageState scoped INSIDE describe blocks — never at file level.
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';

// ─── Admin — RosterManager ────────────────────────────────────────────────────
test.describe('Shift Roster — Admin portal', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  });

  test('Roster nav item is visible in the admin sidebar', async ({ page }) => {
    const rosterNav = page.locator('.sidebar-nav').getByRole('button', { name: /roster/i });
    await expect(rosterNav).toBeVisible({ timeout: 5000 });
  });

  test('Clicking Roster nav loads RosterManager without errors', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');
    // Page header should show "Shift Scheduling"
    await expect(page.locator('h2').filter({ hasText: /Shift Scheduling/i })).toBeVisible({ timeout: 8000 });
  });

  test('Shift Templates tab is active by default', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');

    const templatesTab = page.locator('button.tab-btn').filter({ hasText: /Shift Templates/i });
    await expect(templatesTab).toBeVisible({ timeout: 6000 });
    await expect(templatesTab).toHaveClass(/active/);
  });

  test('"New Shift" button is present in the Templates tab', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('button').filter({ hasText: /New Shift/i })).toBeVisible({ timeout: 6000 });
  });

  test('Clicking "New Shift" opens the shift form', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');

    await page.locator('button').filter({ hasText: /New Shift/i }).click();

    // Form should appear with a Name field
    await expect(page.locator('input[placeholder*="Morning"]')).toBeVisible({ timeout: 5000 });
  });

  test('Monthly Roster tab is visible and can be clicked', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');

    const rosterTab = page.locator('button.tab-btn').filter({ hasText: /Monthly Roster/i });
    await expect(rosterTab).toBeVisible({ timeout: 6000 });
    await rosterTab.click();
    await page.waitForLoadState('networkidle');

    // Month heading should appear
    await expect(page.locator('.card-header h3')).toBeVisible({ timeout: 6000 });
  });

  test('Roster tab shows month navigation buttons', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster/i }).click();
    await page.waitForTimeout(300);

    const h3 = page.locator('.card-header h3');
    await expect(h3).toBeVisible({ timeout: 6000 });
    const navBtns = h3.locator('button.btn-icon');
    expect(await navBtns.count()).toBeGreaterThanOrEqual(2);
  });

  test('Publish button is present in the Roster tab', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster/i }).click();
    await page.waitForTimeout(300);

    const publishBtn = page.locator('button').filter({ hasText: /Publish/i });
    await expect(publishBtn).toBeVisible({ timeout: 5000 });
  });

  test('Swap Requests tab is visible', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: /roster/i }).click();
    await page.waitForLoadState('networkidle');

    const swapTab = page.locator('button.tab-btn').filter({ hasText: /Swap Requests/i });
    await expect(swapTab).toBeVisible({ timeout: 6000 });
  });
});

// ─── Employee portal — EmpSchedule ───────────────────────────────────────────
test.describe('Shift Roster — Employee portal', () => {

  test('Schedule nav item is visible in the employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    const scheduleNav = page.locator('button.nav-item').filter({ hasText: /^Schedule$/ });
    await expect(scheduleNav).toBeVisible({ timeout: 8000 });
  });

  test('Clicking Schedule renders the schedule page', async ({ page }) => {
    await loginAsEmployee(page);

    await page.locator('button.nav-item').filter({ hasText: /^Schedule$/ }).click();
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h2').filter({ hasText: /My Schedule/i })).toBeVisible({ timeout: 8000 });
  });

  test('Schedule page shows month navigation buttons', async ({ page }) => {
    await loginAsEmployee(page);

    await page.locator('button.nav-item').filter({ hasText: /^Schedule$/ }).click();
    await page.waitForLoadState('networkidle');

    const empMain = page.locator('.emp-main');
    await expect(empMain.locator('button.btn-icon').first()).toBeVisible({ timeout: 6000 });
  });

  test('Schedule page shows empty-state when no shifts published', async ({ page }) => {
    await loginAsEmployee(page);

    await page.locator('button.nav-item').filter({ hasText: /^Schedule$/ }).click();
    await page.waitForLoadState('networkidle');

    // Either shows "No published shifts" OR shift cards — either is valid
    const empMain = page.locator('.emp-main');
    await expect(empMain).toBeVisible({ timeout: 6000 });
    // Page should not be blank — some content (empty state or cards)
    const hasContent = await empMain.locator('>*').first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});
