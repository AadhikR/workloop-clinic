/**
 * gratuityCalculator.js — UAE End-of-Service Benefit (EOSB / Gratuity) Calculator
 *
 * Based on UAE Labour Law (Federal Decree-Law No. 33 of 2021) Article 51:
 *
 * Eligibility:
 *   - Less than 1 year of service: NO gratuity
 *   - 1 to 5 years: 21 calendar days' basic salary per year of service
 *   - More than 5 years: 30 calendar days' basic salary per year for each year beyond 5
 *     (the first 5 years still accrue at 21 days/year)
 *
 * Cap: Total gratuity cannot exceed 2 years' total basic salary (Article 51 cap).
 *
 * Pro-rata: Partial years beyond the first year are calculated proportionally.
 *
 * Note: Gratuity is based on BASIC SALARY only (not allowances).
 *
 * Under Federal Decree-Law No. 33 of 2021 (effective Feb 2022):
 *   Both resignation and termination receive full gratuity after 1 year of service.
 */

/**
 * Calculate the exact service period between two dates using calendar arithmetic.
 * Returns { years, months, days, totalYears (decimal) }
 *
 * Uses the same method as UAE MOHRE: count complete years, then complete months,
 * then remaining days — all based on calendar dates, not 365.25-day approximation.
 *
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @returns {{ years: number, months: number, days: number, totalYears: number }}
 */
export function servicePeriod(startDate, endDate = new Date()) {
  const s = new Date(startDate);
  // UAE gratuity: the last working day (termination date) is included in the service period.
  // Add 1 day to the end date so that e.g. 01/01/2020 → 01/01/2026 = 6 Years, 0 Months, 1 Days
  // which is the correct UAE MOHRE calculation (inclusive of last day).
  const eRaw = new Date(endDate);
  const e = new Date(eRaw);
  e.setDate(e.getDate() + 1);

  if (isNaN(s.getTime()) || isNaN(e.getTime()) || eRaw < s) {
    return { years: 0, months: 0, days: 0, totalYears: 0 };
  }

  let years  = e.getFullYear() - s.getFullYear();
  let months = e.getMonth()    - s.getMonth();
  let days   = e.getDate()     - s.getDate();

  // Borrow from months if days are negative
  if (days < 0) {
    months--;
    // Days in the previous month relative to end date
    const prevMonth = new Date(e.getFullYear(), e.getMonth(), 0);
    days += prevMonth.getDate();
  }

  // Borrow from years if months are negative
  if (months < 0) {
    years--;
    months += 12;
  }

  // Total years as a decimal for calculation purposes
  // Use the exact calendar difference in days / 365.0 for pro-rata
  // (e already has +1 day added for inclusive last-day counting)
  const msPerDay = 1000 * 60 * 60 * 24;
  const totalDays = Math.round((e - s) / msPerDay);
  const totalYears = totalDays / 365.0;

  return { years, months, days, totalYears };
}

/**
 * Legacy helper — returns decimal years (kept for backward compat).
 * @param {string|Date} startDate
 * @param {string|Date} endDate
 * @returns {number}
 */
export function yearsOfService(startDate, endDate = new Date()) {
  return servicePeriod(startDate, endDate).totalYears;
}

/**
 * Calculate accrued EOSB (gratuity) for an employee.
 *
 * Uses calendar-accurate service period. Gratuity tiers:
 *   - < 1 year: not eligible
 *   - 1–5 years: 21 days basic per year (pro-rata for partial year)
 *   - > 5 years: first 5yr at 21 days/yr + beyond 5yr at 30 days/yr (pro-rata)
 * Cap: 2 years' basic salary (24 months).
 *
 * @param {number} basicSalaryAED   — current monthly basic salary in AED
 * @param {string|Date} startDate   — employment start date
 * @param {string|Date} [endDate]   — calculation date (defaults to today)
 * @returns {{
 *   years: number,           — complete years of service
 *   months: number,          — remaining months
 *   days: number,            — remaining days
 *   totalYears: number,      — total service as decimal
 *   eligible: boolean,
 *   dailyRate: number,       — basic salary / 30
 *   gratuityRaw: number,     — calculated gratuity before cap (AED)
 *   gratuityCapped: number,  — gratuity after 2-year cap (AED)
 *   cap: number,             — 2-year basic salary cap (AED)
 *   breakdown: string,
 *   capped: boolean,
 *   serviceLabel: string,    — e.g. "6 Years, 0 Months, 1 Days"
 * }}
 */
export function calculateGratuity(basicSalaryAED, startDate, endDate = new Date()) {
  const basic  = parseFloat(basicSalaryAED) || 0;
  const period = servicePeriod(startDate, endDate);
  const { years, months, days, totalYears } = period;

  const serviceLabel = `${years} Year${years !== 1 ? 's' : ''}, ${months} Month${months !== 1 ? 's' : ''}, ${days} Day${days !== 1 ? 's' : ''}`;

  if (totalYears < 1) {
    return {
      years, months, days, totalYears,
      eligible: false,
      dailyRate: basic / 30,
      gratuityRaw: 0,
      gratuityCapped: 0,
      cap: basic * 24,
      breakdown: `Less than 1 year of service — no gratuity entitlement. (${serviceLabel})`,
      capped: false,
      serviceLabel,
    };
  }

  // Daily rate = basic / 30 (UAE standard: 30-day month for gratuity)
  const dailyRate = basic / 30;

  let gratuity = 0;
  let breakdown = '';

  if (totalYears <= 5) {
    // 21 days per year (pro-rata for partial year beyond first complete year)
    gratuity = dailyRate * 21 * totalYears;
    breakdown = `${totalYears.toFixed(4)} yrs × 21 days × AED ${dailyRate.toFixed(2)}/day`;
  } else {
    // First 5 years: 21 days/year
    const first5 = dailyRate * 21 * 5;
    // Beyond 5 years: 30 days/year (pro-rata)
    const beyond = dailyRate * 30 * (totalYears - 5);
    gratuity = first5 + beyond;
    breakdown = `5 yrs × 21 days + ${(totalYears - 5).toFixed(4)} yrs × 30 days × AED ${dailyRate.toFixed(2)}/day`;
  }

  // Cap: 2 years' basic salary = 24 months
  const cap = basic * 24;
  const gratuityCapped = Math.min(gratuity, cap);

  return {
    years, months, days, totalYears,
    eligible: true,
    dailyRate,
    gratuityRaw: gratuity,
    gratuityCapped,
    cap,
    breakdown,
    capped: gratuity > cap,
    serviceLabel,
  };
}

/**
 * Calculate end-of-service settlement when an employee leaves.
 *
 * @param {object} employee — employee record with basicSalary, startDate, housingAllowance, transportAllowance, etc.
 * @param {string} terminationDate — YYYY-MM-DD
 * @param {number} [outstandingAdvances] — any salary advances to deduct (AED)
 * @returns {object} full settlement breakdown
 */
export function calculateEndOfService(employee, terminationDate, outstandingAdvances = 0) {
  const termDate  = new Date(terminationDate);
  const startDate = new Date(employee.startDate || employee.employmentStartDate);

  // Days worked in final month (pro-rata final salary)
  const lastDayOfMonth = new Date(termDate.getFullYear(), termDate.getMonth() + 1, 0).getDate();
  const daysWorked  = termDate.getDate();
  const daysInMonth = lastDayOfMonth;

  const basicSalary        = parseFloat(employee.basicSalary) || 0;
  const housingAllowance   = parseFloat(employee.housingAllowance) || 0;
  const transportAllowance = parseFloat(employee.transportAllowance) || 0;
  const otherAllowances    = parseFloat(employee.otherAllowances) || 0;
  const totalMonthly       = basicSalary + housingAllowance + transportAllowance + otherAllowances;

  // Pro-rata final salary
  const proRataFinalSalary = (totalMonthly / daysInMonth) * daysWorked;

  // Gratuity
  const gratuityResult = calculateGratuity(basicSalary, startDate, termDate);

  // Total settlement
  const totalGross = proRataFinalSalary + gratuityResult.gratuityCapped;
  const totalNet   = totalGross - (parseFloat(outstandingAdvances) || 0);

  return {
    employee:          employee.name,
    startDate:         startDate.toISOString().split('T')[0],
    terminationDate,
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
