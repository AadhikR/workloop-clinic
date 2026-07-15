import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Home, CalendarDays, CalendarClock, Clock, FileText, User, LogOut, DollarSign, Receipt, GraduationCap, FolderOpen, Mail, Star, PanelLeftClose, PanelLeftOpen, ListTodo } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import NotificationBell from '../NotificationBell';
import { getMyEmployeeRecord, getMyCompany } from '../../utils/profileStorage';
import EmpHome from './EmpHome';
import EmpLeave from './EmpLeave';
import EmpAttendance from './EmpAttendance';
import EmpPayslips from './EmpPayslips';
import EmpProfile from './EmpProfile';
import EmpAdvances from './EmpAdvances';
import EmpSchedule from './EmpSchedule';
import EmpExpenses from './EmpExpenses';
import EmpTraining from './EmpTraining';
import EmpDocuments from './EmpDocuments';
import EmpRequests from './EmpRequests';
import EmpAppraisal from './EmpAppraisal';
import TasksPanel from '../TasksPanel';

const TABS = [
  { id: 'home',        label: 'Home',        icon: Home },
  { id: 'leave',       label: 'Leave',       icon: CalendarDays },
  { id: 'schedule',    label: 'Schedule',    icon: CalendarClock },
  { id: 'attendance',  label: 'Attendance',  icon: Clock },
  { id: 'payslips',    label: 'Payslips',    icon: FileText },
  { id: 'advances',    label: 'Advances',    icon: DollarSign },
  { id: 'expenses',    label: 'Expenses',    icon: Receipt },
  { id: 'training',    label: 'Training',    icon: GraduationCap },
  { id: 'appraisals',  label: 'Appraisals',  icon: Star },
  { id: 'documents',   label: 'Documents',   icon: FolderOpen },
  { id: 'requests',    label: 'Requests',    icon: Mail },
  { id: 'profile',     label: 'Profile',     icon: User },
  { id: 'tasks',        label: 'Tasks',       icon: ListTodo, divider: true },
];

export default function EmployeeShell() {
  const { signOut } = useAuth();
  const [tab, setTab]               = useState('home');
  const [signingOut, setSigningOut] = useState(false);
  const [emp, setEmp]               = useState(null);
  const [company, setCompany]       = useState(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try { return localStorage.getItem('emp-sidebar-collapsed') === 'true'; } catch { return false; }
  });

  const navRef = useRef(null);
  const [pill, setPill] = useState({ top: 0, height: 36 });

  useEffect(() => {
    Promise.all([getMyEmployeeRecord(), getMyCompany()]).then(([e, c]) => {
      setEmp(e);
      setCompany(c);
    });
  }, []);

  const measurePill = () => {
    if (!navRef.current) return;
    const active = navRef.current.querySelector('.nav-item.active');
    if (!active) return;
    const navRect  = navRef.current.getBoundingClientRect();
    const itemRect = active.getBoundingClientRect();
    setPill({
      top:    itemRect.top - navRect.top + navRef.current.scrollTop,
      height: itemRect.height,
    });
  };

  useLayoutEffect(() => { measurePill(); }, [tab, sidebarCollapsed]);
  useEffect(() => { const t = setTimeout(measurePill, 300); return () => clearTimeout(t); }, [sidebarCollapsed]);

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      try { localStorage.setItem('emp-sidebar-collapsed', String(next)); } catch {}
      return next;
    });
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    try { await signOut(); } catch { /* ignore */ }
    setSigningOut(false);
  };

  const renderTab = () => {
    switch (tab) {
      case 'home':       return <EmpHome onNavigate={setTab} />;
      case 'leave':      return <EmpLeave />;
      case 'schedule':   return <EmpSchedule />;
      case 'attendance': return <EmpAttendance />;
      case 'payslips':   return <EmpPayslips />;
      case 'advances':   return <EmpAdvances />;
      case 'expenses':   return <EmpExpenses />;
      case 'training':    return <EmpTraining />;
      case 'appraisals':  return <EmpAppraisal emp={emp} />;
      case 'documents':   return <EmpDocuments />;
      case 'requests':    return <EmpRequests />;
      case 'profile':    return <EmpProfile onSignOut={handleSignOut} signingOut={signingOut} />;
      case 'tasks':      return <TasksPanel role="employee" navigateTo={setTab} />;
      default:           return <EmpHome onNavigate={setTab} />;
    }
  };

  return (
    <div className="emp-shell">
      {/* Desktop sidebar */}
      <aside className={`emp-sidebar${sidebarCollapsed ? ' emp-sidebar-collapsed' : ''}`}>
        <div className="emp-sidebar-logo" style={sidebarCollapsed ? { padding: '18px 8px 14px', textAlign: 'center' } : undefined}>
          {sidebarCollapsed ? (
            <button onClick={toggleSidebar} title="Expand sidebar" className="sidebar-collapse-btn">
              <PanelLeftOpen size={16} />
            </button>
          ) : (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h1 style={{ fontSize: 15, fontWeight: 700 }}>{company?.name || 'Workloop'}</h1>
                <button onClick={toggleSidebar} title="Collapse sidebar" className="sidebar-collapse-btn">
                  <PanelLeftClose size={16} />
                </button>
              </div>
              <p style={{ fontSize: 11, marginTop: 2 }}>Employee Portal</p>
            </>
          )}
        </div>

        {/* Nav with sliding pill */}
        <nav ref={navRef} style={{ flex: 1, padding: '12px 10px', position: 'relative', overflowY: 'auto' }}>
          <div
            style={{
              position: 'absolute',
              left: 10, right: 10, top: 0,
              height: pill.height,
              background: 'linear-gradient(135deg, #2563EB 0%, #06B6D4 100%)',
              borderRadius: 10,
              pointerEvents: 'none',
              zIndex: 0,
              boxShadow: '0 4px 18px rgba(37,99,235,0.38)',
              transform: `translateY(${pill.top}px)`,
              transition: 'transform 0.40s cubic-bezier(0.34, 1.3, 0.64, 1), height 0.40s cubic-bezier(0.34, 1.3, 0.64, 1)',
            }}
          />
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <div key={t.id}>
                {t.divider && (
                  <div style={{ margin: '6px 10px', borderTop: '1px solid rgba(56,189,248,0.12)' }} />
                )}
                <button
                  className={`nav-item ${tab === t.id ? 'active' : ''}`}
                  onClick={() => setTab(t.id)}
                  title={t.label}
                >
                  <Icon size={16} />
                  {!sidebarCollapsed && <span className="nav-item-label">{t.label}</span>}
                </button>
              </div>
            );
          })}
        </nav>

        {/* Employee identity + sign out */}
        <div style={{
          padding: sidebarCollapsed ? '12px 8px' : '12px 16px',
          borderTop: '1px solid rgba(56,189,248,0.10)',
        }}>
          {emp && (
            <div style={{
              display: 'flex', alignItems: 'center',
              gap: sidebarCollapsed ? 0 : 8,
              flexDirection: sidebarCollapsed ? 'column' : 'row',
              marginBottom: 10, padding: sidebarCollapsed ? '8px 4px' : '8px 10px', borderRadius: 10,
              background: 'rgba(37,99,235,0.08)',
              border: '1px solid rgba(56,189,248,0.12)',
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: 'linear-gradient(135deg, rgba(37,99,235,0.50), rgba(6,182,212,0.50))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
                border: '1px solid rgba(56,189,248,0.20)',
              }}>
                <User size={13} color="rgba(255,255,255,0.9)" />
              </div>
              {!sidebarCollapsed && (
                <div style={{ overflow: 'hidden', flex: 1 }}>
                  <div style={{
                    fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.88)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {emp.name}
                  </div>
                  <div style={{ fontSize: 10, color: 'rgba(148,163,184,0.70)', marginTop: 1 }}>
                    {emp.jobTitle || 'Employee'}
                  </div>
                </div>
              )}
              <NotificationBell />
            </div>
          )}

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
            <LogOut size={14} />
            {!sidebarCollapsed && (signingOut ? 'Signing out…' : 'Sign out')}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className={`emp-main${sidebarCollapsed ? ' emp-main-collapsed' : ''}`}>
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
