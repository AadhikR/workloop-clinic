import { calculatePayrollEntry } from './payrollCalculator.js';
import { validateBankRoutingCode, validateIBAN, validateMolId } from './uaeValidators.js';
import { getSifComplianceIssues } from './sifCompliance.js';

const issue = (severity, code, message, employeeId = null) => ({ severity, code, message, employeeId });

export function validatePayrollRun({ entries = [], employees = [], company, meta = {}, period, attendanceClosed }) {
  const issues = [];
  const activeEntries = entries.filter(entry => !entry.excluded);
  const seenEmployees = new Set();
  const [year, month] = String(period || '').split('-').map(Number);
  const periodStart = year && month ? `${year}-${String(month).padStart(2, '0')}-01` : '';
  const periodEnd = year && month
    ? `${year}-${String(month).padStart(2, '0')}-${String(new Date(year, month, 0).getDate()).padStart(2, '0')}`
    : '';

  if (!company?.molEmployerId) issues.push(issue('error', 'company_mol', 'Company MOL Employer ID is missing.'));
  if (!meta.paymentDate) issues.push(issue('error', 'payment_date', 'Payment date is required.'));
  const companyRouting = validateBankRoutingCode(meta.scrBankRoutingCode);
  if (!meta.scrBankRoutingCode || !companyRouting.valid) {
    issues.push(issue('error', 'company_routing', companyRouting.message || 'SCR bank routing code is required.'));
  }
  if (!activeEntries.length) issues.push(issue('error', 'no_employees', 'Include at least one employee in payroll.'));
  if (attendanceClosed === false) issues.push(issue('error', 'attendance_open', 'Close the attendance period before submitting payroll.'));
  if (attendanceClosed == null) issues.push(issue('warning', 'attendance_unavailable', 'Attendance status could not be verified.'));

  issues.push(...getSifComplianceIssues({
    entries: activeEntries,
    employees,
    paymentDate: meta.paymentDate,
  }));

  for (const entry of activeEntries) {
    const emp = employees.find(employee => employee.id === entry.employeeId);
    if (!emp) {
      issues.push(issue('error', 'employee_missing', 'A payroll entry has no matching employee record.', entry.employeeId));
      continue;
    }
    if (seenEmployees.has(entry.employeeId)) {
      issues.push(issue('error', 'duplicate_employee', `${emp.name} appears more than once.`, entry.employeeId));
    }
    seenEmployees.add(entry.employeeId);

    const mol = validateMolId(emp.molId);
    if (!mol.valid) issues.push(issue('error', 'mol_id', `${emp.name}: ${mol.message}`, entry.employeeId));
    const iban = validateIBAN(emp.iban);
    if (!iban.valid) issues.push(issue('error', 'iban', `${emp.name}: ${iban.message}`, entry.employeeId));
    const routing = validateBankRoutingCode(emp.bankRoutingCode);
    if (!emp.bankRoutingCode || !routing.valid) {
      issues.push(issue('error', 'employee_routing', `${emp.name}: ${routing.message || 'Bank routing code is required'}`, entry.employeeId));
    }

    const calc = calculatePayrollEntry(entry);
    if (calc.basicSalary <= 0) issues.push(issue('error', 'basic_salary', `${emp.name}: Basic salary must be greater than zero.`, entry.employeeId));
    if (calc.netPay <= 0) issues.push(issue('error', 'net_pay', `${emp.name}: Net pay must be greater than zero.`, entry.employeeId));
    if (calc.wpsVariableAmount < 0) {
      issues.push(issue('error', 'negative_wps_allowance', `${emp.name}: Deductions reduce pay below basic salary, which creates a negative WPS allowance.`, entry.employeeId));
    }
    if (calc.totalDeductions > calc.grossEarnings) {
      issues.push(issue('error', 'deductions_exceed_gross', `${emp.name}: Deductions exceed gross earnings.`, entry.employeeId));
    }
    if (emp.employmentStartDate && periodEnd && emp.employmentStartDate > periodEnd) {
      issues.push(issue('error', 'not_joined', `${emp.name}: Employment starts after this payroll period.`, entry.employeeId));
    }
    if (emp.terminationDate && periodStart && emp.terminationDate < periodStart) {
      issues.push(issue('error', 'already_terminated', `${emp.name}: Employment ended before this payroll period.`, entry.employeeId));
    }
  }

  const byEmployee = {};
  for (const current of issues) {
    if (!current.employeeId) continue;
    if (!byEmployee[current.employeeId]) byEmployee[current.employeeId] = [];
    byEmployee[current.employeeId].push(current);
  }

  return {
    issues,
    errors: issues.filter(current => current.severity === 'error'),
    warnings: issues.filter(current => current.severity === 'warning'),
    byEmployee,
    ready: issues.every(current => current.severity !== 'error'),
  };
}
