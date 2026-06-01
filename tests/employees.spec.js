import { test, expect } from '@playwright/test';

// Use saved admin session — no need to log in each test
test.use({ storageState: '.playwright/admin-session.json' });

const UNIQUE = `Playwright_${Date.now()}`;
const EMP_EMAIL = `playwright_${Date.now()}@test.local`;

test.describe('Employees', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('add new employee appears in list', async ({ page }) => {
    await page.getByRole('button', { name: /add employee/i }).click();
    await page.locator('input[placeholder*="Full name" i]').fill(UNIQUE);
    await page.locator('input[placeholder*="work email" i], input[type="email"]').first().fill(EMP_EMAIL);
    await page.locator('input[placeholder*="basic salary" i], input[placeholder*="salary" i]').first().fill('6000');
    await page.getByRole('button', { name: /save/i }).last().click();
    await expect(page.locator(`text=${UNIQUE}`)).toBeVisible({ timeout: 10000 });
  });

  test('edit employee salary updates the record', async ({ page }) => {
    // Click the test employee we just created
    const row = page.locator(`tr:has-text("${UNIQUE}")`);
    await expect(row).toBeVisible({ timeout: 8000 });
    await row.getByRole('button', { name: /edit/i }).click();
    const salaryInput = page.locator('input[placeholder*="salary" i]').first();
    await salaryInput.clear();
    await salaryInput.fill('7500');
    await page.getByRole('button', { name: /save/i }).last().click();
    // Confirm save succeeded (no error alert)
    await expect(page.locator('.alert-danger')).not.toBeVisible({ timeout: 5000 });
  });

  test('archive employee removes from active list', async ({ page }) => {
    const row = page.locator(`tr:has-text("${UNIQUE}")`);
    if (!await row.isVisible()) {
      test.skip(true, 'Test employee not found — run add test first');
    }
    await row.getByRole('button', { name: /archive|terminate/i }).click();
    // Confirm dialog if one appears
    const confirmBtn = page.getByRole('button', { name: /confirm|yes/i });
    if (await confirmBtn.isVisible({ timeout: 2000 })) await confirmBtn.click();
    // Employee should no longer be in active list
    await expect(page.locator(`text=${UNIQUE}`)).not.toBeVisible({ timeout: 8000 });
  });

  test('no console errors on employees page', async ({ page }) => {
    const errors = [];
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.waitForTimeout(2000);
    expect(errors).toHaveLength(0);
  });
});
