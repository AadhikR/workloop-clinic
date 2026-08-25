/**
 * payslipGenerator.js — PDF Payslip Generator for Workloop
 *
 * Uses jsPDF to generate a professional payslip PDF per employee.
 * Payslip includes:
 *   - Company name + logo area + payroll run date
 *   - Employee name, ID, department, designation
 *   - Salary period
 *   - Earnings breakdown (basic, housing, transport, other allowances)
 *   - Deductions breakdown
 *   - Net pay in AED
 */

import { jsPDF } from 'jspdf';
import { zipSync } from 'fflate';
import { formatDateUAE, formatAED } from './uaeValidators';
import { calculatePayrollEntry } from './payrollCalculator';

const MONTH_NAMES = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
];

function getMonthName(month) {
  return MONTH_NAMES[month - 1] || '';
}

async function tryLoadImage(url) {
  if (!url) return null;
  return new Promise(resolve => {
    const img = new Image();
    // crossOrigin only matters for cross-origin http(s) resources. Setting
    // it on a data: URI is a no-op at best and, on some browser/jsPDF
    // combinations, silently blocks the load — leaving the payslip
    // falling back to text with no visible error.
    if (!/^data:/i.test(url)) img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = (e) => {
      // Surface the failure so a broken logo doesn't disappear silently.
      console.warn('[payslip] Company logo failed to load. URL prefix:',
        url.slice(0, 60), e);
      resolve(null);
    };
    img.src = url;
  });
}

// Detect image format from a data: URI so we can pass it explicitly to
// jsPDF's addImage — auto-detection from an HTMLImageElement source can be
// unreliable for data URIs.
function detectFormat(url) {
  if (!url) return null;
  const m = /^data:image\/(png|jpeg|jpg|webp|svg\+xml)/i.exec(url);
  if (!m) return null;
  const f = m[1].toLowerCase();
  if (f === 'jpg') return 'JPEG';
  if (f === 'svg+xml') return 'PNG'; // shouldn't happen — upload util rasterizes
  return f.toUpperCase();
}

/**
 * Generate a PDF payslip for a single employee in a payroll run.
 *
 * @param {object} company   — company settings
 * @param {object} employee  — employee record (full profile)
 * @param {object} payroll   — payroll run object
 * @param {object} entry     — payroll entry for this employee
 * @returns {Promise<jsPDF>} — the PDF document (call .save() to download)
 */
export async function generatePayslipPDF(company, employee, payroll, entry) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

  // Diagnostic: surface the state of the logo so silent "no logo showing"
  // reports are one console glance away. Logs to console once per payslip.
  const logoUrl = company?.logoUrl || '';
  if (!logoUrl) {
    console.info('[payslip] No company logo configured (company.logoUrl is empty). Upload one in Company Settings → Payroll Settings.');
  } else {
    console.info(`[payslip] Loading company logo (${Math.round(logoUrl.length / 1024)}KB, type=${logoUrl.slice(5, 25)}…)`);
  }

  const logoImg = await tryLoadImage(logoUrl);

  const [year, month] = payroll.period.split('-').map(Number);
  const periodLabel   = `${getMonthName(month)} ${year}`;
  const runDate       = payroll.paymentDate ? formatDateUAE(payroll.paymentDate) : formatDateUAE(new Date().toISOString().split('T')[0]);

  // ── Colours ──────────────────────────────────────────────────────────────
  const PRIMARY   = [26, 86, 219];   // #1a56db
  const DARK      = [17, 24, 39];    // #111827
  const GRAY      = [107, 114, 128]; // #6b7280
  const LIGHT     = [249, 250, 251]; // #f9fafb
  const SUCCESS   = [5, 122, 85];    // #057a55
  const DANGER    = [200, 30, 30];   // #c81e1e
  const WHITE     = [255, 255, 255];

  const pageW = 210;
  const pageH = 297;
  const margin = 14;
  const contentW = pageW - margin * 2;

  // ── Header band ──────────────────────────────────────────────────────────
  doc.setFillColor(...PRIMARY);
  doc.rect(0, 0, pageW, 32, 'F');

  doc.setTextColor(...WHITE);
  let logoDrawn = false;
  if (logoImg) {
    const maxLogoH = 22;
    const aspect   = (logoImg.naturalWidth || logoImg.width) / (logoImg.naturalHeight || logoImg.height);
    const logoW    = Math.min(aspect * maxLogoH, 50);
    const logoH    = logoW / aspect;
    // Prefer the raw data URL over the HTMLImageElement when we have one —
    // jsPDF is more consistent decoding a data URI string than reading pixels
    // out of an Image element (especially with mixed browsers).
    const src = /^data:/i.test(company?.logoUrl || '') ? company.logoUrl : logoImg;
    const fmt = detectFormat(company?.logoUrl) || 'PNG';
    try {
      doc.addImage(src, fmt, margin, (32 - logoH) / 2, logoW, logoH);
      logoDrawn = true;
    } catch (err) {
      // Log so silent breakage is diagnosable; fall through to text branch.
      console.warn('[payslip] jsPDF addImage failed, falling back to text:',
        err?.message || err);
    }
    if (logoDrawn) {
      const textStart = margin + logoW + 4;
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.text(company?.name || '', textStart, 13);
      doc.setFontSize(9);
      doc.setFont('helvetica', 'normal');
      doc.text('SALARY PAYSLIP', textStart, 20);
      doc.text(`Period: ${periodLabel}`, textStart, 26);
    }
  }
  if (!logoDrawn) {
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text(company?.name || 'Company Name', margin, 13);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.text('SALARY PAYSLIP', margin, 20);
    doc.text(`Period: ${periodLabel}`, margin, 26);
  }

  // Right side of header
  doc.setFontSize(9);
  doc.text(`Payment Date: ${runDate}`, pageW - margin, 13, { align: 'right' });
  doc.text(`MOL Employer ID: ${company?.molEmployerId || '—'}`, pageW - margin, 20, { align: 'right' });
  if (company?.address) {
    doc.text(company.address, pageW - margin, 26, { align: 'right' });
  }

  // ── Employee info band ───────────────────────────────────────────────────
  doc.setFillColor(...LIGHT);
  doc.rect(0, 32, pageW, 28, 'F');
  doc.setDrawColor(229, 231, 235);
  doc.line(0, 60, pageW, 60);

  doc.setTextColor(...DARK);
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.text(employee.name || '—', margin, 42);

  doc.setFontSize(9);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...GRAY);

  const empInfoLeft = [
    `Employee ID: ${employee.empNo || employee.molId || '—'}`,
    `MOL ID: ${employee.molId || '—'}`,
    `Department: ${employee.department || '—'}`,
  ];
  const empInfoRight = [
    `Designation: ${employee.jobTitle || '—'}`,
    `Contract: ${employee.contractType || '—'}`,
    `Start Date: ${formatDateUAE(employee.startDate || employee.employmentStartDate)}`,
  ];

  empInfoLeft.forEach((line, i) => doc.text(line, margin, 49 + i * 5));
  empInfoRight.forEach((line, i) => doc.text(line, pageW / 2 + 4, 49 + i * 5));

  // ── Salary breakdown ─────────────────────────────────────────────────────
  let y = 68;

  // Section header helper
  const sectionHeader = (label, yPos) => {
    doc.setFillColor(...PRIMARY);
    doc.rect(margin, yPos, contentW, 7, 'F');
    doc.setTextColor(...WHITE);
    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.text(label, margin + 3, yPos + 5);
    return yPos + 7;
  };

  // Row helper
  const tableRow = (label, amount, yPos, isTotal = false, color = DARK) => {
    if (isTotal) {
      doc.setFillColor(240, 245, 255);
      doc.rect(margin, yPos, contentW, 7, 'F');
    }
    doc.setTextColor(...color);
    doc.setFontSize(9);
    doc.setFont('helvetica', isTotal ? 'bold' : 'normal');
    doc.text(label, margin + 3, yPos + 5);
    doc.text(formatAED(amount), pageW - margin - 3, yPos + 5, { align: 'right' });
    doc.setDrawColor(229, 231, 235);
    doc.line(margin, yPos + 7, pageW - margin, yPos + 7);
    return yPos + 7;
  };

  // ── EARNINGS ─────────────────────────────────────────────────────────────
  y = sectionHeader('EARNINGS', y);

  const basicSalary      = parseFloat(entry.basicSalary) || 0;
  const housingAllowance = parseFloat(entry.housingAllowance ?? employee.housingAllowance) || 0;
  const transportAllowance = parseFloat(entry.transportAllowance ?? employee.transportAllowance) || 0;
  const baseAllowance    = parseFloat(entry.allowance) || 0;
  const increment        = parseFloat(entry.increment) || 0;
  const bonus            = parseFloat(entry.bonus) || 0;
  const otherPay         = parseFloat(entry.otherPay) || 0;
  const additionalAllowances = entry.additionalAllowances || [];
  const calc = calculatePayrollEntry({
    ...entry,
    housingAllowance,
    transportAllowance,
  });

  y = tableRow('Basic Salary', basicSalary, y);
  if (housingAllowance > 0) y = tableRow('Housing Allowance', housingAllowance, y);
  if (transportAllowance > 0) y = tableRow('Transport Allowance', transportAllowance, y);
  if (baseAllowance > 0) y = tableRow('Other Fixed Allowance', baseAllowance, y);
  if (increment > 0) y = tableRow('Increment', increment, y);
  if (bonus > 0) y = tableRow('Bonus / Incentive', bonus, y);
  if (otherPay > 0) y = tableRow('Other Pay', otherPay, y);
  additionalAllowances.forEach(a => {
    if (parseFloat(a.amount) > 0) y = tableRow(a.label || 'Additional Allowance', parseFloat(a.amount), y);
  });

  const totalEarnings = calc.grossEarnings;

  y = tableRow('TOTAL EARNINGS', totalEarnings, y, true, SUCCESS);
  y += 4;

  // ── DEDUCTIONS ───────────────────────────────────────────────────────────
  const deductions = entry.deductions || [];
  const duCost     = parseFloat(entry.duCost) || 0;
  const leaveDeduction = parseFloat(entry.leaveDeduction) || 0;
  const totalDeductions = calc.totalDeductions;

  if (totalDeductions > 0) {
    y = sectionHeader('DEDUCTIONS', y);
    deductions.forEach(d => {
      if (parseFloat(d.amount) > 0) y = tableRow(d.label || 'Deduction', parseFloat(d.amount), y);
    });
    if (leaveDeduction > 0) y = tableRow('Leave Deduction', leaveDeduction, y);
    if (duCost > 0) y = tableRow('DU / Telecom Cost', duCost, y);
    y = tableRow('TOTAL DEDUCTIONS', totalDeductions, y, true, DANGER);
    y += 4;
  }

  // ── NET PAY ──────────────────────────────────────────────────────────────
  const netPay = calc.netPay;

  doc.setFillColor(...PRIMARY);
  doc.rect(margin, y, contentW, 14, 'F');
  doc.setTextColor(...WHITE);
  doc.setFontSize(11);
  doc.setFont('helvetica', 'bold');
  doc.text('NET PAY', margin + 3, y + 9);
  doc.setFontSize(13);
  doc.text(formatAED(netPay), pageW - margin - 3, y + 9, { align: 'right' });
  y += 18;

  // ── Bank details ─────────────────────────────────────────────────────────
  if (employee.iban || employee.bankName) {
    doc.setFillColor(...LIGHT);
    doc.rect(margin, y, contentW, 14, 'F');
    doc.setTextColor(...GRAY);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.text('Bank Transfer Details', margin + 3, y + 5);
    doc.setTextColor(...DARK);
    doc.setFontSize(9);
    if (employee.bankName) doc.text(`Bank: ${employee.bankName}`, margin + 3, y + 10);
    if (employee.iban) doc.text(`IBAN: ${employee.iban}`, pageW / 2, y + 10);
    y += 18;
  }

  // ── Footer ───────────────────────────────────────────────────────────────
  doc.setFillColor(...DARK);
  doc.rect(0, pageH - 14, pageW, 14, 'F');
  doc.setTextColor(...WHITE);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  doc.text('This is a computer-generated payslip. No signature required.', pageW / 2, pageH - 7, { align: 'center' });
  doc.text('Workloop — UAE Payroll & HRMS', margin, pageH - 7);
  doc.text(`Generated: ${formatDateUAE(new Date().toISOString().split('T')[0])}`, pageW - margin, pageH - 7, { align: 'right' });

  return doc;
}

/**
 * Download a payslip PDF for a single employee.
 *
 * @param {object} company
 * @param {object} employee
 * @param {object} payroll
 * @param {object} entry
 */
export async function downloadPayslip(company, employee, payroll, entry) {
  const doc = await generatePayslipPDF(company, employee, payroll, entry);
  const [year, month] = payroll.period.split('-').map(Number);
  const filename = `Payslip_${employee.name?.replace(/\s+/g, '_')}_${getMonthName(month)}_${year}.pdf`;
  doc.save(filename);
}

/**
 * Download payslips for ALL active employees in a payroll run (one PDF per employee).
 *
 * @param {object} company
 * @param {Array}  employees
 * @param {object} payroll
 */
export async function downloadAllPayslips(company, employees, payroll) {
  const activeEntries = payroll.entries.filter(e => !e.excluded);
  const files = {};
  for (const entry of activeEntries) {
    const emp = employees.find(e => e.id === entry.employeeId);
    if (!emp) continue;
    const doc = await generatePayslipPDF(company, emp, payroll, entry);
    const [year, month] = payroll.period.split('-').map(Number);
    const safeName = (emp.name || emp.empNo || 'Employee').replace(/[^a-z0-9_-]+/gi, '_');
    const filename = `Payslip_${safeName}_${getMonthName(month)}_${year}.pdf`;
    files[filename] = new Uint8Array(doc.output('arraybuffer'));
  }
  if (!Object.keys(files).length) return;
  const zipped = zipSync(files, { level: 6 });
  const blob = new Blob([zipped], { type: 'application/zip' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `Payslips_${payroll.period}.zip`;
  anchor.click();
  URL.revokeObjectURL(url);
}
