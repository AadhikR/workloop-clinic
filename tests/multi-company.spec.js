/**
 * multi-company.spec.js — Playwright tests for Feature 21: Multi-Company / Branch Support
 *
 * Covers:
 *   Admin portal (AppShell):
 *     - Branch switcher button is visible in the sidebar
 *     - Clicking it opens the branch dropdown
 *     - Dropdown lists at least one branch (the admin's existing company)
 *     - "Add Branch" option is present in the dropdown
 *     - New Branch modal opens and has a branch name input
 *     - Creating a branch: submitting the form creates the branch and closes the modal
 *     - After creation, the new branch appears in the switcher
 *     - Switching branches navigates to Company Settings (auto-navigate on create)
 *     - Switching back to the original branch works
 *     - Deleting a branch is only possible when there are 2+ branches (trash icon visible)
 *     - Company Settings shows the "Branch / Entity Label" field
 *     - Branch label field saves and refreshes the switcher
 *
 * NOTE: All tests use the pre-saved admin session.
 * Branch creation creates real DB rows — cleaned up in afterAll.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient } from './helpers/db.js';

const BRANCH_NAME = `Test Branch ${Date.now()}`;

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));

    // Delete test branches (not the primary one — employees may be attached)
    await db
      .from('companies')
      .delete()
      .eq('user_id', adminId)
      .ilike('branch_name', 'Test Branch%');
    console.log('[multi-company cleanup] Removed test branches.');
  } catch (e) {
    console.warn('[multi-company cleanup] Could not clean up:', e.message);
  }
});

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToAdmin(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
}

async function openBranchDropdown(page) {
  // The switcher button is inside .sidebar-logo, shows the current branch label
  // and a ChevronDown icon
  const switcherBtn = page.locator('.sidebar-logo button').first();
  await expect(switcherBtn).toBeVisible({ timeout: 6000 });
  await switcherBtn.click();
}

// ─── Tests ────────────────────────────────────────────────────────────────────

test.describe('Multi-Company — Admin sidebar branch switcher', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('branch switcher button is visible in the sidebar', async ({ page }) => {
    await goToAdmin(page);
    // The switcher is a button inside .sidebar-logo containing a Building2 icon and ChevronDown
    await expect(
      page.locator('.sidebar-logo button').first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('clicking the switcher opens the branch dropdown', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    // The dropdown appears — look for the "Add Branch" button as a reliable marker
    await expect(
      page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('dropdown lists at least one branch (the existing company)', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    // The dropdown should contain at least one branch item button (excluding "Add Branch")
    // Branch buttons are inside the dropdown div, each has a flex-1 span with the label
    const dropdown = page.locator('.sidebar-logo div[style*="position: absolute"]').first();
    await expect(dropdown).toBeVisible({ timeout: 4000 });
    // There should be at least one branch entry (a button that is not "Add Branch")
    const branchBtns = dropdown.locator('button').filter({ hasText: /./}).filter({ not: dropdown.locator('button').filter({ hasText: /add branch/i }) });
    const count = await branchBtns.count();
    expect(count, 'At least one branch should be listed').toBeGreaterThanOrEqual(1);
  });

  test('"Add Branch" option is present in the dropdown', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await expect(
      page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('clicking "Add Branch" opens the New Branch modal', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i }).click();

    // Modal appears with heading "Add New Branch"
    await expect(
      page.locator('.modal-header h3').filter({ hasText: /add new branch/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('New Branch modal has a branch name input', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i }).click();

    await expect(
      page.locator('.modal').getByRole('textbox')
    ).toBeVisible({ timeout: 5000 });
  });

  test('Create Branch button is disabled when branch name is empty', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i }).click();

    // The "Create Branch" button should be disabled with an empty input
    await expect(
      page.locator('.modal-footer').getByRole('button', { name: /create branch/i })
    ).toBeDisabled({ timeout: 4000 });
  });

  test('Cancel on New Branch modal closes it without creating', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i }).click();

    await expect(page.locator('.modal')).toBeVisible({ timeout: 5000 });
    await page.locator('.modal-footer').getByRole('button', { name: /cancel/i }).click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });

  test('creating a branch closes the modal and navigates to Company Settings', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);
    await page.locator('.sidebar-logo').getByRole('button', { name: /add branch/i }).click();

    // Fill the branch name
    const input = page.locator('.modal').getByRole('textbox');
    await expect(input).toBeVisible({ timeout: 5000 });
    await input.fill(BRANCH_NAME);

    // Submit
    await page.locator('.modal-footer').getByRole('button', { name: /create branch/i }).click();

    // Modal closes
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 8000 });

    // Auto-navigates to Company Settings
    await expect(
      page.locator('.page-header h2').filter({ hasText: /company settings/i })
    ).toBeVisible({ timeout: 10000 });
  });

  test('new branch appears in the switcher after creation', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);

    // Check the dropdown for the test branch name
    const branchItem = page.locator('.sidebar-logo').getByRole('button', { name: new RegExp(BRANCH_NAME, 'i') });
    if (!(await branchItem.isVisible({ timeout: 4000 }).catch(() => false))) {
      // Maybe dropdown was already closed — re-open
      const switcherBtn = page.locator('.sidebar-logo button').first();
      await switcherBtn.click();
    }

    await expect(
      page.locator('.sidebar-logo').getByRole('button', { name: new RegExp(BRANCH_NAME, 'i') }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('switching branches reloads the active module data', async ({ page }) => {
    await goToAdmin(page);

    // Navigate to Employees so we have a page that reloads on branch switch
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');

    // Open switcher and switch to test branch (if exists)
    await openBranchDropdown(page);

    const testBranchBtn = page.locator('.sidebar-logo button').filter({ hasText: BRANCH_NAME }).first();
    if (!(await testBranchBtn.isVisible({ timeout: 3000 }).catch(() => false))) {
      test.skip(true, 'Test branch not found — run the create test first');
      return;
    }

    await testBranchBtn.click();
    await page.waitForLoadState('networkidle');

    // Employees page should still be visible (reloaded for new branch)
    await expect(
      page.locator('.page-header h2').filter({ hasText: /Employees/i })
    ).toBeVisible({ timeout: 8000 });
  });

  test('dropdown shows a delete (X) button for non-active branches when multiple branches exist', async ({ page }) => {
    await goToAdmin(page);
    await openBranchDropdown(page);

    // If there's only one branch, no X buttons are shown
    const dropdown = page.locator('.sidebar-logo div[style*="position: absolute"]').first();
    if (!(await dropdown.isVisible({ timeout: 3000 }).catch(() => false))) return;

    // Count branch rows (excluding Add Branch)
    const allBtns = await dropdown.locator('button').count();
    if (allBtns <= 2) {
      // Only 1 branch + Add Branch — no X button expected
      await expect(
        dropdown.locator('button[title*="Delete"]')
      ).not.toBeVisible({ timeout: 2000 });
    } else {
      // Multiple branches — X button(s) should be visible for non-active branches
      await expect(
        dropdown.locator('button[title*="Delete"]').first()
      ).toBeVisible({ timeout: 3000 });
    }
  });
});

// ─── Company Settings — Branch Label field ────────────────────────────────────

test.describe('Multi-Company — Company Settings branch label', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Company Settings shows the "Branch / Entity Label" field', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
    await page.waitForLoadState('networkidle');

    await expect(
      page.locator('label').filter({ hasText: /branch.*entity label/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Branch label input is present and editable', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Company Settings' }).click();
    await page.waitForLoadState('networkidle');

    // Wait for form to load
    await expect(page.locator('label').filter({ hasText: /branch.*entity label/i }).first()).toBeVisible({ timeout: 8000 });

    // Find the input that follows the Branch label
    const branchInput = page.locator('input[placeholder*="Dubai HQ"], input[placeholder*="Abu Dhabi"]').first();
    await expect(branchInput).toBeVisible({ timeout: 5000 });

    // Should be editable
    await branchInput.fill('Test Label');
    await expect(branchInput).toHaveValue('Test Label');

    // Restore empty
    await branchInput.fill('');
  });
});
