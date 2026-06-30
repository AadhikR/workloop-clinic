/**
 * auth.js — Page-level login helpers for Playwright tests.
 * Each helper navigates to the app and signs in as admin or employee.
 */

/** Sign in as admin and wait for the dashboard to load. */
export async function loginAsAdmin(page) {
  await page.goto('/');
  await page.getByRole('button', { name: /sign in as admin/i }).click();
  await page.locator('input[type="email"]').fill(process.env.TEST_ADMIN_EMAIL);
  await page.locator('input[type="password"]').fill(process.env.TEST_ADMIN_PASSWORD);
  // Use button[type="submit"] — the button text is "Sign in as Admin", not just "Sign in"
  await page.locator('button[type="submit"]').click();
  // Admin shell uses .sidebar-logo
  await page.waitForSelector('.sidebar-logo', { timeout: 30000 });
}

/** Sign in as employee and wait for the employee shell to load. */
export async function loginAsEmployee(page) {
  await page.goto('/');
  await page.getByRole('button', { name: /sign in as employee/i }).click();
  await page.locator('input[type="email"]').fill(process.env.TEST_EMPLOYEE_EMAIL);
  await page.locator('input[type="password"]').fill(process.env.TEST_EMPLOYEE_PASSWORD);
  // Use button[type="submit"] — the button text is "Sign in as Employee", not just "Sign in"
  await page.locator('button[type="submit"]').click();
  // Employee shell uses .emp-sidebar-logo (different from the admin .sidebar-logo)
  await page.waitForSelector('.emp-sidebar-logo', { timeout: 30000 });
}

/** Sign in as manager and wait for the manager shell to load. */
export async function loginAsManager(page) {
  const email    = process.env.TEST_MANAGER_EMAIL    || 'test.manager@workloop-test.local';
  const password = process.env.TEST_MANAGER_PASSWORD || 'TestManager123!';
  await page.goto('/');
  await page.getByRole('button', { name: /sign in as employee/i }).click();
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.locator('button[type="submit"]').click();
  // ManagerShell renders .emp-sidebar-logo (same visual design as EmployeeShell)
  await page.waitForSelector('.emp-sidebar-logo', { timeout: 30000 });
}

/** Navigate to a named admin section via the sidebar. */
export async function goTo(page, section) {
  // section = 'Attendance' | 'Employees' | 'Payroll Module' | 'Leave' | 'Company Settings'
  await page.getByRole('button', { name: section }).click();
  await page.waitForLoadState('networkidle');
}
