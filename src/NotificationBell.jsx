import { useCallback, useEffect, useRef, useState } from 'react'

import {
  markAllNotificationsRead,
  markNotificationRead,
  readNotifications,
  readUnreadCount,
} from './notificationApi.js'

export default function NotificationBell({ account, authentication, branchId }) {
  const closeButtonRef = useRef(null)
  const toggleButtonRef = useRef(null)
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

  const closeInbox = useCallback(() => {
    setOpen(false)
    queueMicrotask(() => toggleButtonRef.current?.focus())
  }, [])

  useEffect(() => {
    if (!open) return undefined
    closeButtonRef.current?.focus()
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') closeInbox()
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [closeInbox, open])

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
      <button
        ref={toggleButtonRef}
        type="button"
        className="notification-toggle secondary"
        aria-label={`Notifications${unread > 0 ? ` (${unread > 99 ? '99+' : unread})` : ''}`}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={showInbox}
      >
        Notifications{unread > 0 ? ` (${unread > 99 ? '99+' : unread})` : ''}
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
          <path d="M10 21h4" />
        </svg>
      </button>
      {open && (
        <div className="notification-panel" role="dialog" aria-label="Notification inbox">
          <div className="notification-heading">
            <h3>Notifications</h3>
            <div>
              {unread > 0 && <button type="button" className="secondary" onClick={readAll}>Mark all read</button>}
              <button ref={closeButtonRef} type="button" className="secondary" onClick={closeInbox}>Close</button>
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
