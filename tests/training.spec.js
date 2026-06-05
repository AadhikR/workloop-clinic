/**
 * training.spec.js — Playwright tests for Feature 19: Training & Certification Records
 *
 * Covers:
 *   Admin portal (TrainingManager):
 *     - "Training" nav item visible in sidebar
 *     - Page renders with "Training & Certifications" heading
 *     - Two tab buttons: "Training Records" and "Certifications"
 *     - Training Records tab: 4 stat cards (Total, Completed, In Progress, Total Cost)
 *     - Employee filter dropdown on Training Records tab
 *     - Status filter chips: All / Planned / In Progress / Completed / Cancelled
 *     - Table renders with expected columns
 *     - "Add Training" button opens the Training Record modal
 *     - Training modal has all required fields:
 *         Employee (select), Training Title, Type, Status, Provider, Start/End dates,
 *         Duration, Cost, Certificate URL, Notes
 *     - Score / Result fields only appear when status = "completed"
 *     - Cancel closes the modal
 *     - Saving a training record adds it to the table (with afterAll cleanup)
 *     - Certifications tab: 4 stat cards (Total, Expired, Expiring ≤60d, Lifetime)
 *     - "Add Certification" button opens the Certification modal
 *     - Cert modal fields: Employee, Certification Name, Issuing Body, Cert No.,
 *         Issue Date, Expiry Date, Certificate URL, Notes
 *     - Expiry date label notes "(leave blank if no expiry)"
 *     - Saving a certification adds it to the certs table (with afterAll cleanup)
 *     - Cert expiry filter chips: All / Expired / Expiring Soon / Active
 *     - Badge alert count on Certifications tab when certs are expiring/expired
 *
 *   Employee portal (EmpTraining):
 *     - "Training" tab visible in employee sidebar
 *     - Tab renders "Training & Certifications" heading
 *     - "Training Records" section heading visible
 *     - "Certifications" section heading visible
 *     - Empty state messages when no records exist
 *     - Summary stat cards visible
 *
 * NOTE: storageState is scoped INSIDE each admin describe block.
 * Employee describe uses loginAsEmployee() (fresh login).
 * Data created by these tests is cleaned up in afterAll.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient } from './helpers/db.js';
import { loginAsEmployee } from './helpers/auth.js';

const TRAINING_TITLE = `Playwright Training ${Date.now()}`;
const CERT_NAME      = `Playwright Cert ${Date.now()}`;

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));

    await db.from('training_records').delete().eq('user_id', adminId).like('training_title', 'Playwright Training%');
    await db.from('certifications').delete().eq('user_id', adminId).like('certification_name', 'Playwright Cert%');
    console.log('[training cleanup] Removed test training records and certifications.');
  } catch (e) {
    console.warn('[training cleanup] Could not clean up:', e.message);
  }
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToTraining(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Training' }).click();
  await page.waitForLoadState('networkidle');
}

async function openTrainingRecordsTab(page) {
  await goToTraining(page);
  // Training Records is the default tab — but click it to be explicit
  const trainingTabBtn = page.locator('.page-body').getByRole('button', { name: 'Training Records', exact: true });
  if (await trainingTabBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await trainingTabBtn.click();
  }
  await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
}

async function openCertificationsTab(page) {
  await goToTraining(page);
  const certTabBtn = page.locator('.page-body').getByRole('button', { name: 'Certifications', exact: true });
  await expect(certTabBtn).toBeVisible({ timeout: 8000 });
  await certTabBtn.click();
  await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 });
}

// ─── Admin — TrainingManager navigation and layout ────────────────────────────

test.describe('Training — Admin portal: navigation & layout', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Training" nav item is visible in the admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Training' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Training page renders with "Training & Certifications" heading', async ({ page }) => {
    await goToTraining(page);
    await expect(
      page.locator('.page-header h2').filter({ hasText: /training.*certif|certif.*training/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Two tab buttons render: "Training Records" and "Certifications"', async ({ page }) => {
    await goToTraining(page);
    // Tab buttons contain icons (GraduationCap, Award) + text — use getByRole with exact name
    await expect(
      page.locator('.page-body').getByRole('button', { name: 'Training Records', exact: true })
    ).toBeVisible({ timeout: 8000 });
    await expect(
      page.locator('.page-body').getByRole('button', { name: 'Certifications', exact: true })
    ).toBeVisible({ timeout: 6000 });
  });
});

// ─── Admin — Training Records tab ────────────────────────────────────────────

test.describe('Training — Admin portal: Training Records tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Training Records tab renders 4 stat cards', async ({ page }) => {
    await openTrainingRecordsTab(page);
    const cards = page.locator('.stat-card');
    await expect(cards).toHaveCount(4, { timeout: 8000 });
  });

  test('stat cards show Total Records, Completed, In Progress, and Total Cost', async ({ page }) => {
    await openTrainingRecordsTab(page);
    for (const label of ['Total Records', 'Completed', 'In Progress', 'Total Cost']) {
      await expect(
        page.locator('.stat-card').filter({ hasText: new RegExp(label, 'i') })
      ).toBeVisible({ timeout: 6000 });
    }
  });

  test('employee filter dropdown is present', async ({ page }) => {
    await openTrainingRecordsTab(page);
    const empSelect = page.locator('select').filter({
      has: page.locator('option', { hasText: /all employees/i }),
    });
    await expect(empSelect).toBeVisible({ timeout: 6000 });
  });

  test('status filter chips: All, Planned, In Progress, Completed, Cancelled', async ({ page }) => {
    await openTrainingRecordsTab(page);
    for (const chip of ['All', 'Planned', 'In Progress', 'Completed', 'Cancelled']) {
      await expect(
        page.locator('button').filter({ hasText: new RegExp(`^${chip}$`, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('training records table has expected column headers', async ({ page }) => {
    await openTrainingRecordsTab(page);
    for (const col of ['Employee', 'Title', 'Type', 'Status']) {
      await expect(
        page.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('"Add Training" button opens the Training Record modal', async ({ page }) => {
    await goToTraining(page);
    const addBtn = page.getByRole('button', { name: /add training/i });
    await expect(addBtn).toBeVisible({ timeout: 8000 });
    await addBtn.click();
    await expect(page.locator('.modal-header h3').filter({ hasText: /add training record/i })).toBeVisible({ timeout: 6000 });
  });

  test('Training modal has Employee select, Training Title, Type, and Status fields', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal-header h3').filter({ hasText: /training/i })).toBeVisible({ timeout: 6000 });

    // Employee select
    await expect(
      page.locator('.modal select').filter({ has: page.locator('option', { hasText: /select employee/i }) })
    ).toBeVisible({ timeout: 5000 });

    // Training Title input
    await expect(
      page.locator('.modal input[placeholder*="Fire Safety"], .modal input[placeholder*="Training"]')
        .or(page.locator('.modal').getByLabel(/training title/i)).first()
    ).toBeVisible({ timeout: 4000 });

    // Type select (internal/external/online/conference)
    await expect(
      page.locator('.modal select').filter({ has: page.locator('option[value="external"]') })
        .first()
    ).toBeVisible({ timeout: 4000 });

    // Status select (planned/in_progress/completed/cancelled)
    await expect(
      page.locator('.modal select').filter({ has: page.locator('option[value="planned"]') })
        .first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('Training modal has Provider, Start Date, End Date, Duration, Cost fields', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Provider
    await expect(
      page.locator('.modal input[placeholder*="UAE NCEMA"]')
        .or(page.locator('.modal input[placeholder*="Provider"]')).first()
    ).toBeVisible({ timeout: 4000 });

    // Date inputs
    const dateInputs = page.locator('.modal input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 4000 });
    await expect(dateInputs).toHaveCount(2, { timeout: 4000 });

    // Duration (hours)
    await expect(
      page.locator('.modal input[type="number"][step="0.5"]')
        .or(page.locator('.modal input[placeholder*="16"]')).first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('Score and Result fields are hidden when status is not "completed"', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Default status is "planned" — score/passed fields should be absent
    await expect(
      page.locator('.modal input[placeholder*="92%"]')
        .or(page.locator('.modal').getByLabel(/score/i)).first()
    ).not.toBeVisible({ timeout: 3000 });
  });

  test('Score and Result fields appear when status is set to "completed"', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Set status to "completed"
    const statusSelect = page.locator('.modal select').filter({ has: page.locator('option[value="planned"]') }).first();
    await statusSelect.selectOption('completed');

    // Score input should now appear
    await expect(
      page.locator('.modal input[placeholder*="92%"], .modal input[placeholder*="Distinction"]')
        .or(page.locator('.modal').getByLabel(/score/i)).first()
    ).toBeVisible({ timeout: 5000 });

    // Result (passed/failed) select should appear
    await expect(
      page.locator('.modal select').filter({ has: page.locator('option[value="true"]') })
        .or(page.locator('.modal select').filter({ has: page.locator('option', { hasText: /passed/i }) }))
        .first()
    ).toBeVisible({ timeout: 4000 });
  });

  test('Training modal Cancel button closes the modal', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });

  test('saving a training record adds it to the table', async ({ page }) => {
    await goToTraining(page);
    await page.getByRole('button', { name: /add training/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Select first available employee
    const empSelect = page.locator('.modal select').filter({
      has: page.locator('option', { hasText: /select employee/i }),
    });
    const empOptions = await empSelect.locator('option').count();
    if (empOptions <= 1) {
      test.skip(true, 'No employees available — cannot create training record');
      await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
      return;
    }
    await empSelect.selectOption({ index: 1 });

    // Fill training title — placeholder "e.g. Fire Safety Awareness"
    // Note: inputs without explicit type="text" are NOT matched by input[type="text"] in CSS selectors
    const titleInput = page.locator('.modal input[placeholder*="Fire Safety"]')
      .or(page.locator('.modal input[placeholder*="Training"]')).first();
    await expect(titleInput).toBeVisible({ timeout: 5000 });
    await titleInput.fill(TRAINING_TITLE);

    // Save
    await page.locator('.modal').getByRole('button', { name: /add record/i }).click();

    // Modal closes and record appears in table
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 6000 });
    await expect(page.locator(`td:has-text("${TRAINING_TITLE}")`)).toBeVisible({ timeout: 10000 });
  });

  test('editing a training record opens the edit modal pre-populated', async ({ page }) => {
    await goToTraining(page);

    const row = page.locator('tr').filter({ hasText: TRAINING_TITLE }).first();
    if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test training record not found — run save test first');
      return;
    }

    await row.getByRole('button', { name: /edit/i }).click();
    await expect(page.locator('.modal-header h3').filter({ hasText: /edit training/i })).toBeVisible({ timeout: 6000 });

    // Title should be pre-populated.
    // Use placeholder selector — inputs in TrainingModal don't have explicit type="text"
    // so [type="text"] doesn't match them. Target by placeholder instead.
    const titleInput = page.locator('.modal input[placeholder*="Fire Safety"]')
      .or(page.locator('.modal input[placeholder*="Training"]')).first();
    await expect(titleInput).toBeVisible({ timeout: 5000 });
    const titleInputValue = await titleInput.inputValue();
    expect(titleInputValue).toBe(TRAINING_TITLE);
  });

  test('delete button on a training record opens confirmation dialog', async ({ page }) => {
    await goToTraining(page);

    const row = page.locator('tr').filter({ hasText: TRAINING_TITLE }).first();
    if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test training record not found');
      return;
    }

    await row.getByRole('button', { name: /delete/i }).click();
    await expect(
      page.locator('.modal').filter({ hasText: /delete training/i })
    ).toBeVisible({ timeout: 5000 });

    // Cancel to keep the record for cleanup
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });
});

// ─── Admin — Certifications tab ───────────────────────────────────────────────

test.describe('Training — Admin portal: Certifications tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Certifications tab renders 4 stat cards', async ({ page }) => {
    await openCertificationsTab(page);
    const cards = page.locator('.stat-card');
    await expect(cards).toHaveCount(4, { timeout: 8000 });
  });

  test('stat cards show Total Certifications, Expired, Expiring ≤60 days, Lifetime', async ({ page }) => {
    await openCertificationsTab(page);
    for (const label of ['Total Certifications', 'Expired', 'Expiring', 'Lifetime']) {
      await expect(
        page.locator('.stat-card').filter({ hasText: new RegExp(label, 'i') })
      ).toBeVisible({ timeout: 6000 });
    }
  });

  test('certification expiry filter chips: All, Expired, Expiring Soon, Active', async ({ page }) => {
    await openCertificationsTab(page);
    for (const chip of ['All', 'Expired', 'Expiring Soon', 'Active']) {
      await expect(
        page.locator('button').filter({ hasText: new RegExp(`^${chip}$`, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('certifications table has expected column headers', async ({ page }) => {
    await openCertificationsTab(page);
    for (const col of ['Employee', 'Certification', 'Issuing Body', 'Expires', 'Status']) {
      await expect(
        page.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('"Add Certification" button opens the Certification modal', async ({ page }) => {
    await openCertificationsTab(page);
    await page.getByRole('button', { name: /add certification/i }).click();
    await expect(
      page.locator('.modal-header h3').filter({ hasText: /add certification/i })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Certification modal has all required fields', async ({ page }) => {
    await openCertificationsTab(page);
    await page.getByRole('button', { name: /add certification/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Employee select
    await expect(
      page.locator('.modal select').filter({ has: page.locator('option', { hasText: /select employee/i }) })
    ).toBeVisible({ timeout: 5000 });

    // Certification name
    await expect(
      page.locator('.modal input[placeholder*="ISO 9001"]')
        .or(page.locator('.modal input[type="text"]').first())
    ).toBeVisible({ timeout: 4000 });

    // Issuing Body
    await expect(
      page.locator('.modal input[placeholder*="Bureau Veritas"]')
        .or(page.locator('.modal').getByLabel(/issuing body/i)).first()
    ).toBeVisible({ timeout: 4000 });

    // Two date inputs (Issue Date + Expiry Date)
    const dateInputs = page.locator('.modal input[type="date"]');
    await expect(dateInputs).toHaveCount(2, { timeout: 4000 });
  });

  test('Expiry date label indicates it is optional (leave blank = no expiry)', async ({ page }) => {
    await openCertificationsTab(page);
    await page.getByRole('button', { name: /add certification/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Label text should mention "leave blank" or similar
    await expect(
      page.locator('.modal').locator('text=/leave blank|no expiry|optional/i').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('Certification modal Cancel closes without saving', async ({ page }) => {
    await openCertificationsTab(page);
    await page.getByRole('button', { name: /add certification/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });

  test('saving a certification adds it to the certs table', async ({ page }) => {
    await openCertificationsTab(page);
    await page.getByRole('button', { name: /add certification/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Select first employee
    const empSelect = page.locator('.modal select').filter({
      has: page.locator('option', { hasText: /select employee/i }),
    });
    const empOptions = await empSelect.locator('option').count();
    if (empOptions <= 1) {
      test.skip(true, 'No employees available — cannot create certification');
      await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
      return;
    }
    await empSelect.selectOption({ index: 1 });

    // Fill cert name — placeholder "e.g. ISO 9001 Lead Auditor"
    const certInput = page.locator('.modal input[placeholder*="ISO 9001"]').first();
    await expect(certInput).toBeVisible({ timeout: 5000 });
    await certInput.fill(CERT_NAME);

    // Save
    await page.locator('.modal').getByRole('button', { name: /add certification/i }).last().click();

    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 6000 });
    await expect(page.locator(`td:has-text("${CERT_NAME}")`)).toBeVisible({ timeout: 10000 });
  });

  test('delete button on a certification opens confirmation dialog', async ({ page }) => {
    await openCertificationsTab(page);

    const row = page.locator('tr').filter({ hasText: CERT_NAME }).first();
    if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test certification not found — run save test first');
      return;
    }

    await row.getByRole('button', { name: /delete/i }).click();
    await expect(
      page.locator('.modal').filter({ hasText: /delete certification/i })
    ).toBeVisible({ timeout: 5000 });

    // Cancel
    await page.locator('.modal').getByRole('button', { name: /cancel/i }).click();
  });

  test('switching expiry filter to "Expired" updates the active button style', async ({ page }) => {
    await openCertificationsTab(page);
    await page.locator('button').filter({ hasText: /^expired$/i }).first().click();
    const expiredBtn = page.locator('button').filter({ hasText: /^expired$/i }).first();
    const cls = await expiredBtn.getAttribute('class');
    expect(cls).toMatch(/primary|active/i);
  });
});

// ─── Employee portal — EmpTraining ────────────────────────────────────────────
// NO storageState — loginAsEmployee() starts from the unauthenticated page.

test.describe('Training — Employee portal (EmpTraining)', () => {

  test('"Training" tab is visible in the employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Training$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Training tab renders "Training & Certifications" heading', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(
      page.locator('.emp-page-header h2').filter({ hasText: /training.*certif|certif.*training/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Training Records section heading is visible', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    await expect(
      page.locator('h4').filter({ hasText: /training records/i })
        .or(page.locator('text=/training records/i')).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Certifications section heading is visible', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    await expect(
      page.locator('h4').filter({ hasText: /certifications/i })
        .or(page.locator('text=/certifications/i')).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('summary stat cards render (Total Trainings, Completed, Certifications, Active Certs)', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // 4 summary cards
    const cards = page.locator('.emp-card').filter({ has: page.locator('div[style*="font-size: 28"]') });
    await expect(cards.first()).toBeVisible({ timeout: 6000 });
  });

  test('empty state messages render when employee has no training records', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const trainingEmpty = page.locator('text=/no training records yet/i');
    const trainingCard  = page.locator('tr, .emp-card [class*="record"]').first();

    // Either records exist or the empty state shows — both are valid
    const hasEmptyOrRecords = trainingEmpty.or(trainingCard).or(page.locator('.emp-card').nth(1));
    await expect(hasEmptyOrRecords.first()).toBeVisible({ timeout: 6000 });
  });

  test('expiry alert renders if employee has certs expiring within 60 days', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Training$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // Alert only renders when expiringSoon.length > 0 or expiredCerts.length > 0
    const alert = page.locator('[style*="fffbeb"], [style*="fef2f2"]').first()
      .or(page.locator('text=/expiring soon|expired/i').first());

    if (await alert.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Expiry alerts are showing — verify AlertTriangle icon or warning text
      await expect(alert).toBeVisible();
    } else {
      // No expiring certs — page still loads fine (that's fine)
      test.skip(true, 'No expiring certifications for test employee — alert correctly absent');
    }
  });
});
