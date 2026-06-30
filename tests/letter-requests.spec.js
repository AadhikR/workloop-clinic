/**
 * letter-requests.spec.js
 * Feature 1.3 — Letter & Certificate Requests
 *
 * Admin portal (LetterRequestsManager):
 *   - "Letter Requests" nav item is visible
 *   - Page renders with "Letter Requests" heading
 *   - Filter tabs: All, Pending, Completed, Rejected
 *   - Pending count badge appears in sidebar when there are pending requests
 *   - Complete / Reject action buttons visible on pending rows (if data exists)
 *   - Reject inline form appears when Reject is clicked
 *
 * Employee portal (EmpRequests):
 *   - "Requests" tab is visible in employee sidebar
 *   - Tab renders a letter request form
 *   - Letter type selector includes all 7 letter types
 *   - Purpose textarea is present
 *   - Submit is disabled with empty purpose
 *   - Cancel hides the form (if form is toggled)
 *   - My Requests history section renders
 *
 * NOTE: storageState inside admin describe blocks; loginAsEmployee() for employee.
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';

const LETTER_TYPES = [
  'Salary Certificate — Bank',
  'Salary Certificate — Embassy',
  'Salary Certificate — Personal Use',
  'NOC (No Objection Certificate)',
  'Experience Letter',
  'Employment Certificate',
  'Salary Transfer Letter',
];

// ─── helpers ──────────────────────────────────────────────────────────────────

async function goToLetterRequests(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Letter Requests' }).click();
  await page.waitForLoadState('networkidle');
}

// ─── Admin — LetterRequestsManager ────────────────────────────────────────────

test.describe('Letter Requests (1.3) — Admin portal', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Letter Requests" nav item is visible in admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Letter Requests' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Letter Requests page renders with the correct heading', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(
      page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('filter buttons "Pending" and "All Requests" render', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()).toBeVisible({ timeout: 8000 });

    // LetterRequestsManager only has two filter buttons (not All/Pending/Completed/Rejected).
    // "Pending" button may show count badge ("Pending 3") so avoid anchored regex.
    await expect(
      page.locator('button').filter({ hasText: /Pending/i }).first()
    ).toBeVisible({ timeout: 5000 });
    await expect(
      page.locator('button').filter({ hasText: /All Requests/i }).first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('switching to "All Requests" filter updates the active button', async ({ page }) => {
    await goToLetterRequests(page);
    // Wait for filter buttons (only rendered after loading completes)
    await expect(page.locator('button').filter({ hasText: /All Requests/i }).first()).toBeVisible({ timeout: 8000 });

    const allBtn = page.locator('button').filter({ hasText: /All Requests/i }).first();
    await allBtn.click();
    const cls = await allBtn.getAttribute('class');
    expect(cls).toMatch(/primary|active/i);
  });

  test('table renders with expected column headers (if requests exist)', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()).toBeVisible({ timeout: 8000 });

    const table = page.locator('table').first();
    if (!(await table.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No letter requests in test data — table not rendered');
      return;
    }

    for (const col of ['Employee', 'Letter Type', 'Status']) {
      await expect(
        page.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('Complete button is present on pending rows when requests exist', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()).toBeVisible({ timeout: 8000 });

    const completeBtn = page.locator('button').filter({ hasText: /complete/i }).first();
    if (!(await completeBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No pending letter requests — Complete button correctly absent');
    }
    await expect(completeBtn).toBeVisible();
  });

  test('Reject button triggers inline reason input on pending rows', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()).toBeVisible({ timeout: 8000 });

    const rejectBtn = page.locator('button').filter({ hasText: /^reject$/i }).first();
    if (!(await rejectBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'No pending letter requests — Reject button correctly absent');
      return;
    }

    await rejectBtn.click();
    await expect(
      page.locator('input[placeholder*="reason"], textarea[placeholder*="reason"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('stat cards or summary section renders on the page', async ({ page }) => {
    await goToLetterRequests(page);
    await expect(page.locator('h1, h2').filter({ hasText: /Letter Requests/i }).first()).toBeVisible({ timeout: 8000 });

    // Either stat cards or a table or an empty state — page should have meaningful content
    const body = page.locator('.page-body');
    await expect(body).toBeVisible({ timeout: 5000 });
    const childCount = await body.locator('> *').count();
    expect(childCount).toBeGreaterThan(0);
  });
});

// ─── Employee portal — EmpRequests ───────────────────────────────────────────

test.describe('Letter Requests (1.3) — Employee portal', () => {

  test('"Requests" tab is visible in employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Requests$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Requests tab renders a letter request form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // Form heading or select for letter type
    await expect(
      page.locator('select').filter({
        has: page.locator('option', { hasText: /salary certificate|NOC|experience/i }),
      }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Letter type selector contains all 7 letter types', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const typeSelect = page.locator('select').filter({
      has: page.locator('option', { hasText: /salary certificate/i }),
    }).first();
    await expect(typeSelect).toBeVisible({ timeout: 6000 });

    const options = await typeSelect.locator('option').allTextContents();
    for (const lt of LETTER_TYPES) {
      const found = options.some(o => o.trim() === lt);
      expect(found, `Expected letter type option: "${lt}"`).toBe(true);
    }
  });

  test('Purpose input is present in the form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // EmpRequests uses a plain <input> (not textarea) with placeholder referencing "Abu Dhabi Islamic Bank".
    // Use .or().first() order — .first().or() is an invalid chain per CLAUDE.md.
    await expect(
      page.locator('input[placeholder*="Abu Dhabi"], input[placeholder*="purpose"]')
        .or(page.locator('.emp-card input.form-control').nth(1))
        .first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Submit Request button is present and enabled (purpose is optional)', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // EmpRequests.jsx: purpose is "(optional)" — the Submit button is enabled even when empty.
    // disabled={submitting} only — disabled solely while a request is in flight.
    const submitBtn = page.locator('button').filter({ hasText: /submit request|request letter/i }).first();
    await expect(submitBtn).toBeVisible({ timeout: 6000 });
    await expect(submitBtn).toBeEnabled();
  });

  test('My Requests section renders (with h3 "My Requests")', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // EmpRequests renders a card with h3 "My Requests (N)" — always present after load.
    // Uses proper waiting (not non-waiting isVisible) to handle async data load.
    await expect(
      page.locator('h3').filter({ hasText: /My Requests/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('selecting a letter type updates the dropdown value', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Requests$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const typeSelect = page.locator('select').filter({
      has: page.locator('option', { hasText: /salary certificate/i }),
    }).first();
    await typeSelect.selectOption('NOC (No Objection Certificate)');
    const val = await typeSelect.inputValue();
    expect(val).toBe('NOC (No Objection Certificate)');
  });
});
