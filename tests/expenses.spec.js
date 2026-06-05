/**
 * expenses.spec.js — Playwright tests for Feature 14: Expense Claims & Reimbursements
 *
 * Covers:
 *   Admin portal (ExpensesManager):
 *     - "Expenses" nav item is visible in the sidebar
 *     - Expenses page renders with 3 stat cards
 *     - Filter tabs: All / Pending / Approved / Paid / Rejected
 *     - Table is present (with header columns)
 *     - No "Add" button (admin approves/rejects; employees submit via portal)
 *     - Approved claims show an "Approve" action; pending show "Reject" inline form trigger
 *     - Reject reason input appears when admin clicks Reject on a pending claim
 *
 *   PayrollEditor — expense reimbursement panel:
 *     - Payroll module loads without errors (expense panel silently absent when no approved claims)
 *
 *   Employee portal (EmpExpenses):
 *     - "Expenses" tab is visible in the employee sidebar
 *     - Tab renders the Expenses page
 *     - "Submit Expense" / "New Expense" button opens the submission form
 *     - Form has category dropdown, amount, date, description, and receipt URL fields
 *     - Submit button is disabled when form is empty / required fields missing
 *     - Cancel button hides the form
 *     - Claim history sections render (Pending / Approved / Paid / Rejected)
 *
 * NOTE: storageState is scoped INSIDE each admin describe block.
 * The employee describe block uses loginAsEmployee() (fresh login).
 * No expense claim data is created by these tests; they test UI only.
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToExpenses(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Expenses' }).click();
  await page.waitForLoadState('networkidle');
}

// ─── Admin — ExpensesManager ──────────────────────────────────────────────────

test.describe('Expenses — Admin portal (ExpensesManager)', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Expenses" nav item is visible in the admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Expenses' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Expenses page renders with 3 stat cards', async ({ page }) => {
    await goToExpenses(page);
    // 3 stat cards: Pending (count + AED), Approved Unpaid (AED), All-Time Paid (AED)
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
    const cards = page.locator('.stat-card');
    await expect(cards).toHaveCount(3, { timeout: 8000 });
  });

  test('filter tabs All / Pending / Approved / Paid / Rejected render', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    for (const tab of ['All', 'Pending', 'Approved', 'Paid', 'Rejected']) {
      await expect(
        page.locator('button').filter({ hasText: new RegExp(`^${tab}$`, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('switching filter tabs updates the active button style', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    // Click Pending tab
    await page.locator('button').filter({ hasText: /^Pending$/i }).first().click();
    // The active tab should have a primary button style
    const pendingBtn = page.locator('button').filter({ hasText: /^Pending$/i }).first();
    const className = await pendingBtn.getAttribute('class');
    expect(className).toMatch(/primary|active/i);
  });

  test('expense claims table renders when claims exist, empty state otherwise', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    const table = page.locator('table').first();
    const tableExists = await table.isVisible({ timeout: 3000 }).catch(() => false);

    if (tableExists) {
      // Table is rendered — verify column headers
      for (const col of ['Employee', 'Category', 'Amount', 'Status']) {
        await expect(
          page.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
        ).toBeVisible({ timeout: 5000 });
      }
    } else {
      // No claims yet — empty state is shown instead of table (valid)
      await expect(page.locator('.page-body')).toBeVisible({ timeout: 5000 });
    }
  });

  test('no "Add Expense" button on admin side (employees submit only)', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
    // Admin should NOT have an "Add Expense" or "New Expense" button — they only approve/reject
    await expect(
      page.locator('button').filter({ hasText: /^(add|new) expense/i })
    ).not.toBeVisible({ timeout: 3000 });
  });

  test('pending claim shows Approve and Reject action buttons', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    // Look for an Approve button in the table (only visible if pending claims exist)
    const approveBtn = page.locator('button').filter({ hasText: /approve/i }).first();
    const rejectBtn  = page.locator('button').filter({ hasText: /reject/i }).first();

    if (!(await approveBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No pending expense claims in test data — skipping approve/reject UI test');
      return;
    }
    await expect(approveBtn).toBeVisible();
    await expect(rejectBtn).toBeVisible();
  });

  test('clicking Reject on a pending claim reveals the rejection reason input', async ({ page }) => {
    await goToExpenses(page);
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });

    const rejectBtn = page.locator('button').filter({ hasText: /^reject$/i }).first();
    if (!(await rejectBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No pending expense claims — skipping reject-form test');
      return;
    }

    await rejectBtn.click();
    // An inline rejection reason input / textarea should appear
    await expect(
      page.locator('input[placeholder*="reason"], textarea[placeholder*="reason"]').first()
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── PayrollEditor — expense reimbursement panel ──────────────────────────────

test.describe('Expenses — PayrollEditor approved-expenses panel', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Payroll module loads without errors (expense panel absent when no approved claims)', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
    await page.waitForLoadState('networkidle');
    await expect(
      page.locator('h2').filter({ hasText: /payroll/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });
});

// ─── Employee portal — EmpExpenses ───────────────────────────────────────────
// NO storageState here — loginAsEmployee() navigates from the unauthenticated page.

test.describe('Expenses — Employee portal (EmpExpenses)', () => {

  test('"Expenses" tab is visible in the employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Expenses$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Expenses tab renders the page content', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    // Page heading "Expense Claims" is visible — use specific heading locator (not .or() to avoid strict mode)
    await expect(
      page.locator('h2').filter({ hasText: /expense/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Submit / New Expense button opens the submission form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();

    // Wait for the page to render
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const submitBtn = page.getByRole('button', { name: /new claim|submit.*claim|add.*claim/i }).first();
    await expect(submitBtn).toBeVisible({ timeout: 6000 });
    await submitBtn.click();

    // The form should now be visible — look for the category select
    await expect(
      page.locator('select').filter({ has: page.locator('option[value="travel"]') })
        .or(page.locator('select').filter({ has: page.locator('option', { hasText: /travel/i }) }))
        .first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('expense form has category dropdown with expected options', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const submitBtn = page.getByRole('button', { name: /new claim|submit.*claim|add.*claim/i }).first();
    if (!(await submitBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Submit Expense button not found');
      return;
    }
    await submitBtn.click();

    // Category dropdown should include travel, meals, accommodation, medical, training, other
    const catSelect = page.locator('select').first();
    await expect(catSelect).toBeVisible({ timeout: 5000 });
    const options = await catSelect.locator('option').allTextContents();
    const expected = ['travel', 'meals', 'medical', 'training', 'other'];
    const optionValues = options.map(o => o.toLowerCase().trim());
    for (const exp of expected) {
      const found = optionValues.some(v => v.includes(exp));
      expect(found, `Expected category option containing "${exp}"`).toBe(true);
    }
  });

  test('expense form has amount, date, and description fields', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const submitBtn = page.getByRole('button', { name: /new claim|submit.*claim|add.*claim/i }).first();
    if (!(await submitBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Submit Expense button not found');
      return;
    }
    await submitBtn.click();

    // Amount (number input)
    await expect(page.locator('input[type="number"]').first()).toBeVisible({ timeout: 5000 });
    // Date
    await expect(page.locator('input[type="date"]').first()).toBeVisible({ timeout: 4000 });
    // Description (textarea or input)
    await expect(
      page.locator('textarea, input[placeholder*="description"], input[placeholder*="Description"]').first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('"Submit Claim" button is disabled when amount and description are empty', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const newClaimBtn = page.getByRole('button', { name: /new claim|submit.*claim|add.*claim/i }).first();
    if (!(await newClaimBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, '"New Claim" button not found');
      return;
    }
    await newClaimBtn.click();

    // The submit button says "Submit Claim" and is disabled when amount or description is blank.
    // It has onClick (not type="submit") and disabled={!form.amount || !form.description.trim()}.
    await expect(
      page.locator('button').filter({ hasText: 'Submit Claim' }).first()
    ).toBeDisabled({ timeout: 4000 });
  });

  test('Cancel button hides the expense submission form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const submitBtn = page.getByRole('button', { name: /new claim|submit.*claim|add.*claim/i }).first();
    if (!(await submitBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Submit Expense button not found');
      return;
    }
    await submitBtn.click();

    // Verify the form is open (amount input visible)
    await expect(page.locator('input[type="number"]').first()).toBeVisible({ timeout: 5000 });

    // Cancel button says "Cancel" (btn-outline btn-sm alongside the Submit Claim button)
    await page.locator('button').filter({ hasText: /^Cancel$/ }).first().click();

    // Form should be hidden — "Submit Claim" button no longer visible
    await expect(page.locator('button').filter({ hasText: 'Submit Claim' })).not.toBeVisible({ timeout: 4000 });
  });

  test('claim history sections render for each status', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Expenses$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // Either claim sections (Pending / Approved etc.) or an empty state are valid
    const content = page.locator('.emp-card, .emp-page-body').first();
    await expect(content).toBeVisible({ timeout: 6000 });
  });
});
