import { useState, useRef, useLayoutEffect, useEffect } from 'react';
import { LayoutDashboard, Building2, Users, FileText, LogOut, User, CalendarDays, Clock, DollarSign, LayoutGrid, BarChart2, Receipt, Package, GraduationCap, ChevronDown, Plus, X, Check, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { CompanyProvider, useCompany } from './context/CompanyContext';
import AuthPage from './components/AuthPage';
import NotificationBell from './components/NotificationBell';
import Dashboard from './components/Dashboard';
import CompanySettings from './components/CompanySettings';
import EmployeeManager from './components/EmployeeManager';
import PayrollManager from './components/PayrollManager';
import LeaveManager from './components/LeaveManager';
import AttendanceManager from './components/AttendanceManager';
import AdvancesManager from './components/AdvancesManager';
import RosterManager from './components/RosterManager';
import Reports from './components/Reports';
import ExpensesManager from './components/ExpensesManager';
import AssetsManager from './components/AssetsManager';
import TrainingManager from './components/TrainingManager';
import EmployeeShell from './components/employee/EmployeeShell';
import ManagerShell from './components/ManagerShell';
import './index.css';

const NAV_ITEMS = [
  { id: 'dashboard',  label: 'Dashboard',        icon: LayoutDashboard },
  { id: 'company',    label: 'Company Settings', icon: Building2 },
  { id: 'employees',  label: 'Employees',         icon: Users },
  { id: 'payroll',    label: 'Payroll Module',    icon: FileText },
  { id: 'advances',   label: 'Advances',          icon: DollarSign },
  { id: 'expenses',   label: 'Expenses',          icon: Receipt },
  { id: 'leave',      label: 'Leave',             icon: CalendarDays },
  { id: 'attendance', label: 'Attendance',        icon: Clock },
  { id: 'assets',     label: 'Assets',            icon: Package },
  { id: 'training',   label: 'Training',          icon: GraduationCap },
  { id: 'roster',     label: 'Roster',            icon: LayoutGrid },
  { id: 'reports',    label: 'Reports',           icon: BarChart2 },
];

// ─── Admin shell (HR users) ──────────────────────────────────────────────────
function AppShell() {
  const { user, signOut } = useAuth();
  const { companies, activeCompany, activeCompanyId, setActiveCompanyId, createBranch, deleteBranch } = useCompany();
  const [page, setPage]               = useState('dashboard');
  const [signingOut, setSigningOut]   = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return localStorage.getItem('sidebar-collapsed') === 'true'; } catch { return false; }
  });
  const navRef  = useRef(null);
  const [pill, setPill] = useState({ top: 0, height: 36 });

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('sidebar-collapsed', String(next)); } catch {}
      return next;
    });
  };

  // ── Branch switcher state ──
  const switcherRef                   = useRef(null);
  const [showSwitcher, setShowSwitcher] = useState(false);
  const [showNewBranch, setShowNewBranch] = useState(false);
  const [newBranchName, setNewBranchName] = useState('');
  const [creatingBranch, setCreatingBranch] = useState(false);
  const [branchError, setBranchError] = useState('');

  // Close the branch dropdown on click-outside
  useEffect(() => {
    if (!showSwitcher) return;
    const handler = (e) => {
      if (switcherRef.current && !switcherRef.current.contains(e.target)) {
        setShowSwitcher(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSwitcher]);

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
  }, [page, sidebarCollapsed]);

  const handleSignOut = async () => {
    setSigningOut(true);
    try { await signOut(); } catch { /* ignore */ }
    setSigningOut(false);
  };

  const handleCreateBranch = async () => {
    if (!newBranchName.trim()) return;
    setCreatingBranch(true);
    setBranchError('');
    try {
      await createBranch(newBranchName.trim(), activeCompany);
      setShowNewBranch(false);
      setNewBranchName('');
      // Auto-navigate to Company Settings so user can configure the new branch
      setPage('company');
    } catch (err) {
      setBranchError(err.message || 'Failed to create branch');
    } finally {
      setCreatingBranch(false);
    }
  };

  const handleDeleteBranch = async (id) => {
    if (!window.confirm('Delete this branch? This cannot be undone.')) return;
    try {
      await deleteBranch(id);
    } catch (err) {
      alert(err.message);
    }
  };

  // Display label for active branch in the switcher button
  const activeBranchLabel = activeCompany
    ? (activeCompany.branchName || activeCompany.name || 'Unnamed Branch')
    : 'Setup Company';

  const renderPage = () => {
    switch (page) {
      case 'dashboard':  return <Dashboard onNavigate={setPage} />;
      case 'company':    return <CompanySettings />;
      case 'employees':  return <EmployeeManager />;
      case 'payroll':    return <PayrollManager />;
      case 'advances':   return <AdvancesManager />;
      case 'expenses':   return <ExpensesManager />;
      case 'leave':      return <LeaveManager />;
      case 'attendance': return <AttendanceManager />;
      case 'assets':     return <AssetsManager />;
      case 'training':   return <TrainingManager />;
      case 'roster':     return <RosterManager />;
      case 'reports':    return <Reports />;
      default:           return <Dashboard onNavigate={setPage} />;
    }
  };

  return (
    <div className="app-layout">
      <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`}>
        {/* ── Brand + Company/Branch Switcher ── */}
        <div className={`sidebar-logo${sidebarCollapsed ? ' sidebar-logo--collapsed' : ''}`}>
          {!sidebarCollapsed ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h1>Workloop</h1>
                <button
                  onClick={toggleSidebar}
                  title="Collapse sidebar"
                  className="sidebar-collapse-btn"
                >
                  <PanelLeftClose size={15} />
                </button>
              </div>

              {/* Branch switcher button */}
              <div style={{ position: 'relative', marginTop: 6 }} ref={switcherRef}>
                <button
                  onClick={() => setShowSwitcher(s => !s)}
                  title="Switch branch"
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', gap: 6,
                    padding: '5px 8px', borderRadius: 7,
                    border: '1px solid rgba(56,189,248,0.15)',
                    background: 'rgba(37,99,235,0.08)',
                    color: 'rgba(255,255,255,0.80)', fontSize: 11, fontWeight: 500,
                    cursor: 'pointer', textAlign: 'left',
                  }}
                >
                  <Building2 size={11} style={{ flexShrink: 0, color: 'rgba(6,182,212,0.80)' }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {activeBranchLabel}
                  </span>
                  {companies.length > 1 && (
                    <span style={{
                      fontSize: 9, background: 'rgba(37,99,235,0.30)',
                      padding: '1px 5px', borderRadius: 10, flexShrink: 0,
                      color: 'rgba(148,213,202,0.90)',
                    }}>
                      {companies.length}
                    </span>
                  )}
                  <ChevronDown
                    size={11}
                    style={{
                      flexShrink: 0,
                      transform: showSwitcher ? 'rotate(180deg)' : 'none',
                      transition: 'transform 0.18s',
                    }}
                  />
                </button>

                {/* Branch dropdown */}
                {showSwitcher && (
                  <div style={{
                    position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
                    background: '#0d1b3e', border: '1px solid rgba(56,189,248,0.15)',
                    borderRadius: 8, zIndex: 200, overflow: 'hidden',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.40)',
                  }}>
                    {companies.map(co => {
                      const label = co.branchName || co.name || 'Unnamed';
                      const isActive = co.id === activeCompanyId;
                      return (
                        <div
                          key={co.id}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 6,
                            padding: '7px 10px',
                            background: isActive ? 'rgba(37,99,235,0.18)' : 'transparent',
                            borderBottom: '1px solid rgba(56,189,248,0.06)',
                          }}
                        >
                          <button
                            onClick={() => { setActiveCompanyId(co.id); setShowSwitcher(false); }}
                            style={{
                              flex: 1, display: 'flex', alignItems: 'center', gap: 6,
                              background: 'none', border: 'none', cursor: 'pointer',
                              color: isActive ? 'rgba(255,255,255,0.95)' : 'rgba(148,163,184,0.85)',
                              fontSize: 11, fontWeight: isActive ? 600 : 400, textAlign: 'left',
                              padding: 0,
                            }}
                          >
                            {isActive && <Check size={10} style={{ color: '#06B6D4', flexShrink: 0 }} />}
                            {!isActive && <span style={{ width: 10, flexShrink: 0 }} />}
                            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {label}
                            </span>
                          </button>
                          {/* Delete branch — only shown when there's more than one branch */}
                          {companies.length > 1 && !isActive && (
                            <button
                              onClick={() => { setShowSwitcher(false); handleDeleteBranch(co.id); }}
                              title={`Delete ${label}`}
                              style={{
                                flexShrink: 0, background: 'none', border: 'none',
                                cursor: 'pointer', color: 'rgba(148,163,184,0.45)',
                                padding: 2, borderRadius: 4, lineHeight: 1,
                              }}
                            >
                              <X size={11} />
                            </button>
                          )}
                        </div>
                      );
                    })}

                    {/* Add branch */}
                    <button
                      onClick={() => { setShowSwitcher(false); setShowNewBranch(true); }}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', gap: 6,
                        padding: '7px 10px', background: 'none', border: 'none',
                        cursor: 'pointer', color: 'rgba(6,182,212,0.85)',
                        fontSize: 11, fontWeight: 500,
                      }}
                    >
                      <Plus size={11} />
                      Add Branch
                    </button>
                  </div>
                )}
              </div>
            </>
          ) : (
            /* Collapsed: show only the expand button */
            <button
              onClick={toggleSidebar}
              title="Expand sidebar"
              className="sidebar-collapse-btn"
            >
              <PanelLeftOpen size={15} />
            </button>
          )}
        </div>

        <nav className="sidebar-nav" ref={navRef}>
          {!sidebarCollapsed && <div className="nav-section-label">Navigation</div>}

          {/* Sliding pill behind active item */}
          <div className="nav-pill" style={{ transform: `translateY(${pill.top}px)`, height: pill.height }} />

          {NAV_ITEMS.map(item => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
                title={item.label}
              >
                <Icon size={16} />
                {!sidebarCollapsed && <span className="nav-item-label">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div style={{
          marginTop: 'auto',
          padding: sidebarCollapsed ? '12px 8px' : '12px 16px',
          borderTop: '1px solid rgba(56,189,248,0.10)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center',
            gap: sidebarCollapsed ? 0 : 10,
            flexDirection: sidebarCollapsed ? 'column' : 'row',
            marginBottom: 10, padding: sidebarCollapsed ? '8px 4px' : '8px 10px', borderRadius: 10,
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
            {!sidebarCollapsed && (
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
            )}
            <NotificationBell />
          </div>

          <button
            onClick={handleSignOut}
            disabled={signingOut}
            title="Sign out"
            style={{
              width: '100%', display: 'flex', alignItems: 'center',
              justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
              gap: 8,
              padding: sidebarCollapsed ? '7px 0' : '7px 10px', borderRadius: 8,
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
            {!sidebarCollapsed && (signingOut ? 'Signing out…' : 'Sign out')}
          </button>
        </div>
      </aside>

      <main className={`main-content${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        {renderPage()}
      </main>

      {/* ── New Branch modal ── */}
      {showNewBranch && (
        <div
          className="modal-backdrop"
          onClick={() => { setShowNewBranch(false); setNewBranchName(''); setBranchError(''); }}
        >
          <div className="modal" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: 16 }}>Add New Branch</h3>
              <button
                onClick={() => { setShowNewBranch(false); setNewBranchName(''); setBranchError(''); }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--gray-400)' }}
              >
                <X size={18} />
              </button>
            </div>
            <div className="modal-body">
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--gray-700)' }}>Branch Name</label>
              <input
                className="form-control"
                placeholder="e.g. Abu Dhabi Branch"
                value={newBranchName}
                onChange={e => setNewBranchName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreateBranch()}
                autoFocus
                style={{ marginTop: 6 }}
              />
              <p style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 8 }}>
                This label identifies the branch in the switcher. Configure the branch's company name,
                MOL Employer ID, and other details in Company Settings after creation.
              </p>
              {branchError && (
                <p style={{ fontSize: 12, color: 'var(--red-600)', marginTop: 6 }}>{branchError}</p>
              )}
            </div>
            <div className="modal-footer">
              <button
                className="btn"
                onClick={() => { setShowNewBranch(false); setNewBranchName(''); setBranchError(''); }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCreateBranch}
                disabled={!newBranchName.trim() || creatingBranch}
              >
                {creatingBranch ? 'Creating…' : 'Create Branch'}
              </button>
            </div>
          </div>
        </div>
      )}
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
  // Admins get the multi-company context
  return <CompanyProvider><AppShell /></CompanyProvider>;
}

export default function App() {
  return (
    <AuthProvider>
      <Root />
    </AuthProvider>
  );
}
