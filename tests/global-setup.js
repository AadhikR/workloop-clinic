/**
 * global-setup.js — Runs once before all tests.
 *
 * 1. Creates the test admin user (if not exists) and their company row.
 * 2. Creates the test employee user (if not exists) and their employee row.
 * 3. Links the employee auth account to the employee row.
 * 4. Saves browser session state so tests don't need to re-login.
 */
import { chromium } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';
import { config } from 'dotenv';
import { writeFileSync, mkdirSync } from 'fs';

config({ path: '.env.test' });

const {
  VITE_SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY,
  TEST_ADMIN_EMAIL,
  TEST_ADMIN_PASSWORD,
  TEST_ADMIN_COMPANY,
  TEST_EMPLOYEE_EMAIL,
  TEST_EMPLOYEE_PASSWORD,
  TEST_EMPLOYEE_NAME,
} = process.env;

export default async function globalSetup() {
  if (!SUPABASE_SERVICE_ROLE_KEY) {
    throw new Error(
      'SUPABASE_SERVICE_ROLE_KEY missing. Copy .env.test.example → .env.test and fill in values.'
    );
  }

  const db = createClient(VITE_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  console.log('\n[setup] Creating test admin user…');
  const { data: adminData } = await db.auth.admin.createUser({
    email: TEST_ADMIN_EMAIL,
    password: TEST_ADMIN_PASSWORD,
    email_confirm: true,
  });
  // If user already exists, look them up
  let adminUser = adminData?.user;
  if (!adminUser) {
    const { data: { users } } = await db.auth.admin.listUsers();
    adminUser = users.find(u => u.email === TEST_ADMIN_EMAIL);
  }
  if (!adminUser) throw new Error('Could not create or find test admin user');

  console.log('[setup] Creating test company row…');
  await db.from('companies').upsert(
    { user_id: adminUser.id, name: TEST_ADMIN_COMPANY },
    { onConflict: 'user_id' }
  );

  await db.from('user_profiles').upsert(
    { user_id: adminUser.id, role: 'admin', company_user_id: adminUser.id, employee_id: null },
    { onConflict: 'user_id' }
  );

  console.log('[setup] Creating test employee user…');
  const { data: empData } = await db.auth.admin.createUser({
    email: TEST_EMPLOYEE_EMAIL,
    password: TEST_EMPLOYEE_PASSWORD,
    email_confirm: true,
  });
  let empUser = empData?.user;
  if (!empUser) {
    const { data: { users } } = await db.auth.admin.listUsers();
    empUser = users.find(u => u.email === TEST_EMPLOYEE_EMAIL);
  }
  if (!empUser) throw new Error('Could not create or find test employee user');

  console.log('[setup] Creating test employee row…');
  const empRow = await db.from('employees').upsert(
    {
      user_id:            adminUser.id,
      auth_user_id:       empUser.id,
      name:               TEST_EMPLOYEE_NAME,
      work_email:         TEST_EMPLOYEE_EMAIL.toLowerCase(),
      basic_salary:       5000,
      employment_status:  'Full-Time',
      active:             true,
    },
    { onConflict: 'user_id,work_email' }
  ).select().single();

  const employeeId = empRow.data?.id;

  if (employeeId) {
    await db.from('user_profiles').upsert(
      {
        user_id:         empUser.id,
        role:            'employee',
        company_user_id: adminUser.id,
        employee_id:     employeeId,
      },
      { onConflict: 'user_id' }
    );
  }

  // ── Save browser sessions so tests don't need to log in every time ──────────
  mkdirSync('.playwright', { recursive: true });

  const browser = await chromium.launch();

  console.log('[setup] Saving admin session state…');
  const adminCtx = await browser.newContext({ baseURL: 'http://localhost:5173' });
  const adminPage = await adminCtx.newPage();
  await adminPage.goto('http://localhost:5173');
  await adminPage.getByRole('button', { name: /sign in as admin/i }).click();
  await adminPage.locator('input[type="email"]').fill(TEST_ADMIN_EMAIL);
  await adminPage.locator('input[type="password"]').fill(TEST_ADMIN_PASSWORD);
  await adminPage.getByRole('button', { name: /^sign in$/i }).click();
  await adminPage.waitForSelector('.sidebar-logo', { timeout: 15000 });
  await adminCtx.storageState({ path: '.playwright/admin-session.json' });
  await adminCtx.close();

  console.log('[setup] Saving employee session state…');
  const empCtx = await browser.newContext({ baseURL: 'http://localhost:5173' });
  const empPage = await empCtx.newPage();
  await empPage.goto('http://localhost:5173');
  await empPage.getByRole('button', { name: /sign in as employee/i }).click();
  await empPage.locator('input[type="email"]').fill(TEST_EMPLOYEE_EMAIL);
  await empPage.locator('input[type="password"]').fill(TEST_EMPLOYEE_PASSWORD);
  await empPage.getByRole('button', { name: /^sign in$/i }).click();
  await empPage.waitForSelector('.sidebar-logo', { timeout: 15000 });
  await empCtx.storageState({ path: '.playwright/employee-session.json' });
  await empCtx.close();

  await browser.close();

  // Write env values for test files to read
  writeFileSync('.playwright/env.json', JSON.stringify({
    adminId: adminUser.id,
    employeeId,
  }));

  console.log('[setup] Done.\n');
}
