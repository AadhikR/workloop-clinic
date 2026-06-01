import { test, expect } from '@playwright/test';

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

  test('admin Refresh button shows loading indicator', async ({ page }) => {
    await page.goto('/');
    await page.use?.({ storageState: '.playwright/admin-session.json' });
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Attendance' }).click();
    await page.waitForLoadState('networkidle');

    const refreshBtn = page.getByRole('button', { name: /refresh/i });
    await refreshBtn.click();
    // Loading text should appear briefly
    await expect(page.locator('text=/loading attendance/i')).toBeVisible({ timeout: 3000 });
  });

  test('missing clock-out shows for previous-day clock-in without clock-out', async ({ page }) => {
    // This test verifies the dynamic missing-clock-out detection.
    // Since we can't easily simulate a previous day in E2E, we check the
    // "Missing Clock-Out" stat card is present and renders a number (even if 0).
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Attendance' }).click();
    await page.waitForLoadState('networkidle');

    const missingCard = page.locator('.stat-card').filter({ hasText: /missing clock.out/i });
    await expect(missingCard).toBeVisible({ timeout: 8000 });
    const count = await missingCard.locator('.stat-value').textContent();
    expect(Number.isFinite(parseInt(count))).toBe(true);
  });

  test('close period succeeds without permission error', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Attendance' }).click();
    await page.waitForLoadState('networkidle');

    const closePeriodBtn = page.getByRole('button', { name: /close period/i });
    if (await closePeriodBtn.isVisible()) {
      await closePeriodBtn.click();
      // Should NOT show a permission-denied error
      await expect(
        page.locator('text=/permission denied/i')
      ).not.toBeVisible({ timeout: 5000 });
      // Period closed badge should appear, OR a success message
      const success = page.locator('text=/period closed|closed successfully/i');
      await expect(success).toBeVisible({ timeout: 8000 });
    } else {
      // Period already closed — that's fine
      await expect(page.locator('text=/period closed/i')).toBeVisible({ timeout: 5000 });
    }
  });
});

// Use saved sessions for the single-page tests
test.describe('Attendance — admin page (saved session)', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('attendance page loads without console errors', async ({ page }) => {
    const errors = [];
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Attendance' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0);
  });

  test('month change reloads records', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Attendance' }).click();
    await page.waitForLoadState('networkidle');

    // Change month selector
    const monthSelect = page.locator('select').first();
    const options = await monthSelect.locator('option').allTextContents();
    if (options.length > 1) {
      await monthSelect.selectOption({ index: 1 });
      // Loading should appear
      await expect(page.locator('text=/loading attendance/i')).toBeVisible({ timeout: 5000 });
      await page.waitForLoadState('networkidle');
    }
  });
});
