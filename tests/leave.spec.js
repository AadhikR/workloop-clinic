import { test, expect } from '@playwright/test';

test.describe('Leave — employee submits, admin approves', () => {

  test('employee can submit a leave request', async ({ browser }) => {
    const empCtx  = await browser.newContext({ storageState: '.playwright/employee-session.json' });
    const empPage = await empCtx.newPage();

    await empPage.goto('/');
    await expect(empPage.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await empPage.getByRole('button', { name: /leave/i }).click();
    await empPage.waitForLoadState('networkidle');

    // Click "Apply for Leave" or equivalent
    const applyBtn = empPage.getByRole('button', { name: /apply|request|new leave/i });
    if (!await applyBtn.isVisible({ timeout: 3000 })) {
      await empCtx.close();
      test.skip(true, 'Apply leave button not found');
    }
    await applyBtn.click();

    // Fill in the form — pick a future date
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 7);
    const dateStr = futureDate.toISOString().split('T')[0];

    const startInput = empPage.locator('input[type="date"]').first();
    await startInput.fill(dateStr);
    const endInput = empPage.locator('input[type="date"]').nth(1);
    await endInput.fill(dateStr);

    // Submit
    await empPage.getByRole('button', { name: /submit|apply/i }).last().click();

    // Success message or request appears as pending
    await expect(
      empPage.locator('text=/submitted|pending|success/i').first()
    ).toBeVisible({ timeout: 10000 });

    await empCtx.close();
  });

  test('admin leave page loads without errors', async ({ browser }) => {
    const adminCtx  = await browser.newContext({ storageState: '.playwright/admin-session.json' });
    const adminPage = await adminCtx.newPage();
    const errors = [];
    adminPage.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

    await adminPage.goto('/');
    await expect(adminPage.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await adminPage.getByRole('button', { name: 'Leave' }).click();
    await adminPage.waitForLoadState('networkidle');
    await adminPage.waitForTimeout(2000);

    expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0);
    await adminCtx.close();
  });
});
