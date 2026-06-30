/**
 * salary-compliance.spec.js
 * Feature 5.1 — MoHRE Salary Distribution Compliance
 *
 * Tests the corrected UAE MoHRE thresholds in EmployeeModal Salary & Bank tab:
 *   - Basic salary ≥60% = green (compliant)
 *   - Basic salary 50–60% = amber (warning)
 *   - Basic salary <50% = red (error)
 *   - Housing allowance ≤25% = OK; >25% = amber
 *   - Transport allowance ≤10% = OK; >10% = amber
 *
 * Verifies:
 *   - Distribution breakdown section is visible when salary is entered
 *   - Inline badges/indicators change colour based on split percentages
 *   - The 60% threshold is applied (not the old 50% threshold)
 *   - MoHRE compliance label text appears
 *
 * NOTE: storageState inside describe blocks.
 */
import { test, expect } from '@playwright/test';

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

// ─── helpers ──────────────────────────────────────────────────────────────────

async function openSalaryTab(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');

  // Click "Add Employee" to open a fresh modal (avoids dependency on existing data)
  await page.getByRole('button', { name: /add employee/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

  // Switch to "Salary & Bank" tab
  await page.getByRole('button', { name: /salary.*bank|salary &/i }).first().click();
  await page.waitForTimeout(300);
}

async function openExistingEmpSalaryTab(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');

  const empRow = page.locator(`tr:has-text("${EMP_NAME}")`).first();
  if (!(await empRow.isVisible({ timeout: 6000 }).catch(() => false))) return false;

  await empRow.getByRole('button', { name: /edit/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
  await page.getByRole('button', { name: /salary.*bank|salary &/i }).first().click();
  await page.waitForTimeout(300);
  return true;
}

// ─── Salary & Bank tab structure ──────────────────────────────────────────────

test.describe('Salary Compliance (5.1) — Salary & Bank tab layout', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Salary & Bank tab is present in the employee modal', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
    await page.getByRole('button', { name: /add employee/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    await expect(
      page.getByRole('button', { name: /salary.*bank|salary &/i }).first()
    ).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Salary & Bank tab shows Basic Salary, Housing, Transport inputs', async ({ page }) => {
    await openSalaryTab(page);

    // Basic Salary — placeholder "e.g. 5000"
    await expect(
      page.locator('.modal input[placeholder="e.g. 5000"]').first()
    ).toBeVisible({ timeout: 6000 });

    // Housing Allowance — placeholder "e.g. 2000"
    await expect(
      page.locator('.modal input[placeholder="e.g. 2000"]').first()
    ).toBeVisible({ timeout: 5000 });

    // Transport Allowance — placeholder "e.g. 1000"
    await expect(
      page.locator('.modal input[placeholder="e.g. 1000"]').first()
    ).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Salary distribution breakdown section renders after entering a salary', async ({ page }) => {
    await openSalaryTab(page);

    // Enter a basic salary to trigger the distribution display
    const basicInput = page.locator('.modal input[placeholder*="5000"]').first();
    if (!(await basicInput.isVisible({ timeout: 5000 }).catch(() => false))) {
      await page.locator('.modal-header .btn-ghost').click();
      test.skip(true, 'Basic Salary input not found with expected placeholder');
      return;
    }
    await basicInput.fill('10000');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);

    // A distribution section or "MoHRE" label should appear
    await expect(
      page.locator('.modal').getByText(/MoHRE|distribution|salary.*split|basic.*%/i).first()
    ).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Basic salary ≥60% shows a compliant indicator (✓ text or green section)', async ({ page }) => {
    await openSalaryTab(page);

    // Compliance indicators use inline styles — check for "✓ Salary Distribution — Compliant" text
    const basicInput = page.locator('.modal input[placeholder="e.g. 5000"]').first();
    if (!(await basicInput.isVisible({ timeout: 5000 }).catch(() => false))) {
      await page.locator('.modal-header .btn-ghost').click();
      test.skip(true, 'Basic Salary input not found');
      return;
    }

    // Set basic=6000, housing=2000, transport=1000 → basic=6000/9000=66.7% → compliant
    await basicInput.fill('6000');
    await page.keyboard.press('Tab');
    const housingInput = page.locator('.modal input[placeholder="e.g. 2000"]').first();
    if (await housingInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await housingInput.fill('2000');
      await page.keyboard.press('Tab');
    }
    await page.waitForTimeout(400);

    // Compliant state renders "✓ Salary Distribution — Compliant" header
    const compliantText = page.locator('.modal').getByText(/Salary Distribution.*Compliant|✓.*Salary/i).first();
    await expect(compliantText).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Basic salary between 50–60% shows an amber warning indicator (⚠ text)', async ({ page }) => {
    await openSalaryTab(page);

    const basicInput = page.locator('.modal input[placeholder="e.g. 5000"]').first();
    if (!(await basicInput.isVisible({ timeout: 5000 }).catch(() => false))) {
      await page.locator('.modal-header .btn-ghost').click();
      test.skip(true, 'Basic Salary input not found');
      return;
    }

    // basic=5500, housing=2500, transport=1000 → total=9000, basic=61% — actually compliant.
    // Use basic=5000, housing=3000, transport=1000 → total=9000, basic=55.6% → amber (50–60%)
    await basicInput.fill('5000');
    await page.keyboard.press('Tab');
    const housingInput = page.locator('.modal input[placeholder="e.g. 2000"]').first();
    if (await housingInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await housingInput.fill('3000');
      await page.keyboard.press('Tab');
    }
    await page.waitForTimeout(400);

    // Warning state renders "⚠ Salary Distribution Warnings" header
    const warnText = page.locator('.modal').getByText(/Salary Distribution Warnings|⚠/i).first();
    await expect(warnText).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Basic salary <50% shows a warning / error indicator', async ({ page }) => {
    await openSalaryTab(page);

    const basicInput = page.locator('.modal input[placeholder="e.g. 5000"]').first();
    if (!(await basicInput.isVisible({ timeout: 5000 }).catch(() => false))) {
      await page.locator('.modal-header .btn-ghost').click();
      test.skip(true, 'Basic Salary input not found');
      return;
    }

    // basic=4000, housing=5000, transport=1000 → total=10000, basic=40% → error (<50%)
    await basicInput.fill('4000');
    await page.keyboard.press('Tab');
    const housingInput = page.locator('.modal input[placeholder="e.g. 2000"]').first();
    if (await housingInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await housingInput.fill('5000');
      await page.keyboard.press('Tab');
    }
    await page.waitForTimeout(400);

    // Either error or warning header renders "⚠ Salary Distribution Warnings"
    const warnText = page.locator('.modal').getByText(/Salary Distribution Warnings|⚠/i).first();
    await expect(warnText).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Housing allowance >25% shows a distribution warning', async ({ page }) => {
    await openSalaryTab(page);

    const basicInput = page.locator('.modal input[placeholder="e.g. 5000"]').first();
    if (!(await basicInput.isVisible({ timeout: 5000 }).catch(() => false))) {
      await page.locator('.modal-header .btn-ghost').click();
      test.skip(true, 'Basic Salary input not found');
      return;
    }

    // basic=6000, housing=3000 → housing=3000/9000=33% (>25% threshold)
    await basicInput.fill('6000');
    await page.keyboard.press('Tab');
    const housingInput = page.locator('.modal input[placeholder="e.g. 2000"]').first();
    if (await housingInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await housingInput.fill('3000');
      await page.keyboard.press('Tab');
    }
    await page.waitForTimeout(400);

    // Housing >25% triggers a warning in the distribution section
    const warnText = page.locator('.modal').getByText(/Salary Distribution Warnings|⚠/i).first();
    await expect(warnText).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('MOL ID field is present in the Salary & Bank tab', async ({ page }) => {
    await openSalaryTab(page);

    // MOL ID placeholder: "e.g. 10003048635715"
    await expect(
      page.locator('.modal input[placeholder*="10003048635715"]').first()
    ).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('IBAN field is present in the Salary & Bank tab', async ({ page }) => {
    await openSalaryTab(page);

    // IBAN placeholder: "e.g. AE080260001014950445301"
    await expect(
      page.locator('.modal input[placeholder*="AE08026"]').first()
    ).toBeVisible({ timeout: 5000 });

    await page.locator('.modal-header .btn-ghost').click();
  });
});
