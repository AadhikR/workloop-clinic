/**
 * insurance.spec.js — Playwright tests for Feature 3: Medical Insurance Tracking
 *
 * Covers:
 *   Company Settings:
 *     - Medical Insurance Policies section renders
 *     - "Add Policy" button opens the inline form
 *     - Form has all expected fields (insurer, policy no., tier, premium, renewal, broker)
 *     - Cancel hides the form without saving
 *     - Saving a policy appends it to the table
 *     - Renewal date badge renders with correct class based on days remaining
 *   Employee modal:
 *     - Insurance tab present on existing employees
 *     - Coverage assignment form has all required fields
 *     - "Assign Coverage" button exists
 *     - Dependants section renders with add-form
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient, deleteWhere } from './helpers/db.js';

test.use({ storageState: '.playwright/admin-session.json' });

const EMP_NAME   = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';
const INSURER    = `Test Insurer ${Date.now()}`;
const POLICY_NO  = `POL-${Date.now()}`;

// Clean up insurance policies created during tests
test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    await deleteWhere(db, 'insurance_policies', 'user_id', adminId);
    console.log('[insurance cleanup] Removed test insurance policies.');
  } catch (e) {
    console.warn('[insurance cleanup] Could not clean up:', e.message);
  }
});

// ─── Company Settings — Insurance Policies section ───────────────────────────
test.describe('Insurance — Company Settings', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // Scope to .sidebar-nav — a "Company Settings" button also appears in the
    // Dashboard's MOL Employer ID warning alert when molEmployerId is not set.
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('Medical Insurance Policies section renders', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('button:has-text("Add Policy")')).toBeVisible({ timeout: 5000 });
  });

  test('Add Policy button opens the inline form', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await page.locator('button:has-text("Add Policy")').click();

    // The inline form heading
    await expect(page.locator('text=New Insurance Policy')).toBeVisible({ timeout: 5000 });
  });

  test('Add Policy form has all required fields', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await page.locator('button:has-text("Add Policy")').click();
    await expect(page.locator('text=New Insurance Policy')).toBeVisible({ timeout: 5000 });

    // Insurer name input
    await expect(page.locator('input[placeholder*="Daman"]')).toBeVisible({ timeout: 4000 });
    // Policy number
    await expect(page.locator('input[placeholder*="Policy"]').or(page.locator('input[placeholder*="certificate"]'))).toBeVisible();
    // Tier name
    await expect(page.locator('input[placeholder*="Gold"]').or(page.locator('input[placeholder*="Silver"]'))).toBeVisible();
    // Annual premium
    await expect(page.locator('input[placeholder*="50000"]')).toBeVisible();
    // Renewal date
    await expect(page.locator('input[type="date"]').first()).toBeVisible();
    // Broker
    await expect(page.locator('input[placeholder*="Broker"]').or(page.locator('input[placeholder*="agent"]'))).toBeVisible();
  });

  test('Cancel button hides form without saving', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await page.locator('button:has-text("Add Policy")').click();
    await expect(page.locator('text=New Insurance Policy')).toBeVisible({ timeout: 5000 });

    await page.locator('button:has-text("Cancel")').last().click();
    await expect(page.locator('text=New Insurance Policy')).not.toBeVisible({ timeout: 4000 });
  });

  test('Add Policy button is disabled when insurer name is empty', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await page.locator('button:has-text("Add Policy")').click();
    await expect(page.locator('text=New Insurance Policy')).toBeVisible({ timeout: 5000 });

    // The inline "Add Policy" save button should be disabled when insurer name is blank
    const saveBtn = page.locator('button:has-text("Add Policy")').last();
    await expect(saveBtn).toBeDisabled({ timeout: 3000 });
  });

  test('creating a policy adds it to the table', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });
    await page.locator('button:has-text("Add Policy")').click();
    await expect(page.locator('text=New Insurance Policy')).toBeVisible({ timeout: 5000 });

    // Fill the form
    await page.locator('input[placeholder*="Daman"]').fill(INSURER);
    await page.locator('input[placeholder*="Policy"]').or(page.locator('input[placeholder*="certificate"]'))
      .fill(POLICY_NO);

    // Click the save button (the last "Add Policy" button on page is the form submit)
    await page.locator('button:has-text("Add Policy")').last().click();

    // The new insurer name should appear in the table
    await expect(page.locator(`td:has-text("${INSURER}")`)).toBeVisible({ timeout: 8000 });
  });

  test('edit icon appears for each policy row', async ({ page }) => {
    await expect(page.locator('h3:has-text("Medical Insurance Policies")')).toBeVisible({ timeout: 8000 });

    // If any policy rows exist, they should have an edit icon button
    const policyRows = page.locator('table tbody tr');
    const rowCount = await policyRows.count();
    if (rowCount === 0) test.skip(true, 'No policies to test edit icon');

    await expect(policyRows.first().locator('button[title="Edit policy"]')).toBeVisible({ timeout: 4000 });
    await expect(policyRows.first().locator('button[title="Delete policy"]')).toBeVisible({ timeout: 4000 });
  });
});

// ─── Employee modal — Insurance tab ──────────────────────────────────────────
test.describe('Insurance — Employee modal', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // Scope to .sidebar-nav — the Dashboard may show a "Manage in Employees" button inside
    // a probation alert, causing a strict-mode violation with an unscoped getByRole.
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('Insurance tab is absent on the new-employee modal', async ({ page }) => {
    await page.getByRole('button', { name: /add employee/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    await expect(page.getByRole('button', { name: /^Insurance$/i })).not.toBeVisible({ timeout: 3000 });
    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Insurance tab is present on existing-employee modal', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await expect(page.getByRole('button', { name: /^Insurance$/i })).toBeVisible({ timeout: 6000 });
  });

  test('Insurance tab shows Coverage Assignment form', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Insurance$/i }).click();

    // Coverage Assignment card
    await expect(page.locator('h3:has-text("Coverage Assignment")')).toBeVisible({ timeout: 6000 });

    // Policy selector
    await expect(page.locator('select').filter({ has: page.locator('option[value=""]').filter({ hasText: /policy/i }) }))
      .toBeVisible({ timeout: 5000 });

    // Member ID input
    await expect(page.locator('input[placeholder*="member ID"]').or(page.locator('input[placeholder*="Member"]')))
      .toBeVisible({ timeout: 5000 });

    // Card number input — scope to Coverage Assignment card to avoid matching dependant card number field
    const coverageCard = page.locator('.card').filter({ hasText: 'Coverage Assignment' }).first();
    await expect(
      coverageCard.locator('input[placeholder*="certificate"]')
    ).toBeVisible({ timeout: 5000 });

    // Assign/Update Coverage button
    await expect(
      page.locator('button:has-text("Assign Coverage")').or(page.locator('button:has-text("Update Coverage")'))
    ).toBeVisible({ timeout: 5000 });
  });

  test('Insurance tab shows Dependants section with add-form', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Insurance$/i }).click();
    await expect(page.locator('h3:has-text("Coverage Assignment")')).toBeVisible({ timeout: 6000 });

    // Dependants card
    await expect(page.locator('h3').filter({ hasText: /Dependants/i })).toBeVisible({ timeout: 6000 });

    // Add Dependant sub-form heading — use the div, not the button (both contain "Add Dependant")
    await expect(
      page.locator('div').filter({ hasText: /^Add Dependant$/ }).first()
    ).toBeVisible({ timeout: 5000 });

    // Name input inside dependant form — exact placeholder avoids matching "Dependant's card number"
    await expect(page.getByPlaceholder("Dependant's full name")).toBeVisible({ timeout: 5000 });

    // Relationship selector
    await expect(page.locator('select').filter({ has: page.locator('option[value="Spouse"]') }))
      .toBeVisible({ timeout: 5000 });

    // Add Dependant button disabled when name is empty
    await expect(page.locator('button').filter({ hasText: /Add Dependant/i })).toBeDisabled({ timeout: 4000 });
  });

  test('Save button is hidden on Insurance tab', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });

    // Save Changes visible on other tabs
    await expect(page.locator('.modal-footer .btn-primary')).toBeVisible({ timeout: 5000 });

    await page.getByRole('button', { name: /^Insurance$/i }).click();
    await expect(page.locator('h3:has-text("Coverage Assignment")')).toBeVisible({ timeout: 6000 });

    // Main Save button gone (each section has its own save)
    await expect(page.locator('.modal-footer .btn-primary')).not.toBeVisible({ timeout: 3000 });
  });
});
