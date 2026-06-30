/**
 * global-teardown.js — Runs once after all tests.
 * Removes attendance records and clock events created during tests.
 * Leaves the test users and company intact so globalSetup is faster next time.
 */
import { createClient } from '@supabase/supabase-js';
import { config } from 'dotenv';
import { readFileSync, existsSync } from 'fs';

config({ path: '.env.test' });

export default async function globalTeardown() {
  const url = process.env.VITE_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key || key === 'PASTE_YOUR_SERVICE_ROLE_KEY_HERE') {
    console.log('[teardown] Skipping — no service role key.');
    return;
  }
  const db = createClient(url, key, { auth: { autoRefreshToken: false, persistSession: false } });

  const envPath = '.playwright/env.json';
  if (!existsSync(envPath)) return;
  const { adminId, empAuthId, mgrAuthId } = JSON.parse(readFileSync(envPath, 'utf8'));

  console.log('\n[teardown] Cleaning up test attendance data…');
  await db.from('attendance_records').delete().eq('user_id', adminId);
  await db.from('clock_events').delete().eq('user_id', adminId);
  await db.from('attendance_periods').delete().eq('user_id', adminId);
  // Clock-in/out events are recorded under the employee's own auth user_id,
  // not the admin's — clean those up too so "today" doesn't carry a
  // leftover clock-in into the next test run.
  if (empAuthId) {
    await db.from('attendance_records').delete().eq('user_id', empAuthId);
    await db.from('clock_events').delete().eq('user_id', empAuthId);
  }

  console.log('[teardown] Cleaning up test payroll data…');
  const { data: runs } = await db.from('payroll_runs').select('id').eq('user_id', adminId);
  if (runs?.length) {
    const runIds = runs.map(r => r.id);
    await db.from('payroll_entries').delete().in('payroll_run_id', runIds);
    await db.from('payslips').delete().in('payroll_run_id', runIds);
    await db.from('payroll_runs').delete().eq('user_id', adminId);
  }

  // Leave requests and leave types seeded by global-setup
  console.log('[teardown] Cleaning up seeded leave data…');
  await db.from('leave_requests').delete().eq('user_id', adminId).like('reason', '%PLAYWRIGHT_SEED%');

  console.log('[teardown] Cleaning up Feature 1–5 test data…');
  // Nafis reports created during Feature 1 tests
  await db.from('nafis_reports').delete().eq('user_id', adminId);
  // Insurance policies + dependant data from Feature 3 tests
  await db.from('insurance_dependants').delete().eq('user_id', adminId);
  await db.from('employee_insurance').delete().eq('user_id', adminId);
  await db.from('insurance_policies').delete().eq('user_id', adminId);
  // Notifications seeded or auto-generated during Feature 4 tests
  await db.from('notifications').delete().eq('user_id', adminId);
  // Employee documents from Feature 2 tests (DB rows; storage objects are not cleaned here)
  await db.from('employee_documents').delete().eq('user_id', adminId);
  // Salary advances from Feature 5 tests (repayments cascade-delete automatically)
  await db.from('salary_advances').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up Feature 12–13 test data…');
  // Employee contracts (Feature 12) — no rows created by current test suite but clean anyway
  await db.from('employee_contracts').delete().eq('user_id', adminId);
  // Offboarding checklists (Feature 13) — tasks cascade-delete with checklist
  await db.from('offboarding_checklists').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up Feature 14 test data…');
  // Expense claims (Feature 14)
  await db.from('expense_claims').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up Feature 16 test data…');
  // Asset assignments first (FK to assets), then assets
  const { data: testAssets } = await db.from('assets').select('id').eq('user_id', adminId);
  if (testAssets?.length) {
    await db.from('asset_assignments').delete().in('asset_id', testAssets.map(a => a.id));
  }
  await db.from('assets').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up Feature 17 test data…');
  // payroll_approval_log cascades on payroll_runs delete (already handled above)

  console.log('[teardown] Cleaning up Feature 19 test data…');
  await db.from('training_records').delete().eq('user_id', adminId);
  await db.from('certifications').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up Feature 21 test branches…');
  // Remove any extra company branches created by the multi-company tests.
  // Keep only the primary branch (the one with the oldest created_at).
  const { data: branches } = await db.from('companies').select('id, created_at').eq('user_id', adminId).order('created_at', { ascending: true });
  if (branches?.length > 1) {
    const extraIds = branches.slice(1).map(b => b.id);
    await db.from('companies').delete().in('id', extraIds);
  }

  console.log('[teardown] Cleaning up Clinic feature test data…');
  // Clinic 1.3 — Letter requests
  await db.from('letter_requests').delete().eq('user_id', adminId);
  // Roster assignments (seeded by global-setup + created during tests)
  await db.from('roster_assignments').delete().eq('user_id', adminId);
  // Shift template seeded by global-setup (soft-deleted shifts stay but is_active=false)
  await db.from('shifts').delete().eq('user_id', adminId).eq('name', 'PW Morning Shift');
  // Clinic 3.1 — Seeded 'Engineering' department + test departments created by departments.spec.js
  await db.from('departments').delete().eq('user_id', adminId).eq('name', 'Engineering');
  await db.from('departments').delete().eq('user_id', adminId).like('name', 'Playwright Dept%');
  // Clinic 3.2 — No expense claims created by manager-expense-queue.spec.js
  // Clinic 6.1 — Seeded PW Test Cycle + test cycles created by appraisals.spec.js
  // appraisals and appraisal_sections cascade-delete when their cycle is deleted
  await db.from('appraisal_cycles').delete().eq('user_id', adminId).like('name', 'PW Test Cycle%');
  await db.from('appraisal_cycles').delete().eq('user_id', adminId).like('name', 'Playwright Cycle%');
  // Clinic 7.1 — Compliance overrides written during SIF/publish gate tests
  await db.from('compliance_overrides').delete().eq('user_id', adminId);
  // Clinic 7.2 — Staffing rules: seeded Engineering rule + rules created during departments.spec.js
  await db.from('department_staffing_rules').delete().eq('user_id', adminId).eq('department', 'Engineering');
  await db.from('department_staffing_rules').delete().eq('user_id', adminId).like('department', 'Playwright%');

  // Seeded payroll run (period starts with 'PW-TEST-')
  console.log('[teardown] Cleaning up seeded payroll data…');
  const { data: seedRuns } = await db.from('payroll_runs').select('id').eq('user_id', adminId).like('period', 'PW-TEST-%');
  if (seedRuns?.length) {
    await db.from('payroll_entries').delete().in('payroll_run_id', seedRuns.map(r => r.id));
    await db.from('payroll_runs').delete().in('id', seedRuns.map(r => r.id));
  }

  console.log('[teardown] Done.\n');
}
