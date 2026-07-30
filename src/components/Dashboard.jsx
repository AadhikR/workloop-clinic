import { useState, useEffect } from 'react';
import { Building2, Users, FileText, CheckCircle, AlertCircle, ArrowRight, Clock, ShieldAlert, ShieldCheck, Heart, Mail } from 'lucide-react';
import { getCompany, getEmployees, getPayrolls, getInsurancePolicies, getAllEmployeeInsurance, getAllEmployeeDocuments } from '../utils/storage';
import { getAllCertifications } from '../utils/trainingStorage';
import { generateExpiryNotifications } from '../utils/notificationStorage';
import { getPendingLetterCount } from '../utils/letterStorage';
import { getAppraisalCycles, getAppraisalsForCycle } from '../utils/appraisalStorage';
import { useCompany } from '../context/CompanyContext';
import NafisReportModal from './NafisReportModal';
import LoadError from './LoadError';

export default function Dashboard({ onNavigate }) {
  const { activeCompanyId } = useCompany();
  const [company, setCompany]         = useState(null);
  const [employees, setEmployees]     = useState([]);
  const [payrolls, setPayrolls]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [loadError, setLoadError]     = useState(null);
  const [showNafisReport, setShowNafisReport] = useState(false);
  const [insurancePolicies, setInsurancePolicies] = useState([]);
  const [allEmpInsurance, setAllEmpInsurance]     = useState([]);
  const [allCertifications, setAllCertifications] = useState([]);
  const [pendingLetters, setPendingLetters]       = useState(0);
  const [pendingAppraisals, setPendingAppraisals] = useState(0);

  useEffect(() => {
    setLoading(true);
    setLoadError(null);
    Promise.all([
      getCompany(activeCompanyId), getEmployees(activeCompanyId), getPayrolls(activeCompanyId),
      getInsurancePolicies(), getAllEmployeeInsurance(),
      getAllCertifications().catch(() => []),
      getAllEmployeeDocuments().catch(() => []),
      getPendingLetterCount().catch(() => 0),
    ]).then(([co, emps, pays, pols, empIns, certs, allDocs, letterCount]) => {
      setCompany(co);
      setEmployees(emps);
      setPayrolls(pays);
      setInsurancePolicies(pols);
      setAllEmpInsurance(empIns);
      setAllCertifications(certs || []);
      setPendingLetters(letterCount || 0);
      setLoading(false);
      // Silently generate persistent expiry notifications (ON CONFLICT DO NOTHING)
      generateExpiryNotifications(emps, co, pols, empIns, certs || [], allDocs || []).catch(() => {});
      // Count pending appraisals across all active cycles
      getAppraisalCycles().then(async cycles => {
        const activeCycles = cycles.filter(c => c.status === 'active' || c.status === 'open');
        if (!activeCycles.length) return;
        const allAppraisals = (await Promise.all(activeCycles.map(c => getAppraisalsForCycle(c.id).catch(() => [])))).flat();
        setPendingAppraisals(allAppraisals.filter(a => a.status === 'pending').length);
      }).catch(() => {});
    }).catch(err => {
      console.error('Dashboard load error:', err);
      setLoadError(err.message || 'Failed to load dashboard data');
      setLoading(false);
    });
  }, [activeCompanyId]); // Re-load when the active branch changes

  const activeEmps    = employees.filter(e => e.active !== false && e.employmentStatus !== 'Terminated');
  const generatedRuns = payrolls.filter(p => p.status === 'generated');

  // ── Emiratization / Nafis compliance ──
  // 2026 rules (Cabinet Res. 27/2023 + MoHRE 2026 updates):
  //   <20  employees → not mandatory (Nafis participation is voluntary)
  //   20-49 in priority sectors → fixed minimum of 2 Emirati staff
  //   50+  employees → percentage-based quota per sector (default 2% healthcare, 10% general)
  // Fine (2026): AED 9,000 / month per unfilled Emirati slot.
  const emiratiEmps     = activeEmps.filter(e => e.nationality === 'United Arab Emirates');
  const emiratiCount    = emiratiEmps.length;
  const totalHeadcount  = activeEmps.length;
  const nafisRequired   = parseFloat(company?.nafisQuotaPercent) || 2;
  // Which tier applies to this company?
  const nafisTier =
    totalHeadcount < 20 ? 'not_mandatory'
    : totalHeadcount < 50 ? 'fixed_two'
    : 'percentage';
  const nafisMinCount   = nafisTier === 'fixed_two'
    ? 2
    : nafisTier === 'percentage'
      ? Math.ceil((nafisRequired / 100) * totalHeadcount)
      : 0;
  const nafisRatio      = totalHeadcount > 0 ? (emiratiCount / totalHeadcount) * 100 : 0;
  const nafisCompliant  = nafisTier === 'not_mandatory' || emiratiCount >= nafisMinCount;
  const nafisGap        = Math.max(0, nafisMinCount - emiratiCount);
  const nafisFine       = nafisGap * 9000;  // 2026 monthly fine per unfilled slot
  const draftRuns          = payrolls.filter(p => p.status !== 'generated');
  // Payroll Approval (Feature 17)
  const pendingApprovalRuns = payrolls.filter(p => p.approvalStatus === 'pending_approval');

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

  // ── Probation ending alert (Feature 11) ────────────────────────────────────
  const todayStr = today.toISOString().slice(0, 10);
  const probationEnding = employees.filter(emp => {
    if (emp.employmentStatus !== 'Probation') return false;
    if (!emp.probationEndDate) return false;
    const days = Math.ceil((new Date(emp.probationEndDate) - today) / 86400000);
    return days <= 14; // includes already-expired
  }).map(emp => ({
    emp,
    days: Math.ceil((new Date(emp.probationEndDate) - today) / 86400000),
  })).sort((a, b) => a.days - b.days);

  // ── Contract expiry alert (Feature 12) ────────────────────────────────────
  const contractExpiring = employees.filter(emp => {
    if (emp.employmentStatus === 'Terminated') return false;
    if (emp.contractType !== 'Limited') return false;
    if (!emp.contractEndDate) return false;
    const days = Math.ceil((new Date(emp.contractEndDate) - today) / 86400000);
    return days <= 60;
  }).map(emp => ({
    emp,
    days: Math.ceil((new Date(emp.contractEndDate) - today) / 86400000),
  })).sort((a, b) => a.days - b.days);

  // ── Certification expiry alert (Feature 19) ───────────────────────────────
  const certExpiring = allCertifications.filter(cert => {
    if (!cert.expiryDate) return false;
    const days = Math.ceil((new Date(cert.expiryDate) - today) / 86400000);
    return days >= 0 && days <= 60;
  }).map(cert => ({
    cert,
    days: Math.ceil((new Date(cert.expiryDate) - today) / 86400000),
  })).sort((a, b) => a.days - b.days);

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

  // ── Insurance expiry alerts ──────────────────────────────────────────────────
  // Employee-level: coverage expiring within 60 days
  const insuranceCovWarnings = [];
  allEmpInsurance.forEach(ins => {
    if (!ins.expiryDate) return;
    const emp = employees.find(e => e.id === ins.employeeId);
    if (!emp || emp.employmentStatus === 'Terminated') return;
    const days = Math.ceil((new Date(ins.expiryDate) - today) / (1000 * 60 * 60 * 24));
    if (days <= 60 && days >= 0) {
      insuranceCovWarnings.push({ empName: emp.name, daysLeft: days });
    }
  });
  // Policy-level: renewal date within 60 days
  const policyRenewalWarnings = insurancePolicies.filter(p => {
    if (!p.renewalDate) return false;
    const days = Math.ceil((new Date(p.renewalDate) - today) / (1000 * 60 * 60 * 24));
    return days <= 60 && days >= 0;
  }).map(p => ({
    name:     `${p.insurerName}${p.tierName ? ` (${p.tierName})` : ''}`,
    daysLeft: Math.ceil((new Date(p.renewalDate) - today) / (1000 * 60 * 60 * 24)),
  }));

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

  if (loadError) {
    return (
      <div className="page-body">
        <LoadError message={loadError} onRetry={() => window.location.reload()} />
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

        {/* Payroll pending approval alert (Feature 17) */}
        {pendingApprovalRuns.length > 0 && (
          <div className="alert alert-info mb-4">
            <AlertCircle size={16} />
            <div>
              <strong>{pendingApprovalRuns.length} payroll run{pendingApprovalRuns.length !== 1 ? 's' : ''} pending approval: </strong>
              {pendingApprovalRuns.map((p, i) => {
                const [y, m] = p.period.split('-').map(Number);
                const mn = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][m-1];
                return <span key={p.id}>{i > 0 && ', '}<strong>{mn} {y}</strong></span>;
              })}.{' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('payroll')}>
                Review in Payroll
              </button>
            </div>
          </div>
        )}

        {/* Probation ending alert (Feature 11) */}
        {probationEnding.length > 0 && (
          <div className="alert alert-warning mb-4">
            <Clock size={16} />
            <div>
              <strong>{probationEnding.length} employee{probationEnding.length !== 1 ? 's' : ''} on probation ending soon:</strong>{' '}
              {probationEnding.map(({ emp, days }, i) => (
                <span key={emp.id}>
                  {i > 0 && ', '}
                  <strong>{emp.name}</strong>
                  {' '}({days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'ends today' : `${days}d`})
                </span>
              ))}
              {'. '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('employees')}>
                Manage in Employees
              </button>
            </div>
          </div>
        )}

        {/* Contract expiry alert (Feature 12) */}
        {contractExpiring.length > 0 && (
          <div className="alert alert-warning mb-4">
            <Clock size={16} />
            <div>
              <strong>{contractExpiring.length} limited contract{contractExpiring.length !== 1 ? 's' : ''} expiring within 60 days:</strong>{' '}
              {contractExpiring.slice(0, 3).map(({ emp, days }, i) => (
                <span key={emp.id}>
                  {i > 0 && ', '}
                  <strong>{emp.name}</strong>
                  {' '}({days < 0 ? `${Math.abs(days)}d overdue` : days === 0 ? 'today' : `${days}d`})
                </span>
              ))}
              {contractExpiring.length > 3 && ` and ${contractExpiring.length - 3} more.`}
              {'. '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('employees')}>
                Manage in Employees
              </button>
            </div>
          </div>
        )}

        {/* Certification expiry alert (Feature 19) */}
        {certExpiring.length > 0 && (
          <div className="alert alert-warning mb-4">
            <AlertCircle size={16} />
            <div>
              <strong>{certExpiring.length} certification{certExpiring.length !== 1 ? 's' : ''} expiring within 60 days: </strong>
              {certExpiring.slice(0, 3).map(({ cert, days }, i) => (
                <span key={cert.id}>
                  {i > 0 && ', '}
                  <strong>{cert.employeeName}</strong>{' '}
                  ({cert.certificationName} — {days === 0 ? 'today' : `${days}d`})
                </span>
              ))}
              {certExpiring.length > 3 && ` and ${certExpiring.length - 3} more.`}
              {'. '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('training')}>
                View in Training
              </button>
            </div>
          </div>
        )}

        {/* Pending letter requests alert (Feature 1.3) */}
        {pendingLetters > 0 && (
          <div className="alert alert-info mb-4">
            <Mail size={16} />
            <div>
              <strong>{pendingLetters} letter request{pendingLetters !== 1 ? 's' : ''} pending.</strong>
              {' '}Employees are waiting for HR letters to be generated.{' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('letters')}>
                View Letter Requests
              </button>
            </div>
          </div>
        )}

        {/* Appraisals pending review alert (Feature 6.1) */}
        {pendingAppraisals > 0 && (
          <div className="alert alert-info mb-4">
            <CheckCircle size={16} />
            <div>
              <strong>{pendingAppraisals} appraisal{pendingAppraisals !== 1 ? 's' : ''} pending review.</strong>
              {' '}Staff appraisals in active cycles have not been rated yet.{' '}
              <button className="btn btn-ghost btn-sm" style={{ padding: '0 4px', textDecoration: 'underline' }}
                onClick={() => onNavigate('appraisals')}>
                Open Appraisals
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

        {/* Emiratization non-compliance alert — only when the tier makes it mandatory */}
        {company?.enableNafis !== false && nafisTier !== 'not_mandatory' && totalHeadcount > 0 && !nafisCompliant && (
          <div className="alert alert-danger mb-4">
            <ShieldAlert size={16} />
            <div>
              <strong>Emiratization Target Not Met (MoHRE 2026 rules):</strong>{' '}
              {nafisTier === 'fixed_two'
                ? <>You employ <strong>{emiratiCount}</strong> UAE national{emiratiCount !== 1 ? 's' : ''} — the 20-49 staff tier requires a minimum of <strong>2</strong>.</>
                : <>Current rate <strong>{nafisRatio.toFixed(1)}%</strong> ({emiratiCount} UAE national{emiratiCount !== 1 ? 's' : ''}) is below the required <strong>{nafisRequired}%</strong>{company?.sector ? ` for ${company.sector}` : ''}.</>
              }
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

        {/* Insurance coverage expiry alerts */}
        {insuranceCovWarnings.length > 0 && (
          <div className="alert alert-warning mb-4">
            <Heart size={16} />
            <div>
              <strong>{insuranceCovWarnings.length} employee insurance coverage{insuranceCovWarnings.length !== 1 ? 's' : ''} expiring within 60 days:</strong>{' '}
              {insuranceCovWarnings.slice(0, 3).map((w, i) => (
                <span key={i}>{w.empName} ({w.daysLeft}d){i < Math.min(insuranceCovWarnings.length, 3) - 1 ? ', ' : ''}</span>
              ))}
              {insuranceCovWarnings.length > 3 && ` and ${insuranceCovWarnings.length - 3} more.`}
              {' '}
              <button className="btn btn-ghost btn-sm" style={{ padding:'0 4px', textDecoration:'underline' }}
                onClick={() => onNavigate('employees')}>
                Update in Employee Profiles
              </button>
            </div>
          </div>
        )}

        {/* Insurance policy renewal alerts */}
        {policyRenewalWarnings.length > 0 && (
          <div className="alert alert-warning mb-4">
            <Heart size={16} />
            <div>
              <strong>{policyRenewalWarnings.length} insurance polic{policyRenewalWarnings.length !== 1 ? 'ies' : 'y'} renewing within 60 days:</strong>{' '}
              {policyRenewalWarnings.map((w, i) => (
                <span key={i}>{w.name} ({w.daysLeft}d){i < policyRenewalWarnings.length - 1 ? ', ' : ''}</span>
              ))}
              {' '}
              <button className="btn btn-ghost btn-sm" style={{ padding:'0 4px', textDecoration:'underline' }}
                onClick={() => onNavigate('company')}>
                View in Company Settings
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
          <div className="stat-card">
            <div className="stat-label">Insurance Alerts</div>
            <div className="stat-value" style={{ color: (insuranceCovWarnings.length + policyRenewalWarnings.length) > 0 ? 'var(--warning)' : 'var(--success)' }}>
              {insuranceCovWarnings.length + policyRenewalWarnings.length}
            </div>
            <div className="stat-sub">{insurancePolicies.length} polic{insurancePolicies.length !== 1 ? 'ies' : 'y'} on file</div>
          </div>
        </div>

        {/* Emiratization / Nafis compliance panel */}
        {company?.enableNafis !== false && (
        <div className="card mb-4">
          <div className="card-header">
            <h3><ShieldCheck size={15} style={{ marginRight:6, display:'inline' }} />Emiratization / Nafis Compliance</h3>
            <button className="btn btn-ghost btn-sm" onClick={() => setShowNafisReport(true)}>
              View Report <ArrowRight size={13} />
            </button>
          </div>
          <div className="card-body">
            {totalHeadcount === 0 ? (
              <div style={{ fontSize:13.5, color:'var(--gray-500)' }}>
                No active employees on record.
              </div>
            ) : nafisTier === 'not_mandatory' ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <ShieldCheck size={22} color="var(--success)" />
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--gray-800)' }}>
                    Nafis compliance not mandatory
                  </div>
                  <div style={{ fontSize: 12.5, color: 'var(--gray-500)', marginTop: 3 }}>
                    You have <strong>{totalHeadcount}</strong> active employee{totalHeadcount !== 1 ? 's' : ''}.
                    Emiratization quotas apply from <strong>20 skilled staff</strong> upwards (MoHRE 2026 rules).
                    Voluntary Nafis participation may still qualify you for salary support &amp; training grants.
                  </div>
                </div>
              </div>
            ) : !company?.sector ? (
              <div style={{ fontSize:13.5, color:'var(--gray-500)', display:'flex', alignItems:'center', gap:10 }}>
                <AlertCircle size={15} color="var(--warning)" />
                Emiratization tracking not configured.{' '}
                <button className="btn btn-ghost btn-sm" style={{ padding:'0 4px', textDecoration:'underline' }}
                  onClick={() => onNavigate('company')}>
                  Set your sector in Company Settings
                </button>{' '}
                to enable the compliance dashboard.
              </div>
            ) : (
              <div style={{ display:'flex', alignItems:'center', gap:32, flexWrap:'wrap' }}>
                {/* Headline metric — count for 20-49, % for 50+ */}
                <div style={{ textAlign:'center', minWidth:80 }}>
                  <div style={{ fontSize:34, fontWeight:800, lineHeight:1, color: nafisCompliant ? 'var(--success)' : 'var(--danger)' }}>
                    {nafisTier === 'fixed_two' ? `${emiratiCount}/${nafisMinCount}` : `${nafisRatio.toFixed(1)}%`}
                  </div>
                  <div style={{ fontSize:11, color:'var(--gray-500)', marginTop:4 }}>
                    {nafisTier === 'fixed_two' ? 'UAE Nationals' : 'Current Rate'}
                  </div>
                </div>

                <div style={{ flex:1, minWidth:160 }}>
                  {nafisTier === 'fixed_two' && (
                    <div style={{ fontSize:12.5, color:'var(--gray-700)' }}>
                      <strong>MoHRE 2026 rule:</strong> employers with 20–49 skilled staff in priority sectors must employ a minimum of <strong>2 UAE nationals</strong>.
                      <div style={{ marginTop:5, color:'var(--gray-500)' }}>
                        <strong>{emiratiCount}</strong> UAE national{emiratiCount !== 1 ? 's' : ''} of <strong>{totalHeadcount}</strong> active employees
                        {company?.sector && <span style={{ marginLeft:8 }}>· {company.sector}</span>}
                      </div>
                    </div>
                  )}
                  {nafisTier !== 'fixed_two' && (
                    <div>
                      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:'var(--gray-400)', marginBottom:5 }}>
                        <span>0%</span>
                        <span style={{ color:'var(--gray-600)', fontWeight:600 }}>Target: {nafisRequired}%</span>
                      </div>
                      <div style={{ height:10, background:'var(--gray-200)', borderRadius:6, overflow:'hidden', position:'relative' }}>
                        <div style={{ position:'absolute', top:0, bottom:0, left:`${Math.min(nafisRequired, 100)}%`, width:2, background:'var(--gray-500)', zIndex:2 }} />
                        <div style={{ height:'100%', width:`${Math.min(nafisRatio, 100)}%`, background: nafisCompliant ? 'var(--success)' : 'var(--danger)', borderRadius:6, transition:'width 0.4s' }} />
                      </div>
                      <div style={{ marginTop:6, fontSize:12.5, color:'var(--gray-700)' }}>
                        <strong>{emiratiCount}</strong> UAE national{emiratiCount !== 1 ? 's' : ''} of <strong>{totalHeadcount}</strong> active employees
                        {company?.sector && <span style={{ color:'var(--gray-400)', marginLeft:8 }}>· {company.sector}</span>}
                      </div>
                    </div>
                  )}
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
        )}

        {/* Payroll trend */}
        <div className="card mb-4">
          <div className="card-header">
            <h3>Payroll Cost Trend</h3>
            <span style={{ fontSize:12, color:'var(--gray-500)' }}>
              {trendRuns.length >= 2 ? `Last ${trendRuns.length} processed months` : 'No generated runs yet'}
            </span>
          </div>
          <div className="card-body">
            {trendRuns.length < 2 ? (
              <div style={{ textAlign:'center', color:'var(--gray-400)', padding:'20px 0', fontSize:13 }}>
                Generate at least 2 payroll runs to see the cost trend chart.
                <div style={{ marginTop:8 }}>
                  <button className="btn btn-ghost btn-sm" style={{ textDecoration:'underline' }}
                    onClick={() => onNavigate('payroll')}>
                    Go to Payroll Module →
                  </button>
                </div>
              </div>
            ) : (
              <>
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
              </>
            )}
          </div>
        </div>

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
                    <th>WPS</th>
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
                        <td>
                          {p.status === 'generated' && (() => {
                            const wps = p.wpsStatus ?? 'draft';
                            const badges = { draft:'badge-yellow', sif_generated:'badge-blue', submitted:'badge-amber', confirmed:'badge-green', partial_rejection:'badge-amber', failed:'badge-red' };
                            const labels = { draft:'—', sif_generated:'SIF Ready', submitted:'Submitted', confirmed:'Confirmed', partial_rejection:'Partial Reject', failed:'Failed' };
                            return wps !== 'draft'
                              ? <span className={`badge ${badges[wps]}`} style={{ fontSize:11 }}>{labels[wps]}</span>
                              : <span style={{ color:'var(--gray-400)', fontSize:12 }}>—</span>;
                          })()}
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
