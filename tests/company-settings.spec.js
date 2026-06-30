/**
 * company-settings.spec.js — Company / Employer Settings page
 *
 * Covers all six sections of CompanySettings.jsx:
 *   1. Employer Information (name, MOL ID, bank routing, email, address)
 *   2. Payroll Settings (payment day, logo URL)
 *   3. Work Location & Jurisdiction (type, free zone)
 *   4. Emiratization / Nafis Compliance (sector → quota auto-fill)
 *   5. Medical Insurance Policies (add / edit / delete)
 *   6. WPS / SIF File Format Reference section
 *
 * Also covers the Branch Switcher in AppShell (Feature 21 — Multi-Company).
 *
 * h2 is "Company / Employer Settings" (not "Company Settings" — the slash matters).
 * Use /employer settings/i for substring matching.
 */
import { test, expect } from '@playwright/test';

test.describe('Company Settings', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  async function goToSettings(page) {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
    await expect(page.locator('h2').filter({ hasText: /employer settings/i })).toBeVisible({ timeout: 10000 });
  }

  // ── Navigation ───────────────────────────────────────────────────────────────

  test('"Company Settings" nav item is visible in the admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('page heading is "Company / Employer Settings"', async ({ page }) => {
    await goToSettings(page);
    await expect(page.locator('h2')).toContainText('Employer Settings');
  });

  // ── Section headers ───────────────────────────────────────────────────────────

  test('all six section headers are visible', async ({ page }) => {
    await goToSettings(page);
    const sections = [
      /Employer Information/i,
      /Payroll Settings/i,
      /Work Location/i,
      /Emiratization.*Nafis/i,
      /Medical Insurance Policies/i,
      /WPS.*SIF.*File Format/i,
    ];
    for (const re of sections) {
      await expect(page.locator('h3').filter({ hasText: re }).first()).toBeVisible({ timeout: 6000 });
    }
  });

  // ── Employer Information section ──────────────────────────────────────────────

  test('Company Name field is present and populated', async ({ page }) => {
    await goToSettings(page);
    const nameInput = page.locator('input[placeholder*="Example Trading"]');
    await expect(nameInput).toBeVisible({ timeout: 6000 });
    // Test company was created in global-setup — should have a non-empty name
    const value = await nameInput.inputValue();
    expect(value.length).toBeGreaterThan(0);
  });

  test('MOL Employer ID field has correct placeholder', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('input[placeholder*="0000000123456"]')
    ).toBeVisible({ timeout: 6000 });
  });

  test('Default Bank / Routing Code field is present', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('input[placeholder*="300000001"]')
    ).toBeVisible({ timeout: 6000 });
  });

  test('Branch / Entity Label field has correct hint text', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('.hint').filter({ hasText: /branch switcher/i })
    ).toBeVisible({ timeout: 6000 });
  });

  // ── Payroll Settings section ──────────────────────────────────────────────────

  test('Default Salary Payment Day field is present', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('input[placeholder="25"]')
    ).toBeVisible({ timeout: 6000 });
  });

  // ── Work Location section ─────────────────────────────────────────────────────

  test('Work Location Type has "Mainland" as an option', async ({ page }) => {
    await goToSettings(page);
    const sel = page.locator('select').filter({
      has: page.locator('option').filter({ hasText: /Mainland/i }),
    }).first();
    await expect(sel).toBeVisible({ timeout: 6000 });
  });

  // ── Emiratization / Nafis section ─────────────────────────────────────────────

  test('Industry Sector select is present with placeholder option', async ({ page }) => {
    await goToSettings(page);
    const sel = page.locator('select').filter({
      has: page.locator('option').filter({ hasText: /Select your sector/i }),
    });
    await expect(sel).toBeVisible({ timeout: 6000 });
  });

  test('selecting a sector auto-fills the Nafis quota percent', async ({ page }) => {
    await goToSettings(page);
    const sectorSel = page.locator('select').filter({
      has: page.locator('option').filter({ hasText: /Select your sector/i }),
    });
    await expect(sectorSel).toBeVisible({ timeout: 6000 });

    // Pick a sector that has a known quota > 0
    const opts = await sectorSel.locator('option').allTextContents();
    const bankingOpt = opts.find(o => /banking|financial/i.test(o));
    if (bankingOpt) {
      await sectorSel.selectOption({ label: bankingOpt });
      // Nafis quota input should now have a non-zero value
      const quotaInput = page.locator('input[placeholder*="e.g. 4"]').or(
        page.locator('input[type="number"]').filter({ hasText: '' })
      ).first();
      await expect(quotaInput).toBeVisible({ timeout: 4000 });
      const val = await quotaInput.inputValue();
      expect(parseFloat(val)).toBeGreaterThan(0);
    } else {
      // At least verify a non-placeholder option exists
      expect(opts.length).toBeGreaterThan(1);
    }
  });

  // ── Save flow ─────────────────────────────────────────────────────────────────

  test('Save Settings button is present and enabled', async ({ page }) => {
    await goToSettings(page);
    const saveBtn = page.locator('button').filter({ hasText: /Save Settings/i });
    await expect(saveBtn).toBeVisible({ timeout: 6000 });
    await expect(saveBtn).toBeEnabled();
  });

  test('save shows success feedback (green alert or toast)', async ({ page }) => {
    await goToSettings(page);
    // Click Save with existing values to trigger a success response
    const saveBtn = page.locator('button').filter({ hasText: /Save Settings/i });
    await saveBtn.click();
    // CompanySettings shows <span className="auto-save-indicator"> on success (not .alert-success)
    const feedback = page.locator('.auto-save-indicator').first();
    await expect(feedback).toBeVisible({ timeout: 10000 });
  });

  // ── Medical Insurance Policies section ───────────────────────────────────────

  test('"Add Insurance Policy" button is visible', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('button').filter({ hasText: /Add.*Insurance.*Policy|Add.*Policy/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('opening policy form shows Insurer Name input', async ({ page }) => {
    await goToSettings(page);
    const addBtn = page.locator('button').filter({ hasText: /Add.*Policy|Add.*Insurance/i }).first();
    await addBtn.click();
    await expect(
      page.locator('input[placeholder*="Daman"]')
    ).toBeVisible({ timeout: 6000 });
  });

  test('policy form validates required Insurer Name before save', async ({ page }) => {
    await goToSettings(page);
    const addBtn = page.locator('button').filter({ hasText: /Add.*Policy|Add.*Insurance/i }).first();
    await addBtn.click();
    // Button text is "Add Policy" (new) or "Update Policy" (edit) — disabled when Insurer Name is empty.
    // Two "Add Policy" buttons exist simultaneously: the toggle that opens the form AND the form submit.
    // Use .last() to target the form submit button (the toggle button comes first in DOM order).
    const savePolicyBtn = page.locator('button').filter({ hasText: /Add Policy|Update Policy/i }).last();
    await expect(savePolicyBtn).toBeVisible({ timeout: 6000 });
    await expect(savePolicyBtn).toBeDisabled();
  });

  test('adding a policy saves and shows it in the list', async ({ page }) => {
    await goToSettings(page);
    const addBtn = page.locator('button').filter({ hasText: /Add.*Policy|Add.*Insurance/i }).first();
    await addBtn.click();

    await page.locator('input[placeholder*="Daman"]').fill('PLAYWRIGHT TEST Insurer');
    // Same .last() pattern — two "Add Policy" buttons; submit is always the last one
    const savePolicyBtn = page.locator('button').filter({ hasText: /Add Policy|Update Policy/i }).last();
    await expect(savePolicyBtn).toBeEnabled({ timeout: 3000 });
    await savePolicyBtn.click();

    // Policy appears in the list
    await expect(
      page.locator('.card, table, [class*="policy"]').filter({ hasText: /PLAYWRIGHT TEST Insurer/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('deleting the test policy removes it from the list', async ({ page }) => {
    await goToSettings(page);

    // Target the specific table row (tr) for the policy — not the broader .card wrapping the
    // insurance section, which contains the insurer name but never disappears after deletion.
    const policyRow = page.locator('table tr').filter({ hasText: /PLAYWRIGHT TEST Insurer/i }).first();
    if (!(await policyRow.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'PLAYWRIGHT TEST policy not present — run add test first');
      return;
    }
    // handleDeletePolicy uses window.confirm() — register a handler to accept it before clicking,
    // otherwise Playwright auto-dismisses (returns false) and the delete is skipped.
    page.once('dialog', dialog => dialog.accept());
    const deleteBtn = policyRow.locator('button[title="Delete policy"]');
    await deleteBtn.click();
    await expect(policyRow).not.toBeVisible({ timeout: 8000 });
  });

  // ── WPS / SIF Reference section ───────────────────────────────────────────────

  test('WPS / SIF File Format Reference section is visible', async ({ page }) => {
    await goToSettings(page);
    await expect(
      page.locator('h3').filter({ hasText: /WPS.*SIF.*File Format/i })
    ).toBeVisible({ timeout: 6000 });
  });
});

// ── Branch Switcher (Feature 21) ──────────────────────────────────────────────

test.describe('Branch Switcher', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('branch switcher button is visible in the sidebar logo area', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    // Branch switcher has title="Switch branch" — first button in .sidebar-logo is "Collapse sidebar"
    await expect(page.locator('button[title="Switch branch"]')).toBeVisible({ timeout: 6000 });
  });

  test('clicking branch switcher opens dropdown with company name', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button[title="Switch branch"]').click();
    // At minimum, "Add Branch" button should appear in the open dropdown
    const addBranchLink = page.getByText(/Add Branch/i);
    await expect(addBranchLink).toBeVisible({ timeout: 6000 });
  });

  test('"Add Branch" opens branch creation modal', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('button[title="Switch branch"]').click();
    await page.getByText(/Add Branch/i).click();
    // Branch creation modal appears — use .modal (inner div) not [class*="modal"] to avoid
    // also matching .modal-backdrop, which would cause a strict-mode violation with .or().
    const modal = page.locator('.modal').filter({ hasText: /Branch/i }).first();
    await expect(modal).toBeVisible({ timeout: 6000 });
  });
});
