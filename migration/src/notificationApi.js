const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const sourceVersionPattern = /^sha256:[0-9a-f]{64}$/

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

export function parseNotification(value) {
  if (
    !exactKeys(value, [
      'id', 'type', 'title', 'body', 'relatedEntityType', 'relatedEntityId', 'readAt',
      'createdAt',
    ])
    || !uuidPattern.test(value.id)
    || typeof value.type !== 'string'
    || typeof value.title !== 'string'
    || typeof value.body !== 'string'
    || typeof value.relatedEntityType !== 'string'
    || typeof value.relatedEntityId !== 'string'
    || !(value.readAt === null || timestampPattern.test(value.readAt))
    || !timestampPattern.test(value.createdAt)
  ) throw new Error('Invalid notification response')
  return value
}

function headers(role, branchId, mutation = false) {
  if (!['admin', 'manager', 'employee'].includes(role)) throw new TypeError('Invalid role')
  if (role !== 'admin') {
    return mutation ? { 'Idempotency-Key': crypto.randomUUID() } : {}
  }
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    'X-Workloop-Branch-ID': branchId,
    ...(mutation ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

export async function readNotifications(authentication, role, branchId, options = {}) {
  const parameters = new URLSearchParams()
  if (options.limit !== undefined) {
    if (!Number.isInteger(options.limit) || options.limit < 1 || options.limit > 200) {
      throw new TypeError('Invalid notification limit')
    }
    parameters.set('limit', String(options.limit))
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    if (typeof options.cursor !== 'string' || options.cursor.length > 512) {
      throw new TypeError('Invalid notification cursor')
    }
    parameters.set('cursor', options.cursor)
  }
  const query = parameters.size ? `?${parameters}` : ''
  const envelope = await authentication.request(`/api/v1/notifications${query}`, {
    access: 'protected', headers: headers(role, branchId),
  })
  const response = envelope.data
  if (
    !exactKeys(response, ['items', 'nextCursor', 'asOf', 'sourceVersion'])
    || !Array.isArray(response.items)
    || !(response.nextCursor === null || typeof response.nextCursor === 'string')
    || !timestampPattern.test(response.asOf)
    || !sourceVersionPattern.test(response.sourceVersion)
  ) throw new Error('Invalid notification response')
  return { ...response, items: response.items.map(parseNotification) }
}

export async function readUnreadCount(authentication, role, branchId) {
  const response = (await authentication.request('/api/v1/notifications/unread-count', {
    access: 'protected', headers: headers(role, branchId),
  })).data
  if (
    !exactKeys(response, ['count', 'asOf']) || !Number.isInteger(response.count)
    || response.count < 0 || !timestampPattern.test(response.asOf)
  ) throw new Error('Invalid notification response')
  return response
}

export async function markNotificationRead(authentication, role, branchId, notificationId) {
  if (!uuidPattern.test(notificationId)) throw new TypeError('Invalid notification ID')
  const response = await authentication.request(`/api/v1/notifications/${notificationId}/read`, {
    access: 'protected', method: 'PUT', headers: headers(role, branchId),
  })
  return parseNotification(response.data)
}

export async function markAllNotificationsRead(authentication, role, branchId) {
  const response = (await authentication.request('/api/v1/notifications/read-all', {
    access: 'protected', method: 'POST', headers: headers(role, branchId, true), json: {},
  })).data
  if (
    !exactKeys(response, ['changedCount', 'unreadCount', 'asOf'])
    || !Number.isInteger(response.changedCount) || response.changedCount < 0
    || !Number.isInteger(response.unreadCount) || response.unreadCount < 0
    || !timestampPattern.test(response.asOf)
  ) throw new Error('Invalid notification response')
  return response
}
