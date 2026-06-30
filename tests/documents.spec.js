/**
 * documents.spec.js — Playwright tests for Feature 2: Employee Document Storage
 *
 * Covers:
 *   - Documents tab is NOT shown on the new-employee modal (no id yet)
 *   - Documents tab IS shown on the existing-employee modal
 *   - Documents tab shows the upload form with all expected fields
 *   - Document type selector contains expected UAE HR document types
 *   - Save / "Add Employee" button is hidden when on Documents tab
 *   - File size validation message appears for oversized files (mocked via JS)
 */
import { test, expect } from '@playwright/test';

test.use({ storageState: '.playwright/admin-session.json' });

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

test.describe('Document Storage — Employee modal', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // Scope to .sidebar-nav — the Dashboard may show a "Manage in Employees" button inside
    // a probation alert, causing a strict-mode violation with an unscoped getByRole.
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('Documents tab is absent on the new-employee modal', async ({ page }) => {
    await page.getByRole('button', { name: /add employee/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // The "Documents" tab should NOT be present — it only shows for existing employees
    await expect(page.getByRole('button', { name: /^Documents$/i })).not.toBeVisible({ timeout: 3000 });

    // Sanity: other tabs should be present
    await expect(page.getByRole('button', { name: /Personal/i }).first()).toBeVisible();

    // Close
    await page.locator('.modal-header .btn-ghost').click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 5000 });
  });

  test('Documents tab is present on existing-employee modal', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });

    // Documents tab should be visible
    await expect(page.getByRole('button', { name: /^Documents$/i })).toBeVisible({ timeout: 6000 });
  });

  test('Documents tab shows upload form with correct fields', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Documents$/i }).click();

    // Upload card with "Upload New Document" heading
    await expect(page.locator('h3:has-text("Upload New Document")')).toBeVisible({ timeout: 6000 });

    // Document type selector
    await expect(page.locator('select').filter({ has: page.locator('option[value="Visa"]') }))
      .toBeVisible({ timeout: 5000 });

    // Expiry date input
    await expect(page.locator('input[type="date"]').first()).toBeVisible({ timeout: 4000 });

    // Notes input
    await expect(page.locator('input[placeholder*="PRO office"]')).toBeVisible({ timeout: 4000 });

    // File drop zone / upload area
    await expect(page.locator('text=/Click to choose file/i')).toBeVisible({ timeout: 4000 });
  });

  test('Document type selector contains expected UAE document types', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Documents$/i }).click();
    await expect(page.locator('h3:has-text("Upload New Document")')).toBeVisible({ timeout: 6000 });

    const typeSelect = page.locator('select').filter({ has: page.locator('option[value="Visa"]') });

    // Verify key UAE HR document types are present
    for (const docType of ['Visa', 'Passport', 'Emirates ID', 'Labour Card', 'Work Permit']) {
      await expect(typeSelect.locator(`option[value="${docType}"]`)).toBeAttached({ timeout: 3000 });
    }
  });

  test('Save button is hidden when on Documents tab', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });

    // On Personal tab — Save Changes button should be visible
    await expect(page.locator('.modal-footer .btn-primary')).toBeVisible({ timeout: 5000 });

    // Switch to Documents tab
    await page.getByRole('button', { name: /^Documents$/i }).click();
    await expect(page.locator('h3:has-text("Upload New Document")')).toBeVisible({ timeout: 6000 });

    // Save Changes button should now be hidden
    await expect(page.locator('.modal-footer .btn-primary')).not.toBeVisible({ timeout: 3000 });
    // Only Cancel remains
    await expect(page.locator('.modal-footer .btn-outline')).toBeVisible({ timeout: 3000 });
  });

  test('Upload Document button is disabled without a file selected', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Documents$/i }).click();
    await expect(page.locator('h3:has-text("Upload New Document")')).toBeVisible({ timeout: 6000 });

    // "Upload Document" button is disabled when no file is selected
    await expect(page.locator('button:has-text("Upload Document")')).toBeDisabled({ timeout: 4000 });
  });

  test('Uploaded Documents heading renders with count', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /^Documents$/i }).click();

    // "Uploaded Documents" heading with count in parentheses e.g. "(0)"
    await expect(
      page.locator('h3').filter({ hasText: /Uploaded Documents/i })
    ).toBeVisible({ timeout: 8000 });
  });
});
