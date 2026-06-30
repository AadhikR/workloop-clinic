import { test, expect } from '@playwright/test';

// ── Auth flows ─────────────────────────────────────────────────────────────────
// These tests do NOT use saved session state — they test the login page itself.

test.describe('Auth', () => {

  test('admin sign-in lands on dashboard', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(process.env.TEST_ADMIN_PASSWORD);
    // Button text is "Sign in as Admin" — use type=submit to avoid matching portal-switcher buttons
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('h2')).toContainText('Dashboard');
  });

  test('wrong password shows error and does not crash', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill('WrongPassword999!');
    await page.locator('button[type="submit"]').click();
    // Error banner should appear — use .alert-danger specifically (not [class*="alert"] which
    // also matches the SVG lucide-circle-alert icon inside the banner, causing strict mode failure)
    await expect(page.locator('.alert-danger')).toBeVisible({ timeout: 8000 });
    // Auth page still visible (not dashboard) — check neither admin nor employee shell is showing
    await expect(page.locator('.sidebar-logo, .emp-sidebar-logo')).not.toBeVisible();
  });

  test('duplicate company registration shows helpful message', async ({ page }) => {
    await page.goto('/');
    // Find the "Create Company" option (Landing page button)
    const createBtn = page.getByRole('button', { name: /create.*company/i });
    if (await createBtn.isVisible()) {
      await createBtn.click();
      // CreateCompanyForm has 4 required fields: company name, email, password, confirm password
      await page.locator('input[placeholder="Acme LLC"]').fill('Existing Company Test');
      await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
      await page.locator('input[type="password"]').first().fill('SomePassword123!');
      await page.locator('input[type="password"]').nth(1).fill('SomePassword123!');
      await page.locator('button[type="submit"]').click();
      // Supabase returns identities=[] for already-registered email → app shows error
      await expect(page.locator('text=/already registered/i')).toBeVisible({ timeout: 8000 });
      await expect(page.locator('.sidebar-logo, .emp-sidebar-logo')).not.toBeVisible();
    } else {
      test.skip(true, 'Create Company button not visible on auth page');
    }
  });

  test('employee sign-in lands on employee portal', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as employee/i }).click();
    await page.locator('input[type="email"]').fill(process.env.TEST_EMPLOYEE_EMAIL);
    await page.locator('input[type="password"]').fill(process.env.TEST_EMPLOYEE_PASSWORD);
    // Button text is "Sign in as Employee" — use type=submit
    await page.locator('button[type="submit"]').click();
    // Employee shell renders .emp-sidebar-logo (not .sidebar-logo which is admin-only)
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
    // Employee portal shows employee-specific content (not HR admin nav items)
    await expect(page.locator('text=Payroll Module')).not.toBeVisible();
  });

  test('admin reload stays logged in', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(process.env.TEST_ADMIN_PASSWORD);
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 15000 });
    // Reload
    await page.reload();
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h2')).toContainText('Dashboard');
  });

  test('sign out returns to login page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
    await page.locator('input[type="password"]').fill(process.env.TEST_ADMIN_PASSWORD);
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /sign out/i }).click();
    // Should return to auth page — neither shell should be visible
    await expect(page.locator('.sidebar-logo, .emp-sidebar-logo')).not.toBeVisible({ timeout: 8000 });
  });

  test('admin email is case-insensitive (UPPERCASE input signs in correctly)', async ({ page }) => {
    // AuthPage normalises email to lowercase before calling signInAsAdmin.
    // Signing in with UPPER-CASE email must still work.
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await page.locator('input[type="email"]').fill((process.env.TEST_ADMIN_EMAIL ?? '').toUpperCase());
    await page.locator('input[type="password"]').fill(process.env.TEST_ADMIN_PASSWORD);
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.sidebar-logo')).toBeVisible({ timeout: 15000 });
  });

  test('employee email is case-insensitive (mixed case signs in correctly)', async ({ page }) => {
    const email = process.env.TEST_EMPLOYEE_EMAIL ?? '';
    const mixed = email.split('').map((c, i) => i % 2 === 0 ? c.toUpperCase() : c).join('');
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as employee/i }).click();
    await page.locator('input[type="email"]').fill(mixed);
    await page.locator('input[type="password"]').fill(process.env.TEST_EMPLOYEE_PASSWORD);
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.emp-sidebar-logo')).toBeVisible({ timeout: 15000 });
  });

  test('wrong employee email shows error and stays on auth page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /sign in as employee/i }).click();
    await page.locator('input[type="email"]').fill('nobody@not-a-real-email.local');
    await page.locator('input[type="password"]').fill('WrongPassword999!');
    await page.locator('button[type="submit"]').click();
    await expect(page.locator('.alert-danger')).toBeVisible({ timeout: 8000 });
    await expect(page.locator('.emp-sidebar-logo')).not.toBeVisible();
  });

  test('auth page shows both "Sign in as Admin" and "Sign in as Employee" buttons', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('button', { name: /sign in as admin/i })).toBeVisible({ timeout: 8000 });
    await expect(page.getByRole('button', { name: /sign in as employee/i })).toBeVisible({ timeout: 5000 });
  });

  test('switching portal tab changes form title and submit button text', async ({ page }) => {
    await page.goto('/');
    // Click "Sign in as Employee" — form should switch
    await page.getByRole('button', { name: /sign in as employee/i }).click();
    await expect(page.locator('button[type="submit"]')).toContainText(/Employee/i);
    // Switch back to Admin — AuthPage is multi-step navigation, not a tab switcher.
    // After clicking "Sign in as Employee" you're on the employee form; must click Back
    // to return to the PortalSelect landing before the "Sign in as Admin" button appears.
    // The Back button renders <ArrowLeft aria-hidden /> Back — textContent has a leading space,
    // so anchored /^Back$/ never matches. Use accessible name via getByRole instead.
    await page.getByRole('button', { name: 'Back', exact: true }).click();
    await page.getByRole('button', { name: /sign in as admin/i }).click();
    await expect(page.locator('button[type="submit"]')).toContainText(/Admin/i);
  });
});
