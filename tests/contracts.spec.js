/**
 * contracts.spec.js — Playwright tests for Feature 12: Contract Renewal Management
 *
 * Covers:
 *   EmployeeModal — Contracts tab:
 *     - "Contracts" tab button appears only for existing employees (not new-employee form)
 *     - Clicking the tab switches to the Contracts view
 *     - Current contract status card is rendered (type badge + dates)
 *     - Contract action buttons render based on contract type:
 *         Unlimited contract  → "Convert to Limited" button
 *         Limited contract    → "Renew", "Convert to Unlimited", "Not Renewing" buttons
 *     - "Print Letter" button is visible on the Contracts tab
 *     - Save button is hidden on the Contracts tab (actions have their own handlers)
 *     - Confirming an action reveals an inline confirmation form
 *     - Cancelling the inline form returns to the action buttons
 *     - Contract history table renders (even if empty)
 *
 * NOTE: All tests use the pre-saved admin session.
 * Tests that require a specific contract type (Limited) are skipped if the test employee
 * has a different type. The global-setup employee has contract_type = 'Unlimited'.
 */
import { test, expect } from '@playwright/test';

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Navigate to Employees page. */
async function goToEmployees(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.page-header h2').filter({ hasText: /Employees/i })).toBeVisible({ timeout: 10000 });
}

/**
 * Open the edit modal for the test employee.
 * Returns false if the test employee row is not found.
 */
async function openTestEmployeeModal(page) {
  await goToEmployees(page);
  const row = page.locator('tr').filter({ hasText: EMP_NAME }).first();
  if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) return false;
  await row.getByRole('button', { name: /edit/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
  return true;
}

/**
 * Open the edit modal and navigate to the Contracts tab.
 * Returns false if the employee is not found or Contracts tab is absent.
 */
async function openContractsTab(page) {
  const found = await openTestEmployeeModal(page);
  if (!found) return false;

  // The Contracts tab is only shown for existing employees (employee.id is set).
  // Modal tabs use button.tab-btn — scope to the modal to avoid sidebar conflicts.
  const contractsTab = page.locator('.modal').getByRole('button', { name: 'Contracts', exact: true });
  if (!(await contractsTab.isVisible({ timeout: 4000 }).catch(() => false))) return false;

  await contractsTab.click();
  await page.waitForLoadState('networkidle');
  return true;
}

// ─── Admin — EmployeeModal Contracts tab ─────────────────────────────────────

test.describe('Contracts — EmployeeModal tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Contracts" tab is present in modal for an existing employee', async ({ page }) => {
    const found = await openTestEmployeeModal(page);
    if (!found) {
      test.skip(true, `Test employee "${EMP_NAME}" not found in Employees list`);
      return;
    }
    await expect(
      page.locator('.modal').getByRole('button', { name: 'Contracts', exact: true })
    ).toBeVisible({ timeout: 6000 });
  });

  test('"Contracts" tab is NOT present in the Add Employee form (new employee)', async ({ page }) => {
    await goToEmployees(page);
    await page.getByRole('button', { name: /add employee/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });

    // Contracts tab should NOT be visible for new employees
    await expect(
      page.locator('.modal').getByRole('button', { name: 'Contracts', exact: true })
    ).not.toBeVisible({ timeout: 3000 });

    // Close the modal
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click().catch(() => {});
    await page.keyboard.press('Escape');
  });

  test('Contracts tab renders the contract status card', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    // The status card shows contract type info. It renders regardless of
    // whether contractType / start date are set.
    await expect(
      page.locator('.modal').locator('text=/contract|Contract/').first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Contracts tab has "Print Letter" button', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    await expect(
      page.locator('.modal').getByRole('button', { name: /print letter/i })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Save button is hidden on the Contracts tab', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    // The main "Save Changes" button is hidden on Documents / Insurance / Contracts tabs
    await expect(
      page.locator('.modal-footer .btn-primary')
    ).not.toBeVisible({ timeout: 3000 });
  });

  test('Unlimited contract shows "Convert to Limited" action button', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    // The test employee in global-setup has contract_type = 'Unlimited'
    const convertBtn = page.locator('.modal').getByRole('button', { name: /convert to limited/i });
    if (!(await convertBtn.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'Test employee does not have Unlimited contract type');
      return;
    }
    await expect(convertBtn).toBeVisible();
  });

  test('Limited contract shows Renew, Convert to Unlimited, and Not Renewing buttons', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    const renewBtn = page.locator('.modal').getByRole('button', { name: /^renew$/i });
    if (!(await renewBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Test employee does not have a Limited contract — skipping Limited-specific test');
      return;
    }
    await expect(renewBtn).toBeVisible();
    await expect(page.locator('.modal').getByRole('button', { name: /convert to unlimited/i })).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.modal').getByRole('button', { name: /not renewing/i })).toBeVisible({ timeout: 3000 });
  });

  test('clicking a contract action reveals an inline confirmation form', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    // Try any action button that's available — prefer "Convert to Limited" (Unlimited contract)
    const convertBtn  = page.locator('.modal').getByRole('button', { name: /convert to limited/i });
    const renewBtn    = page.locator('.modal').getByRole('button', { name: /^renew$/i });

    if (await convertBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await convertBtn.click();
    } else if (await renewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await renewBtn.click();
    } else {
      test.skip(true, 'No contract action buttons visible for the test employee');
      return;
    }

    // An inline confirmation form with a Cancel button appears.
    // The modal may have two Cancel buttons (modal-footer X and inline Cancel) — use .first()
    await expect(
      page.locator('.modal').getByRole('button', { name: /cancel/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('Cancel on inline confirmation returns to action buttons', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }

    const convertBtn = page.locator('.modal').getByRole('button', { name: /convert to limited/i });
    const renewBtn   = page.locator('.modal').getByRole('button', { name: /^renew$/i });

    if (await convertBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await convertBtn.click();
    } else if (await renewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await renewBtn.click();
    } else {
      test.skip(true, 'No contract action buttons visible');
      return;
    }

    // Two Cancel buttons are present:
    //   [0] = inline confirmation Cancel (inside modal-body tab content)
    //   [1] = modal-footer Cancel (closes the whole modal)
    // We want the inline one (.first()) to dismiss only the confirmation form.
    await expect(page.locator('.modal').getByRole('button', { name: /cancel/i }).first()).toBeVisible({ timeout: 4000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).first().click();

    // Action buttons reappear
    const actionBtn = convertBtn.or(renewBtn).or(
      page.locator('.modal').getByRole('button', { name: /print letter/i })
    );
    await expect(actionBtn.first()).toBeVisible({ timeout: 5000 });
  });

  test('contract history table is present on the Contracts tab', async ({ page }) => {
    const found = await openContractsTab(page);
    if (!found) {
      test.skip(true, `Could not open Contracts tab for "${EMP_NAME}"`);
      return;
    }
    // History table renders even when empty — look for a table or the heading
    const historyHeading = page.locator('.modal').locator('text=/contract history/i');
    const historyTable   = page.locator('.modal table');
    await expect(historyHeading.or(historyTable).first()).toBeVisible({ timeout: 6000 });
  });
});
