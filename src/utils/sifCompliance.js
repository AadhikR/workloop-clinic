const UAE_NATIONALITY = 'United Arab Emirates';

function formatDate(dateStr) {
  if (!dateStr) return 'unknown date';
  const [year, month, day] = dateStr.split('-');
  return year && month && day ? `${day}/${month}/${year}` : dateStr;
}

function expired(dateStr, asOfDate) {
  return Boolean(dateStr && asOfDate && dateStr < asOfDate);
}

/**
 * Return employee compliance reminders for an SIF transfer.
 * Expiry is assessed against the payroll payment date, not the browser date.
 */
export function getSifComplianceIssues({ entries = [], employees = [], paymentDate }) {
  const issues = [];
  const activeEntries = entries.filter(entry => !entry.excluded);

  for (const entry of activeEntries) {
    const employee = employees.find(current => current.id === entry.employeeId);
    if (!employee) continue;

    const addExpiry = (code, document, dateStr) => {
      if (!expired(dateStr, paymentDate)) return;
      issues.push({
        severity: 'warning',
        code,
        employeeId: employee.id,
        employeeName: employee.name,
        document,
        expiryDate: dateStr,
        message: `${employee.name}: ${document} expired on ${formatDate(dateStr)}. Review and update the employee record as soon as possible.`,
      });
    };

    if (employee.nationality !== UAE_NATIONALITY) {
      addExpiry('visa_expired', 'Residence visa', employee.visaExpiry);
    }
    addExpiry('emirates_id_expired', 'Emirates ID', employee.emiratesIdExpiry);
    addExpiry('labour_card_expired', 'Labour card / work permit', employee.labourCardExpiry);
    addExpiry('passport_expired', 'Passport', employee.passportExpiry);
    if (employee.licenceAuthority && employee.licenceAuthority !== 'None') {
      addExpiry('professional_licence_expired', `${employee.licenceAuthority} professional licence`, employee.licenceExpiry);
    }
  }

  return issues;
}
