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

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ── ATTENDANCE SETTINGS ───────────────────────────────────────────────────────

export async function getAttendanceSettings() {
  const user = await getSessionUser();
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
  void settings;
  throw new Error('Attendance settings have moved to the migration attendance configuration screen.');
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
  const user = await getSessionUser();
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
  void shift;
  throw new Error('Shift changes have moved to the migration attendance configuration screen.');
}

export async function deleteShift(id) {
  void id;
  throw new Error('Shift changes have moved to the migration attendance configuration screen.');
}

function dbToShift(row) {
  return {
    id:                row.id,
    name:              row.name,
    code:              row.code || '',
    shiftCategory:     row.shift_category || 'morning',
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
    color:             row.color || '#6366f1',
    minStaff:          row.min_staff ?? 1,
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
  void employeeId; void shiftId; void effectiveFrom; void effectiveTo;
  throw new Error('Shift assignments have moved to the migration attendance configuration screen.');
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
  void employeeId; void eventType; void method; void notes; void enteredBy; void ipAddress;
  throw new Error('Clock-event writes have moved to the migration attendance ingestion screen.');
}

export async function recordManualClockEvent({ employeeId, eventType, eventTime, notes, enteredBy }) {
  void employeeId; void eventType; void eventTime; void notes; void enteredBy;
  throw new Error('Manual clock-event writes have moved to the migration attendance ingestion screen.');
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
  void filters;
  throw new Error('Attendance reads moved to the migration attendance calculation screen.');
}

export async function upsertAttendanceRecord(record) {
  void record;
  throw new Error('Attendance record writes moved to the migration attendance calculation screen.');
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
  void employee; void date; void shift; void settings; void approvedLeaves;
  void holidayDates; void ramadanStart; void ramadanEnd;
  throw new Error('Attendance calculation moved to the migration attendance calculation screen.');
}

// ── ATTENDANCE PERIODS ────────────────────────────────────────────────────────

export async function getAttendancePeriod(period) {
  void period;
  throw new Error('Attendance period reads have moved to the migration attendance close screen.');
}

export async function getAttendancePeriods() {
  throw new Error('Attendance period reads have moved to the migration attendance close screen.');
}

export async function closeAttendancePeriod(period, closedBy) {
  void period; void closedBy;
  throw new Error('Attendance period close has moved to the migration attendance close screen.');
}

// ── REGULARISATION REQUESTS ───────────────────────────────────────────────────

export async function getRegularisationRequests(filters = {}) {
  void filters;
  throw new Error('Attendance corrections have moved to the migration attendance exceptions screen.');
}

export async function submitRegularisationRequest({ employeeId, attendanceDate, correctClockIn, correctClockOut, reason, originalClockIn, originalClockOut }) {
  void employeeId; void attendanceDate; void correctClockIn; void correctClockOut;
  void reason; void originalClockIn; void originalClockOut;
  throw new Error('Attendance corrections have moved to the migration attendance exceptions screen.');
}

export async function approveRegularisationRequest(id, approvedBy) {
  void id; void approvedBy;
  throw new Error('Attendance corrections have moved to the migration attendance exceptions screen.');
}

export async function rejectRegularisationRequest(id, rejectionReason, rejectedBy) {
  void id; void rejectionReason; void rejectedBy;
  throw new Error('Attendance corrections have moved to the migration attendance exceptions screen.');
}

// ── AUDIT LOG ─────────────────────────────────────────────────────────────────

export async function addAttendanceAuditLog({ employeeId, attendanceDate, action, actor, oldValue, newValue, reason }) {
  void employeeId; void attendanceDate; void action; void actor;
  void oldValue; void newValue; void reason;
  throw new Error('Attendance audit writes have moved to the migration attendance exceptions screen.');
}

// ── PAYROLL INTEGRATION ───────────────────────────────────────────────────────

/**
 * Get attendance-derived payroll data for a period.
 * Connection C: Called by Payroll module — never requires manual input.
 * Returns absence deductions, overtime earnings, late deductions per employee.
 */
export async function getAttendancePayrollData(period) {
  void period;
  throw new Error('Attendance payroll input is available only through the migration payroll service.');
}

// ── ROSTER ASSIGNMENTS (Feature 8) ───────────────────────────────────────────

/**
 * Compute overtime from roster for a payroll period (Feature 5.2).
 * Reads roster_assignments where actual_hours > planned_hours and returns
 * per-employee overtime totals.
 *
 * Returns: { [employeeId]: { overtimeHours, plannedHours, actualHours } }
 */
export async function getOvertimeFromRoster(year, month) {
  void year; void month;
  throw new Error('Roster payroll input is available only through the migration payroll service.');
}

/**
 * Fetch all roster assignments for a calendar month.
 * Joins shifts table to include shift name and color.
 *
 * When `companyId` is passed, results are scoped to that company using the
 * project-standard "own-company OR legacy-null" filter — matching how
 * getEmployees / getPayrolls handle multi-company scoping (see CLAUDE.md).
 */
export async function getRosterForMonth(year, month, companyId = null) {
  const monthStart = `${year}-${String(month).padStart(2, '0')}-01`;
  const lastDay    = new Date(year, month, 0).getDate();
  const monthEnd   = `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;

  let q = supabase
    .from('roster_assignments')
    .select('*, shifts(*)')
    .gte('date', monthStart)
    .lte('date', monthEnd)
    .order('date', { ascending: true });

  if (companyId) {
    q = q.or(`company_id.eq.${companyId},company_id.is.null`);
  }

  const { data, error } = await q;
  if (error) { console.error('getRosterForMonth:', error); return []; }
  return (data || []).map(dbToRosterAssignment);
}

/**
 * Upsert a single roster assignment (employee × date → shift).
 * Uses ON CONFLICT on (employee_id, date) to update if already assigned.
 */
export async function saveRosterAssignment({ employeeId, shiftId, date, notes = '', published = false, plannedHours = null, companyId = null }) {
  void employeeId; void shiftId; void date; void notes; void published; void plannedHours; void companyId;
  throw new Error('Roster draft writes have moved to the migration roster screen.');
}

/**
 * Remove a roster assignment for a specific employee on a specific date.
 */
export async function deleteRosterAssignment(employeeId, date) {
  void employeeId; void date;
  throw new Error('Roster draft writes have moved to the migration roster screen.');
}

/**
 * Mark all roster assignments for a given month as published.
 * Once published, employees can see their schedule in the portal.
 * Scoped to the active company when `companyId` is provided.
 */
export async function publishRoster(year, month, companyId = null) {
  void year; void month; void companyId;
  throw new Error('Roster publication has moved to the migration roster screen.');
}

function dbToRosterAssignment(row) {
  return {
    id:           row.id,
    employeeId:   row.employee_id,
    shiftId:      row.shift_id,
    date:         row.date,
    published:    row.published,
    notes:        row.notes || '',
    plannedHours: row.planned_hours != null ? parseFloat(row.planned_hours) : null,
    actualHours:  row.actual_hours  != null ? parseFloat(row.actual_hours)  : null,
    coHours:      row.co_hours      != null ? parseFloat(row.co_hours)      : 0,
    shift:        row.shifts ? dbToShift(row.shifts) : null,
    createdAt:    row.created_at,
  };
}

// ── SHIFT SWAP REQUESTS (Feature 8) ──────────────────────────────────────────

export async function getShiftSwapRequests(filters = {}, companyId = null) {
  void filters; void companyId;
  throw new Error('Shift swap queues have moved to the migration roster workspace.');
}

/**
 * Admin approves or rejects a shift swap request.
 *
 * Approval routes through the `admin_execute_shift_swap` SECURITY DEFINER RPC
 * (sql/052_shift_swap_execution.sql) which atomically swaps the two
 * `roster_assignments` rows *and* flips the request's status in one
 * transaction. Rejection remains a simple UPDATE — no roster mutation.
 *
 * If the RPC hasn't been deployed yet (older environments), we fall back to
 * the pre-052 status-only update so the admin can still clear the queue —
 * but they'll see a warning message explaining the roster wasn't rewritten.
 */
export async function updateShiftSwapRequest(id, status, rejectionReason = '') {
  void id; void status; void rejectionReason;
  throw new Error('Shift swap decisions have moved to the migration roster workspace.');
}

// ── EMPLOYEE PORTAL — ROSTER & SWAPS ─────────────────────────────────────────

/**
 * Employee reads their own published roster via RPC.
 * Falls back to [] if the SQL migration hasn't been applied yet.
 */
export async function getMyRoster(dateFrom, dateTo) {
  void dateFrom; void dateTo;
  throw new Error('Personal schedules have moved to the migration employee workspace.');
}

/**
 * Employee gets a name-only list of colleagues (same company, not terminated).
 * Used to populate the "swap with" dropdown.
 */
export async function getMyColleagues() {
  throw new Error('Shift swap colleagues are available only in the migration employee workspace.');
}

/**
 * Employee submits a shift swap request via SECURITY DEFINER RPC.
 */
export async function requestShiftSwap({ requesterDate, targetEmployeeId, targetDate, reason }) {
  void requesterDate; void targetEmployeeId; void targetDate; void reason;
  throw new Error('Shift swap requests have moved to the migration employee workspace.');
}
