/**
 * attendanceEngine.js — UAE Attendance Calculation Engine for Workloop
 *
 * UAE Law References:
 *   Art. 17  — Max 8 hrs/day, 48 hrs/week ordinary working hours
 *   Art. 19  — Overtime rate 1.25× for hours beyond daily/weekly limit
 *   Art. 20  — Rest day work: 1.5× if no substitute rest day given
 *   Art. 26  — Night work (22:00–06:00): 1.25× premium
 *   Art. 17 (Ramadan) — Working hours reduced by 2/day during Ramadan
 *   Art. 44  — 7 consecutive unexplained absent days threshold
 *   Art. 56  — WPS 30-day payment deadline
 *   Min. Res. 279/2022 — Remote/flexible work framework
 */

// ── Attendance Status Constants ───────────────────────────────────────────────
export const ATTENDANCE_STATUS = {
  PRESENT:              'PRESENT',
  ABSENT:               'ABSENT',
  ON_LEAVE:             'ON_LEAVE',
  PUBLIC_HOLIDAY:       'PUBLIC_HOLIDAY',
  WEEKEND:              'WEEKEND',
  LATE:                 'LATE',
  EARLY_DEPARTURE:      'EARLY_DEPARTURE',
  HALF_DAY:             'HALF_DAY',
  OVERTIME:             'OVERTIME',
  UNEXPLAINED_ABSENCE:  'UNEXPLAINED_ABSENCE',
  PRESENT_REMOTE:       'PRESENT_REMOTE',
  MISSING_CLOCK_OUT:    'MISSING_CLOCK_OUT',
};

export const STATUS_COLORS = {
  PRESENT:             '#057a55',
  ABSENT:              '#c81e1e',
  ON_LEAVE:            '#1a56db',
  PUBLIC_HOLIDAY:      '#7c3aed',
  WEEKEND:             '#9ca3af',
  LATE:                '#c27803',
  EARLY_DEPARTURE:     '#c27803',
  HALF_DAY:            '#0891b2',
  OVERTIME:            '#059669',
  UNEXPLAINED_ABSENCE: '#dc2626',
  PRESENT_REMOTE:      '#0d9488',
  MISSING_CLOCK_OUT:   '#d97706',
};

export const STATUS_LABELS = {
  PRESENT:             'Present',
  ABSENT:              'Absent',
  ON_LEAVE:            'On Leave',
  PUBLIC_HOLIDAY:      'Public Holiday',
  WEEKEND:             'Weekend',
  LATE:                'Late',
  EARLY_DEPARTURE:     'Early Departure',
  HALF_DAY:            'Half Day',
  OVERTIME:            'Overtime',
  UNEXPLAINED_ABSENCE: 'Unexplained Absence',
  PRESENT_REMOTE:      'Present (Remote)',
  MISSING_CLOCK_OUT:   'Missing Clock-Out',
};

// ── Day-of-week helpers ───────────────────────────────────────────────────────

const DAY_NAMES = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

/**
 * Get the short day name for a date.
 * @param {string|Date} date
 * @returns {string} e.g. 'Mon'
 */
export function getDayName(date) {
  return DAY_NAMES[new Date(date).getDay()];
}

/**
 * Check if a date is a weekend day based on company settings.
 * @param {string|Date} date
 * @param {string[]} weekendDays — e.g. ['Fri','Sat']
 * @returns {boolean}
 */
export function isWeekendDay(date, weekendDays = ['Fri','Sat']) {
  return weekendDays.includes(getDayName(date));
}

/**
 * Check if a date is a public holiday.
 * @param {string|Date} date
 * @param {string[]} holidayDates — array of 'YYYY-MM-DD'
 * @returns {boolean}
 */
export function isPublicHolidayDay(date, holidayDates = []) {
  const d = new Date(date).toISOString().split('T')[0];
  return holidayDates.includes(d);
}

/**
 * Check if a date falls within the Ramadan period.
 * Reads Ramadan dates from Leave Management settings — never hardcoded.
 * Art. 17 (Ramadan): working hours reduced by 2 per day.
 * @param {string|Date} date
 * @param {string|null} ramadanStart — 'YYYY-MM-DD'
 * @param {string|null} ramadanEnd   — 'YYYY-MM-DD'
 * @returns {boolean}
 */
export function isRamadanDay(date, ramadanStart, ramadanEnd) {
  if (!ramadanStart || !ramadanEnd) return false;
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  const s = new Date(ramadanStart);
  const e = new Date(ramadanEnd);
  s.setHours(0, 0, 0, 0);
  e.setHours(23, 59, 59, 999);
  return d >= s && d <= e;
}

/**
 * Get the expected working hours for a day, accounting for Ramadan.
 * Art. 17: max 8 hrs/day; Art. 17 (Ramadan): reduce by 2 during Ramadan.
 * @param {object} shift
 * @param {boolean} isRamadan
 * @returns {number} expected hours
 */
export function getExpectedHours(shift, isRamadan = false) {
  const base = parseFloat(shift?.expectedHours) || 8;
  // Art. 17 (Ramadan): reduce by 2 hours during Ramadan
  return isRamadan ? Math.max(0, base - 2) : base;
}

// ── Time parsing helpers ──────────────────────────────────────────────────────

/**
 * Parse a time string 'HH:MM' or 'HH:MM:SS' into minutes since midnight.
 * @param {string} timeStr
 * @returns {number}
 */
export function timeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + (m || 0);
}

/**
 * Format minutes since midnight as 'HH:MM'.
 * @param {number} minutes
 * @returns {string}
 */
export function minutesToTime(minutes) {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
}

/**
 * Get minutes since midnight from a Date or ISO timestamp.
 * @param {string|Date} dt
 * @returns {number}
 */
export function getMinutesOfDay(dt) {
  const d = new Date(dt);
  return d.getHours() * 60 + d.getMinutes();
}

// ── Overtime Calculation (UAE Law) ────────────────────────────────────────────

/**
 * Calculate the hourly rate for an employee.
 * UAE formula: (monthly basic × 12) ÷ (52 × weekly working hours)
 * @param {number} monthlyBasic
 * @param {number} weeklyHours — default 48 (Art. 17 max)
 * @returns {number} hourly rate in AED
 */
export function calculateHourlyRate(monthlyBasic, weeklyHours = 48) {
  return (parseFloat(monthlyBasic) * 12) / (52 * weeklyHours);
}

/**
 * Calculate overtime pay for a given attendance record.
 *
 * Art. 19: Overtime rate = hourly rate × 1.25 (standard)
 * Art. 20: Rest day (no substitute) = hourly rate × 1.50
 * Art. 26: Night shift (22:00–06:00) = hourly rate × 1.25
 * Note: Do NOT stack premiums — apply only the HIGHER rate.
 *
 * @param {number} overtimeHours
 * @param {string} overtimeType — 'STANDARD' | 'REST_DAY_NO_SUB' | 'REST_DAY_WITH_SUB' | 'NIGHT_SHIFT'
 * @param {number} hourlyRate
 * @returns {{ amount: number, rate: number, label: string }}
 */
export function calculateOvertimePay(overtimeHours, overtimeType, hourlyRate) {
  let rate = 1.25;
  let label = 'Standard Overtime (Art. 19)';

  switch (overtimeType) {
    case 'REST_DAY_NO_SUB':
      // Art. 20: 1.5× if no substitute rest day
      rate = 1.50;
      label = 'Rest Day — No Substitute (Art. 20)';
      break;
    case 'REST_DAY_WITH_SUB':
      // Art. 20: normal rate if substitute rest day given
      rate = 1.0;
      label = 'Rest Day — Substitute Given (Art. 20)';
      break;
    case 'NIGHT_SHIFT':
      // Art. 26: 1.25× for night hours (22:00–06:00)
      rate = 1.25;
      label = 'Night Shift Premium (Art. 26)';
      break;
    default:
      // Art. 19: standard overtime 1.25×
      rate = 1.25;
      label = 'Standard Overtime (Art. 19)';
  }

  const amount = parseFloat(overtimeHours) * hourlyRate * rate;
  return { amount, rate, label };
}

/**
 * Check if hours worked include night shift hours (22:00–06:00).
 * Art. 26: Night work premium applies.
 * @param {string|Date} clockIn
 * @param {string|Date} clockOut
 * @returns {boolean}
 */
export function hasNightShiftHours(clockIn, clockOut) {
  if (!clockIn || !clockOut) return false;
  const inMins  = getMinutesOfDay(clockIn);
  const outMins = getMinutesOfDay(clockOut);
  const nightStart = 22 * 60; // 22:00
  const nightEnd   = 6 * 60;  // 06:00
  // Night shift: after 22:00 or before 06:00
  return inMins >= nightStart || outMins <= nightEnd || outMins < inMins;
}

// ── Attendance Status Derivation ──────────────────────────────────────────────

/**
 * Derive the attendance status for a single employee on a single day.
 * This is the core function — called whenever any input changes.
 *
 * Priority order:
 *   1. Weekend → WEEKEND
 *   2. Public holiday → PUBLIC_HOLIDAY
 *   3. Approved leave → ON_LEAVE
 *   4. Has clock-in but no clock-out → MISSING_CLOCK_OUT
 *   5. Has clock-in and clock-out → PRESENT (with late/early/overtime sub-status)
 *   6. No clock-in, no leave → UNEXPLAINED_ABSENCE (if past today) or ABSENT
 *
 * @param {object} params
 * @param {string} params.date — 'YYYY-MM-DD'
 * @param {string|null} params.clockIn — ISO timestamp or null
 * @param {string|null} params.clockOut — ISO timestamp or null
 * @param {object|null} params.shift — shift config object
 * @param {boolean} params.hasApprovedLeave — from Leave Management
 * @param {boolean} params.isWeekend
 * @param {boolean} params.isHoliday
 * @param {boolean} params.isRamadan
 * @param {object} params.settings — attendance settings
 * @param {number} params.monthlyBasic — for overtime calculation
 * @returns {object} attendance record fields
 */
export function deriveAttendanceStatus({
  date,
  clockIn,
  clockOut,
  shift,
  hasApprovedLeave,
  isWeekend,
  isHoliday,
  isRamadan,
  settings,
  monthlyBasic = 0,
}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const recordDate = new Date(date);
  recordDate.setHours(0, 0, 0, 0);
  const isPast = recordDate <= today;

  // 1. Weekend
  if (isWeekend) {
    return { status: ATTENDANCE_STATUS.WEEKEND, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: false, isRamadanDay: isRamadan };
  }

  // 2. Public holiday
  if (isHoliday) {
    return { status: ATTENDANCE_STATUS.PUBLIC_HOLIDAY, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: false, isRamadanDay: isRamadan };
  }

  // 3. Approved leave (read from Leave Management — do NOT mark as absent)
  if (hasApprovedLeave) {
    return { status: ATTENDANCE_STATUS.ON_LEAVE, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: false, isRamadanDay: isRamadan };
  }

  // 4. No clock-in
  if (!clockIn) {
    if (!isPast) {
      return { status: ATTENDANCE_STATUS.ABSENT, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: false, isRamadanDay: isRamadan };
    }
    return { status: ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: false, isRamadanDay: isRamadan };
  }

  // 5. Has clock-in but no clock-out
  if (clockIn && !clockOut) {
    return { status: ATTENDANCE_STATUS.MISSING_CLOCK_OUT, lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: 0, overtimeAmount: 0, missingClockOut: true, isRamadanDay: isRamadan };
  }

  // 6. Has both clock-in and clock-out — calculate details
  const inTime  = new Date(clockIn);
  const outTime = new Date(clockOut);
  const totalMs = outTime - inTime;
  const breakMs = (parseFloat(shift?.breakMinutes) || 60) * 60 * 1000;
  const totalHours = Math.max(0, (totalMs - breakMs) / (1000 * 60 * 60));

  // Expected hours (Ramadan-adjusted)
  // Art. 17 (Ramadan): reduce by 2 hours
  const expectedHours = getExpectedHours(shift, isRamadan);

  // Late minutes
  const lateGrace = parseInt(settings?.lateGraceMinutes ?? shift?.lateGraceMinutes ?? 10);
  let lateMinutes = 0;
  if (shift?.startTime) {
    const shiftStartMins = timeToMinutes(shift.startTime);
    const actualStartMins = getMinutesOfDay(inTime);
    lateMinutes = Math.max(0, actualStartMins - shiftStartMins - lateGrace);
  }

  // Early departure minutes
  const earlyGrace = parseInt(settings?.earlyDepartureGraceMinutes ?? shift?.earlyDepartureGraceMinutes ?? 10);
  let earlyDepartureMinutes = 0;
  if (shift?.endTime) {
    const shiftEndMins = timeToMinutes(shift.endTime);
    const actualEndMins = getMinutesOfDay(outTime);
    earlyDepartureMinutes = Math.max(0, shiftEndMins - earlyGrace - actualEndMins);
  }

  // Overtime hours (Art. 19)
  const overtimeHours = Math.max(0, totalHours - expectedHours);

  // Overtime type
  let overtimeType = 'STANDARD';
  if (hasNightShiftHours(clockIn, clockOut)) {
    overtimeType = 'NIGHT_SHIFT';
  }

  // Overtime amount
  const hourlyRate = calculateHourlyRate(monthlyBasic);
  const { amount: overtimeAmount } = overtimeHours > 0
    ? calculateOvertimePay(overtimeHours, overtimeType, hourlyRate)
    : { amount: 0 };

  // Determine status
  let status = ATTENDANCE_STATUS.PRESENT;
  if (overtimeHours > 0) status = ATTENDANCE_STATUS.OVERTIME;
  if (lateMinutes > 0 && earlyDepartureMinutes > 0) status = ATTENDANCE_STATUS.HALF_DAY;
  else if (lateMinutes > 0) status = ATTENDANCE_STATUS.LATE;
  else if (earlyDepartureMinutes > 0) status = ATTENDANCE_STATUS.EARLY_DEPARTURE;

  // Late deduction
  let lateDeduction = 0;
  if (lateMinutes > 0 && settings?.lateDeductionPolicy === 'per_minute') {
    lateDeduction = lateMinutes * (parseFloat(settings.lateDeductionAmount) || 0);
  } else if (lateMinutes > 0 && settings?.lateDeductionPolicy === 'per_occurrence') {
    lateDeduction = parseFloat(settings.lateDeductionAmount) || 0;
  }

  return {
    status,
    totalHours,
    lateMinutes,
    earlyDepartureMinutes,
    overtimeHours,
    overtimeType: overtimeHours > 0 ? overtimeType : null,
    overtimeAmount,
    lateDeduction,
    missingClockOut: false,
    isRamadanDay: isRamadan,
  };
}

// ── Absence Deduction ─────────────────────────────────────────────────────────

/**
 * Calculate absence deduction for payroll.
 * Deduction = (monthly basic ÷ 30) × absent days
 * Only applies to UNEXPLAINED_ABSENCE with resolution_type = 'UNAUTHORISED'.
 * Does NOT double-count leave deductions already handled by Leave Management.
 *
 * @param {number} unauthorisedAbsentDays
 * @param {number} monthlyBasic
 * @returns {{ days: number, dailyRate: number, deduction: number }}
 */
export function calculateAbsenceDeduction(unauthorisedAbsentDays, monthlyBasic) {
  const dailyRate = (parseFloat(monthlyBasic) || 0) / 30;
  const deduction = Math.max(0, unauthorisedAbsentDays) * dailyRate;
  return {
    days: Math.max(0, unauthorisedAbsentDays),
    dailyRate,
    deduction,
  };
}

// ── Consecutive Absence Check (Art. 44) ───────────────────────────────────────

/**
 * Check if an employee has 7+ consecutive unexplained absent working days.
 * Art. 44: Employer may consider this a resignation after conditions are met.
 * Do NOT auto-terminate — surface the flag to HR.
 *
 * @param {object[]} records — attendance records sorted by date ascending
 * @param {string[]} weekendDays
 * @param {string[]} holidayDates
 * @returns {{ flagged: boolean, consecutiveDays: number, since: string|null }}
 */
export function checkConsecutiveAbsences(records, weekendDays = ['Fri','Sat'], holidayDates = []) {
  let consecutive = 0;
  let since = null;

  for (const rec of [...records].sort((a, b) => a.date.localeCompare(b.date))) {
    if (isWeekendDay(rec.date, weekendDays) || isPublicHolidayDay(rec.date, holidayDates)) continue;
    if (rec.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE) {
      consecutive++;
      if (!since) since = rec.date;
    } else {
      consecutive = 0;
      since = null;
    }
  }

  return {
    flagged: consecutive >= 7,
    consecutiveDays: consecutive,
    since,
  };
}

// ── Payroll Summary for a Period ──────────────────────────────────────────────

/**
 * Summarise attendance data for payroll integration.
 * Returns all payroll-relevant values for a single employee for a period.
 * Connection C: Payroll reads this — never requires manual input.
 *
 * @param {object[]} records — attendance records for the period
 * @param {number} monthlyBasic
 * @returns {{
 *   unauthorisedAbsentDays: number,
 *   absenceDeduction: number,
 *   totalOvertimeHours: number,
 *   totalOvertimeAmount: number,
 *   totalLateDeduction: number,
 *   lineItems: Array<{label: string, amount: number, type: 'deduction'|'earning'}>,
 * }}
 */
export function getPayrollSummaryFromAttendance(records, monthlyBasic) {
  const unauthorisedAbsent = records.filter(r =>
    r.status === ATTENDANCE_STATUS.UNEXPLAINED_ABSENCE && r.resolutionType === 'UNAUTHORISED'
  );
  const { deduction: absenceDeduction } = calculateAbsenceDeduction(unauthorisedAbsent.length, monthlyBasic);

  const totalOvertimeHours  = records.reduce((s, r) => s + (parseFloat(r.overtimeHours) || 0), 0);
  const totalOvertimeAmount = records.reduce((s, r) => s + (parseFloat(r.overtimeAmount) || 0), 0);
  const totalLateDeduction  = records.reduce((s, r) => s + (parseFloat(r.lateDeduction) || 0), 0);

  const lineItems = [];

  if (absenceDeduction > 0) {
    lineItems.push({
      label: `Absence Deduction (${unauthorisedAbsent.length} day${unauthorisedAbsent.length !== 1 ? 's' : ''})`,
      amount: absenceDeduction,
      type: 'deduction',
      attendanceDates: unauthorisedAbsent.map(r => r.date),
    });
  }

  if (totalOvertimeAmount > 0) {
    lineItems.push({
      label: `Overtime Earnings (${totalOvertimeHours.toFixed(2)} hrs)`,
      amount: totalOvertimeAmount,
      type: 'earning',
    });
  }

  if (totalLateDeduction > 0) {
    lineItems.push({
      label: `Late/Early Departure Deduction`,
      amount: totalLateDeduction,
      type: 'deduction',
    });
  }

  return {
    unauthorisedAbsentDays: unauthorisedAbsent.length,
    absenceDeduction,
    totalOvertimeHours,
    totalOvertimeAmount,
    totalLateDeduction,
    lineItems,
  };
}

// ── Period helpers ────────────────────────────────────────────────────────────

/**
 * Get all working days in a month (excluding weekends and public holidays).
 * @param {number} year
 * @param {number} month — 1-based
 * @param {string[]} weekendDays
 * @param {string[]} holidayDates
 * @returns {string[]} array of 'YYYY-MM-DD'
 */
export function getWorkingDaysInMonth(year, month, weekendDays = ['Fri','Sat'], holidayDates = []) {
  const days = [];
  const daysInMonth = new Date(year, month, 0).getDate();
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    if (!isWeekendDay(dateStr, weekendDays) && !isPublicHolidayDay(dateStr, holidayDates)) {
      days.push(dateStr);
    }
  }
  return days;
}

/**
 * Format a decimal hours value as "Xh Ym".
 * @param {number} hours
 * @returns {string}
 */
export function formatHours(hours) {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}
