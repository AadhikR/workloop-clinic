import { useCallback, useEffect, useState } from 'react'
import Dialog from './PortalDialog.jsx'
import { markAllNotificationsRead, markNotificationRead, readNotifications, readUnreadCount } from './notificationApi.js'

export default function NotificationBell(props) {
  return <ScopedNotifications key={`${props.account.appUserId}:${props.account.role}:${props.branchId}`} {...props} />
}
function ScopedNotifications({ account, authentication, branchId }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [cursor, setCursor] = useState(null)
  const refreshCount = useCallback(async () => {
    try { setUnread((await readUnreadCount(authentication, account.role, branchId)).count) }
    catch { setMessage('Notifications are unavailable. Try again.') }
  }, [account.role, authentication, branchId])
  useEffect(() => {
    const initial = globalThis.setTimeout(refreshCount, 0)
    const timer = globalThis.setInterval(refreshCount, 60_000)
    return () => { globalThis.clearTimeout(initial); globalThis.clearInterval(timer) }
  }, [refreshCount])
  const load = async (next = null) => {
    setBusy(true)
    setMessage('')
    try {
      const result = await readNotifications(authentication, account.role, branchId, { limit: 40, ...(next ? { cursor: next } : {}) })
      setItems((current) => next ? [...current, ...result.items.filter((item) => !current.some((value) => value.id === item.id))] : result.items)
      setCursor(result.nextCursor)
      await refreshCount()
    } catch { setMessage('Notifications are unavailable. Try again.') }
    finally { setBusy(false) }
  }
  const markRead = async (item = null) => {
    setBusy(true)
    setMessage('')
    try {
      if (item) {
        const updated = await markNotificationRead(authentication, account.role, branchId, item.id)
        setItems((current) => current.map((value) => value.id === updated.id ? updated : value))
      } else {
        const result = await markAllNotificationsRead(authentication, account.role, branchId)
        setItems((current) => current.map((value) => ({ ...value, readAt: value.readAt ?? result.asOf })))
      }
      await refreshCount()
    } catch { setMessage('The read status could not be saved. Try again.') }
    finally { setBusy(false) }
  }
  return <section className="notification-bell" aria-label="Notifications">
    <button type="button" className="notification-toggle secondary" aria-label={`Notifications${unread > 0 ? ` (${unread > 99 ? '99+' : unread})` : ''}`} aria-expanded={open} aria-haspopup="dialog" onClick={() => { setOpen(true); load() }}>
      <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></svg>{unread > 0 && <span className="notification-count">{unread > 99 ? '99+' : unread}</span>}
    </button>
    {open && <Dialog labelledBy="notification-inbox-title" onClose={() => setOpen(false)} drawer><div className="modal-header notification-heading"><div><h3 id="notification-inbox-title">Notification inbox</h3>{unread !== null && <small>{unread} unread</small>}</div><div>{unread > 0 && <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => markRead()}>Mark all read</button>}<button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>Close</button></div></div>
      <div className="modal-body">{message && <p role="alert">{message}</p>}{busy && <p role="status">Loading notifications...</p>}{!busy && !message && items.length === 0 && <div className="empty-state"><h4>No notifications yet</h4><p>Document expiry alerts, leave updates, and payslip notifications will appear here.</p></div>}<ol className="notification-list">{items.map((item) => <li key={item.id} data-read={item.readAt !== null}><button type="button" disabled={busy || item.readAt !== null} onClick={() => markRead(item)}><span className="notification-type" aria-hidden="true">{item.type.includes('payslip') ? '$' : item.type.includes('leave') ? '✓' : '○'}</span><strong>{item.title}</strong><span>{item.body}</span><time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString()}</time></button></li>)}</ol></div>
      <div className="modal-footer"><button type="button" className="btn btn-outline" disabled={busy} onClick={() => load()}>Refresh</button>{cursor && <button type="button" disabled={busy} onClick={() => load(cursor)}>Load more</button>}</div>
    </Dialog>}
  </section>
}
