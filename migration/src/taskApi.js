const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const sourceVersionPattern = /^sha256:[0-9a-f]{64}$/
const taskIdPattern = /^[a-zA-Z][a-zA-Z0-9]*:[0-9a-f-]{36}(?::[a-zA-Z0-9]+)?$/
const urgencyValues = new Set(['action', 'expired', 'urgent', 'warning', 'info'])

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

export function parseTask(value) {
  if (
    !exactKeys(value, [
      'id', 'entity', 'entityId', 'title', 'subtitle', 'urgency', 'dueDate', 'createdAt',
      'navigation',
    ])
    || !taskIdPattern.test(value.id)
    || typeof value.entity !== 'string'
    || !uuidPattern.test(value.entityId)
    || typeof value.title !== 'string'
    || typeof value.subtitle !== 'string'
    || !urgencyValues.has(value.urgency)
    || !(value.dueDate === null || datePattern.test(value.dueDate))
    || !(value.createdAt === null || timestampPattern.test(value.createdAt))
    || !exactKeys(value.navigation, ['screen'])
    || typeof value.navigation.screen !== 'string'
  ) throw new Error('Invalid task response')
  return value
}

export function parseTaskCatalogue(response) {
  if (
    !exactKeys(response, ['categories', 'nextCursor', 'asOf', 'sourceVersion'])
    || !Array.isArray(response.categories)
    || !(response.nextCursor === null || typeof response.nextCursor === 'string')
    || !timestampPattern.test(response.asOf)
    || !sourceVersionPattern.test(response.sourceVersion)
  ) throw new Error('Invalid task response')
  const categories = response.categories.map((category) => {
    if (
      !exactKeys(category, ['code', 'label', 'status', 'count', 'items', 'errorCode'])
      || typeof category.code !== 'string'
      || typeof category.label !== 'string'
      || !['ok', 'empty', 'failed'].includes(category.status)
      || !Number.isInteger(category.count)
      || category.count < 0
      || !Array.isArray(category.items)
      || (category.status === 'empty' && (category.count !== 0 || category.items.length !== 0))
      || (category.status === 'failed'
        && (category.count !== 0 || category.items.length !== 0
          || category.errorCode !== 'task_source_unavailable'))
      || (category.status !== 'failed' && category.errorCode !== null)
    ) throw new Error('Invalid task response')
    return { ...category, items: category.items.map(parseTask) }
  })
  return { ...response, categories }
}

function headers(role, branchId) {
  if (!['admin', 'manager', 'employee'].includes(role)) throw new TypeError('Invalid role')
  if (role !== 'admin') return {}
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

export async function readTasks(authentication, role, branchId, options = {}) {
  const parameters = new URLSearchParams()
  if (options.category !== undefined && options.category !== '') {
    if (typeof options.category !== 'string' || options.category.length > 64) {
      throw new TypeError('Invalid task category')
    }
    parameters.set('category', options.category)
  }
  if (options.urgency !== undefined && options.urgency !== '') {
    if (!urgencyValues.has(options.urgency)) throw new TypeError('Invalid task urgency')
    parameters.set('urgency', options.urgency)
  }
  if (options.limit !== undefined) {
    if (!Number.isInteger(options.limit) || options.limit < 1 || options.limit > 200) {
      throw new TypeError('Invalid task limit')
    }
    parameters.set('limit', String(options.limit))
  }
  if (options.cursor !== undefined && options.cursor !== null) {
    if (typeof options.cursor !== 'string' || options.cursor.length > 512) {
      throw new TypeError('Invalid task cursor')
    }
    parameters.set('cursor', options.cursor)
  }
  const query = parameters.size ? `?${parameters}` : ''
  const envelope = await authentication.request(`/api/v1/tasks${query}`, {
    access: 'protected', headers: headers(role, branchId),
  })
  return parseTaskCatalogue(envelope.data)
}
