const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const digest = /^sha256:[0-9a-f]{64}$/
const statuses = ['pending', 'approved', 'rejected', 'cancelled']

function invalid() { return new Error('Invalid shift swap response') }
function nullable(value, predicate) { return value === null || predicate(value) }
function exact(value, keys) { return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }

function parseSwap(value) {
  const keys = ['id', 'requesterEmployeeId', 'requesterEmployeeName', 'targetEmployeeId', 'targetEmployeeName', 'requesterDate', 'targetDate', 'reason', 'status', 'rejectionReason', 'expectedSourceVersion', 'requesterAssignmentId', 'targetAssignmentId', 'requesterAssignmentVersion', 'targetAssignmentVersion', 'approvedPublicationVersionId', 'decidedAt', 'decidedByAppUserId', 'createdAt', 'updatedAt', 'version']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.requesterEmployeeId) || !uuid.test(value.targetEmployeeId) || typeof value.requesterEmployeeName !== 'string' || typeof value.targetEmployeeName !== 'string' || !datePattern.test(value.requesterDate) || !datePattern.test(value.targetDate) || typeof value.reason !== 'string' || value.reason.length < 3 || !statuses.includes(value.status) || typeof value.rejectionReason !== 'string' || !digest.test(value.expectedSourceVersion) || !uuid.test(value.requesterAssignmentId) || !uuid.test(value.targetAssignmentId) || !Number.isInteger(value.requesterAssignmentVersion) || value.requesterAssignmentVersion < 1 || !Number.isInteger(value.targetAssignmentVersion) || value.targetAssignmentVersion < 1 || !nullable(value.approvedPublicationVersionId, (item) => uuid.test(item)) || !nullable(value.decidedAt, (item) => instant.test(item)) || !nullable(value.decidedByAppUserId, (item) => uuid.test(item)) || !instant.test(value.createdAt) || !instant.test(value.updatedAt) || !Number.isInteger(value.version) || value.version < 1) throw invalid()
  const pending = value.status === 'pending'
  if (pending !== (value.decidedAt === null && value.decidedByAppUserId === null)) throw invalid()
  if ((value.status === 'approved') !== (value.approvedPublicationVersionId !== null)) throw invalid()
  if (value.status === 'rejected' && value.rejectionReason.trim().length < 3) throw invalid()
  return Object.freeze({ ...value })
}

function parseCollection(result) {
  if (!Array.isArray(result.data) || !exact(result.page, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(result.page.limit) || result.page.limit < 1 || result.page.limit > 100 || result.page.nextCursor !== null || result.page.hasMore !== false) throw invalid()
  return Object.freeze(result.data.map(parseSwap))
}

function query(status, limit) {
  if (status !== null && !statuses.includes(status)) throw new TypeError('Invalid shift swap query')
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new TypeError('Invalid shift swap query')
  const params = new URLSearchParams({ limit: String(limit) })
  if (status !== null) params.set('status', status)
  return params
}

function mutation(idempotencyKey, json, branchId = null) {
  if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid idempotency key')
  if (branchId !== null && !uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return { access: 'protected', method: 'POST', json, headers: { 'Idempotency-Key': idempotencyKey, ...(branchId === null ? {} : { 'X-Workloop-Branch-ID': branchId }) } }
}

export async function readPersonalShiftSwaps(authentication, { status = null, limit = 100 } = {}) {
  const result = await authentication.request(`/api/v1/roster/shift-swaps/self?${query(status, limit)}`, { access: 'protected' })
  return parseCollection(result)
}

export async function readAdminShiftSwaps(authentication, branchId, { status = null, limit = 100 } = {}) {
  if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  const result = await authentication.request(`/api/v1/roster/shift-swaps?${query(status, limit)}`, { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId } })
  return parseCollection(result)
}

export async function submitShiftSwap(authentication, values, { idempotencyKey } = {}) {
  const reason = String(values.reason ?? '').trim()
  if (!uuid.test(values.targetEmployeeId) || !datePattern.test(values.requesterDate) || !datePattern.test(values.targetDate) || values.requesterDate === values.targetDate || values.requesterDate.slice(0, 7) !== values.targetDate.slice(0, 7) || reason.length < 3 || reason.length > 500 || !digest.test(values.expectedSourceVersion)) throw new TypeError('Invalid shift swap request')
  const body = { requesterDate: values.requesterDate, targetEmployeeId: values.targetEmployeeId, targetDate: values.targetDate, reason, expectedSourceVersion: values.expectedSourceVersion }
  const result = await authentication.request('/api/v1/roster/shift-swaps', mutation(idempotencyKey, body))
  return parseSwap(result.data)
}

export async function cancelShiftSwap(authentication, swap, { idempotencyKey } = {}) {
  if (!uuid.test(swap.id) || !Number.isInteger(swap.version) || swap.version < 1) throw new TypeError('Invalid shift swap request')
  const result = await authentication.request(`/api/v1/roster/shift-swaps/${swap.id}/cancel`, mutation(idempotencyKey, { expectedVersion: swap.version, reason: null }))
  return parseSwap(result.data)
}

export async function rejectShiftSwap(authentication, branchId, swap, reason, { idempotencyKey } = {}) {
  const normalized = String(reason).trim()
  if (!uuid.test(swap.id) || !Number.isInteger(swap.version) || swap.version < 1 || normalized.length < 3 || normalized.length > 500) throw new TypeError('Invalid shift swap rejection')
  const result = await authentication.request(`/api/v1/roster/shift-swaps/${swap.id}/reject`, mutation(idempotencyKey, { expectedVersion: swap.version, reason: normalized }, branchId))
  return parseSwap(result.data)
}

export async function approveShiftSwap(authentication, branchId, swap, { idempotencyKey } = {}) {
  if (!uuid.test(swap.id) || !Number.isInteger(swap.version) || swap.version < 1 || !digest.test(swap.expectedSourceVersion)) throw new TypeError('Invalid shift swap approval')
  const result = await authentication.request(`/api/v1/roster/shift-swaps/${swap.id}/approve`, mutation(idempotencyKey, { expectedVersion: swap.version, expectedSourceVersion: swap.expectedSourceVersion }, branchId))
  return parseSwap(result.data)
}
