import { useEffect, useState } from 'react';
import { Home, CalendarDays, Clock, FileText, User, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { getMyEmployeeRecord, getMyCompany } from '../../utils/profileStorage';
import EmpHome from './EmpHome';
import EmpLeave from './EmpLeave';
import EmpAttendance from './EmpAttendance';
import EmpPayslips from './EmpPayslips';
import EmpProfile from './EmpProfile';

const TABS = [
  { id: 'home',       label: 'Home',       icon: Home },
  { id: 'leave',      label: 'Leave',      icon: CalendarDays },
  { id: 'attendance', label: 'Attendance', icon: Clock },
  { id: 'payslips',   label: 'Payslips',   icon: FileText },
  { id: 'profile',    label: 'Profile',    icon: User },
];

export default function EmployeeShell() {
  const { signOut } = useAuth();
  const [tab, setTab]             = useState('home');
  const [signingOut, setSigningOut] = useState(false);
  const [emp, setEmp]             = useState(null);
  const [company, setCompany]     = useState(null);

  useEffect(() => {
    Promise.all([getMyEmployeeRecord(), getMyCompany()]).then(([e, c]) => {
      setEmp(e);
      setCompany(c);
    });
  }, []);

  const handleSignOut = async () => {
    setSigningOut(true);
    try { await signOut(); } catch { /* ignore */ }
    setSigningOut(false);
  };

  const renderTab = () => {
    switch (tab) {
      case 'home':       return <EmpHome onNavigate={setTab} />;
      case 'leave':      return <EmpLeave />;
      case 'attendance': return <EmpAttendance />;
      case 'payslips':   return <EmpPayslips />;
      case 'profile':    return <EmpProfile onSignOut={handleSignOut} signingOut={signingOut} />;
      default:           return <EmpHome onNavigate={setTab} />;
    }
  };

  return (
    <div className="emp-shell">
      {/* Desktop sidebar */}
      <aside className="emp-sidebar">
        <div className="emp-sidebar-logo">
          {company?.name
            ? <>
                <h1 style={{ fontSize: 15, fontWeight: 700 }}>{company.name}</h1>
                <p style={{ fontSize: 11, opacity: 0.5, marginTop: 2 }}>Employee Portal</p>
              </>
            : <>
                <h1>Workloop</h1>
                <p>Employee Portal</p>
              </>
          }
        </div>

        <nav style={{ flex: 1, padding: '8px 0' }}>
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                className={`nav-item ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                <Icon size={16} />
                {t.label}
              </button>
            );
          })}
        </nav>

        {/* Employee identity + sign out */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
          {emp && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginBottom: 10, padding: '8px 10px', borderRadius: 8,
              background: 'rgba(255,255,255,0.06)',
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: 'rgba(255,255,255,0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <User size={13} color="rgba(255,255,255,0.8)" />
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.9)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {emp.name}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 1 }}>
                  {emp.job_title || 'Employee'}
                </div>
              </div>
            </div>
          )}

          <button
            onClick={handleSignOut}
            disabled={signingOut}
            className="nav-item"
            style={{ width: '100%', color: 'rgba(255,255,255,0.5)' }}
          >
            <LogOut size={14} />
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="emp-main">
        {renderTab()}
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="emp-bottom-nav">
        {TABS.map(t => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              className={`emp-tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <Icon size={20} />
              {t.label}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
