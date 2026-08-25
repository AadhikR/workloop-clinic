import { calculatePayrollEntry, calculatePayrollTotals } from './payrollCalculator.js';
import { calculateGratuity } from './gratuityCalculator.js';
/**
 * reportUtils.js — Pure aggregation helpers for the HR Reports module (Feature 10)
 *
 * All functions are synchronous and operate on data already fetched from Supabase.
 * CSV export uses papaparse; PDF export uses a lightweight table renderer on top of jsPDF.
 */
import Papa from 'papaparse';
import { jsPDF } from 'jspdf';
import { formatDateUAE } from './uaeValidators.js';

// ─── CSV export ───────────────────────────────────────────────────────────────

export function exportCSV(rows, filename) {
  if (!rows?.length) return;
  const csv  = Papa.unparse(rows);
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── PDF export (simple auto-table) ──────────────────────────────────────────

export function exportPDF(title, headers, rows, filename) {
  if (!rows?.length) return;
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });

  // Title
  doc.setFontSize(14);
  doc.setFont(undefined, 'bold');
  doc.text(title, 14, 16);
  doc.setFontSize(9);
  doc.setFont(undefined, 'normal');
  doc.text(`Generated: ${new Date().toLocaleDateString('en-AE')}`, 14, 22);

  const pageW    = doc.internal.pageSize.getWidth();
  const colW     = Math.min(40, (pageW - 28) / headers.length);
  let   y        = 30;
  const rowH     = 7;
  const lineH    = 5;

  // Table header
  doc.setFillColor(37, 99, 235);
  doc.setTextColor(255, 255, 255);
  doc.setFontSize(8);
  doc.setFont(undefined, 'bold');
  doc.rect(14, y, pageW - 28, rowH, 'F');
  headers.forEach((h, i) => doc.text(String(h), 16 + i * colW, y + 5));
  y += rowH;

  // Table rows
  doc.setTextColor(30, 30, 30);
  doc.setFont(undefined, 'normal');
  rows.forEach((row, ri) => {
    if (y + rowH > doc.internal.pageSize.getHeight() - 14) {
      doc.addPage();
      y = 20;
    }
    if (ri % 2 === 0) {
      doc.setFillColor(245, 247, 250);
      doc.rect(14, y, pageW - 28, rowH, 'F');
    }
    Object.values(row).forEach((val, i) => {
      const txt = val == null ? '' : String(val);
      doc.text(txt.slice(0, 22), 16 + i * colW, y + lineH);
    });
    y += rowH;
  });

  doc.save(filename);
}

// ─── 1. Headcount Report ─────────────────────────────────────────────────────

export function buildHeadcountReport(employees) {
  const active = employees.filter(isActiveEmployee);

  const byDept = groupCount(active, e => e.department || 'Unspecified');
  const byNat  = groupCount(active, e => e.nationality || 'Unspecified');
  const byType = groupCount(active, e => e.contractType || 'Unspecified');
  const byGend = groupCount(active, e => e.gender || 'Unspecified');
  const byStatus = groupCount(active, e => e.employmentStatus || 'Active');

  return { total: active.length, byDept, byNat, byType, byGend, byStatus };
}

export function headcountToRows(report) {
  const rows = [];
  const sections = [
    { label: 'By Department',       data: report.byDept },
    { label: 'By Nationality',      data: report.byNat },
    { label: 'By Contract Type',    data: report.byType },
    { label: 'By Gender',           data: report.byGend },
    { label: 'By Employment Status',data: report.byStatus },
  ];
  for (const s of sections) {
    for (const [key, count] of Object.entries(s.data)) {
      rows.push({ Category: s.label, Group: key, Count: count, 'Share %': report.total ? `${((count / report.total) * 100).toFixed(1)}%` : '0.0%' });
    }
  }
  return rows;
}

// ─── 2. Payroll Cost Report ───────────────────────────────────────────────────

export function buildPayrollCostReport(payrolls, employees) {
  const generated = payrolls.filter(p => p.status === 'generated');
  return generated.map(p => {
    const active = (p.entries || []).filter(e => !e.excluded);
    const totals = calculatePayrollTotals(active);
    const totalBasic = totals.basicSalary;
    const totalBonus = sum(active, e => (parseFloat(e.bonus) || 0) + (parseFloat(e.otherPay) || 0) + (parseFloat(e.increment) || 0));
    const totalAllow = totals.grossEarnings - totals.basicSalary - totalBonus;
    const totalGross = totals.grossEarnings;

    // Group by department
    const byDept = {};
    for (const entry of active) {
      const emp  = employees.find(e => e.id === entry.employeeId);
      const dept = emp?.department || 'Unspecified';
      if (!byDept[dept]) byDept[dept] = 0;
      byDept[dept] += calculatePayrollEntry(entry).grossEarnings;
    }

    return {
      period: p.period, paymentDate: p.paymentDate || '—', employeeCount: active.length,
      totalBasic, totalAllow, totalBonus, totalGross, byDept,
    };
  }).sort((a, b) => b.period.localeCompare(a.period));
}

export function payrollCostToRows(report) {
  return report.map(r => ({
    Period:           r.period,
    'Payment Date':   formatDateUAE(r.paymentDate),
    Employees:        r.employeeCount,
    'Basic (AED)':    fmt(r.totalBasic),
    'Allowances (AED)': fmt(r.totalAllow),
    'Bonus/Other (AED)': fmt(r.totalBonus),
    'Total Cost (AED)': fmt(r.totalGross),
  }));
}

// ─── 3. Leave Utilization Report ─────────────────────────────────────────────

export function buildLeaveUtilizationReport(employees, leaveRequests, year) {
  const yearStr = String(year);
  const approved = leaveRequests.filter(r =>
    r.status === 'Approved' && r.startDate?.startsWith(yearStr)
  );

  return employees
    .filter(isActiveEmployee)
    .map(emp => {
      const empLeaves = approved.filter(r => r.employeeId === emp.id);
      const byType    = {};
      let totalDays   = 0;
      for (const req of empLeaves) {
        const days = req.daysRequested || 0;
        totalDays += days;
        const typeName = req.leaveTypeCode || req.leaveType || 'Annual';
        byType[typeName] = (byType[typeName] || 0) + days;
      }
      return {
        empId: emp.id, name: emp.name, department: emp.department || '—',
        totalDays, byType, requestCount: empLeaves.length,
      };
    })
    .filter(r => r.totalDays > 0)
    .sort((a, b) => b.totalDays - a.totalDays);
}

export function leaveUtilToRows(report) {
  return report.map(r => ({
    Employee:    r.name,
    Department:  r.department,
    'Requests':  r.requestCount,
    'Total Days Taken': r.totalDays,
    'Leave Types': Object.entries(r.byType).map(([t, d]) => `${t}: ${d}d`).join(', '),
  }));
}

// ─── 4. Attendance Summary Report ────────────────────────────────────────────

export function buildAttendanceSummaryReport(employees, attendanceRecords, period) {
  const filtered = attendanceRecords.filter(r => r.date?.startsWith(period));

  return employees
    .filter(isActiveEmployee)
    .map(emp => {
      const recs    = filtered.filter(r => r.employeeId === emp.id);
      const workedStatuses = new Set(['PRESENT', 'LATE', 'EARLY_DEPARTURE', 'HALF_DAY', 'OVERTIME', 'PRESENT_REMOTE', 'MISSING_CLOCK_OUT']);
      const present = recs.filter(r => workedStatuses.has(r.status)).length;
      const absent  = recs.filter(r => r.status === 'ABSENT' || r.status === 'UNEXPLAINED_ABSENCE').length;
      const late    = recs.filter(r => r.status === 'LATE').length;
      const earlyDep = recs.filter(r => r.status === 'EARLY_DEPARTURE').length;
      const totalHrs = recs.reduce((s, r) => s + (parseFloat(r.totalHours) || 0), 0);
      return {
        empId: emp.id, name: emp.name, department: emp.department || '—',
        present, absent, late, earlyDep, totalDays: recs.length,
        totalHours: Math.round(totalHrs * 10) / 10,
      };
    })
    .filter(r => r.totalDays > 0)
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function attendanceSummaryToRows(report) {
  return report.map(r => ({
    Employee:        r.name,
    Department:      r.department,
    'Days Recorded': r.totalDays,
    Present:         r.present,
    Absent:          r.absent,
    Late:            r.late,
    'Early Departure': r.earlyDep,
    'Total Hours':   r.totalHours,
  }));
}

// ─── Overtime Report ─────────────────────────────────────────────────────────

export function buildOvertimeReport(employees, attendanceRecords, period) {
  const filtered = attendanceRecords.filter(r => r.date?.startsWith(period) && (parseFloat(r.overtimeHours) || 0) > 0);
  return employees
    .filter(isActiveEmployee)
    .map(emp => {
      const records = filtered.filter(r => r.employeeId === emp.id);
      const approved = records.filter(r => r.overtimeApproved === true);
      const pending = records.filter(r => r.overtimeApproved !== true);
      return {
        empId: emp.id,
        name: emp.name,
        department: emp.department || '—',
        overtimeDays: records.length,
        approvedHours: round1(sum(approved, r => parseFloat(r.overtimeHours) || 0)),
        pendingHours: round1(sum(pending, r => parseFloat(r.overtimeHours) || 0)),
        approvedCost: round2(sum(approved, r => parseFloat(r.overtimeAmount) || 0)),
      };
    })
    .filter(r => r.overtimeDays > 0)
    .sort((a, b) => b.approvedHours - a.approvedHours || a.name.localeCompare(b.name));
}

export function overtimeToRows(report) {
  return report.map(r => ({
    Employee: r.name,
    Department: r.department,
    'Overtime Days': r.overtimeDays,
    'Approved Hours': r.approvedHours,
    'Pending Hours': r.pendingHours,
    'Approved Cost (AED)': fmt(r.approvedCost),
  }));
}

// ─── 5. Document Expiry Report ────────────────────────────────────────────────

export function buildDocumentExpiryReport(employees, documents, daysThreshold = 90) {
  const today   = new Date();
  today.setHours(0, 0, 0, 0);
  const cutoff  = new Date(today);
  cutoff.setDate(cutoff.getDate() + daysThreshold);

  const employeeMap = new Map(employees.filter(isActiveEmployee).map(employee => [employee.id, employee]));
  const candidates = [];

  for (const employee of employeeMap.values()) {
    const profileDocuments = [
      { documentType: 'Visa', expiryDate: employee.visaExpiry },
      { documentType: 'Passport', expiryDate: employee.passportExpiry },
      { documentType: 'Emirates ID', expiryDate: employee.emiratesIdExpiry },
      { documentType: 'Labour Card / Work Permit', expiryDate: employee.labourCardExpiry },
      {
        documentType: employee.licenceAuthority && employee.licenceAuthority !== 'None'
          ? `${employee.licenceAuthority} Professional Licence`
          : 'Professional Licence',
        expiryDate: employee.licenceExpiry,
      },
    ];
    for (const profileDocument of profileDocuments) {
      if (!profileDocument.expiryDate) continue;
      candidates.push({
        employeeId: employee.id,
        ...profileDocument,
        source: 'Employee Profile',
      });
    }
  }

  for (const document of documents) {
    if (!employeeMap.has(document.employeeId) || !document.expiryDate) continue;
    candidates.push({
      employeeId: document.employeeId,
      documentType: document.documentType || 'Uploaded Document',
      expiryDate: document.expiryDate,
      source: 'Uploaded Document',
    });
  }

  const unique = new Map();
  for (const candidate of candidates) {
    const expiryDate = dateOnly(candidate.expiryDate);
    if (!expiryDate || expiryDate > cutoff) continue; // includes already-expired
    const key = `${candidate.employeeId}|${canonicalDocumentType(candidate.documentType)}|${candidate.expiryDate}`;
    if (!unique.has(key)) unique.set(key, { ...candidate, parsedExpiryDate: expiryDate });
  }

  return [...unique.values()]
    .map(doc => {
      const emp = employeeMap.get(doc.employeeId);
      const days = Math.round((doc.parsedExpiryDate - today) / 86400000);
      return {
        employeeId:    doc.employeeId,
        employee:      emp?.name || '—',
        department:    emp?.department || '—',
        documentType:  doc.documentType,
        source:        doc.source,
        expiryDate:    doc.expiryDate,
        daysRemaining: days,
        status:        days < 0 ? 'Expired' : days < 30 ? 'Critical' : days < 60 ? 'Warning' : 'Expiring Soon',
      };
    })
    .sort((a, b) => a.daysRemaining - b.daysRemaining);
}

export function docExpiryToRows(report) {
  return report.map(r => ({
    Employee:        r.employee,
    Department:      r.department,
    'Document Type': r.documentType,
    Source:          r.source,
    'Expiry Date':   formatDateUAE(r.expiryDate),
    'Days Remaining': r.daysRemaining,
    Status:          r.status,
  }));
}

// ─── 6. Salary Movement History ───────────────────────────────────────────────

export function buildSalaryMovementReport(employees, jobHistory, startDate, endDate) {
  const start = startDate ? startOfDay(startDate) : null;
  const end   = endDate   ? endOfDay(endDate) : null;

  return jobHistory
    .filter(h => {
      if (h.changeType !== 'salary_change') return false;
      const d = new Date(h.changedAt);
      if (!isValidDate(d) || !employees.some(e => e.id === h.employeeId)) return false;
      if (start && d < start) return false;
      if (end   && d > end)   return false;
      return true;
    })
    .map(h => {
      const emp = employees.find(e => e.id === h.employeeId);
      const oldVal = parseFloat(h.oldValue) || 0;
      const newVal = parseFloat(h.newValue) || 0;
      return {
        employee:   emp?.name || '—',
        department: emp?.department || '—',
        changedAt:  h.changedAt ? h.changedAt.slice(0, 10) : '—',
        changedBy:  h.changedBy || '—',
        oldSalary:  oldVal,
        newSalary:  newVal,
        change:     newVal - oldVal,
        changePct:  oldVal > 0 ? `${((newVal - oldVal) / oldVal * 100).toFixed(1)}%` : '—',
        reason:     h.reason || '—',
      };
    })
    .sort((a, b) => b.changedAt.localeCompare(a.changedAt));
}

export function salaryMovementToRows(report) {
  return report.map(r => ({
    Employee:       r.employee,
    Department:     r.department,
    Date:           formatDateUAE(r.changedAt),
    'Changed By':   r.changedBy,
    'Old Salary':   fmt(r.oldSalary),
    'New Salary':   fmt(r.newSalary),
    'Change (AED)': (r.change >= 0 ? '+' : '') + fmt(r.change),
    'Change %':     r.changePct,
    Reason:         r.reason,
  }));
}

// ─── 7. Staff Turnover Report ─────────────────────────────────────────────────

export function buildTurnoverReport(employees, startDate, endDate) {
  const start = startOfDay(startDate);
  const end   = endOfDay(endDate);

  const joiners = employees.filter(e => {
    const d = new Date(e.employmentStartDate || e.startDate);
    return isValidDate(d) && d >= start && d <= end;
  });

  const leavers = employees.filter(e => {
    if (!e.terminationDate) return false;
    const d = new Date(e.terminationDate);
    return isValidDate(d) && d >= start && d <= end;
  });

  // Average tenure of leavers (days)
  const avgTenure = leavers.length
    ? Math.round(leavers.reduce((s, e) => {
        const hired  = new Date(e.employmentStartDate || e.startDate);
        const left   = new Date(e.terminationDate);
        if (!isValidDate(hired) || !isValidDate(left)) return s;
        return s + Math.max(0, (left - hired) / 86400000);
      }, 0) / leavers.length)
    : 0;

  return { joiners, leavers, avgTenureDays: avgTenure };
}

export function turnoverJoinersToRows(joiners) {
  return joiners.map(e => ({
    Employee:    e.name,
    Department:  e.department || '—',
    'Start Date': formatDateUAE(e.employmentStartDate || e.startDate),
    'Job Title': e.jobTitle || '—',
    'Contract':  e.contractType || '—',
  }));
}

export function turnoverLeaversToRows(leavers) {
  return leavers.map(e => ({
    Employee:          e.name,
    Department:        e.department || '—',
    'Start Date':      formatDateUAE(e.employmentStartDate || e.startDate),
    'Termination Date': formatDateUAE(e.terminationDate),
    Reason:            e.terminationReason || '—',
  }));
}

// ─── WPS Compliance Report ──────────────────────────────────────────────────

export function buildWpsComplianceReport(payrolls) {
  const generated = payrolls.filter(p => p.status === 'generated');
  const submitted = generated.filter(p => ['submitted', 'confirmed', 'partial_rejection', 'failed'].includes(p.wpsStatus));
  const confirmed = generated.filter(p => p.wpsStatus === 'confirmed');
  const failed = generated.filter(p => p.wpsStatus === 'failed' || p.wpsStatus === 'partial_rejection');
  const pending = generated.filter(p => ['draft', 'sif_generated', 'submitted'].includes(p.wpsStatus || 'draft'));

  return { generated, submitted, confirmed, failed, pending, complianceRate: generated.length ? Math.round(confirmed.length / generated.length * 100) : 0 };
}

export function wpsComplianceToRows(payrolls) {
  return payrolls.filter(p => p.status === 'generated').map(p => ({
    Period:          p.period,
    Status:          p.status,
    'WPS Status':    p.wpsStatus || 'draft',
    'Submitted At':  p.wpsSubmittedAt ? formatDateUAE(p.wpsSubmittedAt.split('T')[0]) : '—',
    'Confirmed At':  p.wpsConfirmedAt ? formatDateUAE(p.wpsConfirmedAt.split('T')[0]) : '—',
    'Reference No':  p.wpsReferenceNo || '—',
    'Employees':     p.employeeCount || 0,
    'Total (AED)':   fmt(p.totalDisbursed),
  }));
}

// ─── Emiratization / Nafis Report ───────────────────────────────────────────

export function buildEmiratizationReport(employees, quotaPercent = 2) {
  const active = employees.filter(isActiveEmployee);
  const emiratis = active.filter(e => isEmiratiNationality(e.nationality));
  const ratio = active.length ? (emiratis.length / active.length * 100).toFixed(1) : '0.0';
  const tier = active.length < 20 ? 'not_mandatory' : active.length < 50 ? 'fixed_two' : 'percentage';
  const requiredCount = tier === 'fixed_two' ? 2 : tier === 'percentage' ? Math.ceil((Number(quotaPercent) || 2) / 100 * active.length) : 0;
  const gap = Math.max(0, requiredCount - emiratis.length);
  const byDept = {};
  active.forEach(e => {
    const d = e.department || 'Unassigned';
    if (!byDept[d]) byDept[d] = { total: 0, emirati: 0 };
    byDept[d].total++;
    if (isEmiratiNationality(e.nationality)) byDept[d].emirati++;
  });
  return { active, emiratis, ratio, byDept, tier, requiredCount, gap, compliant: gap === 0, monthlyFine: gap * 9000 };
}

export function emiratizationToRows(employees) {
  const active = employees.filter(isActiveEmployee);
  return active.map(e => ({
    Employee:     e.name,
    Department:   e.department || '—',
    Nationality:  e.nationality || '—',
    'Job Title':  e.jobTitle || '—',
    'Is Emirati': isEmiratiNationality(e.nationality) ? 'Yes' : 'No',
    'Nafis ID':   e.nafisRegistrationNo || e.nafisId || '—',
  }));
}

// ─── End of Service Liability Report ────────────────────────────────────────

export function buildEOSLiabilityReport(employees, asOfDate = new Date()) {
  const active = employees.filter(isActiveEmployee);
  const items = active.map(e => {
    const startDate = e.employmentStartDate || e.startDate;
    const start = new Date(startDate);
    if (!startDate || !isValidDate(start)) return { ...e, serviceYears: 0, liability: 0, dataWarning: 'Missing start date' };
    const gratuity = calculateGratuity(e.basicSalary, startDate, asOfDate, 'Termination', e.contractType || 'Unlimited');
    return { ...e, serviceYears: gratuity.totalYears, liability: gratuity.gratuityCapped, dataWarning: '' };
  });
  const totalLiability = items.reduce((s, i) => s + i.liability, 0);
  return { items, totalLiability };
}

export function eosLiabilityToRows(items) {
  return items.map(e => ({
    Employee:        e.name,
    Department:      e.department || '—',
    'Start Date':    formatDateUAE(e.employmentStartDate || e.startDate),
    'Service Years': e.serviceYears.toFixed(1),
    'Basic Salary':  fmt(e.basicSalary),
    'EOS Liability': fmt(e.liability),
    'Data Note':     e.dataWarning || '—',
  }));
}

// ─── Leave Balance Report ───────────────────────────────────────────────────

export function buildLeaveBalanceReport(employees, leaveBalances, year) {
  const active = employees.filter(isActiveEmployee);
  return active.map(e => {
    const balances = leaveBalances.filter(b => b.employeeId === e.id && Number(b.leaveYear) === Number(year));
    const annual = balances.find(b => b.leaveTypeCode === 'ANNUAL');
    return {
      employee: e,
      annualEntitled: annual?.entitledDays || 0,
      annualAccrued: annual?.accruedDays || 0,
      annualUsed: annual?.usedDays || 0,
      annualRemaining: annual?.remaining || 0,
      totalUsed: round1(sum(balances, b => parseFloat(b.usedDays) || 0)),
      pending: round1(sum(balances, b => parseFloat(b.pendingDays) || 0)),
      totalRemaining: round1(sum(balances, b => parseFloat(b.remaining) || 0)),
      hasBalanceData: balances.length > 0,
    };
  });
}

export function leaveBalanceToRows(balanceData) {
  return balanceData.map(b => ({
    Employee:         b.employee.name,
    Department:       b.employee.department || '—',
    'Annual Entitled': Math.round(b.annualEntitled),
    'Annual Accrued':  Math.round(b.annualAccrued),
    'Annual Used':     Math.round(b.annualUsed),
    'Annual Remaining': Math.round(b.annualRemaining),
    'All Types Used':  Math.round(b.totalUsed),
    'Pending':         Math.round(b.pending),
    'All Types Remaining': Math.round(b.totalRemaining),
    Status: b.hasBalanceData ? 'Calculated' : 'Not calculated',
  }));
}

// ─── Internal helpers ─────────────────────────────────────────────────────────

function groupCount(arr, keyFn) {
  const map = {};
  for (const item of arr) {
    const k = keyFn(item);
    map[k] = (map[k] || 0) + 1;
  }
  return Object.fromEntries(Object.entries(map).sort((a, b) => b[1] - a[1]));
}

function sum(arr, fn) {
  return arr.reduce((s, x) => s + fn(x), 0);
}

function isActiveEmployee(employee) {
  return employee?.active !== false && employee?.employmentStatus !== 'Terminated';
}

function isEmiratiNationality(nationality) {
  const normalized = String(nationality || '').trim().toLowerCase();
  return ['united arab emirates', 'uae', 'emirati'].includes(normalized);
}

function isValidDate(date) {
  return date instanceof Date && Number.isFinite(date.getTime());
}

function startOfDay(value) {
  const date = new Date(`${value}T00:00:00`);
  return isValidDate(date) ? date : null;
}

function endOfDay(value) {
  const date = new Date(`${value}T23:59:59.999`);
  return isValidDate(date) ? date : null;
}

function dateOnly(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00`);
  return isValidDate(date) ? date : null;
}

function canonicalDocumentType(documentType) {
  const type = String(documentType || '').toLowerCase().replace(/[^a-z0-9]/g, '');
  if (type.includes('visa')) return 'visa';
  if (type.includes('passport')) return 'passport';
  if (type.includes('emiratesid') || type === 'eid') return 'emirates-id';
  if (type.includes('labourcard') || type.includes('laborcard') || type.includes('workpermit')) return 'labour-card';
  if (type.includes('licence') || type.includes('license')) return 'professional-licence';
  return type || 'uploaded-document';
}

function round1(value) {
  return Math.round((value + Number.EPSILON) * 10) / 10;
}

function round2(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function fmt(n) {
  return (parseFloat(n) || 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
