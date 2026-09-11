const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4Pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const categories = new Set(['morning', 'afternoon', 'night', 'flexible'])

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
  return new Error('Invalid department response')
}

function parseDepartment(value) {
  if (
    !hasExactKeys(value, [
      'id', 'name', 'parentId', 'headEmployeeId', 'color', 'description', 'sortOrder', 'createdAt',
    ])
    || !uuidPattern.test(value.id)
    || typeof value.name !== 'string'
    || value.parentId !== null && !uuidPattern.test(value.parentId)
    || value.headEmployeeId !== null && !uuidPattern.test(value.headEmployeeId)
    || typeof value.color !== 'string'
    || typeof value.description !== 'string'
    || !Number.isInteger(value.sortOrder)
    || !instantPattern.test(value.createdAt)
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

function parseStaffingRule(value) {
  if (
    !hasExactKeys(value, [
      'id', 'department', 'shiftCategory', 'minStaff', 'effectiveFrom', 'effectiveTo',
    ])
    || !uuidPattern.test(value.id)
    || typeof value.department !== 'string'
    || !categories.has(value.shiftCategory)
    || !Number.isInteger(value.minStaff)
    || value.minStaff < 0
    || value.effectiveFrom !== null && !datePattern.test(value.effectiveFrom)
    || value.effectiveTo !== null && !datePattern.test(value.effectiveTo)
    || value.effectiveFrom !== null && value.effectiveTo !== null
      && value.effectiveTo < value.effectiveFrom
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

function collection(response, parser) {
  if (!Array.isArray(response.data)) throw invalidResponse()
  return Object.freeze({
    data: Object.freeze(response.data.map(parser)),
    page: parsePage(response.page),
  })
}

function queryString(options, allowed) {
  const parameters = new URLSearchParams()
  for (const [key, value] of Object.entries(options)) {
    if (value === undefined || key === 'signal') continue
    if (!allowed.has(key)) throw new TypeError('Invalid department query')
    if (key === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid department query')
    }
    if (['search', 'department'].includes(key) && (
      typeof value !== 'string' || !value.trim() || value.trim().length > (key === 'search' ? 100 : 200)
    )) throw new TypeError('Invalid department query')
    if (['parentId', 'headEmployeeId'].includes(key) && value !== 'null' && !uuidPattern.test(value)) {
      throw new TypeError('Invalid department query')
    }
    if (key === 'shiftCategory' && !categories.has(value)) throw new TypeError('Invalid staffing query')
    if (key === 'effectiveOn' && !datePattern.test(value)) throw new TypeError('Invalid staffing query')
    if (['cursor', 'sort'].includes(key) && (typeof value !== 'string' || !value)) {
      throw new TypeError('Invalid department query')
    }
    parameters.set(key, ['search', 'department'].includes(key) ? value.normalize('NFC').trim() : String(value))
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

function requireBranch(branchId) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
}

function requestOptions(branchId, options = {}) {
  requireBranch(branchId)
  return { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId }, ...options }
}

const departmentQueries = new Set(['limit', 'cursor', 'search', 'parentId', 'headEmployeeId', 'sort'])
const staffingQueries = new Set(['limit', 'cursor', 'department', 'shiftCategory', 'effectiveOn', 'sort'])

export async function readDepartments(authentication, branchId, options = {}) {
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/departments${queryString(query, departmentQueries)}`,
    requestOptions(branchId, { signal }),
  )
  return collection(response, parseDepartment)
}

export function readAllDepartments(authentication, branchId, options = {}) {
  return readAll(
    (page) => readDepartments(authentication, branchId, page),
    options,
  )
}

export async function readStaffingRules(authentication, branchId, options = {}) {
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/department-staffing-rules${queryString(query, staffingQueries)}`,
    requestOptions(branchId, { signal }),
  )
  return collection(response, parseStaffingRule)
}

export function readAllStaffingRules(authentication, branchId, options = {}) {
  return readAll(
    (page) => readStaffingRules(authentication, branchId, page),
    options,
  )
}

function exactMutation(value, allowed, required) {
  if (
    !isRecord(value)
    || Object.keys(value).some((key) => !allowed.includes(key))
    || required.some((key) => !Object.hasOwn(value, key))
  ) throw new TypeError('Invalid department mutation')
  return value
}

const departmentFields = ['name', 'parentId', 'headEmployeeId', 'color', 'description', 'sortOrder']
const staffingFields = ['department', 'shiftCategory', 'minStaff', 'effectiveFrom', 'effectiveTo']

function validateDepartmentMutation(body) {
  if (Object.hasOwn(body, 'name') && (
    typeof body.name !== 'string' || !body.name.trim() || body.name.length > 200
  )) throw new TypeError('Invalid department mutation')
  for (const key of ['parentId', 'headEmployeeId']) {
    if (Object.hasOwn(body, key) && body[key] !== null && !uuidPattern.test(body[key])) {
      throw new TypeError('Invalid department mutation')
    }
  }
  if (Object.hasOwn(body, 'color') && (
    typeof body.color !== 'string' || body.color.length > 100
  )) throw new TypeError('Invalid department mutation')
  if (Object.hasOwn(body, 'description') && (
    typeof body.description !== 'string' || body.description.length > 2000
  )) throw new TypeError('Invalid department mutation')
  if (Object.hasOwn(body, 'sortOrder') && !Number.isInteger(body.sortOrder)) {
    throw new TypeError('Invalid department mutation')
  }
}

function validateStaffingMutation(body) {
  if (Object.hasOwn(body, 'department') && (
    typeof body.department !== 'string' || !body.department.trim() || body.department.length > 200
  )) throw new TypeError('Invalid staffing mutation')
  if (Object.hasOwn(body, 'shiftCategory') && !categories.has(body.shiftCategory)) {
    throw new TypeError('Invalid staffing mutation')
  }
  if (Object.hasOwn(body, 'minStaff') && (
    !Number.isInteger(body.minStaff) || body.minStaff < 0
  )) throw new TypeError('Invalid staffing mutation')
  for (const key of ['effectiveFrom', 'effectiveTo']) {
    if (Object.hasOwn(body, key) && body[key] !== null && !datePattern.test(body[key])) {
      throw new TypeError('Invalid staffing mutation')
    }
  }
  const start = body.effectiveFrom
  const end = body.effectiveTo
  if (start !== undefined && end !== undefined && start !== null && end !== null && end < start) {
    throw new TypeError('Invalid staffing mutation')
  }
}

function validateDepartmentExpected(value) {
  if (!hasExactKeys(value, departmentFields)) throw new TypeError('Invalid department snapshot')
  validateDepartmentMutation(value)
}

function validateStaffingExpected(value) {
  if (!hasExactKeys(value, staffingFields)) throw new TypeError('Invalid staffing snapshot')
  validateStaffingMutation(value)
}

export function departmentSnapshot(value) {
  const parsed = parseDepartment(value)
  return Object.freeze(Object.fromEntries(departmentFields.map((key) => [key, parsed[key]])))
}

export function staffingRuleSnapshot(value) {
  const parsed = parseStaffingRule(value)
  return Object.freeze(Object.fromEntries(staffingFields.map((key) => [key, parsed[key]])))
}

export async function createDepartment(authentication, branchId, values, { signal } = {}) {
  const body = exactMutation(values, departmentFields, ['name'])
  validateDepartmentMutation(body)
  const response = await authentication.request('/api/v1/departments', requestOptions(branchId, {
    method: 'POST', json: body, signal,
  }))
  const data = parseDepartment(response.data)
  if (response.status !== 201 || response.location !== `/api/v1/departments/${data.id}`) {
    throw invalidResponse()
  }
  return data
}

export async function updateDepartment(
  authentication,
  branchId,
  departmentId,
  changes,
  { idempotencyKey, signal } = {},
) {
  if (!uuidPattern.test(departmentId)) throw new TypeError('Invalid department ID')
  const body = exactMutation(changes, [...departmentFields, 'expected'], ['expected'])
  if (Object.keys(body).length === 1) throw new TypeError('Invalid department update')
  validateDepartmentMutation(body)
  validateDepartmentExpected(body.expected)
  const headers = { 'X-Workloop-Branch-ID': branchId }
  if (Object.hasOwn(body, 'name')) {
    if (!uuid4Pattern.test(idempotencyKey)) throw new TypeError('Invalid idempotency key')
    headers['Idempotency-Key'] = idempotencyKey
  }
  const response = await authentication.request(`/api/v1/departments/${departmentId}`, {
    access: 'protected', method: 'PATCH', headers, json: body, signal,
  })
  const data = parseDepartment(response.data)
  if (data.id !== departmentId) throw invalidResponse()
  return Object.freeze({ data, replayed: response.replayed })
}

export async function deleteDepartment(authentication, branchId, value, { signal } = {}) {
  const department = parseDepartment(value)
  const response = await authentication.request(`/api/v1/departments/${department.id}`, requestOptions(branchId, {
    method: 'DELETE', json: { expected: departmentSnapshot(department) }, signal,
  }))
  if (response.status !== 204 || response.data !== null) throw invalidResponse()
}

export async function createStaffingRule(authentication, branchId, values, { signal } = {}) {
  const body = exactMutation(values, staffingFields, staffingFields)
  validateStaffingMutation(body)
  const response = await authentication.request('/api/v1/department-staffing-rules', requestOptions(branchId, {
    method: 'POST', json: body, signal,
  }))
  const data = parseStaffingRule(response.data)
  if (response.status !== 201 || response.location !== `/api/v1/department-staffing-rules/${data.id}`) {
    throw invalidResponse()
  }
  return data
}

export async function updateStaffingRule(authentication, branchId, value, changes, { signal } = {}) {
  const rule = parseStaffingRule(value)
  const body = exactMutation(changes, [...staffingFields, 'expected'], ['expected'])
  if (Object.keys(body).length === 1) throw new TypeError('Invalid staffing update')
  validateStaffingMutation(body)
  validateStaffingExpected(body.expected)
  validateStaffingMutation({ ...body.expected, ...body })
  const { data } = await authentication.request(`/api/v1/department-staffing-rules/${rule.id}`, requestOptions(branchId, {
    method: 'PATCH', json: body, signal,
  }))
  const parsed = parseStaffingRule(data)
  if (parsed.id !== rule.id) throw invalidResponse()
  return parsed
}

export async function deleteStaffingRule(authentication, branchId, value, { signal } = {}) {
  const rule = parseStaffingRule(value)
  const response = await authentication.request(`/api/v1/department-staffing-rules/${rule.id}`, requestOptions(branchId, {
    method: 'DELETE', json: { expected: staffingRuleSnapshot(rule) }, signal,
  }))
  if (response.status !== 204 || response.data !== null) throw invalidResponse()
}
