/**
 * attendanceStorage.js — Supabase data layer for the Attendance module
 *
 * Covers: attendance settings, shifts, shift assignments, clock events,
 *         attendance records, period close, regularisation requests, audit log.
 *
 * Integration points:
 *   - Reads leave requests from Leave Management (leaveStorage.js)
 *   - Reads public holidays from Leave Management (leaveStorage.js)
 *   - Reads Ramadan period from Leave Management settings
 *   - Reads employee data from Employee Records (storage.js)
 */

import { supabase } from '../lib/supabase';
import {
  deriveAttendanceStatus,
  isWeekendDay,
  isPublicHolidayDay,
  isRamadanDay,
  ATTENDANCE_STATUS,
} from './attendanceEngine';

// ── ATTENDANCE SETTINGS ───────────────────────────────────────────────────────

export async function getAttendanceSettings() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data, error } = await supabase
    .from('attendance_settings')
    .select('*')
    .eq('user_id', user.id)
    .limit(1)
    .maybeSingle();
  if (error) { console.error('getAttendanceSettings:', error); return null; }
  if (!data) return null;
  return dbToAttendanceSettings(data);
}

export async function saveAttendanceSettings(settings) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:                    user.id,
    working_days:               settings.workingDays || ['Mon','Tue','Wed','Thu'],
    weekend_days:               settings.weekendDays || ['Fri','Sat'],
    default_hours_per_day:      settings.defaultHoursPerDay ?? 8,
    late_grace_minutes:         settings.lateGraceMinutes ?? 10,
    early_departure_grace_minutes: settings.earlyDepartureGraceMinutes ?? 10,
    overtime_requires_approval: settings.overtimeRequiresApproval ?? true,
    max_daily_overtime_hours:   settings.maxDailyOvertimeHours ?? 2,
    late_deduction_policy:      settings.lateDeductionPolicy || 'none',
    late_deduction_amount:      settings.lateDeductionAmount ?? 0,
    wfh_enabled:                settings.wfhEnabled ?? false,
    regularisation_max_days_per_month: settings.regularisationMaxDaysPerMonth ?? 2,
    regularisation_window_days: settings.regularisationWindowDays ?? 7,
    biometric_api_enabled:      settings.biometricApiEnabled ?? false,
    biometric_api_key:          settings.biometricApiKey || '',
  };
  if (settings.id) {
    const { error } = await supabase.from('attendance_settings').update(row).eq('id', settings.id);
    if (error) throw error;
  } else {
    const { data, error } = await supabase.from('attendance_settings')
      .upsert(row, { onConflict: 'user_id' }).select().single();
    if (error) throw error;
    return data ? { ...dbToAttendanceSettings(data) } : settings;
  }
}

function dbToAttendanceSettings(row) {
  return {
    id:                          row.id,
    workingDays:                 row.working_days || ['Mon','Tue','Wed','Thu'],
    weekendDays:                 row.weekend_days || ['Fri','Sat'],
    defaultHoursPerDay:          parseFloat(row.default_hours_per_day) || 8,
    lateGraceMinutes:            row.late_grace_minutes ?? 10,
    earlyDepartureGraceMinutes:  row.early_departure_grace_minutes ?? 10,
    overtimeRequiresApproval:    row.overtime_requires_approval ?? true,
    maxDailyOvertimeHours:       parseFloat(row.max_daily_overtime_hours) || 2,
    lateDeductionPolicy:         row.late_deduction_policy || 'none',
    lateDeductionAmount:         parseFloat(row.late_deduction_amount) || 0,
    wfhEnabled:                  row.wfh_enabled ?? false,
    regularisationMaxDaysPerMonth: row.regularisation_max_days_per_month ?? 2,
    regularisationWindowDays:    row.regularisation_window_days ?? 7,
    biometricApiEnabled:         row.biometric_api_enabled ?? false,
    biometricApiKey:             row.biometric_api_key || '',
  };
}

// ── SHIFTS ────────────────────────────────────────────────────────────────────

export async function getShifts() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('shifts')
    .select('*')
    .eq('user_id', user.id)
    .eq('is_active', true)
    .order('name');
  if (error) { console.error('getShifts:', error); return []; }
  return (data || []).map(dbToShift);
}

export async function saveShift(shift) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:          user.id,
    name:             shift.name,
    shift_type:       shift.shiftType || 'fixed',
    start_time:       shift.startTime || null,
    end_time:         shift.endTime || null,
    break_minutes:    shift.breakMinutes ?? 60,
    expected_hours:   shift.expectedHours ?? 8,
    late_grace_minutes: shift.lateGraceMinutes ?? 10,
    early_departure_grace_minutes: shift.earlyDepartureGraceMinutes ?? 10,
    split_start_time: shift.splitStartTime || null,
    split_end_time:   shift.splitEndTime || null,
    is_overnight:     shift.isOvernight ?? false,
    min_hours_flexible: shift.minHoursFlexible || null,
    is_active:        shift.isActive ?? true,
  };
  if (shift.id) {
    const { data, error } = await supabase.from('shifts').update(row).eq('id', shift.id).select().single();
    if (error) throw error;
    return dbToShift(data);
  } else {
    const { data, error } = await supabase.from('shifts').insert(row).select().single();
    if (error) throw error;
    return dbToShift(data);
  }
}

export async function deleteShift(id) {
  const { error } = await supabase.from('shifts').update({ is_active: false }).eq('id', id);
  if (error) throw error;
}

function dbToShift(row) {
  return {
    id:                row.id,
    name:              row.name,
    shiftType:         row.shift_type,
    startTime:         row.start_time,
    endTime:           row.end_time,
    breakMinutes:      row.break_minutes,
    expectedHours:     parseFloat(row.expected_hours) || 8,
    lateGraceMinutes:  row.late_grace_minutes,
    earlyDepartureGraceMinutes: row.early_departure_grace_minutes,
    splitStartTime:    row.split_start_time,
    splitEndTime:      row.split_end_time,
    isOvernight:       row.is_overnight,
    minHoursFlexible:  row.min_hours_flexible,
    isActive:          row.is_active,
  };
}

// ── SHIFT ASSIGNMENTS ─────────────────────────────────────────────────────────

export async function getShiftForEmployee(employeeId, date) {
  const { data, error } = await supabase
    .from('shift_assignments')
    .select('*, shifts(*)')
    .eq('employee_id', employeeId)
    .lte('effective_from', date)
    .or(`effective_to.is.null,effective_to.gte.${date}`)
    .order('effective_from', { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error || !data) return null;
  return dbToShift(data.shifts);
}

export async function assignShift(employeeId, shiftId, effectiveFrom, effectiveTo = null) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { error } = await supabase.from('shift_assignments').insert({
    user_id:        user.id,
    employee_id:    employeeId,
    shift_id:       shiftId,
    effective_from: effectiveFrom,
    effective_to:   effectiveTo,
  });
  if (error) throw error;
}

// ── CLOCK EVENTS ──────────────────────────────────────────────────────────────

export async function getClockEvents(employeeId, date) {
  const dateStart = `${date}T00:00:00+04:00`;
  const dateEnd   = `${date}T23:59:59+04:00`;
  const { data, error } = await supabase
    .from('clock_events')
    .select('*')
    .eq('employee_id', employeeId)
    .gte('event_time', dateStart)
    .lte('event_time', dateEnd)
    .eq('is_superseded', false)
    .order('event_time', { ascending: true });
  if (error) { console.error('getClockEvents:', error); return []; }
  return (data || []).map(dbToClockEvent);
}

export async function recordClockEvent({ employeeId, eventType, method = 'WEB', notes = '', enteredBy = null, ipAddress = null }) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase.from('clock_events').insert({
    user_id:     user.id,
    employee_id: employeeId,
    event_type:  eventType,
    event_time:  new Date().toISOString(),
    method,
    ip_address:  ipAddress,
    entered_by:  enteredBy || user.id,
    notes,
  }).select().single();
  if (error) throw error;
  return dbToClockEvent(data);
}

export async function recordManualClockEvent({ employeeId, eventType, eventTime, notes, enteredBy }) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase.from('clock_events').insert({
    user_id:     user.id,
    employee_id: employeeId,
    event_type:  eventType,
    event_time:  eventTime,
    method:      'MANUAL',
    entered_by:  enteredBy || user.id,
    notes:       notes || '',
  }).select().single();
  if (error) throw error;
  return dbToClockEvent(data);
}

function dbToClockEvent(row) {
  return {
    id:          row.id,
    employeeId:  row.employee_id,
    eventType:   row.event_type,
    eventTime:   row.event_time,
    method:      row.method,
    ipAddress:   row.ip_address,
    enteredBy:   row.entered_by,
    notes:       row.notes,
    isSuperseded: row.is_superseded,
    createdAt:   row.created_at,
  };
}

// ── ATTENDANCE RECORDS ────────────────────────────────────────────────────────

export async function getAttendanceRecords(filters = {}) {
  let query = supabase.from('attendance_records').select('*').order('date', { ascending: false });

  // When filtering by employeeId (employee self-service path) we rely solely on
  // the employee SELECT RLS policy. When there is no employeeId filter (admin
  // path) we also add an explicit user_id constraint as defense-in-depth.
  if (filters.employeeId) {
    query = query.eq('employee_id', filters.employeeId);
  } else {
    const { data: authData } = await supabase.auth.getUser();
    if (authData?.user) query = query.eq('user_id', authData.user.id);
  }

  if (filters.dateFrom)   query = query.gte('date', filters.dateFrom);
  if (filters.dateTo)     query = query.lte('date', filters.dateTo);
  if (filters.status)     query = query.eq('status', filters.status);
  if (filters.period) {
    const [y, m] = filters.period.split('-').map(Number);
    query = query.gte('date', `${y}-${String(m).padStart(2,'0')}-01`)
                 .lte('date', `${y}-${String(m).padStart(2,'0')}-${new Date(y, m, 0).getDate()}`);
  }
  const { data, error } = await query;
  if (error) { console.error('getAttendanceRecords:', error); return []; }
  return (data || []).map(dbToAttendanceRecord);
}

export async function upsertAttendanceRecord(record) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:                user.id,
    employee_id:            record.employeeId,
    date:                   record.date,
    shift_id:               record.shiftId || null,
    clock_in_time:          record.clockInTime || null,
    clock_out_time:         record.clockOutTime || null,
    total_hours:            record.totalHours ?? 0,
    status:                 record.status || ATTENDANCE_STATUS.ABSENT,
    late_minutes:           record.lateMinutes ?? 0,
    early_departure_minutes: record.earlyDepartureMinutes ?? 0,
    overtime_hours:         record.overtimeHours ?? 0,
    overtime_type:          record.overtimeType || null,
    overtime_amount:        record.overtimeAmount ?? 0,
    overtime_approved_by:   record.overtimeApprovedBy || '',
    overtime_approved:      record.overtimeApproved ?? false,
    worked_on_rest_day:     record.workedOnRestDay ?? false,
    rest_day_substitute:    record.restDaySubstitute ?? false,
    missing_clock_out:      record.missingClockOut ?? false,
    is_ramadan_day:         record.isRamadanDay ?? false,
    absence_deduction:      record.absenceDeduction ?? 0,
    late_deduction:         record.lateDeduction ?? 0,
    period_closed:          record.periodClosed ?? false,
    resolved_by:            record.resolvedBy || '',
    resolution_type:        record.resolutionType || '',
    resolution_notes:       record.resolutionNotes || '',
  };
  const { data, error } = await supabase
    .from('attendance_records')
    .upsert(row, { onConflict: 'user_id,employee_id,date' })
    .select()
    .single();
  if (error) throw error;
  return dbToAttendanceRecord(data);
}

function dbToAttendanceRecord(row) {
  return {
    id:                    row.id,
    employeeId:            row.employee_id,
    date:                  row.date,
    shiftId:               row.shift_id,
    clockInTime:           row.clock_in_time,
    clockOutTime:          row.clock_out_time,
    totalHours:            parseFloat(row.total_hours) || 0,
    status:                row.status,
    lateMinutes:           row.late_minutes || 0,
    earlyDepartureMinutes: row.early_departure_minutes || 0,
    overtimeHours:         parseFloat(row.overtime_hours) || 0,
    overtimeType:          row.overtime_type,
    overtimeAmount:        parseFloat(row.overtime_amount) || 0,
    overtimeApprovedBy:    row.overtime_approved_by,
    overtimeApproved:      row.overtime_approved,
    workedOnRestDay:       row.worked_on_rest_day,
    restDaySubstitute:     row.rest_day_substitute,
    missingClockOut:       row.missing_clock_out,
    isRamadanDay:          row.is_ramadan_day,
    absenceDeduction:      parseFloat(row.absence_deduction) || 0,
    lateDeduction:         parseFloat(row.late_deduction) || 0,
    periodClosed:          row.period_closed,
    resolvedBy:            row.resolved_by,
    resolutionType:        row.resolution_type,
    resolutionNotes:       row.resolution_notes,
    updatedAt:             row.updated_at,
  };
}

// ── COMPUTE & SAVE ATTENDANCE FOR A DAY ──────────────────────────────────────

/**
 * Compute and save the attendance record for one employee on one day.
 * Reads clock events, leave status, holiday status, Ramadan status.
 * This is the main integration function — called after any clock event.
 */
export async function computeAndSaveAttendance({
  employee,
  date,
  shift,
  settings,
  approvedLeaves,
  holidayDates,
  ramadanStart,
  ramadanEnd,
}) {
  const weekendDays = settings?.weekendDays || ['Fri','Sat'];
  const isWeekend   = isWeekendDay(date, weekendDays);
  const isHoliday   = isPublicHolidayDay(date, holidayDates);
  const isRamadan   = isRamadanDay(date, ramadanStart, ramadanEnd);

  // Check if employee has approved leave on this date (Connection B)
  const hasApprovedLeave = (approvedLeaves || []).some(l =>
    l.status === 'Approved' && l.startDate <= date && l.endDate >= date
  );

  // Get clock events for this day
  const events = await getClockEvents(employee.id, date);
  const clockIn  = events.find(e => e.eventType === 'CLOCK_IN')?.eventTime || null;
  const clockOut = events.filter(e => e.eventType === 'CLOCK_OUT').pop()?.eventTime || null;

  // Derive status
  const derived = deriveAttendanceStatus({
    date,
    clockIn,
    clockOut,
    shift,
    hasApprovedLeave,
    isWeekend,
    isHoliday,
    isRamadan,
    settings,
    monthlyBasic: employee.basicSalary || 0,
  });

  // Save record
  return upsertAttendanceRecord({
    employeeId:            employee.id,
    date,
    shiftId:               shift?.id || null,
    clockInTime:           clockIn,
    clockOutTime:          clockOut,
    totalHours:            derived.totalHours || 0,
    status:                derived.status,
    lateMinutes:           derived.lateMinutes || 0,
    earlyDepartureMinutes: derived.earlyDepartureMinutes || 0,
    overtimeHours:         derived.overtimeHours || 0,
    overtimeType:          derived.overtimeType || null,
    overtimeAmount:        derived.overtimeAmount || 0,
    missingClockOut:       derived.missingClockOut || false,
    isRamadanDay:          isRamadan,
    lateDeduction:         derived.lateDeduction || 0,
  });
}

// ── ATTENDANCE PERIODS ────────────────────────────────────────────────────────

export async function getAttendancePeriod(period) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data, error } = await supabase
    .from('attendance_periods')
    .select('*')
    .eq('user_id', user.id)
    .eq('period', period)
    .maybeSingle();
  if (error) { console.error('getAttendancePeriod:', error); return null; }
  return data ? { id: data.id, period: data.period, status: data.status, closedAt: data.closed_at, closedBy: data.closed_by, payrollReady: data.payroll_ready, openItems: data.open_items } : null;
}

export async function getAttendancePeriods() {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('attendance_periods')
    .select('*')
    .eq('user_id', user.id)
    .order('period', { ascending: false });
  if (error) { console.error('getAttendancePeriods:', error); return []; }
  return (data || []).map(row => ({ id: row.id, period: row.period, status: row.status, closedAt: row.closed_at, closedBy: row.closed_by, payrollReady: row.payroll_ready, openItems: row.open_items }));
}

export async function closeAttendancePeriod(period, closedBy) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { error } = await supabase.from('attendance_periods').upsert({
    user_id:       user.id,
    period,
    status:        'closed',
    closed_at:     new Date().toISOString(),
    closed_by:     closedBy || user.email || user.id,
    payroll_ready: true,
  }, { onConflict: 'user_id,period' });
  if (error) throw error;
  // Lock all attendance records for this period
  const [y, m] = period.split('-').map(Number);
  await supabase.from('attendance_records')
    .update({ period_closed: true })
    .eq('user_id', user.id)
    .gte('date', `${y}-${String(m).padStart(2,'0')}-01`)
    .lte('date', `${y}-${String(m).padStart(2,'0')}-${new Date(y, m, 0).getDate()}`);
}

// ── REGULARISATION REQUESTS ───────────────────────────────────────────────────

export async function getRegularisationRequests(filters = {}) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return [];
  let query = supabase.from('regularisation_requests').select('*').eq('user_id', user.id).order('submitted_at', { ascending: false });
  if (filters.employeeId) query = query.eq('employee_id', filters.employeeId);
  if (filters.status)     query = query.eq('status', filters.status);
  const { data, error } = await query;
  if (error) { console.error('getRegularisationRequests:', error); return []; }
  return (data || []).map(row => ({
    id:               row.id,
    employeeId:       row.employee_id,
    attendanceDate:   row.attendance_date,
    correctClockIn:   row.correct_clock_in,
    correctClockOut:  row.correct_clock_out,
    reason:           row.reason,
    status:           row.status,
    approvedBy:       row.approved_by,
    approvedAt:       row.approved_at,
    rejectionReason:  row.rejection_reason,
    originalClockIn:  row.original_clock_in,
    originalClockOut: row.original_clock_out,
    submittedAt:      row.submitted_at,
  }));
}

export async function submitRegularisationRequest({ employeeId, attendanceDate, correctClockIn, correctClockOut, reason, originalClockIn, originalClockOut }) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase.from('regularisation_requests').insert({
    user_id:           user.id,
    employee_id:       employeeId,
    attendance_date:   attendanceDate,
    correct_clock_in:  correctClockIn,
    correct_clock_out: correctClockOut,
    reason,
    original_clock_in:  originalClockIn || null,
    original_clock_out: originalClockOut || null,
    status:            'Pending',
  }).select().single();
  if (error) throw error;
  return data;
}

export async function approveRegularisationRequest(id, approvedBy) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase.from('regularisation_requests')
    .update({ status: 'Approved', approved_by: approvedBy || user.email, approved_at: new Date().toISOString() })
    .eq('id', id)
    .select()
    .single();
  if (error) throw error;
  return data;
}

export async function rejectRegularisationRequest(id, rejectionReason, rejectedBy) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error('Not authenticated');
  const { error } = await supabase.from('regularisation_requests')
    .update({ status: 'Rejected', rejection_reason: rejectionReason, approved_by: rejectedBy || user.email })
    .eq('id', id);
  if (error) throw error;
}

// ── AUDIT LOG ─────────────────────────────────────────────────────────────────

export async function addAttendanceAuditLog({ employeeId, attendanceDate, action, actor, oldValue, newValue, reason }) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return;
  await supabase.from('attendance_audit_log').insert({
    user_id:         user.id,
    employee_id:     employeeId,
    attendance_date: attendanceDate || null,
    action,
    actor:           actor || user.email || user.id,
    old_value:       String(oldValue ?? ''),
    new_value:       String(newValue ?? ''),
    reason:          reason || '',
  });
}

// ── PAYROLL INTEGRATION ───────────────────────────────────────────────────────

/**
 * Get attendance-derived payroll data for a period.
 * Connection C: Called by Payroll module — never requires manual input.
 * Returns absence deductions, overtime earnings, late deductions per employee.
 */
export async function getAttendancePayrollData(period) {
  const periodData = await getAttendancePeriod(period);
  const records    = await getAttendanceRecords({ period });

  // Group by employee
  const byEmployee = {};
  for (const rec of records) {
    if (!byEmployee[rec.employeeId]) byEmployee[rec.employeeId] = [];
    byEmployee[rec.employeeId].push(rec);
  }

  return {
    periodClosed:  periodData?.status === 'closed',
    payrollReady:  periodData?.payrollReady ?? false,
    byEmployee,
  };
}
