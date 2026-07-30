/**
 * Reports.jsx — HR Reporting & Analytics (Feature 10)
 *
 * Seven report tabs:
 *   1. Headcount       — employee breakdown by dept, nationality, gender, contract type
 *   2. Payroll Cost    — period-by-period cost summary with department breakdown
 *   3. Leave Usage     — days taken per employee per year
 *   4. Attendance      — present/absent/late days per employee for a selected period
 *   5. Doc Expiry      — all documents expiring within N days
 *   6. Salary History  — salary change events from employee_job_history
 *   7. Staff Turnover  — joiners & leavers for a selected date range
 */
import { useState, useEffect } from 'react';
import { BarChart2, Users, DollarSign, CalendarDays, Clock, FileText, TrendingUp, UserMinus, Download, AlertCircle, ShieldCheck, Landmark, Flag, Wallet, ClipboardList } from 'lucide-react';
import { getEmployees, getPayrolls, getAllEmployeeDocuments, getAllJobHistory } from '../utils/storage';
import { getLeaveRequests } from '../utils/leaveStorage';
import { getAttendanceRecords, getRosterForMonth } from '../utils/attendanceStorage';
import { getDeptStaffingRules } from '../utils/staffingStorage';
import { formatDateUAE } from '../utils/uaeValidators';
import { useCompany } from '../context/CompanyContext';
import {
  buildHeadcountReport,     headcountToRows,
  buildPayrollCostReport,   payrollCostToRows,
  buildLeaveUtilizationReport, leaveUtilToRows,
  buildAttendanceSummaryReport, attendanceSummaryToRows,
  buildDocumentExpiryReport, docExpiryToRows,
  buildSalaryMovementReport, salaryMovementToRows,
  buildTurnoverReport,      turnoverJoinersToRows, turnoverLeaversToRows,
  buildWpsComplianceReport, wpsComplianceToRows,
  buildEmiratizationReport, emiratizationToRows,
  buildEOSLiabilityReport,  eosLiabilityToRows,
  buildLeaveBalanceReport,  leaveBalanceToRows,
  exportCSV, exportPDF,
} from '../utils/reportUtils';

const ALL_TABS = [
  { id: 'headcount',   label: 'Headcount',          icon: Users },
  { id: 'payroll',     label: 'Payroll Cost',        icon: DollarSign },
  { id: 'leave',       label: 'Leave Usage',         icon: CalendarDays },
  { id: 'attendance',  label: 'Attendance',          icon: Clock },
  { id: 'documents',   label: 'Doc Expiry',          icon: FileText },
  { id: 'salary',      label: 'Salary History',      icon: TrendingUp },
  { id: 'turnover',    label: 'Staff Turnover',      icon: UserMinus },
  { id: 'staffing',    label: 'Staffing Compliance', icon: ShieldCheck, feature: 'staffing' },
  { id: 'wps',         label: 'WPS Compliance',      icon: Landmark },
  { id: 'emiratization', label: 'Emiratization',      icon: Flag, feature: 'nafis' },
  { id: 'eos',         label: 'EOS Liability',        icon: Wallet },
  { id: 'leaveBalance', label: 'Leave Balance',       icon: ClipboardList },
];

const thisYear  = new Date().getFullYear();
const thisMonth = String(new Date().getMonth() + 1).padStart(2, '0');
const thisPeriod = `${thisYear}-${thisMonth}`;

function fmtAED(n) {
  return `AED ${(parseFloat(n) || 0).toLocaleString('en-AE', { minimumFractionDigits: 0 })}`;
}

function EmptyState({ message }) {
  return (
    <div className="empty-state" style={{ padding: '40px 0' }}>
      <BarChart2 size={36} />
      <h3>No data</h3>
      <p>{message || 'No records match the current filters.'}</p>
    </div>
  );
}

// ─── 1. Headcount ─────────────────────────────────────────────────────────────
function HeadcountTab({ employees }) {
  const report = buildHeadcountReport(employees);

  const sections = [
    { title: 'By Department',        data: report.byDept },
    { title: 'By Nationality',       data: report.byNat },
    { title: 'By Contract Type',     data: report.byType },
    { title: 'By Gender',            data: report.byGend },
    { title: 'By Employment Status', data: report.byStatus },
  ];

  return (
    <div>
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Active Employees</div>
          <div className="stat-value">{report.total}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Departments</div>
          <div className="stat-value">{Object.keys(report.byDept).length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Nationalities</div>
          <div className="stat-value">{Object.keys(report.byNat).length}</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 16 }}>
        {sections.map(s => (
          <div key={s.title} className="card">
            <div className="card-header"><h3>{s.title}</h3></div>
            {Object.keys(s.data).length === 0
              ? <div style={{ padding: '16px 20px', color: 'var(--gray-400)', fontSize: 13 }}>No data</div>
              : (
                <div style={{ padding: '0 20px 12px' }}>
                  {Object.entries(s.data).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 0', borderBottom: '1px solid var(--gray-100)' }}>
                      <div style={{ flex: 1, fontSize: 13, color: 'var(--gray-700)' }}>{k}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)', minWidth: 28, textAlign: 'right' }}>{v}</div>
                      <div style={{ width: 80, height: 6, background: 'var(--gray-100)', borderRadius: 3 }}>
                        <div style={{ width: `${Math.round((v / report.total) * 100)}%`, height: '100%', background: 'var(--primary)', borderRadius: 3 }} />
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--gray-400)', minWidth: 32, textAlign: 'right' }}>{Math.round((v / report.total) * 100)}%</div>
                    </div>
                  ))}
                </div>
              )}
          </div>
        ))}
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" onClick={() => exportCSV(headcountToRows(report), `headcount_${thisYear}.csv`)}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" onClick={() => exportPDF('Headcount Report', ['Category', 'Group', 'Count', 'Share %'], headcountToRows(report), `headcount_${thisYear}.pdf`)}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 2. Payroll Cost ──────────────────────────────────────────────────────────
function PayrollCostTab({ payrolls, employees }) {
  const report = buildPayrollCostReport(payrolls, employees);

  if (!report.length) return <EmptyState message="No finalised payroll runs found." />;

  return (
    <div>
      <div className="card">
        <div className="card-header"><h3>Period-by-Period Summary</h3></div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Payment Date</th>
                <th className="text-right">Employees</th>
                <th className="text-right">Basic (AED)</th>
                <th className="text-right">Allowances (AED)</th>
                <th className="text-right">Bonus/Other (AED)</th>
                <th className="text-right" style={{ background: 'var(--primary-light)', color: 'var(--primary-dark)' }}>Total Cost (AED)</th>
              </tr>
            </thead>
            <tbody>
              {report.map(r => (
                <tr key={r.period}>
                  <td style={{ fontWeight: 600 }}>{r.period}</td>
                  <td>{formatDateUAE(r.paymentDate)}</td>
                  <td className="text-right">{r.employeeCount}</td>
                  <td className="text-right">{r.totalBasic.toLocaleString('en-AE')}</td>
                  <td className="text-right">{r.totalAllow.toLocaleString('en-AE')}</td>
                  <td className="text-right">{r.totalBonus.toLocaleString('en-AE')}</td>
                  <td className="text-right font-bold" style={{ color: 'var(--primary)' }}>{r.totalGross.toLocaleString('en-AE')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Department breakdown for the most recent period */}
      {report[0] && Object.keys(report[0].byDept).length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <h3>Department Breakdown — {report[0].period}</h3>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Department</th><th className="text-right">Total (AED)</th><th className="text-right">Share %</th></tr></thead>
              <tbody>
                {Object.entries(report[0].byDept).sort((a,b) => b[1]-a[1]).map(([dept, total]) => (
                  <tr key={dept}>
                    <td>{dept}</td>
                    <td className="text-right font-bold">{total.toLocaleString('en-AE')}</td>
                    <td className="text-right text-muted">{report[0].totalGross > 0 ? `${((total / report[0].totalGross) * 100).toFixed(1)}%` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" onClick={() => exportCSV(payrollCostToRows(report), 'payroll_cost_report.csv')}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" onClick={() => exportPDF('Payroll Cost Report', ['Period','Payment Date','Employees','Basic (AED)','Allowances (AED)','Bonus/Other (AED)','Total Cost (AED)'], payrollCostToRows(report), 'payroll_cost_report.pdf')}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 3. Leave Usage ───────────────────────────────────────────────────────────
function LeaveUsageTab({ employees, leaveRequests }) {
  const [year, setYear] = useState(thisYear);
  const report = buildLeaveUtilizationReport(employees, leaveRequests, year);
  const rows   = leaveUtilToRows(report);

  const years = Array.from({ length: 4 }, (_, i) => thisYear - i);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>Year</label>
        <select className="form-control" style={{ width: 120 }} value={year} onChange={e => setYear(Number(e.target.value))}>
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <span className="text-muted text-sm">{report.length} employee{report.length !== 1 ? 's' : ''} with approved leave</span>
      </div>

      {!report.length ? <EmptyState message={`No approved leave found for ${year}.`} /> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th className="text-right">Requests</th>
                  <th className="text-right">Days Taken</th>
                  <th>Leave Types</th>
                </tr>
              </thead>
              <tbody>
                {report.map(r => (
                  <tr key={r.empId}>
                    <td style={{ fontWeight: 500 }}>{r.name}</td>
                    <td className="text-muted">{r.department}</td>
                    <td className="text-right">{r.requestCount}</td>
                    <td className="text-right font-bold" style={{ color: 'var(--primary)' }}>{r.totalDays}</td>
                    <td className="text-sm text-muted">{Object.entries(r.byType).map(([t, d]) => `${t}: ${d}d`).join(' · ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportCSV(rows, `leave_usage_${year}.csv`)}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportPDF(`Leave Utilization ${year}`, ['Employee','Department','Requests','Total Days Taken','Leave Types'], rows, `leave_usage_${year}.pdf`)}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 4. Attendance Summary ────────────────────────────────────────────────────
function AttendanceTab({ employees, attendanceRecords }) {
  const [period, setPeriod] = useState(thisPeriod);
  const report = buildAttendanceSummaryReport(employees, attendanceRecords, period);
  const rows   = attendanceSummaryToRows(report);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>Period (YYYY-MM)</label>
        <input className="form-control" type="month" style={{ width: 160 }} value={period} onChange={e => setPeriod(e.target.value)} />
        <span className="text-muted text-sm">{report.length} employee{report.length !== 1 ? 's' : ''} with records</span>
      </div>

      {!report.length ? <EmptyState message={`No attendance records found for ${period}.`} /> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th className="text-right">Days</th>
                  <th className="text-right" style={{ color: 'var(--success)' }}>Present</th>
                  <th className="text-right" style={{ color: 'var(--danger)' }}>Absent</th>
                  <th className="text-right" style={{ color: 'var(--warning)' }}>Late</th>
                  <th className="text-right">Early Dep.</th>
                  <th className="text-right">Hours</th>
                </tr>
              </thead>
              <tbody>
                {report.map(r => (
                  <tr key={r.empId}>
                    <td style={{ fontWeight: 500 }}>{r.name}</td>
                    <td className="text-muted">{r.department}</td>
                    <td className="text-right">{r.totalDays}</td>
                    <td className="text-right font-bold" style={{ color: 'var(--success)' }}>{r.present}</td>
                    <td className="text-right font-bold" style={{ color: r.absent > 0 ? 'var(--danger)' : 'var(--gray-400)' }}>{r.absent}</td>
                    <td className="text-right" style={{ color: r.late > 0 ? 'var(--warning)' : 'var(--gray-400)' }}>{r.late}</td>
                    <td className="text-right text-muted">{r.earlyDep}</td>
                    <td className="text-right text-muted">{r.totalHours}h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportCSV(rows, `attendance_${period}.csv`)}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportPDF(`Attendance Summary ${period}`, ['Employee','Department','Days','Present','Absent','Late','Early Dep.','Hours'], rows, `attendance_${period}.pdf`)}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 5. Document Expiry ───────────────────────────────────────────────────────
function DocExpiryTab({ employees, documents }) {
  const [days, setDays] = useState(90);
  const report = buildDocumentExpiryReport(employees, documents, days);
  const rows   = docExpiryToRows(report);

  const STATUS_BADGE = { Expired: 'badge-red', Critical: 'badge-red', Warning: 'badge-amber', 'Expiring Soon': 'badge-yellow' };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>Expiring within</label>
        <select className="form-control" style={{ width: 140 }} value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={30}>30 days</option>
          <option value={60}>60 days</option>
          <option value={90}>90 days</option>
          <option value={180}>180 days</option>
          <option value={365}>1 year</option>
        </select>
        <span className="text-muted text-sm">{report.length} document{report.length !== 1 ? 's' : ''}</span>
      </div>

      {!report.length ? <EmptyState message={`No documents expiring within ${days} days.`} /> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Document Type</th>
                  <th>Expiry Date</th>
                  <th className="text-right">Days Remaining</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {report.map((r, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{r.employee}</td>
                    <td className="text-muted">{r.department}</td>
                    <td>{r.documentType}</td>
                    <td className="font-mono text-sm">{formatDateUAE(r.expiryDate)}</td>
                    <td className="text-right font-bold" style={{ color: r.daysRemaining < 0 ? 'var(--danger)' : r.daysRemaining < 30 ? 'var(--danger)' : r.daysRemaining < 60 ? 'var(--warning)' : 'var(--gray-600)' }}>
                      {r.daysRemaining < 0 ? `${Math.abs(r.daysRemaining)}d ago` : `${r.daysRemaining}d`}
                    </td>
                    <td><span className={`badge ${STATUS_BADGE[r.status] ?? 'badge-yellow'}`}>{r.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportCSV(rows, `doc_expiry_${days}d.csv`)}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportPDF(`Document Expiry Report (${days} days)`, ['Employee','Department','Document Type','Expiry Date','Days Remaining','Status'], rows, `doc_expiry_${days}d.pdf`)}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 6. Salary Movement History ───────────────────────────────────────────────
function SalaryHistoryTab({ employees, jobHistory }) {
  const [startDate, setStartDate] = useState(`${thisYear}-01-01`);
  const [endDate,   setEndDate]   = useState(`${thisYear}-12-31`);

  const report = buildSalaryMovementReport(employees, jobHistory, startDate, endDate);
  const rows   = salaryMovementToRows(report);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>From</label>
        <input className="form-control" type="date" style={{ width: 150 }} value={startDate} onChange={e => setStartDate(e.target.value)} />
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>To</label>
        <input className="form-control" type="date" style={{ width: 150 }} value={endDate} onChange={e => setEndDate(e.target.value)} />
        <span className="text-muted text-sm">{report.length} change{report.length !== 1 ? 's' : ''}</span>
      </div>

      {!report.length ? <EmptyState message="No salary changes found in the selected date range." /> : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Date</th>
                  <th className="text-right">Old Salary</th>
                  <th className="text-right">New Salary</th>
                  <th className="text-right">Change</th>
                  <th className="text-right">%</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {report.map((r, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{r.employee}</td>
                    <td className="text-muted">{r.department}</td>
                    <td className="text-sm">{formatDateUAE(r.changedAt)}</td>
                    <td className="text-right text-muted">{r.oldSalary.toLocaleString('en-AE')}</td>
                    <td className="text-right font-bold">{r.newSalary.toLocaleString('en-AE')}</td>
                    <td className="text-right font-bold" style={{ color: r.change >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                      {r.change >= 0 ? '+' : ''}{r.change.toLocaleString('en-AE')}
                    </td>
                    <td className="text-right text-sm" style={{ color: r.change >= 0 ? 'var(--success)' : 'var(--danger)' }}>{r.changePct}</td>
                    <td className="text-sm text-muted">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportCSV(rows, `salary_history_${startDate}_${endDate}.csv`)}>
          <Download size={13} /> Export CSV
        </button>
        <button className="btn btn-outline btn-sm" disabled={!rows.length} onClick={() => exportPDF('Salary Movement History', ['Employee','Department','Date','Old Salary','New Salary','Change (AED)','Change %','Reason'], rows, `salary_history_${startDate}.pdf`)}>
          <Download size={13} /> Export PDF
        </button>
      </div>
    </div>
  );
}

// ─── 7. Staff Turnover ────────────────────────────────────────────────────────
function TurnoverTab({ employees }) {
  const [startDate, setStartDate] = useState(`${thisYear}-01-01`);
  const [endDate,   setEndDate]   = useState(`${thisYear}-12-31`);

  const { joiners, leavers, avgTenureDays } = buildTurnoverReport(employees, startDate, endDate);
  const joinerRows = turnoverJoinersToRows(joiners);
  const leaverRows = turnoverLeaversToRows(leavers);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>From</label>
        <input className="form-control" type="date" style={{ width: 150 }} value={startDate} onChange={e => setStartDate(e.target.value)} />
        <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-600)' }}>To</label>
        <input className="form-control" type="date" style={{ width: 150 }} value={endDate} onChange={e => setEndDate(e.target.value)} />
      </div>

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Joiners</div>
          <div className="stat-value" style={{ color: 'var(--success)' }}>{joiners.length}</div>
          <div className="stat-sub">New hires in period</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Leavers</div>
          <div className="stat-value" style={{ color: 'var(--danger)' }}>{leavers.length}</div>
          <div className="stat-sub">Terminations in period</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Avg. Tenure (Leavers)</div>
          <div className="stat-value">{leavers.length ? Math.round(avgTenureDays / 30) : '—'}</div>
          <div className="stat-sub">months</div>
        </div>
      </div>

      {joiners.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <h3 style={{ color: 'var(--success)' }}>Joiners ({joiners.length})</h3>
            <button className="btn btn-outline btn-sm" onClick={() => exportCSV(joinerRows, `joiners_${startDate}.csv`)}>
              <Download size={13} /> CSV
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Department</th><th>Start Date</th><th>Job Title</th><th>Contract</th></tr></thead>
              <tbody>
                {joiners.map(e => (
                  <tr key={e.id}>
                    <td style={{ fontWeight: 500 }}>{e.name}</td>
                    <td className="text-muted">{e.department || '—'}</td>
                    <td>{e.employmentStartDate || e.startDate || '—'}</td>
                    <td className="text-muted">{e.jobTitle || '—'}</td>
                    <td>{e.contractType || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {leavers.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 style={{ color: 'var(--danger)' }}>Leavers ({leavers.length})</h3>
            <button className="btn btn-outline btn-sm" onClick={() => exportCSV(leaverRows, `leavers_${startDate}.csv`)}>
              <Download size={13} /> CSV
            </button>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Department</th><th>Start Date</th><th>Termination Date</th><th>Reason</th></tr></thead>
              <tbody>
                {leavers.map(e => (
                  <tr key={e.id}>
                    <td style={{ fontWeight: 500 }}>{e.name}</td>
                    <td className="text-muted">{e.department || '—'}</td>
                    <td>{e.employmentStartDate || e.startDate || '—'}</td>
                    <td style={{ color: 'var(--danger)' }}>{e.terminationDate || '—'}</td>
                    <td className="text-muted text-sm">{e.terminationReason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!joiners.length && !leavers.length && (
        <EmptyState message="No joiners or leavers found in the selected date range." />
      )}
    </div>
  );
}

// ─── 8. Staffing Compliance ────────────────────────────────────────────────────
function StaffingComplianceTab({ employees, staffingRules }) {
  const [month, setMonth]   = useState(thisPeriod);
  const [roster, setRoster] = useState([]);
  const [loading, setLoading] = useState(true);
  const SHIFT_LABELS = { morning: '☀ Morning', afternoon: '🌤 Afternoon', night: '🌙 Night' };

  useEffect(() => {
    setLoading(true);
    const [y, m] = month.split('-').map(Number);
    getRosterForMonth(y, m).then(r => {
      setRoster(r);
      setLoading(false);
    }).catch(() => { setRoster([]); setLoading(false); });
  }, [month]);

  if (!staffingRules.length) {
    return (
      <EmptyState message="No staffing rules defined. Add rules in Departments → Staffing Rules tab." />
    );
  }

  const MonthPicker = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
      <label style={{ fontSize: 13, fontWeight: 600 }}>Month:</label>
      <input type="month" className="form-control" style={{ display: 'inline-block', width: 'auto' }} value={month} onChange={e => setMonth(e.target.value)} />
    </div>
  );

  if (loading) return <div><MonthPicker /><div style={{ padding: 24, textAlign: 'center', color: 'var(--gray-400)' }}>Loading roster…</div></div>;

  if (!roster.length) {
    return (
      <div>
        <MonthPicker />
        <EmptyState message="No roster data for this month. Publish the roster first." />
      </div>
    );
  }

  // Build compliance heatmap: for each rule, for each day — actual vs required
  const [y, m] = month.split('-').map(Number);
  const daysInMonth = new Date(y, m, 0).getDate();
  const days = Array.from({ length: daysInMonth }, (_, i) => {
    const d = i + 1;
    return `${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
  });

  const rows = staffingRules.map(rule => {
    const dayCounts = days.map(dateStr => {
      const count = roster.filter(r => {
        if (r.date !== dateStr) return false;
        const emp = employees.find(e => e.id === r.employeeId);
        if (!emp || emp.department !== rule.department) return false;
        return (r.shift?.shiftCategory || '') === rule.shiftCategory;
      }).length;
      return { dateStr, count, ok: count >= rule.minStaff };
    });
    const violations = dayCounts.filter(d => !d.ok).length;
    return { rule, dayCounts, violations };
  });

  const overallOk = rows.every(r => r.violations === 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: 13, fontWeight: 600 }}>Month:</label>
          <input type="month" className="form-control" style={{ display: 'inline-block', width: 'auto' }} value={month} onChange={e => setMonth(e.target.value)} />
        </div>
        <span className={`badge ${overallOk ? 'badge-green' : 'badge-red'}`}>
          {overallOk ? '✓ Fully Compliant' : `${rows.reduce((s, r) => s + r.violations, 0)} violations`}
        </span>
      </div>

      {rows.map(({ rule, dayCounts, violations }) => (
        <div key={rule.id} className="card" style={{ marginBottom: 16, padding: '14px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div>
              <span style={{ fontWeight: 600 }}>{rule.department}</span>
              <span style={{ fontSize: 12, color: 'var(--gray-500)', marginLeft: 8 }}>{SHIFT_LABELS[rule.shiftCategory] || rule.shiftCategory}</span>
              <span style={{ fontSize: 12, color: 'var(--gray-400)', marginLeft: 8 }}>Min: {rule.minStaff}</span>
            </div>
            <span className={`badge ${violations === 0 ? 'badge-green' : 'badge-red'}`}>
              {violations === 0 ? '✓ Compliant' : `${violations} day${violations > 1 ? 's' : ''} below minimum`}
            </span>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            {dayCounts.map(({ dateStr, count, ok }) => (
              <div
                key={dateStr}
                title={`${dateStr}: ${count} staff (min ${rule.minStaff})`}
                style={{
                  width: 28, height: 28, borderRadius: 4,
                  background: ok ? '#dcfce7' : '#fee2e2',
                  border: `1px solid ${ok ? '#a7f3d0' : '#fca5a5'}`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 600,
                  color: ok ? '#16a34a' : '#dc2626',
                }}
              >
                {count}
              </div>
            ))}
          </div>
          <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 6 }}>
            Each cell = day count (green ≥ min, red &lt; min)
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── WPS Compliance ─────────────────────────────────────────────────────────
function WpsComplianceTab({ payrolls }) {
  const report = buildWpsComplianceReport(payrolls);
  const rows = wpsComplianceToRows(payrolls);
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>WPS Submission Compliance</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => exportCSV(rows, 'wps-compliance.csv')}><Download size={13}/> CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={() => exportPDF('WPS Compliance', Object.keys(rows[0] || {}), rows.map(Object.values), 'wps-compliance.pdf')}><Download size={13}/> PDF</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#2563eb' }}>{report.generated.length}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Generated</div>
        </div>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#10b981' }}>{report.confirmed.length}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Confirmed</div>
        </div>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#f59e0b' }}>{report.pending.length}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Pending</div>
        </div>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: report.complianceRate >= 80 ? '#10b981' : '#ef4444' }}>{report.complianceRate}%</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Compliance Rate</div>
        </div>
      </div>
      {rows.length === 0 ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No generated payroll runs yet.</p> : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table"><thead><tr>{Object.keys(rows[0]).map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Emiratization ──────────────────────────────────────────────────────────
function EmiratizationTab({ employees }) {
  const report = buildEmiratizationReport(employees);
  const rows = emiratizationToRows(employees);
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>Emiratization / Nafis Compliance</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => exportCSV(rows, 'emiratization.csv')}><Download size={13}/> CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={() => exportPDF('Emiratization Report', Object.keys(rows[0] || {}), rows.map(Object.values), 'emiratization.pdf')}><Download size={13}/> PDF</button>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#2563eb' }}>{report.active.length}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Total Active</div>
        </div>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#10b981' }}>{report.emiratis.length}</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>UAE Nationals</div>
        </div>
        <div className="card" style={{ padding: 14, flex: 1, minWidth: 120, textAlign: 'center' }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: parseFloat(report.ratio) >= 2 ? '#10b981' : '#ef4444' }}>{report.ratio}%</div>
          <div style={{ fontSize: 11, color: '#64748b' }}>Emiratization Rate</div>
        </div>
      </div>
      <h4 style={{ fontSize: 12, fontWeight: 600, color: '#475569', marginBottom: 8 }}>By Department</h4>
      <div style={{ overflowX: 'auto', marginBottom: 16 }}>
        <table className="table"><thead><tr><th>Department</th><th>Total</th><th>Emirati</th><th>Rate</th></tr></thead>
          <tbody>{Object.entries(report.byDept).map(([d, v]) => (
            <tr key={d}><td>{d}</td><td>{v.total}</td><td>{v.emirati}</td><td>{v.total ? (v.emirati/v.total*100).toFixed(1) : 0}%</td></tr>
          ))}</tbody>
        </table>
      </div>
      {rows.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table className="table"><thead><tr>{Object.keys(rows[0]).map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── EOS Liability ──────────────────────────────────────────────────────────
function EOSLiabilityTab({ employees }) {
  const report = buildEOSLiabilityReport(employees);
  const rows = eosLiabilityToRows(report.items);
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>End-of-Service Liability</h3>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => exportCSV(rows, 'eos-liability.csv')}><Download size={13}/> CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={() => exportPDF('EOS Liability', Object.keys(rows[0] || {}), rows.map(Object.values), 'eos-liability.pdf')}><Download size={13}/> PDF</button>
        </div>
      </div>
      <div className="card" style={{ padding: 16, marginBottom: 16, textAlign: 'center', background: 'rgba(37,99,235,0.04)' }}>
        <div style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>Total EOS Liability (all active employees)</div>
        <div style={{ fontSize: 28, fontWeight: 700, color: '#2563eb' }}>AED {report.totalLiability.toLocaleString('en-AE', { minimumFractionDigits: 2 })}</div>
      </div>
      {rows.length === 0 ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No active employees.</p> : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table"><thead><tr>{Object.keys(rows[0]).map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Leave Balance ──────────────────────────────────────────────────────────
function LeaveBalanceTab({ employees, leaveRequests }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const balanceData = buildLeaveBalanceReport(employees, leaveRequests, year);
  const rows = leaveBalanceToRows(balanceData);
  return (
    <div className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: '#1e293b' }}>Leave Balance Report</h3>
          <select className="form-control" style={{ width: 100 }} value={year} onChange={e => setYear(parseInt(e.target.value))}>
            {[0, 1, 2].map(offset => {
              const y = new Date().getFullYear() - offset;
              return <option key={y} value={y}>{y}</option>;
            })}
          </select>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => exportCSV(rows, `leave-balance-${year}.csv`)}><Download size={13}/> CSV</button>
          <button className="btn btn-ghost btn-sm" onClick={() => exportPDF(`Leave Balance ${year}`, Object.keys(rows[0] || {}), rows.map(Object.values), `leave-balance-${year}.pdf`)}><Download size={13}/> PDF</button>
        </div>
      </div>
      {rows.length === 0 ? <p style={{ color: '#94a3b8', fontSize: 13 }}>No active employees.</p> : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table"><thead><tr>{Object.keys(rows[0]).map(h => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{rows.map((r, i) => <tr key={i}>{Object.values(r).map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Main Reports component ───────────────────────────────────────────────────
export default function Reports() {
  const { activeCompany } = useCompany();
  const TABS = ALL_TABS.filter(t => {
    if (t.feature === 'nafis'    && activeCompany?.enableNafis         === false) return false;
    if (t.feature === 'staffing' && activeCompany?.enableStaffingRules === false) return false;
    return true;
  });
  const [tab, setTab]         = useState('headcount');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const [employees,         setEmployees]         = useState([]);
  const [payrolls,          setPayrolls]          = useState([]);
  const [leaveRequests,     setLeaveRequests]     = useState([]);
  const [attendanceRecords, setAttendanceRecords] = useState([]);
  const [documents,         setDocuments]         = useState([]);
  const [jobHistory,        setJobHistory]        = useState([]);
  const [staffingRules,     setStaffingRules]     = useState([]);

  useEffect(() => {
    Promise.all([
      getEmployees(),
      getPayrolls(),
      getLeaveRequests(),
      getAttendanceRecords(),
      getAllEmployeeDocuments(),
      getAllJobHistory(),
      getDeptStaffingRules().catch(() => []),
    ]).then(([emps, pays, leaves, attn, docs, hist, rules]) => {
      setEmployees(emps);
      setPayrolls(pays);
      setLeaveRequests(leaves);
      setAttendanceRecords(attn);
      setDocuments(docs);
      setJobHistory(hist);
      setStaffingRules(rules);
      setLoading(false);
    }).catch(err => {
      console.error('Reports load failed:', err);
      setError(err.message);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading reports…</div>;
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <div className="alert alert-danger">
          <AlertCircle size={16} /> Failed to load report data: {error}
        </div>
      </div>
    );
  }

  const renderTab = () => {
    switch (tab) {
      case 'headcount':  return <HeadcountTab  employees={employees} />;
      case 'payroll':    return <PayrollCostTab payrolls={payrolls} employees={employees} />;
      case 'leave':      return <LeaveUsageTab  employees={employees} leaveRequests={leaveRequests} />;
      case 'attendance': return <AttendanceTab  employees={employees} attendanceRecords={attendanceRecords} />;
      case 'documents':  return <DocExpiryTab   employees={employees} documents={documents} />;
      case 'salary':     return <SalaryHistoryTab employees={employees} jobHistory={jobHistory} />;
      case 'turnover':   return <TurnoverTab    employees={employees} />;
      case 'staffing':   return <StaffingComplianceTab employees={employees} staffingRules={staffingRules} />;
      case 'wps':          return <WpsComplianceTab payrolls={payrolls} />;
      case 'emiratization': return <EmiratizationTab employees={employees} />;
      case 'eos':          return <EOSLiabilityTab employees={employees} />;
      case 'leaveBalance': return <LeaveBalanceTab employees={employees} leaveRequests={leaveRequests} />;
      default:           return null;
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2><BarChart2 size={18} style={{ marginRight: 8, display: 'inline' }} />HR Reports & Analytics</h2>
        <span className="text-muted text-sm">{employees.filter(e => e.active).length} active employees</span>
      </div>

      <div className="page-body">
        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 20, flexWrap: 'wrap', borderBottom: '2px solid var(--gray-100)', paddingBottom: 4 }}>
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                className={`btn btn-sm ${tab === t.id ? 'btn-primary' : 'btn-ghost'}`}
                style={{ borderRadius: 8, gap: 5 }}
                onClick={() => setTab(t.id)}
              >
                <Icon size={13} /> {t.label}
              </button>
            );
          })}
        </div>

        {renderTab()}
      </div>
    </div>
  );
}
