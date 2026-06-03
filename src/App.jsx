import { useState, useRef, useLayoutEffect, useEffect } from 'react';
import { LayoutDashboard, Building2, Users, FileText, LogOut, User, CalendarDays, Clock, DollarSign, LayoutGrid } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import AuthPage from './components/AuthPage';
import { getCompany } from './utils/storage';
import NotificationBell from './components/NotificationBell';
import Dashboard from './components/Dashboard';
import CompanySettings from './components/CompanySettings';
import EmployeeManager from './components/EmployeeManager';
import PayrollManager from './components/PayrollManager';
import LeaveManager from './components/LeaveManager';
import AttendanceManager from './components/AttendanceManager';
import AdvancesManager from './components/AdvancesManager';
import RosterManager from './components/RosterManager';
import EmployeeShell from './components/employee/EmployeeShell';
import ManagerShell from './components/ManagerShell';
import './index.css';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',        icon: LayoutDashboard },
  { id: 'company',    label: 'Company Settings', icon: Building2 },
  { id: 'employees',  label: 'Employees',         icon: Users },
  { id: 'payroll',    label: 'Payroll Module',    icon: FileText },
  { id: 'advances',   label: 'Advances',          icon: DollarSign },
  { id: 'leave',      label: 'Leave',             icon: CalendarDays },
  { id: 'attendance', label: 'Attendance',        icon: Clock },
  { id: 'roster',     label: 'Roster',            icon: LayoutGrid },
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
      case 'advances':   return <AdvancesManager />;
      case 'leave':      return <LeaveManager />;
      case 'attendance': return <AttendanceManager />;
      case 'roster':     return <RosterManager />;
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
          borderTop: '1px solid rgba(56,189,248,0.10)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            marginBottom: 10, padding: '8px 10px', borderRadius: 10,
            background: 'rgba(37,99,235,0.08)',
            border: '1px solid rgba(56,189,248,0.12)',
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: '50%',
              background: 'linear-gradient(135deg, rgba(37,99,235,0.50), rgba(6,182,212,0.50))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
              border: '1px solid rgba(56,189,248,0.20)',
            }}>
              <User size={14} color="rgba(255,255,255,0.9)" />
            </div>
            <div style={{ overflow: 'hidden', flex: 1 }}>
              <div style={{
                fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.88)',
                whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
              }}>
                {user?.email}
              </div>
              <div style={{ fontSize: 10, color: 'rgba(148,163,184,0.70)', marginTop: 1 }}>
                HR Admin
              </div>
            </div>
            <NotificationBell />
          </div>

          <button
            onClick={handleSignOut}
            disabled={signingOut}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 8,
              padding: '7px 10px', borderRadius: 8,
              border: '1px solid rgba(56,189,248,0.10)',
              background: 'transparent', color: 'rgba(148,163,184,0.70)',
              fontSize: 12, cursor: 'pointer', transition: 'all 0.18s',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(220,38,38,0.15)';
              e.currentTarget.style.color = 'rgba(252,165,165,0.95)';
              e.currentTarget.style.borderColor = 'rgba(220,38,38,0.25)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = 'rgba(148,163,184,0.70)';
              e.currentTarget.style.borderColor = 'rgba(56,189,248,0.10)';
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

// ─── Shared spinner / error screens ──────────────────────────────────────────
const PAGE_BG = {
  minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
  background: '#F8FAFC',
  backgroundImage: 'radial-gradient(ellipse 70% 55% at 20% 40%, rgba(37,99,235,0.07) 0%, transparent 65%), radial-gradient(ellipse 60% 45% at 80% 20%, rgba(6,182,212,0.05) 0%, transparent 65%)',
};
const SPIN_CSS = `@keyframes spin { to { transform: rotate(360deg); } }`;

function Spinner({ label = 'Loading…' }) {
  return (
    <div style={PAGE_BG}>
      <div style={{ textAlign: 'center', color: '#64748B' }}>
        <div style={{ width: 40, height: 40, border: '3px solid rgba(37,99,235,0.18)', borderTopColor: '#2563EB', borderRadius: '50%', animation: 'spin 0.8s linear infinite', margin: '0 auto 16px' }} />
        <p style={{ fontSize: 14 }}>{label}</p>
      </div>
      <style>{SPIN_CSS}</style>
    </div>
  );
}

// ─── Root: resolves role then renders the correct shell ──────────────────────
function Root() {
  const { user, profile, loading, signOut } = useAuth();
  // If profile is still null 8 s after loading finished, let the user escape.
  const [profileTimeout, setProfileTimeout] = useState(false);

  useEffect(() => {
    if (!loading && user && !profile) {
      const t = setTimeout(() => setProfileTimeout(true), 8000);
      return () => clearTimeout(t);
    }
    setProfileTimeout(false);
  }, [loading, user, profile]);

  if (loading) return <Spinner label="Loading…" />;
  if (!user)   return <AuthPage />;

  // Profile is being resolved (INITIAL_SESSION handler is running).
  // Show a spinner for up to 8 s, then offer a sign-out escape hatch.
  if (!profile) {
    if (profileTimeout) {
      return (
        <div style={PAGE_BG}>
          <div style={{ textAlign: 'center', color: '#64748B', maxWidth: 320 }}>
            <p style={{ fontSize: 15, fontWeight: 600, color: '#1e293b', marginBottom: 8 }}>Could not load your account</p>
            <p style={{ fontSize: 13, marginBottom: 20 }}>
              Your session exists but your profile could not be read. This is usually a database permissions issue — ask your admin to check the Supabase RLS policies.
            </p>
            <button
              onClick={() => signOut().catch(() => {})}
              style={{ background: '#2563EB', color: '#fff', border: 'none', borderRadius: 10, padding: '10px 24px', fontSize: 14, fontWeight: 600, cursor: 'pointer' }}
            >
              Sign out and try again
            </button>
          </div>
          <style>{SPIN_CSS}</style>
        </div>
      );
    }
    return <Spinner label="Setting up your account…" />;
  }

  if (profile.role === 'employee') return <EmployeeShell />;
  if (profile.role === 'manager')  return <ManagerShell />;
  return <AppShell />;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
