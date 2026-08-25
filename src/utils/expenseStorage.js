/**
 * expenseStorage.js — Feature 14: Expense Claims & Reimbursements
 *
 * Admin functions:
 *   getExpenseClaims()                          — all claims for the company
 *   getApprovedUnpaidExpenses()                 — approved but not yet in a payroll run
 *   approveExpenseClaim(claimId)                — set status → 'approved'
 *   rejectExpenseClaim(claimId, reason)         — set status → 'rejected'
 *   markExpensesPaid(claimIds, payrollRunId)    — bulk-set paid + link to payroll run
 *   deleteExpenseClaim(claimId)                 — hard-delete (admin only)
 *   uploadExpenseReceipt(file, employeeId)      — upload to expense-receipts bucket
 *   getExpenseReceiptUrl(storagePath)           — signed URL (1 h)
 *
 * Employee functions (via RPC):
 *   employee_submit_expense RPC is called directly in EmpExpenses.jsx
 *   deleteEmployeeExpense(claimId) deletes the caller's pending/rejected claim
 *   Employees read their own claims via expense_claims_employee_read RLS policy.
 */
import { supabase } from '../lib/supabase';

// ── Auth helper (never use getUser() — see CLAUDE.md) ────────────────────────
async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user ?? null;
  if (!user) throw new Error('Not authenticated');
  return user;
}

// ── Shape converter ───────────────────────────────────────────────────────────
function dbToExpense(row) {
  return {
    id:                     row.id,
    userId:                 row.user_id,
    employeeId:             row.employee_id,
    category:               row.category,
    amount:                 parseFloat(row.amount) || 0,
    expenseDate:            row.expense_date,
    description:            row.description,
    receiptUrl:             row.receipt_url,
    status:                 row.status,
    rejectionReason:        row.rejection_reason,
    payrollRunId:           row.payroll_run_id,
    approvedBy:             row.approved_by,
    approvedAt:             row.approved_at,
    createdAt:              row.created_at,
    managerApprovedAt:      row.manager_approved_at ?? null,
    managerApprovedBy:      row.manager_approved_by ?? '',
    managerRejectionReason: row.manager_rejection_reason ?? '',
    // Joined employee name (when .select includes employees)
    employeeName:           row.employees?.name ?? null,
  };
}

// ── Admin functions ───────────────────────────────────────────────────────────

/**
 * Return every expense claim for the admin's company, with the employee name
 * joined in, newest first.
 */
export async function getExpenseClaims() {
  const user = await getSessionUser();
  const { data, error } = await supabase
    .from('expense_claims')
    .select('*, employees(name)')
    .eq('user_id', user.id)
    .order('created_at', { ascending: false });
  if (error) throw error;
  return (data || []).map(dbToExpense);
}

/**
 * Return approved claims that haven't been linked to a payroll run yet.
 * Used by PayrollEditor to show the informational panel and to bulk-mark paid
 * on submission.
 */
export async function getApprovedUnpaidExpenses() {
  const user = await getSessionUser();
  const { data, error } = await supabase
    .from('expense_claims')
    .select('*, employees(name)')
    .eq('user_id', user.id)
    .eq('status', 'approved')
    .is('payroll_run_id', null)
    .order('expense_date', { ascending: true });
  if (error) throw error;
  return (data || []).map(dbToExpense);
}

/**
 * Approve an expense claim. Stamps approved_by with the admin's email.
 */
export async function approveExpenseClaim(claimId) {
  const user = await getSessionUser();
  const { error } = await supabase
    .from('expense_claims')
    .update({
      status:      'approved',
      approved_by: user.email,
      approved_at: new Date().toISOString(),
      rejection_reason: '',
    })
    .eq('id', claimId)
    .eq('user_id', user.id);
  if (error) throw error;
}

/**
 * Reject an expense claim with a mandatory reason.
 */
export async function rejectExpenseClaim(claimId, reason) {
  const user = await getSessionUser();
  const { error } = await supabase
    .from('expense_claims')
    .update({
      status:           'rejected',
      rejection_reason: reason || '',
      approved_by:      '',
      approved_at:      null,
    })
    .eq('id', claimId)
    .eq('user_id', user.id);
  if (error) throw error;
}

/**
 * Bulk-mark approved expenses as paid and link them to a payroll run.
 * Called by PayrollEditor on payroll submission.
 * @param {string[]} claimIds  — array of expense_claims.id values
 * @param {string}   payrollRunId — the payroll_runs.id being finalised
 */
export async function markExpensesPaid(claimIds, payrollRunId) {
  if (!claimIds || claimIds.length === 0) return;
  const user = await getSessionUser();
  const { error } = await supabase
    .from('expense_claims')
    .update({
      status:        'paid',
      payroll_run_id: payrollRunId,
    })
    .in('id', claimIds)
    .eq('user_id', user.id);
  if (error) throw error;
}

/**
 * Hard-delete an expense claim (admin only — used for test/cleanup scenarios).
 * Does not delete the receipt file from Storage; do that separately if needed.
 */
export async function deleteExpenseClaim(claimId) {
  const user = await getSessionUser();
  const { error } = await supabase
    .from('expense_claims')
    .delete()
    .eq('id', claimId)
    .eq('user_id', user.id);
  if (error) throw error;
}

/**
 * Delete the signed-in employee's own pending or rejected expense claim.
 * The SECURITY DEFINER RPC enforces ownership and protected statuses server-side.
 */
export async function deleteEmployeeExpense(claimId) {
  const { data, error } = await supabase.rpc('employee_delete_expense', {
    p_expense_id: claimId,
  });
  if (error) throw error;
  if (data !== true) throw new Error('The expense claim could not be deleted.');
}

/**
 * Upload a receipt file to the expense-receipts Storage bucket.
 * Returns the storage path on success.
 * Bucket must exist in Supabase Dashboard (see sql/014_expense_claims.sql).
 */
export async function uploadExpenseReceipt(file, employeeId) {
  const user = await getSessionUser();
  const ts       = Date.now();
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
  const path     = `${user.id}/${employeeId}/${ts}_${safeName}`;
  const { error } = await supabase.storage
    .from('expense-receipts')
    .upload(path, file, { upsert: false });
  if (error) throw error;
  return path;
}

/**
 * Generate a 1-hour signed URL for an expense receipt.
 */
export async function getExpenseReceiptUrl(storagePath) {
  if (!storagePath) return null;
  const { data, error } = await supabase.storage
    .from('expense-receipts')
    .createSignedUrl(storagePath, 3600);
  if (error) return null;
  return data?.signedUrl ?? null;
}

// ── Manager functions (Feature 3.2: Multi-Level Expense Approvals) ────────────

/**
 * Manager: fetch all expense claims from direct reports.
 * Uses manager_get_expense_queue SECURITY DEFINER RPC (crosses RLS boundary).
 */
export async function getExpenseQueueForManager() {
  const { data, error } = await supabase.rpc('manager_get_expense_queue');
  if (error) { console.error('getExpenseQueueForManager:', error); return []; }
  return (data || []).map(dbToExpense);
}

/**
 * Manager: pre-approve a direct report's pending expense.
 * Sets status → 'manager_approved'.
 */
export async function managerApproveExpense(expenseId) {
  const { data, error } = await supabase.rpc('manager_approve_expense', { p_expense_id: expenseId });
  if (error) throw error;
  if (!data) throw new Error('Expense not found or already actioned.');
}

/**
 * Manager: reject a direct report's pending or manager_approved expense.
 * Sets status → 'manager_rejected'.
 */
export async function managerRejectExpense(expenseId, reason) {
  const { data, error } = await supabase.rpc('manager_reject_expense', {
    p_expense_id: expenseId,
    p_reason:     reason || '',
  });
  if (error) throw error;
  if (!data) throw new Error('Expense not found or already actioned.');
}
