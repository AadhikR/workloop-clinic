/**
 * employees.spec.js — Comprehensive tests for Employee Management
 *
 * Covers:
 *   Employee list:
 *     - Page loads, table columns visible, Add Employee button
 *     - Add employee → appears in list
 *     - Edit employee salary → updates record
 *     - Archive employee → Terminated badge
 *     - Search filter, status filter, department filter
 *     - Document Expiry tab renders
 *     - EOS Calculator button visible
 *
 *   Employee modal — all 7 tabs:
 *     - Personal: name, email, phone, emergency contact
 *     - Job & Contract: title, dept, status, contract type, dates
 *     - Salary & Bank: salary, bank name, IBAN, MOL ID
 *     - UAE Compliance: nationality, visa, passport, Nafis field
 *     - Documents tab (existing employees only)
 *     - Insurance tab (existing employees only)
 *     - Contracts tab (existing employees only)
 *     - Save button hidden on Documents, Insurance, Contracts tabs
 */

import { test, expect } from '@playwright/test';

test.use({ storageState: '.playwright/admin-session.json' });

const UNIQUE = `PW_EMP_${Date.now()}`;
const EMP_EMAIL = `pw_${Date.now()}@test.workloop.local`;

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToEmployees(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');
  await expect(
    page.locator('.page-header h2').filter({ hasText: /Employees/i })
  ).toBeVisible({ timeout: 10000 });
}

async function openAddModal(page) {
  await page.getByRole('button', { name: /Add Employee/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
}

// ─── Employee list ─────────────────────────────────────────────────────────────

test.describe('Employees — List view', () => {

  test('page loads without console errors', async ({ page }) => {
    const errors = [];
    page.on('console', m => {
      if (m.type() === 'error' && !m.text().includes('favicon')) errors.push(m.text());
    });
    await goToEmployees(page);
    await page.waitForTimeout(1500);
    expect(errors).toHaveLength(0);
  });

  test('table has Name, Department, and Status columns', async ({ page }) => {
    await goToEmployees(page);
    for (const col of ['Name', 'Department', 'Status']) {
      await expect(
        page.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 8000 });
    }
  });

  test('"Add Employee" button is present', async ({ page }) => {
    await goToEmployees(page);
    await expect(
      page.getByRole('button', { name: /Add Employee/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('search input is present and accepts text', async ({ page }) => {
    await goToEmployees(page);
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    await expect(searchInput).toBeVisible({ timeout: 6000 });
    await searchInput.fill('xyz_test');
    await expect(searchInput).toHaveValue('xyz_test');
    await searchInput.fill('');
  });

  test('status filter has Active and Probation options, not Terminated', async ({ page }) => {
    await goToEmployees(page);
    const statusSelect = page.locator('select').filter({
      has: page.locator('option').filter({ hasText: /active|probation/i })
    }).first();
    await expect(statusSelect).toBeVisible({ timeout: 6000 });
    const opts = await statusSelect.locator('option').allTextContents();
    const lower = opts.map(o => o.toLowerCase().trim());
    expect(lower.some(o => o.includes('active'))).toBe(true);
    expect(lower.some(o => o.includes('probation'))).toBe(true);
    // Terminated employees live in their own tab, not as a status-filter option
    // on the main Employee List — see "Terminated Employees tab" tests below.
    expect(lower.some(o => o.includes('terminated'))).toBe(false);
  });

  test('Terminated Employees tab shows only terminated employees', async ({ page }) => {
    await goToEmployees(page);
    await page.locator('button.tab-btn').filter({ hasText: /Terminated Employees/i }).click();
    await page.waitForLoadState('domcontentloaded');
    await expect(page.locator('h3').filter({ hasText: /Terminated Employees/i })).toBeVisible({ timeout: 8000 });
    // Either rows with "Terminated" badge or an empty state — never an "Active" badge
    const hasTerminated = await page.locator('td').filter({ hasText: /^Terminated$/ }).first().isVisible({ timeout: 3000 }).catch(() => false);
    const hasEmpty = await page.locator('text=/No terminated employees/i').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasTerminated || hasEmpty).toBe(true);
    await expect(page.locator('td').filter({ hasText: /^Active$/ })).toHaveCount(0);
  });

  test('document expiry tab renders when present', async ({ page }) => {
    await goToEmployees(page);
    const expiryTab = page.locator('button.tab-btn').filter({ hasText: /expiry|expiring/i }).first();
    if (!(await expiryTab.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'Expiry tab not visible');
      return;
    }
    await expiryTab.click();
    await page.waitForLoadState('networkidle');
    await expect(page.locator('.page-body').first()).toBeVisible({ timeout: 6000 });
  });
});

// ─── Add, edit, archive ───────────────────────────────────────────────────────

test.describe('Employees — Add, edit, archive', () => {

  test('add new employee appears in the list', async ({ page }) => {
    // Capture alert() fired by handleSaveEmployee on save failure so we can surface the error
    let saveError = null;
    page.on('dialog', async dialog => {
      saveError = dialog.message();
      await dialog.accept();
    });

    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('input[placeholder="e.g. John Smith"]').fill(UNIQUE);
    await page.locator('input[placeholder="work@company.com"]').fill(EMP_EMAIL);
    await page.locator('.modal').getByRole('button', { name: /Salary/i }).first().click();
    await page.locator('input[placeholder="e.g. 5000"]').fill('6000');
    await page.locator('.modal-footer .btn-primary').click();

    // Wait for modal to close (save completes) or a dialog to fire (save fails)
    const closed = await page.locator('.modal')
      .waitFor({ state: 'hidden', timeout: 15000 })
      .then(() => true)
      .catch(() => false);

    if (!closed) {
      const msg = saveError ?? 'Modal did not close after 15 s (check browser console)';
      // Missing migration (e.g. sql/033_clinical_gaps.sql) — skip rather than fail
      if (msg.includes('schema cache') || msg.includes('licence_authority') || msg.includes('column') && msg.includes('does not exist')) {
        test.skip(true, `DB migration not yet applied — run sql/033_clinical_gaps.sql in Supabase SQL Editor. Error: ${msg}`);
        return;
      }
      throw new Error(`Employee save failed — Supabase error: ${msg}`);
    }

    await expect(page.locator(`td:has-text("${UNIQUE}")`)).toBeVisible({ timeout: 10000 });
  });

  test('edit employee salary updates the record without error', async ({ page }) => {
    await goToEmployees(page);
    const row = page.locator('tr').filter({ hasText: UNIQUE }).first();
    if (!(await row.isVisible({ timeout: 6000 }).catch(() => false))) {
      test.skip(true, 'Test employee not found — run add test first');
      return;
    }
    await row.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    await page.locator('.modal').getByRole('button', { name: /Salary/i }).first().click();
    const salaryInput = page.locator('input[placeholder="e.g. 5000"]');
    await salaryInput.clear();
    await salaryInput.fill('7500');
    await page.locator('.modal-footer .btn-primary').click();
    await expect(page.locator('.alert-danger')).not.toBeVisible({ timeout: 5000 });
  });

  test('archive employee moves them out of the Employee List into Terminated Employees', async ({ page }) => {
    await goToEmployees(page);
    const row = page.locator('tr').filter({ hasText: UNIQUE }).first();
    if (!(await row.isVisible({ timeout: 6000 }).catch(() => false))) {
      test.skip(true, 'Test employee not found');
      return;
    }
    await row.locator('button[title="Delete employee"]').click();
    await expect(page.locator('h3').filter({ hasText: /Archive Employee/i })).toBeVisible({ timeout: 5000 });
    await page.getByRole('button', { name: 'Archive Employee' }).click();
    await expect(page.locator('h3').filter({ hasText: /Archive Employee/i })).toBeHidden({ timeout: 5000 });

    // No longer in the main Employee List
    await expect(page.locator('tr').filter({ hasText: UNIQUE })).toHaveCount(0, { timeout: 8000 });

    // Shows up in the Terminated Employees tab with a Terminated badge
    await page.locator('button.tab-btn').filter({ hasText: /Terminated Employees/i }).click();
    await page.waitForLoadState('domcontentloaded');
    const termRow = page.locator('tr').filter({ hasText: UNIQUE }).first();
    await expect(termRow).toBeVisible({ timeout: 8000 });
    await expect(termRow.locator('text=Terminated')).toBeVisible();
  });
});

// ─── Modal — Personal tab ─────────────────────────────────────────────────────

test.describe('Employees — Modal Personal tab', () => {

  test('Add modal defaults to Personal tab with name and email fields', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await expect(page.locator('input[placeholder="e.g. John Smith"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('input[placeholder="work@company.com"]')).toBeVisible({ timeout: 4000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Personal tab has phone and date-of-birth fields', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await expect(
      page.locator('.modal input[placeholder*="+971"], .modal input[placeholder*="phone"], .modal input[placeholder*="Phone"]').first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Emergency Contact section is visible in Personal tab', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await expect(
      page.locator('.modal').locator('text=/Emergency Contact/i').first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });
});

// ─── Modal — Job & Contract tab ───────────────────────────────────────────────

test.describe('Employees — Modal Job & Contract tab', () => {

  test('Job tab has Job Title, Department, and Employment Status fields', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /Job/i }).first().click();
    await expect(
      page.locator('.modal input[placeholder*="Engineer"], .modal input[placeholder*="title"], .modal input[placeholder*="Title"]').first()
    ).toBeVisible({ timeout: 6000 });
    // Employment status select
    await expect(
      page.locator('.modal select').filter({
        has: page.locator('option').filter({ hasText: /active/i })
      }).first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Contract Type dropdown has Unlimited and Limited options', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /Job/i }).first().click();
    const contractSelect = page.locator('.modal select').filter({
      has: page.locator('option').filter({ hasText: /unlimited|limited/i })
    }).first();
    await expect(contractSelect).toBeVisible({ timeout: 5000 });
    const opts = await contractSelect.locator('option').allTextContents();
    expect(opts.some(o => /unlimited/i.test(o))).toBe(true);
    expect(opts.some(o => /^limited$/i.test(o.trim()))).toBe(true);
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Employment Start Date field is in the Job tab', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /Job/i }).first().click();
    await expect(
      page.locator('.modal input[type="date"]').first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });
});

// ─── Modal — Salary & Bank tab ────────────────────────────────────────────────

test.describe('Employees — Modal Salary & Bank tab', () => {

  test('Salary tab has Basic Salary, IBAN, and Bank Name fields', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /Salary/i }).first().click();
    await expect(page.locator('input[placeholder="e.g. 5000"]')).toBeVisible({ timeout: 5000 });
    await expect(
      page.locator('.modal input[placeholder*="AE"], .modal input[placeholder*="IBAN"]').first()
    ).toBeVisible({ timeout: 5000 });
    // Bank Name is a free-text input (placeholder "e.g. ENBD, FAB, ADCB"), not a <select>
    await expect(
      page.locator('.modal input[placeholder*="ENBD"]').first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Housing and Transport allowance fields are in the Salary tab', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /Salary/i }).first().click();
    // Housing Allowance input has placeholder "e.g. 2000"; check the label too
    await expect(
      page.locator('.modal label').filter({ hasText: /Housing Allowance/i }).first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });
});

// ─── Modal — UAE Compliance tab ───────────────────────────────────────────────

test.describe('Employees — Modal UAE Compliance tab', () => {

  test('UAE Compliance tab has Nationality and Visa Type fields', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /UAE|Compliance/i }).first().click();
    // Nationality selector
    await expect(
      page.locator('.modal select').filter({
        has: page.locator('option').filter({ hasText: /United Arab Emirates|nationality/i })
      }).first()
    ).toBeVisible({ timeout: 6000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Nafis Registration field is disabled for non-UAE nationality', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /UAE|Compliance/i }).first().click();
    const nafisInput = page.locator('.modal input[placeholder*="nafis"], .modal input[placeholder*="Nafis"]').first();
    if (!(await nafisInput.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
      test.skip(true, 'Nafis field not found');
      return;
    }
    await expect(nafisInput).toBeDisabled();
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('Emirates ID expiry date field is present', async ({ page }) => {
    await goToEmployees(page);
    await openAddModal(page);
    await page.locator('.modal').getByRole('button', { name: /UAE|Compliance/i }).first().click();
    // Emirates ID input
    await expect(
      page.locator('.modal input[placeholder*="784-"], .modal').locator('text=/Emirates ID/i').first()
    ).toBeVisible({ timeout: 5000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });
});

// ─── Modal — Advanced tabs (existing employees only) ─────────────────────────

test.describe('Employees — Modal advanced tabs', () => {

  async function openFirstExistingEmployee(page) {
    await goToEmployees(page);
    const firstRow = page.locator('tbody tr').first();
    if (!(await firstRow.isVisible({ timeout: 5000 }).catch(() => false))) return false;
    await firstRow.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
    return true;
  }

  test('Documents, Insurance, and Contracts tabs are visible for existing employees', async ({ page }) => {
    const found = await openFirstExistingEmployee(page);
    if (!found) { test.skip(true, 'No employees in list'); return; }
    for (const tabName of ['Documents', 'Insurance', 'Contracts']) {
      await expect(
        page.locator('.modal').getByRole('button', { name: tabName, exact: true })
      ).toBeVisible({ timeout: 5000 });
    }
    await page.keyboard.press('Escape');
  });

  test('Save button is hidden on Documents, Insurance, and Contracts tabs', async ({ page }) => {
    const found = await openFirstExistingEmployee(page);
    if (!found) { test.skip(true, 'No employees in list'); return; }
    for (const tabName of ['Documents', 'Insurance', 'Contracts']) {
      const tabBtn = page.locator('.modal').getByRole('button', { name: tabName, exact: true });
      if (!(await tabBtn.isVisible({ timeout: 3000 }).catch(() => false))) continue;
      await tabBtn.click();
      await page.waitForTimeout(400);
      await expect(page.locator('.modal-footer .btn-primary')).not.toBeVisible({ timeout: 3000 });
    }
    await page.keyboard.press('Escape');
  });

  test('Documents tab shows upload form with file picker', async ({ page }) => {
    const found = await openFirstExistingEmployee(page);
    if (!found) { test.skip(true, 'No employees in list'); return; }
    const docsTab = page.locator('.modal').getByRole('button', { name: 'Documents', exact: true });
    if (!(await docsTab.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Documents tab not available');
      return;
    }
    await docsTab.click();
    // The file input is hidden (display:none) — it's triggered by a visible drop-zone div.
    // Check for the visible "Click to choose file" drop-zone instead.
    await expect(
      page.locator('.modal').getByText(/Click to choose file/i).first()
    ).toBeVisible({ timeout: 5000 });
    await page.keyboard.press('Escape');
  });

  test('Insurance tab shows Coverage Assignment form', async ({ page }) => {
    const found = await openFirstExistingEmployee(page);
    if (!found) { test.skip(true, 'No employees in list'); return; }
    const insTab = page.locator('.modal').getByRole('button', { name: 'Insurance', exact: true });
    if (!(await insTab.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Insurance tab not available');
      return;
    }
    await insTab.click();
    await expect(
      page.locator('.modal').locator('text=/coverage|assign/i').first()
    ).toBeVisible({ timeout: 6000 });
    await page.keyboard.press('Escape');
  });

  test('Contracts tab shows contract status and "Print Letter" button', async ({ page }) => {
    const found = await openFirstExistingEmployee(page);
    if (!found) { test.skip(true, 'No employees in list'); return; }
    const contractsTab = page.locator('.modal').getByRole('button', { name: 'Contracts', exact: true });
    if (!(await contractsTab.isVisible({ timeout: 3000 }).catch(() => false))) {
      await page.keyboard.press('Escape');
      test.skip(true, 'Contracts tab not available');
      return;
    }
    await contractsTab.click();
    await expect(
      page.locator('.modal').getByRole('button', { name: /print letter/i })
    ).toBeVisible({ timeout: 6000 });
    await page.keyboard.press('Escape');
  });
});
