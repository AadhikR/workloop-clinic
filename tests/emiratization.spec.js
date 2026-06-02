/**
 * emiratization.spec.js — Playwright tests for Feature 1: Emiratization / Nafis Compliance
 *
 * Covers:
 *   - Company Settings: sector selector + quota % field exist and are editable
 *   - Sector auto-fill: selecting an industry pre-fills the required quota %
 *   - Dashboard: Emiratization compliance panel renders
 *   - Employee modal UAE Compliance tab: UAE National badge appears when nationality = UAE
 *   - Employee modal UAE Compliance tab: Nafis field enabled only for UAE nationals
 */
import { test, expect } from '@playwright/test';

test.use({ storageState: '.playwright/admin-session.json' });

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

// ─── Company Settings ─────────────────────────────────────────────────────────
test.describe('Emiratization — Company Settings', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // Scope to .sidebar-nav — a "Company Settings" button also appears in the
    // Dashboard's MOL Employer ID warning alert when molEmployerId is not set.
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('Emiratization card renders sector selector and quota input', async ({ page }) => {
    // The Emiratization section has a heading and two form fields
    await expect(page.locator('text=Emiratization / Nafis Compliance').first()).toBeVisible({ timeout: 8000 });

    // Sector dropdown exists
    const sectorSelect = page.locator('select').filter({ hasNearby: page.locator('text=Industry Sector') });
    // Fallback: find by placeholder option text
    await expect(
      page.locator('select option[value=""]').filter({ hasText: /sector/i }).first()
    ).toBeAttached({ timeout: 6000 });

    // Required % input exists — identified by its unique placeholder "e.g. 4"
    await expect(page.locator('input[placeholder="e.g. 4"]')).toBeAttached({ timeout: 6000 });
  });

  test('selecting Banking sector auto-fills quota to 8%', async ({ page }) => {
    await expect(page.locator('text=Emiratization / Nafis Compliance').first()).toBeVisible({ timeout: 8000 });

    // Find the sector <select> — it has an "Other" option and "Banking & Financial Services"
    const sectorSelect = page.locator('select').filter({ has: page.locator('option[value="Banking & Financial Services"]') });
    await expect(sectorSelect).toBeVisible({ timeout: 6000 });
    await sectorSelect.selectOption('Banking & Financial Services');

    // The quota % input should now read 8
    // It's labelled "Required Emiratization Rate (%)"
    const quotaInput = page.locator('input[type="number"][min="0"][max="100"]');
    await expect(quotaInput).toHaveValue('8', { timeout: 4000 });
  });

  test('selecting Construction sector auto-fills quota to 2%', async ({ page }) => {
    await expect(page.locator('text=Emiratization / Nafis Compliance').first()).toBeVisible({ timeout: 8000 });
    const sectorSelect = page.locator('select').filter({ has: page.locator('option[value="Construction"]') });
    await expect(sectorSelect).toBeVisible({ timeout: 6000 });
    await sectorSelect.selectOption('Construction');
    const quotaInput = page.locator('input[type="number"][min="0"][max="100"]');
    await expect(quotaInput).toHaveValue('2', { timeout: 4000 });
  });

  test('quota % is editable after sector auto-fill', async ({ page }) => {
    await expect(page.locator('text=Emiratization / Nafis Compliance').first()).toBeVisible({ timeout: 8000 });
    const sectorSelect = page.locator('select').filter({ has: page.locator('option[value="Retail & Trade"]') });
    await expect(sectorSelect).toBeVisible({ timeout: 6000 });
    await sectorSelect.selectOption('Retail & Trade');

    const quotaInput = page.locator('input[type="number"][min="0"][max="100"]');
    await quotaInput.fill('6');
    await expect(quotaInput).toHaveValue('6');
  });

  test('saving sector does not show an error', async ({ page }) => {
    await expect(page.locator('text=Emiratization / Nafis Compliance').first()).toBeVisible({ timeout: 8000 });
    const sectorSelect = page.locator('select').filter({ has: page.locator('option[value="Retail & Trade"]') });
    if (!await sectorSelect.isVisible({ timeout: 3000 })) test.skip(true, 'Sector select not found');

    await sectorSelect.selectOption('Other');
    await page.locator('button:has-text("Save Settings")').click();
    // No error alert should appear
    await expect(page.locator('.alert-danger')).not.toBeVisible({ timeout: 6000 });
  });
});

// ─── Dashboard Emiratization panel ───────────────────────────────────────────
test.describe('Emiratization — Dashboard panel', () => {

  test('Dashboard renders Emiratization / Nafis panel', async ({ page }) => {
    await page.goto('/');
    // Wait for dashboard to fully load (stat cards indicate data has loaded)
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 15000 });

    // The panel heading
    await expect(
      page.locator('text=Emiratization / Nafis Compliance').first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Dashboard Emiratization panel shows current rate or setup prompt', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 15000 });

    // Either a "View Report" button (when sector configured) or a "Set your sector" prompt.
    // Two "View Report" buttons can exist (panel header + non-compliance alert) — .first() handles both.
    const viewReport   = page.getByRole('button', { name: /view report/i }).first();
    const sectorPrompt = page.locator('text=/set your sector/i');
    await expect(viewReport.or(sectorPrompt)).toBeVisible({ timeout: 8000 });
  });
});

// ─── Employee modal — UAE Compliance tab ─────────────────────────────────────
test.describe('Emiratization — Employee modal', () => {

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('UAE Compliance tab has nationality selector', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found in list');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });

    // Click UAE Compliance tab
    await page.getByRole('button', { name: /UAE Compliance/i }).click();
    await expect(page.locator('select').filter({ has: page.locator('option[value="United Arab Emirates"]') }))
      .toBeVisible({ timeout: 6000 });
  });

  test('Nafis registration field is disabled for non-UAE nationality', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /UAE Compliance/i }).click();

    // Set nationality to something other than UAE
    const natSelect = page.locator('select').filter({ has: page.locator('option[value="United Arab Emirates"]') });
    await natSelect.selectOption('India');

    // Nafis field should be disabled — it has placeholder "e.g. NFS-2024-XXXXXXX"
    await expect(page.locator('input[placeholder*="NFS"]')).toBeDisabled({ timeout: 4000 });
  });

  test('Nafis registration field is enabled when nationality is UAE', async ({ page }) => {
    const empRow = page.locator(`tr:has-text("${EMP_NAME}")`);
    if (!await empRow.isVisible({ timeout: 6000 })) test.skip(true, 'Test employee not found');

    await empRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.getByRole('button', { name: /UAE Compliance/i }).click();

    // Set nationality to UAE
    const natSelect = page.locator('select').filter({ has: page.locator('option[value="United Arab Emirates"]') });
    await natSelect.selectOption('United Arab Emirates');

    // UAE National badge appears — match the full badge text to avoid matching the Nafis label
    await expect(
      page.getByText('UAE National — counts toward Emiratization quota')
    ).toBeVisible({ timeout: 4000 });

    // Nafis field becomes enabled
    await expect(page.locator('input[placeholder*="NFS"]')).toBeEnabled({ timeout: 4000 });
  });
});
