/**
 * profileStorage.js — user_profiles data layer
 *
 * Handles role resolution for every authenticated user:
 *   - 'admin'    → HR user who owns a company; company_user_id = their own auth.uid()
 *   - 'employee' → linked to an employees row via auth_user_id
 *
 * The auto-link flow (called by AuthContext on first login):
 *   1. Fetch existing profile → if found, done.
 *   2. Check for a company owned by this user → if found, create admin profile.
 *   3. Call link_employee_account() RPC → matches auth.email() to work_email.
 *   4. If still unmatched → new admin (no company set up yet), create admin profile.
 */

import { supabase } from '../lib/supabase';

/**
 * Fetch the profile row for the currently signed-in user.
 * Returns null if no profile exists yet.
 */
export async function getProfile() {
  const { data, error } = await supabase
    .from('user_profiles')
    .select('role, company_user_id, employee_id')
    .maybeSingle();

  if (error) { console.error('getProfile:', error); return null; }
  if (!data)  return null;

  return {
    role:          data.role,
    companyUserId: data.company_user_id,
    employeeId:    data.employee_id ?? null,
  };
}

/**
 * Create an admin profile for the current user.
 * Safe to call if a profile already exists (ON CONFLICT is handled server-side
 * by the unique PK — Supabase returns a 23505 which we swallow).
 */
export async function createAdminProfile(user) {
  // Accept the already-resolved user to avoid a second auth round-trip
  if (!user) {
    const { data: { session } } = await supabase.auth.getSession();
    user = session?.user ?? null;
  }
  if (!user) return null;

  const { error } = await supabase
    .from('user_profiles')
    .insert({
      user_id:         user.id,
      role:            'admin',
      company_user_id: user.id,
      employee_id:     null,
    });

  // 23505 = unique_violation — profile already exists, not a real error
  if (error && error.code !== '23505') {
    console.error('createAdminProfile:', error);
  }

  // Always return a working profile — DB persistence failure must not lock the user out
  return { role: 'admin', companyUserId: user.id, employeeId: null };
}

/**
 * Call the SECURITY DEFINER RPC that matches the signed-in user's email
 * against employees.work_email and writes the auth_user_id link.
 *
 * Returns { success: true, already_linked, employee_id, company_user_id, employee_name }
 *      or { success: false, error: 'no_match' }
 */
export async function linkEmployeeAccount() {
  const { data, error } = await supabase.rpc('link_employee_account');

  if (error) {
    console.error('linkEmployeeAccount RPC:', error);
    return { success: false, error: error.message };
  }

  return data;
}

/**
 * Fetch the employee record for the currently signed-in employee.
 * Relies on the RLS policy: employees.auth_user_id = auth.uid()
 *
 * Returns null for admin users (their UID is not stored as auth_user_id
 * on any employee row).
 */
export async function getMyEmployeeRecord() {
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user ?? null;
  if (!user) return null;

  const { data, error } = await supabase
    .from('employees')
    .select('*')
    .eq('auth_user_id', user.id)
    .maybeSingle();

  if (error) { console.error('getMyEmployeeRecord:', error); return null; }
  return data;
}

/**
 * Fetch the company record for the currently signed-in employee.
 * Requires the "employees: read own company" RLS policy on the companies table.
 */
export async function getMyCompany() {
  const profile = await getProfile();
  if (!profile?.companyUserId) return null;

  const { data, error } = await supabase
    .from('companies')
    .select('*')
    .eq('user_id', profile.companyUserId)
    .maybeSingle();

  if (error) { console.error('getMyCompany:', error); return null; }
  return data;
}

/**
 * Admin: get the current portal role of an employee ('employee', 'manager', or null if not activated).
 */
export async function getEmployeePortalRole(employeeId) {
  const { data, error } = await supabase.rpc('admin_get_employee_portal_role', {
    p_employee_id: employeeId,
  });
  if (error) { console.error('getEmployeePortalRole:', error); return null; }
  return data;
}

/**
 * Admin: promote/demote an employee's portal role to 'manager' or 'employee'.
 * Requires the employee to have activated their portal account (user_profiles row must exist).
 * Uses SECURITY DEFINER RPC so the admin can write another user's profile row.
 */
export async function setEmployeePortalRole(employeeId, role) {
  const { error } = await supabase.rpc('admin_set_employee_portal_role', {
    p_employee_id: employeeId,
    p_role:        role,
  });
  if (error) throw error;
}

/**
 * Fetch all payslips for the currently signed-in employee.
 * RLS restricts rows to employee_id = their linked employee row.
 * Returns newest period first.
 */
export async function getMyPayslips() {
  const { data, error } = await supabase
    .from('payslips')
    .select('*')
    .order('period', { ascending: false });

  if (error) { console.error('getMyPayslips:', error); return []; }

  return (data || []).map(row => ({
    id:           row.id,
    payrollRunId: row.payroll_run_id,
    employeeId:   row.employee_id,
    period:       row.period,
    paymentDate:  row.payment_date,
    grossPay:     parseFloat(row.gross_pay) || 0,
    netPay:       parseFloat(row.net_pay)   || 0,
    snapshot:     row.data_snapshot ?? {},
    issuedAt:     row.issued_at,
  }));
}
