/**
 * leaveStorage.js — Supabase data layer for the Leave Management module
 * All functions are async and scoped to the current user via RLS.
 * Covers: leave settings, leave types, public holidays, leave requests,
 *         approval workflows, and audit log. Balance reads and writes have
 *         moved to the migration application.
 */

import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ── LEAVE SETTINGS ────────────────────────────────────────────────────────────

export async function getLeaveSettings() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function saveLeaveSettings() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

// ── LEAVE TYPES ───────────────────────────────────────────────────────────────

export async function getLeaveTypes() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function seedDefaultLeaveTypes() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function saveLeaveType() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function deleteLeaveType() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

/**
 * Upload a leave supporting document to the employee-documents bucket under the
 * leave/ sub-path. Returns a 7-day signed URL (long enough for HR review).
 * Reuses existing Storage RLS policies — no new bucket needed.
 */
export async function uploadLeaveAttachment(adminUserId, employeeId, file) {
  const safeName    = file.name.replace(/[^a-z0-9._-]/gi, '_');
  const storagePath = `${adminUserId}/${employeeId}/leave/${Date.now()}_${safeName}`;
  const { error: uploadErr } = await supabase.storage
    .from('employee-documents')
    .upload(storagePath, file, { cacheControl: '3600', upsert: false });
  if (uploadErr) throw uploadErr;
  const { data: signed } = await supabase.storage
    .from('employee-documents')
    .createSignedUrl(storagePath, 604800); // 7 days
  return signed?.signedUrl ?? '';
}

// ── PUBLIC HOLIDAYS ───────────────────────────────────────────────────────────

export async function getPublicHolidays() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function seedPublicHolidays() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

/**
 * Seeds UAE public holidays for a specific year if not already present.
 * Returns true if any rows were inserted.
 */
export async function seedPublicHolidaysForYear() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function savePublicHoliday() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

export async function deletePublicHoliday() {
  throw new Error('Leave configuration has moved to the migration settings screen.');
}

// ── LEAVE REQUESTS ────────────────────────────────────────────────────────────

export async function getLeaveRequests(filters = {}) {
  let query = supabase
    .from('leave_requests')
    .select('*')
    .order('submitted_at', { ascending: false });

  if (filters.employeeId) query = query.eq('employee_id', filters.employeeId);
  if (filters.status)     query = query.eq('status', filters.status);
  if (filters.leaveTypeCode) query = query.eq('leave_type_code', filters.leaveTypeCode);
  if (filters.year) {
    query = query
      .gte('start_date', `${filters.year}-01-01`)
      .lte('start_date', `${filters.year}-12-31`);
  }

  const { data, error } = await query;
  if (error) { console.error('getLeaveRequests:', error); return []; }
  return (data || []).map(dbToLeaveRequest);
}

export async function submitLeaveRequest(request) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:                 user.id,
    employee_id:             request.employeeId,
    leave_type_id:           request.leaveTypeId,
    leave_type_code:         request.leaveTypeCode,
    start_date:              request.startDate,
    end_date:                request.endDate,
    is_half_day:             request.isHalfDay || false,
    half_day_period:         request.halfDayPeriod || null,
    days_requested:          request.daysRequested || 0,
    status:                  'Pending',
    reason:                  request.reason || '',
    attachment_url:          request.attachmentUrl || '',
    relationship:            request.relationship || '',
    deceased_name:           request.deceasedName || '',
    date_of_death:           request.dateOfDeath || null,
    child_birth_date:        request.childBirthDate || null,
    child_name:              request.childName || '',
    expected_due_date:       request.expectedDueDate || null,
    institution_name:        request.institutionName || '',
    exam_dates:              request.examDates || '',
    approval_level_required: request.approvalLevelRequired || 1,
    substitute_employee_id:  request.substituteEmployeeId || null,
    approval_comment:        request.approvalComment || '',
    submitted_at:            new Date().toISOString(),
  };

  const { data, error } = await supabase.from('leave_requests').insert(row).select().single();
  if (error) throw error;

  // Log to audit trail
  await addLeaveAuditLog(data.id, request.employeeId, 'Submitted', user.email || user.id, '', 'Pending');

  return dbToLeaveRequest(data);
}

export async function updateLeaveRequestStatus(requestId, status, actorEmail, reason = '') {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  // Get current status for audit log
  const { data: current } = await supabase
    .from('leave_requests')
    .select('status, employee_id')
    .eq('id', requestId)
    .single();

  const updateData = {
    status,
    rejection_reason: reason,
    approved_by:      status === 'Approved' ? actorEmail : '',
    approved_at:      status === 'Approved' ? new Date().toISOString() : null,
  };

  const { data, error } = await supabase
    .from('leave_requests')
    .update(updateData)
    .eq('id', requestId)
    .select()
    .single();
  if (error) throw error;

  // Immutable audit log entry
  await addLeaveAuditLog(requestId, current.employee_id, status, actorEmail, reason, current.status);

  return dbToLeaveRequest(data);
}

export async function cancelLeaveRequest(requestId, actorEmail) {
  return updateLeaveRequestStatus(requestId, 'Cancelled', actorEmail, 'Cancelled by employee');
}

async function addLeaveAuditLog(leaveRequestId, employeeId, action, actor, reason, oldStatus) {
  const user = await getSessionUser();
  if (!user) return;
  await supabase.from('leave_audit_log').insert({
    user_id:          user.id,
    leave_request_id: leaveRequestId,
    employee_id:      employeeId,
    action,
    actor,
    reason:           reason || '',
    old_status:       oldStatus || '',
    new_status:       action,
  });
}

export async function getLeaveAuditLog(leaveRequestId) {
  const { data, error } = await supabase
    .from('leave_audit_log')
    .select('*')
    .eq('leave_request_id', leaveRequestId)
    .order('created_at', { ascending: true });
  if (error) { console.error('getLeaveAuditLog:', error); return []; }
  return (data || []).map(row => ({
    id:             row.id,
    leaveRequestId: row.leave_request_id,
    employeeId:     row.employee_id,
    action:         row.action,
    actor:          row.actor,
    reason:         row.reason,
    oldStatus:      row.old_status,
    newStatus:      row.new_status,
    createdAt:      row.created_at,
  }));
}

function dbToLeaveRequest(row) {
  return {
    id:                     row.id,
    employeeId:             row.employee_id,
    leaveTypeId:            row.leave_type_id,
    leaveTypeCode:          row.leave_type_code,
    startDate:              row.start_date,
    endDate:                row.end_date,
    isHalfDay:              row.is_half_day,
    halfDayPeriod:          row.half_day_period,
    daysRequested:          parseFloat(row.days_requested) || 0,
    status:                 row.status,
    reason:                 row.reason,
    attachmentUrl:          row.attachment_url,
    rejectionReason:        row.rejection_reason,
    approvedBy:             row.approved_by,
    approvedAt:             row.approved_at,
    // Feature 6: multi-level approval fields
    managerApprovedAt:      row.manager_approved_at ?? null,
    managerApprovedBy:      row.manager_approved_by ?? '',
    managerRejectionReason: row.manager_rejection_reason ?? '',
    substituteEmployeeId:   row.substitute_employee_id ?? null,
    approvalLevelRequired:  row.approval_level_required ?? 1,
    approvalComment:        row.approval_comment ?? '',
    // leave-specific detail fields
    relationship:    row.relationship,
    deceasedName:    row.deceased_name,
    dateOfDeath:     row.date_of_death,
    childBirthDate:  row.child_birth_date,
    childName:       row.child_name,
    expectedDueDate: row.expected_due_date,
    institutionName: row.institution_name,
    examDates:       row.exam_dates,
    submittedAt:     row.submitted_at,
    createdAt:       row.created_at,
    warnings:        Array.isArray(row.warnings) ? row.warnings : (row.warnings ?? []),
  };
}

// ── MANAGER LEAVE QUEUE (Feature 6) ──────────────────────────────────────────

/**
 * Returns all Pending leave requests from employees who report directly
 * to the given manager (by reporting_manager_id).
 */
export async function getLeaveQueueForManager(managerEmployeeId) {
  if (!managerEmployeeId) return [];

  // Get direct reports with probation status
  const { data: reports, error: rErr } = await supabase
    .from('employees')
    .select('id, employment_status, probation_end_date')
    .eq('reporting_manager_id', managerEmployeeId);

  if (rErr) { console.error('getLeaveQueueForManager (reports):', rErr); return []; }
  if (!reports?.length) return [];

  const ids = reports.map(r => r.id);
  const empMap = Object.fromEntries(reports.map(r => [r.id, r]));

  const [reqResult, balResult] = await Promise.all([
    supabase
      .from('leave_requests')
      .select('*')
      .in('employee_id', ids)
      .in('status', ['Pending', 'ManagerApproved', 'ManagerRejected'])
      .order('submitted_at', { ascending: false }),
    supabase
      .from('leave_balances')
      .select('*')
      .in('employee_id', ids)
      .eq('leave_year', new Date().getFullYear()),
  ]);

  if (reqResult.error) { console.error('getLeaveQueueForManager:', reqResult.error); return []; }

  const balByEmp = {};
  for (const b of (balResult.data || [])) {
    if (!balByEmp[b.employee_id]) balByEmp[b.employee_id] = [];
    balByEmp[b.employee_id].push(b);
  }

  return (reqResult.data || []).map(row => {
    const req = dbToLeaveRequest(row);
    const warnings = [...(req.warnings || [])];
    const emp = empMap[req.employeeId];

    // Probation warning
    if (emp?.employment_status === 'Probation') {
      warnings.push('Employee is on probation');
    }

    // Low balance warning
    const empBals = balByEmp[req.employeeId] || [];
    const matchBal = empBals.find(b => b.leave_type_code === req.leaveTypeCode);
    if (matchBal) {
      const remaining = (matchBal.entitled || 0) - (matchBal.used || 0);
      if (remaining < req.daysRequested) {
        warnings.push(`Insufficient balance: ${remaining}d remaining, ${req.daysRequested}d requested`);
      } else if (remaining - req.daysRequested <= 2) {
        warnings.push(`Low balance after approval: ${remaining - req.daysRequested}d will remain`);
      }
    }

    req.warnings = warnings;
    return req;
  });
}

/**
 * Manager approves a direct report's leave request.
 * If approval_level_required = 1, the request moves straight to 'Approved'.
 * If 2-level, it moves to 'ManagerApproved' and waits for HR.
 */
export async function approveLeaveAsManager(requestId) {
  const { error } = await supabase.rpc('manager_approve_leave', { p_request_id: requestId });
  if (error) throw error;
}

/**
 * Manager rejects a direct report's leave request.
 */
export async function rejectLeaveAsManager(requestId, reason = '') {
  const { error } = await supabase.rpc('manager_reject_leave', {
    p_request_id: requestId,
    p_reason:     reason,
  });
  if (error) throw error;
}

// ── LEAVE APPROVAL DELEGATES (Feature 6) ──────────────────────────────────────

export async function getLeaveApprovalDelegates() {
  const { data, error } = await supabase
    .from('leave_approval_delegates')
    .select('*')
    .order('from_date', { ascending: false });
  if (error) { console.error('getLeaveApprovalDelegates:', error); return []; }
  return (data || []).map(row => ({
    id:                  row.id,
    approverEmployeeId:  row.approver_employee_id,
    delegateEmployeeId:  row.delegate_employee_id,
    fromDate:            row.from_date,
    toDate:              row.to_date,
    createdAt:           row.created_at,
  }));
}

export async function saveLeaveApprovalDelegate(delegate) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:              user.id,
    approver_employee_id: delegate.approverEmployeeId,
    delegate_employee_id: delegate.delegateEmployeeId,
    from_date:            delegate.fromDate,
    to_date:              delegate.toDate,
  };
  if (delegate.id) {
    const { error } = await supabase.from('leave_approval_delegates').update(row).eq('id', delegate.id);
    if (error) throw error;
    return delegate;
  } else {
    const { data, error } = await supabase
      .from('leave_approval_delegates').insert(row).select().single();
    if (error) throw error;
    return { ...delegate, id: data.id, createdAt: data.created_at };
  }
}

export async function deleteLeaveApprovalDelegate(id) {
  const { error } = await supabase.from('leave_approval_delegates').delete().eq('id', id);
  if (error) throw error;
}

// ── LEAVE BALANCES ────────────────────────────────────────────────────────────

export async function getLeaveBalances(employeeId, year) {
  void employeeId;
  void year;
  throw new Error('Leave balance reads have moved to the migration leave view.');
}

export async function getAllLeaveBalances(year) {
  void year;
  throw new Error('Leave balance reads have moved to the migration leave view.');
}

export async function upsertLeaveBalance(balance) {
  void balance;
  throw new Error('Leave balance writes have moved to the migration leave view.');
}

// ── INITIALISE LEAVE MODULE ───────────────────────────────────────────────────

/**
 * Called on first load of the Leave module.
 * Seeds default leave types and public holidays if not already present.
 */
export async function initialiseLeaveModule() {
  try {
    await seedDefaultLeaveTypes();
    await seedPublicHolidays();
  } catch (err) {
    console.error('initialiseLeaveModule:', err);
  }
}

// ── RECALCULATE BALANCES ──────────────────────────────────────────────────────

/**
 * Recalculate and save leave balances for all employees.
 * Called when the Balances tab is opened or when a leave request is approved.
 *
 * For each employee × leave type:
 *   - entitled_days = annual entitlement (from leave type config)
 *   - accrued_days  = calculated from employment start date (annual leave only)
 *   - used_days     = sum of approved leave days for this type in the current year
 *   - pending_days  = sum of pending leave days
 *   - remaining     = accrued_days - used_days (or entitled - used for fixed types)
 *
 * @param {object[]} employees
 * @param {object[]} leaveTypes
 * @param {object[]} allRequests — all leave requests (any status)
 * @param {number} year — leave year (default: current year)
 * @param {string} leaveYearType — 'calendar' | 'anniversary'
 */
export async function recalculateAllBalances(employees, leaveTypes, allRequests, year, leaveYearType = 'calendar') {
  void employees;
  void leaveTypes;
  void allRequests;
  void year;
  void leaveYearType;
  throw new Error('Leave balance recalculation has moved to the migration leave view.');
}

// ── CALENDAR DATA ─────────────────────────────────────────────────────────────

/**
 * Returns all approved leave requests that overlap a given calendar month.
 * Useful for calendar views that lazy-load data when navigating months,
 * or for components that don't already have the full requests list in memory.
 *
 * @param {number} year
 * @param {number} month — 1-indexed (1 = January, 12 = December)
 * @returns {Promise<object[]>} — array of leave request objects (camelCase)
 */
export async function getApprovedLeavesForMonth(year, month) {
  const monthStart = `${year}-${String(month).padStart(2, '0')}-01`;
  const lastDay    = new Date(year, month, 0).getDate();
  const monthEnd   = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;

  const { data, error } = await supabase
    .from('leave_requests')
    .select('*')
    .eq('status', 'Approved')
    .lte('start_date', monthEnd)   // leave starts on or before last day of month
    .gte('end_date',   monthStart) // leave ends on or after first day of month
    .order('start_date', { ascending: true });

  if (error) { console.error('getApprovedLeavesForMonth:', error); return []; }
  return (data || []).map(dbToLeaveRequest);
}
