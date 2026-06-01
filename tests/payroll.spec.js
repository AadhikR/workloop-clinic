import { test, expect } from '@playwright/test';

test.use({ storageState: '.playwright/admin-session.json' });

test.describe('Payroll', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Payroll Module' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('payroll page loads without errors', async ({ page }) => {
    const errors = [];
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.waitForTimeout(2000);
    expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0);
  });

  test('create new payroll run appears as draft', async ({ page }) => {
    await page.getByRole('button', { name: /new payroll|create.*run/i }).click();
    // Select period (first available) and confirm
    const confirmBtn = page.getByRole('button', { name: /create|confirm|start/i }).last();
    if (await confirmBtn.isVisible({ timeout: 3000 })) await confirmBtn.click();

    await page.waitForLoadState('networkidle');
    // A draft run should now exist
    await expect(page.locator('text=/draft/i').first()).toBeVisible({ timeout: 10000 });
  });

  test('generated run locks all inputs', async ({ page }) => {
    // Find a generated run (if any)
    const generatedRow = page.locator('tr, .card').filter({ hasText: /generated/i }).first();
    if (!await generatedRow.isVisible({ timeout: 3000 })) {
      test.skip(true, 'No generated payroll runs to test locking');
    }
    await generatedRow.click();
    await page.waitForLoadState('networkidle');

    // All salary inputs should be disabled
    const inputs = page.locator('input[type="number"]:not([disabled])');
    const count = await inputs.count();
    expect(count).toBe(0);

    // Lock banner should be visible
    await expect(page.locator('text=/locked|generated/i').first()).toBeVisible();
  });

  test('dashboard payroll trend renders without crash', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h2:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });
    // getMonthName is declared before trendRuns — no temporal dead zone crash
    const errors = [];
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.waitForTimeout(3000);
    expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0);
    // Page should not be blank
    await expect(page.locator('h2')).toBeVisible();
  });
});
