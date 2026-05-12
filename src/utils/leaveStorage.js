/**
 * leaveStorage.js — Supabase data layer for the Leave Management module
 * Includes recalculateAllBalances() which computes leave balances from
 * approved requests + employee accrual and saves them to leave_balances.
 *
 * All functions are async and scoped to the current user via RLS.
 * Covers: leave settings, leave types, public holidays, leave requests,
 *         leave balances, and audit log.
 */

import { supabase } from '../lib/supabase';
import { DEFAULT_LEAVE_TYPES, UAE_PUBLIC_HOLIDAYS_2025, UAE_PUBLIC_HOLIDAYS_2026, calculateAnnualLeaveAccrual } from './leaveEngine';

// ── LEAVE SETTINGS ────────────────────────────────────────────────────────────

export async function getLeaveSettings() {
  const { data, error } = await supabase
    .from('leave_settings')
    .select('*')
    .limit(1)
    .maybeSingle();
  if (error) { console.error('getLeaveSettings:', error); return null; }
  if (!data) return null;
  return {
    id:                  data.id,
    leaveYearType:       data.leave_year_type,
    weekendDefinition:   data.weekend_definition,
    carryForwardEnabled: data.carry_forward_enabled,
    carryForwardMaxDays: data.carry_forward_max_days,
    approvalChain:       data.approval_chain,
    ramadanActive:       data.ramadan_active,
    ramadanStart:        data.ramadan_start,
    ramadanEnd:          data.ramadan_end,
  };
}

export async function saveLeaveSettings(settings) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:               user.id,
    leave_year_type:       settings.leaveYearType || 'calendar',
    weekend_definition:    settings.weekendDefinition || 'fri-sat',
    carry_forward_enabled: settings.carryForwardEnabled ?? true,
    carry_forward_max_days: settings.carryForwardMaxDays ?? 15,
    approval_chain:        settings.approvalChain || '1-level',
    ramadan_active:        settings.ramadanActive ?? false,
    ramadan_start:         settings.ramadanStart || null,
    ramadan_end:           settings.ramadanEnd || null,
  };
  if (settings.id) {
    const { error } = await supabase.from('leave_settings').update(row).eq('id', settings.id);
    if (error) throw error;
  } else {
    const { data, error } = await supabase.from('leave_settings')
      .upsert(row, { onConflict: 'user_id' }).select().single();
    if (error) throw error;
    return data ? { ...settings, id: data.id } : settings;
  }
}

// ── LEAVE TYPES ───────────────────────────────────────────────────────────────

export async function getLeaveTypes() {
  const { data, error } = await supabase
    .from('leave_types')
    .select('*')
    .eq('is_active', true)
    .order('sort_order', { ascending: true });
  if (error) { console.error('getLeaveTypes:', error); return []; }
  return (data || []).map(dbToLeaveType);
}

export async function seedDefaultLeaveTypes() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  // Check if already seeded
  const { data: existing } = await supabase
    .from('leave_types')
    .select('id')
    .eq('user_id', user.id)
    .limit(1);
  if (existing?.length) return; // already seeded

  const rows = DEFAULT_LEAVE_TYPES.map((lt, i) => ({
    user_id:                 user.id,
    code:                    lt.code,
    name:                    lt.name,
    color:                   lt.color,
    is_paid:                 lt.isPaid,
    is_unlimited:            lt.isUnlimited,
    requires_approval:       lt.requiresApproval,
    requires_attachment:     lt.requiresAttachment,
    requires_reason:         lt.requiresReason,
    min_notice_days:         lt.minNoticeDays,
    annual_entitlement_days: lt.annualEntitlementDays,
    accrual_type:            lt.accrualType,
    day_count_type:          lt.dayCountType,
    auto_approve:            lt.autoApprove,
    carry_forward_allowed:   lt.carryForwardAllowed,
    carry_forward_max_days:  lt.carryForwardMaxDays,
    gender_restriction:      lt.genderRestriction || null,
    min_service_months:      lt.minServiceMonths || 0,
    once_per_career:         lt.oncePerCareer || false,
    not_deducted_from_annual: lt.notDeductedFromAnnual || false,
    affects_payroll:         lt.affectsPayroll || false,
    law_reference:           lt.lawReference,
    is_active:               true,
    sort_order:              i,
  }));

  const { error } = await supabase.from('leave_types').insert(rows);
  if (error) throw error;
}

function dbToLeaveType(row) {
  return {
    id:                    row.id,
    code:                  row.code,
    name:                  row.name,
    color:                 row.color,
    isPaid:                row.is_paid,
    isUnlimited:           row.is_unlimited,
    requiresApproval:      row.requires_approval,
    requiresAttachment:    row.requires_attachment,
    requiresReason:        row.requires_reason,
    minNoticeDays:         row.min_notice_days,
    annualEntitlementDays: parseFloat(row.annual_entitlement_days) || 0,
    accrualType:           row.accrual_type,
    dayCountType:          row.day_count_type,
    autoApprove:           row.auto_approve,
    carryForwardAllowed:   row.carry_forward_allowed,
    carryForwardMaxDays:   row.carry_forward_max_days,
    genderRestriction:     row.gender_restriction,
    minServiceMonths:      row.min_service_months,
    oncePerCareer:         row.once_per_career,
    notDeductedFromAnnual: row.not_deducted_from_annual,
    affectsPayroll:        row.affects_payroll,
    lawReference:          row.law_reference,
    isActive:              row.is_active,
    sortOrder:             row.sort_order,
  };
}

// ── PUBLIC HOLIDAYS ───────────────────────────────────────────────────────────

export async function getPublicHolidays(year) {
  const query = supabase.from('public_holidays').select('*').order('date', { ascending: true });
  if (year) query.eq('year', year);
  const { data, error } = await query;
  if (error) { console.error('getPublicHolidays:', error); return []; }
  return (data || []).map(row => ({
    id:   row.id,
    date: row.date,
    name: row.name,
    type: row.type,
    year: row.year,
  }));
}

export async function seedPublicHolidays() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  // Check if already seeded for 2025
  const { data: existing } = await supabase
    .from('public_holidays')
    .select('id')
    .eq('user_id', user.id)
    .eq('year', 2025)
    .limit(1);
  if (existing?.length) return;

  const allHolidays = [
    ...UAE_PUBLIC_HOLIDAYS_2025.map(h => ({ ...h, year: 2025 })),
    ...UAE_PUBLIC_HOLIDAYS_2026.map(h => ({ ...h, year: 2026 })),
  ];

  const rows = allHolidays.map(h => ({
    user_id: user.id,
    date:    h.date,
    name:    h.name,
    type:    h.type,
    year:    h.year,
  }));

  const { error } = await supabase.from('public_holidays').insert(rows);
  if (error) throw error;
}

export async function savePublicHoliday(holiday) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id: user.id,
    date:    holiday.date,
    name:    holiday.name,
    type:    holiday.type || 'company',
    year:    new Date(holiday.date).getFullYear(),
  };
  if (holiday.id) {
    const { error } = await supabase.from('public_holidays').update(row).eq('id', holiday.id);
    if (error) throw error;
  } else {
    const { data, error } = await supabase.from('public_holidays').insert(row).select().single();
    if (error) throw error;
    return { ...holiday, id: data.id };
  }
}

export async function deletePublicHoliday(id) {
  const { error } = await supabase.from('public_holidays').delete().eq('id', id);
  if (error) throw error;
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
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:          user.id,
    employee_id:      request.employeeId,
    leave_type_id:    request.leaveTypeId,
    leave_type_code:  request.leaveTypeCode,
    start_date:       request.startDate,
    end_date:         request.endDate,
    is_half_day:      request.isHalfDay || false,
    half_day_period:  request.halfDayPeriod || null,
    days_requested:   request.daysRequested || 0,
    status:           'Pending',
    reason:           request.reason || '',
    attachment_url:   request.attachmentUrl || '',
    relationship:     request.relationship || '',
    deceased_name:    request.deceasedName || '',
    date_of_death:    request.dateOfDeath || null,
    child_birth_date: request.childBirthDate || null,
    child_name:       request.childName || '',
    expected_due_date: request.expectedDueDate || null,
    institution_name: request.institutionName || '',
    exam_dates:       request.examDates || '',
    submitted_at:     new Date().toISOString(),
  };

  const { data, error } = await supabase.from('leave_requests').insert(row).select().single();
  if (error) throw error;

  // Log to audit trail
  await addLeaveAuditLog(data.id, request.employeeId, 'Submitted', user.email || user.id, '', 'Pending');

  return dbToLeaveRequest(data);
}

export async function updateLeaveRequestStatus(requestId, status, actorEmail, reason = '') {
  const { data: { user } } = await supabase.auth.getUser();
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
  const { data: { user } } = await supabase.auth.getUser();
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
    id:              row.id,
    employeeId:      row.employee_id,
    leaveTypeId:     row.leave_type_id,
    leaveTypeCode:   row.leave_type_code,
    startDate:       row.start_date,
    endDate:         row.end_date,
    isHalfDay:       row.is_half_day,
    halfDayPeriod:   row.half_day_period,
    daysRequested:   parseFloat(row.days_requested) || 0,
    status:          row.status,
    reason:          row.reason,
    attachmentUrl:   row.attachment_url,
    rejectionReason: row.rejection_reason,
    approvedBy:      row.approved_by,
    approvedAt:      row.approved_at,
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
  };
}

// ── LEAVE BALANCES ────────────────────────────────────────────────────────────

export async function getLeaveBalances(employeeId, year) {
  const currentYear = year || new Date().getFullYear();
  const { data, error } = await supabase
    .from('leave_balances')
    .select('*')
    .eq('employee_id', employeeId)
    .eq('leave_year', currentYear);
  if (error) { console.error('getLeaveBalances:', error); return []; }
  return (data || []).map(dbToLeaveBalance);
}

export async function getAllLeaveBalances(year) {
  const currentYear = year || new Date().getFullYear();
  const { data, error } = await supabase
    .from('leave_balances')
    .select('*')
    .eq('leave_year', currentYear)
    .order('employee_id');
  if (error) { console.error('getAllLeaveBalances:', error); return []; }
  return (data || []).map(dbToLeaveBalance);
}

export async function upsertLeaveBalance(balance) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:            user.id,
    employee_id:        balance.employeeId,
    leave_type_id:      balance.leaveTypeId,
    leave_type_code:    balance.leaveTypeCode,
    leave_year:         balance.leaveYear,
    entitled_days:      balance.entitledDays || 0,
    accrued_days:       balance.accruedDays || 0,
    used_days:          balance.usedDays || 0,
    pending_days:       balance.pendingDays || 0,
    carried_forward:    balance.carriedForward || 0,
    remaining_days:     balance.remainingDays || 0,
    sick_full_pay_used: balance.sickFullPayUsed || 0,
    sick_half_pay_used: balance.sickHalfPayUsed || 0,
    sick_unpaid_used:   balance.sickUnpaidUsed || 0,
    hajj_taken:         balance.hajjTaken || false,
  };

  const { error } = await supabase
    .from('leave_balances')
    .upsert(row, { onConflict: 'user_id,employee_id,leave_type_code,leave_year' });
  if (error) throw error;
}

function dbToLeaveBalance(row) {
  return {
    id:              row.id,
    employeeId:      row.employee_id,
    leaveTypeId:     row.leave_type_id,
    leaveTypeCode:   row.leave_type_code,
    leaveYear:       row.leave_year,
    entitledDays:    parseFloat(row.entitled_days) || 0,
    accruedDays:     parseFloat(row.accrued_days) || 0,
    usedDays:        parseFloat(row.used_days) || 0,
    pendingDays:     parseFloat(row.pending_days) || 0,
    carriedForward:  parseFloat(row.carried_forward) || 0,
    remaining:       parseFloat(row.remaining_days) || 0,
    sickFullPayUsed: parseFloat(row.sick_full_pay_used) || 0,
    sickHalfPayUsed: parseFloat(row.sick_half_pay_used) || 0,
    sickUnpaidUsed:  parseFloat(row.sick_unpaid_used) || 0,
    hajjTaken:       row.hajj_taken || false,
    updatedAt:       row.updated_at,
  };
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
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');

  const currentYear = year || new Date().getFullYear();

  const rows = [];

  for (const emp of employees) {
    if (!emp.id) continue;

    for (const lt of leaveTypes) {
      if (!lt.id) continue;

      // Filter requests for this employee + type + year
      const empRequests = allRequests.filter(r =>
        r.employeeId === emp.id &&
        r.leaveTypeCode === lt.code &&
        r.startDate?.startsWith(String(currentYear))
      );

      const usedDays    = empRequests.filter(r => r.status === 'Approved').reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);
      const pendingDays = empRequests.filter(r => r.status === 'Pending').reduce((s, r) => s + (parseFloat(r.daysRequested) || 0), 0);

      // Sick leave tier tracking
      const sickFullPayUsed  = empRequests.filter(r => r.status === 'Approved').reduce((s, r) => {
        const days = parseFloat(r.daysRequested) || 0;
        const prev = s;
        if (prev < 15) return Math.min(prev + days, 15);
        return prev;
      }, 0);
      const sickHalfPayUsed  = Math.max(0, Math.min(usedDays - 15, 30));
      const sickUnpaidUsed   = Math.max(0, usedDays - 45);

      // Hajj: check if ever taken
      const hajjTaken = lt.code === 'HAJJ' && allRequests.some(r =>
        r.employeeId === emp.id && r.leaveTypeCode === 'HAJJ' && r.status === 'Approved'
      );

      // Accrued days
      let accruedDays    = lt.annualEntitlementDays;
      let entitledDays   = lt.annualEntitlementDays;

      if (lt.code === 'ANNUAL' && (emp.startDate || emp.employmentStartDate)) {
        const accrual = calculateAnnualLeaveAccrual(
          emp.startDate || emp.employmentStartDate,
          new Date(),
          leaveYearType
        );
        accruedDays  = accrual.totalAccrued;
        entitledDays = accrual.entitlementPerYear;
      }

      const remainingDays = Math.max(0, accruedDays - usedDays);

      rows.push({
        user_id:            user.id,
        employee_id:        emp.id,
        leave_type_id:      lt.id,
        leave_type_code:    lt.code,
        leave_year:         currentYear,
        entitled_days:      entitledDays,
        accrued_days:       accruedDays,
        used_days:          usedDays,
        pending_days:       pendingDays,
        carried_forward:    0,
        remaining_days:     remainingDays,
        sick_full_pay_used: lt.code === 'SICK' ? sickFullPayUsed : 0,
        sick_half_pay_used: lt.code === 'SICK' ? sickHalfPayUsed : 0,
        sick_unpaid_used:   lt.code === 'SICK' ? sickUnpaidUsed : 0,
        hajj_taken:         hajjTaken,
      });
    }
  }

  if (rows.length === 0) return;

  // Upsert all balances in one call
  const { error } = await supabase
    .from('leave_balances')
    .upsert(rows, { onConflict: 'user_id,employee_id,leave_type_code,leave_year' });
  if (error) throw error;
}
