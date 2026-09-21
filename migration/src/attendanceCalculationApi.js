const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const decimal = /^\d+\.\d{2}$/
const day = /^\d{4}-\d{2}-\d{2}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const digest = /^[0-9a-f]{64}$/
const statuses = new Set(['PRESENT', 'ABSENT', 'ON_LEAVE', 'PUBLIC_HOLIDAY', 'WEEKEND', 'LATE', 'EARLY_DEPARTURE', 'HALF_DAY', 'OVERTIME', 'UNEXPLAINED_ABSENCE', 'PRESENT_REMOTE', 'MISSING_CLOCK_OUT'])
const overtimeTypes = new Set(['STANDARD', 'REST_DAY_NO_SUB', 'REST_DAY_WITH_SUB', 'NIGHT_SHIFT'])
const eventTypes = new Set(['CLOCK_IN', 'CLOCK_OUT'])
const eventMethods = new Set(['MANUAL', 'BIOMETRIC', 'WEB', 'MOBILE', 'EMPLOYEE_APP'])

function invalid() { return new Error('Invalid attendance calculation response') }
function options(branchId, init = {}) {
  if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId }, ...init }
}
function exact(value, keys) { return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === keys.sort().join('|') }
function parseRecord(value) {
  const keys = ['id', 'employeeId', 'date', 'shiftId', 'clockInTime', 'clockOutTime', 'totalHours', 'expectedHours', 'status', 'lateMinutes', 'earlyDepartureMinutes', 'overtimeHours', 'overtimeType', 'overtimeAmount', 'absenceDeduction', 'lateDeduction', 'workedOnRestDay', 'restDaySubstitute', 'missingClockOut', 'isRamadanDay', 'periodClosed', 'evidenceFlags', 'sourceDigest', 'sourceStale', 'calculationVersion', 'updatedAt']
  const decimals = ['totalHours', 'expectedHours', 'overtimeHours', 'overtimeAmount', 'absenceDeduction', 'lateDeduction']
  const instants = ['clockInTime', 'clockOutTime']
  const booleans = ['workedOnRestDay', 'restDaySubstitute', 'missingClockOut', 'isRamadanDay', 'periodClosed', 'sourceStale']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || value.shiftId !== null && !uuid.test(value.shiftId) || !day.test(value.date) || !instants.every((key) => value[key] === null || instant.test(value[key])) || !decimals.every((key) => decimal.test(value[key])) || !statuses.has(value.status) || !Number.isInteger(value.lateMinutes) || value.lateMinutes < 0 || !Number.isInteger(value.earlyDepartureMinutes) || value.earlyDepartureMinutes < 0 || value.overtimeType !== null && !overtimeTypes.has(value.overtimeType) || !booleans.every((key) => typeof value[key] === 'boolean') || !Array.isArray(value.evidenceFlags) || !value.evidenceFlags.every((item) => typeof item === 'string') || !digest.test(value.sourceDigest) || !Number.isInteger(value.calculationVersion) || value.calculationVersion < 1 || !instant.test(value.updatedAt)) throw invalid()
  return Object.freeze({ ...value, evidenceFlags: Object.freeze([...value.evidenceFlags]) })
}
function page(value) { if (!exact(value, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100 || value.nextCursor !== null && typeof value.nextCursor !== 'string' || value.hasMore !== (value.nextCursor !== null)) throw invalid(); return Object.freeze({ ...value }) }

function calculationBody(values) {
  const hasDigest = values.expectedSourceDigest !== undefined && values.expectedSourceDigest !== null
  const hasVersion = values.expectedCalculationVersion !== undefined && values.expectedCalculationVersion !== null
  if (!uuid.test(values.employeeId) || !day.test(values.attendanceDate) || hasDigest !== hasVersion || hasDigest && !digest.test(values.expectedSourceDigest) || hasVersion && (!Number.isInteger(values.expectedCalculationVersion) || values.expectedCalculationVersion < 1)) throw new TypeError('Invalid attendance calculation request')
  return { employeeId: values.employeeId, attendanceDate: values.attendanceDate, expectedSourceDigest: values.expectedSourceDigest ?? null, expectedCalculationVersion: values.expectedCalculationVersion ?? null }
}

export async function readAttendanceRecords(authentication, branchId, query = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) if (value !== undefined && ['employeeId', 'from', 'to', 'limit', 'cursor'].includes(key)) params.set(key, String(value))
  const result = await authentication.request(`/api/v1/attendance-records${params.size ? `?${params}` : ''}`, options(branchId))
  if (!Array.isArray(result.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(result.data.map(parseRecord)), page: page(result.page) })
}
export async function calculateAttendance(authentication, branchId, values, { idempotencyKey } = {}) {
  if (!uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid attendance calculation request')
  const response = await authentication.request('/api/v1/attendance/calculations', options(branchId, { method: 'POST', json: calculationBody(values), headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': idempotencyKey } }))
  return parseRecord(response.data)
}
export async function calculateAttendanceBatch(authentication, branchId, items, { idempotencyKey } = {}) {
  if (!uuid4.test(idempotencyKey ?? '') || !Array.isArray(items) || items.length < 1 || items.length > 100) throw new TypeError('Invalid attendance calculation batch')
  const body = items.map(calculationBody)
  if (new Set(body.map((item) => item.employeeId)).size !== body.length || new Set(body.map((item) => item.attendanceDate)).size !== 1) throw new TypeError('Invalid attendance calculation batch')
  const response = await authentication.request('/api/v1/attendance/calculations/batch', options(branchId, { method: 'POST', json: { items: body }, headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': idempotencyKey } }))
  if (!Array.isArray(response.data)) throw invalid()
  return Object.freeze(response.data.map(parseRecord))
}
export async function readPersonalAttendance(authentication) {
  const result = await authentication.request('/api/v1/attendance/me/today', { access: 'protected' })
  if (!exact(result.data, ['record', 'rawEventFallback', 'rawEvents']) || !['none', 'self_only'].includes(result.data.rawEventFallback) || !Array.isArray(result.data.rawEvents)) throw invalid()
  const rawEvents = result.data.rawEvents.map((item) => {
    if (!exact(item, ['id', 'eventType', 'eventTime', 'method']) || !uuid.test(item.id) || !eventTypes.has(item.eventType) || !instant.test(item.eventTime) || !eventMethods.has(item.method)) throw invalid()
    return Object.freeze({ ...item })
  })
  if (result.data.record !== null && rawEvents.length || result.data.record === null && result.data.rawEventFallback !== 'self_only') throw invalid()
  return Object.freeze({ ...result.data, record: result.data.record === null ? null : parseRecord(result.data.record), rawEvents: Object.freeze(rawEvents) })
}

export async function readPersonalAttendanceHistory(authentication, query = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) if (value !== undefined && ['from', 'to', 'limit', 'cursor'].includes(key)) params.set(key, String(value))
  const result = await authentication.request(`/api/v1/attendance/me${params.size ? `?${params}` : ''}`, { access: 'protected' })
  if (!Array.isArray(result.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(result.data.map(parseRecord)), page: page(result.page) })
}
