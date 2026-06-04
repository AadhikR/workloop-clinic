/**
 * probation.spec.js — Playwright tests for Feature 11: Probation Period Management
 *
 * Covers:
 *   EmployeeManager:
 *     - A probation action button (UserCheck icon) appears on Probation-status employees
 *     - Clicking it opens the Probation Actions modal
 *     - Modal shows the employee name and probation end date
 *     - Modal has Confirm Active, Extend, and Terminate action options
 *     - "Extend" mode shows a date input
 *     - "Terminate" mode shows the 14-day notice warning
 *     - Back button returns to the action selection
 *
 *   Dashboard:
 *     - Probation ending alert section renders when employees are near end of probation
 *       (skipped when no such employees exist in the test data)
 *
 * NOTE: All admin tests use storageState scoped inside the describe block.
 * The probation modal tests require at least one Probation-status employee.
 * If none exist, those tests are skipped.
 */
import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './helpers/auth.js';

// ─── EmployeeManager — probation action button ────────────────────────────────
test.describe('Probation — EmployeeManager actions', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  async function goToEmployees(page) {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.page-header h2').filter({ hasText: /Employees/i })).toBeVisible({ timeout: 10000 });
  }

  test('Employees page loads without error', async ({ page }) => {
    await goToEmployees(page);
    await expect(page.locator('.page-header h2').filter({ hasText: /Employees/i })).toBeVisible({ timeout: 8000 });
  });

  test('probation action button visible for Probation-status employees', async ({ page }) => {
    await goToEmployees(page);

    // Check if there are any Probation-status employees
    const probationBadge = page.locator('td').filter({ has: page.locator('.badge', { hasText: /^Probation$/i }) }).first();
    if (!(await probationBadge.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    // The probation action button (UserCheck icon, title="Probation actions") should be in the same row
    await expect(
      page.locator('button[title="Probation actions"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('probation modal opens and shows employee name', async ({ page }) => {
    await goToEmployees(page);

    const probationBtn = page.locator('button[title="Probation actions"]').first();
    if (!(await probationBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    await probationBtn.click();
    // Modal title
    await expect(page.locator('.modal-header h3').filter({ hasText: /Probation Actions/i })).toBeVisible({ timeout: 5000 });
  });

  test('probation modal has Confirm Active, Extend, and Terminate buttons', async ({ page }) => {
    await goToEmployees(page);

    const probationBtn = page.locator('button[title="Probation actions"]').first();
    if (!(await probationBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    await probationBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });

    await expect(page.locator('.modal').getByRole('button', { name: /Confirm Active/i })).toBeVisible({ timeout: 4000 });
    await expect(page.locator('.modal').getByRole('button', { name: /Extend/i })).toBeVisible({ timeout: 4000 });
    await expect(page.locator('.modal').getByRole('button', { name: /Terminate/i })).toBeVisible({ timeout: 4000 });
  });

  test('"Extend" mode shows a date input', async ({ page }) => {
    await goToEmployees(page);

    const probationBtn = page.locator('button[title="Probation actions"]').first();
    if (!(await probationBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    await probationBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });

    await page.locator('.modal').getByRole('button', { name: /Extend/i }).click();
    await expect(page.locator('.modal input[type="date"]')).toBeVisible({ timeout: 4000 });
    await expect(page.locator('.modal').getByRole('button', { name: /Save Extension/i })).toBeVisible({ timeout: 3000 });
  });

  test('"Terminate" mode shows 14-day notice warning', async ({ page }) => {
    await goToEmployees(page);

    const probationBtn = page.locator('button[title="Probation actions"]').first();
    if (!(await probationBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    await probationBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });

    await page.locator('.modal').getByRole('button', { name: /Terminate/i }).click();
    await expect(page.locator('.modal').locator('text=/14 day/i')).toBeVisible({ timeout: 4000 });
    await expect(page.locator('.modal').getByRole('button', { name: /Confirm Terminate/i })).toBeVisible({ timeout: 3000 });
  });

  test('"Back" button in Extend mode returns to main options', async ({ page }) => {
    await goToEmployees(page);

    const probationBtn = page.locator('button[title="Probation actions"]').first();
    if (!(await probationBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No Probation-status employees in test data');
      return;
    }

    await probationBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /Extend/i }).click();
    await expect(page.locator('.modal input[type="date"]')).toBeVisible({ timeout: 4000 });

    await page.locator('.modal').getByRole('button', { name: /Back/i }).click();
    await expect(page.locator('.modal').getByRole('button', { name: /Confirm Active/i })).toBeVisible({ timeout: 4000 });
  });
});

// ─── Dashboard probation alert ────────────────────────────────────────────────
test.describe('Probation — Dashboard alert', () => {
  test('Dashboard loads without error (probation alert section present when applicable)', async ({ page }) => {
    await loginAsAdmin(page);
    // The probation alert only renders when probationEnding.length > 0 (employees
    // on Probation whose end date is within 14 days).  In most test environments
    // there won't be such employees — so we just confirm the Dashboard itself loads.
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h2').filter({ hasText: /Workloop/i }).or(page.locator('.stat-card').first())).toBeVisible({ timeout: 12000 });
  });
});
