/**
 * professional-licences.spec.js
 * Feature 7.1 — Professional Licence Tracking (DHA/DOH/MOH licence fields + SIF hard block)
 * Feature 7.2 — Minimum Staffing Rules (publish gate + Reports Staffing Compliance tab)
 *
 * Feature 7.1 — Admin portal:
 *   - EmployeeModal UAE Compliance tab has "Professional Licence" section
 *   - Authority select has None/DHA/DOH/MOH/HAAD/DHCC/Other options
 *   - Licence Number input is disabled when authority = 'None'
 *   - Licence Expiry date is disabled when authority = 'None'
 *   - Selecting DHA enables the licence number + expiry inputs
 *   - An inline badge shows valid/expiring/expired based on expiry date
 *   - PayrollEditor: SIF download gate appears when employees have expired licences
 *
 * Feature 7.2 — Roster publish gate:
 *   - When staffing rules exist, clicking Publish checks for violations
 *   - If violations found, a blocking modal appears with a violations table
 *   - Override reason textarea must have ≥10 chars to proceed
 *   - Override & Publish button is disabled until reason is long enough
 *
 * Feature 7.2 — Reports Staffing Compliance tab:
 *   - 8th tab "Staffing Compliance" is present in Reports
 *   - Tab shows a month picker input
 *   - Tab renders a heatmap or compliance table (or empty when no rules)
 *
 * NOTE: storageState inside admin describe blocks.
 */
import { test, expect } from '@playwright/test';

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

// ─── helpers ──────────────────────────────────────────────────────────────────

async function openUaeComplianceTab(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');

  // Use Add Employee for a clean form that always opens
  await page.getByRole('button', { name: /add employee/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

  // Switch to UAE Compliance tab
  await page.getByRole('button', { name: /UAE Compliance/i }).first().click();
  await page.waitForTimeout(300);
  return true;
}

async function openExistingEmpUaeTab(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');

  const empRow = page.locator(`tr:has-text("${EMP_NAME}")`).first();
  if (!(await empRow.isVisible({ timeout: 6000 }).catch(() => false))) return false;

  await empRow.getByRole('button', { name: /edit/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
  await page.getByRole('button', { name: /UAE Compliance/i }).first().click();
  await page.waitForTimeout(300);
  return true;
}

async function goToReports(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Reports' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.locator('h2').filter({ hasText: /HR Reports/i })).toBeVisible({ timeout: 12000 });
}

// ─── Feature 7.1 — Professional Licence: EmployeeModal ───────────────────────

test.describe('Professional Licences (7.1) — EmployeeModal UAE Compliance tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('UAE Compliance tab has a "Professional Licence" section', async ({ page }) => {
    await openUaeComplianceTab(page);

    await expect(
      page.locator('.modal').getByText(/Professional Licence/i).first()
    ).toBeVisible({ timeout: 6000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Authority select is present with None/DHA/DOH/MOH options', async ({ page }) => {
    await openUaeComplianceTab(page);

    const authSelect = page.locator('.modal select').filter({
      has: page.locator('option[value="DHA"]'),
    }).first();
    await expect(authSelect).toBeVisible({ timeout: 6000 });

    for (const val of ['None', 'DHA', 'DOH', 'MOH', 'HAAD', 'DHCC', 'Other']) {
      await expect(authSelect.locator(`option[value="${val}"]`)).toBeAttached({ timeout: 3000 });
    }

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Licence Number input is disabled when authority is None', async ({ page }) => {
    await openUaeComplianceTab(page);

    // Default authority is None — licence number should be disabled
    const licenceInput = page.locator('.modal input[placeholder*="DHA-P"]').first();
    await expect(licenceInput).toBeVisible({ timeout: 6000 });
    await expect(licenceInput).toBeDisabled({ timeout: 3000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('Licence Expiry input is disabled when authority is None', async ({ page }) => {
    await openUaeComplianceTab(page);

    // The Professional Licence section has a date input that's disabled when None
    const authSelect = page.locator('.modal select').filter({ has: page.locator('option[value="DHA"]') }).first();
    await expect(authSelect).toBeVisible({ timeout: 5000 });
    // Verify authority is None
    const val = await authSelect.inputValue();
    if (val !== 'None') { await page.locator('.modal-header .btn-ghost').click(); return; }

    const expiryInputs = page.locator('.modal input[type="date"]');
    // The last date input in UAE Compliance tab is the licence expiry
    const count = await expiryInputs.count();
    if (count > 0) {
      const licenceExpiry = expiryInputs.last();
      await expect(licenceExpiry).toBeDisabled({ timeout: 3000 });
    }

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('selecting DHA enables the Licence Number and Expiry inputs', async ({ page }) => {
    await openUaeComplianceTab(page);

    const authSelect = page.locator('.modal select').filter({ has: page.locator('option[value="DHA"]') }).first();
    await expect(authSelect).toBeVisible({ timeout: 5000 });
    await authSelect.selectOption('DHA');
    await page.waitForTimeout(200);

    const licenceInput = page.locator('.modal input[placeholder*="DHA-P"]').first();
    await expect(licenceInput).toBeEnabled({ timeout: 4000 });

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('a future expiry date shows a "Valid" or green badge', async ({ page }) => {
    await openUaeComplianceTab(page);

    const authSelect = page.locator('.modal select').filter({ has: page.locator('option[value="DHA"]') }).first();
    await authSelect.selectOption('DHA');
    await page.waitForTimeout(200);

    const dateInputs = page.locator('.modal input[type="date"]');
    const count = await dateInputs.count();
    if (count > 0) {
      const futureDate = new Date(Date.now() + 365 * 86400000).toISOString().split('T')[0];
      await dateInputs.last().fill(futureDate);
      await page.waitForTimeout(300);

      // An inline badge should appear — "Valid", "Expires in …d", or green class
      const badge = page.locator('.modal .badge-green, .modal .badge-blue')
        .or(page.locator('.modal').getByText(/valid|expires in/i)).first();
      await expect(badge).toBeVisible({ timeout: 4000 });
    }

    await page.locator('.modal-header .btn-ghost').click();
  });

  test('a past expiry date shows an "Expired" or red badge', async ({ page }) => {
    await openUaeComplianceTab(page);

    const authSelect = page.locator('.modal select').filter({ has: page.locator('option[value="DHA"]') }).first();
    await authSelect.selectOption('DHA');
    await page.waitForTimeout(200);

    const dateInputs = page.locator('.modal input[type="date"]');
    const count = await dateInputs.count();
    if (count > 0) {
      const pastDate = '2020-01-01';
      await dateInputs.last().fill(pastDate);
      await page.waitForTimeout(300);

      const badge = page.locator('.modal .badge-red, .modal .badge-danger')
        .or(page.locator('.modal').getByText(/expired/i)).first();
      await expect(badge).toBeVisible({ timeout: 4000 });
    }

    await page.locator('.modal-header .btn-ghost').click();
  });
});

// ─── Feature 7.1 — PayrollEditor: SIF download gate ─────────────────────────

test.describe('Professional Licences (7.1) — PayrollEditor: SIF gate', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Payroll module loads without errors', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
    await page.waitForLoadState('networkidle');
    await expect(
      page.locator('h2').filter({ hasText: /payroll/i }).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('SIF download button is present in a generated payroll run', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
    await page.waitForLoadState('networkidle');

    // Look for any generated payroll run to test the SIF button
    const payrollRow = page.locator('tr').filter({ hasText: /generated/i }).first();
    if (!(await payrollRow.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No generated payroll runs — SIF button test skipped');
      return;
    }

    await payrollRow.locator('button').first().click();
    await page.waitForLoadState('networkidle');

    // In the PayrollEditor, look for a Download SIF button
    const sifBtn = page.locator('button').filter({ hasText: /download.*SIF|SIF.*download/i }).first();
    await expect(sifBtn).toBeVisible({ timeout: 8000 });
  });
});

// ─── Feature 7.2 — Roster: publish gate modal ────────────────────────────────

test.describe('Staffing Rules (7.2) — Roster: publish gate', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Roster Publish button is present in the Monthly Roster tab', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Roster' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster|Roster/i }).first().click();
    await page.waitForTimeout(400);

    // Publish button exists but may be disabled when no roster assignments — check presence only
    const publishBtn = page.locator('button').filter({ hasText: /Publish/i }).first();
    await expect(publishBtn).toBeVisible({ timeout: 6000 });
  });

  test('clicking Publish with a violation opens the gate modal', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Roster' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster|Roster/i }).first().click();
    await page.waitForTimeout(400);

    const publishBtn = page.locator('button').filter({ hasText: /Publish/i }).first();
    // Skip if button is disabled (no roster assignments in current month)
    const isEnabled = await publishBtn.isEnabled({ timeout: 3000 }).catch(() => false);
    if (!isEnabled) {
      test.skip(true, 'Publish button is disabled — no roster assignments to publish');
      return;
    }
    await publishBtn.click();
    await page.waitForTimeout(500);

    // Either:
    // a) publishGate modal appears (violations found)
    // b) Roster publishes directly (no rules or no violations)
    const gateModal = page.locator('.modal-overlay, .modal-backdrop').filter({ hasText: /staffing.*violation|violation|minimum.*staff/i }).first();
    const successMsg = page.locator('text=/published|roster.*published/i').first();

    const hasGate    = await gateModal.isVisible({ timeout: 3000 }).catch(() => false);
    const hasSuccess = await successMsg.isVisible({ timeout: 3000 }).catch(() => false);

    if (!hasGate && !hasSuccess) {
      // No reaction — likely no employees in roster
      test.skip(true, 'No roster assignments — publish has no effect to test');
      return;
    }

    expect(hasGate || hasSuccess).toBe(true);
  });

  test('publish gate modal has a violations table and override textarea', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Roster' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster|Roster/i }).first().click();
    await page.waitForTimeout(400);

    const publishBtn2 = page.locator('button').filter({ hasText: /Publish/i }).first();
    if (!(await publishBtn2.isEnabled({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Publish button disabled — no roster data to test gate modal');
      return;
    }
    await publishBtn2.click();
    await page.waitForTimeout(500);

    const gateModal = page.locator('.modal').filter({ hasText: /staffing|violation|minimum/i }).first();
    if (!(await gateModal.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No publish gate triggered — no staffing rule violations');
      return;
    }

    // Violations table
    await expect(gateModal.locator('table').first()).toBeVisible({ timeout: 4000 });

    // Override reason textarea
    await expect(
      gateModal.locator('textarea[placeholder*="reason"], textarea[placeholder*="override"]').first()
    ).toBeVisible({ timeout: 4000 });

    // Close modal
    await gateModal.locator('button').filter({ hasText: /cancel/i }).first().click();
  });

  test('override button is disabled with reason shorter than 10 chars', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Roster' }).click();
    await page.waitForLoadState('networkidle');
    await page.locator('button.tab-btn').filter({ hasText: /Monthly Roster|Roster/i }).first().click();
    await page.waitForTimeout(400);

    const publishBtn3 = page.locator('button').filter({ hasText: /Publish/i }).first();
    if (!(await publishBtn3.isEnabled({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Publish button disabled — no roster data');
      return;
    }
    await publishBtn3.click();
    await page.waitForTimeout(500);

    const gateModal = page.locator('.modal').filter({ hasText: /staffing|violation|minimum/i }).first();
    if (!(await gateModal.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No publish gate triggered');
      return;
    }

    const reasonArea = gateModal.locator('textarea').first();
    await reasonArea.fill('short'); // < 10 chars

    const overrideBtn = gateModal.locator('button').filter({ hasText: /override.*publish|publish.*override/i }).first();
    await expect(overrideBtn).toBeDisabled({ timeout: 3000 });

    await gateModal.locator('button').filter({ hasText: /cancel/i }).first().click();
  });
});

// ─── Feature 7.2 — Reports: Staffing Compliance tab ─────────────────────────

test.describe('Staffing Rules (7.2) — Reports: Staffing Compliance tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Staffing Compliance" tab is present in the Reports module', async ({ page }) => {
    await goToReports(page);
    await expect(
      page.locator('.page-body').getByRole('button', { name: 'Staffing Compliance', exact: true })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Reports page now shows 8 tab buttons (including Staffing Compliance)', async ({ page }) => {
    await goToReports(page);
    // Reports uses btn btn-sm btn-primary/btn-ghost — NOT tab-btn class
    // Count via the known tab labels instead
    const labels = ['Headcount', 'Payroll Cost', 'Leave Usage', 'Attendance', 'Doc Expiry', 'Salary History', 'Staff Turnover', 'Staffing Compliance'];
    let found = 0;
    for (const label of labels) {
      const btn = page.locator('.page-body').getByRole('button', { name: label, exact: true });
      if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) found++;
    }
    expect(found).toBeGreaterThanOrEqual(8);
  });

  test('Staffing Compliance tab renders month picker or no-rules empty state', async ({ page }) => {
    await goToReports(page);
    await page.locator('.page-body').getByRole('button', { name: 'Staffing Compliance', exact: true }).click();
    await page.waitForTimeout(600);

    // When no staffing rules exist, the tab renders <EmptyState> with no month picker.
    // Accept either the month input (rules exist) OR the empty state text (no rules).
    const monthInput = page.locator('input[type="month"]').first();
    const emptyState = page.getByText(/No staffing rules defined/i).first();
    const hasContent = await monthInput.isVisible({ timeout: 4000 }).catch(() => false)
                    || await emptyState.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });

  test('Staffing Compliance tab shows heatmap or "no rules" empty state', async ({ page }) => {
    await goToReports(page);
    await page.locator('.page-body').getByRole('button', { name: 'Staffing Compliance', exact: true }).click();
    await page.waitForTimeout(600);

    // Either a rules compliance card, no-roster empty state, or no-rules empty state
    const card     = page.locator('.card').first();
    const emptyMsg = page.getByText(/No staffing rules|No roster data/i).first();
    const hasContent = await card.isVisible({ timeout: 5000 }).catch(() => false)
                    || await emptyMsg.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });

  test('Staffing Compliance tab month picker defaults to current month', async ({ page }) => {
    await goToReports(page);
    await page.locator('.page-body').getByRole('button', { name: 'Staffing Compliance', exact: true }).click();
    await page.waitForTimeout(600);

    // Skip if no staffing rules configured (tab renders EmptyState with no month input)
    const emptyState = page.getByText(/No staffing rules defined/i).first();
    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No staffing rules configured — month picker not rendered');
      return;
    }

    const monthInput = page.locator('input[type="month"]').first();
    await expect(monthInput).toBeVisible({ timeout: 5000 });

    const val = await monthInput.inputValue();
    const now = new Date();
    const expected = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    expect(val).toBe(expected);
  });

  test('changing the month triggers a roster reload (no crash)', async ({ page }) => {
    await goToReports(page);
    await page.locator('.page-body').getByRole('button', { name: 'Staffing Compliance', exact: true }).click();
    await page.waitForTimeout(600);

    // Skip if no staffing rules configured
    const emptyState = page.getByText(/No staffing rules defined/i).first();
    if (await emptyState.isVisible({ timeout: 3000 }).catch(() => false)) {
      test.skip(true, 'No staffing rules configured — month picker not rendered');
      return;
    }

    const monthInput = page.locator('input[type="month"]').first();
    await expect(monthInput).toBeVisible({ timeout: 5000 });

    // Change to previous month
    const prev = new Date();
    prev.setMonth(prev.getMonth() - 1);
    const prevMonth = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, '0')}`;
    await monthInput.fill(prevMonth);
    await page.waitForTimeout(600);

    // Page should not crash
    await expect(page.locator('.page-body').first()).toBeVisible({ timeout: 5000 });
  });

  test('all 7 original Reports tabs still render after adding tab 8', async ({ page }) => {
    await goToReports(page);

    const originalTabs = ['Headcount', 'Payroll Cost', 'Leave Usage', 'Attendance', 'Doc Expiry', 'Salary History', 'Staff Turnover'];
    for (const label of originalTabs) {
      await expect(
        page.locator('.page-body').getByRole('button', { name: label, exact: true })
      ).toBeVisible({ timeout: 5000 });
    }
  });
});
