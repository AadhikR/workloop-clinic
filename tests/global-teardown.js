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
  const { adminId } = JSON.parse(readFileSync(envPath, 'utf8'));

  console.log('\n[teardown] Cleaning up test attendance data…');
  await db.from('attendance_records').delete().eq('user_id', adminId);
  await db.from('clock_events').delete().eq('user_id', adminId);
  await db.from('attendance_periods').delete().eq('user_id', adminId);

  console.log('[teardown] Cleaning up test payroll data…');
  const { data: runs } = await db.from('payroll_runs').select('id').eq('user_id', adminId);
  if (runs?.length) {
    const runIds = runs.map(r => r.id);
    await db.from('payroll_entries').delete().in('payroll_run_id', runIds);
    await db.from('payslips').delete().in('payroll_run_id', runIds);
    await db.from('payroll_runs').delete().eq('user_id', adminId);
  }

  console.log('[teardown] Done.\n');
}
