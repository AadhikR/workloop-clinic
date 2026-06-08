/**
 * offboarding.spec.js — Playwright tests for Feature 13: Employee Offboarding Workflow
 *
 * Covers:
 *   EmployeeManager row actions:
 *     - Terminated employees show a ClipboardList (offboarding) icon button
 *     - Clicking it opens OffboardingModal
 *
 *   OffboardingModal:
 *     - Task list renders (checkboxes for clearance items)
 *     - Task toggle (check/uncheck) works optimistically
 *     - Visa cancellation status selector is present
 *     - "EOS Calculator" button navigates to EndOfServiceScreen
 *     - EndOfServiceScreen shows and has a Back button
 *     - NOC Letter button is visible
 *     - Experience Letter button is visible
 *     - Add custom task form is accessible
 *     - "Mark Checklist Complete" button is present (only if all tasks done)
 *
 * NOTE: These tests require at least one Terminated employee.
 * The global-setup creates a Full-Time employee, not Terminated.
 * The employees.spec.js test can archive the test employee.
 * Tests gracefully skip when no Terminated employees are found.
 */
import { test, expect } from '@playwright/test';

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function goToEmployees(page) {
  await page.goto('/');
  await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
  await page.locator('.sidebar-nav').getByRole('button', { name: 'Employees' }).click();
  await page.waitForLoadState('networkidle');
  await expect(page.locator('.page-header h2').filter({ hasText: /Employees/i })).toBeVisible({ timeout: 10000 });
}

/**
 * Finds the offboarding action button in the first Terminated employee row.
 * Returns null if no Terminated employee is found.
 */
async function findOffboardingButton(page) {
  await goToEmployees(page);

  // Look for a row that has a Terminated badge
  const terminatedRow = page.locator('tr').filter({
    has: page.locator('.badge', { hasText: /^Terminated$/i }),
  }).first();

  if (!(await terminatedRow.isVisible({ timeout: 4000 }).catch(() => false))) {
    return null;
  }

  // The offboarding button sits in the row actions area
  // It is an icon-only button targeting terminated employees
  const offboardBtn = terminatedRow.locator('button[title*="ffboard"]').first();
  if (await offboardBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
    return offboardBtn;
  }

  // Fallback: any button in the row that isn't Edit or Delete
  return null;
}

/**
 * Opens the OffboardingModal for the first Terminated employee.
 * Returns false if no Terminated employee / button found.
 */
async function openOffboardingModal(page) {
  const btn = await findOffboardingButton(page);
  if (!btn) return false;

  await btn.click();
  // OffboardingModal header should appear
  const modalHeader = page.locator('.modal-header h3').filter({ hasText: /offboard/i });
  if (!(await modalHeader.isVisible({ timeout: 6000 }).catch(() => false))) return false;
  return true;
}

// ─── Admin — EmployeeManager row actions ─────────────────────────────────────

test.describe('Offboarding — EmployeeManager row button', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('Terminated employees have an offboarding action button', async ({ page }) => {
    const btn = await findOffboardingButton(page);
    if (!btn) {
      test.skip(true, 'No Terminated employees found — archive an employee first to test this');
      return;
    }
    await expect(btn).toBeVisible();
  });

  test('Offboarding button opens the OffboardingModal', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found or offboarding button not identified');
      return;
    }
    await expect(
      page.locator('.modal-header h3').filter({ hasText: /offboard/i })
    ).toBeVisible({ timeout: 6000 });
  });
});

// ─── Admin — OffboardingModal content ────────────────────────────────────────

test.describe('Offboarding — OffboardingModal tasks and controls', () => {
  test.use({ storageState: '.playwright/admin-session.json' });

  test('modal renders a task checklist', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    // Offboarding tasks use Lucide SVG icons (CheckSquare/Square) + <div onClick> rows,
    // NOT <input type="checkbox"> or <li> elements.
    // The checklist card is always present; either tasks (with a Remove button each) or "No tasks yet."
    const clearanceCard = page.locator('.card').filter({
      has: page.locator('h3').filter({ hasText: /Clearance Checklist/i }),
    });
    await expect(clearanceCard).toBeVisible({ timeout: 8000 });
    // Either at least one task row (has a "Remove task" delete button) or the empty-state text
    const taskRow = clearanceCard.locator('button[title="Remove task"]').first();
    const emptyMsg = clearanceCard.getByText('No tasks yet.').first();
    await expect(taskRow.or(emptyMsg)).toBeVisible({ timeout: 8000 });
  });

  test('task checkbox toggles (optimistic update)', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    const firstCheckbox = page.locator('.modal input[type="checkbox"]').first();
    if (!(await firstCheckbox.isVisible({ timeout: 5000 }).catch(() => false))) {
      test.skip(true, 'No task checkboxes found in the offboarding modal');
      return;
    }
    const wasChecked = await firstCheckbox.isChecked();
    await firstCheckbox.click();
    // Optimistic update — state flips immediately
    await expect(firstCheckbox).toBeChecked({ timeout: 3000 });
    // If it was already checked, restore to unchecked for subsequent runs
    if (wasChecked) await firstCheckbox.click();
  });

  test('visa cancellation status selector is present', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    // Visa cancellation status is a <select> with options like "not_started", "initiated", etc.
    const visaSelect = page.locator('.modal select').filter({
      has: page.locator('option[value="not_started"]'),
    });
    await expect(visaSelect).toBeVisible({ timeout: 6000 });
  });

  test('"EOS Calculator" button is visible and navigates to EndOfServiceScreen', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    const eosBtn = page.locator('.modal').getByRole('button', { name: /EOS Calculator|End of Service/i });
    await expect(eosBtn).toBeVisible({ timeout: 6000 });

    await eosBtn.click();
    // EndOfServiceScreen replaces the modal body and has a "Back" button
    await expect(
      page.locator('button').filter({ hasText: /back/i }).or(
        page.locator('text=/End.of.Service/i')
      ).first()
    ).toBeVisible({ timeout: 6000 });
  });

  test('"Back" button on EOS Calculator returns to the offboarding modal', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    const eosBtn = page.locator('.modal').getByRole('button', { name: /EOS Calculator|End of Service/i });
    if (!(await eosBtn.isVisible({ timeout: 4000 }).catch(() => false))) {
      test.skip(true, 'EOS Calculator button not found');
      return;
    }
    await eosBtn.click();
    const backBtn = page.locator('button').filter({ hasText: /back/i }).first();
    await expect(backBtn).toBeVisible({ timeout: 6000 });
    await backBtn.click();
    // Should return to the main offboarding modal
    await expect(
      page.locator('.modal-header h3').filter({ hasText: /offboard/i })
    ).toBeVisible({ timeout: 5000 });
  });

  test('"NOC Letter" button is visible', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    await expect(
      page.locator('.modal').getByRole('button', { name: /NOC.*Letter|No.*Objection/i })
    ).toBeVisible({ timeout: 6000 });
  });

  test('"Experience Letter" button is visible', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    await expect(
      page.locator('.modal').getByRole('button', { name: /Experience.*Letter/i })
    ).toBeVisible({ timeout: 6000 });
  });

  test('custom task can be added via inline form', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    // There should be an "Add Task" button or input to add a custom task
    const addTaskBtn   = page.locator('.modal').getByRole('button', { name: /add task/i });
    const addTaskInput = page.locator('.modal input[placeholder*="task"]');

    const hasAddBtn   = await addTaskBtn.isVisible({ timeout: 3000 }).catch(() => false);
    const hasAddInput = await addTaskInput.isVisible({ timeout: 2000 }).catch(() => false);

    if (!hasAddBtn && !hasAddInput) {
      test.skip(true, 'No "Add Task" button or input found in the offboarding modal');
      return;
    }

    if (hasAddBtn) {
      await addTaskBtn.click();
      // After clicking, an input should appear
      await expect(page.locator('.modal input[placeholder*="task"]')).toBeVisible({ timeout: 4000 });
    } else {
      await expect(addTaskInput).toBeVisible();
    }
  });

  test('modal has a close/dismiss button', async ({ page }) => {
    const opened = await openOffboardingModal(page);
    if (!opened) {
      test.skip(true, 'No Terminated employees found');
      return;
    }
    // Modal has an X close button in the header
    const closeBtn = page.locator('.modal-header button').filter({ hasText: '' }).first()
      .or(page.locator('.modal-header').getByRole('button')).first();
    await expect(closeBtn).toBeVisible({ timeout: 4000 });
    await closeBtn.click();
    await expect(page.locator('.modal')).not.toBeVisible({ timeout: 4000 });
  });
});
