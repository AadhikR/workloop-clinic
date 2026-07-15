/**
 * reportUtils.js — Pure aggregation helpers for the HR Reports module (Feature 10)
 *
 * All functions are synchronous and operate on data already fetched from Supabase.
 * CSV export uses papaparse; PDF export uses a lightweight table renderer on top of jsPDF.
 */
import Papa from 'papaparse';
import { jsPDF } from 'jspdf';
import { formatDateUAE } from './uaeValidators';

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
  const active = employees.filter(e => e.active && e.employmentStatus !== 'Terminated');

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
      rows.push({ Category: s.label, Group: key, Count: count, 'Share %': `${((count / report.total) * 100).toFixed(1)}%` });
    }
  }
  return rows;
}

// ─── 2. Payroll Cost Report ───────────────────────────────────────────────────

export function buildPayrollCostReport(payrolls, employees) {
  const generated = payrolls.filter(p => p.status === 'generated');
  return generated.map(p => {
    const active = (p.entries || []).filter(e => !e.excluded);
    const totalBasic = sum(active, e => parseFloat(e.basicSalary) || 0);
    const totalAllow = sum(active, e => parseFloat(e.variableAllowance) || 0);
    const totalBonus = sum(active, e => (parseFloat(e.bonus) || 0) + (parseFloat(e.otherPay) || 0) + (parseFloat(e.increment) || 0));
    const totalGross = totalBasic + totalAllow + totalBonus;

    // Group by department
    const byDept = {};
    for (const entry of active) {
      const emp  = employees.find(e => e.id === entry.employeeId);
      const dept = emp?.department || 'Unspecified';
      if (!byDept[dept]) byDept[dept] = 0;
      byDept[dept] += (parseFloat(entry.basicSalary) || 0) + (parseFloat(entry.variableAllowance) || 0);
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
    (r.status === 'Approved' || r.status === 'ManagerApproved') && r.startDate?.startsWith(yearStr)
  );

  return employees
    .filter(e => e.active)
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
    .filter(e => e.active)
    .map(emp => {
      const recs    = filtered.filter(r => r.employeeId === emp.id);
      const present = recs.filter(r => r.status === 'PRESENT').length;
      const absent  = recs.filter(r => r.status === 'ABSENT').length;
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

// ─── 5. Document Expiry Report ────────────────────────────────────────────────

export function buildDocumentExpiryReport(employees, documents, daysThreshold = 90) {
  const today   = new Date();
  today.setHours(0, 0, 0, 0);
  const cutoff  = new Date(today);
  cutoff.setDate(cutoff.getDate() + daysThreshold);

  return documents
    .filter(doc => {
      if (!doc.expiryDate) return false;
      const exp = new Date(doc.expiryDate);
      return exp <= cutoff; // includes already-expired
    })
    .map(doc => {
      const emp  = employees.find(e => e.id === doc.employeeId);
      const exp  = new Date(doc.expiryDate);
      const days = Math.ceil((exp - today) / 86400000);
      return {
        employee:     emp?.name || '—',
        department:   emp?.department || '—',
        documentType: doc.documentType || '—',
        expiryDate:   doc.expiryDate,
        daysRemaining: days,
        status:       days < 0 ? 'Expired' : days < 30 ? 'Critical' : days < 60 ? 'Warning' : 'Expiring Soon',
      };
    })
    .sort((a, b) => a.daysRemaining - b.daysRemaining);
}

export function docExpiryToRows(report) {
  return report.map(r => ({
    Employee:        r.employee,
    Department:      r.department,
    'Document Type': r.documentType,
    'Expiry Date':   formatDateUAE(r.expiryDate),
    'Days Remaining': r.daysRemaining,
    Status:          r.status,
  }));
}

// ─── 6. Salary Movement History ───────────────────────────────────────────────

export function buildSalaryMovementReport(employees, jobHistory, startDate, endDate) {
  const start = startDate ? new Date(startDate) : null;
  const end   = endDate   ? new Date(endDate)   : null;

  return jobHistory
    .filter(h => {
      if (h.changeType !== 'salary_change') return false;
      const d = new Date(h.changedAt);
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
  const start = new Date(startDate);
  const end   = new Date(endDate);

  const joiners = employees.filter(e => {
    const d = new Date(e.employmentStartDate || e.startDate);
    return d >= start && d <= end;
  });

  const leavers = employees.filter(e => {
    if (!e.terminationDate) return false;
    const d = new Date(e.terminationDate);
    return d >= start && d <= end;
  });

  // Average tenure of leavers (days)
  const avgTenure = leavers.length
    ? Math.round(leavers.reduce((s, e) => {
        const hired  = new Date(e.employmentStartDate || e.startDate);
        const left   = new Date(e.terminationDate);
        return s + Math.max(0, (left - hired) / 86400000);
      }, 0) / leavers.length)
    : 0;

  return { joiners, leavers, avgTenureDays: avgTenure };
}

export function turnoverJoinersToRows(joiners) {
  return joiners.map(e => ({
    Employee:    e.name,
    Department:  e.department || '—',
    'Start Date': e.employmentStartDate || e.startDate || '—',
    'Job Title': e.jobTitle || '—',
    'Contract':  e.contractType || '—',
  }));
}

export function turnoverLeaversToRows(leavers) {
  return leavers.map(e => ({
    Employee:          e.name,
    Department:        e.department || '—',
    'Start Date':      e.employmentStartDate || e.startDate || '—',
    'Termination Date': e.terminationDate || '—',
    Reason:            e.terminationReason || '—',
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

function fmt(n) {
  return (parseFloat(n) || 0).toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
