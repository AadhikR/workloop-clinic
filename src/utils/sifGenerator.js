/**
 * SIF File Generator
 *
 * Based on analysis of actual SIF files vs source CSV data:
 * - Amounts are stored as INTEGER AED (NOT fils).
 *   e.g. Basic 7200 AED → stored as 7200 in the SIF file.
 *   The SCR total 274821 = sum of all (basic + allowance) values in AED.
 *
 * EDR (Employee Detail Record) format:
 * EDR, MOL_Employee_ID, Bank_Routing_Code, IBAN, Pay_Start_Date, Pay_End_Date,
 *      Days_in_Period, Basic_Salary(AED int), Variable_Allowance(AED int), Days_on_Leave
 *
 * SCR (Salary Control Record) format:
 * SCR, MOL_Employer_ID, Bank_Routing_Code, Payment_Date(YYYY-MM-DD),
 *      File_Sequence_No, Period(MMYYYY), Employee_Count,
 *      Total_Amount(AED int), Currency, Description
 *
 * Filename format: {MOL_employer_ID}{payment_date_DDMMYYYY}{sequence_padded}.sif
 * e.g. 0000000816726260305183002.sif
 *   = MOL:0000000816726 + date:26-03-05 → DDMMYYYY=05032026 + seq:1830 padded to 10 → 0000001830
 *   Wait — actual: 260305183002
 *   = 26 03 05 1830 02? Let's decode: 0000000816726 | 260305 | 183002
 *   payment date 2026-03-05 → YYMMDD = 260305, seq=1830, suffix=02?
 *   Actually: 0000000816726 + 260305 + 183002
 *   The last part 183002 = seq 1830 + "02"? Or just seq padded differently.
 *   Looking at March file: 0000000816726 + 260408 + 102311
 *   payment date 2026-04-08 → YYMMDD=260408, seq=1023, suffix=11?
 *   So format is: {MOL_ID}{YYMMDD}{seq}{??}
 *   The suffix seems to be the last 2 digits of something.
 *   Most likely the bank generates the filename — we'll use: {MOL_ID}{YYYYMMDD}{seq_padded_to_10}
 *   and let the user rename if needed, OR use YYMMDD format to match the examples.
 */

function padLeft(str, len, char = '0') {
  return String(str).padStart(len, char);
}

function toIntAED(amount) {
  // Round to nearest integer AED
  return Math.round(parseFloat(amount || 0));
}

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function getMonthPeriod(year, month) {
  // Returns MMYYYY e.g. 022026
  return `${padLeft(month, 2)}${year}`;
}

function getMonthName(month) {
  const names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return names[month - 1];
}

export function generateSIF(company, employees, payroll) {
  const lines = [];

  // Parse payroll period
  const [year, month] = payroll.period.split('-').map(Number);
  const daysInMonth = getDaysInMonth(year, month);
  const payStartDate = `${year}-${padLeft(month, 2)}-01`;
  const payEndDate = `${year}-${padLeft(month, 2)}-${padLeft(daysInMonth, 2)}`;

  let totalAmount = 0;
  let employeeCount = 0;

  // Build EDR lines for each employee entry in this payroll
  for (const entry of payroll.entries) {
    const emp = employees.find(e => e.id === entry.employeeId);
    if (!emp || entry.excluded) continue;

    const basicAED = toIntAED(entry.basicSalary ?? emp.basicSalary);
    const allowanceAED = toIntAED(entry.variableAllowance ?? 0);
    const daysOnLeave = parseInt(entry.daysOnLeave ?? 0);

    totalAmount += basicAED + allowanceAED;
    employeeCount++;

    lines.push(
      `EDR,${emp.molId},${emp.bankRoutingCode},${emp.iban},${payStartDate},${payEndDate},${daysInMonth},${basicAED},${allowanceAED},${daysOnLeave}`
    );
  }

  // Build SCR line
  // sequenceNo = File Creation Time in HHMM format (per WPS guide, Column E of SCR)
  // Use stored value if present, otherwise use current time HHMM
  const period = getMonthPeriod(year, month);
  const paymentDate = payroll.paymentDate; // YYYY-MM-DD
  const now = new Date();
  const autoHHMM = String(now.getHours()).padStart(2, '0') + String(now.getMinutes()).padStart(2, '0');
  const sequenceNo = payroll.sequenceNo || autoHHMM;
  const description = payroll.description || `Sal for ${getMonthName(month)} ${year}`;

  lines.push(
    `SCR,${company.molEmployerId},${payroll.scrBankRoutingCode || company.defaultBankRoutingCode},${paymentDate},${sequenceNo},${period},${employeeCount},${totalAmount},AED,${description}`
  );

  // WPS banks require Windows line endings (CRLF).
  // Using LF-only causes all lines to appear as a single row when the bank parses the file.
  return lines.join('\r\n');
}

export function generateSIFFilename(company, payroll) {
  /**
   * Filename format per EI businessONLINE WPS User Guide (exactly 25 chars before .sif):
   *   {MOL_Employer_ID_13}{File_Creation_Date_YYMMDD_6}{File_Creation_Time_HHMMSS_6}
   *
   * From the guide (page 12):
   *   "File Name should be saved as EMPLOYER UNIQUE ID FILE CREATION DATE FILE CREATION TIME"
   *   Example: MOL=0000000965625, date=091025 (25 Oct 2009), time=163000 → 0000000965625091025163000
   *
   * Reference files confirm:
   *   0000000816726 260305 183002  → created on 2026-03-05 at 18:30:02
   *   0000000816726 260408 102311  → created on 2026-04-08 at 10:23:11
   *
   * Total: 13 + 6 + 6 = 25 chars
   *
   * We use the current date/time at the moment of file generation.
   */
  const now = new Date();
  const yy  = String(now.getFullYear()).slice(2);
  const mm  = String(now.getMonth() + 1).padStart(2, '0');
  const dd  = String(now.getDate()).padStart(2, '0');
  const hh  = String(now.getHours()).padStart(2, '0');
  const min = String(now.getMinutes()).padStart(2, '0');
  const ss  = String(now.getSeconds()).padStart(2, '0');
  const dateStr = yy + mm + dd;   // YYMMDD (6 chars)
  const timeStr = hh + min + ss;  // HHMMSS (6 chars)
  const molId = String(company.molEmployerId).padStart(13, '0'); // ensure 13 chars
  return `${molId}${dateStr}${timeStr}.sif`;
}

/**
 * Generates a corrected SIF file containing ONLY the rejected employees.
 * Used by the WPS Tracking panel (Feature 9) when some payments were rejected by
 * the bank and need to be re-submitted.
 *
 * @param {object}   company             — company object (same shape as generateSIF)
 * @param {object[]} employees           — full employee list
 * @param {object}   payroll             — the original locked payroll run
 * @param {string[]} rejectedEmployeeIds — array of employee.id values to include
 */
export function generateCorrectedSIF(company, employees, payroll, rejectedEmployeeIds) {
  const rejectedSet = new Set(rejectedEmployeeIds);
  const correctedPayroll = {
    ...payroll,
    entries: payroll.entries.map(e => ({
      ...e,
      // Exclude everyone NOT in the rejected list
      excluded: e.excluded || !rejectedSet.has(e.employeeId),
    })),
  };
  return generateSIF(company, employees, correctedPayroll);
}

export function parseSIFPreview(sifContent) {
  // Normalise both CRLF and LF so the preview works on files generated before the fix too
  return sifContent.split(/\r?\n/).filter(l => l.trim()).map(line => {
    const parts = line.trim().split(',');
    if (parts[0] === 'EDR') {
      return {
        type: 'EDR',
        molId: parts[1],
        bankRouting: parts[2],
        iban: parts[3],
        startDate: parts[4],
        endDate: parts[5],
        days: parts[6],
        basic: parts[7],   // integer AED
        allowance: parts[8], // integer AED
        leave: parts[9],
      };
    } else if (parts[0] === 'SCR') {
      return {
        type: 'SCR',
        employerId: parts[1],
        bankRouting: parts[2],
        paymentDate: parts[3],
        sequence: parts[4],
        period: parts[5],
        count: parts[6],
        total: parts[7],   // integer AED
        currency: parts[8],
        description: parts.slice(9).join(','),
      };
    }
    return { type: 'UNKNOWN', raw: line };
  });
}
