/**
 * ClinicalDashboard.jsx — Feature 4.1: Clinical HR Dashboard with Drill-Down KPI Cards
 *
 * Clinic-specific metrics powered entirely by existing data — no new SQL needed.
 * Six KPI cards; clicking any card expands a drill-down panel with the raw employee
 * or document rows that make up that number.
 *
 * Data sources:
 *   getEmployees()            → headcount, probation, joiners, dept breakdown
 *   getAllEmployeeDocuments()  → credential compliance, expiry pipeline
 *   getRosterForMonth()       → today's shift coverage
 *   getDepartments()          → department colors / labels
 *   CLINICAL_DOC_TYPES        → which document types count as clinical credentials
 */
import { useState, useEffect, useMemo } from 'react';
import {
  Users, ShieldCheck, AlertTriangle, XCircle,
  CalendarClock, UserCheck, RefreshCw, ChevronDown, ChevronUp,
  UserPlus, Cake, BedDouble, Clock, ClipboardList, CheckCircle,
} from 'lucide-react';
import { getEmployees, getAllEmployeeDocuments } from '../utils/storage';
import { getRosterForMonth, getAttendanceRecords } from '../utils/attendanceStorage';
import { getLeaveRequests } from '../utils/leaveStorage';
import { getDepartments } from '../utils/departmentStorage';
import { CLINICAL_DOC_TYPES } from './EmployeeModal';

// ── Helpers ───────────────────────────────────────────────────────────────────

const today = () => new Date().toISOString().split('T')[0];

function daysUntil(dateStr) {
  if (!dateStr) return null;
  return Math.ceil((new Date(dateStr) - new Date(today())) / 86_400_000);
}

function credentialStatus(expiryDate) {
  const d = daysUntil(expiryDate);
  if (d === null) return 'none';
  if (d < 0)  return 'expired';
  if (d <= 90) return 'expiring';
  return 'valid';
}

const EXPIRY_BADGE = {
  expired:  { cls: 'badge-red',   label: 'Expired'  },
  expiring: { cls: 'badge-amber', label: 'Expiring' },
  valid:    { cls: 'badge-green', label: 'Valid'    },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({ icon: Icon, iconBg, iconColor, value, label, sub, active, onClick }) {
  return (
    <div
      className="stat-card"
      onClick={onClick}
      style={{
        cursor: 'pointer',
        outline: active ? '2px solid var(--primary)' : 'none',
        outlineOffset: 2,
        transition: 'outline 0.15s',
      }}
    >
      <div className="stat-icon" style={{ background: iconBg }}>
        <Icon size={20} color={iconColor} />
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
      <div style={{ marginLeft: 'auto', color: 'var(--gray-400)', alignSelf: 'center' }}>
        {active ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>
    </div>
  );
}

function DrillTable({ children, emptyText }) {
  return (
    <div className="card" style={{ marginTop: 12, padding: 0, overflow: 'hidden' }}>
      {children || (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--gray-400)' }}>
          {emptyText || 'No records.'}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ClinicalDashboard() {
  const [employees,    setEmployees]    = useState([]);
  const [documents,    setDocuments]    = useState([]);
  const [roster,       setRoster]       = useState([]);
  const [departments,  setDepartments]  = useState([]);
  const [leaveReqs,    setLeaveReqs]    = useState([]);
  const [todayAttendance, setTodayAttendance] = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [drill,        setDrill]        = useState(null); // active KPI id

  const load = async () => {
    setLoading(true);
    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];
    const [emps, docs, rosterData, depts, leaves, todayRecs] = await Promise.all([
      getEmployees().catch(() => []),
      getAllEmployeeDocuments().catch(() => []),
      getRosterForMonth(now.getFullYear(), now.getMonth() + 1).catch(() => []),
      getDepartments().catch(() => []),
      getLeaveRequests({ status: 'Approved' }).catch(() => []),
      getAttendanceRecords({ dateFrom: todayStr, dateTo: todayStr }).catch(() => []),
    ]);
    setEmployees(emps);
    setDocuments(docs);
    setRoster(rosterData);
    setDepartments(depts);
    setLeaveReqs(leaves);
    setTodayAttendance(todayRecs);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  // ── Derived metrics ────────────────────────────────────────────────────────

  const metrics = useMemo(() => {
    const todayStr   = today();
    const nowDate    = new Date();
    const thisMonth  = `${nowDate.getFullYear()}-${String(nowDate.getMonth() + 1).padStart(2, '0')}`;
    const todayMMDD  = todayStr.slice(5); // MM-DD for birthday matching

    const activeEmps = employees.filter(e => e.active !== false && e.employmentStatus !== 'Terminated');

    // Build doc index per employee: employee_id → [{documentType, expiryDate, ...}]
    const clinicalDocsByEmp = {};
    for (const doc of documents) {
      if (!CLINICAL_DOC_TYPES.has(doc.documentType)) continue;
      if (!clinicalDocsByEmp[doc.employeeId]) clinicalDocsByEmp[doc.employeeId] = [];
      clinicalDocsByEmp[doc.employeeId].push(doc);
    }

    // Credential compliance
    const withValidCred   = [];
    const withExpiredCred = [];
    const noCredentials   = [];

    for (const emp of activeEmps) {
      const docs = clinicalDocsByEmp[emp.id] || [];
      if (docs.length === 0) {
        noCredentials.push(emp);
        continue;
      }
      const hasValid   = docs.some(d => credentialStatus(d.expiryDate) === 'valid');
      const hasExpired = docs.some(d => credentialStatus(d.expiryDate) === 'expired');
      if (hasValid) withValidCred.push(emp);
      if (hasExpired && !hasValid) withExpiredCred.push(emp);
    }

    const credentialTotal  = withValidCred.length + withExpiredCred.length;
    const complianceRate   = credentialTotal === 0 ? null
      : Math.round(withValidCred.length / credentialTotal * 100);

    // Expiring docs (clinical, within 90 days, not expired)
    const expiringDocs = documents.filter(d => {
      if (!CLINICAL_DOC_TYPES.has(d.documentType)) return false;
      const s = credentialStatus(d.expiryDate);
      return s === 'expiring';
    }).map(d => ({
      ...d,
      empName: activeEmps.find(e => e.id === d.employeeId)?.name || '—',
      daysLeft: daysUntil(d.expiryDate),
    })).sort((a, b) => a.daysLeft - b.daysLeft);

    // Expired clinical docs
    const expiredDocs = documents.filter(d => {
      if (!CLINICAL_DOC_TYPES.has(d.documentType)) return false;
      return credentialStatus(d.expiryDate) === 'expired';
    }).map(d => ({
      ...d,
      empName: activeEmps.find(e => e.id === d.employeeId)?.name || '—',
      daysLeft: daysUntil(d.expiryDate),
    }));

    // Today's roster
    const todayRoster = roster.filter(r => r.date === todayStr);
    const rosteredEmpIds = new Set(todayRoster.map(r => r.employeeId));
    const rosteredEmps   = activeEmps.filter(e => rosteredEmpIds.has(e.id));
    const unrosteredEmps = activeEmps.filter(e => !rosteredEmpIds.has(e.id));
    const coveragePct    = activeEmps.length === 0 ? 0
      : Math.round(rosteredEmps.length / activeEmps.length * 100);

    // Probation
    const probationEmps = activeEmps.filter(e => e.employmentStatus === 'Probation');

    // This month's joiners
    const joinersThisMonth = activeEmps.filter(e =>
      e.joiningDate && e.joiningDate.startsWith(thisMonth)
    );

    // Department breakdown
    const deptMap = {};
    for (const emp of activeEmps) {
      const key = emp.department || 'Unassigned';
      if (!deptMap[key]) deptMap[key] = { count: 0, withCreds: 0, deptObj: null };
      deptMap[key].count++;
      if (clinicalDocsByEmp[emp.id]?.some(d => credentialStatus(d.expiryDate) === 'valid')) {
        deptMap[key].withCreds++;
      }
    }
    for (const dept of departments) {
      if (deptMap[dept.name]) deptMap[dept.name].deptObj = dept;
    }
    const deptBreakdown = Object.entries(deptMap)
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.count - a.count);

    // Birthdays this month (compare MM portion of date_of_birth)
    const thisMonthNum = String(nowDate.getMonth() + 1).padStart(2, '0');
    const birthdaysThisMonth = activeEmps.filter(e => {
      if (!e.dateOfBirth) return false;
      return e.dateOfBirth.slice(5, 7) === thisMonthNum;
    }).map(e => {
      const birthdayThisYear = `${nowDate.getFullYear()}-${e.dateOfBirth.slice(5)}`;
      const daysUntilBday = Math.ceil((new Date(birthdayThisYear) - nowDate) / 86_400_000);
      return { ...e, daysUntilBday };
    }).sort((a, b) => a.daysUntilBday - b.daysUntilBday);

    // On leave today (approved leave requests spanning today)
    const onLeaveToday = activeEmps.filter(e => {
      return leaveReqs.some(r =>
        r.employeeId === e.id &&
        r.status === 'Approved' &&
        r.startDate <= todayStr &&
        r.endDate >= todayStr
      );
    });

    // Pending leave requests
    const pendingLeave = leaveReqs.filter(r => r.status === 'Pending' || r.status === 'ManagerApproved');
    const pendingLeaveEmps = pendingLeave.map(r => ({
      ...r,
      empName: activeEmps.find(e => e.id === r.employeeId)?.name || '—',
    }));

    // Staff on duty now (clocked in today, no clock-out)
    const onDutyNow = todayAttendance.filter(r => r.clockInTime && !r.clockOutTime).map(r => ({
      ...r,
      empName: activeEmps.find(e => e.id === r.employeeId)?.name || '—',
    }));

    // Confirmed / Permanent staff
    const confirmedEmps = activeEmps.filter(e =>
      e.employmentStatus === 'Active' || e.employmentStatus === 'Full-Time'
    );

    return {
      activeEmps, withValidCred, withExpiredCred, noCredentials,
      complianceRate, credentialTotal,
      expiringDocs, expiredDocs,
      todayRoster, rosteredEmps, unrosteredEmps, coveragePct,
      probationEmps, joinersThisMonth,
      birthdaysThisMonth, onLeaveToday, pendingLeaveEmps, onDutyNow, confirmedEmps,
      deptBreakdown,
    };
  }, [employees, documents, roster, departments, leaveReqs, todayAttendance]);

  const toggle = (id) => setDrill(prev => prev === id ? null : id);

  if (loading) {
    return (
      <div>
        <div className="page-header"><h2>Clinical Dashboard</h2></div>
        <div className="page-body" style={{ textAlign: 'center', paddingTop: 60, color: 'var(--gray-400)' }}>
          Loading clinical metrics…
        </div>
      </div>
    );
  }

  const { activeEmps, withValidCred, withExpiredCred, noCredentials,
          complianceRate, expiringDocs, expiredDocs,
          todayRoster, rosteredEmps, unrosteredEmps, coveragePct,
          probationEmps, joinersThisMonth,
          birthdaysThisMonth, onLeaveToday, pendingLeaveEmps, onDutyNow, confirmedEmps,
          deptBreakdown } = metrics;

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Clinical Dashboard</h2>
          <p className="text-muted text-sm">
            Real-time clinical HR metrics — click any card to drill down
          </p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={load}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="page-body">

        {/* ── KPI cards ── */}
        <div className="stats-grid mb-2" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>

          {/* 1. Active Headcount */}
          <KpiCard
            icon={Users}
            iconBg="rgba(37,99,235,0.10)" iconColor="var(--primary)"
            value={activeEmps.length}
            label="Active Staff"
            sub={`${joinersThisMonth.length} joined this month`}
            active={drill === 'headcount'}
            onClick={() => toggle('headcount')}
          />

          {/* 2. Credential Compliance */}
          <KpiCard
            icon={ShieldCheck}
            iconBg={complianceRate === null ? 'rgba(107,114,128,0.10)'
              : complianceRate >= 90 ? 'rgba(22,163,74,0.10)'
              : complianceRate >= 70 ? 'rgba(245,158,11,0.10)'
              : 'rgba(220,38,38,0.10)'}
            iconColor={complianceRate === null ? 'var(--gray-400)'
              : complianceRate >= 90 ? 'var(--success)'
              : complianceRate >= 70 ? 'var(--warning)'
              : 'var(--danger)'}
            value={complianceRate === null ? '—' : `${complianceRate}%`}
            label="Credential Compliance"
            sub={complianceRate === null ? 'No credentials on file'
              : `${withValidCred.length} of ${withValidCred.length + withExpiredCred.length} credentialled`}
            active={drill === 'compliance'}
            onClick={() => toggle('compliance')}
          />

          {/* 3. Licences Expiring ≤90 days */}
          <KpiCard
            icon={AlertTriangle}
            iconBg="rgba(245,158,11,0.10)" iconColor="var(--warning)"
            value={expiringDocs.length}
            label="Licences Expiring Soon"
            sub="Within 90 days"
            active={drill === 'expiring'}
            onClick={() => toggle('expiring')}
          />

          {/* 4. Expired Licences */}
          <KpiCard
            icon={XCircle}
            iconBg="rgba(220,38,38,0.10)" iconColor="var(--danger)"
            value={expiredDocs.length}
            label="Expired Credentials"
            sub={`${withExpiredCred.length} staff affected`}
            active={drill === 'expired'}
            onClick={() => toggle('expired')}
          />

          {/* 5. Today's Roster Coverage */}
          <KpiCard
            icon={CalendarClock}
            iconBg={coveragePct >= 80 ? 'rgba(22,163,74,0.10)' : 'rgba(245,158,11,0.10)'}
            iconColor={coveragePct >= 80 ? 'var(--success)' : 'var(--warning)'}
            value={`${rosteredEmps.length}/${activeEmps.length}`}
            label="Today's Coverage"
            sub={`${coveragePct}% rostered`}
            active={drill === 'roster'}
            onClick={() => toggle('roster')}
          />

          {/* 6. On Probation */}
          <KpiCard
            icon={UserCheck}
            iconBg="rgba(99,102,241,0.10)" iconColor="#6366f1"
            value={probationEmps.length}
            label="On Probation"
            sub={probationEmps.length === 0 ? 'None' : 'Click to review'}
            active={drill === 'probation'}
            onClick={() => toggle('probation')}
          />

          {/* 7. New Joiners This Month */}
          <KpiCard
            icon={UserPlus}
            iconBg="rgba(6,182,212,0.10)" iconColor="var(--accent)"
            value={joinersThisMonth.length}
            label="New Joiners This Month"
            sub={joinersThisMonth.length === 0 ? 'No new hires this month' : `Joined in ${new Date().toLocaleString('default',{month:'long'})}`}
            active={drill === 'joiners'}
            onClick={() => toggle('joiners')}
          />

          {/* 8. Birthdays This Month */}
          <KpiCard
            icon={Cake}
            iconBg="rgba(236,72,153,0.10)" iconColor="#ec4899"
            value={birthdaysThisMonth.length}
            label="Birthdays This Month"
            sub={birthdaysThisMonth.length === 0 ? 'No birthdays recorded' : 'Click to see who'}
            active={drill === 'birthdays'}
            onClick={() => toggle('birthdays')}
          />

          {/* 9. On Leave Today */}
          <KpiCard
            icon={BedDouble}
            iconBg="rgba(245,158,11,0.10)" iconColor="var(--warning)"
            value={onLeaveToday.length}
            label="On Leave Today"
            sub={onLeaveToday.length === 0 ? 'Full team available' : 'Click to see who'}
            active={drill === 'on-leave'}
            onClick={() => toggle('on-leave')}
          />

          {/* 10. Pending Leave Requests */}
          <KpiCard
            icon={ClipboardList}
            iconBg={pendingLeaveEmps.length > 0 ? 'rgba(220,38,38,0.10)' : 'rgba(107,114,128,0.10)'}
            iconColor={pendingLeaveEmps.length > 0 ? 'var(--danger)' : 'var(--gray-400)'}
            value={pendingLeaveEmps.length}
            label="Pending Leave Requests"
            sub={pendingLeaveEmps.length === 0 ? 'None outstanding' : 'Requires approval'}
            active={drill === 'pending-leave'}
            onClick={() => toggle('pending-leave')}
          />

          {/* 11. Staff on Duty Now */}
          <KpiCard
            icon={Clock}
            iconBg="rgba(22,163,74,0.10)" iconColor="var(--success)"
            value={onDutyNow.length}
            label="Staff on Duty Now"
            sub={`${onDutyNow.length} clocked in, no clock-out`}
            active={drill === 'on-duty'}
            onClick={() => toggle('on-duty')}
          />

        </div>

        {/* ── Drill-down panels ── */}

        {drill === 'headcount' && (
          <DrillTable>
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Job Title</th>
                  <th>Department</th>
                  <th>Status</th>
                  <th>Joining Date</th>
                </tr>
              </thead>
              <tbody>
                {activeEmps.map(e => (
                  <tr key={e.id}>
                    <td style={{ fontWeight: 500 }}>{e.name}</td>
                    <td>{e.jobTitle || '—'}</td>
                    <td>{e.department || '—'}</td>
                    <td><span className="badge badge-green">{e.employmentStatus || 'Active'}</span></td>
                    <td style={{ color: 'var(--gray-500)', fontSize: 13 }}>{e.joiningDate || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DrillTable>
        )}

        {drill === 'compliance' && (
          <DrillTable emptyText="No employees with clinical credentials on file.">
            {(withExpiredCred.length > 0 || noCredentials.length > 0) ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Issue</th>
                  </tr>
                </thead>
                <tbody>
                  {withExpiredCred.map(e => (
                    <tr key={e.id} style={{ background: '#fff5f5' }}>
                      <td style={{ fontWeight: 500 }}>{e.name}</td>
                      <td>{e.department || '—'}</td>
                      <td>
                        <span className="badge badge-red">Expired credential — no valid licence</span>
                      </td>
                    </tr>
                  ))}
                  {noCredentials.map(e => (
                    <tr key={e.id}>
                      <td style={{ fontWeight: 500 }}>{e.name}</td>
                      <td>{e.department || '—'}</td>
                      <td>
                        <span className="badge badge-amber">No clinical credentials on file</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div style={{ padding: 32, textAlign: 'center', color: 'var(--success)' }}>
                All credentialled staff have at least one valid licence. ✓
              </div>
            )}
          </DrillTable>
        )}

        {drill === 'expiring' && (
          <DrillTable emptyText="No clinical licences expiring within 90 days.">
            {expiringDocs.length > 0 && (
              <table className="table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Credential Type</th>
                    <th>Expiry Date</th>
                    <th>Days Left</th>
                  </tr>
                </thead>
                <tbody>
                  {expiringDocs.map(d => (
                    <tr key={d.id}>
                      <td style={{ fontWeight: 500 }}>{d.empName}</td>
                      <td>{d.documentType}</td>
                      <td>{d.expiryDate}</td>
                      <td>
                        <span className={`badge ${d.daysLeft <= 30 ? 'badge-red' : 'badge-amber'}`}>
                          {d.daysLeft}d
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'expired' && (
          <DrillTable emptyText="No expired clinical credentials.">
            {expiredDocs.length > 0 && (
              <table className="table">
                <thead>
                  <tr>
                    <th>Employee</th>
                    <th>Credential Type</th>
                    <th>Expired</th>
                    <th>Days Overdue</th>
                  </tr>
                </thead>
                <tbody>
                  {expiredDocs.map(d => (
                    <tr key={d.id} style={{ background: '#fff5f5' }}>
                      <td style={{ fontWeight: 500 }}>{d.empName}</td>
                      <td>{d.documentType}</td>
                      <td>{d.expiryDate}</td>
                      <td>
                        <span className="badge badge-red">{Math.abs(d.daysLeft)}d overdue</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'roster' && (
          <DrillTable>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--gray-100)', fontSize: 13, color: 'var(--gray-500)' }}>
              {today()} — {rosteredEmps.length} rostered, {unrosteredEmps.length} unrostered
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Roster Status</th>
                  <th>Shift</th>
                </tr>
              </thead>
              <tbody>
                {rosteredEmps.map(e => {
                  const assignment = todayRoster.find(r => r.employeeId === e.id);
                  return (
                    <tr key={e.id}>
                      <td style={{ fontWeight: 500 }}>{e.name}</td>
                      <td>{e.department || '—'}</td>
                      <td><span className="badge badge-green">Rostered</span></td>
                      <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>
                        {assignment?.shiftName || assignment?.shiftId || '—'}
                      </td>
                    </tr>
                  );
                })}
                {unrosteredEmps.map(e => (
                  <tr key={e.id} style={{ opacity: 0.6 }}>
                    <td style={{ fontWeight: 500 }}>{e.name}</td>
                    <td>{e.department || '—'}</td>
                    <td><span className="badge badge-amber">Unrostered</span></td>
                    <td>—</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DrillTable>
        )}

        {drill === 'probation' && (
          <DrillTable emptyText="No staff currently on probation.">
            {probationEmps.length > 0 && (
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Probation End</th>
                    <th>Days Remaining</th>
                  </tr>
                </thead>
                <tbody>
                  {probationEmps
                    .sort((a, b) => (a.probationEndDate || '').localeCompare(b.probationEndDate || ''))
                    .map(e => {
                      const days = daysUntil(e.probationEndDate);
                      return (
                        <tr key={e.id} style={days !== null && days <= 14 ? { background: '#fffbeb' } : {}}>
                          <td style={{ fontWeight: 500 }}>{e.name}</td>
                          <td>{e.department || '—'}</td>
                          <td>{e.probationEndDate || '—'}</td>
                          <td>
                            {days === null ? '—' : (
                              <span className={`badge ${days < 0 ? 'badge-red' : days <= 14 ? 'badge-amber' : 'badge-blue'}`}>
                                {days < 0 ? `${Math.abs(days)}d overdue` : `${days}d left`}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'joiners' && (
          <DrillTable emptyText="No new joiners this month.">
            {joinersThisMonth.length > 0 && (
              <table className="table">
                <thead><tr><th>Name</th><th>Job Title</th><th>Department</th><th>Joining Date</th></tr></thead>
                <tbody>
                  {joinersThisMonth.map(e => (
                    <tr key={e.id}>
                      <td style={{ fontWeight: 500 }}>{e.name}</td>
                      <td>{e.jobTitle || '—'}</td>
                      <td>{e.department || '—'}</td>
                      <td><span className="badge badge-blue">{e.joiningDate}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'birthdays' && (
          <DrillTable emptyText="No birthday records this month. Add dates of birth in employee profiles.">
            {birthdaysThisMonth.length > 0 && (
              <table className="table">
                <thead><tr><th>Name</th><th>Department</th><th>Date of Birth</th><th>Status</th></tr></thead>
                <tbody>
                  {birthdaysThisMonth.map(e => (
                    <tr key={e.id}>
                      <td style={{ fontWeight: 500 }}>{e.name}</td>
                      <td>{e.department || '—'}</td>
                      <td>{e.dateOfBirth}</td>
                      <td>
                        {e.daysUntilBday === 0
                          ? <span className="badge badge-green">🎂 Today!</span>
                          : e.daysUntilBday > 0
                            ? <span className="badge badge-blue">In {e.daysUntilBday}d</span>
                            : <span className="badge badge-amber">Was {Math.abs(e.daysUntilBday)}d ago</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'on-leave' && (
          <DrillTable emptyText="No approved leave today.">
            {onLeaveToday.length > 0 && (
              <table className="table">
                <thead><tr><th>Name</th><th>Department</th><th>Leave Type</th><th>Returns</th></tr></thead>
                <tbody>
                  {onLeaveToday.map(e => {
                    const req = leaveReqs.find(r => r.employeeId === e.id && r.startDate <= today() && r.endDate >= today());
                    return (
                      <tr key={e.id} style={{ background: '#fffbeb' }}>
                        <td style={{ fontWeight: 500 }}>{e.name}</td>
                        <td>{e.department || '—'}</td>
                        <td>{req?.leaveType || '—'}</td>
                        <td style={{ fontSize: 13, color: 'var(--gray-500)' }}>{req?.endDate || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'pending-leave' && (
          <DrillTable emptyText="No pending leave requests.">
            {pendingLeaveEmps.length > 0 && (
              <table className="table">
                <thead><tr><th>Employee</th><th>Leave Type</th><th>From</th><th>To</th><th>Status</th></tr></thead>
                <tbody>
                  {pendingLeaveEmps.map(r => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 500 }}>{r.empName}</td>
                      <td>{r.leaveType}</td>
                      <td>{r.startDate}</td>
                      <td>{r.endDate}</td>
                      <td>
                        <span className={`badge ${r.status === 'ManagerApproved' ? 'badge-blue' : 'badge-amber'}`}>
                          {r.status === 'ManagerApproved' ? 'Mgr Approved' : 'Pending'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {drill === 'on-duty' && (
          <DrillTable emptyText="No staff currently clocked in.">
            {onDutyNow.length > 0 && (
              <table className="table">
                <thead><tr><th>Employee</th><th>Clocked In</th><th>Dept</th></tr></thead>
                <tbody>
                  {onDutyNow.map(r => {
                    const emp = activeEmps.find(e => e.id === r.employeeId);
                    return (
                      <tr key={r.id}>
                        <td style={{ fontWeight: 500 }}>{r.empName}</td>
                        <td style={{ fontSize: 13 }}>{r.clockInTime ? r.clockInTime.slice(11, 16) : '—'}</td>
                        <td>{emp?.department || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </DrillTable>
        )}

        {/* ── Department breakdown ── */}
        <div className="card mt-4">
          <h3 style={{ marginBottom: 16, fontSize: 15, fontWeight: 600 }}>Department Headcount</h3>
          {deptBreakdown.length === 0 ? (
            <p className="text-muted text-sm">No department data. Add employees or configure departments.</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Department</th>
                  <th>Headcount</th>
                  <th>Credentialled Staff</th>
                  <th>Compliance</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                {deptBreakdown.map(({ name, count, withCreds, deptObj }) => {
                  const pct = count === 0 ? null : Math.round(withCreds / count * 100);
                  const deptColor = deptObj?.color || '#6366f1';
                  const todayInDept = rosteredEmps.filter(e => e.department === name).length;
                  const covPct = count === 0 ? 0 : Math.round(todayInDept / count * 100);
                  return (
                    <tr key={name}>
                      <td>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: 6,
                          fontWeight: 500,
                        }}>
                          <span style={{
                            width: 10, height: 10, borderRadius: '50%',
                            background: deptColor, flexShrink: 0,
                          }} />
                          {name}
                        </span>
                      </td>
                      <td>{count}</td>
                      <td>{withCreds}</td>
                      <td>
                        {pct === null ? <span className="text-muted">—</span> : (
                          <span className={`badge ${pct >= 90 ? 'badge-green' : pct >= 70 ? 'badge-amber' : 'badge-red'}`}>
                            {pct}%
                          </span>
                        )}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{
                            flex: 1, height: 6, borderRadius: 4,
                            background: 'var(--gray-100)', maxWidth: 80,
                          }}>
                            <div style={{
                              width: `${covPct}%`, height: '100%', borderRadius: 4,
                              background: covPct >= 80 ? 'var(--success)' : 'var(--warning)',
                              transition: 'width 0.4s ease',
                            }} />
                          </div>
                          <span style={{ fontSize: 12, color: 'var(--gray-500)', whiteSpace: 'nowrap' }}>
                            {todayInDept}/{count}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  );
}
