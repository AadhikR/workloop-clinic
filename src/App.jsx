import { useState, useRef, useLayoutEffect, useEffect } from 'react';
import { LayoutDashboard, Building2, Users, FileText, LogOut, User, CalendarDays, Clock } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthPage from './components/AuthPage';
import { getCompany } from './utils/storage';
import Dashboard from './components/Dashboard';
import CompanySettings from './components/CompanySettings';
import EmployeeManager from './components/EmployeeManager';
import PayrollManager from './components/PayrollManager';
import LeaveManager from './components/LeaveManager';
import AttendanceManager from './components/AttendanceManager';
import EmployeeShell from './components/employee/EmployeeShell';
import './index.css';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',        icon: LayoutDashboard },
  { id: 'company',    label: 'Company Settings', icon: Building2 },
  { id: 'employees',  label: 'Employees',         icon: Users },
  { id: 'payroll',    label: 'Payroll Module',    icon: FileText },
  { id: 'leave',      label: 'Leave',             icon: CalendarDays },
  { id: 'attendance', label: 'Attendance',        icon: Clock },
];

// ─── Admin shell (HR users) ──────────────────────────────────────────────────
function AppShell() {
  const { user, signOut } = useAuth();
  const [page, setPage] = useState('dashboard');
  const [signingOut, setSigningOut] = useState(false);
  const navRef  = useRef(null);
  const [pill, setPill]         = useState({ top: 0, height: 36 });
  const [companyName, setCompanyName] = useState('');

  useEffect(() => {
    getCompany().then(co => { if (co?.name) setCompanyName(co.name); });
  }, []);

  useLayoutEffect(() => {
    if (!navRef.current) return;
    const active = navRef.current.querySelector('.nav-item.active');
    if (!active) return;
    const navRect  = navRef.current.getBoundingClientRect();
    const itemRect = active.getBoundingClientRect();
    setPill({
      top:    itemRect.top  - navRect.top  + navRef.current.scrollTop,
      height: itemRect.height,
    });
  }, [page]);

  const handleSignOut = async () => {
    setSigningOut(true);
    try { await signOut(); } catch { /* ignore */ }
    setSigningOut(false);
  };

  const renderPage = () => {
    switch (page) {
      case 'dashboard':  return <Dashboard onNavigate={setPage} />;
      case 'company':    return <CompanySettings />;
      case 'employees':  return <EmployeeManager />;
      case 'payroll':    return <PayrollManager />;
      case 'leave':      return <LeaveManager />;
      case 'attendance': return <AttendanceManager />;
      default:           return <Dashboard onNavigate={setPage} />;
    }
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>Workloop</h1>
          {companyName
            ? <p style={{ color: 'rgba(255,255,255,0.75)', fontWeight: 500, fontSize: 12, marginTop: 3 }}>{companyName}</p>
            : <p>UAE Payroll &amp; HRMS</p>
          }
        </div>

        <nav className="sidebar-nav" ref={navRef}>
          <div className="nav-section-label">Navigation</div>

          {/* Sliding pill behind active item */}
          <div className="nav-pill" style={{ transform: `translateY(${pill.top}px)`, height: pill.height }} />

          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div style={{
          marginTop: 'auto',
          padding: '12px 16px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginBottom: 10, padding: '8px 10px', borderRadius: 8,
            background: 'rgba(255,255,255,0.06)',
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: '50%',
              background: 'rgba(255,255,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <User size={14} color="rgba(255,255,255,0.8)" />
            </div>
            <div style={{ overflow: 'hidden', flex: 1 }}>
              <div style={{
                fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.9)',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {user?.email}
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 1 }}>
                HR Admin
              </div>
            </div>
          </div>

          <button
            onClick={handleSignOut}
            disabled={signingOut}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 8,
              padding: '7px 10px', borderRadius: 7,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'transparent', color: 'rgba(255,255,255,0.55)',
              fontSize: 12, cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(239,68,68,0.15)';
              e.currentTarget.style.color = '#fca5a5';
              e.currentTarget.style.borderColor = 'rgba(239,68,68,0.3)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'rgba(255,255,255,0.55)';
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)';
            }}
          >
            <LogOut size={13} />
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </aside>

      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}

// ─── Root: resolves role then renders the correct shell ──────────────────────
function Root() {
  const { user, profile, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)',
      }}>
        <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
          <div style={{
            width: 40, height: 40, border: '3px solid rgba(255,255,255,0.2)',
            borderTopColor: '#1a56db', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 16px',
          }} />
          <p style={{ fontSize: 14 }}>Loading…</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!user) return <AuthPage />;

  // profile is null briefly while resolveProfile() runs after sign-in
  if (!profile) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%)',
      }}>
        <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.6)' }}>
          <div style={{
            width: 40, height: 40, border: '3px solid rgba(255,255,255,0.2)',
            borderTopColor: '#1a56db', borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            margin: '0 auto 16px',
          }} />
          <p style={{ fontSize: 14 }}>Setting up your account…</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return profile.role === 'employee' ? <EmployeeShell /> : <AppShell />;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
