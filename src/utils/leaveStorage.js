/**
 * leaveStorage.js — Supabase data layer for the Leave Management module
 * All functions are async and scoped to the current user via RLS.
 * Covers: leave settings, leave types, public holidays, leave requests,
 *         approval workflows, and audit log. Balance reads and writes have
 *         moved to the migration application.
 */

import { supabase } from '../lib/supabase';

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

export async function uploadLeaveAttachment() {
  throw new Error('Leave attachments have moved to the migration leave screen.');
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
  void request;
  throw new Error('Leave request submission has moved to the migration leave screen.');
}

export async function updateLeaveRequestStatus(requestId, status, actorEmail, reason = '') {
  void requestId;
  void status;
  void actorEmail;
  void reason;
  throw new Error('Leave decisions have moved to the migration approval queue.');
}

export async function cancelLeaveRequest(requestId, actorEmail) {
  void requestId;
  void actorEmail;
  throw new Error('Leave request cancellation has moved to the migration leave screen.');
}

export async function getLeaveAuditLog(leaveRequestId) {
  void leaveRequestId;
  throw new Error('Leave audit reads have moved to the migration approval queue.');
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
  void managerEmployeeId;
  throw new Error('Manager leave queues have moved to the migration approval queue.');
}

/**
 * Manager approves a direct report's leave request.
 * If approval_level_required = 1, the request moves straight to 'Approved'.
 * If 2-level, it moves to 'ManagerApproved' and waits for HR.
 */
export async function approveLeaveAsManager(requestId) {
  void requestId;
  throw new Error('Manager leave decisions have moved to the migration approval queue.');
}

/**
 * Manager rejects a direct report's leave request.
 */
export async function rejectLeaveAsManager(requestId, reason = '') {
  void requestId;
  void reason;
  throw new Error('Manager leave decisions have moved to the migration approval queue.');
}

// ── LEAVE APPROVAL DELEGATES (Feature 6) ──────────────────────────────────────

export async function getLeaveApprovalDelegates() {
  throw new Error('Leave delegations have moved to the migration approval queue.');
}

export async function saveLeaveApprovalDelegate(delegate) {
  void delegate;
  throw new Error('Leave delegations have moved to the migration approval queue.');
}

export async function deleteLeaveApprovalDelegate(id) {
  void id;
  throw new Error('Leave delegations have moved to the migration approval queue.');
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
