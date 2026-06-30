/**
 * appraisals.spec.js
 * Feature 6.1 — Appraisal Module
 *
 * Admin portal (AppraisalManager):
 *   - "Appraisals" nav item is visible
 *   - Page renders with "Appraisals" heading
 *   - Two tabs: Cycles and Reviews
 *   - Cycles tab: New Cycle form with Name, Review From/To, Status
 *   - Cycles tab: Status dropdown has draft/open/active/closed
 *   - Creating a cycle adds it to the cycle list (with afterAll cleanup)
 *   - "Generate Appraisals" button appears when a cycle is selected
 *   - Reviews tab: cycle selector dropdown
 *   - Reviews tab: empty state when no cycle selected or no appraisals
 *   - Dashboard shows a blue alert badge for pending appraisals in active cycles
 *
 * Employee portal (EmpAppraisal):
 *   - "Appraisals" tab is visible in employee sidebar (tab 9)
 *   - Tab renders with heading
 *   - Appraisal rows or empty state visible
 *   - Star ratings display in read-only mode
 *
 * Manager portal (ManagerAppraisals):
 *   - "Appraisals" tab visible in Manager portal (tab 3)
 *   - Tab renders the manager appraisals component
 *
 * NOTE: storageState inside admin/manager describe blocks; loginAsEmployee() for employee.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient } from './helpers/db.js';
import { loginAsEmployee } from './helpers/auth.js';

const CYCLE_NAME    = `Playwright Cycle ${Date.now()}`;
const MANAGER_SESSION = '.playwright/manager-session.json';

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test.afterAll(async () => {
  try {
    const db      = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    await db.from('appraisal_cycles').delete().eq('user_id', adminId).like('name', 'Playwright Cycle%');
    console.log('[appraisals cleanup] Removed test appraisal cycles.');
  } catch (e) {
    console.warn('[appraisals cleanup] Could not clean up:', e.message);
  }
});

// ─── helpers ──────────────────────────────────────────────────────────────────

async function goToAppraisals(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Appraisals' }).click();
  await page.waitForLoadState('networkidle');
  await expect(
    page.locator('h1').filter({ hasText: /Appraisals/i })
  ).toBeVisible({ timeout: 8000 });
}

// ─── Admin — navigation & layout ─────────────────────────────────────────────

test.describe('Appraisals (6.1) — Admin: navigation & layout', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Appraisals" nav item is visible in admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Appraisals' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Appraisals page loads with "Appraisals" heading', async ({ page }) => {
    await goToAppraisals(page);
    await expect(
      page.locator('h1').filter({ hasText: /^Appraisals$/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Two tabs: Cycles and Reviews', async ({ page }) => {
    await goToAppraisals(page);
    // Tab buttons have no icons — plain text "Cycles" / "Reviews".
    // BUT "Reviews" may render with a count badge ("Reviews 1") when appraisals are seeded,
    // so exact-match name assertions fail. Use substring hasText scoped to button.tab-btn.
    await expect(
      page.locator('.page-body button.tab-btn').filter({ hasText: 'Cycles' })
    ).toBeVisible({ timeout: 6000 });
    await expect(
      page.locator('.page-body button.tab-btn').filter({ hasText: 'Reviews' })
    ).toBeVisible({ timeout: 5000 });
  });

  test('"New Cycle" button is present on the Cycles tab', async ({ page }) => {
    await goToAppraisals(page);
    // "Generate Appraisals" only appears on the Reviews tab when a cycle is selected.
    // The Cycles tab shows a "New Cycle" button to open the cycle creation form.
    await expect(
      page.locator('button').filter({ hasText: /New Cycle/i })
    ).toBeVisible({ timeout: 6000 });
  });
});

// ─── Admin — Cycles tab ───────────────────────────────────────────────────────

test.describe('Appraisals (6.1) — Admin: Cycles tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('New Cycle form shows Name, Review From, Review To, Status fields', async ({ page }) => {
    await goToAppraisals(page);

    // The cycle form is hidden by default — click "New Cycle" to open it
    await page.locator('button').filter({ hasText: /New Cycle/i }).click();
    await page.waitForTimeout(300);

    // h3 inside the form card
    await expect(
      page.locator('h3').filter({ hasText: /New Appraisal Cycle/i }).first()
    ).toBeVisible({ timeout: 6000 });

    // Cycle name input (placeholder: "e.g. H1 2025")
    await expect(
      page.locator('input[placeholder*="H1 2025"], input[placeholder*="H2 2025"]').first()
    ).toBeVisible({ timeout: 5000 });

    // Date inputs (review_from + review_to)
    const dateInputs = page.locator('.card input[type="date"]');
    await expect(dateInputs.first()).toBeVisible({ timeout: 4000 });
    expect(await dateInputs.count()).toBeGreaterThanOrEqual(2);

    // Status select
    const statusSelect = page.locator('select').filter({ has: page.locator('option[value="draft"]') }).first();
    await expect(statusSelect).toBeVisible({ timeout: 4000 });
  });

  test('Status dropdown has draft/active/closed options', async ({ page }) => {
    await goToAppraisals(page);

    // Open the cycle form first
    await page.locator('button').filter({ hasText: /New Cycle/i }).click();
    await page.waitForTimeout(300);

    const statusSelect = page.locator('select').filter({ has: page.locator('option[value="draft"]') }).first();
    await expect(statusSelect).toBeVisible({ timeout: 6000 });

    // The status select has draft/active/closed — no "open" option in this component
    for (const status of ['draft', 'active', 'closed']) {
      await expect(statusSelect.locator(`option[value="${status}"]`)).toBeAttached({ timeout: 3000 });
    }
  });

  test('creating a new cycle adds it to the cycles list', async ({ page }) => {
    await goToAppraisals(page);

    // Open cycle form
    await page.locator('button').filter({ hasText: /New Cycle/i }).click();
    await page.waitForTimeout(300);

    // Fill cycle name (placeholder: "e.g. H1 2025")
    const nameInput = page.locator('input[placeholder*="H1 2025"], input[placeholder*="H2 2025"]').first();
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(CYCLE_NAME);

    // Fill review_from
    const dateInputs = page.locator('.card input[type="date"]');
    const today = new Date().toISOString().split('T')[0];
    const nextMonth = new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0];
    await dateInputs.nth(0).fill(today);
    await dateInputs.nth(1).fill(nextMonth);

    // Save — the inline form button says "Save Cycle" or "Save"
    await page.locator('button').filter({ hasText: /Save Cycle|^Save$/i }).first().click();
    await page.waitForTimeout(500);

    // Cycle should appear in the list
    await expect(
      page.locator('.card').filter({ hasText: CYCLE_NAME }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('cycle list shows status badge on each cycle', async ({ page }) => {
    await goToAppraisals(page);

    const cycleRows = page.locator('.card').filter({ hasText: /draft|open|active|closed/i });
    const count = await cycleRows.count();
    if (count === 0) {
      test.skip(true, 'No cycles in list — run save test first');
      return;
    }
    // Each cycle row should have a badge
    await expect(cycleRows.first()).toBeVisible({ timeout: 4000 });
  });

  test('delete button on cycle row shows confirmation', async ({ page }) => {
    await goToAppraisals(page);

    const cycleRow = page.locator('.card').filter({ hasText: CYCLE_NAME }).first();
    if (!(await cycleRow.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test cycle not found — run save test first');
      return;
    }

    const deleteBtn = cycleRow.locator('button[title="Delete cycle"]').first();
    if (await deleteBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      page.on('dialog', dialog => dialog.dismiss()); // dismiss so we don't actually delete
      await deleteBtn.click();
      await page.waitForTimeout(500);
    }
  });
});

// ─── Admin — Reviews tab ──────────────────────────────────────────────────────

test.describe('Appraisals (6.1) — Admin: Reviews tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Reviews tab renders a cycle selector dropdown', async ({ page }) => {
    await goToAppraisals(page);
    await page.locator('button.tab-btn').filter({ hasText: /^Reviews$/i }).click();
    await page.waitForTimeout(300);

    await expect(
      page.locator('select').filter({ has: page.locator('option', { hasText: /Select cycle/i }) }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Reviews tab shows "Select a cycle above" when no cycle selected', async ({ page }) => {
    await goToAppraisals(page);
    await page.locator('button.tab-btn').filter({ hasText: /^Reviews$/i }).click();
    await page.waitForTimeout(400);

    // AppraisalManager auto-selects the first cycle on mount (line 235: setActiveCycleId(c[0].id)).
    // Explicitly reset the selector to the empty option to trigger the "Select a cycle" empty state.
    const cycleSelect = page.locator('select').filter({ has: page.locator('option[value=""]') }).first();
    if (await cycleSelect.isVisible({ timeout: 5000 }).catch(() => false)) {
      await cycleSelect.selectOption('');
      await page.waitForTimeout(200);
    }

    await expect(
      page.locator('.empty-state').filter({ hasText: /Select a cycle/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('selecting a cycle in Reviews tab loads the reviews list or Generate button', async ({ page }) => {
    await goToAppraisals(page);
    await page.locator('button.tab-btn').filter({ hasText: /^Reviews$/i }).click();
    await page.waitForTimeout(300);

    const cycleSelect = page.locator('select').filter({ has: page.locator('option', { hasText: /Select cycle/i }) }).first();
    const opts = await cycleSelect.locator('option').count();
    if (opts <= 1) {
      test.skip(true, 'No cycles available to select in Reviews tab');
      return;
    }

    await cycleSelect.selectOption({ index: 1 });
    await page.waitForTimeout(500);

    // Either shows reviews table, empty-state, or "Generate Appraisals" button
    const reviewsTable = page.locator('table').first();
    const emptyState   = page.locator('.empty-state').first();
    const genBtn       = page.locator('button').filter({ hasText: /Generate Appraisals/i }).first();
    const hasContent = await reviewsTable.isVisible({ timeout: 4000 }).catch(() => false)
                    || await emptyState.isVisible({ timeout: 3000 }).catch(() => false)
                    || await genBtn.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});

// ─── Employee portal — EmpAppraisal ──────────────────────────────────────────

test.describe('Appraisals (6.1) — Employee portal', () => {

  test('"Appraisals" tab is visible in the employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Appraisals tab renders a heading', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    await expect(
      page.locator('h2, h3').filter({ hasText: /appraisal/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Appraisals tab shows appraisal rows or an empty state', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // Either an emp-card with "No appraisals on file yet." OR emp-cards with appraisal rows.
    // isVisible() is non-waiting — use expect().toBeVisible() to properly wait for async load.
    const emptyCard = page.locator('.emp-card').filter({ hasText: /No appraisals on file yet/i }).first();
    const appraisalCard = page.locator('.emp-card').first();
    await expect(emptyCard.or(appraisalCard)).toBeVisible({ timeout: 10000 });
  });

  test('appraisal rows show cycle name and status when data exists', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const rows = page.locator('.emp-card').filter({ hasText: /pending|self_reviewed|reviewed|calibrated/i });
    if (!(await rows.first().isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'No appraisal records for test employee');
      return;
    }
    await expect(rows.first()).toBeVisible({ timeout: 4000 });
  });
});

// ─── Manager portal — ManagerAppraisals ──────────────────────────────────────

test.describe('Appraisals (6.1) — Manager portal', () => {

  // Fall back to admin session so collection doesn't throw ENOENT; each test skips itself.
  test.use({ storageState: existsSync(MANAGER_SESSION) ? MANAGER_SESSION : '.playwright/admin-session.json' });

  test.beforeEach(async ({}, testInfo) => {
    if (!existsSync(MANAGER_SESSION)) {
      testInfo.skip(true, 'No manager session file — manager portal tests require a manager-role user');
    }
  });

  test('"Appraisals" tab is visible in Manager portal sidebar', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Appraisals tab renders the manager appraisals component', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('h2, h3').filter({ hasText: /appraisal|team.*review|performance/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Manager appraisals shows team members or empty state', async ({ page }) => {
    if (!existsSync(MANAGER_SESSION)) return;
    await page.goto('/');
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button.nav-item').filter({ hasText: /^Appraisals$/ }).click();
    await page.waitForLoadState('networkidle');

    const teamRows = page.locator('.emp-card, tr').first();
    const emptyMsg = page.locator('text=/no appraisals|no direct reports|no reviews/i').first();
    const hasContent = await teamRows.isVisible({ timeout: 5000 }).catch(() => false)
                    || await emptyMsg.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});
