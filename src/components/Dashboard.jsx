import { useState, useEffect } from 'react';
import { Building2, Users, FileText, CheckCircle, AlertCircle, ArrowRight, Clock, ShieldAlert, ShieldCheck } from 'lucide-react';
import { getCompany, getEmployees, getPayrolls } from '../utils/storage';
import NafisReportModal from './NafisReportModal';

export default function Dashboard({ onNavigate }) {
  const [company, setCompany]     = useState(null);
  const [employees, setEmployees] = useState([]);
  const [payrolls, setPayrolls]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showNafisReport, setShowNafisReport] = useState(false);

  useEffect(() => {
    Promise.all([getCompany(), getEmployees(), getPayrolls()]).then(([co, emps, pays]) => {
      setCompany(co);
      setEmployees(emps);
      setPayrolls(pays);
      setLoading(false);
    });
  }, []);

  const activeEmps    = employees.filter(e => e.active !== false && e.employmentStatus !== 'Terminated');
  const generatedRuns = payrolls.filter(p => p.status === 'generated');

  // ── Emiratization / Nafis compliance (Cabinet Resolution No. 27 of 2023) ──
  const emiratiEmps     = activeEmps.filter(e => e.nationality === 'United Arab Emirates');
  const emiratiCount    = emiratiEmps.length;
  const totalHeadcount  = activeEmps.length;
  const nafisRequired   = parseFloat(company?.nafisQuotaPercent) || 2;
  const nafisRatio      = totalHeadcount > 0 ? (emiratiCount / totalHeadcount) * 100 : 0;
  const nafisCompliant  = nafisRatio >= nafisRequired;
  const nafisGap        = Math.max(0, Math.ceil((nafisRequired / 100) * totalHeadcount) - emiratiCount);
  const nafisFine       = nafisGap * 6000;
  const draftRuns     = payrolls.filter(p => p.status !== 'generated');

  const recentPayrolls = [...payrolls]
    .sort((a, b) => b.period.localeCompare(a.period))
    .slice(0, 5);

  const getMonthName = (month) =>
    ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month - 1];

  const trendRuns = [...generatedRuns]
    .sort((a, b) => a.period.localeCompare(b.period))
    .slice(-6)
    .map(p => {
      const active = (p.entries ?? []).filter(e => !e.excluded);
      const total = active.reduce((s, e) =>
        s + (parseFloat(e.basicSalary) || 0) + (parseFloat(e.variableAllowance) || 0), 0);
      const [y, m] = p.period.split('-').map(Number);
      return { period: p.period, label: `${getMonthName(m)} ${y}`, total, count: active.length };
    });
  const trendMax = Math.max(...trendRuns.map(r => r.total), 1);

  // ── WPS 30-day deadline tracker (UAE Labour Law Article 56) ─────────────────
  const today = new Date();
  const currentYear  = today.getFullYear();
  const currentMonth = today.getMonth() + 1;
  const prevMonth = currentMonth === 1 ? 12 : currentMonth - 1;
  const prevYear  = currentMonth === 1 ? currentYear - 1 : currentYear;
  const prevPeriod = `${prevYear}-${String(prevMonth).padStart(2, '0')}`;

  const prevPayroll = payrolls.find(p => p.period === prevPeriod && p.status === 'generated');

  // Salary must be paid within the company's configured salary day each month.
  // Warn once that day has passed and prev month payroll isn't generated yet.
  const salaryDay = company?.defaultSalaryDay ?? 25;
  const salaryDueThisMonth = new Date(currentYear, currentMonth - 1, salaryDay);
  const daysPastDue = Math.floor((today - salaryDueThisMonth) / 86400000);
  const wpsDeadlineWarning  = !prevPayroll && daysPastDue >= 0  && activeEmps.length > 0;
  const wpsDeadlineCritical = !prevPayroll && daysPastDue >= 10 && activeEmps.length > 0;

  // ── Document expiry summary (next 30 days) ──────────────────────────────────
  const docWarnings = [];
  employees.forEach(emp => {
    if (emp.employmentStatus === 'Terminated') return;
    const checks = [
      { label: 'Visa', date: emp.visaExpiry, days: 60 },
      { label: 'Passport', date: emp.passportExpiry, days: 60 },
      { label: 'Emirates ID', date: emp.emiratesIdExpiry, days: 30 },
      { label: 'Labour Card', date: emp.labourCardExpiry, days: 60 },
    ];
    checks.forEach(({ label, date, days }) => {
      if (!date) return;
      const expiry = new Date(date);
      const diffDays = Math.ceil((expiry - today) / (1000 * 60 * 60 * 24));
      if (diffDays <= days && diffDays >= 0) {
        docWarnings.push({ emp: emp.name, label, expiry: date, daysLeft: diffDays });
      }
    });
  });
  const criticalDocs = docWarnings.filter(d => d.daysLeft < 30);

  const steps = [
    {
      done: !!company?.molEmployerId,
      label: 'Company Settings',
      desc: 'Set your MOL Employer ID and bank routing code',
      nav: 'company',
      icon: Building2,
    },
    {
      done: activeEmps.length > 0,
      label: 'Employees',
      desc: `${activeEmps.length} active employee${activeEmps.length !== 1 ? 's' : ''} configured`,
      nav: 'employees',
      icon: Users,
    },
    {
      done: generatedRuns.length > 0,
      label: 'Payroll Module',
      desc: `${generatedRuns.length} payroll run${generatedRuns.length !== 1 ? 's' : ''} generated`,
      nav: 'payroll',
      icon: FileText,
    },
  ];

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
        Loading dashboard…
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
      </div>

      <div className="page-body">
        {/* Welcome */}
        <div className="card mb-4" style={{ background: 'linear-gradient(135deg, #1a56db 0%, #1e429f 100%)', border: 'none', color: 'white' }}>
          <div className="card-body">
            <h3 style={{ color: 'white', fontSize: 20, marginBottom: 6 }}>
              Workloop — UAE Payroll &amp; HRMS
            </h3>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: 14 }}>
              {company?.name
                ? `Welcome back, ${company.name}`
                : 'Manage payroll, employees, WPS/SIF files, and UAE compliance — all in one place.'}
            </p>
          </div>
        </div>

        {/* WPS 30-day deadline warning (UAE Labour Law Article 56) */}
        {wpsDeadlineWarning && (
          <div className={`alert ${wpsDeadlineCritical ? 'alert-danger' : 'alert-warning'} mb-4`}>
            <Clock size={16} />
            <div>
              <strong>WPS Deadline Alert (Article 56):</strong>{' '}
              {wpsDeadlineCritical
                ? `Salary for ${getMonthName(prevMonth)} ${prevYear} is overdue — UAE Labour Law requires payment within 30 days of the salary due date.`
                : `Salary for ${getMonthName(prevMonth)} ${prevYear} has not been processed yet. Payment is due within 30 days to comply with UAE WPS regulations.`}
              {' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('payroll')}>
                Go to Payroll
              </button>
            </div>
          </div>
        )}

        {/* Document expiry critical warnings */}
        {criticalDocs.length > 0 && (
          <div className="alert alert-danger mb-4">
            <ShieldAlert size={16} />
            <div>
              <strong>{criticalDocs.length} document{criticalDocs.length !== 1 ? 's' : ''} expiring within 30 days:</strong>{' '}
              {criticalDocs.slice(0, 3).map((d, i) => (
                <span key={i}>{d.emp} ({d.label} — {d.daysLeft}d){i < Math.min(criticalDocs.length, 3) - 1 ? ', ' : ''}</span>
              ))}
              {criticalDocs.length > 3 && ` and ${criticalDocs.length - 3} more.`}
              {' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('employees')}>
                View Employees
              </button>
            </div>
          </div>
        )}

        {/* Emiratization non-compliance alert */}
        {company?.sector && totalHeadcount > 0 && !nafisCompliant && (
          <div className="alert alert-danger mb-4">
            <ShieldAlert size={16} />
            <div>
              <strong>Emiratization Target Not Met (Cabinet Res. 27/2023):</strong>{' '}
              Current rate <strong>{nafisRatio.toFixed(1)}%</strong> ({emiratiCount} UAE national{emiratiCount !== 1 ? 's' : ''}) is below the required{' '}
              <strong>{nafisRequired}%</strong> for {company.sector}.
              {nafisGap > 0 && (
                <> You need <strong>{nafisGap} more UAE national{nafisGap !== 1 ? 's' : ''}</strong>.
                  Potential fine: <strong>AED {nafisFine.toLocaleString('en-AE')} / month</strong>.
                </>
              )}
              {' '}
              <button className="btn btn-ghost btn-sm" style={{ padding:'0 4px', textDecoration:'underline' }}
                onClick={() => setShowNafisReport(true)}>
                View Report
              </button>
            </div>
          </div>
        )}

        {/* Setup checklist */}
        <div className="card mb-4">
          <div className="card-header">
            <h3>Setup Checklist</h3>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 14,
                    padding: '14px 20px',
                    borderBottom: i < steps.length - 1 ? '1px solid var(--gray-100)' : 'none',
                    cursor: 'pointer',
                  }}
                  onClick={() => onNavigate(step.nav)}
                >
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    background: step.done ? 'var(--success-light)' : 'var(--gray-100)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    {step.done
                      ? <CheckCircle size={18} color="var(--success)" />
                      : <Icon size={18} color="var(--gray-400)" />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: 14, color: step.done ? 'var(--gray-800)' : 'var(--gray-600)' }}>
                      {step.label}
                    </div>
                    <div style={{ fontSize: 12.5, color: 'var(--gray-500)', marginTop: 2 }}>
                      {step.desc}
                    </div>
                  </div>
                  <ArrowRight size={16} color="var(--gray-400)" />
                </div>
              );
            })}
          </div>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Active Employees</div>
            <div className="stat-value">{activeEmps.length}</div>
            <div className="stat-sub">{employees.length} total</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Payroll Runs</div>
            <div className="stat-value">{payrolls.length}</div>
            <div className="stat-sub">{draftRuns.length} draft</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">SIF Files Generated</div>
            <div className="stat-value" style={{ color: 'var(--success)' }}>{generatedRuns.length}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Doc Expiry Alerts</div>
            <div className="stat-value" style={{ color: criticalDocs.length > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {criticalDocs.length}
            </div>
            <div className="stat-sub">{docWarnings.length} within 60 days</div>
          </div>
        </div>

        {/* Emiratization / Nafis compliance panel */}
        <div className="card mb-4">
          <div className="card-header">
            <h3><ShieldCheck size={15} style={{ marginRight:6, display:'inline' }} />Emiratization / Nafis Compliance</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowNafisReport(true)}>
              View Report <ArrowRight size={13} />
            </button>
          </div>
          <div className="card-body">
            {!company?.sector ? (
              <div style={{ fontSize:13.5, color:'var(--gray-500)', display:'flex', alignItems:'center', gap:10 }}>
                <AlertCircle size={15} color="var(--warning)" />
                Emiratization tracking not configured.{' '}
                <button className="btn btn-ghost btn-sm" style={{ padding:'0 4px', textDecoration:'underline' }}
                  onClick={() => onNavigate('company')}>
                  Set your sector in Company Settings
                </button>{' '}
                to enable the compliance dashboard.
              </div>
            ) : totalHeadcount === 0 ? (
              <div style={{ fontSize:13.5, color:'var(--gray-500)' }}>
                No active employees on record.
              </div>
            ) : (
              <div style={{ display:'flex', alignItems:'center', gap:32, flexWrap:'wrap' }}>
                {/* Ratio number */}
                <div style={{ textAlign:'center', minWidth:80 }}>
                  <div style={{ fontSize:34, fontWeight:800, lineHeight:1, color: nafisCompliant ? 'var(--success)' : 'var(--danger)' }}>
                    {nafisRatio.toFixed(1)}%
                  </div>
                  <div style={{ fontSize:11, color:'var(--gray-500)', marginTop:4 }}>Current Rate</div>
                </div>

                {/* Bar */}
                <div style={{ flex:1, minWidth:160 }}>
                  <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--gray-400)', marginBottom:5 }}>
                    <span>0%</span>
                    <span style={{ color:'var(--gray-600)', fontWeight:600 }}>Target: {nafisRequired}%</span>
                  </div>
                  <div style={{ height:10, background:'var(--gray-200)', borderRadius:6, overflow:'hidden', position:'relative' }}>
                    {/* Target marker */}
                    <div style={{ position:'absolute', top:0, bottom:0, left:`${Math.min(nafisRequired, 100)}%`, width:2, background:'var(--gray-500)', zIndex:2 }} />
                    {/* Fill */}
                    <div style={{ height:'100%', width:`${Math.min(nafisRatio, 100)}%`, background: nafisCompliant ? 'var(--success)' : 'var(--danger)', borderRadius:6, transition:'width 0.4s' }} />
                  </div>
                  <div style={{ marginTop:6, fontSize:12.5, color:'var(--gray-700)' }}>
                    <strong>{emiratiCount}</strong> UAE national{emiratiCount !== 1 ? 's' : ''} of <strong>{totalHeadcount}</strong> active employees
                    {company.sector && <span style={{ color:'var(--gray-400)', marginLeft:8 }}>· {company.sector}</span>}
                  </div>
                  {!nafisCompliant && nafisGap > 0 && (
                    <div style={{ marginTop:5, fontSize:12, color:'var(--danger)', fontWeight:600 }}>
                      {nafisGap} more UAE national{nafisGap !== 1 ? 's' : ''} needed
                      · Potential fine: AED {nafisFine.toLocaleString('en-AE')} / month
                    </div>
                  )}
                </div>

                {/* Status badge */}
                <div style={{ textAlign:'center', minWidth:80 }}>
                  <div style={{ fontSize:11, color:'var(--gray-500)', marginBottom:6 }}>Status</div>
                  <span className={`badge ${nafisCompliant ? 'badge-green' : 'badge-red'}`} style={{ fontSize:12, padding:'5px 12px' }}>
                    {nafisCompliant ? 'Compliant' : 'Non-Compliant'}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Payroll trend */}
        {trendRuns.length >= 2 && (
          <div className="card mb-4">
            <div className="card-header">
              <h3>Payroll Trend</h3>
              <span style={{ fontSize:12, color:'var(--gray-500)' }}>Last {trendRuns.length} processed months</span>
            </div>
            <div className="card-body">
              <div style={{ display:'flex', alignItems:'flex-end', gap:12, height:100 }}>
                {trendRuns.map((r, i) => {
                  const pct = trendMax > 0 ? (r.total / trendMax) * 100 : 0;
                  const prev = trendRuns[i - 1];
                  const delta = prev ? r.total - prev.total : 0;
                  const isLast = i === trendRuns.length - 1;
                  return (
                    <div key={r.period} style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:4 }}>
                      {isLast && delta !== 0 && (
                        <div style={{ fontSize:10, fontWeight:700, color: delta > 0 ? 'var(--success)' : 'var(--danger)' }}>
                          {delta > 0 ? '▲' : '▼'} {Math.abs(delta).toLocaleString('en-AE', { maximumFractionDigits:0 })}
                        </div>
                      )}
                      <div
                        title={`${r.label}: AED ${r.total.toLocaleString('en-AE', { minimumFractionDigits:0 })}`}
                        style={{
                          width:'100%', borderRadius:'4px 4px 0 0',
                          background: isLast ? 'var(--primary)' : 'var(--primary-light)',
                          height: `${Math.max(pct, 4)}%`,
                          transition: 'height 0.3s',
                        }}
                      />
                      <div style={{ fontSize:10, color:'var(--gray-500)', textAlign:'center', whiteSpace:'nowrap' }}>
                        {r.label.split(' ')[0]}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ marginTop:8, fontSize:12, color:'var(--gray-500)', textAlign:'right' }}>
                Latest: <strong style={{ color:'var(--gray-800)' }}>
                  AED {trendRuns[trendRuns.length - 1]?.total.toLocaleString('en-AE', { minimumFractionDigits:0 })}
                </strong>
              </div>
            </div>
          </div>
        )}

        {/* Recent payrolls */}
        {recentPayrolls.length > 0 && (
          <div className="card">
            <div className="card-header">
              <h3>Recent Payroll Runs</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => onNavigate('payroll')}>
                View all <ArrowRight size={13} />
              </button>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Payment Date</th>
                    <th>Employees</th>
                    <th>Total (AED)</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPayrolls.map(p => {
                    const [y, m] = p.period.split('-').map(Number);
                    const active = p.entries.filter(e => !e.excluded);
                    const total  = active.reduce(
                      (s, e) => s + (parseFloat(e.basicSalary) || 0) + (parseFloat(e.variableAllowance) || 0), 0
                    );
                    return (
                      <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => onNavigate('payroll')}>
                        <td style={{ fontWeight: 600 }}>{getMonthName(m)} {y}</td>
                        <td>{p.paymentDate || '—'}</td>
                        <td>{active.length}</td>
                        <td className="text-right font-bold">
                          {total.toLocaleString('en-AE', { minimumFractionDigits: 2 })}
                        </td>
                        <td>
                          <span className={`badge ${p.status === 'generated' ? 'badge-green' : 'badge-yellow'}`}>
                            {p.status === 'generated' ? 'Generated' : 'Draft'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Warnings */}
        {!company?.molEmployerId && (
          <div className="alert alert-warning mt-4">
            <AlertCircle size={16} />
            <div>
              <strong>Action required:</strong> Please go to{' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('company')}>
                Company Settings
              </button>{' '}
              and enter your MOL Employer ID to start generating WPS/SIF files.
            </div>
          </div>
        )}
      </div>

      {showNafisReport && (
        <NafisReportModal
          employees={employees}
          company={company}
          onClose={() => setShowNafisReport(false)}
        />
      )}
    </div>
  );
}
