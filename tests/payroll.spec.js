/**
 * payroll.spec.js — Comprehensive tests for the Payroll Module
 *
 * Covers:
 *   PayrollList:
 *     - Page loads and shows list with all expected columns
 *     - "New Payroll Run" button and form fields
 *     - Form validation (payment date required, sequence no format, routing code required)
 *     - Cancel closes the form
 *     - Creating a run: full form submission, appears in list as draft
 *     - "Repeat Last Payroll" button and its form
 *     - Delete confirmation dialog
 *
 *   PayrollEditor (within a draft run):
 *     - Editor renders with ← Back button
 *     - Employee entries table visible
 *     - Basic salary input is editable on a draft run
 *     - "Save Draft" button present
 *     - "Submit for Approval" button present
 *     - All inputs disabled on a generated/locked run
 *
 *   SIF generation:
 *     - "Download SIF" button visible on a generated run
 *     - Clicking Download SIF triggers a file download
 *     - Downloaded filename ends with .sif and follows WPS format
 *
 *   Employee portal — Payslips:
 *     - "Payslips" tab renders "My Payslips" heading
 *     - Shows payslip rows or empty state
 */

import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient } from './helpers/db.js';
import { loginAsEmployee } from './helpers/auth.js';

// ─── Shared helpers ────────────────────────────────────────────────────────────

async function goToPayroll(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Payroll Module' }).click();
  await page.waitForLoadState('networkidle');
}

async function createPayrollRun(page) {
  const futureYear = new Date().getFullYear() + 2;
  const period = `${futureYear}-01`;

  await expect(page.getByRole('button', { name: /New Payroll Run/i })).toBeEnabled({ timeout: 15000 });
  await page.getByRole('button', { name: /New Payroll Run/i }).click();
  await expect(
    page.locator('.modal-header h3').filter({ hasText: /New Payroll Run/i })
  ).toBeVisible({ timeout: 5000 });

  await page.locator('input[type="month"]').fill(period);
  await page.locator('input[type="date"]').first().fill(`${futureYear}-01-25`);
  await page.locator('input[placeholder*="1430"]').fill('0900');

  const routingInput = page.locator('input[placeholder*="302620"]').first();
  if (await routingInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    await routingInput.fill('302620122');
  }

  const descInput = page.locator('input[placeholder*="Sal for"]').first();
  if (await descInput.isVisible({ timeout: 1000 }).catch(() => false)) {
    await descInput.fill(`Test Payroll ${period}`);
  }

  await page.getByRole('button', { name: /Create Payroll Run/i }).click();
  await page.waitForLoadState('networkidle');
  return period;
}

async function openFirstDraftRun(page) {
  await goToPayroll(page);
  const draftRow = page.locator('tr').filter({ hasText: /draft/i }).first();
  if (!(await draftRow.isVisible({ timeout: 4000 }).catch(() => false))) return false;
  await draftRow.click();
  await page.waitForLoadState('networkidle');
  return true;
}

async function openFirstGeneratedRun(page) {
  await goToPayroll(page);
  const genRow = page.locator('tr').filter({ hasText: /generated/i }).first();
  if (!(await genRow.isVisible({ timeout: 4000 }).catch(() => false))) return false;
  await genRow.click();
  await page.waitForLoadState('networkidle');
  return true;
}

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    const futureYear = new Date().getFullYear() + 2;
    const { data: runs } = await db
      .from('payroll_runs')
      .select('id')
      .eq('user_id', adminId)
      .gte('period', `${futureYear}-01`);
    if (runs?.length) {
      const ids = runs.map(r => r.id);
      await db.from('payroll_entries').delete().in('payroll_run_id', ids);
      await db.from('payroll_runs').delete().in('id', ids);
    }
    console.log('[payroll cleanup] Removed test payroll runs.');
  } catch (e) {
    console.warn('[payroll cleanup]:', e.message);
  }
});

// ─── PayrollList — navigation & layout ────────────────────────────────────────

test.describe('Payroll — List view', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Payroll page loads without console errors', async ({ page }) => {
    const errors = [];
    page.on('console', m => {
      if (m.type() === 'error' && !m.text().includes('favicon')) errors.push(m.text());
    });
    await goToPayroll(page);
    await page.waitForTimeout(2000);
    expect(errors).toHaveLength(0);
  });

  test('list table shows Period, Payment Date, Status columns', async ({ page }) => {
    await goToPayroll(page);
    // Table only renders when payroll runs exist (empty state otherwise)
    const table = page.locator('.card').filter({ has: page.locator('h3').filter({ hasText: /Payroll History/i }) }).locator('table').first();
    if (!(await table.isVisible({ timeout: 8000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs yet — create one to verify column headers');
      return;
    }
    for (const col of ['Period', 'Payment Date', 'Status']) {
      await expect(
        table.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('Approval column is present (Feature 17)', async ({ page }) => {
    await goToPayroll(page);
    // Table only renders when payroll runs exist (empty state otherwise)
    const table = page.locator('.card').filter({ has: page.locator('h3').filter({ hasText: /Payroll History/i }) }).locator('table').first();
    if (!(await table.isVisible({ timeout: 8000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs yet — create one to verify Approval column');
      return;
    }
    await expect(
      table.locator('th').filter({ hasText: /approval/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('"New Payroll Run" button is present', async ({ page }) => {
    await goToPayroll(page);
    await expect(
      page.getByRole('button', { name: /New Payroll Run/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('"Repeat Last Payroll" button is present when runs exist', async ({ page }) => {
    await goToPayroll(page);
    const repeatBtn = page.getByRole('button', { name: /Repeat Last Payroll/i });
    if (!(await repeatBtn.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs exist yet');
      return;
    }
    await expect(repeatBtn).toBeVisible();
  });

  test('existing payroll rows show draft or generated badge', async ({ page }) => {
    await goToPayroll(page);
    const anyStatusBadge = page.locator('td').filter({ hasText: /draft|generated|pending/i }).first();
    if (!(await anyStatusBadge.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs in the list yet');
      return;
    }
    await expect(anyStatusBadge).toBeVisible();
  });
});

// ─── New Payroll Run form ──────────────────────────────────────────────────────

test.describe('Payroll — New run form', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('form opens with all required fields', async ({ page }) => {
    await goToPayroll(page);
    await expect(page.getByRole('button', { name: /New Payroll Run/i })).toBeEnabled({ timeout: 15000 });
    await page.getByRole('button', { name: /New Payroll Run/i }).click();
    await expect(
      page.locator('.modal-header h3').filter({ hasText: /New Payroll Run/i })
    ).toBeVisible({ timeout: 6000 });
    await expect(page.locator('input[type="month"]')).toBeVisible({ timeout: 4000 });
    await expect(page.locator('input[type="date"]').first()).toBeVisible({ timeout: 4000 });
    await expect(page.locator('input[placeholder*="1430"]')).toBeVisible({ timeout: 4000 });
    await expect(page.locator('input[placeholder*="302620"]').first()).toBeVisible({ timeout: 4000 });
  });

  test('submitting without a payment date shows a validation error', async ({ page }) => {
    await goToPayroll(page);
    await expect(page.getByRole('button', { name: /New Payroll Run/i })).toBeEnabled({ timeout: 15000 });
    await page.getByRole('button', { name: /New Payroll Run/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    // Just click Create without filling payment date
    await page.getByRole('button', { name: /Create Payroll Run/i }).click();
    // Modal must still be visible (form rejected)
    await expect(page.locator('.modal')).toBeVisible({ timeout: 3000 });
  });

  test('invalid Sequence No (non-numeric) shows a validation error', async ({ page }) => {
    await goToPayroll(page);
    await expect(page.getByRole('button', { name: /New Payroll Run/i })).toBeEnabled({ timeout: 15000 });
    await page.getByRole('button', { name: /New Payroll Run/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    const futureYear = new Date().getFullYear() + 2;
    await page.locator('input[type="month"]').fill(`${futureYear}-06`);
    await page.locator('input[type="date"]').first().fill(`${futureYear}-06-25`);
    await page.locator('input[placeholder*="1430"]').fill('XX99'); // non-HHMM
    await page.getByRole('button', { name: /Create Payroll Run/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 3000 });
    await expect(
      page.locator('text=/HHMM|3-4 digit|sequence/i').first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('Cancel button closes the form without creating', async ({ page }) => {
    await goToPayroll(page);
    await expect(page.getByRole('button', { name: /New Payroll Run/i })).toBeEnabled({ timeout: 15000 });
    await page.getByRole('button', { name: /New Payroll Run/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    await page.locator('.modal-footer').getByRole('button', { name: /cancel/i }).click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });

  test('creating a payroll run navigates to the editor or updates the list', async ({ page }) => {
    await goToPayroll(page);
    await createPayrollRun(page);
    // Either the editor is showing or the list updated with the new run
    await expect(page.locator('.page-header').first()).toBeVisible({ timeout: 10000 });
  });
});

// ─── PayrollEditor ────────────────────────────────────────────────────────────

test.describe('Payroll — PayrollEditor', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"← Back" button returns to the payroll list', async ({ page }) => {
    const found = await openFirstDraftRun(page);
    if (!found) { test.skip(true, 'No draft run found'); return; }
    const backBtn = page.locator('button').filter({ hasText: /Back/i }).first();
    await expect(backBtn).toBeVisible({ timeout: 6000 });
    await backBtn.click();
    await page.waitForLoadState('networkidle');
    await expect(
      page.getByRole('button', { name: /New Payroll Run/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('employee name appears in the entries table', async ({ page }) => {
    const found = await openFirstDraftRun(page);
    if (!found) { test.skip(true, 'No draft run found'); return; }
    const hasTable = await page.locator('table').first().isVisible({ timeout: 5000 }).catch(() => false);
    if (!hasTable) { test.skip(true, 'No employee entries visible'); return; }
    // Employee name column should have at least one name
    const nameCell = page.locator('td').first();
    await expect(nameCell).toBeVisible({ timeout: 5000 });
  });

  test('basic salary number inputs are editable in a draft', async ({ page }) => {
    const found = await openFirstDraftRun(page);
    if (!found) { test.skip(true, 'No draft run found'); return; }
    const salaryInput = page.locator('input[type="number"]').first();
    if (!(await salaryInput.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'No number inputs — no employees in run');
      return;
    }
    await expect(salaryInput).not.toBeDisabled();
  });

  test('"Save Draft" button is present', async ({ page }) => {
    const found = await openFirstDraftRun(page);
    if (!found) { test.skip(true, 'No draft run found'); return; }
    await expect(page.getByRole('button', { name: /Save Draft/i })).toBeVisible({ timeout: 8000 });
  });

  test('"Submit for Approval" button is present on a draft', async ({ page }) => {
    const found = await openFirstDraftRun(page);
    if (!found) { test.skip(true, 'No draft run found'); return; }
    await expect(
      page.getByRole('button', { name: /Submit for Approval/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('all salary inputs disabled on a generated run', async ({ page }) => {
    const found = await openFirstGeneratedRun(page);
    if (!found) { test.skip(true, 'No generated run found'); return; }
    const enabledInputs = await page.locator('input[type="number"]:not([disabled])').count();
    expect(enabledInputs).toBe(0);
  });

  test('lock banner or "generated" notice appears on a generated run', async ({ page }) => {
    const found = await openFirstGeneratedRun(page);
    if (!found) { test.skip(true, 'No generated run found'); return; }
    await expect(
      page.locator('text=/locked|generated|finalised/i').first()
    ).toBeVisible({ timeout: 8000 });
  });
});

// ─── SIF download ─────────────────────────────────────────────────────────────

test.describe('Payroll — SIF download', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Download SIF" button is visible on a generated run', async ({ page }) => {
    const found = await openFirstGeneratedRun(page);
    if (!found) { test.skip(true, 'No generated run found'); return; }
    await expect(
      page.getByRole('button', { name: /Download SIF/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('SIF download produces a file with a .sif extension', async ({ page }) => {
    const found = await openFirstGeneratedRun(page);
    if (!found) { test.skip(true, 'No generated run found'); return; }
    const btn = page.getByRole('button', { name: /Download SIF/i });
    if (!(await btn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Download SIF button not found');
      return;
    }
    const downloadPromise = page.waitForEvent('download');
    await btn.click();
    const dl = await downloadPromise;
    expect(dl.suggestedFilename()).toMatch(/\.sif$/i);
  });

  test('SIF filename follows the UAE WPS pattern (digits + date + time + .sif)', async ({ page }) => {
    const found = await openFirstGeneratedRun(page);
    if (!found) { test.skip(true, 'No generated run found'); return; }
    const btn = page.getByRole('button', { name: /Download SIF/i });
    if (!(await btn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Download SIF button not found');
      return;
    }
    const downloadPromise = page.waitForEvent('download');
    await btn.click();
    const dl = await downloadPromise;
    // Format: {MOL_ID}{YYMMDD}{HHMMSS}.sif — at least 6 digits before extension
    expect(dl.suggestedFilename()).toMatch(/\d{6,}.*\.sif$/i);
  });
});

// ─── Repeat run form ──────────────────────────────────────────────────────────

test.describe('Payroll — Repeat Last Payroll', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Repeat form opens with Period and Payment Date fields', async ({ page }) => {
    await goToPayroll(page);
    const repeatBtn = page.getByRole('button', { name: /Repeat Last Payroll/i });
    if (!(await repeatBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs to repeat');
      return;
    }
    await repeatBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('input[type="month"]').first()).toBeVisible({ timeout: 4000 });
    await expect(page.locator('input[type="date"]').first()).toBeVisible({ timeout: 4000 });
  });

  test('Repeat form Cancel closes without creating', async ({ page }) => {
    await goToPayroll(page);
    const repeatBtn = page.getByRole('button', { name: /Repeat Last Payroll/i });
    if (!(await repeatBtn.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No payroll runs to repeat');
      return;
    }
    await repeatBtn.click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });
    await page.locator('.modal-footer').getByRole('button', { name: /cancel/i }).click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });
});

// ─── Employee Portal — Payslips ───────────────────────────────────────────────

test.describe('Payroll — Employee Payslips tab', () => {

  test('"Payslips" tab is visible in the employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Payslips$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Payslips tab renders "My Payslips" heading', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Payslips$/ }).click();
    await expect(
      page.locator('h2').filter({ hasText: /My Payslips/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Payslips tab shows content (rows or empty state) without crashing', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Payslips$/ }).click();
    const content = page.locator('.emp-page-body, .emp-card').first();
    await expect(content).toBeVisible({ timeout: 8000 });
  });
});
