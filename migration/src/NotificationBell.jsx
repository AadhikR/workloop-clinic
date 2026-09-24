import { useCallback, useEffect, useState } from 'react'

import {
  markAllNotificationsRead,
  markNotificationRead,
  readNotifications,
  readUnreadCount,
} from './notificationApi.js'

export default function NotificationBell({ account, authentication, branchId }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [status, setStatus] = useState('loading')

  const refreshCount = useCallback(async () => {
    try {
      const response = await readUnreadCount(authentication, account.role, branchId)
      setUnread(response.count)
      setStatus('ready')
    } catch {
      setStatus('unavailable')
    }
  }, [account.role, authentication, branchId])

  useEffect(() => {
    const initial = globalThis.setTimeout(refreshCount, 0)
    const timer = globalThis.setInterval(refreshCount, 60_000)
    return () => {
      globalThis.clearTimeout(initial)
      globalThis.clearInterval(timer)
    }
  }, [refreshCount])

  const showInbox = async () => {
    setOpen(true)
    setStatus('loading')
    try {
      const response = await readNotifications(authentication, account.role, branchId, { limit: 40 })
      setItems(response.items)
      await refreshCount()
    } catch {
      setStatus('unavailable')
    }
  }

  const readOne = async (item) => {
    if (item.readAt !== null) return
    try {
      const updated = await markNotificationRead(authentication, account.role, branchId, item.id)
      setItems((current) => current.map((value) => value.id === updated.id ? updated : value))
      setUnread((current) => Math.max(0, current - 1))
    } catch {
      setStatus('unavailable')
    }
  }

  const readAll = async () => {
    try {
      const response = await markAllNotificationsRead(authentication, account.role, branchId)
      setItems((current) => current.map((item) => ({ ...item, readAt: item.readAt ?? response.asOf })))
      setUnread(response.unreadCount)
    } catch {
      setStatus('unavailable')
    }
  }

  return (
    <section className="notification-bell" aria-label="Notifications">
      <button type="button" className="notification-toggle secondary" onClick={showInbox}>
        Notifications{unread > 0 ? ` (${unread > 99 ? '99+' : unread})` : ''}
      </button>
      {open && (
        <div className="notification-panel" role="dialog" aria-label="Notification inbox">
          <div className="notification-heading">
            <h3>Notifications</h3>
            <div>
              {unread > 0 && <button type="button" className="secondary" onClick={readAll}>Mark all read</button>}
              <button type="button" className="secondary" onClick={() => setOpen(false)}>Close</button>
            </div>
          </div>
          {status === 'loading' && <p>Loading notifications...</p>}
          {status === 'unavailable' && <p role="alert">Notifications are unavailable. Try again.</p>}
          {status === 'ready' && items.length === 0 && <p>No notifications yet.</p>}
          {status === 'ready' && items.length > 0 && (
            <ol className="notification-list">
              {items.map((item) => (
                <li key={item.id} data-read={item.readAt !== null}>
                  <button type="button" onClick={() => readOne(item)} disabled={item.readAt !== null}>
                    <strong>{item.title}</strong>
                    <span>{item.body}</span>
                    <time dateTime={item.createdAt}>{new Date(item.createdAt).toLocaleString()}</time>
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </section>
  )
}
