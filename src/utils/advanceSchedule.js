import { calculatePayrollEntry } from './payrollCalculator.js';

const money = value => {
  const parsed = typeof value === 'number' ? value : parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const roundMoney = value => Math.round((value + Number.EPSILON) * 100) / 100;

export function dateToMonth(dateStr) {
  return /^\d{4}-\d{2}/.test(String(dateStr || '')) ? String(dateStr).slice(0, 7) : '';
}

export function addMonths(period, offset) {
  if (!/^\d{4}-\d{2}$/.test(String(period || ''))) return '';
  const [year, month] = period.split('-').map(Number);
  const date = new Date(year, month - 1 + offset, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
}

export function monthDifference(fromPeriod, toPeriod) {
  if (!/^\d{4}-\d{2}$/.test(String(fromPeriod || '')) || !/^\d{4}-\d{2}$/.test(String(toPeriod || ''))) return -1;
  const [fromYear, fromMonth] = fromPeriod.split('-').map(Number);
  const [toYear, toMonth] = toPeriod.split('-').map(Number);
  return (toYear - fromYear) * 12 + (toMonth - fromMonth);
}

export function getFixedWpsCapacity(employee = {}) {
  return roundMoney(Math.max(0,
    money(employee.housingAllowance ?? employee.housing_allowance) +
    money(employee.transportAllowance ?? employee.transport_allowance) +
    money(employee.allowance),
  ));
}

export function createAdvancePlan({ amount, repaymentMonths, disbursedDate, repaymentStartMonth, employee }) {
  const total = roundMoney(Math.max(0, money(amount)));
  const requestedMonths = Math.max(1, parseInt(repaymentMonths) || 1);
  const startMonth = repaymentStartMonth || dateToMonth(disbursedDate);
  const fixedCapacity = getFixedWpsCapacity(employee);
  const requestedInstallment = roundMoney(total / requestedMonths);
  const monthlyDeduction = fixedCapacity > 0
    ? roundMoney(Math.min(requestedInstallment, fixedCapacity))
    : requestedInstallment;
  const effectiveMonths = monthlyDeduction > 0 ? Math.ceil(total / monthlyDeduction) : requestedMonths;

  return {
    startMonth,
    requestedMonths,
    effectiveMonths,
    monthlyDeduction,
    fixedWpsCapacity: fixedCapacity,
    extendedForWps: fixedCapacity > 0 && effectiveMonths > requestedMonths,
    requiresPayrollReview: fixedCapacity <= 0,
    endMonth: startMonth ? addMonths(startMonth, effectiveMonths - 1) : '',
  };
}

export function getAdvanceInstallmentForPeriod(advance, period) {
  if (!advance || advance.status !== 'active' || money(advance.outstandingBalance) <= 0) return 0;
  const startMonth = advance.repaymentStartMonth || dateToMonth(advance.disbursedDate);
  const offset = monthDifference(startMonth, period);
  const monthly = money(advance.monthlyDeduction);
  const months = Math.max(1, parseInt(advance.repaymentMonths) || 1);
  if (!startMonth || offset < 0 || offset >= months || monthly <= 0) return 0;
  return roundMoney(Math.min(monthly, money(advance.outstandingBalance)));
}

export function getAdvanceSchedule(advance) {
  const startMonth = advance?.repaymentStartMonth || dateToMonth(advance?.disbursedDate);
  const months = Math.max(1, parseInt(advance?.repaymentMonths) || 1);
  return Array.from({ length: months }, (_, index) => ({
    month: addMonths(startMonth, index),
    amount: roundMoney(Math.min(
      money(advance?.monthlyDeduction),
      Math.max(0, money(advance?.amount) - money(advance?.monthlyDeduction) * index),
    )),
  }));
}

export function getAdvanceProgress(advance, repayments = []) {
  const schedule = getAdvanceSchedule(advance);
  const paidPeriods = new Set(repayments.map(item => item.payrollPeriod || dateToMonth(item.paidDate)).filter(Boolean));
  const next = schedule.find(item => !paidPeriods.has(item.month) && item.amount > 0) || null;
  const repaidAmount = roundMoney(Math.max(0, money(advance?.amount) - money(advance?.outstandingBalance)));
  const progressPct = money(advance?.amount) > 0
    ? Math.min(100, (repaidAmount / money(advance.amount)) * 100)
    : 0;
  return { schedule, paidPeriods, next, repaidAmount, progressPct };
}

export function stageAdvancesForPayroll(advances, period, entry) {
  const entryWithoutAdvance = {
    ...entry,
    deductions: (entry?.deductions || []).filter(item => item.label !== 'Advance Repayment'),
  };
  let remainingWpsCapacity = Math.max(0, calculatePayrollEntry(entryWithoutAdvance).wpsVariableAmount);
  const staged = [];

  for (const advance of advances || []) {
    const scheduled = getAdvanceInstallmentForPeriod(advance, period);
    if (scheduled <= 0 || remainingWpsCapacity <= 0) continue;
    const amount = roundMoney(Math.min(scheduled, remainingWpsCapacity));
    if (amount <= 0) continue;
    staged.push({ advance, amount, scheduledAmount: scheduled, cappedForWps: amount < scheduled });
    remainingWpsCapacity = roundMoney(remainingWpsCapacity - amount);
  }

  return {
    staged,
    total: roundMoney(staged.reduce((sum, item) => sum + item.amount, 0)),
    remainingWpsCapacity,
  };
}
