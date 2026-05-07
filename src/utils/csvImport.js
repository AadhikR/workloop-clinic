import Papa from 'papaparse';

/**
 * Parse the salary CSV file format used by this company.
 * Columns (0-indexed):
 * 0: No, 1: Month, 2: Name, 3: Labor card No (MOL ID),
 * 4: Bank, 5: Bank/Routing code, 6: Bank Account No (IBAN),
 * 7: Basic, 8: Allowance, 9: Increment, 10: Bonus/Incentive,
 * 11: Other pay, 12: DU Deduction, 13: Salary Deduction,
 * 14: Loan Deduction, 15: Other Deduction,
 * 16: WPS BASIC, 17: WPS ALLOW, 18: TOTAL
 */

// Strip thousand-separator commas and parse as float
function parseNum(val) {
  if (val === undefined || val === null) return 0;
  return parseFloat(String(val).replace(/,/g, '').trim()) || 0;
}

export function parseCSV(fileContent) {
  const result = Papa.parse(fileContent, {
    skipEmptyLines: false,
    header: false,
  });

  const rows = result.data;
  const employees = [];
  const payrollEntries = [];

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const empNo = row[0]?.toString().trim();
    const molId = row[3]?.toString().trim();
    const name = row[2]?.toString().trim();

    // Only process rows that look like employee records
    // (have a numeric employee number and a MOL ID that looks like a labor card)
    if (!empNo || !molId || !/^\d{10,}$/.test(molId)) continue;
    if (!name || name === '') continue;

    const bankName = row[4]?.toString().trim() || '';
    const bankRouting = row[5]?.toString().trim() || '';
    const iban = row[6]?.toString().trim() || '';
    const basic    = parseNum(row[7]);   // Basic
    const rawAllow = parseNum(row[8]);   // Allowance
    const wpsBasic = parseNum(row[16]);  // WPS BASIC
    const wpsAllow = parseNum(row[17]);  // WPS ALLOW

    // Employee master data
    employees.push({
      empNo,
      name,
      molId,
      bankName,
      bankRoutingCode: bankRouting,
      iban,
      basicSalary: basic || wpsBasic,
      allowance: rawAllow,
    });

    // Payroll entry
    payrollEntries.push({
      empNo,
      molId,
      name,
      basicSalary: wpsBasic || basic,
      variableAllowance: wpsAllow,
      daysOnLeave: 0,
      excluded: false,
    });
  }

  return { employees, payrollEntries };
}

export function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = reject;
    reader.readAsText(file);
  });
}
