/**
 * TasksPanel.jsx — Shared tasks dashboard for all three portals.
 * Receives role ('admin' | 'manager' | 'employee') and navigateTo callback.
 * Admin also receives employees array for expiry checks.
 */
import { useState, useEffect, useCallback } from 'react';
import {
  CalendarDays, Receipt, DollarSign, Mail, FolderOpen, GraduationCap,
  Clock, FileText, AlertTriangle, Star, User, ChevronDown, ChevronRight,
  RefreshCw, Loader2,
} from 'lucide-react';
import { getAdminTasks, getManagerTasks, getEmployeeTasks } from '../utils/taskStorage';

const ICON_MAP = {
  calendar: CalendarDays,
  receipt: Receipt,
  dollar: DollarSign,
  mail: Mail,
  folder: FolderOpen,
  graduation: GraduationCap,
  clock: Clock,
  file: FileText,
  alert: AlertTriangle,
  star: Star,
  user: User,
};

const URGENCY_STYLES = {
  expired:  { bg: 'rgba(220,38,38,0.06)', border: 'rgba(220,38,38,0.25)', color: '#dc2626', dot: '#ef4444' },
  urgent:   { bg: 'rgba(220,38,38,0.05)', border: 'rgba(220,38,38,0.20)', color: '#dc2626', dot: '#ef4444' },
  action:   { bg: 'rgba(37,99,235,0.05)', border: 'rgba(37,99,235,0.18)', color: '#2563eb', dot: '#3b82f6' },
  warning:  { bg: 'rgba(245,158,11,0.06)', border: 'rgba(245,158,11,0.20)', color: '#d97706', dot: '#f59e0b' },
  info:     { bg: 'rgba(6,182,212,0.05)', border: 'rgba(6,182,212,0.18)', color: '#0891b2', dot: '#06b6d4' },
};

export default function TasksPanel({ role, navigateTo, employees }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState({});

  const loadTasks = useCallback(async () => {
    setLoading(true);
    try {
      let result;
      if (role === 'admin') result = await getAdminTasks(employees || []);
      else if (role === 'manager') result = await getManagerTasks();
      else result = await getEmployeeTasks();
      setData(result);
    } catch (err) {
      console.error('TasksPanel load error:', err);
      setData({ categories: [] });
    } finally {
      setLoading(false);
    }
  }, [role, employees]);

  useEffect(() => { loadTasks(); }, [loadTasks]);

  // Auto-refresh every 60s
  useEffect(() => {
    const interval = setInterval(loadTasks, 60000);
    return () => clearInterval(interval);
  }, [loadTasks]);

  const toggleCategory = (label) => {
    setCollapsed(prev => ({ ...prev, [label]: !prev[label] }));
  };

  const totalCount = data?.categories?.reduce((sum, c) => sum + c.items.length, 0) || 0;

  const isAdmin = role === 'admin';
  const headerClass = isAdmin ? 'page-header' : 'emp-page-header';
  const bodyClass = isAdmin ? 'page-body' : 'emp-page-body';
  const cardClass = isAdmin ? 'card' : 'emp-card';

  return (
    <div>
      <div className={headerClass}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2>Tasks</h2>
          {!loading && (
            <span style={{
              fontSize: 12, padding: '2px 10px', borderRadius: 12,
              background: totalCount > 0 ? 'rgba(37,99,235,0.10)' : 'rgba(6,182,212,0.08)',
              color: totalCount > 0 ? '#2563eb' : '#0891b2',
              fontWeight: 600,
            }}>
              {totalCount} {totalCount === 1 ? 'item' : 'items'}
            </span>
          )}
        </div>
        <button
          onClick={loadTasks}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 14px', borderRadius: 8,
            background: 'rgba(37,99,235,0.08)',
            border: '1px solid rgba(37,99,235,0.18)',
            color: '#2563eb', fontSize: 12, cursor: 'pointer',
          }}
        >
          {loading ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
          Refresh
        </button>
      </div>

      <div className={bodyClass}>
        {loading && !data && (
          <div className={cardClass} style={{ padding: 40, textAlign: 'center' }}>
            <Loader2 size={24} className="spin" style={{ color: '#2563eb', margin: '0 auto 12px' }} />
            <p style={{ color: '#64748b', fontSize: 13 }}>Loading tasks…</p>
          </div>
        )}

        {!loading && totalCount === 0 && (
          <div className={cardClass} style={{ padding: 40, textAlign: 'center' }}>
            <div style={{
              width: 48, height: 48, borderRadius: '50%', margin: '0 auto 14px',
              background: 'rgba(6,182,212,0.10)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Star size={22} style={{ color: '#06B6D4' }} />
            </div>
            <p style={{ color: '#1e293b', fontSize: 14, fontWeight: 600, marginBottom: 4 }}>
              All caught up!
            </p>
            <p style={{ color: '#94a3b8', fontSize: 12 }}>
              No pending tasks or expiry alerts right now.
            </p>
          </div>
        )}

        {data?.categories?.map(cat => {
          const Icon = ICON_MAP[cat.icon] || AlertTriangle;
          const isCollapsed = collapsed[cat.label];
          const urgentCount = cat.items.filter(i => i.urgency === 'urgent' || i.urgency === 'expired').length;

          return (
            <div key={cat.label} className={cardClass} style={{ marginBottom: 12, overflow: 'hidden' }}>
              <button
                onClick={() => toggleCategory(cat.label)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 10,
                  padding: isAdmin ? '14px 18px' : '14px 18px',
                  background: 'none', border: 'none', cursor: 'pointer',
                  borderBottom: isCollapsed ? 'none' : '1px solid rgba(100,116,139,0.10)',
                }}
              >
                <Icon size={16} style={{ color: '#06B6D4', flexShrink: 0 }} />
                <span style={{ flex: 1, textAlign: 'left', fontSize: 13, fontWeight: 600, color: '#1e293b' }}>
                  {cat.label}
                </span>
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 10,
                  background: urgentCount > 0 ? 'rgba(220,38,38,0.08)' : 'rgba(37,99,235,0.08)',
                  color: urgentCount > 0 ? '#dc2626' : '#2563eb',
                  fontWeight: 600,
                }}>
                  {cat.items.length}
                </span>
                {isCollapsed ? <ChevronRight size={14} style={{ color: '#94a3b8' }} /> :
                  <ChevronDown size={14} style={{ color: '#94a3b8' }} />}
              </button>

              {!isCollapsed && (
                <div style={{ padding: '4px 0' }}>
                  {cat.items.map(item => {
                    const style = URGENCY_STYLES[item.urgency] || URGENCY_STYLES.info;
                    return (
                      <div
                        key={item.id}
                        onClick={() => navigateTo && navigateTo(item.entity)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '10px 18px',
                          cursor: navigateTo ? 'pointer' : 'default',
                          transition: 'background 0.15s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.background = style.bg; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <div style={{
                          width: 7, height: 7, borderRadius: '50%',
                          background: style.dot, flexShrink: 0,
                        }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: 12, fontWeight: 500,
                            color: '#1e293b',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                          }}>
                            {item.title}
                          </div>
                          <div style={{
                            fontSize: 11, color: '#64748b',
                            marginTop: 2,
                          }}>
                            {item.subtitle}
                          </div>
                        </div>
                        <span style={{
                          fontSize: 10, padding: '2px 7px', borderRadius: 6,
                          background: style.bg, border: `1px solid ${style.border}`,
                          color: style.color, fontWeight: 600, flexShrink: 0,
                          textTransform: 'capitalize',
                        }}>
                          {item.urgency === 'action' ? 'Action' :
                           item.urgency === 'expired' ? 'Expired' :
                           item.urgency === 'urgent' ? 'Urgent' :
                           item.urgency === 'warning' ? 'Warning' : 'Info'}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
