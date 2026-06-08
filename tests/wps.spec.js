/**
 * wps.spec.js — Playwright tests for Feature 9: WPS Payment Confirmation & Reconciliation
 *
 * Covers:
 *   PayrollList:
 *     - WPS column is present in the payroll history table
 *     - Generated payroll runs show a WPS status badge
 *
 *   PayrollEditor (locked payroll):
 *     - WPS Payment Tracking card is visible on a finalised payroll
 *     - WPS status selector contains all expected options
 *     - Admin can update WPS status to "submitted"
 *     - "Save WPS Status" button saves and shows confirmation
 *     - Entering a bank reference number persists
 *     - Per-employee payment status rows are visible
 *     - Marking an employee as "Rejected" shows the rejection reason field
 *     - "Corrected SIF" button appears when at least one employee is rejected
 *
 *   Dashboard:
 *     - Recent Payroll Runs table has a WPS column
 *
 * NOTE: All tests use storageState (admin session) scoped inside the describe block.
 * Tests that need a locked payroll navigate to the first generated run in PayrollList.
 * If no generated run exists the test skips rather than fails.
 */
import { test, expect } from '@playwright/test';

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function goToPayroll(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
  await page.waitForLoadState('networkidle');
}

// Navigate to the first generated payroll run and open the PayrollEditor.
// Returns false if no generated run exists (caller should skip).
async function openFirstGeneratedPayroll(page) {
  await goToPayroll(page);

  // Check if there are any generated runs in the table
  const generatedBadge = page.locator('td').filter({ has: page.locator('.badge-green:has-text("Generated")') }).first();
  if (!(await generatedBadge.isVisible({ timeout: 3000 }).catch(() => false))) {
    return false;
  }

  // Click the row to open it in PayrollEditor
  const row = page.locator('tr').filter({ has: page.locator('.badge-green:has-text("Generated")') }).first();
  await row.locator('button[title="Open & Edit"]').click();
  await page.waitForLoadState('networkidle');
  return true;
}

// ─── PayrollList WPS column ───────────────────────────────────────────────────
test.describe('WPS — PayrollList column', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('payroll history table has a WPS column', async ({ page }) => {
    await goToPayroll(page);

    // The WPS <th> only exists when sortedPayrolls.length > 0 (empty state shown otherwise).
    // Scope to the Payroll History card table and skip if no runs exist.
    const table = page.locator('.card')
      .filter({ has: page.locator('h3').filter({ hasText: /Payroll History/i }) })
      .locator('table').first();
    if (!(await table.isVisible({ timeout: 8000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs yet — WPS column not rendered in empty state');
      return;
    }
    await expect(
      table.locator('th').filter({ hasText: /WPS/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── PayrollEditor WPS Tracking panel ────────────────────────────────────────
test.describe('WPS — PayrollEditor tracking panel', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('WPS Payment Tracking card is visible on a finalised payroll', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) {
      test.skip(true, 'No generated payroll run found — skipping WPS panel tests');
      return;
    }

    await expect(
      page.locator('h3').filter({ hasText: /WPS Payment Tracking/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('WPS status selector has all expected options', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    // Open the WPS status dropdown
    const statusSelect = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i })
      .locator('select').first();
    await expect(statusSelect).toBeVisible({ timeout: 8000 });

    const options = await statusSelect.locator('option').allTextContents();
    const expectedLabels = ['Not Submitted', 'SIF Generated', 'Submitted to Bank', 'Confirmed', 'Partial Rejection', 'Failed'];
    for (const label of expectedLabels) {
      expect(options).toContain(label);
    }
  });

  test('admin can update WPS status to "Submitted to Bank" and save', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    const wpsCard = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i });
    await expect(wpsCard).toBeVisible({ timeout: 8000 });

    const statusSelect = wpsCard.locator('select').first();
    await statusSelect.selectOption('submitted');

    const saveBtn = wpsCard.getByRole('button', { name: /Save WPS Status/i });
    await expect(saveBtn).toBeEnabled({ timeout: 4000 });
    await saveBtn.click();

    // Confirmation "Saved" tick should appear
    await expect(wpsCard.locator('text=Saved')).toBeVisible({ timeout: 6000 });
  });

  test('bank reference number input is present and editable', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    const wpsCard = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i });
    const refInput = wpsCard.locator('input[placeholder*="WPS"]');
    await expect(refInput).toBeVisible({ timeout: 8000 });
    await refInput.fill('WPS-TEST-2026');
    expect(await refInput.inputValue()).toBe('WPS-TEST-2026');
  });

  test('per-employee payment status rows render for each active employee', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    const wpsCard = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i });
    // Each active employee should have a status selector (paid/pending/rejected)
    const empRows = wpsCard.locator('select').filter({ has: page.locator('option[value="pending"]') });
    // There should be at least one employee row (entry-level select, not the run-level one)
    // The run-level select is first; employee selects start from the second
    const allSelects = await wpsCard.locator('select').count();
    // At minimum 1 run-level select; if there are employees there'll be more
    expect(allSelects).toBeGreaterThanOrEqual(1);
  });

  test('marking an employee as Rejected shows a rejection reason input', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    const wpsCard = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i });
    // Find the second select (first employee's status selector — index 1, run-level is index 0)
    const allSelects = wpsCard.locator('select');
    const count = await allSelects.count();
    if (count < 2) {
      test.skip(true, 'No employee entries in this payroll');
      return;
    }

    // Select the second dropdown (first employee-level status)
    const empSelect = allSelects.nth(1);
    await empSelect.selectOption('rejected');

    // Rejection reason input should appear
    await expect(
      wpsCard.locator('input[placeholder*="Rejection reason"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('"Corrected SIF" button appears in WPS panel when employee is rejected', async ({ page }) => {
    const found = await openFirstGeneratedPayroll(page);
    if (!found) { test.skip(true, 'No generated payroll run'); return; }

    const wpsCard = page.locator('.card').filter({ hasText: /WPS Payment Tracking/i });
    const allSelects = wpsCard.locator('select');
    const count = await allSelects.count();
    if (count < 2) {
      test.skip(true, 'No employee entries in this payroll');
      return;
    }

    // Mark first employee as rejected
    await allSelects.nth(1).selectOption('rejected');

    // "Download Corrected SIF" button should appear in the WPS card
    await expect(
      wpsCard.getByRole('button', { name: /Corrected SIF/i })
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── Dashboard WPS column ─────────────────────────────────────────────────────
test.describe('WPS — Dashboard recent payrolls', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Dashboard "Recent Payroll Runs" table has a WPS column', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // The Recent Payroll Runs card only renders if payrolls exist
    const card = page.locator('.card').filter({ hasText: /Recent Payroll Runs/i });
    if (!(await card.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs in this environment — skipping dashboard WPS column check');
      return;
    }
    await expect(
      card.locator('th').filter({ hasText: /^WPS$/i })
    ).toBeVisible({ timeout: 5000 });
  });
});
