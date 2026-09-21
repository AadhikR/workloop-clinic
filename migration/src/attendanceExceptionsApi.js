const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const day = /^\d{4}-\d{2}-\d{2}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const offsetInstant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/
const decimal = /^\d+\.\d{2}$/
const requestStatuses = new Set(['Pending', 'Approved', 'Rejected'])
const resolutionTypes = new Set(['LEAVE_LINKED', 'UNAUTHORISED', 'WFH'])
const auditActions = new Set(['REGULARISATION_APPROVED', 'REGULARISATION_REJECTED', 'ABSENCE_RESOLVED', 'OVERTIME_APPROVED'])

function invalid() { return new Error('Invalid attendance exception response') }
function exact(value, keys) { return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }
function nullable(value, predicate) { return value === null || predicate(value) }
function page(value) { if (!exact(value, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100 || !nullable(value.nextCursor, (item) => typeof item === 'string' && item.length > 0) || value.hasMore !== (value.nextCursor !== null)) throw invalid(); return Object.freeze({ ...value }) }
function branchOptions(branchId, init = {}) { if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID'); return { access: 'protected', ...init, headers: { ...init.headers, 'X-Workloop-Branch-ID': branchId } } }
function mutationOptions(branchId, idempotencyKey, json) { if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid attendance exception request'); return branchOptions(branchId, { method: 'POST', json, headers: { 'Idempotency-Key': idempotencyKey } }) }
function personalMutationOptions(idempotencyKey, json) { if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid attendance exception request'); return { access: 'protected', method: 'POST', json, headers: { 'Idempotency-Key': idempotencyKey } } }
function reason(value, name = 'reason') { const result = typeof value === 'string' ? value.trim() : ''; if (result.length < 3 || result.length > 500) throw new TypeError(`Invalid ${name}`); return result }
function queryString(query, allowed) { const params = new URLSearchParams(); for (const [key, value] of Object.entries(query)) { if (!allowed.includes(key)) throw new TypeError('Invalid attendance exception query'); if (value !== undefined && value !== null && value !== '') params.set(key, String(value)) } return params.size ? `?${params}` : '' }

function parseRegularisation(value) {
  const keys = ['id', 'employeeId', 'attendanceDate', 'correctClockIn', 'correctClockOut', 'reason', 'status', 'rejectionReason', 'submittedAt', 'decidedAt', 'version']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !day.test(value.attendanceDate) || !instant.test(value.correctClockIn) || !instant.test(value.correctClockOut) || typeof value.reason !== 'string' || !requestStatuses.has(value.status) || !nullable(value.rejectionReason, (item) => typeof item === 'string') || !instant.test(value.submittedAt) || !nullable(value.decidedAt, (item) => instant.test(item)) || !Number.isInteger(value.version) || value.version < 1) throw invalid()
  return Object.freeze({ ...value })
}

function parseExceptionRecord(value) {
  const keys = ['id', 'employeeId', 'date', 'status', 'resolutionType', 'absenceDeduction', 'overtimeHours', 'overtimeType', 'overtimeAmount', 'overtimeApproved', 'overtimeApprovedAt', 'overtimeApprovalSourceDigest', 'resolvedAt', 'resolutionSourceDigest', 'calculationVersion']
  const digest = (item) => typeof item === 'string' && item.length >= 1 && item.length <= 128
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !day.test(value.date) || typeof value.status !== 'string' || !nullable(value.resolutionType, (item) => resolutionTypes.has(item)) || !decimal.test(value.absenceDeduction) || !decimal.test(value.overtimeHours) || !nullable(value.overtimeType, (item) => typeof item === 'string') || !decimal.test(value.overtimeAmount) || typeof value.overtimeApproved !== 'boolean' || !nullable(value.overtimeApprovedAt, (item) => instant.test(item)) || !nullable(value.overtimeApprovalSourceDigest, digest) || !nullable(value.resolvedAt, (item) => instant.test(item)) || !nullable(value.resolutionSourceDigest, digest) || !Number.isInteger(value.calculationVersion) || value.calculationVersion < 1) throw invalid()
  return Object.freeze({ ...value })
}

function parseAudit(value) {
  if (!exact(value, ['id', 'employeeId', 'attendanceDate', 'action', 'occurredAt']) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !nullable(value.attendanceDate, (item) => day.test(item)) || !auditActions.has(value.action) || !instant.test(value.occurredAt)) throw invalid()
  return Object.freeze({ ...value })
}

function parseCollection(result, parser) {
  if (!exact(result, ['data', 'page']) || !Array.isArray(result.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(result.data.map(parser)), page: page(result.page) })
}

function regularisationBody(values) {
  if (!day.test(values.attendanceDate ?? '') || !offsetInstant.test(values.correctClockIn ?? '') || !offsetInstant.test(values.correctClockOut ?? '') || Date.parse(values.correctClockOut) <= Date.parse(values.correctClockIn) || Date.parse(values.correctClockOut) - Date.parse(values.correctClockIn) > 86400000) throw new TypeError('Invalid attendance correction')
  return { attendanceDate: values.attendanceDate, correctClockIn: values.correctClockIn, correctClockOut: values.correctClockOut, reason: reason(values.reason) }
}

export async function readPersonalRegularisations(authentication, query = {}) {
  const result = await authentication.request(`/api/v1/attendance/regularisations/me${queryString(query, ['status', 'from', 'to', 'limit', 'cursor'])}`, { access: 'protected' })
  return parseCollection(result, parseRegularisation)
}

export async function submitRegularisation(authentication, values, { idempotencyKey } = {}) {
  const result = await authentication.request('/api/v1/attendance/regularisations', personalMutationOptions(idempotencyKey, regularisationBody(values)))
  return parseRegularisation(result.data)
}

export async function readRegularisationQueue(authentication, branchId, query = {}) {
  const result = await authentication.request(`/api/v1/attendance/regularisations${queryString(query, ['employeeId', 'status', 'from', 'to', 'limit', 'cursor'])}`, branchOptions(branchId))
  return parseCollection(result, parseRegularisation)
}

export async function decideRegularisation(authentication, branchId, requestId, action, expectedVersion, rejectionReason, { idempotencyKey } = {}) {
  if (!uuid.test(requestId) || !['approve', 'reject'].includes(action) || !Number.isInteger(expectedVersion) || expectedVersion < 1) throw new TypeError('Invalid attendance correction decision')
  const body = { expectedVersion, rejectionReason: action === 'reject' ? reason(rejectionReason, 'rejection reason') : null }
  const result = await authentication.request(`/api/v1/attendance/regularisations/${requestId}/${action}`, mutationOptions(branchId, idempotencyKey, body))
  return parseRegularisation(result.data)
}

export async function resolveAbsence(authentication, branchId, recordId, values, { idempotencyKey } = {}) {
  if (!uuid.test(recordId) || !Number.isInteger(values.expectedCalculationVersion) || values.expectedCalculationVersion < 1 || !resolutionTypes.has(values.resolutionType)) throw new TypeError('Invalid absence resolution')
  const result = await authentication.request(`/api/v1/attendance-records/${recordId}/absence-resolution`, mutationOptions(branchId, idempotencyKey, { expectedCalculationVersion: values.expectedCalculationVersion, resolutionType: values.resolutionType, reason: reason(values.reason) }))
  return parseExceptionRecord(result.data)
}

export async function approveOvertime(authentication, branchId, recordId, expectedCalculationVersion, { idempotencyKey } = {}) {
  if (!uuid.test(recordId) || !Number.isInteger(expectedCalculationVersion) || expectedCalculationVersion < 1) throw new TypeError('Invalid overtime approval')
  const result = await authentication.request(`/api/v1/attendance-records/${recordId}/overtime-approval`, mutationOptions(branchId, idempotencyKey, { expectedCalculationVersion }))
  return parseExceptionRecord(result.data)
}

export async function readAttendanceAudit(authentication, branchId, query = {}) {
  const result = await authentication.request(`/api/v1/attendance/audit${queryString(query, ['employeeId', 'action', 'from', 'to', 'limit', 'cursor'])}`, branchOptions(branchId))
  return parseCollection(result, parseAudit)
}
