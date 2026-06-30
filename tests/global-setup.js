/**
 * global-setup.js — Runs once before all tests.
 *
 * 1. Creates three test users (admin, employee, manager) and their DB rows.
 * 2. Links employee + manager auth accounts to their employee rows.
 * 3. Sets test employee's reporting_manager_id → test manager (cross-profile queue tests).
 * 4. Seeds deterministic test data so data-conditional tests never skip:
 *    leave types, leave requests, expense claims, salary advances, assets,
 *    training records, certifications, insurance policy, letter requests.
 * 5. Saves three browser sessions (.playwright/*.session.json).
 * 6. Writes .playwright/env.json with all IDs for teardown + tests.
 */
import { chromium } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';
import { config } from 'dotenv';
import { writeFileSync, mkdirSync } from 'fs';

config({ path: '.env.test' });

const {
  VITE_SUPABASE_URL,
  VITE_SUPABASE_ANON_KEY,
  SUPABASE_SERVICE_ROLE_KEY,
  TEST_ADMIN_EMAIL,
  TEST_ADMIN_PASSWORD,
  TEST_ADMIN_COMPANY,
  TEST_EMPLOYEE_EMAIL,
  TEST_EMPLOYEE_PASSWORD,
  TEST_EMPLOYEE_NAME,
  TEST_MANAGER_EMAIL,
  TEST_MANAGER_PASSWORD,
  TEST_MANAGER_NAME,
} = process.env;

/** Create a user or return the existing one by email. */
async function ensureUser(db, email, password, label) {
  const { data: created, error: createErr } = await db.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (created?.user) return created.user;

  console.log(`  [${label}] create: ${createErr?.message ?? 'no user'} — searching…`);
  let page = 1;
  while (true) {
    const { data, error: listErr } = await db.auth.admin.listUsers({ page, perPage: 50 });
    if (listErr) throw new Error(`listUsers failed for ${label}: ${listErr.message}`);
    const found = data.users.find(u => u.email?.toLowerCase() === email.toLowerCase());
    if (found) return found;
    if (data.users.length < 50) break;
    page++;
  }
  throw new Error(
    `Could not create or find ${label} user (${email}).\n` +
    `  Make sure SUPABASE_SERVICE_ROLE_KEY is the service_role key.\n` +
    `  Find it at: Supabase Dashboard → Project Settings → API → service_role`
  );
}

/** Upsert a single employee row, returning its id. */
async function ensureEmployee(db, adminId, companyId, rowData) {
  const { data: existing } = await db
    .from('employees')
    .select('id')
    .eq('user_id', adminId)
    .eq('work_email', rowData.work_email)
    .maybeSingle();

  if (existing) {
    await db.from('employees')
      .update({ auth_user_id: rowData.auth_user_id, active: true, company_id: companyId })
      .eq('id', existing.id);
    return existing.id;
  }
  const { data: inserted, error } = await db.from('employees').insert(rowData).select('id').single();
  if (error) console.warn(`  employees insert (${rowData.work_email}):`, error.message);
  return inserted?.id;
}

export default async function globalSetup() {
  if (!SUPABASE_SERVICE_ROLE_KEY || SUPABASE_SERVICE_ROLE_KEY === 'PASTE_YOUR_SERVICE_ROLE_KEY_HERE') {
    throw new Error(
      '\n  SUPABASE_SERVICE_ROLE_KEY is missing.\n' +
      '  Supabase Dashboard → Project Settings → API → service_role key → paste into .env.test\n'
    );
  }
  if (!VITE_SUPABASE_URL) throw new Error('VITE_SUPABASE_URL missing from .env.test');

  console.log('\n[setup] Connecting to Supabase:', VITE_SUPABASE_URL);

  const db = createClient(VITE_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  // ── Admin user + company ─────────────────────────────────────────────────────
  console.log('[setup] Ensuring test admin user…');
  const adminUser = await ensureUser(db, TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, 'admin');
  console.log(`  admin id: ${adminUser.id}`);

  const { data: existingCo } = await db
    .from('companies').select('id')
    .eq('user_id', adminUser.id)
    .order('created_at', { ascending: true }).limit(1).maybeSingle();

  let companyId = existingCo?.id;
  if (existingCo) {
    await db.from('companies').update({ name: TEST_ADMIN_COMPANY }).eq('id', existingCo.id);
  } else {
    const { data: newCo } = await db.from('companies')
      .insert({ user_id: adminUser.id, name: TEST_ADMIN_COMPANY }).select('id').single();
    companyId = newCo?.id;
  }

  await db.from('user_profiles').upsert(
    { user_id: adminUser.id, role: 'admin', company_user_id: adminUser.id, employee_id: null },
    { onConflict: 'user_id' }
  );

  // ── Employee user ────────────────────────────────────────────────────────────
  console.log('[setup] Ensuring test employee user…');
  const empUser = await ensureUser(db, TEST_EMPLOYEE_EMAIL, TEST_EMPLOYEE_PASSWORD, 'employee');
  console.log(`  employee auth id: ${empUser.id}`);

  const baseEmpRow = {
    user_id: adminUser.id, company_id: companyId, auth_user_id: empUser.id,
    name: TEST_EMPLOYEE_NAME, work_email: TEST_EMPLOYEE_EMAIL.toLowerCase(),
    emp_no: 'TEST-001', mol_id: '', bank_name: '', bank_routing_code: '', iban: '',
    basic_salary: 5000, allowance: 500, employment_status: 'Full-Time',
    contract_type: 'Unlimited', active: true,
    personal_email: '', phone: '', gender: 'Male', marital_status: 'Single',
    home_country_address: '', photo_url: '',
    emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '',
    job_title: 'Test Employee', department: 'Engineering',
    nationality: 'Indian', employment_start_date: '2024-01-01',
  };

  const employeeId = await ensureEmployee(db, adminUser.id, companyId, baseEmpRow);
  console.log(`  employee row id: ${employeeId}`);

  // ── Manager user ─────────────────────────────────────────────────────────────
  console.log('[setup] Ensuring test manager user…');
  const mgrEmail    = TEST_MANAGER_EMAIL    || 'test.manager@workloop-test.local';
  const mgrPassword = TEST_MANAGER_PASSWORD || 'TestManager123!';
  const mgrName     = TEST_MANAGER_NAME     || 'Test Manager';

  const mgrUser = await ensureUser(db, mgrEmail, mgrPassword, 'manager');
  console.log(`  manager auth id: ${mgrUser.id}`);

  const mgrEmpRow = {
    user_id: adminUser.id, company_id: companyId, auth_user_id: mgrUser.id,
    name: mgrName, work_email: mgrEmail.toLowerCase(),
    emp_no: 'TEST-MGR-001', mol_id: '', bank_name: '', bank_routing_code: '', iban: '',
    basic_salary: 8000, allowance: 1000, employment_status: 'Full-Time',
    contract_type: 'Unlimited', active: true,
    personal_email: '', phone: '', gender: 'Male', marital_status: 'Single',
    home_country_address: '', photo_url: '',
    emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '',
    job_title: 'Test Manager', department: 'Engineering',
    nationality: 'Indian', employment_start_date: '2023-01-01',
  };

  const managerEmpId = await ensureEmployee(db, adminUser.id, companyId, mgrEmpRow);
  console.log(`  manager emp row id: ${managerEmpId}`);

  // Set the test employee's reporting manager so Leave Queue + Expense Queue populate
  if (employeeId && managerEmpId) {
    await db.from('employees').update({ reporting_manager_id: managerEmpId }).eq('id', employeeId);
    console.log(`  employee.reporting_manager_id → ${managerEmpId}`);
  }

  // Upsert user_profiles for both linked users
  if (employeeId) {
    await db.from('user_profiles').upsert(
      { user_id: empUser.id, role: 'employee', company_user_id: adminUser.id, employee_id: employeeId },
      { onConflict: 'user_id' }
    );
  }
  if (managerEmpId) {
    await db.from('user_profiles').upsert(
      { user_id: mgrUser.id, role: 'manager', company_user_id: adminUser.id, employee_id: managerEmpId },
      { onConflict: 'user_id' }
    );
  }

  // ── Migration health check ───────────────────────────────────────────────────
  {
    const { error: migCheck } = await db.from('employees').select('licence_authority').limit(0);
    if (migCheck) {
      console.warn('\n  ⚠️  WARNING: sql/033_clinical_gaps.sql has not been applied.');
      console.warn('     Run it in Supabase SQL Editor — employee INSERT tests will skip until then.\n');
    }
  }

  // ── Seed test data ───────────────────────────────────────────────────────────
  // All seeding is idempotent: delete-then-insert using the test admin's user_id scope.
  // global-teardown.js removes all seeded rows; global-setup re-creates them fresh each run.
  const adminId = adminUser.id;

  console.log('[setup] Seeding leave types…');
  const { data: existingLt } = await db.from('leave_types').select('id').eq('user_id', adminId).limit(1);
  if (!existingLt?.length) {
    await db.from('leave_types').insert([
      {
        user_id: adminId, code: 'ANNUAL', name: 'Annual Leave', color: '#2563EB',
        is_paid: true, is_unlimited: false, requires_approval: true, requires_attachment: false,
        requires_reason: false, min_notice_days: 1, annual_entitlement_days: 30,
        accrual_type: 'monthly', day_count_type: 'calendar', auto_approve: false,
        carry_forward_allowed: true, carry_forward_max_days: 15,
        is_active: true, sort_order: 0, probation_eligible: true,
      },
      {
        user_id: adminId, code: 'SICK', name: 'Sick Leave', color: '#DC2626',
        is_paid: true, is_unlimited: false, requires_approval: true, requires_attachment: false,
        requires_reason: false, min_notice_days: 0, annual_entitlement_days: 15,
        accrual_type: 'fixed', day_count_type: 'calendar', auto_approve: false,
        carry_forward_allowed: false, carry_forward_max_days: 0,
        is_active: true, sort_order: 1, probation_eligible: true,
      },
      {
        user_id: adminId, code: 'EMERGENCY', name: 'Emergency Leave', color: '#F59E0B',
        is_paid: true, is_unlimited: false, requires_approval: true, requires_attachment: false,
        requires_reason: true, min_notice_days: 0, annual_entitlement_days: 5,
        accrual_type: 'fixed', day_count_type: 'calendar', auto_approve: false,
        carry_forward_allowed: false, carry_forward_max_days: 0,
        is_active: true, sort_order: 2, probation_eligible: true,
      },
      {
        user_id: adminId, code: 'HAJJ', name: 'Hajj Leave', color: '#059669',
        is_paid: true, is_unlimited: false, requires_approval: true, requires_attachment: false,
        requires_reason: false, min_notice_days: 30, annual_entitlement_days: 21,
        accrual_type: 'fixed', day_count_type: 'calendar', auto_approve: false,
        carry_forward_allowed: false, carry_forward_max_days: 0,
        is_active: true, sort_order: 3, probation_eligible: false,
      },
    ]);
    console.log('  inserted 4 leave types');
  } else {
    console.log(`  leave types already exist (${existingLt.length}+ rows)`);
  }

  // Get annual leave type id for request seeding
  const { data: annualLt } = await db
    .from('leave_types').select('id').eq('user_id', adminId).eq('code', 'ANNUAL').maybeSingle();

  // Seed leave requests — 8 Pending + 1 Approved.
  // Multiple pending requests are needed because specs run alphabetically and each
  // action test (approve/reject) consumes one. Consumption chain across the suite:
  //   cross-profile.spec.js  → 2 consumed (approve + reject)
  //   leave.spec.js          → 1 consumed (approve)
  //   manager-portal.spec.js → 2 consumed (approve + reject)
  //   multi-level-leave.spec.js → up to 2 consumed
  // 8 pending leaves ensures all action paths run without skipping.
  if (employeeId && annualLt?.id) {
    console.log('[setup] Seeding leave requests…');
    await db.from('leave_requests').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('reason', '%PLAYWRIGHT_SEED%');

    const today = new Date();
    const fmt = d => d.toISOString().split('T')[0];
    const d = n => new Date(today.getTime() + n * 86400000);

    const pendingLeaves = [7, 14, 21, 28, 35, 42, 49, 56].map((offset, i) => ({
      user_id: adminId, employee_id: employeeId,
      leave_type_id: annualLt.id, leave_type_code: 'ANNUAL',
      start_date: fmt(d(offset)), end_date: fmt(d(offset + 2)),
      days_requested: 3, status: 'Pending',
      reason: `PLAYWRIGHT_SEED pending leave ${i + 1}`, is_half_day: false,
      approval_level_required: 1,
    }));

    await db.from('leave_requests').insert([
      ...pendingLeaves,
      {
        user_id: adminId, employee_id: employeeId,
        leave_type_id: annualLt.id, leave_type_code: 'ANNUAL',
        start_date: fmt(d(-14)), end_date: fmt(d(-12)),
        days_requested: 3, status: 'Approved',
        reason: 'PLAYWRIGHT_SEED approved leave', is_half_day: false,
        approval_level_required: 1,
      },
    ]);
    console.log('  inserted 9 leave requests (8 pending + 1 approved)');
  }

  // Seed expense claims — 6 pending + 1 approved.
  // Consumption chain:
  //   cross-profile.spec.js      → 2 consumed (manager pre-approve + admin approve)
  //   expenses.spec.js           → 2 consumed (approve + reject)
  //   manager-expense-queue.spec.js → 1 consumed (pre-approve)
  //   manager-portal.spec.js     → 1 consumed (pre-approve)
  // 6 pending ensures all action paths run without skipping.
  if (employeeId) {
    console.log('[setup] Seeding expense claims…');
    await db.from('expense_claims').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('description', '%PLAYWRIGHT_SEED%');

    const today = new Date().toISOString().split('T')[0];
    await db.from('expense_claims').insert([
      {
        user_id: adminId, employee_id: employeeId,
        category: 'travel', amount: 350, expense_date: today,
        description: 'PLAYWRIGHT_SEED — travel to client site', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'training', amount: 200, expense_date: today,
        description: 'PLAYWRIGHT_SEED — online training course', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'accommodation', amount: 450, expense_date: today,
        description: 'PLAYWRIGHT_SEED — client visit hotel', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'equipment', amount: 300, expense_date: today,
        description: 'PLAYWRIGHT_SEED — office equipment', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'fuel', amount: 150, expense_date: today,
        description: 'PLAYWRIGHT_SEED — fuel reimbursement', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'other', amount: 80, expense_date: today,
        description: 'PLAYWRIGHT_SEED — office supplies', status: 'pending',
      },
      {
        user_id: adminId, employee_id: employeeId,
        category: 'meals', amount: 120, expense_date: today,
        description: 'PLAYWRIGHT_SEED — team lunch', status: 'approved',
      },
    ]);
    console.log('  inserted 7 expense claims (6 pending + 1 approved)');
  }

  // Seed salary advances — 3 pending + 1 active.
  // Consumption chain:
  //   advances.spec.js     → 1 consumed (admin approve)
  //   cross-profile.spec.js → 1 consumed (admin approve)
  // 3 pending leaves 1 unconsumed for display/history tests.
  if (employeeId) {
    console.log('[setup] Seeding salary advances…');
    await db.from('salary_advances').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('reason', '%PLAYWRIGHT_SEED%');

    const today = new Date().toISOString().split('T')[0];
    await db.from('salary_advances').insert([
      {
        user_id: adminId, employee_id: employeeId,
        amount: 1500, reason: 'PLAYWRIGHT_SEED — pending advance 1',
        status: 'pending', repayment_months: 3, monthly_deduction: 500, outstanding_balance: 1500,
        disbursement_date: today,
      },
      {
        user_id: adminId, employee_id: employeeId,
        amount: 1200, reason: 'PLAYWRIGHT_SEED — pending advance 2',
        status: 'pending', repayment_months: 3, monthly_deduction: 400, outstanding_balance: 1200,
        disbursement_date: today,
      },
      {
        user_id: adminId, employee_id: employeeId,
        amount: 800, reason: 'PLAYWRIGHT_SEED — pending advance 3',
        status: 'pending', repayment_months: 2, monthly_deduction: 400, outstanding_balance: 800,
        disbursement_date: today,
      },
      {
        user_id: adminId, employee_id: employeeId,
        amount: 2000, reason: 'PLAYWRIGHT_SEED — active advance',
        status: 'active', repayment_months: 4, monthly_deduction: 500, outstanding_balance: 2000,
        disbursement_date: today,
      },
    ]);
    console.log('  inserted 4 salary advances (3 pending + 1 active)');
  }

  // Seed an available asset
  console.log('[setup] Seeding assets…');
  await db.from('assets').delete().eq('user_id', adminId).like('serial_no', 'PW-TEST-%');
  await db.from('assets').insert([
    {
      user_id: adminId, name: 'Playwright Test Laptop', category: 'laptop',
      serial_no: 'PW-TEST-001', status: 'available',
      purchase_date: '2025-01-01', purchase_cost: 5000,
      notes: 'PLAYWRIGHT_SEED',
    },
    {
      user_id: adminId, name: 'Playwright Test Phone', category: 'phone',
      serial_no: 'PW-TEST-002', status: 'available',
      purchase_date: '2025-03-01', purchase_cost: 2000,
      notes: 'PLAYWRIGHT_SEED',
    },
  ]);
  console.log('  inserted 2 assets');

  // Seed training records + certifications
  if (employeeId) {
    console.log('[setup] Seeding training records…');
    await db.from('training_records').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('training_title', 'PLAYWRIGHT_SEED%');
    await db.from('training_records').insert({
      user_id: adminId, employee_id: employeeId,
      training_title: 'PLAYWRIGHT_SEED — React Advanced',
      training_type: 'online', status: 'completed',
      start_date: '2025-04-01', end_date: '2025-04-30',
      duration_hours: 20, score: 90, passed: true,
    });

    console.log('[setup] Seeding certifications…');
    await db.from('certifications').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('certification_name', 'PLAYWRIGHT_SEED%');
    const today = new Date();
    const expiry = new Date(today.getTime() + 400 * 86400000).toISOString().split('T')[0];
    await db.from('certifications').insert({
      user_id: adminId, employee_id: employeeId,
      certification_name: 'PLAYWRIGHT_SEED — AWS Solutions Architect',
      issuing_body: 'Amazon Web Services',
      certificate_no: 'PW-CERT-001',
      issued_date: '2025-01-01',
      expiry_date: expiry,
    });
    console.log('  inserted 1 training record + 1 certification');
  }

  // Seed insurance policy
  console.log('[setup] Seeding insurance policy…');
  await db.from('insurance_policies').delete().eq('user_id', adminId).like('policy_number', 'PW-POL-%');
  const { data: insPolicy } = await db.from('insurance_policies').insert({
    user_id: adminId,
    insurer_name: 'Playwright Test Insurer',
    policy_number: 'PW-POL-001',
    tier: 'Basic',
    annual_premium: 5000,
    renewal_date: '2027-01-01',
    broker: 'Test Broker',
  }).select('id').single();
  console.log('  inserted insurance policy');

  // Seed letter request
  if (employeeId) {
    console.log('[setup] Seeding letter request…');
    await db.from('letter_requests').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('purpose', '%PLAYWRIGHT_SEED%');
    await db.from('letter_requests').insert({
      user_id: adminId, employee_id: employeeId,
      letter_type: 'salary_certificate',
      purpose: 'PLAYWRIGHT_SEED — bank loan application',
      status: 'pending',
    });
    console.log('  inserted 1 letter request');
  }

  // Seed a payroll run in draft state so payroll tests don't skip
  console.log('[setup] Seeding draft payroll run…');
  await db.from('payroll_entries').delete().in(
    'payroll_run_id',
    (await db.from('payroll_runs').select('id').eq('user_id', adminId).like('period', 'PW-TEST-%')).data?.map(r => r.id) ?? []
  );
  await db.from('payroll_runs').delete().eq('user_id', adminId).like('period', 'PW-TEST-%');

  const { data: payrollRun } = await db.from('payroll_runs').insert({
    user_id: adminId, company_id: companyId,
    period: 'PW-TEST-2026-06', period_label: 'June 2026 (Test)',
    status: 'draft', approval_status: 'draft',
  }).select('id').single();

  if (payrollRun?.id && employeeId) {
    await db.from('payroll_entries').insert({
      payroll_run_id: payrollRun.id, user_id: adminId, employee_id: employeeId,
      basic_salary: 5000, allowance: 500, other_allowance: 0,
      deductions: 0, leave_deduction: 0, advance_deduction: 0,
      gross_salary: 5500, net_salary: 5500,
    });
    console.log('  inserted draft payroll run + 1 entry');
  }

  // Seed payslip for the test employee (makes employee portal Payslips tab non-empty)
  if (payrollRun?.id && employeeId) {
    console.log('[setup] Seeding payslip…');
    await db.from('payslips').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).eq('payroll_run_id', payrollRun.id);
    await db.from('payslips').insert({
      user_id: adminId, employee_id: employeeId, payroll_run_id: payrollRun.id,
      period: 'PW-TEST-2026-06', payment_date: new Date().toISOString().split('T')[0],
      gross_pay: 5500, net_pay: 5500,
      data_snapshot: { basicSalary: 5000, allowance: 500 },
    });
    console.log('  inserted 1 payslip');
  }

  // ── Probation employee (probation.spec.js + probation-leave-rules.spec.js) ───
  console.log('[setup] Ensuring probation employee…');
  const fmtDate = d => d.toISOString().split('T')[0];
  const addDays  = n => new Date(new Date().getTime() + n * 86400000);

  const probationEmpRow = {
    user_id: adminId, company_id: companyId,
    name: 'Test Probation Employee', work_email: 'test.probation@workloop-test.local',
    emp_no: 'TEST-PROB-001', mol_id: '', bank_name: '', bank_routing_code: '', iban: '',
    basic_salary: 4000, allowance: 400, employment_status: 'Probation',
    contract_type: 'Unlimited', active: true,
    personal_email: '', phone: '', gender: 'Male', marital_status: 'Single',
    home_country_address: '', photo_url: '',
    emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '',
    job_title: 'Test Probation Staff', department: 'Engineering',
    nationality: 'Indian', employment_start_date: '2026-01-15',
    probation_end_date: fmtDate(addDays(14)),
  };
  const probationEmpId = await ensureEmployee(db, adminId, companyId, probationEmpRow);
  // ensureEmployee resets active=true on update — also force correct status
  if (probationEmpId) {
    await db.from('employees').update({
      employment_status: 'Probation', active: true,
      probation_end_date: fmtDate(addDays(14)),
    }).eq('id', probationEmpId);
  }
  console.log(`  probation employee id: ${probationEmpId}`);

  // ── Terminated employee (offboarding.spec.js) ────────────────────────────────
  console.log('[setup] Ensuring terminated employee…');
  const terminatedEmpRow = {
    user_id: adminId, company_id: companyId,
    name: 'Test Terminated Employee', work_email: 'test.terminated@workloop-test.local',
    emp_no: 'TEST-TERM-001', mol_id: '', bank_name: '', bank_routing_code: '', iban: '',
    basic_salary: 3000, allowance: 300, employment_status: 'Terminated',
    contract_type: 'Unlimited', active: false,
    personal_email: '', phone: '', gender: 'Female', marital_status: 'Single',
    home_country_address: '', photo_url: '',
    emergency_contact_name: '', emergency_contact_relationship: '', emergency_contact_phone: '',
    job_title: 'Test Terminated Staff', department: 'Engineering',
    nationality: 'Indian', employment_start_date: '2024-01-01',
  };
  const terminatedEmpId = await ensureEmployee(db, adminId, companyId, terminatedEmpRow);
  // ensureEmployee resets active=true — force Terminated state
  if (terminatedEmpId) {
    await db.from('employees').update({ employment_status: 'Terminated', active: false }).eq('id', terminatedEmpId);
  }
  console.log(`  terminated employee id: ${terminatedEmpId}`);

  // ── Department (clinical-dashboard.spec.js + departments.spec.js) ────────────
  console.log('[setup] Seeding Engineering department…');
  const { data: existingDept } = await db.from('departments')
    .select('id').eq('user_id', adminId).eq('name', 'Engineering').maybeSingle();
  let deptId = existingDept?.id;
  if (!existingDept) {
    const { data: dept } = await db.from('departments').insert({
      user_id: adminId, name: 'Engineering', color: '#2563EB',
      description: 'Software Engineering Department', sort_order: 0,
    }).select('id').single();
    deptId = dept?.id;
    console.log('  inserted Engineering department');
  } else {
    console.log('  Engineering department already exists');
  }

  // ── Shift template (clinical-rota.spec.js + professional-licences.spec.js) ───
  console.log('[setup] Seeding shift template…');
  const { data: existingShift } = await db.from('shifts')
    .select('id').eq('user_id', adminId).eq('name', 'PW Morning Shift').maybeSingle();
  let shiftId = existingShift?.id;
  if (!existingShift) {
    const { data: shift, error: shiftErr } = await db.from('shifts').insert({
      user_id: adminId, name: 'PW Morning Shift', code: 'M',
      shift_category: 'morning', shift_type: 'fixed',
      start_time: '07:00', end_time: '15:00',
      break_minutes: 60, expected_hours: 8,
      late_grace_minutes: 10, early_departure_grace_minutes: 10,
      is_overnight: false, is_active: true, color: '#2563EB', min_staff: 1,
    }).select('id').single();
    if (shiftErr) console.warn('  shift insert:', shiftErr.message);
    shiftId = shift?.id;
    if (shiftId) console.log('  inserted PW Morning Shift template');
  } else {
    console.log('  shift template already exists');
  }

  // ── Roster assignments (clinical-rota + employee portal Schedule + professional-licences) ─
  if (shiftId && employeeId) {
    console.log('[setup] Seeding roster assignments…');
    const rosterDates = [0, 1, 2, 3, 4].map(n => fmtDate(addDays(n)));
    for (const date of rosterDates) {
      await db.from('roster_assignments')
        .delete().eq('user_id', adminId).eq('employee_id', employeeId).eq('date', date);
      const { error: raErr } = await db.from('roster_assignments').insert({
        user_id: adminId, employee_id: employeeId, date, shift_id: shiftId,
        published: true, planned_hours: 8,
      });
      if (raErr) console.warn(`  roster ${date}:`, raErr.message);
    }
    console.log('  inserted 5 roster assignments (today + 4 days, published)');
  }

  // ── Appraisal cycle + appraisals (appraisals.spec.js) ───────────────────────
  console.log('[setup] Seeding appraisal cycle…');
  const { data: existingCycle } = await db.from('appraisal_cycles')
    .select('id').eq('user_id', adminId).eq('name', 'PW Test Cycle 2026-Q2').maybeSingle();
  let appraisalCycleId = existingCycle?.id;
  if (!existingCycle) {
    const { data: cycle, error: cycleErr } = await db.from('appraisal_cycles').insert({
      user_id: adminId, name: 'PW Test Cycle 2026-Q2',
      review_from: '2026-04-01', review_to: '2026-06-30', status: 'active',
    }).select('id').single();
    if (cycleErr) console.warn('  appraisal cycle insert:', cycleErr.message);
    appraisalCycleId = cycle?.id;
    if (appraisalCycleId) console.log('  inserted appraisal cycle');
  } else {
    console.log('  appraisal cycle already exists');
  }

  if (appraisalCycleId && employeeId) {
    const { data: existingAppr } = await db.from('appraisals')
      .select('id').eq('user_id', adminId).eq('cycle_id', appraisalCycleId).eq('employee_id', employeeId).maybeSingle();
    if (!existingAppr) {
      const { data: appr, error: apprErr } = await db.from('appraisals').insert({
        user_id: adminId, cycle_id: appraisalCycleId, employee_id: employeeId, status: 'pending',
      }).select('id').single();
      if (apprErr) console.warn('  appraisal insert:', apprErr.message);
      if (appr?.id) {
        await db.from('appraisal_sections').insert([
          { appraisal_id: appr.id, section_name: 'Performance',   weight: 0.4, sort_order: 0 },
          { appraisal_id: appr.id, section_name: 'Teamwork',      weight: 0.3, sort_order: 1 },
          { appraisal_id: appr.id, section_name: 'Communication', weight: 0.3, sort_order: 2 },
        ]);
        console.log('  inserted appraisal + 3 sections for test employee');
      }
    } else {
      console.log('  appraisal already exists for test employee');
    }
  }

  // ── Staffing rules (reports.spec.js Staffing Compliance + professional-licences.spec.js) ─
  console.log('[setup] Seeding staffing rule…');
  const { data: existingRule } = await db.from('department_staffing_rules')
    .select('id').eq('user_id', adminId).eq('department', 'Engineering').eq('shift_category', 'morning').maybeSingle();
  if (!existingRule) {
    const { error: ruleErr } = await db.from('department_staffing_rules').insert({
      user_id: adminId, department: 'Engineering', shift_category: 'morning',
      min_staff: 2, effective_from: '2026-01-01',
    });
    if (ruleErr) console.warn('  staffing rule insert:', ruleErr.message);
    else console.log('  inserted staffing rule: Engineering / morning / min 2');
  } else {
    console.log('  staffing rule already exists');
  }

  // ── Employee documents (clinical-credentials.spec.js) ───────────────────────
  if (employeeId) {
    console.log('[setup] Seeding employee documents…');
    await db.from('employee_documents').delete()
      .eq('user_id', adminId).eq('employee_id', employeeId).like('file_name', 'PW-TEST-%');
    const { error: docsErr } = await db.from('employee_documents').insert([
      {
        user_id: adminId, employee_id: employeeId,
        document_type: 'DHA Licence', document_number: 'DHA-TEST-001',
        file_name: 'PW-TEST-dha_licence.pdf', file_size: 1024,
        storage_path: `${adminId}/${employeeId}/1000000_PW-TEST-dha_licence.pdf`,
        expiry_date: '2027-01-01', status: 'verified', submitted_by: 'admin',
        notes: 'PLAYWRIGHT_SEED',
      },
      {
        user_id: adminId, employee_id: employeeId,
        document_type: 'BLS Certificate', document_number: 'BLS-TEST-EMP-001',
        file_name: 'PW-TEST-bls_certificate.pdf', file_size: 2048,
        storage_path: `${adminId}/${employeeId}/1000001_PW-TEST-bls_certificate.pdf`,
        expiry_date: '2027-06-01', status: 'pending', submitted_by: 'employee',
        notes: 'PLAYWRIGHT_SEED',
      },
    ]);
    if (docsErr) console.warn('  employee documents insert:', docsErr.message);
    else console.log('  inserted 2 employee documents (admin/verified + employee/pending)');
  }

  // ── Set manager user_profiles to role='manager' ─────────────────────────────
  // MUST run before browser sessions so the manager's INITIAL_SESSION finds the
  // correct role row. user_profiles has no UNIQUE constraint on user_id, so upsert
  // with onConflict creates duplicate rows. Fix: delete all rows then insert one.
  // Requires sql/034_manager_role.sql to have been applied so role='manager' passes
  // the user_profiles_role_check constraint.
  if (managerEmpId && mgrUser?.id) {
    await db.from('user_profiles').delete().eq('user_id', mgrUser.id);
    const { error: mgrProfErr } = await db.from('user_profiles').insert({
      user_id: mgrUser.id, role: 'manager',
      company_user_id: adminUser.id, employee_id: managerEmpId,
    });
    if (mgrProfErr) {
      throw new Error(
        `[setup] Failed to insert manager user_profiles with role='manager': ${mgrProfErr.message}\n` +
        `  → Run sql/034_manager_role.sql in Supabase SQL Editor first:\n` +
        `      ALTER TABLE user_profiles DROP CONSTRAINT IF EXISTS user_profiles_role_check;\n` +
        `      ALTER TABLE user_profiles ADD CONSTRAINT user_profiles_role_check CHECK (role IN ('admin','employee','manager'));`
      );
    }
    console.log('  [setup] Manager user_profiles set to role=manager');
  }

  // ── Save browser sessions ────────────────────────────────────────────────────
  mkdirSync('.playwright', { recursive: true });
  const browser = await chromium.launch();

  console.log('[setup] Saving admin browser session…');
  const adminCtx = await browser.newContext();
  const adminPage = await adminCtx.newPage();
  await adminPage.goto('http://localhost:5173');
  await adminPage.getByRole('button', { name: /sign in as admin/i }).click();
  await adminPage.waitForTimeout(500);
  await adminPage.locator('input[type="email"]').fill(TEST_ADMIN_EMAIL);
  await adminPage.locator('input[type="password"]').fill(TEST_ADMIN_PASSWORD);
  await adminPage.locator('button[type="submit"]').click();
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
  await empPage.waitForSelector('.emp-sidebar-logo', { timeout: 25000 });
  await empCtx.storageState({ path: '.playwright/employee-session.json' });
  await empCtx.close();

  // Manager session: sign in programmatically (bypasses browser auth flow which
  // may call linkEmployeeAccount() and overwrite the user_profiles row we just set).
  // Build the localStorage state Supabase expects from a direct signInWithPassword call.
  console.log('[setup] Creating manager session programmatically…');
  {
    const projectRef = VITE_SUPABASE_URL.match(/https:\/\/([^.]+)\.supabase/)?.[1];
    const anonDb = createClient(VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, {
      auth: { autoRefreshToken: false, persistSession: false },
    });
    const { data: mgrLogin, error: mgrLoginErr } = await anonDb.auth.signInWithPassword({
      email: mgrEmail, password: mgrPassword,
    });
    if (mgrLoginErr || !mgrLogin?.session) {
      throw new Error(`[setup] Manager sign-in failed: ${mgrLoginErr?.message ?? 'no session'}`);
    }
    const sess = mgrLogin.session;
    const storageKey = `sb-${projectRef}-auth-token`;
    const storageValue = JSON.stringify({
      access_token:  sess.access_token,
      token_type:    'bearer',
      expires_in:    sess.expires_in,
      expires_at:    sess.expires_at,
      refresh_token: sess.refresh_token,
      user:          sess.user,
    });
    writeFileSync(
      '.playwright/manager-session.json',
      JSON.stringify({
        cookies: [],
        origins: [{
          origin: 'http://localhost:5173',
          localStorage: [{ name: storageKey, value: storageValue }],
        }],
      }, null, 2)
    );
    console.log('  [setup] Manager session file written (fresh tokens, no browser needed)');
  }

  await browser.close();

  writeFileSync(
    '.playwright/env.json',
    JSON.stringify({
      adminId,
      employeeId,
      empAuthId: empUser.id,
      managerEmpId,
      mgrAuthId: mgrUser.id,
      companyId,
      payrollRunId: payrollRun?.id ?? null,
      insPolicyId: insPolicy?.id ?? null,
      probationEmpId: probationEmpId ?? null,
      terminatedEmpId: terminatedEmpId ?? null,
      shiftId: shiftId ?? null,
      appraisalCycleId: appraisalCycleId ?? null,
    })
  );
  console.log('[setup] Done.\n');
}
