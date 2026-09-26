import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  markAllNotificationsRead,
  markNotificationRead,
  parseNotification,
  readNotifications,
  readUnreadCount,
} from '../src/notificationApi.js'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const notificationId = 'b2000000-0000-4000-8000-000000000003'
const now = '2026-09-24T08:00:00.000Z'
const item = {
  id: notificationId,
  type: 'leave_approved',
  title: 'Leave approved',
  body: 'Your leave request was approved.',
  relatedEntityType: 'leave_request',
  relatedEntityId: 'b2000000-0000-4000-8000-000000000004',
  readAt: null,
  createdAt: now,
}

function client(responses) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return responses.shift()
    },
  }
}

test('notification parser enforces the exact safe camelCase shape', () => {
  assert.deepEqual(parseNotification(item), item)
  assert.throws(() => parseNotification({ ...item, recipientAppUserId: notificationId }), /Invalid/)
  assert.throws(() => parseNotification({ ...item, createdAt: '2026-09-24' }), /Invalid/)
})

test('all three roles use the migration notification routes with derived scope', async () => {
  const admin = client([{ data: {
    items: [item], nextCursor: null, asOf: now, sourceVersion: `sha256:${'a'.repeat(64)}`,
  } }])
  const manager = client([{ data: { count: 1, asOf: now } }])
  const employee = client([{ data: { ...item, readAt: now } }])

  await readNotifications(admin, 'admin', branchId, { limit: 40 })
  await readUnreadCount(manager, 'manager', branchId)
  await markNotificationRead(employee, 'employee', branchId, notificationId)

  assert.equal(admin.calls[0].path, '/api/v1/notifications?limit=40')
  assert.deepEqual(admin.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
  assert.deepEqual(manager.calls[0].options.headers, {})
  assert.deepEqual(employee.calls[0].options.headers, {})
})

test('read-all sends one idempotency key and accepts the consistent result', async () => {
  const api = client([{ data: { changedCount: 2, unreadCount: 0, asOf: now } }])
  const result = await markAllNotificationsRead(api, 'admin', branchId)
  assert.equal(result.unreadCount, 0)
  assert.equal(api.calls[0].options.method, 'POST')
  assert.equal(api.calls[0].options.headers['X-Workloop-Branch-ID'], branchId)
  assert.match(api.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
})

test('migration bell is wired without the retained Supabase notification module', async () => {
  const [bell, shell] = await Promise.all([
    readFile(new URL('../src/NotificationBell.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/OrganizationPanel.jsx', import.meta.url), 'utf8'),
  ])
  assert.equal(/supabase|notificationStorage/.test(bell), false)
  assert.match(shell, /<NotificationBell/)
})
