/**
 * gratuityCalculator.js — UAE End-of-Service Benefit (EOSB / Gratuity) Calculator
 *
 * Based on UAE Labour Law (Federal Law No. 33 of 2021) Article 51:
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
 * Resignation vs Termination:
 *   Under the new law (2022+), both resignation and termination receive full gratuity
 *   after 1 year of service. The old partial-gratuity-on-resignation rules no longer apply
 *   under Federal Decree-Law No. 33 of 2021.
 */

/**
 * Calculate years of service (decimal) between two dates.
 * @param {string|Date} startDate
 * @param {string|Date} endDate  — defaults to today
 * @returns {number} years (decimal)
 */
export function yearsOfService(startDate, endDate = new Date()) {
  const start = new Date(startDate);
  const end   = new Date(endDate);
  if (isNaN(start.getTime())) return 0;
  const msPerYear = 365.25 * 24 * 60 * 60 * 1000;
  return Math.max(0, (end - start) / msPerYear);
}

/**
 * Calculate accrued EOSB (gratuity) for an employee.
 *
 * @param {number} basicSalaryAED   — current monthly basic salary in AED
 * @param {string|Date} startDate   — employment start date
 * @param {string|Date} [endDate]   — calculation date (defaults to today)
 * @returns {{
 *   years: number,           — total years of service (decimal)
 *   fullYears: number,       — complete years
 *   eligible: boolean,       — true if >= 1 year
 *   dailyRate: number,       — basic salary / 30 (AED per day)
 *   gratuityRaw: number,     — calculated gratuity before cap (AED)
 *   gratuityCapped: number,  — gratuity after 2-year cap (AED)
 *   cap: number,             — 2-year basic salary cap (AED)
 *   breakdown: string,       — human-readable breakdown
 * }}
 */
export function calculateGratuity(basicSalaryAED, startDate, endDate = new Date()) {
  const basic  = parseFloat(basicSalaryAED) || 0;
  const years  = yearsOfService(startDate, endDate);
  const fullYears = Math.floor(years);

  if (years < 1) {
    return {
      years,
      fullYears,
      eligible: false,
      dailyRate: basic / 30,
      gratuityRaw: 0,
      gratuityCapped: 0,
      cap: basic * 24,
      breakdown: 'Less than 1 year of service — no gratuity entitlement.',
    };
  }

  // Daily rate = basic / 30 (UAE standard: 30-day month for gratuity)
  const dailyRate = basic / 30;

  let gratuity = 0;
  let breakdown = '';

  if (years <= 5) {
    // 21 days per year (pro-rata for partial year)
    gratuity = dailyRate * 21 * years;
    breakdown = `${years.toFixed(2)} yrs × 21 days × AED ${dailyRate.toFixed(2)}/day`;
  } else {
    // First 5 years: 21 days/year
    const first5 = dailyRate * 21 * 5;
    // Beyond 5 years: 30 days/year (pro-rata)
    const beyond = dailyRate * 30 * (years - 5);
    gratuity = first5 + beyond;
    breakdown = `5 yrs × 21 days + ${(years - 5).toFixed(2)} yrs × 30 days × AED ${dailyRate.toFixed(2)}/day`;
  }

  // Cap: 2 years' basic salary = 24 months
  const cap = basic * 24;
  const gratuityCapped = Math.min(gratuity, cap);

  return {
    years,
    fullYears,
    eligible: true,
    dailyRate,
    gratuityRaw: gratuity,
    gratuityCapped,
    cap,
    breakdown,
    capped: gratuity > cap,
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
  const termDate = new Date(terminationDate);
  const startDate = new Date(employee.startDate || employee.employmentStartDate);

  // Days worked in final month (pro-rata final salary)
  const lastDayOfMonth = new Date(termDate.getFullYear(), termDate.getMonth() + 1, 0).getDate();
  const daysWorked = termDate.getDate();
  const daysInMonth = lastDayOfMonth;

  const basicSalary      = parseFloat(employee.basicSalary) || 0;
  const housingAllowance = parseFloat(employee.housingAllowance) || 0;
  const transportAllowance = parseFloat(employee.transportAllowance) || 0;
  const otherAllowances  = parseFloat(employee.otherAllowances) || 0;
  const totalMonthly     = basicSalary + housingAllowance + transportAllowance + otherAllowances;

  // Pro-rata final salary
  const proRataFinalSalary = (totalMonthly / daysInMonth) * daysWorked;

  // Gratuity
  const gratuityResult = calculateGratuity(basicSalary, startDate, termDate);

  // Total settlement
  const totalGross = proRataFinalSalary + gratuityResult.gratuityCapped;
  const totalNet   = totalGross - (parseFloat(outstandingAdvances) || 0);

  return {
    employee: employee.name,
    startDate: startDate.toISOString().split('T')[0],
    terminationDate,
    yearsOfService: gratuityResult.years,
    basicSalary,
    housingAllowance,
    transportAllowance,
    otherAllowances,
    totalMonthly,
    daysWorked,
    daysInMonth,
    proRataFinalSalary,
    gratuity: gratuityResult,
    outstandingAdvances: parseFloat(outstandingAdvances) || 0,
    totalGross,
    totalNet,
  };
}
