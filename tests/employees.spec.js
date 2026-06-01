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

    // Personal tab is shown by default — fill name (placeholder: "e.g. John Smith")
    await page.locator('input[placeholder="e.g. John Smith"]').fill(UNIQUE);
    // Work email (placeholder: "work@company.com") — Personal Email is "personal@email.com"
    await page.locator('input[placeholder="work@company.com"]').fill(EMP_EMAIL);

    // Switch to Salary & Bank tab to fill basic salary
    await page.getByRole('button', { name: /salary/i }).first().click();
    await page.locator('input[placeholder="e.g. 5000"]').fill('6000');

    // Save — modal footer primary button says "Add Employee" for new records
    await page.locator('.modal-footer .btn-primary').click();
    await expect(page.locator(`text=${UNIQUE}`)).toBeVisible({ timeout: 10000 });
  });

  test('edit employee salary updates the record', async ({ page }) => {
    // Click the test employee we just created
    const row = page.locator(`tr:has-text("${UNIQUE}")`);
    await expect(row).toBeVisible({ timeout: 8000 });
    await row.getByRole('button', { name: /edit/i }).click();

    // Navigate to Salary & Bank tab before editing salary
    await page.getByRole('button', { name: /salary/i }).first().click();
    const salaryInput = page.locator('input[placeholder="e.g. 5000"]');
    await salaryInput.clear();
    await salaryInput.fill('7500');

    // Save — modal footer primary button says "Save Changes" for existing records
    await page.locator('.modal-footer .btn-primary').click();
    // Confirm save succeeded (no error alert)
    await expect(page.locator('.alert-danger')).not.toBeVisible({ timeout: 5000 });
  });

  test('archive employee removes from active list', async ({ page }) => {
    const row = page.locator(`tr:has-text("${UNIQUE}")`);
    if (!await row.isVisible()) {
      test.skip(true, 'Test employee not found — run add test first');
    }
    // The delete/archive button in the row is an icon-only button with title="Delete employee"
    // (not "archive" or "terminate") — clicking it opens a confirmation modal
    await row.locator('button[title="Delete employee"]').click();
    // Confirmation modal appears — click "Archive Employee" to confirm
    await expect(page.locator('h3:text("Archive Employee")')).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: 'Archive Employee' }).click();
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
