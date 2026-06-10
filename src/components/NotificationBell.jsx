/**
 * NotificationBell.jsx — Bell icon with unread badge + right-side panel.
 * Used in both AppShell (admin) and EmployeeShell sidebars.
 * Polls getUnreadCount() every 60 seconds; loads full list when panel opens.
 */
import { useState, useEffect, useRef } from 'react';
import { Bell, X, CheckCheck } from 'lucide-react';
import {
  getNotifications, getUnreadCount,
  markNotificationRead, markAllNotificationsRead,
} from '../utils/notificationStorage';

const TYPE_ICON = {
  document_expiry:   '📄',
  wps_deadline:      '⚠️',
  insurance_expiry:  '🏥',
  policy_renewal:    '🔄',
  leave_approved:    '✅',
  leave_rejected:    '❌',
  leave_submitted:   '📝',
  payslip_available: '💰',
};

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationBell() {
  const [open, setOpen]     = useState(false);
  const [unread, setUnread] = useState(0);
  const [notifs, setNotifs] = useState([]);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef(null);

  const refreshCount = async () => {
    try { setUnread(await getUnreadCount()); } catch { /* ignore */ }
  };

  const openPanel = async () => {
    setOpen(true);
    setLoading(true);
    try {
      const list = await getNotifications(40);
      setNotifs(list);
      setUnread(list.filter(n => !n.readAt).length);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  };

  useEffect(() => {
    refreshCount();
    pollRef.current = setInterval(refreshCount, 60000);
    return () => clearInterval(pollRef.current);
  }, []);

  const handleMarkRead = async (n) => {
    if (n.readAt) return;
    try {
      await markNotificationRead(n.id);
      setNotifs(prev => prev.map(x => x.id === n.id ? { ...x, readAt: new Date().toISOString() } : x));
      setUnread(prev => Math.max(0, prev - 1));
    } catch { /* ignore */ }
  };

  const handleMarkAll = async () => {
    try {
      await markAllNotificationsRead();
      setNotifs(prev => prev.map(x => ({ ...x, readAt: x.readAt || new Date().toISOString() })));
      setUnread(0);
    } catch { /* ignore */ }
  };

  return (
    <>
      {/* Bell button */}
      <button
        onClick={openPanel}
        title="Notifications"
        style={{
          position: 'relative', background: 'transparent', border: 'none',
          cursor: 'pointer', padding: '6px 8px', borderRadius: 8,
          color: 'rgba(148,163,184,0.85)', display: 'flex', alignItems: 'center',
          transition: 'background 0.15s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,71,67,0.15)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        <Bell size={16} />
        {unread > 0 && (
          <span style={{
            position: 'absolute', top: 1, right: 1,
            background: '#ef4444', color: '#fff',
            borderRadius: '50%', fontSize: 9, fontWeight: 700,
            minWidth: 15, height: 15,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            lineHeight: 1, padding: '0 2px',
          }}>
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {/* Overlay + panel */}
      {open && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 2000 }}>
          {/* Backdrop */}
          <div
            style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.18)' }}
            onClick={() => setOpen(false)}
          />

          {/* Right-side panel */}
          <div style={{
            position: 'absolute', right: 12, top: 12, bottom: 12,
            width: 380, background: '#fff', borderRadius: 16,
            boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
            zIndex: 2001, display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* Header */}
            <div style={{
              padding: '16px 20px', borderBottom: '1px solid var(--gray-100)',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              flexShrink: 0,
            }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 15, color: 'var(--gray-900)' }}>
                  Notifications
                </div>
                {unread > 0 && (
                  <div style={{ fontSize: 12, color: 'var(--gray-400)', marginTop: 2 }}>
                    {unread} unread
                  </div>
                )}
              </div>
              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                {unread > 0 && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={handleMarkAll}
                    style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 4 }}
                  >
                    <CheckCheck size={13} /> All read
                  </button>
                )}
                <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setOpen(false)}>
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Notification list */}
            <div style={{ overflowY: 'auto', flex: 1 }}>
              {loading ? (
                <div style={{ padding: 24, textAlign: 'center', color: 'var(--gray-400)', fontSize: 13 }}>
                  Loading…
                </div>
              ) : notifs.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)', fontSize: 13 }}>
                  <Bell size={32} style={{ marginBottom: 12, opacity: 0.25, display: 'block', margin: '0 auto 12px' }} />
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>No notifications yet</div>
                  <div style={{ fontSize: 12, lineHeight: 1.5 }}>
                    Document expiry alerts, leave updates, and payslip notifications will appear here.
                  </div>
                </div>
              ) : (
                notifs.map(n => (
                  <div
                    key={n.id}
                    onClick={() => handleMarkRead(n)}
                    style={{
                      padding: '13px 20px',
                      borderBottom: '1px solid var(--gray-100)',
                      cursor: n.readAt ? 'default' : 'pointer',
                      background: n.readAt ? 'transparent' : '#f0f7ff',
                      display: 'flex', gap: 12, alignItems: 'flex-start',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={e => { if (!n.readAt) e.currentTarget.style.background = '#e8f1fe'; }}
                    onMouseLeave={e => { if (!n.readAt) e.currentTarget.style.background = '#f0f7ff'; }}
                  >
                    <div style={{ fontSize: 18, flexShrink: 0, marginTop: 2, lineHeight: 1 }}>
                      {TYPE_ICON[n.type] || '🔔'}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: n.readAt ? 500 : 700, fontSize: 13.5, color: 'var(--gray-800)', lineHeight: 1.35 }}>
                        {n.title}
                      </div>
                      {n.body && (
                        <div style={{ fontSize: 12.5, color: 'var(--gray-500)', marginTop: 3, lineHeight: 1.45 }}>
                          {n.body}
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 5 }}>
                        {timeAgo(n.createdAt)}
                      </div>
                    </div>
                    {!n.readAt && (
                      <div style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: 'var(--primary)', flexShrink: 0, marginTop: 5,
                      }} />
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
