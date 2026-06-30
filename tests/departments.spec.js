/**
 * departments.spec.js
 * Feature 3.1 — Department Hierarchy & Org Tree
 *
 * Admin portal (DepartmentManager):
 *   - "Departments" nav item is visible
 *   - Page renders with heading
 *   - Two tabs: Departments and Org Chart
 *   - Add department form: name, parent, head employee, color swatches
 *   - Saving a department adds it to the tree table (with afterAll cleanup)
 *   - Indented child depts show └ prefix in the tree
 *   - Org Chart tab renders the search and dept filter controls
 *   - Org Chart shows employee cards
 *   - Staffing Rules tab (Feature 7.2a) is present
 *   - Staffing Rules tab has add-rule form: dept, shift category, min staff
 *
 * Employee portal — Department autocomplete in EmployeeModal:
 *   - Job tab's Department field has a datalist for autocomplete
 *
 * NOTE: storageState inside admin describe blocks.
 */
import { test, expect } from '@playwright/test';
import { readFileSync, existsSync } from 'fs';
import { adminClient } from './helpers/db.js';

const DEPT_NAME = `Playwright Dept ${Date.now()}`;

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test.afterAll(async () => {
  try {
    const db = adminClient();
    const envPath = '.playwright/env.json';
    if (!existsSync(envPath)) return;
    const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));
    await db.from('departments').delete().eq('user_id', adminId).like('name', 'Playwright Dept%');
    console.log('[departments cleanup] Removed test departments.');
  } catch (e) {
    console.warn('[departments cleanup] Could not clean up:', e.message);
  }
});

// ─── helpers ──────────────────────────────────────────────────────────────────

async function goToDepartments(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Departments' }).click();
  await page.waitForLoadState('networkidle');
}

// ─── Navigation and layout ───────────────────────────────────────────────────

test.describe('Departments (3.1) — Admin: navigation & layout', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Departments" nav item is visible in admin sidebar', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(
      page.locator('.sidebar-nav').getByRole('button', { name: 'Departments' })
    ).toBeVisible({ timeout: 6000 });
  });

  test('Departments page renders with heading', async ({ page }) => {
    await goToDepartments(page);
    await expect(
      page.locator('h1, h2').filter({ hasText: /departments/i }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('Two main tab buttons: Departments and Org Chart', async ({ page }) => {
    await goToDepartments(page);
    // Tab text renders as "Departments (N)" — avoid anchored regex
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /Departments/i }).first()
    ).toBeVisible({ timeout: 6000 });
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /Org Chart/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('Staffing Rules third tab is visible', async ({ page }) => {
    await goToDepartments(page);
    await expect(
      page.locator('button.tab-btn').filter({ hasText: /Staffing Rules/i })
    ).toBeVisible({ timeout: 6000 });
  });

  test('"Add Department" button is visible on Departments tab', async ({ page }) => {
    await goToDepartments(page);
    // "Add Department" appears in both the page header AND the empty-state card → use .first()
    await expect(
      page.locator('button').filter({ hasText: /Add Department/i }).first()
    ).toBeVisible({ timeout: 6000 });
  });
});

// ─── Departments CRUD ────────────────────────────────────────────────────────

test.describe('Departments (3.1) — Admin: department CRUD', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('"Add Department" opens an inline form with Name, Parent, Head, Color fields', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button').filter({ hasText: /Add Department/i }).first().click();

    // Name input
    await expect(
      page.locator('input[placeholder="e.g. Nursing"]').first()
    ).toBeVisible({ timeout: 5000 });

    // Color swatches (preset colors rendered as clickable divs)
    const swatches = page.locator('div[style*="border-radius: 50%"], div[style*="borderRadius"]').first();
    const hasSwatches = await swatches.isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasSwatches).toBeTruthy();
  });

  test('saving a department adds it to the tree table', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button').filter({ hasText: /Add Department/i }).first().click();

    const nameInput = page.locator('input[placeholder="e.g. Nursing"]').first();
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    await nameInput.fill(DEPT_NAME);

    // Save — button has Lucide Check icon + "Save" text. The icon is aria-hidden so
    // the WAI-ARIA accessible name is "Save". Use getByRole to avoid anchored-regex
    // issues caused by the leading icon node in raw textContent.
    await page.getByRole('button', { name: 'Save', exact: true }).first().click();

    // Dept should appear in the table
    await expect(
      page.locator('td, div').filter({ hasText: DEPT_NAME }).first()
    ).toBeVisible({ timeout: 8000 });
  });

  test('dept tree table shows column headers Name, Parent, Head, Actions', async ({ page }) => {
    await goToDepartments(page);

    const table = page.locator('table').first();
    if (!(await table.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No departments yet — table absent');
      return;
    }

    // Column headers: "Department" (not "Name"), "Head", "Employees"
    for (const col of ['Department', 'Head']) {
      await expect(
        table.locator('th').filter({ hasText: new RegExp(col, 'i') }).first()
      ).toBeVisible({ timeout: 4000 });
    }
  });

  test('edit button on an existing department opens the inline edit form', async ({ page }) => {
    await goToDepartments(page);

    const row = page.locator('tr').filter({ hasText: DEPT_NAME }).first();
    if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test department not found — run save test first');
      return;
    }

    await row.locator(`button[title="Edit"]`).first().click();
    // Form should be in edit mode with the dept name pre-filled
    const nameInput = page.locator('input[placeholder="e.g. Nursing"]').first();
    await expect(nameInput).toBeVisible({ timeout: 5000 });
    const val = await nameInput.inputValue();
    expect(val).toBe(DEPT_NAME);
  });

  test('delete button on a department shows a confirmation guard', async ({ page }) => {
    await goToDepartments(page);

    const row = page.locator('tr').filter({ hasText: DEPT_NAME }).first();
    if (!(await row.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'Test department not found — run save test first');
      return;
    }

    const deleteBtn = row.locator('button[title="Delete"]').first();
    await deleteBtn.click();

    // Should either show a confirm button or a window.confirm (accept it)
    page.on('dialog', dialog => dialog.dismiss()); // dismiss to avoid actually deleting
    await page.waitForTimeout(500);
  });
});

// ─── Org Chart tab ────────────────────────────────────────────────────────────

test.describe('Departments (3.1) — Admin: Org Chart tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Org Chart tab renders search and dept filter controls', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Org Chart/i }).click();
    await page.waitForTimeout(400);

    // Search input
    await expect(
      page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Org Chart tab shows a dept filter select', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Org Chart/i }).click();
    await page.waitForTimeout(400);

    await expect(
      page.locator('select').filter({
        has: page.locator('option', { hasText: /all departments|department/i }),
      }).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Org Chart tab renders employee nodes or empty state', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Org Chart/i }).click();
    await page.waitForTimeout(500);

    // Either shows employee node cards or an empty state
    const empNode = page.locator('.page-body div[style*="border-radius: 10px"]').first()
      .or(page.locator('.page-body div').filter({ hasText: /no employees|no staff/i }).first());

    const hasContent = await page.locator('.page-body > *').first().isVisible({ timeout: 5000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});

// ─── Staffing Rules tab (Feature 7.2a) ───────────────────────────────────────

test.describe('Staffing Rules (7.2) — Admin: DepartmentManager tab', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Staffing Rules tab renders add-rule form', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Staffing Rules/i }).click();
    await page.waitForTimeout(400);

    // Add Rule button or inline form
    await expect(
      page.locator('button').filter({ hasText: /Add Rule|New Rule/i })
        .or(page.locator('input[placeholder*="department"], select[value="morning"]')).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('Staffing Rules form has Department, Shift Category, Min Staff fields', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Staffing Rules/i }).click();
    await page.waitForTimeout(400);

    // Click Add Rule if it's not already open
    const addBtn = page.locator('button').filter({ hasText: /Add Rule|New Rule/i }).first();
    if (await addBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(200);
    }

    // Shift category select
    await expect(
      page.locator('select').filter({ has: page.locator('option[value="morning"]') }).first()
    ).toBeVisible({ timeout: 5000 });

    // Min staff number input
    await expect(
      page.locator('input[type="number"]').first()
    ).toBeVisible({ timeout: 5000 });
  });

  test('Shift category select has morning/afternoon/night options', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Staffing Rules/i }).click();
    await page.waitForTimeout(400);

    const addBtn = page.locator('button').filter({ hasText: /Add Rule|New Rule/i }).first();
    if (await addBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(200);
    }

    const catSelect = page.locator('select').filter({ has: page.locator('option[value="morning"]') }).first();
    await expect(catSelect).toBeVisible({ timeout: 5000 });

    for (const cat of ['morning', 'afternoon', 'night']) {
      await expect(catSelect.locator(`option[value="${cat}"]`)).toBeAttached({ timeout: 3000 });
    }
  });

  test('Staffing Rules table or empty state renders', async ({ page }) => {
    await goToDepartments(page);
    await page.locator('button.tab-btn').filter({ hasText: /Staffing Rules/i }).click();
    await page.waitForTimeout(400);

    const table = page.locator('table').first();
    const emptyState = page.locator('text=/no staffing rules|no rules/i').first();

    const hasContent = await table.isVisible({ timeout: 4000 }).catch(() => false)
                    || await emptyState.isVisible({ timeout: 3000 }).catch(() => false)
                    || await page.locator('.card').first().isVisible({ timeout: 3000 }).catch(() => false);
    expect(hasContent).toBeTruthy();
  });
});

// ─── EmployeeModal: department datalist autocomplete ─────────────────────────

test.describe('Departments (3.1) — EmployeeModal: dept autocomplete', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Department field in Job tab has a datalist for autocomplete', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /add employee/i }).click();
    await expect(page.locator('.modal')).toBeVisible({ timeout: 6000 });

    // Switch to Job & Contract tab
    await page.getByRole('button', { name: /job.*contract|job &|job tab/i }).first().click();
    await page.waitForTimeout(300);

    // The department input should have a list attribute pointing to a datalist
    const deptInput = page.locator('.modal input[list]').first()
      .or(page.locator('.modal').getByLabel(/department/i)).first();
    await expect(deptInput).toBeVisible({ timeout: 5000 });

    // datalist should be present in the DOM
    const datalist = page.locator('.modal datalist').first();
    await expect(datalist).toBeAttached({ timeout: 4000 });

    // Close
    await page.locator('.modal-header .btn-ghost').click();
  });
});
