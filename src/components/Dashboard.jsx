import { useState, useEffect } from 'react';
import { Building2, Users, FileText, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';
import { getCompany, getEmployees, getPayrolls } from '../utils/storage';

export default function Dashboard({ onNavigate }) {
  const [company, setCompany]     = useState(null);
  const [employees, setEmployees] = useState([]);
  const [payrolls, setPayrolls]   = useState([]);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    Promise.all([getCompany(), getEmployees(), getPayrolls()]).then(([co, emps, pays]) => {
      setCompany(co);
      setEmployees(emps);
      setPayrolls(pays);
      setLoading(false);
    });
  }, []);

  const activeEmps    = employees.filter(e => e.active);
  const generatedRuns = payrolls.filter(p => p.status === 'generated');
  const draftRuns     = payrolls.filter(p => p.status !== 'generated');

  const recentPayrolls = [...payrolls]
    .sort((a, b) => b.period.localeCompare(a.period))
    .slice(0, 5);

  const getMonthName = (month) =>
    ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month - 1];

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
      label: 'Employee Master Data',
      desc: `${activeEmps.length} active employee${activeEmps.length !== 1 ? 's' : ''} configured`,
      nav: 'employees',
      icon: Users,
    },
    {
      done: generatedRuns.length > 0,
      label: 'Generate SIF Files',
      desc: `${generatedRuns.length} SIF file${generatedRuns.length !== 1 ? 's' : ''} generated`,
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
              UAE WPS SIF File Generator
            </h3>
            <p style={{ color: 'rgba(255,255,255,0.8)', fontSize: 14 }}>
              {company?.name
                ? `Welcome back, ${company.name}`
                : 'Generate compliant Wage Protection System (WPS) SIF files for salary uploads in Dubai.'}
            </p>
          </div>
        </div>

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
            <div className="stat-label">MOL Employer ID</div>
            <div className="stat-value" style={{ fontSize: 14, fontFamily: 'monospace', marginTop: 8 }}>
              {company?.molEmployerId || '—'}
            </div>
            <div className="stat-sub">{company?.name || 'Not configured'}</div>
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
              and enter your MOL Employer ID to start generating SIF files.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
