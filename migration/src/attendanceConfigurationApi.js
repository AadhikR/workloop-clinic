const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const day = /^\d{4}-\d{2}-\d{2}$/
const clock = /^\d{2}:\d{2}:\d{2}$/
const decimal = /^(?:0|[1-9]\d*)\.\d{2}$/
const days = new Set(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
const types = new Set(['fixed', 'flexible', 'split', 'overnight'])
const categories = new Set(['morning', 'afternoon', 'night', 'flexible', 'split'])
const policies = new Set(['none', 'per_minute', 'per_occurrence'])
const code = /^[A-Z0-9](?:[A-Z0-9-]{0,10}[A-Z0-9])?$/
const color = /^#[0-9A-F]{6}$/

function record(value) { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function exact(value, keys) { return record(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }
function invalid() { return new Error('Invalid attendance configuration response') }
function branchOptions(branchId, options = {}) {
  if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId }, ...options }
}
function mutationOptions(branchId, idempotencyKey, options) {
  if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid idempotency key')
  return branchOptions(branchId, { ...options, headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': idempotencyKey } })
}
function page(value) {
  if (!exact(value, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100 || value.nextCursor !== null && typeof value.nextCursor !== 'string' || value.hasMore !== (value.nextCursor !== null)) throw invalid()
  return Object.freeze({ ...value })
}
function decimalValue(value) { return typeof value === 'string' && decimal.test(value) }
function decimalBetween(value, low, high) { return decimalValue(value) && Number(value) >= low && Number(value) <= high }
function integerBetween(value, low, high) { return Number.isInteger(value) && value >= low && value <= high }

function parseSettings(value) {
  const keys = ['id', 'workingDays', 'weekendDays', 'defaultHoursPerDay', 'lateGraceMinutes', 'earlyDepartureGraceMinutes', 'overtimeRequiresApproval', 'maxDailyOvertimeHours', 'lateDeductionPolicy', 'lateDeductionAmount', 'wfhEnabled', 'regularisationMaxDaysPerMonth', 'regularisationWindowDays', 'biometricApiEnabled', 'biometricApiKeyConfigured', 'createdAt', 'updatedAt']
  if (!exact(value, keys) || !uuid.test(value.id) || !Array.isArray(value.workingDays) || !Array.isArray(value.weekendDays) || value.workingDays.length === 0 || value.weekendDays.length === 0 || value.workingDays.length + value.weekendDays.length !== 7 || !value.workingDays.every((item) => days.has(item)) || !value.weekendDays.every((item) => days.has(item)) || new Set([...value.workingDays, ...value.weekendDays]).size !== 7 || !decimalBetween(value.defaultHoursPerDay, 0.25, 24) || !integerBetween(value.lateGraceMinutes, 0, 240) || !integerBetween(value.earlyDepartureGraceMinutes, 0, 240) || typeof value.overtimeRequiresApproval !== 'boolean' || !decimalBetween(value.maxDailyOvertimeHours, 0, 12) || !policies.has(value.lateDeductionPolicy) || !decimalBetween(value.lateDeductionAmount, 0, 9999999999.99) || typeof value.wfhEnabled !== 'boolean' || !integerBetween(value.regularisationMaxDaysPerMonth, 0, 31) || !integerBetween(value.regularisationWindowDays, 0, 365) || typeof value.biometricApiEnabled !== 'boolean' || typeof value.biometricApiKeyConfigured !== 'boolean' || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) throw invalid()
  return Object.freeze({ ...value, workingDays: Object.freeze([...value.workingDays]), weekendDays: Object.freeze([...value.weekendDays]) })
}

function parseShift(value) {
  const keys = ['id', 'name', 'code', 'shiftType', 'shiftCategory', 'startTime', 'endTime', 'splitStartTime', 'splitEndTime', 'breakMinutes', 'expectedHours', 'lateGraceMinutes', 'earlyDepartureGraceMinutes', 'isOvernight', 'minHoursFlexible', 'isActive', 'color', 'minStaff', 'createdAt', 'updatedAt']
  if (!exact(value, keys) || !uuid.test(value.id) || typeof value.name !== 'string' || value.name.length < 1 || value.name.length > 80 || value.name !== value.name.trim() || value.code !== null && (typeof value.code !== 'string' || !code.test(value.code)) || !types.has(value.shiftType) || !categories.has(value.shiftCategory) || ![value.startTime, value.endTime, value.splitStartTime, value.splitEndTime].every((item) => item === null || clock.test(item)) || !integerBetween(value.breakMinutes, 0, 240) || !decimalBetween(value.expectedHours, 0.25, 24) || !integerBetween(value.lateGraceMinutes, 0, 240) || !integerBetween(value.earlyDepartureGraceMinutes, 0, 240) || value.minHoursFlexible !== null && !decimalBetween(value.minHoursFlexible, 0.25, 24) || typeof value.isOvernight !== 'boolean' || typeof value.isActive !== 'boolean' || !color.test(value.color) || !integerBetween(value.minStaff, 0, 999) || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) throw invalid()
  const fixed = value.shiftType === 'fixed' && clock.test(value.startTime) && clock.test(value.endTime) && value.startTime < value.endTime && !value.isOvernight && value.splitStartTime === null && value.splitEndTime === null && value.minHoursFlexible === null && ['morning', 'afternoon', 'night'].includes(value.shiftCategory)
  const overnight = value.shiftType === 'overnight' && clock.test(value.startTime) && clock.test(value.endTime) && value.endTime <= value.startTime && value.isOvernight && value.shiftCategory === 'night' && value.splitStartTime === null && value.splitEndTime === null && value.minHoursFlexible === null
  const split = value.shiftType === 'split' && clock.test(value.startTime) && clock.test(value.endTime) && clock.test(value.splitStartTime) && clock.test(value.splitEndTime) && value.startTime < value.endTime && value.endTime <= value.splitStartTime && value.splitStartTime < value.splitEndTime && !value.isOvernight && value.shiftCategory === 'split' && value.minHoursFlexible === null
  const flexible = value.shiftType === 'flexible' && value.startTime === null && value.endTime === null && value.splitStartTime === null && value.splitEndTime === null && !value.isOvernight && value.breakMinutes === 0 && value.shiftCategory === 'flexible' && decimalValue(value.minHoursFlexible) && Number(value.minHoursFlexible) <= Number(value.expectedHours)
  if (!fixed && !overnight && !split && !flexible) throw invalid()
  return Object.freeze({ ...value })
}

function parseAssignment(value) {
  const keys = ['id', 'employeeId', 'shiftId', 'effectiveFrom', 'effectiveTo', 'createdAt', 'updatedAt']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !uuid.test(value.shiftId) || !day.test(value.effectiveFrom) || value.effectiveTo !== null && !day.test(value.effectiveTo) || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) throw invalid()
  return Object.freeze({ ...value })
}

function collection(response, parser) {
  if (!Array.isArray(response.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(response.data.map(parser)), page: page(response.page) })
}

function query(options, kind) {
  const allowed = kind === 'shift' ? new Set(['limit', 'cursor', 'active', 'shiftType', 'shiftCategory', 'search']) : new Set(['limit', 'cursor', 'employeeId', 'effectiveOn'])
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(options)) {
    if (value === undefined || key === 'signal') continue
    if (!allowed.has(key) || key === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100) || key === 'employeeId' && !uuid.test(value) || key === 'effectiveOn' && !day.test(value) || key === 'shiftType' && !types.has(value) || key === 'shiftCategory' && !categories.has(value) || key === 'active' && typeof value !== 'boolean') throw new TypeError(kind === 'shift' ? 'Invalid shift query' : 'Invalid assignment query')
    params.set(key, String(value))
  }
  if (kind === 'assignment' && !params.has('employeeId')) throw new TypeError('Invalid assignment query')
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

const shiftFields = ['name', 'code', 'shiftType', 'shiftCategory', 'startTime', 'endTime', 'splitStartTime', 'splitEndTime', 'breakMinutes', 'expectedHours', 'lateGraceMinutes', 'earlyDepartureGraceMinutes', 'isOvernight', 'minHoursFlexible', 'color', 'minStaff']

function shiftBody(values) { return Object.fromEntries(shiftFields.map((key) => [key, values[key]])) }

export async function readAttendanceSettings(authentication, branchId, { signal } = {}) {
  return parseSettings((await authentication.request('/api/v1/attendance-settings', branchOptions(branchId, { signal }))).data)
}
export async function updateAttendanceSettings(authentication, branchId, values, { idempotencyKey, signal } = {}) {
  const body = Object.fromEntries(['workingDays', 'weekendDays', 'defaultHoursPerDay', 'lateGraceMinutes', 'earlyDepartureGraceMinutes', 'overtimeRequiresApproval', 'maxDailyOvertimeHours', 'lateDeductionPolicy', 'lateDeductionAmount', 'wfhEnabled', 'regularisationMaxDaysPerMonth', 'regularisationWindowDays', 'biometricApiEnabled'].map((key) => [key, values[key]]))
  body.expectedUpdatedAt = values.updatedAt
  if (Object.hasOwn(values, 'biometricApiKey') && values.biometricApiKey !== '') body.biometricApiKey = values.biometricApiKey
  const response = await authentication.request('/api/v1/attendance-settings', mutationOptions(branchId, idempotencyKey, { method: 'PUT', json: body, signal }))
  return Object.freeze({ data: parseSettings(response.data), replayed: response.replayed })
}
export async function readShifts(authentication, branchId, options = {}) {
  const { signal, ...values } = options
  return collection(await authentication.request(`/api/v1/shifts${query(values, 'shift')}`, branchOptions(branchId, { signal })), parseShift)
}
export async function createShift(authentication, branchId, values, { idempotencyKey, signal } = {}) {
  const response = await authentication.request('/api/v1/shifts', mutationOptions(branchId, idempotencyKey, { method: 'POST', json: shiftBody(values), signal }))
  const data = parseShift(response.data)
  if (response.status !== 201 || response.location !== `/api/v1/shifts/${data.id}`) throw invalid()
  return data
}
export async function updateShift(authentication, branchId, shift, changes, { idempotencyKey, signal } = {}) {
  const body = { expectedUpdatedAt: shift.updatedAt }
  for (const key of shiftFields) if (Object.hasOwn(changes, key)) body[key] = changes[key]
  const response = await authentication.request(`/api/v1/shifts/${shift.id}`, mutationOptions(branchId, idempotencyKey, { method: 'PATCH', json: body, signal }))
  return parseShift(response.data)
}
export async function deactivateShift(authentication, branchId, shift, { idempotencyKey, signal } = {}) {
  const response = await authentication.request(`/api/v1/shifts/${shift.id}/deactivate`, mutationOptions(branchId, idempotencyKey, { method: 'POST', json: { expectedUpdatedAt: shift.updatedAt }, signal }))
  return Object.freeze({ data: parseShift(response.data), replayed: response.replayed })
}
export async function readShiftAssignments(authentication, branchId, options = {}) {
  const { signal, ...values } = options
  return collection(await authentication.request(`/api/v1/shift-assignments${query(values, 'assignment')}`, branchOptions(branchId, { signal })), parseAssignment)
}
export async function assignShift(authentication, branchId, values, { idempotencyKey, signal } = {}) {
  const keys = ['employeeId', 'shiftId', 'effectiveFrom', 'expectedCurrentAssignmentId', 'expectedCurrentAssignmentUpdatedAt']
  const body = Object.fromEntries(keys.map((key) => [key, values[key]]))
  const response = await authentication.request('/api/v1/shift-assignments', mutationOptions(branchId, idempotencyKey, { method: 'POST', json: body, signal }))
  const data = parseAssignment(response.data)
  if (response.status !== 201 || response.location !== `/api/v1/shift-assignments/${data.id}`) throw invalid()
  return data
}
