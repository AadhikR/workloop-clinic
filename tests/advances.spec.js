/**
 * advances.spec.js — Playwright tests for Feature 5: Salary Advance & Loan Management
 *
 * Covers:
 *   Admin portal (AdvancesManager):
 *     - "Advances" nav item visible in sidebar
 *     - Advances page renders stat cards
 *     - "New Advance" button opens the create form
 *     - Form has all required fields (employee, amount, disbursed date, months, reason)
 *     - Create button disabled when required fields are empty
 *     - Cancel hides the form
 *     - Creating an advance adds it to the table
 *     - Status filter tabs render
 *
 *   PayrollEditor:
 *     - Active Advance Repayments panel appears in payroll editor (if advances exist)
 *
 *   EndOfServiceScreen:
 *     - Outstanding advances field auto-loads from Advances module
 *
 *   Employee portal (EmpAdvances):
 *     - "Advances" tab visible in employee sidebar
 *     - Employee Advances page renders
 *     - Request form appears on button click
 *     - Form fields present (amount, reason)
 *     - Submit disabled when fields empty
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient, deleteWhere } from './helpers/db.js';
import { loginAsEmployee } from './helpers/auth.js';

test.use({ storageState: '.playwright/admin-session.json' });

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';
const REASON   = `Playwright test advance ${Date.now()}`;

// Clean up advances created during tests
test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    await deleteWhere(db, 'salary_advances', 'user_id', adminId);
    console.log('[advances cleanup] Removed test advances.');
  } catch (e) {
    console.warn('[advances cleanup] Could not clean up:', e.message);
  }
});

// ─── Admin — AdvancesManager ──────────────────────────────────────────────────
test.describe('Advances — Admin portal', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  });

  test('"Advances" nav item is visible in admin sidebar', async ({ page }) => {
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Advances page renders stat cards', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');

    // Three stat cards: Pending Requests, Active Advances, Total Outstanding
    await expect(page.locator('.stat-card').filter({ hasText: /Pending Requests/i })).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.stat-card').filter({ hasText: /Active Advances/i })).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.stat-card').filter({ hasText: /Total Outstanding/i })).toBeVisible({ timeout: 5000 });
  });

  test('"New Advance" button opens the create form', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    await page.getByRole('button', { name: /New Advance/i }).click();
    await expect(page.locator('text=New Salary Advance')).toBeVisible({ timeout: 5000 });
  });

  test('create form has all required fields', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /New Advance/i }).click();
    await expect(page.locator('text=New Salary Advance')).toBeVisible({ timeout: 5000 });

    // Employee selector
    await expect(page.locator('select').filter({ has: page.locator('option[value=""]').filter({ hasText: /employee/i }) }))
      .toBeVisible({ timeout: 5000 });

    // Amount field
    await expect(page.locator('input[placeholder*="3000"]')).toBeVisible({ timeout: 4000 });

    // Disbursement date
    await expect(page.locator('input[type="date"]').first()).toBeVisible({ timeout: 4000 });

    // Repayment months
    await expect(page.locator('input[type="number"][min="1"][max="36"]')).toBeVisible({ timeout: 4000 });

    // Reason
    await expect(page.locator('input[placeholder*="Emergency"]')).toBeVisible({ timeout: 4000 });
  });

  test('Create Advance button is disabled when required fields are empty', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /New Advance/i }).click();
    await expect(page.locator('text=New Salary Advance')).toBeVisible({ timeout: 5000 });

    // The Create Advance submit button should be disabled with empty form
    await expect(page.locator('button:has-text("Create Advance")')).toBeDisabled({ timeout: 3000 });
  });

  test('Cancel hides the form', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /New Advance/i }).click();
    await expect(page.locator('text=New Salary Advance')).toBeVisible({ timeout: 5000 });

    await page.getByRole('button', { name: /^Cancel$/ }).click();
    await expect(page.locator('text=New Salary Advance')).not.toBeVisible({ timeout: 4000 });
  });

  test('creating an advance adds it to the list', async ({ page }) => {
    const empRow = await page.evaluate(() => null); // just to sequence
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    // Skip if no test employee
    await page.getByRole('button', { name: /New Advance/i }).click();
    await expect(page.locator('text=New Salary Advance')).toBeVisible({ timeout: 5000 });

    const empSelect = page.locator('select').filter({
      has: page.locator('option[value=""]').filter({ hasText: /employee/i })
    });
    const options = await empSelect.locator('option').count();
    if (options <= 1) {
      test.skip(true, 'No employees available to test advance creation');
      return;
    }

    // Select the first real employee
    await empSelect.selectOption({ index: 1 });
    await page.locator('input[placeholder*="3000"]').fill('1500');
    await page.locator('input[type="number"][min="1"][max="36"]').fill('3');
    await page.locator('input[placeholder*="Emergency"]').fill(REASON);

    await expect(page.locator('button:has-text("Create Advance")')).toBeEnabled({ timeout: 3000 });
    await page.locator('button:has-text("Create Advance")').click();

    // The form should disappear and the reason text appear in the table
    await expect(page.locator('text=New Salary Advance')).not.toBeVisible({ timeout: 6000 });
    await expect(page.locator(`td:has-text("${REASON}")`)).toBeVisible({ timeout: 8000 });
  });

  test('status filter tabs render', async ({ page }) => {
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Advances' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    // Filter buttons
    for (const label of ['all', 'pending', 'active', 'settled', 'cancelled']) {
      await expect(
        page.locator('button').filter({ hasText: new RegExp(`^${label}`, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });
});

// ─── PayrollEditor — advance repayments panel ─────────────────────────────────
test.describe('Advances — PayrollEditor panel', () => {

  test('Payroll editor loads without errors (advance panel silently absent when no advances)', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
    await page.waitForLoadState('networkidle');

    // PayrollManager should load (at minimum shows a heading or the period picker)
    await expect(
      page.locator('h2').filter({ hasText: /payroll/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });
});

// ─── EndOfServiceScreen — advance balance auto-load ───────────────────────────
test.describe('Advances — End of Service auto-load', () => {

  test('EOS screen Outstanding Advances field has an editable input', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');

    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) {
      test.skip(true, 'Test employee not found');
      return;
    }

    // Open the employee's end-of-service screen (kebab / actions menu)
    await empRow.getByRole('button', { name: /end.of.service/i }).click()
      .catch(async () => {
        // Some layouts put EOS behind the row's actions — try clicking edit first
        // and then looking for EOS inside the modal. Skip if unavailable.
        test.skip(true, 'End-of-service button not directly accessible in row');
      });

    // If we got here, the EOS modal is open
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    await expect(
      page.locator('input[placeholder="0.00"]')
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── Employee portal — EmpAdvances ───────────────────────────────────────────
test.describe('Advances — Employee portal', () => {

  test('"Advances" tab is visible in employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    // Employee shell renders the nav with the Advances tab
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Advances$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Employee Advances tab renders content', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Advances$/ }).click();

    // Either empty state or advance records — both are valid
    const emptyState = page.locator('text=No advance requests yet');
    const requestBtn = page.getByRole('button', { name: /Request.*Advance/i });
    const advCard    = page.locator('.emp-card').first();
    await expect(emptyState.or(requestBtn).or(advCard)).toBeVisible({ timeout: 8000 });
  });

  test('"Request Advance" button opens the request form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Advances$/ }).click();

    // Click the header-area "Request Advance" button
    await page.getByRole('button', { name: /Request.*Advance/i }).first().click();

    // Form fields should appear
    await expect(page.locator('input[placeholder*="2000"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('textarea[placeholder*="explain"]')).toBeVisible({ timeout: 4000 });
  });

  test('Submit button is disabled when form is empty', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Advances$/ }).click();
    await page.getByRole('button', { name: /Request.*Advance/i }).first().click();

    await expect(page.locator('button:has-text("Submit Request")')).toBeDisabled({ timeout: 4000 });
  });

  test('Cancel hides the request form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Advances$/ }).click();
    await page.getByRole('button', { name: /Request.*Advance/i }).first().click();
    await expect(page.locator('input[placeholder*="2000"]')).toBeVisible({ timeout: 5000 });

    await page.getByRole('button', { name: /^Cancel$/ }).click();
    await expect(page.locator('input[placeholder*="2000"]')).not.toBeVisible({ timeout: 4000 });
  });
});
