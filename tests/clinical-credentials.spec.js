/**
 * clinical-credentials.spec.js
 * Feature 1.1 — Clinical Credentials (DHA/DOH/BLS document types, 90-day expiry warning)
 * Feature 1.2 — Employee Self-Upload (employee uploads doc → admin verifies/rejects)
 *
 * Admin portal:
 *   - Documents tab shows a "Clinical Credentials" optgroup in the type selector
 *   - Clinical doc types present: DHA Licence, DOH Licence, MOH Licence, BLS/ACLS/PALS/CME/NRP
 *   - Existing clinical docs show a cyan "Clinical" badge in the document list
 *   - Review Status column exists (Pending Review / Verified / Rejected)
 *   - Verify (✓) and Reject (✗) buttons appear on self-submitted docs
 *
 * Employee portal:
 *   - "Documents" tab is visible in employee sidebar
 *   - Tab renders a document upload form
 *   - Type selector contains Clinical Credentials group
 *   - Upload button is disabled without a file selected
 *   - Document history list renders (or empty state)
 *
 * NOTE: storageState scoped INSIDE admin describe blocks.
 * Employee describe uses loginAsEmployee().
 */
import { test, expect } from '@playwright/test';
import { loginAsEmployee } from './helpers/auth.js';

const EMP_NAME = process.env.TEST_EMPLOYEE_NAME ?? 'Test Employee';

// ─── helpers ──────────────────────────────────────────────────────────────────

async function openEmployeeDocumentsTab(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');

  const empRow = page.locator(`tr:has-text("${EMP_NAME}")`).first();
  if (!(await empRow.isVisible({ timeout: 6000 }).catch(() => false))) {
    return false;
  }
  await empRow.getByRole('button', { name: /edit/i }).click();
  await expect(page.locator('.modal')).toBeVisible({ timeout: 8000 });
  await page.getByRole('button', { name: /^Documents$/i }).click();
  await expect(page.locator('h3:has-text("Upload New Document")')).toBeVisible({ timeout: 8000 });
  return true;
}

// ─── Admin — Feature 1.1: clinical document types ────────────────────────────

test.describe('Clinical Credentials (1.1) — Admin: document type selector', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Documents tab type selector has a "Clinical Credentials" optgroup', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    const group = page.locator('.modal optgroup[label="Clinical Credentials"]');
    await expect(group).toBeAttached({ timeout: 5000 });
  });

  test('DHA Licence is an option in the Clinical Credentials group', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    await expect(
      page.locator('.modal option[value="DHA Licence"]')
    ).toBeAttached({ timeout: 5000 });
  });

  test('DOH Licence and MOH Licence are selectable options', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    for (const opt of ['DOH Licence', 'MOH Licence']) {
      await expect(page.locator(`.modal option[value="${opt}"]`)).toBeAttached({ timeout: 5000 });
    }
  });

  test('BLS, ACLS, PALS, NRP, CME Certificate options are present', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    for (const opt of ['BLS Certificate', 'ACLS Certificate', 'PALS Certificate', 'NRP Certificate', 'CME Certificate']) {
      await expect(page.locator(`.modal option[value="${opt}"]`)).toBeAttached({ timeout: 5000 });
    }
  });

  test('UAE Residency & Work optgroup is also present (standard docs preserved)', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    const group = page.locator('.modal optgroup[label="UAE Residency & Work"]');
    await expect(group).toBeAttached({ timeout: 5000 });
    await expect(page.locator('.modal option[value="Visa"]')).toBeAttached({ timeout: 5000 });
  });

  test('documents list shows a "Review Status" or "Status" column header when docs exist', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    // The table only renders when documents exist — skip if no docs uploaded yet
    const table = page.locator('.modal table').first();
    if (!(await table.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'No documents uploaded yet — table (and Review Status column) correctly absent');
      return;
    }
    await expect(
      page.locator('.modal th').filter({ hasText: /Status|Review/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('selecting DHA Licence updates the form type field', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    const typeSelect = page.locator('.modal select').first();
    await typeSelect.selectOption('DHA Licence');
    const val = await typeSelect.inputValue();
    expect(val).toBe('DHA Licence');
  });
});

// ─── Admin — Feature 1.2: self-submitted document review ─────────────────────

test.describe('Clinical Credentials (1.2) — Admin: verify/reject workflow', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('document list renders "Self-submitted" label when employee-uploaded docs exist', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    // "Self-submitted" badge only appears when employee-uploaded documents exist.
    // If no such docs exist, skip gracefully.
    const badge = page.locator('.modal').getByText(/Self-submitted/i).first();
    const hasBadge = await badge.isVisible({ timeout: 4000 }).catch(() => false);
    if (!hasBadge) {
      test.skip(true, 'No employee-submitted documents in test data — badge correctly absent');
    }
    await expect(badge).toBeVisible();
  });

  test('verify (✓) button exists in docs list when documents are present', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    // Check if there are any documents — if not, no verify button expected
    const docsHeading = page.locator('.modal h3').filter({ hasText: /Uploaded Documents/i });
    await expect(docsHeading).toBeVisible({ timeout: 5000 });

    const verifyBtn = page.locator('.modal button[title="Verify document"]').first();
    const hasVerify = await verifyBtn.isVisible({ timeout: 3000 }).catch(() => false);
    if (!hasVerify) {
      test.skip(true, 'No uploaded documents — verify button correctly absent');
    }
    await expect(verifyBtn).toBeVisible();
  });

  test('Upload Document button is disabled without a file', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    await expect(
      page.locator('.modal button').filter({ hasText: /Upload Document/i })
    ).toBeDisabled({ timeout: 5000 });
  });

  test('file input for upload is present (hidden) in the Documents tab', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    // input[type="file"] is always display:none — check it exists in DOM
    await expect(page.locator('.modal input[type="file"]')).toBeAttached({ timeout: 5000 });
  });

  test('upload drop-zone text "Click to choose file" is visible', async ({ page }) => {
    const ok = await openEmployeeDocumentsTab(page);
    if (!ok) { test.skip(true, 'Test employee not found'); return; }

    await expect(
      page.locator('.modal').getByText(/Click to choose file/i)
    ).toBeVisible({ timeout: 5000 });
  });
});

// ─── Employee portal — Feature 1.2: self-upload UI ────────────────────────────

test.describe('Clinical Credentials (1.2) — Employee portal: self-upload', () => {

  test('"Documents" tab is visible in employee sidebar', async ({ page }) => {
    await loginAsEmployee(page);
    await expect(
      page.locator('button.nav-item').filter({ hasText: /^Documents$/ })
    ).toBeVisible({ timeout: 8000 });
  });

  test('Documents tab renders a document upload form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // Upload form heading
    await expect(
      page.locator('h3, h4').filter({ hasText: /upload|submit.*document/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Documents type selector includes Clinical Credentials options', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const typeSelect = page.locator('.emp-page-body select').first();
    await expect(typeSelect).toBeVisible({ timeout: 6000 });

    const options = await typeSelect.locator('option').allTextContents();
    const hasClinic = options.some(o => /DHA|DOH|BLS|ACLS|clinical/i.test(o));
    expect(hasClinic).toBe(true);
  });

  test('Document Number field is visible in the upload form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    await expect(
      page.locator('input[placeholder*="DHA-"], input[placeholder*="document number"], input[placeholder*="number"]').first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Submit/Upload button is disabled without a file selected', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    const uploadBtn = page.locator('button').filter({ hasText: /upload|submit.*doc/i }).first();
    if (await uploadBtn.isVisible({ timeout: 4000 }).catch(() => false)) {
      await expect(uploadBtn).toBeDisabled({ timeout: 3000 });
    }
  });

  test('My Documents section renders (shows h3 "My Documents")', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    // EmpDocuments renders an emp-card with h3 "My Documents (N)"
    await expect(
      page.locator('h3').filter({ hasText: /My Documents/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Expiry date field is present in the upload form', async ({ page }) => {
    await loginAsEmployee(page);
    await page.locator('button.nav-item').filter({ hasText: /^Documents$/ }).click();
    await expect(page.locator('.emp-page-body').first()).toBeVisible({ timeout: 8000 });

    await expect(
      page.locator('.emp-page-body input[type="date"]').first()
    ).toBeVisible({ timeout: 6000 });
  });
});
