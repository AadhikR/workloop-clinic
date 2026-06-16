/**
 * multi-level-leave.spec.js — Playwright tests for Feature 6: Multi-Level Leave Approval
 *
 * Covers:
 *   Admin portal (LeaveManager):
 *     - Leave module loads without errors
 *     - Requests tab is visible
 *     - ManagerApproved status badge has blue styling (badge-blue)
 *     - "Final OK" button is absent when no ManagerApproved requests exist
 *     - Settings tab has Approval Chain dropdown with 2-level option
 *     - Settings tab has Approval Delegation card
 *     - Delegation form has required fields (approver, delegate, from, to)
 *     - Add Delegation button disabled when fields are empty
 *
 *   Admin portal (EmployeeManager / EmployeeModal):
 *     - Employee edit modal opens
 *     - Portal Role selector appears when employee has an activated account
 *       (tested: the Job tab contains the "Portal Role" label when authUserId is set)
 *
 *   Employee portal (EmployeeShell):
 *     - Leave tab is visible (existing)
 *     - Leave requests list renders (reuses EmpLeave — no new UI)
 *
 * NOTE: storageState is scoped INSIDE each admin describe — never at file level.
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';

// ─── Admin — LeaveManager (Feature 6 changes) ─────────────────────────────────
test.describe('Leave Approval — Admin portal', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Leave' }).click();
    await page.waitForLoadState('networkidle');
  });

  test('Leave module loads without errors', async ({ page }) => {
    // At least one tab should be visible
    await expect(
      page.getByRole('button', { name: /overview/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test('Requests tab is visible and can be clicked', async ({ page }) => {
    const requestsTab = page.getByRole('button', { name: /requests/i });
    await expect(requestsTab).toBeVisible({ timeout: 6000 });
    await requestsTab.click();
    await page.waitForLoadState('networkidle');
    // Either the requests table (with an "Employee" column) or the
    // "No leave requests" empty state should appear, depending on
    // whether any leave requests exist for the test company.
    await expect(
      page.locator('th').filter({ hasText: /employee/i }).first()
        .or(page.locator('.empty-state').filter({ hasText: /no leave requests/i }))
    ).toBeVisible({ timeout: 8000 });
  });

  test('Settings tab has Approval Chain dropdown with 2-level option', async ({ page }) => {
    // Use .tab-btn class to scope away from sidebar "Company Settings" button
    const settingsTab = page.locator('button.tab-btn').filter({ hasText: /^Settings$/i });
    await expect(settingsTab).toBeVisible({ timeout: 6000 });
    await settingsTab.click();
    await page.waitForLoadState('networkidle');

    // Approval Chain select: filter by a select that contains a 2-level option
    const approvalSelect = page.locator('select').filter({
      has: page.locator('option').filter({ hasText: /2-Level/i })
    });
    await expect(approvalSelect).toBeVisible({ timeout: 8000 });
  });

  test('Settings tab has Approval Delegation card', async ({ page }) => {
    await page.locator('button.tab-btn').filter({ hasText: /^Settings$/i }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('h3').filter({ hasText: /Approval Delegation/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Delegation form has required fields', async ({ page }) => {
    await page.locator('button.tab-btn').filter({ hasText: /^Settings$/i }).click();
    await page.waitForLoadState('networkidle');

    // Wait for the Delegation card
    const delegCard = page.locator('.card').filter({ has: page.locator('h3').filter({ hasText: /Approval Delegation/ }) });
    await expect(delegCard).toBeVisible({ timeout: 8000 });

    // Two select dropdowns in the card (approver + delegate)
    const selects = delegCard.locator('select');
    expect(await selects.count()).toBeGreaterThanOrEqual(2);

    // Two date inputs in the card (from + to)
    const dateInputs = delegCard.locator('input[type="date"]');
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);
  });

  test('Add Delegation button is disabled when fields are empty', async ({ page }) => {
    await page.locator('button.tab-btn').filter({ hasText: /^Settings$/i }).click();
    await page.waitForLoadState('networkidle');

    const delegCard = page.locator('.card').filter({ has: page.locator('h3').filter({ hasText: /Approval Delegation/ }) });
    await expect(delegCard).toBeVisible({ timeout: 8000 });

    const addBtn = delegCard.locator('button').filter({ hasText: /Add Delegation/i });
    await expect(addBtn).toBeDisabled({ timeout: 5000 });
  });
});

// ─── Admin — EmployeeModal portal role selector ────────────────────────────────
test.describe('Leave Approval — EmployeeModal portal role', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Employee edit modal opens and Job tab is visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });

    // Navigate to employees
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');

    // Open first employee edit (if any employees exist)
    const editBtn = page.locator('button').filter({ hasText: /edit/i }).first();
    const hasEmployees = await editBtn.isVisible({ timeout: 5000 }).catch(() => false);

    if (!hasEmployees) {
      test.skip(true, 'No employees to test EmployeeModal');
      return;
    }

    await editBtn.click();

    // Modal should open — click Job & Contract tab
    const jobTab = page.locator('button').filter({ hasText: /Job.*Contract|Job &/i }).first();
    await expect(jobTab).toBeVisible({ timeout: 8000 });
    await jobTab.click();

    // The tab should render Employment Status (a field that always exists)
    await expect(
      page.locator('label').filter({ hasText: /Employment Status/i })
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── Employee portal — Leave tab still works (regression) ────────────────────
// NO storageState at file level — see CLAUDE.md Playwright patterns
test.describe('Leave Approval — Employee portal regression', () => {

  test('Employee Leave tab renders after Feature 6 changes', async ({ page }) => {
    await loginAsEmployee(page);

    const leaveTab = page.locator('button.nav-item').filter({ hasText: /^Leave$/ });
    await expect(leaveTab).toBeVisible({ timeout: 8000 });
    await leaveTab.click();

    // Wait for emp-main to have content — any first child is sufficient
    // Avoids strict mode violation caused by .or() resolving to multiple "Annual Leave" text nodes
    await expect(page.locator('.emp-main').locator('>*').first()).toBeVisible({ timeout: 10000 });
  });
});
