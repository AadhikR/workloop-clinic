/**
 * gratuityCalculator.js — UAE End-of-Service Benefit (EOSB / Gratuity) Calculator
 *
 * Based on UAE Labour Law (Federal Decree-Law No. 33 of 2021) and MOHRE guidelines.
 *
 * ── FORMULA ──────────────────────────────────────────────────────────────────
 * Daily wage = Basic Salary ÷ 30
 *
 * Gratuity tiers (based on years of service):
 *   < 1 year:   No gratuity
 *   1–5 years:  21 days' basic salary per year of service
 *   > 5 years:  30 days' basic salary per year of service (for ALL years, not just beyond 5)
 *               i.e. if service = 6 years: 30 × 6 years × daily rate
 *
 * Cap: Total gratuity cannot exceed 2 years' basic salary (24 months).
 *
 * ── RESIGNATION PARTIAL ENTITLEMENT ─────────────────────────────────────────
 * When the employee RESIGNS (not terminated):
 *   1–3 years:  1/3 of full gratuity
 *   3–5 years:  2/3 of full gratuity
 *   > 5 years:  Full gratuity
 *
 * When TERMINATED (without misconduct): Full gratuity always.
 *
 * ── SERVICE PERIOD ───────────────────────────────────────────────────────────
 * The last working day (termination date) is INCLUDED in the service period.
 * Service is displayed as "X Years, Y Months, Z Days".
 *
 * ── CONTRACT TYPE ────────────────────────────────────────────────────────────
 * Limited and Unlimited contracts both follow the same gratuity formula.
 * Resignation partial entitlement applies to both.
 *
 * ── NOTES ────────────────────────────────────────────────────────────────────
 * - Only BASIC SALARY counts. Allowances are excluded.
 * - DIFC and ADGM follow separate employment regulations.
 * - Gratuity can be denied only for gross misconduct (Article 120).
 */

/**
 * Calculate the exact service period between two dates using calendar arithmetic.
 * The last working day (endDate) is INCLUDED (adds 1 day before calculating).
 *
 * @param {string|Date} startDate
 * @param {string|Date} endDate  — last working day (inclusive)
 * @returns {{ years: number, months: number, days: number, totalYears: number, serviceLabel: string }}
 */
export function servicePeriod(startDate, endDate = new Date()) {
  const s    = new Date(startDate);
  const eRaw = new Date(endDate);

  if (isNaN(s.getTime()) || isNaN(eRaw.getTime()) || eRaw < s) {
    return { years: 0, months: 0, days: 0, totalYears: 0, serviceLabel: '0 Years, 0 Months, 0 Days' };
  }

  // Include the last working day by adding 1 day to end date
  const e = new Date(eRaw);
  e.setDate(e.getDate() + 1);

  let years  = e.getFullYear() - s.getFullYear();
  let months = e.getMonth()    - s.getMonth();
  let days   = e.getDate()     - s.getDate();

  // Borrow from months if days are negative
  if (days < 0) {
    months--;
    const prevMonth = new Date(e.getFullYear(), e.getMonth(), 0);
    days += prevMonth.getDate();
  }

  // Borrow from years if months are negative
  if (months < 0) {
    years--;
    months += 12;
  }

  // Total years as decimal for calculation (use exact day count / 365)
  const msPerDay   = 1000 * 60 * 60 * 24;
  const totalDays  = Math.round((e - s) / msPerDay);
  const totalYears = totalDays / 365.0;

  const serviceLabel = `${years} Year${years !== 1 ? 's' : ''}, ${months} Month${months !== 1 ? 's' : ''}, ${days} Day${days !== 1 ? 's' : ''}`;

  return { years, months, days, totalYears, serviceLabel };
}

/**
 * Legacy helper — returns decimal years.
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @returns {number}
 */
export function yearsOfService(startDate, endDate = new Date()) {
  return servicePeriod(startDate, endDate).totalYears;
}

/**
 * Calculate the FULL gratuity entitlement (before resignation reduction).
 *
 * Formula:
 *   Daily rate = basic / 30
 *   1–5 years:  21 days × years × daily rate
 *   > 5 years:  30 days × years × daily rate  (ALL years at 30 days)
 *
 * @param {number} basicSalaryAED
 * @param {number} totalYears — decimal years of service
 * @returns {{ gratuityFull: number, breakdown: string, dailyRate: number }}
 */
/**
 * Convert a service period (years, months, days) to a decimal year value
 * using the standard UAE gratuity convention:
 *   1 year = 12 months = 365 days
 *   months are counted as 1/12 of a year
 *   remaining days are counted as days/365
 *
 * This avoids floating-point drift from raw millisecond division.
 */
function periodToDecimalYears(years, months, days) {
  return years + (months / 12) + (days / 365);
}

function computeFullGratuity(basicSalaryAED, totalYears, years, months, days) {
  const basic     = parseFloat(basicSalaryAED) || 0;
  const dailyRate = basic / 30;
  let gratuityFull = 0;
  let breakdown    = '';

  if (totalYears < 1) {
    return { gratuityFull: 0, breakdown: 'Less than 1 year — not eligible', dailyRate };
  }

  if (totalYears <= 5) {
    // 1–5 years: 21 days per year (pro-rata using calendar components)
    const decYears = periodToDecimalYears(years, months, days);
    gratuityFull   = dailyRate * 21 * decYears;
    breakdown      = `${decYears.toFixed(4)} yrs × 21 days × AED ${dailyRate.toFixed(2)}/day`;
  } else {
    // > 5 years:
    //   First 5 complete years at 21 days/year = fixed amount
    //   Remaining period (years-5, months, days) at 30 days/year
    const first5 = dailyRate * 21 * 5;

    // Calculate the "beyond 5 years" portion using calendar components
    // Subtract 5 complete years from the service period
    const beyondYears  = years - 5;   // complete years beyond 5
    const beyondDec    = periodToDecimalYears(beyondYears, months, days);
    const beyond       = dailyRate * 30 * beyondDec;

    gratuityFull = first5 + beyond;
    breakdown    = `(5 yrs × 21 days) + (${beyondDec.toFixed(4)} yrs × 30 days) × AED ${dailyRate.toFixed(2)}/day`;
  }

  return { gratuityFull, breakdown, dailyRate };
}

/**
 * Calculate accrued EOSB (gratuity) for an employee.
 *
 * @param {number} basicSalaryAED   — current monthly basic salary in AED
 * @param {string|Date} startDate   — employment start date
 * @param {string|Date} [endDate]   — last working day (defaults to today)
 * @param {'Termination'|'Resignation'} [reason] — reason for leaving (default: Termination)
 * @param {'Limited'|'Unlimited'} [contractType] — contract type (default: Unlimited)
 * @returns {{
 *   years: number, months: number, days: number, totalYears: number, serviceLabel: string,
 *   eligible: boolean,
 *   dailyRate: number,
 *   gratuityFull: number,     — full entitlement before resignation reduction
 *   reductionFactor: number,  — 1 = full, 2/3, 1/3
 *   reductionLabel: string,   — e.g. "1/3 (resignation, 1–3 years)"
 *   gratuityRaw: number,      — after reduction, before cap
 *   gratuityCapped: number,   — after 2-year cap
 *   cap: number,
 *   breakdown: string,
 *   capped: boolean,
 * }}
 */
export function calculateGratuity(
  basicSalaryAED,
  startDate,
  endDate = new Date(),
  reason = 'Termination',
  contractType = 'Unlimited'
) {
  const basic  = parseFloat(basicSalaryAED) || 0;
  const period = servicePeriod(startDate, endDate);
  const { years, months, days, totalYears, serviceLabel } = period;

  if (totalYears < 1) {
    return {
      years, months, days, totalYears, serviceLabel,
      eligible: false,
      dailyRate: basic / 30,
      gratuityFull: 0,
      reductionFactor: 0,
      reductionLabel: 'Not eligible (< 1 year)',
      gratuityRaw: 0,
      gratuityCapped: 0,
      cap: basic * 24,
      breakdown: `Less than 1 year of service — no gratuity entitlement. (${serviceLabel})`,
      capped: false,
    };
  }

  const { gratuityFull, breakdown, dailyRate } = computeFullGratuity(basic, totalYears, years, months, days);

  // ── Resignation partial entitlement ──────────────────────────────────────
  // Termination without misconduct = full gratuity always
  // Resignation:
  //   1–3 years: 1/3
  //   3–5 years: 2/3
  //   > 5 years: full
  let reductionFactor = 1;
  let reductionLabel  = 'Full entitlement (termination)';

  const isResignation = reason === 'Resignation';
  if (isResignation) {
    if (totalYears < 3) {
      reductionFactor = 1 / 3;
      reductionLabel  = '1/3 entitlement (resignation, 1–3 years service)';
    } else if (totalYears < 5) {
      reductionFactor = 2 / 3;
      reductionLabel  = '2/3 entitlement (resignation, 3–5 years service)';
    } else {
      reductionFactor = 1;
      reductionLabel  = 'Full entitlement (resignation, > 5 years service)';
    }
  }

  const gratuityRaw    = gratuityFull * reductionFactor;
  const cap            = basic * 24; // 2 years' basic salary
  const gratuityCapped = Math.min(gratuityRaw, cap);

  return {
    years, months, days, totalYears, serviceLabel,
    eligible: true,
    dailyRate,
    gratuityFull,
    reductionFactor,
    reductionLabel,
    gratuityRaw,
    gratuityCapped,
    cap,
    breakdown,
    capped: gratuityRaw > cap,
  };
}

/**
 * Calculate end-of-service settlement when an employee leaves.
 *
 * @param {object} employee — employee record
 * @param {string} terminationDate — YYYY-MM-DD (last working day)
 * @param {number} [outstandingAdvances] — salary advances to deduct (AED)
 * @param {'Termination'|'Resignation'} [reason]
 * @returns {object} full settlement breakdown
 */
export function calculateEndOfService(
  employee,
  terminationDate,
  outstandingAdvances = 0,
  reason = 'Termination'
) {
  const termDate  = new Date(terminationDate);
  const startDate = new Date(employee.startDate || employee.employmentStartDate);

  // Days worked in final month (pro-rata final salary)
  const lastDayOfMonth = new Date(termDate.getFullYear(), termDate.getMonth() + 1, 0).getDate();
  const daysWorked     = termDate.getDate();
  const daysInMonth    = lastDayOfMonth;

  const basicSalary        = parseFloat(employee.basicSalary) || 0;
  const housingAllowance   = parseFloat(employee.housingAllowance) || 0;
  const transportAllowance = parseFloat(employee.transportAllowance) || 0;
  const otherAllowances    = parseFloat(employee.otherAllowances) || 0;
  const totalMonthly       = basicSalary + housingAllowance + transportAllowance + otherAllowances;

  // Pro-rata final salary
  const proRataFinalSalary = (totalMonthly / daysInMonth) * daysWorked;

  // Gratuity
  const contractType   = employee.contractType || 'Unlimited';
  const gratuityResult = calculateGratuity(basicSalary, startDate, termDate, reason, contractType);

  // Total settlement
  const totalGross = proRataFinalSalary + gratuityResult.gratuityCapped;
  const totalNet   = totalGross - (parseFloat(outstandingAdvances) || 0);

  return {
    employee:          employee.name,
    startDate:         startDate.toISOString().split('T')[0],
    terminationDate,
    reason,
    contractType,
    yearsOfService:    gratuityResult.totalYears,
    serviceLabel:      gratuityResult.serviceLabel,
    basicSalary,
    housingAllowance,
    transportAllowance,
    otherAllowances,
    totalMonthly,
    daysWorked,
    daysInMonth,
    proRataFinalSalary,
    gratuity:          gratuityResult,
    outstandingAdvances: parseFloat(outstandingAdvances) || 0,
    totalGross,
    totalNet,
  };
}
