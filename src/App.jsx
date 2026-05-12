import { useState } from 'react';
import { LayoutDashboard, Building2, Users, FileText, LogOut, User, CalendarDays, Clock } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthPage from './components/AuthPage';
import Dashboard from './components/Dashboard';
import CompanySettings from './components/CompanySettings';
import EmployeeManager from './components/EmployeeManager';
import PayrollManager from './components/PayrollManager';
import LeaveManager from './components/LeaveManager';
import AttendanceManager from './components/AttendanceManager';
import './index.css';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',        icon: LayoutDashboard },
  { id: 'company',    label: 'Company Settings', icon: Building2 },
  { id: 'employees',  label: 'Employees',         icon: Users },
  { id: 'payroll',    label: 'Payroll Module',    icon: FileText },
  { id: 'leave',      label: 'Leave',             icon: CalendarDays },
  { id: 'attendance', label: 'Attendance',        icon: Clock },
];

// ─── Inner app (only rendered when authenticated) ───────────────────────────
function AppShell() {
  const { user, signOut } = useAuth();
  const [page, setPage] = useState('dashboard');
  const [signingOut, setSigningOut] = useState(false);

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
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>Workloop</h1>
          <p>UAE Payroll &amp; HRMS</p>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-section-label">Navigation</div>
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

        {/* User info + logout */}
        <div style={{
          marginTop: 'auto',
          padding: '12px 16px',
          borderTop: '1px solid rgba(255,255,255,0.1)',
        }}>
          {/* Logged-in user */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 10,
            padding: '8px 10px',
            borderRadius: 8,
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
                Signed in
              </div>
            </div>
          </div>

          {/* Sign out button */}
          <button
            onClick={handleSignOut}
            disabled={signingOut}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '7px 10px',
              borderRadius: 7,
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'transparent',
              color: 'rgba(255,255,255,0.55)',
              fontSize: 12,
              cursor: 'pointer',
              transition: 'all 0.15s',
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

      {/* Main content */}
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}

// ─── Root: shows login page or app depending on auth state ──────────────────
function Root() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
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

  return user ? <AppShell /> : <AuthPage />;
}

// ─── App: wraps everything in AuthProvider ───────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
