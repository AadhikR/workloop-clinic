/**
 * Canonical payroll calculation used by the editor, WPS, payslips, dashboards,
 * reports, and persistence. All monetary outputs are rounded to fils.
 */
const money = value => {
  const parsed = typeof value === 'number' ? value : parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const roundMoney = value => Math.round((value + Number.EPSILON) * 100) / 100;

const sumItems = items => (items || []).reduce((sum, item) => sum + money(item?.amount), 0);

export function calculatePayrollEntry(entry = {}) {
  const basicSalary       = money(entry.basicSalary);
  const housingAllowance  = money(entry.housingAllowance);
  const transportAllowance = money(entry.transportAllowance);
  const otherFixedAllowance = money(entry.allowance);
  const increment         = money(entry.increment);
  const bonus             = money(entry.bonus);
  const otherPay          = money(entry.otherPay);
  const additionalEarnings = sumItems(entry.additionalAllowances);
  const namedDeductions   = sumItems(entry.deductions);
  const leaveDeduction    = money(entry.leaveDeduction);
  const otherDirectDeduction = money(entry.duCost);

  const detailedAmount = housingAllowance + transportAllowance + otherFixedAllowance +
    increment + bonus + otherPay + additionalEarnings + namedDeductions +
    leaveDeduction + otherDirectDeduction;

  // Backward compatibility for historical/imported entries that only contain
  // basicSalary + variableAllowance and no itemised breakdown.
  const legacyVariableAmount = detailedAmount === 0 ? money(entry.variableAllowance) : 0;

  const fixedEarnings = basicSalary + housingAllowance + transportAllowance + otherFixedAllowance;
  const variableEarnings = increment + bonus + otherPay + additionalEarnings +
    Math.max(0, legacyVariableAmount);
  const grossEarnings = fixedEarnings + variableEarnings;
  const totalDeductions = namedDeductions + leaveDeduction + otherDirectDeduction +
    Math.max(0, -legacyVariableAmount);
  const netPay = grossEarnings - totalDeductions;

  return {
    basicSalary: roundMoney(basicSalary),
    housingAllowance: roundMoney(housingAllowance),
    transportAllowance: roundMoney(transportAllowance),
    otherFixedAllowance: roundMoney(otherFixedAllowance),
    increment: roundMoney(increment),
    bonus: roundMoney(bonus),
    otherPay: roundMoney(otherPay),
    additionalEarnings: roundMoney(additionalEarnings),
    fixedEarnings: roundMoney(fixedEarnings),
    variableEarnings: roundMoney(variableEarnings),
    grossEarnings: roundMoney(grossEarnings),
    namedDeductions: roundMoney(namedDeductions),
    leaveDeduction: roundMoney(leaveDeduction),
    otherDirectDeduction: roundMoney(otherDirectDeduction),
    totalDeductions: roundMoney(totalDeductions),
    netPay: roundMoney(netPay),
    // WPS EDR stores basic separately; this is the remaining transfer amount.
    wpsVariableAmount: roundMoney(netPay - basicSalary),
  };
}

export function calculatePayrollTotals(entries = []) {
  const active = entries.filter(entry => !entry.excluded);
  return active.reduce((totals, entry) => {
    const calc = calculatePayrollEntry(entry);
    totals.employeeCount += 1;
    totals.basicSalary += calc.basicSalary;
    totals.grossEarnings += calc.grossEarnings;
    totals.totalDeductions += calc.totalDeductions;
    totals.netPay += calc.netPay;
    totals.wpsVariableAmount += calc.wpsVariableAmount;
    return totals;
  }, {
    employeeCount: 0,
    basicSalary: 0,
    grossEarnings: 0,
    totalDeductions: 0,
    netPay: 0,
    wpsVariableAmount: 0,
  });
}

export function withCalculatedPayrollFields(entry) {
  const calc = calculatePayrollEntry(entry);
  return { ...entry, variableAllowance: calc.wpsVariableAmount };
}
