import Papa from 'papaparse';

/**
 * Parse the salary CSV file format used by this company.
 * Columns are matched by header name (case-insensitive), not fixed position —
 * this tolerates reordered or user-edited columns from a saved Excel file.
 */

// Strip thousand-separator commas and parse as float
function parseNum(val) {
  if (val === undefined || val === null) return 0;
  return parseFloat(String(val).replace(/,/g, '').trim()) || 0;
}

// Strips the `="value"` Excel text-formula guard (used on export/template to stop
// Excel mangling long numeric IDs into scientific notation) plus any stray quotes.
function cleanId(val) {
  if (val === undefined || val === null) return '';
  let s = String(val).trim();
  const m = s.match(/^="(.*)"$/);
  if (m) s = m[1];
  return s.replace(/^"+|"+$/g, '').trim();
}

const HEADER_ALIASES = {
  empNo:       ['no', 'emp no', 'employee no', 'employee number'],
  name:        ['name', 'employee name'],
  molId:       ['labor card no', 'labour card no', 'mol id', 'mol employee id'],
  bankName:    ['bank', 'bank name'],
  bankRouting: ['bank / routing code', 'bank/routing code', 'routing code', 'bank routing code'],
  iban:        ['bank account no', 'iban', 'bank account number'],
  basic:       ['basic'],
  allowance:   ['allowance'],
  wpsBasic:    ['wps basic'],
  wpsAllow:    ['wps allow'],
};

function buildHeaderIndex(headerRow) {
  const normalized = (headerRow || []).map(h => String(h ?? '').trim().toLowerCase());
  const index = {};
  for (const [key, aliases] of Object.entries(HEADER_ALIASES)) {
    index[key] = normalized.findIndex(h => aliases.includes(h)); // -1 if missing
  }
  return index;
}

export function parseCSV(fileContent) {
  const result = Papa.parse(fileContent, {
    skipEmptyLines: false,
    header: false,
  });

  const rows = result.data;
  const employees = [];
  const payrollEntries = [];
  if (rows.length < 2) return { employees, payrollEntries };

  const idx = buildHeaderIndex(rows[0]);
  const get = (row, key) => (idx[key] >= 0 ? row[idx[key]] : undefined);

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    if (!row || row.every(c => c === '' || c === undefined || c === null)) continue;

    const empNo = cleanId(get(row, 'empNo'));
    const molId = cleanId(get(row, 'molId'));
    const name  = String(get(row, 'name') ?? '').trim();

    // Only process rows that look like employee records
    // (have an employee number and a MOL ID that looks like a labor card)
    if (!empNo || !molId || !/^\d{10,}$/.test(molId)) continue;
    if (!name) continue;

    const bankName    = String(get(row, 'bankName') ?? '').trim();
    const bankRouting = cleanId(get(row, 'bankRouting'));
    const iban        = String(get(row, 'iban') ?? '').trim();
    const basic       = parseNum(get(row, 'basic'));   // Basic
    const rawAllow    = parseNum(get(row, 'allowance')); // Allowance
    const wpsBasic    = parseNum(get(row, 'wpsBasic'));  // WPS BASIC
    const wpsAllow    = parseNum(get(row, 'wpsAllow'));  // WPS ALLOW

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
