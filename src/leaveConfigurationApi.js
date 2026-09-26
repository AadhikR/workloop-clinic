const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const dayPattern = /^(?:0|[1-9]\d{0,3})\.\d{2}$/

const settingsKeys = [
  'id', 'branchId', 'leaveYearType', 'weekendDefinition', 'carryForwardEnabled',
  'carryForwardMaxDays', 'approvalChain', 'ramadanActive', 'ramadanStart', 'ramadanEnd',
  'createdAt', 'updatedAt',
]
const typeKeys = [
  'id', 'branchId', 'code', 'name', 'color', 'isPaid', 'isUnlimited', 'requiresApproval',
  'requiresAttachment', 'requiresReason', 'minNoticeDays', 'annualEntitlementDays',
  'accrualType', 'dayCountType', 'autoApprove', 'carryForwardAllowed',
  'carryForwardMaxDays', 'genderRestriction', 'minServiceMonths', 'oncePerCareer',
  'notDeductedFromAnnual', 'affectsPayroll', 'lawReference', 'isActive', 'sortOrder',
  'probationEligible', 'createdAt', 'updatedAt',
]
const holidayKeys = ['id', 'branchId', 'date', 'name', 'type', 'year', 'createdAt']
const typeMutationKeys = typeKeys.filter((key) => ![
  'id', 'branchId', 'createdAt', 'updatedAt',
].includes(key))

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function hasExactKeys(value, expected) {
  if (!isRecord(value)) return false
  const actual = Object.keys(value).sort()
  const required = [...expected].sort()
  return actual.length === required.length
    && actual.every((key, index) => key === required[index])
}

function invalidResponse() {
  return new Error('Invalid leave configuration response')
}

function isDateOrNull(value) {
  return value === null || typeof value === 'string' && datePattern.test(value)
}

export function parseLeaveSettings(value) {
  if (
    !hasExactKeys(value, settingsKeys)
    || !uuidPattern.test(value.id)
    || !uuidPattern.test(value.branchId)
    || value.leaveYearType !== 'calendar'
    || !['fri-sat', 'sat-sun'].includes(value.weekendDefinition)
    || typeof value.carryForwardEnabled !== 'boolean'
    || !Number.isInteger(value.carryForwardMaxDays)
    || value.carryForwardMaxDays < 0
    || value.carryForwardMaxDays > 366
    || !['1-level', '2-level'].includes(value.approvalChain)
    || typeof value.ramadanActive !== 'boolean'
    || !isDateOrNull(value.ramadanStart)
    || !isDateOrNull(value.ramadanEnd)
    || (value.ramadanStart === null) !== (value.ramadanEnd === null)
    || value.ramadanStart !== null && value.ramadanEnd < value.ramadanStart
    || !instantPattern.test(value.createdAt)
    || !instantPattern.test(value.updatedAt)
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

export function parseLeaveType(value) {
  const booleans = [
    'isPaid', 'isUnlimited', 'requiresApproval', 'requiresAttachment', 'requiresReason',
    'autoApprove', 'carryForwardAllowed', 'oncePerCareer', 'notDeductedFromAnnual',
    'affectsPayroll', 'isActive', 'probationEligible',
  ]
  if (
    !hasExactKeys(value, typeKeys)
    || !uuidPattern.test(value.id)
    || !uuidPattern.test(value.branchId)
    || ['code', 'name', 'color', 'accrualType', 'dayCountType', 'lawReference']
      .some((key) => typeof value[key] !== 'string')
    || !value.code || !value.name || !value.color
    || !dayPattern.test(value.annualEntitlementDays)
    || !['fixed', 'monthly', 'once_per_career', 'none'].includes(value.accrualType)
    || !['calendar', 'working'].includes(value.dayCountType)
    || value.genderRestriction !== null && !['Female', 'Male'].includes(value.genderRestriction)
    || booleans.some((key) => typeof value[key] !== 'boolean')
    || ['minNoticeDays', 'carryForwardMaxDays', 'minServiceMonths', 'sortOrder']
      .some((key) => !Number.isInteger(value[key]) || value[key] < 0)
    || !instantPattern.test(value.createdAt)
    || !instantPattern.test(value.updatedAt)
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

export function parsePublicHoliday(value) {
  if (
    !hasExactKeys(value, holidayKeys)
    || !uuidPattern.test(value.id)
    || !uuidPattern.test(value.branchId)
    || !datePattern.test(value.date)
    || typeof value.name !== 'string'
    || !value.name
    || typeof value.type !== 'string'
    || !value.type
    || !Number.isInteger(value.year)
    || value.year !== Number(value.date.slice(0, 4))
    || !instantPattern.test(value.createdAt)
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

function parsePage(value) {
  if (
    !hasExactKeys(value, ['limit', 'nextCursor', 'hasMore'])
    || !Number.isInteger(value.limit)
    || value.limit < 1
    || value.limit > 100
    || value.nextCursor !== null && typeof value.nextCursor !== 'string'
    || typeof value.hasMore !== 'boolean'
    || value.hasMore !== (value.nextCursor !== null)
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

function parseCollection(response, parser, branchId) {
  if (!Array.isArray(response.data)) throw invalidResponse()
  const data = response.data.map(parser)
  if (data.some((item) => item.branchId !== branchId)) throw invalidResponse()
  return Object.freeze({ data: Object.freeze(data), page: parsePage(response.page) })
}

function branchHeaders(branchId) {
  if (typeof branchId !== 'string' || !uuidPattern.test(branchId)) {
    throw new TypeError('Invalid branch ID')
  }
  return { 'X-Workloop-Branch-ID': branchId }
}

function queryString(options) {
  const parameters = new URLSearchParams()
  for (const [name, value] of Object.entries(options)) {
    if (value === undefined || name === 'signal') continue
    if (!['cursor', 'limit', 'year'].includes(name)) throw new TypeError('Invalid leave query')
    if (name === 'cursor' && (typeof value !== 'string' || !value)) {
      throw new TypeError('Invalid leave query')
    }
    if (name === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid leave query')
    }
    if (name === 'year' && (!Number.isInteger(value) || value < 2000 || value > 2100)) {
      throw new TypeError('Invalid leave query')
    }
    parameters.set(name, String(value))
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

async function readAll(readPage, options) {
  const rows = []
  const ids = new Set()
  const cursors = new Set()
  let cursor
  do {
    const page = await readPage({ ...options, cursor, limit: 100 })
    for (const row of page.data) {
      if (ids.has(row.id)) throw invalidResponse()
      ids.add(row.id)
      rows.push(row)
    }
    cursor = page.page.nextCursor ?? undefined
    if (cursor !== undefined) {
      if (cursors.has(cursor)) throw invalidResponse()
      cursors.add(cursor)
    }
  } while (cursor !== undefined)
  return Object.freeze(rows)
}

export async function readLeaveSettings(authentication, branchId, { signal } = {}) {
  try {
    const response = await authentication.request('/api/v1/leave/settings', {
      access: 'protected', headers: branchHeaders(branchId), signal,
    })
    const settings = parseLeaveSettings(response.data)
    if (settings.branchId !== branchId) throw invalidResponse()
    return settings
  } catch (error) {
    if (error?.code === 'resource_not_found') return null
    throw error
  }
}

export async function readLeaveTypes(authentication, branchId, options = {}) {
  const { signal, ...query } = options
  const response = await authentication.request(`/api/v1/leave/types${queryString(query)}`, {
    access: 'protected', headers: branchHeaders(branchId), signal,
  })
  return parseCollection(response, parseLeaveType, branchId)
}

export function readAllLeaveTypes(authentication, branchId, options = {}) {
  return readAll(
    (page) => readLeaveTypes(authentication, branchId, page),
    options,
  )
}

export async function readPublicHolidays(authentication, branchId, options = {}) {
  const { signal, ...query } = options
  const response = await authentication.request(`/api/v1/leave/holidays${queryString(query)}`, {
    access: 'protected', headers: branchHeaders(branchId), signal,
  })
  return parseCollection(response, parsePublicHoliday, branchId)
}

export function readAllPublicHolidays(authentication, branchId, options = {}) {
  return readAll(
    (page) => readPublicHolidays(authentication, branchId, page),
    options,
  )
}

export async function readLeaveConfiguration(authentication, branchId, { signal } = {}) {
  const [settings, types, holidays] = await Promise.all([
    readLeaveSettings(authentication, branchId, { signal }),
    readAllLeaveTypes(authentication, branchId, { signal }),
    readAllPublicHolidays(authentication, branchId, { signal }),
  ])
  return Object.freeze({ settings, types, holidays })
}

function requireRecord(value, allowed, required) {
  if (
    !isRecord(value)
    || Object.keys(value).some((key) => !allowed.includes(key))
    || required.some((key) => !Object.hasOwn(value, key))
  ) throw new TypeError('Invalid leave configuration mutation')
  return value
}

export async function updateLeaveSettings(authentication, branchId, values, { signal } = {}) {
  const allowed = [
    'expectedUpdatedAt', 'leaveYearType', 'weekendDefinition', 'carryForwardEnabled',
    'carryForwardMaxDays', 'approvalChain', 'ramadanActive', 'ramadanStart', 'ramadanEnd',
  ]
  requireRecord(values, allowed, allowed.slice(1))
  if (Object.hasOwn(values, 'expectedUpdatedAt') && !instantPattern.test(values.expectedUpdatedAt)) {
    throw new TypeError('Invalid leave settings version')
  }
  const response = await authentication.request('/api/v1/leave/settings', {
    access: 'protected', method: 'PUT', headers: branchHeaders(branchId), json: values, signal,
  })
  const settings = parseLeaveSettings(response.data)
  if (settings.branchId !== branchId) throw invalidResponse()
  return settings
}

export async function seedLeaveTypes(authentication, branchId, { signal } = {}) {
  const response = await authentication.request('/api/v1/leave/types/seed', {
    access: 'protected', method: 'POST', headers: branchHeaders(branchId), signal,
  })
  if (!Array.isArray(response.data)) throw invalidResponse()
  const types = response.data.map(parseLeaveType)
  if (types.some((item) => item.branchId !== branchId)) throw invalidResponse()
  return Object.freeze(types)
}

export async function createLeaveType(authentication, branchId, values, { signal } = {}) {
  requireRecord(values, typeMutationKeys, ['code', 'name', 'annualEntitlementDays'])
  const response = await authentication.request('/api/v1/leave/types', {
    access: 'protected', method: 'POST', headers: branchHeaders(branchId), json: values, signal,
  })
  const type = parseLeaveType(response.data)
  if (response.status !== 201 || type.branchId !== branchId) throw invalidResponse()
  return type
}

export async function updateLeaveType(
  authentication, branchId, typeId, values, { signal } = {},
) {
  if (!uuidPattern.test(typeId)) throw new TypeError('Invalid leave type ID')
  requireRecord(values, [...typeMutationKeys, 'expectedUpdatedAt'], ['expectedUpdatedAt'])
  if (!instantPattern.test(values.expectedUpdatedAt) || Object.keys(values).length < 2) {
    throw new TypeError('Invalid leave type mutation')
  }
  const response = await authentication.request(`/api/v1/leave/types/${typeId}`, {
    access: 'protected', method: 'PATCH', headers: branchHeaders(branchId), json: values, signal,
  })
  const type = parseLeaveType(response.data)
  if (type.id !== typeId || type.branchId !== branchId) throw invalidResponse()
  return type
}

function holidaySnapshot(holiday) {
  return { date: holiday.date, name: holiday.name, type: holiday.type }
}

export async function createPublicHoliday(authentication, branchId, values, { signal } = {}) {
  requireRecord(values, ['date', 'name', 'type'], ['date', 'name', 'type'])
  const response = await authentication.request('/api/v1/leave/holidays', {
    access: 'protected', method: 'POST', headers: branchHeaders(branchId), json: values, signal,
  })
  const holiday = parsePublicHoliday(response.data)
  if (response.status !== 201 || holiday.branchId !== branchId) throw invalidResponse()
  return holiday
}

export async function updatePublicHoliday(
  authentication, branchId, holiday, changes, { signal } = {},
) {
  const current = parsePublicHoliday(holiday)
  if (current.branchId !== branchId) throw new TypeError('Invalid holiday branch')
  requireRecord(changes, ['date', 'name', 'type'], [])
  if (Object.keys(changes).length === 0) throw new TypeError('Invalid holiday mutation')
  const response = await authentication.request(`/api/v1/leave/holidays/${current.id}`, {
    access: 'protected',
    method: 'PATCH',
    headers: branchHeaders(branchId),
    json: { expected: holidaySnapshot(current), ...changes },
    signal,
  })
  const updated = parsePublicHoliday(response.data)
  if (updated.id !== current.id || updated.branchId !== branchId) throw invalidResponse()
  return updated
}

export async function deletePublicHoliday(
  authentication, branchId, holiday, { signal } = {},
) {
  const current = parsePublicHoliday(holiday)
  if (current.branchId !== branchId) throw new TypeError('Invalid holiday branch')
  const expected = holidaySnapshot(current)
  const parameters = new URLSearchParams({
    expectedDate: expected.date,
    expectedName: expected.name,
    expectedType: expected.type,
  })
  const response = await authentication.request(
    `/api/v1/leave/holidays/${current.id}?${parameters}`,
    { access: 'protected', method: 'DELETE', headers: branchHeaders(branchId), signal },
  )
  if (response.status !== 204 || response.data !== null) throw invalidResponse()
}

export async function seedPublicHolidays(
  authentication, branchId, year, holidays, { signal } = {},
) {
  if (!Number.isInteger(year) || year < 2000 || year > 2100 || !Array.isArray(holidays)) {
    throw new TypeError('Invalid holiday seed')
  }
  for (const holiday of holidays) {
    requireRecord(holiday, ['date', 'name', 'type'], ['date', 'name', 'type'])
    if (!datePattern.test(holiday.date) || Number(holiday.date.slice(0, 4)) !== year) {
      throw new TypeError('Invalid holiday seed')
    }
  }
  const response = await authentication.request('/api/v1/leave/holidays/seed', {
    access: 'protected',
    method: 'POST',
    headers: branchHeaders(branchId),
    json: { year, holidays },
    signal,
  })
  if (!Array.isArray(response.data)) throw invalidResponse()
  const seeded = response.data.map(parsePublicHoliday)
  if (seeded.some((item) => item.branchId !== branchId)) throw invalidResponse()
  return Object.freeze(seeded)
}
