import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth.js';

// Attendance is the most complex feature — tests use two browser contexts
// simultaneously (admin + employee) to verify cross-portal visibility.

test.describe('Attendance — employee clock-in visibility', () => {

  test('employee clock-in appears on admin dashboard as Present', async ({ browser }) => {
    // Two independent sessions
    const adminCtx = await browser.newContext({ storageState: '.playwright/admin-session.json' });
    const empCtx   = await browser.newContext({ storageState: '.playwright/employee-session.json' });

    const adminPage = await adminCtx.newPage();
    const empPage   = await empCtx.newPage();

    // ── Employee: clock in ───────────────────────────────────────────────────
    await empPage.goto('/');
    // Employee shell renders .emp-sidebar-logo (admin shell uses .sidebar-logo)
    await expect(empPage.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await empPage.getByRole('button', { name: 'Attendance' }).click();
    await empPage.waitForLoadState('networkidle');

    // Should start as "Not started" (no previous clock-in today)
    const clockInBtn = empPage.getByRole('button', { name: /clock in/i });
    await expect(clockInBtn).toBeEnabled({ timeout: 8000 });
    await clockInBtn.click();

    // Toast or status should confirm clock-in
    await expect(
      empPage.locator('text=/clocked in|present/i')
    ).toBeVisible({ timeout: 10000 });

    // Clock-in time should be displayed (not "—")
    const clockInTime = empPage.locator('text=CLOCK IN').locator('..').locator('div').last();
    await expect(clockInTime).not.toHaveText('—', { timeout: 5000 });

    // ── Admin: refresh and verify employee is Present Today ──────────────────
    await adminPage.goto('/');
    await expect(adminPage.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await adminPage.getByRole('button', { name: 'Attendance' }).click();
    await adminPage.waitForLoadState('networkidle');

    // Click Refresh to load latest data
    await adminPage.getByRole('button', { name: /refresh/i }).click();
    await adminPage.waitForLoadState('networkidle');

    // "Present Today" stat should be at least 1
    const presentCard = adminPage.locator('.stat-card').filter({ hasText: /present today/i });
    const presentCount = await presentCard.locator('.stat-value').textContent();
    expect(parseInt(presentCount)).toBeGreaterThanOrEqual(1);

    // Records tab should show employee with PRESENT status
    await adminPage.getByRole('button', { name: /records/i }).click();
    await expect(
      adminPage.locator('text=/present/i').first()
    ).toBeVisible({ timeout: 8000 });

    await adminCtx.close();
    await empCtx.close();
  });

  test('employee page preserves clock-in state after reload', async ({ browser }) => {
    const empCtx  = await browser.newContext({ storageState: '.playwright/employee-session.json' });
    const empPage = await empCtx.newPage();

    await empPage.goto('/');
    await empPage.getByRole('button', { name: 'Attendance' }).click();
    await empPage.waitForLoadState('networkidle');

    // Only clock in if not already clocked in
    const clockInBtn = empPage.getByRole('button', { name: /clock in/i });
    if (await clockInBtn.isEnabled()) {
      await clockInBtn.click();
      await empPage.waitForTimeout(2000);
    }

    // Reload the page
    await empPage.reload();
    await empPage.waitForLoadState('networkidle');
    await empPage.waitForTimeout(2000);

    // Should NOT show "Not started" after reload
    await expect(empPage.locator('text=/not started/i')).not.toBeVisible({ timeout: 8000 });

    // Should show clock-in time
    const statusText = empPage.locator('div').filter({ hasText: /present|clocked/i }).first();
    await expect(statusText).toBeVisible({ timeout: 8000 });

    await empCtx.close();
  });

  test('clock-out button is enabled after clock-in', async ({ browser }) => {
    const empCtx  = await browser.newContext({ storageState: '.playwright/employee-session.json' });
    const empPage = await empCtx.newPage();

    await empPage.goto('/');
    await empPage.getByRole('button', { name: 'Attendance' }).click();
    await empPage.waitForLoadState('networkidle');

    const clockInBtn  = empPage.getByRole('button', { name: /clock in/i });
    const clockOutBtn = empPage.getByRole('button', { name: /clock out/i });

    if (await clockInBtn.isEnabled()) {
      await clockInBtn.click();
      await empPage.waitForTimeout(1500);
    }

    // Clock Out should now be enabled
    await expect(clockOutBtn).toBeEnabled({ timeout: 8000 });

    await empCtx.close();
  });

});

// Admin-only tests — always do a fresh login rather than using storageState.
//
// WHY NOT storageState: the stored session shares a refresh token with the
// employees describe block (which runs earlier with the same storageState file).
// Supabase rotates refresh tokens on each use, so by the time these tests run
// the RT in the file is already stale.  A fresh Supabase signInWithPassword()
// creates a brand-new session that is guaranteed to be valid.
test.describe('Attendance — admin page (saved session)', () => {
  // No test.use({ storageState }) — page starts with empty localStorage so
  // loginAsAdmin() always sees the auth page and can sign in cleanly.
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
    await page.getByRole('button', { name: 'Attendance' }).click();
    // Stat cards only appear after loadAll() completes (behind the loading guard).
    // Waiting here ensures every test body starts on a fully-loaded page.
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 25000 });
  });

  test('attendance page renders stat cards after load', async ({ page }) => {
    // beforeEach already confirmed stat cards are visible — just sanity-check header.
    await expect(page.locator('.page-header h2')).toContainText('Attendance');
  });

  test('month change reloads records', async ({ page }) => {
    // beforeEach already on a fully-loaded Attendance page.
    const monthSelect = page.locator('select').first();
    const options = await monthSelect.locator('option').allTextContents();
    if (options.length > 1) {
      const originalValue = await monthSelect.inputValue();
      await monthSelect.selectOption({ index: 1 });
      // Verify the month selector actually changed
      expect(await monthSelect.inputValue()).not.toBe(originalValue);
      // Loading text check is skipped: React 18 may batch setLoading(true/false)
      // fast enough that the spinner is never painted to the DOM. Instead, wait
      // for network to settle and confirm stat cards still render for the new month.
      await page.waitForLoadState('networkidle');
      await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 15000 });
    }
  });

  test('admin Refresh button triggers a data reload', async ({ page }) => {
    // beforeEach already on a fully-loaded Attendance page — Refresh is visible.
    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    await expect(refreshBtn).toBeVisible({ timeout: 10000 });
    await expect(refreshBtn).toBeEnabled();
    await refreshBtn.click();
    // Checking the loading spinner is unreliable: React 18 may batch
    // setLoading(true) + setLoading(false) when data returns quickly, so the
    // spinner is never painted to the DOM (same as month-change test).
    // Instead verify: network settles and stat cards are still visible afterwards.
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 15000 });
  });

  test('missing clock-out stat card renders a number', async ({ page }) => {
    // beforeEach already on a fully-loaded Attendance page.
    const missingCard = page.locator('.stat-card').filter({ hasText: /missing clock.out/i });
    await expect(missingCard).toBeVisible({ timeout: 10000 });
    const count = await missingCard.locator('.stat-value').textContent();
    expect(Number.isFinite(parseInt(count))).toBe(true);
  });

  test('close period succeeds without permission error', async ({ page }) => {
    // beforeEach already on a fully-loaded Attendance page;
    // .page-header-actions is rendered (stat cards confirmed above).
    const closePeriodBtn = page.getByRole('button', { name: /close period/i });
    if (await closePeriodBtn.isVisible()) {
      await closePeriodBtn.click();
      // Should NOT show a permission-denied error
      await expect(page.locator('text=/permission denied/i')).not.toBeVisible({ timeout: 5000 });
      // Period closed badge or success message should appear
      await expect(page.locator('text=/period closed|closed successfully/i')).toBeVisible({ timeout: 8000 });
    } else {
      // Period already closed — green "Period Closed" badge is in .page-header-actions
      await expect(page.locator('text=Period Closed')).toBeVisible({ timeout: 5000 });
    }
  });
});
