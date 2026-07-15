/**
 * leaveEngine.js — UAE Leave Management Business Logic
 *
 * Implements UAE Federal Labour Law No. 33 of 2021 leave entitlements.
 *
 * Law references used throughout:
 *   Art. 29  — Annual leave (30 days/yr, advance pay, encashment, Hajj)
 *   Art. 30  — Maternity leave (60 days: 45 full + 15 half)
 *   Art. 31  — Sick leave (15 full / 30 half / 45 unpaid per year)
 *   Art. 32  — Paternity leave (5 working days within 6 months of birth)
 *   Art. 36  — Study/exam leave (10 days/yr, UAE-accredited institution)
 *   Ministerial Resolution No. 43 of 2022 — Nursing break (1hr/day, 6 months post-maternity)
 *   UAE Cabinet Resolution No. 1 of 2022 — Bereavement leave
 */

import { servicePeriod } from './gratuityCalculator';
import { formatDateUAE } from './uaeValidators';

// ── Leave Type Definitions ────────────────────────────────────────────────────

/**
 * Default UAE leave types pre-configured for compliance.
 * These are seeded into the database on first setup.
 */
export const DEFAULT_LEAVE_TYPES = [
  {
    code: 'ANNUAL',
    name: 'Annual Leave',
    color: '#1a56db',
    isPaid: true,
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: false,
    requiresReason: false,
    minNoticeDays: 14,
    // Art. 29: 30 calendar days/yr for 1+ year service; 2 days/month for 6-12 months
    annualEntitlementDays: 30,
    accrualType: 'monthly', // 2.5 days per month
    dayCountType: 'calendar', // annual leave uses calendar days (Art. 29)
    autoApprove: false,
    carryForwardAllowed: true,
    carryForwardMaxDays: 15,
    probationEligible: false, // annual leave not available during probation (Art. 29)
    lawReference: 'Art. 29 — Federal Decree-Law No. 33 of 2021',
  },
  {
    code: 'SICK',
    name: 'Sick Leave',
    color: '#c27803',
    isPaid: true, // partial — tiered pay
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: true, // medical certificate required
    requiresReason: true,
    minNoticeDays: 0,
    // Art. 31: 15 full + 30 half + 45 unpaid = 90 days total per year
    annualEntitlementDays: 90,
    accrualType: 'fixed',
    dayCountType: 'calendar',
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    lawReference: 'Art. 31 — Federal Decree-Law No. 33 of 2021',
    // Sick leave tiers
    tiers: [
      { days: 15, payPercent: 100, label: 'Full pay' },
      { days: 30, payPercent: 50,  label: 'Half pay' },
      { days: 45, payPercent: 0,   label: 'Unpaid' },
    ],
  },
  {
    code: 'MATERNITY',
    name: 'Maternity Leave',
    color: '#e879f9',
    isPaid: true, // partial — tiered pay
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: true,
    requiresReason: false,
    minNoticeDays: 30,
    // Art. 30: 60 days (45 full + 15 half); additional 45 unpaid for complications
    annualEntitlementDays: 60,
    accrualType: 'fixed',
    dayCountType: 'calendar',
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    genderRestriction: 'Female',
    minServiceMonths: 12, // 1 year service required for paid maternity
    lawReference: 'Art. 30 — Federal Decree-Law No. 33 of 2021',
    tiers: [
      { days: 45, payPercent: 100, label: 'Full pay' },
      { days: 15, payPercent: 50,  label: 'Half pay' },
    ],
  },
  {
    code: 'PATERNITY',
    name: 'Paternity Leave',
    color: '#0891b2',
    isPaid: true,
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: false,
    requiresReason: false,
    minNoticeDays: 0,
    // Art. 32: 5 working days within 6 months of child's birth
    annualEntitlementDays: 5,
    accrualType: 'fixed',
    dayCountType: 'working', // paternity uses working days (Art. 32)
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    genderRestriction: 'Male',
    windowMonths: 6, // must be taken within 6 months of birth
    lawReference: 'Art. 32 — Federal Decree-Law No. 33 of 2021',
  },
  {
    code: 'HAJJ',
    name: 'Hajj Leave',
    color: '#16a34a',
    isPaid: false, // unpaid
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: false,
    requiresReason: false,
    minNoticeDays: 30,
    // Art. 29: 30 calendar days unpaid, once per career, min 2 years service
    annualEntitlementDays: 30,
    accrualType: 'once_per_career',
    dayCountType: 'calendar',
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    minServiceMonths: 24, // 2 years service required
    oncePerCareer: true,
    probationEligible: false, // Hajj leave requires min 2 years service
    lawReference: 'Art. 29 (Hajj) — Federal Decree-Law No. 33 of 2021',
  },
  {
    code: 'BEREAVEMENT',
    name: 'Bereavement Leave',
    color: '#6b7280',
    isPaid: true,
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: false,
    requiresReason: true,
    minNoticeDays: 0,
    // UAE Cabinet Resolution No. 1 of 2022
    // Spouse: 5 working days; First-degree relative: 3 working days
    // NOT deducted from annual leave balance
    annualEntitlementDays: 5, // max (spouse)
    accrualType: 'fixed',
    dayCountType: 'working', // bereavement uses working days
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    notDeductedFromAnnual: true,
    lawReference: 'UAE Cabinet Resolution No. 1 of 2022',
    relationships: [
      { label: 'Spouse', days: 5 },
      { label: 'Parent', days: 3 },
      { label: 'Child', days: 3 },
      { label: 'Sibling', days: 3 },
    ],
  },
  {
    code: 'STUDY',
    name: 'Study / Exam Leave',
    color: '#7c3aed',
    isPaid: true,
    isUnlimited: false,
    requiresApproval: true,
    requiresAttachment: true, // proof of enrollment + exam schedule required
    requiresReason: true,
    minNoticeDays: 7,
    // Art. 36: up to 10 days/yr for exams at UAE-accredited institutions
    annualEntitlementDays: 10,
    accrualType: 'fixed',
    dayCountType: 'working',
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    probationEligible: false, // study leave not available during probation (Art. 36)
    lawReference: 'Art. 36 — Federal Decree-Law No. 33 of 2021',
  },
  {
    code: 'UNPAID',
    name: 'Unpaid Leave',
    color: '#9ca3af',
    isPaid: false,
    isUnlimited: true, // at employer discretion
    requiresApproval: true,
    requiresAttachment: false,
    requiresReason: true,
    minNoticeDays: 7,
    annualEntitlementDays: 0,
    accrualType: 'none',
    dayCountType: 'calendar',
    autoApprove: false,
    carryForwardAllowed: false,
    carryForwardMaxDays: 0,
    affectsPayroll: true, // deduct (basic/30) × days from payroll
    lawReference: 'Employer discretion — Federal Decree-Law No. 33 of 2021',
  },
];

// ── UAE Federal Public Holidays ───────────────────────────────────────────────

/**
 * UAE Federal Public Holidays for 2025 and 2026.
 * Note: Eid, Islamic New Year, and Prophet's Birthday dates are approximate
 * (Hijri calendar — exact dates confirmed annually by UAE government).
 *
 * UAE rule: Public holidays falling on a weekend are NOT automatically moved.
 */
// Hint text shown to employees when a leave type requires an attachment.
// Keyed by leave type code — fallback is 'supporting document'.
export const ATTACHMENT_HINTS = {
  SICK:        'medical certificate',
  MATERNITY:   'medical certificate or birth registration',
  STUDY:       'proof of enrollment and exam schedule (Art. 36)',
  BEREAVEMENT: 'death certificate',
  HAJJ:        'pilgrimage permit',
};

export const UAE_PUBLIC_HOLIDAYS_2025 = [
  { date: '2025-01-01', name: "New Year's Day", type: 'federal' },
  { date: '2025-03-30', name: 'Eid Al Fitr (Day 1)', type: 'federal' },
  { date: '2025-03-31', name: 'Eid Al Fitr (Day 2)', type: 'federal' },
  { date: '2025-04-01', name: 'Eid Al Fitr (Day 3)', type: 'federal' },
  { date: '2025-06-06', name: 'Arafat Day (Eid Al Adha Eve)', type: 'federal' },
  { date: '2025-06-07', name: 'Eid Al Adha (Day 1)', type: 'federal' },
  { date: '2025-06-08', name: 'Eid Al Adha (Day 2)', type: 'federal' },
  { date: '2025-06-09', name: 'Eid Al Adha (Day 3)', type: 'federal' },
  { date: '2025-06-27', name: 'Islamic New Year (1 Muharram)', type: 'federal' },
  { date: '2025-09-04', name: "Prophet's Birthday (12 Rabi Al Awwal)", type: 'federal' },
  { date: '2025-12-01', name: 'Commemoration Day', type: 'federal' },
  { date: '2025-12-02', name: 'National Day', type: 'federal' },
  { date: '2025-12-03', name: 'National Day (Day 2)', type: 'federal' },
];

export const UAE_PUBLIC_HOLIDAYS_2026 = [
  { date: '2026-01-01', name: "New Year's Day", type: 'federal' },
  { date: '2026-03-20', name: 'Eid Al Fitr (Day 1)', type: 'federal' },
  { date: '2026-03-21', name: 'Eid Al Fitr (Day 2)', type: 'federal' },
  { date: '2026-03-22', name: 'Eid Al Fitr (Day 3)', type: 'federal' },
  { date: '2026-05-27', name: 'Arafat Day (Eid Al Adha Eve)', type: 'federal' },
  { date: '2026-05-28', name: 'Eid Al Adha (Day 1)', type: 'federal' },
  { date: '2026-05-29', name: 'Eid Al Adha (Day 2)', type: 'federal' },
  { date: '2026-05-30', name: 'Eid Al Adha (Day 3)', type: 'federal' },
  { date: '2026-06-16', name: 'Islamic New Year (1 Muharram)', type: 'federal' },
  { date: '2026-08-25', name: "Prophet's Birthday (12 Rabi Al Awwal)", type: 'federal' },
  { date: '2026-12-01', name: 'Commemoration Day', type: 'federal' },
  { date: '2026-12-02', name: 'National Day', type: 'federal' },
  { date: '2026-12-03', name: 'National Day (Day 2)', type: 'federal' },
];

// ── Working Day Calculation ───────────────────────────────────────────────────

/**
 * Check if a date is a weekend day.
 * UAE default: Friday (5) and Saturday (6).
 * @param {Date} date
 * @param {string} weekendDef — 'fri-sat' (UAE default) or 'sat-sun'
 * @returns {boolean}
 */
export function isWeekend(date, weekendDef = 'fri-sat') {
  const day = date.getDay(); // 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
  if (weekendDef === 'fri-sat') return day === 5 || day === 6;
  return day === 0 || day === 6; // sat-sun
}

/**
 * Check if a date is a public holiday.
 * @param {Date} date
 * @param {string[]} holidayDates — array of 'YYYY-MM-DD' strings
 * @returns {boolean}
 */
export function isPublicHoliday(date, holidayDates = []) {
  const dateStr = date.toISOString().split('T')[0];
  return holidayDates.includes(dateStr);
}

/**
 * Count working days between two dates (inclusive of both start and end).
 * Excludes weekends and public holidays.
 *
 * Used for: paternity leave, bereavement leave, study leave (Art. 32, Cabinet Res. 1/2022, Art. 36)
 *
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @param {string[]} holidayDates
 * @param {string} weekendDef
 * @returns {number}
 */
export function countWorkingDays(startDate, endDate, holidayDates = [], weekendDef = 'fri-sat') {
  const start = new Date(startDate);
  const end   = new Date(endDate);
  start.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);

  let count = 0;
  const current = new Date(start);
  while (current <= end) {
    if (!isWeekend(current, weekendDef) && !isPublicHoliday(current, holidayDates)) {
      count++;
    }
    current.setDate(current.getDate() + 1);
  }
  return count;
}

/**
 * Count calendar days between two dates (inclusive of both start and end).
 * Used for: annual leave, sick leave, maternity leave, Hajj leave (Art. 29, 30, 31)
 *
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @returns {number}
 */
export function countCalendarDays(startDate, endDate) {
  const start = new Date(startDate);
  const end   = new Date(endDate);
  start.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);
  return Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1;
}

/**
 * Count leave days for a request based on the leave type's day count type.
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @param {'calendar'|'working'} dayCountType
 * @param {string[]} holidayDates
 * @param {string} weekendDef
 * @param {boolean} isHalfDay
 * @returns {number}
 */
export function countLeaveDays(startDate, endDate, dayCountType, holidayDates = [], weekendDef = 'fri-sat', isHalfDay = false) {
  if (isHalfDay) return 0.5;
  if (dayCountType === 'working') {
    return countWorkingDays(startDate, endDate, holidayDates, weekendDef);
  }
  return countCalendarDays(startDate, endDate);
}

// ── Annual Leave Accrual ──────────────────────────────────────────────────────

/**
 * Calculate annual leave entitlement and accrual for an employee.
 *
 * Art. 29 — UAE Federal Decree-Law No. 33 of 2021:
 *   - < 6 months service: no annual leave entitlement
 *   - 6–12 months service: 2 calendar days per month (pro-rata)
 *   - 1+ year service: 30 calendar days per year (2.5 days per month)
 *
 * @param {string|Date} startDate — employment start date
 * @param {string|Date} [asOfDate] — calculate as of this date (default: today)
 * @param {string} leaveYearType — 'calendar' (Jan-Dec) or 'anniversary' (hire date)
 * @returns {{
 *   totalAccrued: number,    — total days accrued since start of leave year
 *   monthsOfService: number, — total months of service
 *   eligible: boolean,       — true if >= 6 months service
 *   entitlementPerYear: number, — 30 or pro-rata
 *   accrualPerMonth: number, — 2.5 or 2 depending on service
 *   leaveYearStart: string,  — start of current leave year
 *   leaveYearEnd: string,    — end of current leave year
 * }}
 */
export function calculateAnnualLeaveAccrual(startDate, asOfDate = new Date(), leaveYearType = 'calendar') {
  const start  = new Date(startDate);
  const asOf   = new Date(asOfDate);
  const period = servicePeriod(startDate, asOfDate);
  const totalMonths = period.years * 12 + period.months + (period.days > 0 ? period.days / 30 : 0);

  // Determine leave year boundaries
  let leaveYearStart, leaveYearEnd;
  if (leaveYearType === 'anniversary') {
    // Leave year runs from hire anniversary to next anniversary
    const thisYearAnniversary = new Date(asOf.getFullYear(), start.getMonth(), start.getDate());
    if (asOf >= thisYearAnniversary) {
      leaveYearStart = thisYearAnniversary;
      leaveYearEnd   = new Date(asOf.getFullYear() + 1, start.getMonth(), start.getDate() - 1);
    } else {
      leaveYearStart = new Date(asOf.getFullYear() - 1, start.getMonth(), start.getDate());
      leaveYearEnd   = new Date(asOf.getFullYear(), start.getMonth(), start.getDate() - 1);
    }
  } else {
    // Calendar year: Jan 1 – Dec 31
    leaveYearStart = new Date(asOf.getFullYear(), 0, 1);
    leaveYearEnd   = new Date(asOf.getFullYear(), 11, 31);
  }

  // Art. 29: < 6 months = not eligible
  if (totalMonths < 6) {
    return {
      totalAccrued: 0,
      monthsOfService: totalMonths,
      eligible: false,
      entitlementPerYear: 0,
      accrualPerMonth: 0,
      leaveYearStart: leaveYearStart.toISOString().split('T')[0],
      leaveYearEnd:   leaveYearEnd.toISOString().split('T')[0],
    };
  }

  // Art. 29: 6–12 months = 2 days/month; 12+ months = 2.5 days/month (30/yr)
  const accrualPerMonth     = totalMonths >= 12 ? 2.5 : 2;
  const entitlementPerYear  = totalMonths >= 12 ? 30 : 24;

  // Calculate months elapsed in current leave year
  const yearStartDate = new Date(leaveYearStart);
  const effectiveStart = start > yearStartDate ? start : yearStartDate;
  const msPerMonth = 1000 * 60 * 60 * 24 * 30.44;
  const monthsInYear = Math.max(0, (asOf - effectiveStart) / msPerMonth);

  const totalAccrued = Math.min(monthsInYear * accrualPerMonth, entitlementPerYear);

  return {
    totalAccrued: Math.round(totalAccrued * 100) / 100,
    monthsOfService: totalMonths,
    eligible: true,
    entitlementPerYear,
    accrualPerMonth,
    leaveYearStart: leaveYearStart.toISOString().split('T')[0],
    leaveYearEnd:   leaveYearEnd.toISOString().split('T')[0],
  };
}

// ── Sick Leave Tier Calculation ───────────────────────────────────────────────

/**
 * Calculate sick leave pay for a given number of sick days used in the current year.
 *
 * Art. 31 — UAE Federal Decree-Law No. 33 of 2021:
 *   First 15 days: full pay
 *   Next 30 days: half pay
 *   Next 45 days: unpaid
 *
 * @param {number} daysUsedSoFar — sick days already used this year (before this request)
 * @param {number} daysRequested — days in this request
 * @param {number} dailySalary   — basic salary / 30
 * @returns {{
 *   fullPayDays: number,
 *   halfPayDays: number,
 *   unpaidDays: number,
 *   totalDeduction: number, — amount to deduct from salary (half-pay and unpaid days)
 *   breakdown: string,
 * }}
 */
export function calculateSickLeavePay(daysUsedSoFar, daysRequested, dailySalary) {
  const FULL_PAY_LIMIT = 15;
  const HALF_PAY_LIMIT = 45; // 15 + 30
  const UNPAID_LIMIT   = 90; // 15 + 30 + 45

  let remaining = daysRequested;
  let fullPayDays = 0, halfPayDays = 0, unpaidDays = 0;

  // Full pay tier (days 1–15)
  if (daysUsedSoFar < FULL_PAY_LIMIT) {
    const available = FULL_PAY_LIMIT - daysUsedSoFar;
    const used = Math.min(remaining, available);
    fullPayDays += used;
    remaining   -= used;
  }

  // Half pay tier (days 16–45)
  if (remaining > 0 && daysUsedSoFar < HALF_PAY_LIMIT) {
    const available = HALF_PAY_LIMIT - Math.max(daysUsedSoFar, FULL_PAY_LIMIT);
    const used = Math.min(remaining, available);
    halfPayDays += used;
    remaining   -= used;
  }

  // Unpaid tier (days 46–90)
  if (remaining > 0) {
    unpaidDays = Math.min(remaining, UNPAID_LIMIT - Math.max(daysUsedSoFar, HALF_PAY_LIMIT));
  }

  // Deduction = half of daily salary for half-pay days + full daily salary for unpaid days
  const totalDeduction = (halfPayDays * dailySalary * 0.5) + (unpaidDays * dailySalary);

  return {
    fullPayDays,
    halfPayDays,
    unpaidDays,
    totalDeduction,
    breakdown: `${fullPayDays} full pay + ${halfPayDays} half pay + ${unpaidDays} unpaid`,
  };
}

// ── Leave Encashment ──────────────────────────────────────────────────────────

/**
 * Calculate annual leave encashment on termination/resignation.
 *
 * Art. 29 — UAE Federal Decree-Law No. 33 of 2021:
 * Employee is entitled to encashment of unused annual leave days on exit.
 * Encashment = unused days × (basic salary / 30)
 *
 * @param {number} unusedDays   — unused annual leave days
 * @param {number} basicSalary  — monthly basic salary in AED
 * @returns {{ unusedDays: number, dailyRate: number, encashmentAmount: number }}
 */
export function calculateLeaveEncashment(unusedDays, basicSalary) {
  const dailyRate = (parseFloat(basicSalary) || 0) / 30;
  const encashmentAmount = Math.max(0, unusedDays) * dailyRate;
  return {
    unusedDays: Math.max(0, unusedDays),
    dailyRate,
    encashmentAmount,
  };
}

// ── Payroll Leave Deduction Calculator ───────────────────────────────────────

/**
 * Calculate leave-related salary deductions for a payroll period.
 *
 * Covers:
 *   1. Approved UNPAID leave days overlapping the period → deduct (basic/30) × days
 *   2. Approved SICK leave at half-pay tier → deduct 50% of (basic/30) × half-pay days
 *   3. Approved SICK leave at unpaid tier → deduct (basic/30) × unpaid days
 *   4. Approved HAJJ leave (unpaid) → deduct (basic/30) × days
 *
 * @param {object[]} approvedLeaves — approved leave requests for this employee
 * @param {string} periodStart — 'YYYY-MM-DD' first day of payroll period
 * @param {string} periodEnd   — 'YYYY-MM-DD' last day of payroll period
 * @param {number} basicSalary — monthly basic salary in AED
 * @param {number} sickFullPayUsed — sick full-pay days already used this year
 * @returns {{
 *   unpaidLeaveDays: number,
 *   unpaidLeaveDeduction: number,
 *   sickHalfPayDays: number,
 *   sickHalfPayDeduction: number,
 *   sickUnpaidDays: number,
 *   sickUnpaidDeduction: number,
 *   totalDeduction: number,
 *   lineItems: Array<{label: string, days: number, amount: number}>,
 * }}
 */
export function calculatePayrollLeaveDeductions(approvedLeaves, periodStart, periodEnd, basicSalary, sickFullPayUsed = 0) {
  const daily  = (parseFloat(basicSalary) || 0) / 30;
  const pStart = new Date(periodStart);
  const pEnd   = new Date(periodEnd);
  pStart.setHours(0, 0, 0, 0);
  pEnd.setHours(0, 0, 0, 0);

  let unpaidLeaveDays  = 0;
  let sickHalfPayDays  = 0;
  let sickUnpaidDays   = 0;
  let runningSickUsed  = sickFullPayUsed;
  const lineItems      = [];

  for (const leave of (approvedLeaves || [])) {
    if (leave.status !== 'Approved') continue;

    const lStart = new Date(leave.startDate);
    const lEnd   = new Date(leave.endDate);
    lStart.setHours(0, 0, 0, 0);
    lEnd.setHours(0, 0, 0, 0);

    // Find overlap between leave period and payroll period
    const overlapStart = lStart > pStart ? lStart : pStart;
    const overlapEnd   = lEnd < pEnd ? lEnd : pEnd;
    if (overlapStart > overlapEnd) continue;

    const overlapDays = Math.round((overlapEnd - overlapStart) / (1000 * 60 * 60 * 24)) + 1;
    if (overlapDays <= 0) continue;

    if (leave.leaveTypeCode === 'UNPAID') {
      // Unpaid leave: deduct full daily rate × days
      unpaidLeaveDays += overlapDays;
      lineItems.push({
        label: `Unpaid Leave (${formatDateUAE(leave.startDate)} – ${formatDateUAE(leave.endDate)})`,
        days:  overlapDays,
        amount: overlapDays * daily,
      });
    } else if (leave.leaveTypeCode === 'HAJJ') {
      // Hajj leave is unpaid — Art. 29
      unpaidLeaveDays += overlapDays;
      lineItems.push({
        label: `Hajj Leave — Unpaid (Art. 29)`,
        days:  overlapDays,
        amount: overlapDays * daily,
      });
    } else if (leave.leaveTypeCode === 'SICK') {
      // Art. 31: apply tier calculation based on cumulative sick days used this year
      const tierResult = calculateSickLeavePay(runningSickUsed, overlapDays, daily);
      if (tierResult.halfPayDays > 0) {
        sickHalfPayDays += tierResult.halfPayDays;
        lineItems.push({
          label: `Sick Leave — Half Pay (Art. 31)`,
          days:  tierResult.halfPayDays,
          amount: tierResult.halfPayDays * daily * 0.5,
        });
      }
      if (tierResult.unpaidDays > 0) {
        sickUnpaidDays += tierResult.unpaidDays;
        lineItems.push({
          label: `Sick Leave — Unpaid (Art. 31)`,
          days:  tierResult.unpaidDays,
          amount: tierResult.unpaidDays * daily,
        });
      }
      runningSickUsed += overlapDays;
    }
  }

  const unpaidLeaveDeduction = unpaidLeaveDays * daily;
  const sickHalfPayDeduction = sickHalfPayDays * daily * 0.5;
  const sickUnpaidDeduction  = sickUnpaidDays * daily;
  const totalDeduction       = unpaidLeaveDeduction + sickHalfPayDeduction + sickUnpaidDeduction;

  return {
    unpaidLeaveDays,
    unpaidLeaveDeduction,
    sickHalfPayDays,
    sickHalfPayDeduction,
    sickUnpaidDays,
    sickUnpaidDeduction,
    totalDeduction,
    lineItems,
  };
}

// ── Compliance Validators ─────────────────────────────────────────────────────

/**
 * Validate a leave request against UAE compliance rules.
 * Returns an array of validation messages (empty = valid).
 *
 * @param {object} request — leave request object
 * @param {object} employee — employee record
 * @param {object} leaveType — leave type config
 * @param {object} balance — current leave balance for this type
 * @param {string[]} holidayDates — public holiday dates
 * @param {string} weekendDef
 * @returns {{ valid: boolean, errors: string[], warnings: string[] }}
 */
export function validateLeaveRequest(request, employee, leaveType, balance, holidayDates = [], weekendDef = 'fri-sat') {
  const errors   = [];
  const warnings = [];

  const startDate = new Date(request.startDate);
  const endDate   = new Date(request.endDate);
  const today     = new Date();
  today.setHours(0, 0, 0, 0);

  // Basic date validation
  if (endDate < startDate) {
    errors.push('End date cannot be before start date.');
  }

  // Probation eligibility — HR-configured per leave type
  if (employee.employmentStatus === 'Probation' && leaveType.probationEligible === false) {
    errors.push(`${leaveType.name} is not available during the probation period. Contact HR for exceptions.`);
  }

  // Art. 31 — Sick leave during probation: not entitled to paid sick leave
  if (leaveType.code === 'SICK' && employee.employmentStatus === 'Probation') {
    warnings.push('Art. 31: Employee is on probation. Sick leave during probation is unpaid. HR approval required.');
  }

  // Art. 29 — Annual leave: minimum 6 months service required
  if (leaveType.code === 'ANNUAL') {
    const period = servicePeriod(employee.startDate || employee.employmentStartDate, today);
    const totalMonths = period.years * 12 + period.months;
    if (totalMonths < 6) {
      errors.push('Art. 29: Employee has less than 6 months of service. Annual leave is not yet available.');
    }
    // Minimum notice period check
    const noticeDays = Math.ceil((startDate - today) / (1000 * 60 * 60 * 24));
    if (noticeDays < (leaveType.minNoticeDays || 0)) {
      warnings.push(`Annual leave requires ${leaveType.minNoticeDays} days notice. This request has ${noticeDays} days notice.`);
    }
  }

  // Art. 29 (Hajj) — Hajj leave: once per career, min 2 years service
  if (leaveType.code === 'HAJJ') {
    const period = servicePeriod(employee.startDate || employee.employmentStartDate, today);
    const totalMonths = period.years * 12 + period.months;
    if (totalMonths < 24) {
      errors.push('Art. 29 (Hajj): Employee must have at least 2 years of service for Hajj leave.');
    }
    if (employee.hajjLeaveTaken) {
      errors.push('Art. 29 (Hajj): Employee has already taken Hajj leave. This entitlement is once per career at the same employer.');
    }
  }

  // Art. 30 — Maternity leave: 1 year service for paid leave
  if (leaveType.code === 'MATERNITY') {
    const period = servicePeriod(employee.startDate || employee.employmentStartDate, today);
    const totalMonths = period.years * 12 + period.months;
    if (totalMonths < 12) {
      warnings.push('Art. 30: Employee has less than 1 year of service. Maternity leave will be unpaid. HR will be notified.');
    }
    if (employee.gender !== 'Female') {
      errors.push('Maternity leave is only available to female employees.');
    }
  }

  // Art. 32 — Paternity leave: within 6 months of birth
  if (leaveType.code === 'PATERNITY') {
    if (request.childBirthDate) {
      const birthDate = new Date(request.childBirthDate);
      const monthsSinceBirth = (startDate - birthDate) / (1000 * 60 * 60 * 24 * 30.44);
      if (monthsSinceBirth > 6) {
        errors.push('Art. 32: Paternity leave must be taken within 6 months of the child\'s birth date.');
      }
    }
    if (employee.gender !== 'Male') {
      errors.push('Paternity leave is only available to male employees.');
    }
  }

  // Mandatory attachment — enforced by the requiresAttachment flag set per leave type
  if (leaveType.requiresAttachment && !request.attachmentUrl) {
    const hint = ATTACHMENT_HINTS[leaveType.code] || 'supporting document';
    errors.push(`${leaveType.name} requires a ${hint}. Please upload before submitting.`);
  }

  // Bereavement — relationship required for correct duration
  if (leaveType.code === 'BEREAVEMENT' && !request.relationship) {
    errors.push('Bereavement leave requires the relationship to the deceased to be specified.');
  }

  // Balance check — warn if insufficient (do not block, manager decides)
  if (balance && !leaveType.isUnlimited) {
    const days = countLeaveDays(request.startDate, request.endDate, leaveType.dayCountType, holidayDates, weekendDef, request.isHalfDay);
    if (days > (balance.remaining || 0)) {
      warnings.push(`Insufficient leave balance. Requested: ${days} days. Available: ${balance.remaining || 0} days. Manager approval required.`);
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}

// ── Annual Leave Advance Pay Warning ─────────────────────────────────────────

/**
 * Check if an upcoming annual leave requires advance salary payment.
 *
 * Art. 29 — UAE Federal Decree-Law No. 33 of 2021:
 * Annual leave salary must be paid IN ADVANCE before the employee takes leave.
 * Flag payroll when leave of 7+ days is starting within 7 days.
 *
 * @param {object[]} approvedLeaves — array of approved leave requests
 * @param {string|Date} [asOfDate]
 * @returns {object[]} — leaves requiring advance pay flag
 */
export function getLeaveAdvancePayWarnings(approvedLeaves, asOfDate = new Date()) {
  const today = new Date(asOfDate);
  today.setHours(0, 0, 0, 0);

  return approvedLeaves.filter(leave => {
    if (leave.leaveTypeCode !== 'ANNUAL') return false;
    if (leave.status !== 'Approved') return false;
    const startDate = new Date(leave.startDate);
    const daysUntilStart = Math.ceil((startDate - today) / (1000 * 60 * 60 * 24));
    const duration = countCalendarDays(leave.startDate, leave.endDate);
    // Flag if leave is 7+ days and starts within 7 days
    return duration >= 7 && daysUntilStart >= 0 && daysUntilStart <= 7;
  });
}

// ── Leave Status Helpers ──────────────────────────────────────────────────────

export const LEAVE_STATUS = {
  PENDING:   'Pending',
  APPROVED:  'Approved',
  REJECTED:  'Rejected',
  CANCELLED: 'Cancelled',
  INFO_REQUESTED: 'Info Requested',
};

export const LEAVE_STATUS_COLORS = {
  Pending:          'badge-amber',
  Approved:         'badge-green',
  Rejected:         'badge-red',
  Cancelled:        'badge-gray',
  'Info Requested': 'badge-blue',
  ManagerApproved:  'badge-blue',
  ManagerRejected:  'badge-red',
};

/**
 * Get the display color for a leave type code.
 * @param {string} code
 * @returns {string} hex color
 */
export function getLeaveTypeColor(code) {
  const type = DEFAULT_LEAVE_TYPES.find(t => t.code === code);
  return type?.color || '#6b7280';
}

/**
 * Format a leave duration for display.
 * @param {number} days
 * @param {boolean} isHalfDay
 * @returns {string}
 */
export function formatLeaveDuration(days, isHalfDay = false) {
  if (isHalfDay) return '0.5 day';
  if (days === 1) return '1 day';
  return `${days} days`;
}