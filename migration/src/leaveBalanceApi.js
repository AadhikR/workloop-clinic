const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const dayPattern = /^(?:0|[1-9]\d{0,3})\.\d{2}$/
const statuses = new Set([
  'Pending', 'ManagerApproved', 'ManagerRejected', 'Approved', 'Rejected', 'Cancelled',
])

const balanceKeys = [
  'employeeId', 'leaveTypeId', 'leaveYear', 'entitledDays', 'accruedDays', 'usedDays',
  'pendingDays', 'carriedForward', 'remainingDays', 'sickFullPayUsed',
  'sickHalfPayUsed', 'sickUnpaidUsed',
]
const requestKeys = [
  'id', 'branchId', 'employeeId', 'leaveTypeId', 'startDate', 'endDate', 'isHalfDay',
  'halfDayPeriod', 'daysRequested', 'status', 'reason', 'attachment', 'rejectionReason',
  'managerRejectionReason', 'relationship', 'deceasedName', 'dateOfDeath', 'childBirthDate',
  'childName', 'expectedDueDate', 'institutionName', 'examDates', 'substituteEmployeeId',
  'approvalLevelRequired', 'approvalComment', 'warnings', 'submittedAt', 'createdAt',
  'updatedAt',
]

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
  return new Error('Invalid leave balance response')
}

function isDateOrNull(value) {
  return value === null || typeof value === 'string' && datePattern.test(value)
}

export function parseLeaveBalance(value) {
  if (
    !hasExactKeys(value, balanceKeys)
    || !uuidPattern.test(value.employeeId)
    || !uuidPattern.test(value.leaveTypeId)
    || !Number.isInteger(value.leaveYear)
    || balanceKeys.slice(3).some((key) => !dayPattern.test(value[key]))
  ) throw invalidResponse()
  return Object.freeze({ ...value })
}

export function parseLeaveRequest(value) {
  const textFields = [
    'reason', 'rejectionReason', 'managerRejectionReason', 'relationship', 'deceasedName',
    'childName', 'institutionName', 'examDates', 'approvalComment',
  ]
  if (
    !hasExactKeys(value, requestKeys)
    || !uuidPattern.test(value.id)
    || !uuidPattern.test(value.branchId)
    || !uuidPattern.test(value.employeeId)
    || !uuidPattern.test(value.leaveTypeId)
    || !datePattern.test(value.startDate)
    || !datePattern.test(value.endDate)
    || value.endDate < value.startDate
    || typeof value.isHalfDay !== 'boolean'
    || value.isHalfDay && !['AM', 'PM'].includes(value.halfDayPeriod)
    || !value.isHalfDay && value.halfDayPeriod !== null
    || !dayPattern.test(value.daysRequested)
    || !statuses.has(value.status)
    || textFields.some((key) => typeof value[key] !== 'string')
    || value.attachment !== null
    || !isDateOrNull(value.dateOfDeath)
    || !isDateOrNull(value.childBirthDate)
    || !isDateOrNull(value.expectedDueDate)
    || value.substituteEmployeeId !== null && !uuidPattern.test(value.substituteEmployeeId)
    || !Number.isInteger(value.approvalLevelRequired)
    || value.approvalLevelRequired < 1
    || !Array.isArray(value.warnings)
    || value.warnings.some((warning) => typeof warning !== 'string')
    || !instantPattern.test(value.submittedAt)
    || !instantPattern.test(value.createdAt)
    || !instantPattern.test(value.updatedAt)
  ) throw invalidResponse()
  return Object.freeze({ ...value, warnings: Object.freeze([...value.warnings]) })
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

function parseCollection(response, parser) {
  if (!isRecord(response) || !Array.isArray(response.data)) throw invalidResponse()
  return Object.freeze({
    data: Object.freeze(response.data.map(parser)),
    page: parsePage(response.page),
  })
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
    if (!['cursor', 'limit', 'year', 'employeeId', 'leaveTypeId', 'status'].includes(name)) {
      throw new TypeError('Invalid leave balance query')
    }
    if (name === 'cursor' && (typeof value !== 'string' || !value)) {
      throw new TypeError('Invalid leave balance query')
    }
    if (name === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid leave balance query')
    }
    if (name === 'year' && (!Number.isInteger(value) || value < 2000 || value > 2100)) {
      throw new TypeError('Invalid leave balance query')
    }
    if (['employeeId', 'leaveTypeId'].includes(name) && !uuidPattern.test(value)) {
      throw new TypeError('Invalid leave balance query')
    }
    if (name === 'status' && !statuses.has(value)) {
      throw new TypeError('Invalid leave balance query')
    }
    parameters.set(name, String(value))
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

async function readAll(readPage, keyFor, options) {
  const rows = []
  const keys = new Set()
  const cursors = new Set()
  let cursor
  do {
    const page = await readPage({ ...options, cursor, limit: 100 })
    for (const row of page.data) {
      const key = keyFor(row)
      if (keys.has(key)) throw invalidResponse()
      keys.add(key)
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

async function readCollection(authentication, path, parser, options, headers) {
  const { signal, ...query } = options
  const response = await authentication.request(`${path}${queryString(query)}`, {
    access: 'protected', headers, signal,
  })
  return parseCollection(response, parser)
}

export function readEmployeeLeaveBalances(authentication, options = {}) {
  return readCollection(
    authentication, '/api/v1/leave/balances/self', parseLeaveBalance, options, undefined,
  )
}

export function readEmployeeLeaveRequests(authentication, options = {}) {
  return readCollection(
    authentication, '/api/v1/leave/requests/calendar/self', parseLeaveRequest, options, undefined,
  )
}

export function readAdminLeaveBalances(authentication, branchId, options = {}) {
  return readCollection(
    authentication,
    '/api/v1/leave/balances/branch',
    parseLeaveBalance,
    options,
    branchHeaders(branchId),
  )
}

export function readAdminLeaveRequests(authentication, branchId, options = {}) {
  return readCollection(
    authentication,
    '/api/v1/leave/requests/calendar/branch',
    parseLeaveRequest,
    options,
    branchHeaders(branchId),
  )
}

export function readApproverLeaveBalances(authentication, employeeId, options = {}) {
  if (!uuidPattern.test(employeeId)) throw new TypeError('Invalid employee ID')
  return readCollection(
    authentication,
    '/api/v1/leave/balances/approver',
    parseLeaveBalance,
    { ...options, employeeId },
    undefined,
  )
}

export function readAllEmployeeLeaveBalances(authentication, options = {}) {
  return readAll(
    (page) => readEmployeeLeaveBalances(authentication, page),
    (row) => `${row.employeeId}:${row.leaveTypeId}:${row.leaveYear}`,
    options,
  )
}

export function readAllEmployeeLeaveRequests(authentication, options = {}) {
  return readAll(
    (page) => readEmployeeLeaveRequests(authentication, page),
    (row) => row.id,
    options,
  )
}

export function readAllAdminLeaveBalances(authentication, branchId, options = {}) {
  return readAll(
    (page) => readAdminLeaveBalances(authentication, branchId, page),
    (row) => `${row.employeeId}:${row.leaveTypeId}:${row.leaveYear}`,
    options,
  )
}

export function readAllAdminLeaveRequests(authentication, branchId, options = {}) {
  return readAll(
    (page) => readAdminLeaveRequests(authentication, branchId, page),
    (row) => row.id,
    options,
  )
}

async function mutateBalances(authentication, branchId, operation, leaveYear, signal) {
  if (!Number.isInteger(leaveYear) || leaveYear < 2000 || leaveYear > 2100) {
    throw new TypeError('Invalid leave year')
  }
  const response = await authentication.request(`/api/v1/leave/balances/${operation}`, {
    access: 'protected',
    method: 'POST',
    headers: branchHeaders(branchId),
    json: { leaveYear },
    signal,
  })
  if (!isRecord(response) || !Array.isArray(response.data)) throw invalidResponse()
  return Object.freeze(response.data.map(parseLeaveBalance))
}

export function initializeLeaveBalances(authentication, branchId, leaveYear, { signal } = {}) {
  return mutateBalances(authentication, branchId, 'initialize', leaveYear, signal)
}

export function recalculateLeaveBalances(authentication, branchId, leaveYear, { signal } = {}) {
  return mutateBalances(authentication, branchId, 'recalculate', leaveYear, signal)
}
