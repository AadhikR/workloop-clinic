const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const periodPattern = /^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const digest = /^sha256:[0-9a-f]{64}$/

function invalid() { return new Error('Invalid roster response') }
function exact(value, keys) { return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }
function nullable(value, predicate) { return value === null || predicate(value) }
function options(branchId, init = {}) { if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID'); return { access: 'protected', ...init, headers: { ...init.headers, 'X-Workloop-Branch-ID': branchId } } }
function page(value) { if (!exact(value, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100 || !nullable(value.nextCursor, (item) => typeof item === 'string' && item.length > 0) || value.hasMore !== (value.nextCursor !== null)) throw invalid(); return Object.freeze({ ...value }) }

function parseAssignment(value) {
  const keys = ['id', 'employeeId', 'employeeName', 'department', 'shiftId', 'shiftName', 'shiftCode', 'shiftCategory', 'date', 'published', 'plannedHours', 'notes', 'version', 'leaveConflict', 'updatedAt']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !uuid.test(value.shiftId) || typeof value.employeeName !== 'string' || typeof value.department !== 'string' || typeof value.shiftName !== 'string' || !nullable(value.shiftCode, (item) => typeof item === 'string') || typeof value.shiftCategory !== 'string' || !datePattern.test(value.date) || typeof value.published !== 'boolean' || !/^\d{1,2}\.\d{2}$/.test(value.plannedHours) || typeof value.notes !== 'string' || !Number.isInteger(value.version) || value.version < 1 || typeof value.leaveConflict !== 'boolean' || !instant.test(value.updatedAt)) throw invalid()
  return Object.freeze({ ...value })
}

function parseValidation(value) {
  if (!exact(value, ['period', 'staffingEnforced', 'leaveConflicts', 'staffingViolations', 'ready']) || !periodPattern.test(value.period) || typeof value.staffingEnforced !== 'boolean' || !Array.isArray(value.leaveConflicts) || !nullable(value.staffingViolations, Array.isArray) || typeof value.ready !== 'boolean') throw invalid()
  const leaveConflicts = value.leaveConflicts.map((item) => {
    if (!exact(item, ['rosterAssignmentId', 'employeeId', 'employeeName', 'date', 'leaveRequestId', 'leaveStatus', 'violationDigest', 'overridden']) || !uuid.test(item.rosterAssignmentId) || !uuid.test(item.employeeId) || !uuid.test(item.leaveRequestId) || typeof item.employeeName !== 'string' || !datePattern.test(item.date) || !['Approved', 'ManagerApproved'].includes(item.leaveStatus) || !digest.test(item.violationDigest) || typeof item.overridden !== 'boolean') throw invalid()
    return Object.freeze({ ...item })
  })
  const staffingViolations = value.staffingViolations?.map((item) => {
    if (!exact(item, ['code', 'department', 'date', 'shiftCategory', 'required', 'assigned', 'deficit', 'ruleId', 'violationDigest', 'overridden']) || item.code !== 'staffing_shortfall' || typeof item.department !== 'string' || !datePattern.test(item.date) || typeof item.shiftCategory !== 'string' || ![item.required, item.assigned, item.deficit].every(Number.isInteger) || item.required < 1 || item.assigned < 0 || item.deficit !== item.required - item.assigned || item.deficit < 1 || !uuid.test(item.ruleId) || !digest.test(item.violationDigest) || typeof item.overridden !== 'boolean') throw invalid()
    return Object.freeze({ ...item })
  }) ?? null
  if (!value.staffingEnforced && staffingViolations !== null) throw invalid()
  const expectedReady = leaveConflicts.every((item) => item.overridden) && (staffingViolations === null || staffingViolations.every((item) => item.overridden))
  if (value.ready !== expectedReady) throw invalid()
  return Object.freeze({ ...value, leaveConflicts: Object.freeze(leaveConflicts), staffingViolations: staffingViolations === null ? null : Object.freeze(staffingViolations) })
}

function parseOverride(value) {
  const keys = ['id', 'period', 'ruleCode', 'violationDigest', 'violationSnapshot', 'reason', 'createdAt']
  const snapshot = value?.violationSnapshot
  if (!exact(value, keys) || !uuid.test(value.id) || !periodPattern.test(value.period) || !['leave_conflict', 'staffing_shortfall'].includes(value.ruleCode) || !digest.test(value.violationDigest) || !snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot) || snapshot.code !== value.ruleCode || snapshot.period !== value.period || !uuid.test(snapshot.branchId) || typeof value.reason !== 'string' || value.reason.length < 10 || value.reason.length > 500 || !instant.test(value.createdAt)) throw invalid()
  if (value.ruleCode === 'staffing_shortfall') {
    const snapshotKeys = ['code', 'period', 'branchId', 'ruleId', 'department', 'date', 'shiftCategory', 'required', 'assigned', 'deficit']
    if (!exact(snapshot, snapshotKeys) || !uuid.test(snapshot.ruleId) || typeof snapshot.department !== 'string' || !datePattern.test(snapshot.date) || typeof snapshot.shiftCategory !== 'string' || ![snapshot.required, snapshot.assigned, snapshot.deficit].every(Number.isInteger) || snapshot.required < 1 || snapshot.assigned < 0 || snapshot.deficit !== snapshot.required - snapshot.assigned || snapshot.deficit < 1) throw invalid()
  } else {
    const snapshotKeys = ['code', 'period', 'branchId', 'rosterAssignmentId', 'employeeId', 'date', 'leaveRequestId', 'leaveStatus']
    if (!exact(snapshot, snapshotKeys) || !uuid.test(snapshot.rosterAssignmentId) || !uuid.test(snapshot.employeeId) || !datePattern.test(snapshot.date) || !uuid.test(snapshot.leaveRequestId) || !['Approved', 'ManagerApproved'].includes(snapshot.leaveStatus)) throw invalid()
  }
  return Object.freeze({ ...value, violationSnapshot: Object.freeze({ ...value.violationSnapshot }) })
}

function body(values, includeVersion = false) {
  const result = {
    employeeId: values.employeeId,
    shiftId: values.shiftId,
    date: values.date,
    plannedHours: String(values.plannedHours),
    notes: String(values.notes ?? '').trim(),
  }
  const hours = Number(result.plannedHours)
  if (!uuid.test(result.employeeId) || !uuid.test(result.shiftId) || !datePattern.test(result.date) || !/^\d{1,2}(?:\.\d{1,2})?$/.test(result.plannedHours) || !Number.isFinite(hours) || hours < 0.25 || hours > 24 || result.notes.length > 500) throw new TypeError('Invalid roster draft')
  if (includeVersion) {
    if (!Number.isInteger(values.expectedVersion) || values.expectedVersion < 1) throw new TypeError('Invalid roster draft version')
    result.expectedVersion = values.expectedVersion
  }
  return result
}

function mutationOptions(branchId, idempotencyKey, values, method) {
  if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid idempotency key')
  return options(branchId, { method, json: values, headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': idempotencyKey } })
}

export async function readRosterMonth(authentication, branchId, period, query = {}) {
  if (!periodPattern.test(period)) throw new TypeError('Invalid roster period')
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (!['department', 'employeeId', 'limit', 'cursor'].includes(key)) throw new TypeError('Invalid roster query')
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  if (params.has('employeeId') && !uuid.test(params.get('employeeId'))) throw new TypeError('Invalid roster query')
  if (params.has('limit') && (!/^\d+$/.test(params.get('limit')) || Number(params.get('limit')) < 1 || Number(params.get('limit')) > 100)) throw new TypeError('Invalid roster query')
  const result = await authentication.request(`/api/v1/roster/months/${period}${params.size ? `?${params}` : ''}`, options(branchId))
  if (!exact(result, ['data', 'page']) || !Array.isArray(result.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(result.data.map(parseAssignment)), page: page(result.page) })
}

export async function readRosterValidation(authentication, branchId, period) {
  if (!periodPattern.test(period)) throw new TypeError('Invalid roster period')
  const result = await authentication.request(`/api/v1/roster/months/${period}/validation`, options(branchId))
  if (!exact(result, ['data'])) throw invalid()
  return parseValidation(result.data)
}

export async function createRosterDraft(authentication, branchId, period, values, { idempotencyKey } = {}) {
  if (!periodPattern.test(period)) throw new TypeError('Invalid roster period')
  const result = await authentication.request(`/api/v1/roster/months/${period}/drafts`, mutationOptions(branchId, idempotencyKey, body(values), 'POST'))
  if (!exact(result, ['data'])) throw invalid()
  return parseAssignment(result.data)
}

export async function replaceRosterDraft(authentication, branchId, period, assignmentId, values, { idempotencyKey } = {}) {
  if (!periodPattern.test(period) || !uuid.test(assignmentId)) throw new TypeError('Invalid roster draft')
  const result = await authentication.request(`/api/v1/roster/months/${period}/drafts/${assignmentId}`, mutationOptions(branchId, idempotencyKey, body(values, true), 'PUT'))
  if (!exact(result, ['data'])) throw invalid()
  return parseAssignment(result.data)
}

export async function deleteRosterDraft(authentication, branchId, period, assignment, { idempotencyKey } = {}) {
  if (!periodPattern.test(period) || !uuid.test(assignment.id) || !Number.isInteger(assignment.version)) throw new TypeError('Invalid roster draft')
  return authentication.request(`/api/v1/roster/months/${period}/drafts/${assignment.id}`, mutationOptions(branchId, idempotencyKey, { expectedVersion: assignment.version }, 'DELETE'))
}

export async function createRosterOverride(authentication, branchId, period, violationDigest, reason, { idempotencyKey } = {}) {
  const normalized = String(reason).trim()
  if (!periodPattern.test(period) || !digest.test(violationDigest) || normalized.length < 10 || normalized.length > 500) throw new TypeError('Invalid roster override')
  const result = await authentication.request(`/api/v1/roster/months/${period}/overrides`, mutationOptions(branchId, idempotencyKey, { violationDigest, reason: normalized }, 'POST'))
  if (!exact(result, ['data'])) throw invalid()
  return parseOverride(result.data)
}
