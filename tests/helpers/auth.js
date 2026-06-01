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
  await page.getByRole('button', { name: /^sign in$/i }).click();
  // Wait for sidebar to confirm we're in the admin portal
  await page.waitForSelector('.sidebar-logo', { timeout: 15000 });
}

/** Sign in as employee and wait for the employee shell to load. */
export async function loginAsEmployee(page) {
  await page.goto('/');
  await page.getByRole('button', { name: /sign in as employee/i }).click();
  await page.locator('input[type="email"]').fill(process.env.TEST_EMPLOYEE_EMAIL);
  await page.locator('input[type="password"]').fill(process.env.TEST_EMPLOYEE_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  // Employee portal has emp-page-body or a sidebar with the employee name
  await page.waitForSelector('.sidebar-logo', { timeout: 15000 });
}

/** Navigate to a named admin section via the sidebar. */
export async function goTo(page, section) {
  // section = 'Attendance' | 'Employees' | 'Payroll Module' | 'Leave' | 'Company Settings'
  await page.getByRole('button', { name: section }).click();
  await page.waitForLoadState('networkidle');
}
