/**
 * ManagerShell.jsx — Portal shell for manager-role users.
 *
 * Managers are employees who have been granted the 'manager' portal role
 * by their HR admin (via admin_set_employee_portal_role RPC).
 *
 * Tabs:
 *   1. Leave Queue    — approve / reject direct reports' leave requests
 *   2. My Leave       — personal leave (reuses EmpLeave)
 *   3. My Attendance  — personal attendance (reuses EmpAttendance)
 *   4. My Payslips    — personal payslips (reuses EmpPayslips)
 *   5. Profile        — profile & sign-out (reuses EmpProfile)
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { CheckSquare, CalendarDays, CalendarClock, Clock, FileText, User, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import NotificationBell from './NotificationBell';
import { getMyEmployeeRecord, getMyCompany } from '../utils/profileStorage';
import ManagerLeaveQueue from './manager/ManagerLeaveQueue';
import EmpLeave from './employee/EmpLeave';
import EmpSchedule from './employee/EmpSchedule';
import EmpAttendance from './employee/EmpAttendance';
import EmpPayslips from './employee/EmpPayslips';
import EmpProfile from './employee/EmpProfile';

const TABS = [
  { id: 'queue',      label: 'Leave Queue',  icon: CheckSquare  },
  { id: 'leave',      label: 'My Leave',     icon: CalendarDays },
  { id: 'schedule',   label: 'Schedule',     icon: CalendarClock },
  { id: 'attendance', label: 'Attendance',   icon: Clock        },
  { id: 'payslips',   label: 'Payslips',     icon: FileText     },
  { id: 'profile',    label: 'Profile',      icon: User         },
];

export default function ManagerShell() {
  const { signOut } = useAuth();
  const [tab, setTab]               = useState('queue');
  const [signingOut, setSigningOut] = useState(false);
  const [emp, setEmp]               = useState(null);
  const [company, setCompany]       = useState(null);

  const navRef = useRef(null);
  const [pill, setPill] = useState({ top: 0, height: 36 });

  useEffect(() => {
    Promise.all([getMyEmployeeRecord(), getMyCompany()]).then(([e, c]) => {
      setEmp(e);
      setCompany(c);
    });
  }, []);

  useLayoutEffect(() => {
    if (!navRef.current) return;
    const active = navRef.current.querySelector('.nav-item.active');
    if (!active) return;
    const navRect  = navRef.current.getBoundingClientRect();
    const itemRect = active.getBoundingClientRect();
    setPill({
      top:    itemRect.top - navRect.top + navRef.current.scrollTop,
      height: itemRect.height,
    });
  }, [tab]);

  const handleSignOut = async () => {
    setSigningOut(true);
    try { await signOut(); } catch { /* ignore */ }
    setSigningOut(false);
  };

  const renderTab = () => {
    switch (tab) {
      case 'queue':      return <ManagerLeaveQueue />;
      case 'leave':      return <EmpLeave />;
      case 'schedule':   return <EmpSchedule />;
      case 'attendance': return <EmpAttendance />;
      case 'payslips':   return <EmpPayslips />;
      case 'profile':    return <EmpProfile onSignOut={handleSignOut} signingOut={signingOut} />;
      default:           return <ManagerLeaveQueue />;
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
                <p style={{ fontSize: 11, marginTop: 2 }}>Manager Portal</p>
              </>
            : <>
                <h1>Workloop</h1>
                <p>Manager Portal</p>
              </>
          }
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

        {/* Manager identity + sign out */}
        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(56,189,248,0.10)' }}>
          {emp && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              marginBottom: 10, padding: '8px 10px', borderRadius: 10,
              background: 'rgba(37,99,235,0.08)',
              border: '1px solid rgba(56,189,248,0.12)',
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: 'linear-gradient(135deg, rgba(37,99,235,0.50), rgba(6,182,212,0.50))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0, border: '1px solid rgba(56,189,248,0.20)',
              }}>
                <User size={13} color="rgba(255,255,255,0.9)" />
              </div>
              <div style={{ overflow: 'hidden', flex: 1 }}>
                <div style={{
                  fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.88)',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {emp.name}
                </div>
                <div style={{ fontSize: 10, color: 'rgba(148,163,184,0.70)', marginTop: 1 }}>
                  {emp.jobTitle || 'Manager'}
                </div>
              </div>
              <NotificationBell />
            </div>
          )}

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
