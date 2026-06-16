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

/** Create a user or return the existing one by email. Logs the real error if both fail. */
async function ensureUser(db, email, password, label) {
  // Try creating first
  const { data: created, error: createErr } = await db.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });

  if (created?.user) return created.user;

  // User may already exist — try to find them
  console.log(`  [${label}] create returned: ${createErr?.message ?? 'no user'} — searching existing users…`);

  // listUsers is paginated; iterate all pages
  let page = 1;
  while (true) {
    const { data, error: listErr } = await db.auth.admin.listUsers({ page, perPage: 50 });
    if (listErr) {
      console.error(`  [${label}] listUsers error:`, listErr.message);
      console.error('  → Is your SUPABASE_SERVICE_ROLE_KEY correct? Check Supabase Dashboard → Project Settings → API');
      throw new Error(`listUsers failed for ${label}: ${listErr.message}`);
    }
    const found = data.users.find(u => u.email?.toLowerCase() === email.toLowerCase());
    if (found) return found;
    if (data.users.length < 50) break; // last page
    page++;
  }

  throw new Error(
    `Could not create or find ${label} user (${email}).\n` +
    `  Make sure SUPABASE_SERVICE_ROLE_KEY is the service_role key (not the anon key).\n` +
    `  Find it at: Supabase Dashboard → Project Settings → API → service_role`
  );
}

export default async function globalSetup() {
  if (!SUPABASE_SERVICE_ROLE_KEY || SUPABASE_SERVICE_ROLE_KEY === 'PASTE_YOUR_SERVICE_ROLE_KEY_HERE') {
    throw new Error(
      '\n  SUPABASE_SERVICE_ROLE_KEY is missing or not filled in.\n' +
      '  1. Go to Supabase Dashboard → Project Settings → API\n' +
      '  2. Copy the "service_role" key (the secret one)\n' +
      '  3. Paste it into .env.test as SUPABASE_SERVICE_ROLE_KEY=eyJ...\n'
    );
  }

  if (!VITE_SUPABASE_URL) {
    throw new Error('VITE_SUPABASE_URL missing from .env.test');
  }

  console.log('\n[setup] Connecting to Supabase:', VITE_SUPABASE_URL);

  const db = createClient(VITE_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // ── Admin user ───────────────────────────────────────────────────────────────
  console.log('[setup] Ensuring test admin user exists…');
  const adminUser = await ensureUser(db, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, 'admin');
  console.log(`  admin id: ${adminUser.id}`);

  // companies.user_id no longer has a unique constraint (multi-company support),
  // so select-then-insert/update instead of upsert with onConflict.
  const { data: existingCo } = await db
    .from('companies')
    .select('id')
    .eq('user_id', adminUser.id)
    .maybeSingle();

  let companyId = existingCo?.id;

  if (existingCo) {
    const { error: coErr } = await db.from('companies')
      .update({ name: TEST_ADMIN_COMPANY })
      .eq('id', existingCo.id);
    if (coErr) console.warn('  companies update warning:', coErr.message);
  } else {
    const { data: newCo, error: coErr } = await db.from('companies')
      .insert({ user_id: adminUser.id, name: TEST_ADMIN_COMPANY })
      .select('id').single();
    if (coErr) console.warn('  companies insert warning:', coErr.message);
    companyId = newCo?.id;
  }

  const { error: profErr } = await db.from('user_profiles').upsert(
    { user_id: adminUser.id, role: 'admin', company_user_id: adminUser.id, employee_id: null },
    { onConflict: 'user_id' }
  );
  if (profErr) console.warn('  user_profiles (admin) warning:', profErr.message);

  // ── Employee user ────────────────────────────────────────────────────────────
  console.log('[setup] Ensuring test employee user exists…');
  const empUser = await ensureUser(db, TEST_EMPLOYEE_EMAIL, TEST_EMPLOYEE_PASSWORD, 'employee');
  console.log(`  employee auth id: ${empUser.id}`);

  // employees has no unique constraint on (user_id, work_email) so we
  // select-then-insert/update rather than upsert with onConflict.
  const { data: existingEmp } = await db
    .from('employees')
    .select('id')
    .eq('user_id', adminUser.id)
    .eq('work_email', TEST_EMPLOYEE_EMAIL.toLowerCase())
    .maybeSingle();

  let employeeId = existingEmp?.id;

  // Full row matching all NOT NULL columns in the employees table
  const empRowData = {
    user_id:            adminUser.id,
    company_id:         companyId, // Feature 21: scope to the test admin's branch
    auth_user_id:       empUser.id,
    name:               TEST_EMPLOYEE_NAME,
    work_email:         TEST_EMPLOYEE_EMAIL.toLowerCase(),
    emp_no:             'TEST-001',
    mol_id:             '',
    bank_name:          '',
    bank_routing_code:  '',
    iban:               '',
    basic_salary:       5000,
    allowance:          0,
    employment_status:  'Full-Time',
    contract_type:      'Unlimited',
    active:             true,
    personal_email:     '',
    phone:              '',
    gender:             '',
    marital_status:     '',
    home_country_address: '',
    photo_url:          '',
    emergency_contact_name:         '',
    emergency_contact_relationship: '',
    emergency_contact_phone:        '',
    job_title:          'Test Employee',
    department:         'Test',
  };

  if (existingEmp) {
    console.log(`  found existing employee row: ${existingEmp.id}`);
    await db.from('employees').update({ auth_user_id: empUser.id, active: true, company_id: companyId })
      .eq('id', existingEmp.id);
  } else {
    const { data: newEmp, error: insertErr } = await db.from('employees')
      .insert(empRowData).select().single();
    if (insertErr) console.warn('  employees insert warning:', insertErr.message);
    employeeId = newEmp?.id;
  }
  console.log(`  employee row id: ${employeeId}`);

  if (employeeId) {
    const { error: epErr } = await db.from('user_profiles').upsert(
      {
        user_id:         empUser.id,
        role:            'employee',
        company_user_id: adminUser.id,
        employee_id:     employeeId,
      },
      { onConflict: 'user_id' }
    );
    if (epErr) console.warn('  user_profiles (employee) warning:', epErr.message);
  }

  // ── Save browser sessions ────────────────────────────────────────────────────
  mkdirSync('.playwright', { recursive: true });
  const browser = await chromium.launch();

  console.log('[setup] Saving admin browser session…');
  const adminCtx = await browser.newContext();
  const adminPage = await adminCtx.newPage();
  await adminPage.goto('http://localhost:5173');
  // Click the "Sign in as Admin" tab/button to switch to the admin form
  await adminPage.getByRole('button', { name: /sign in as admin/i }).click();
  await adminPage.waitForTimeout(500);
  await adminPage.locator('input[type="email"]').fill(TEST_ADMIN_EMAIL);
  await adminPage.locator('input[type="password"]').fill(TEST_ADMIN_PASSWORD);
  // Use type=submit to avoid matching the portal-switcher buttons
  await adminPage.locator('button[type="submit"]').click();
  await adminPage.waitForSelector('.sidebar-logo', { timeout: 25000 });
  // Enable the "Advanced features" flag so Assets/Training/Roster nav items
  // (gated behind NAV_ITEMS[].advanced) are visible in tests.
  await adminPage.evaluate(() => localStorage.setItem('workloop-advanced-features', 'true'));
  await adminPage.reload();
  await adminPage.waitForSelector('.sidebar-logo', { timeout: 25000 });
  await adminCtx.storageState({ path: '.playwright/admin-session.json' });
  await adminCtx.close();

  console.log('[setup] Saving employee browser session…');
  const empCtx = await browser.newContext();
  const empPage = await empCtx.newPage();
  await empPage.goto('http://localhost:5173');
  await empPage.getByRole('button', { name: /sign in as employee/i }).click();
  await empPage.waitForTimeout(500);
  await empPage.locator('input[type="email"]').fill(TEST_EMPLOYEE_EMAIL);
  await empPage.locator('input[type="password"]').fill(TEST_EMPLOYEE_PASSWORD);
  await empPage.locator('button[type="submit"]').click();
  // Employee shell uses .emp-sidebar-logo, not .sidebar-logo (that's the admin shell)
  await empPage.waitForSelector('.emp-sidebar-logo', { timeout: 25000 });
  await empCtx.storageState({ path: '.playwright/employee-session.json' });
  await empCtx.close();

  await browser.close();

  writeFileSync('.playwright/env.json', JSON.stringify({ adminId: adminUser.id, employeeId, empAuthId: empUser.id }));
  console.log('[setup] Done.\n');
}
