const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const methods = new Set(['WEB', 'MOBILE', 'MANUAL', 'BIOMETRIC', 'EMPLOYEE_APP'])
const eventTypes = new Set(['CLOCK_IN', 'CLOCK_OUT'])
const outcomes = new Set(['accepted', 'duplicate', 'unknown_badge', 'invalid'])

function record(value) { return value !== null && typeof value === 'object' && !Array.isArray(value) }
function exact(value, keys) { return record(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }
function invalid() { return new Error('Invalid attendance ingestion response') }
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
function parseEvent(value) {
  const keys = ['id', 'employeeId', 'eventType', 'eventTime', 'method', 'notes', 'createdAt']
  if (!exact(value, keys) || !uuid.test(value.id) || !uuid.test(value.employeeId) || !eventTypes.has(value.eventType) || !instant.test(value.eventTime) || !methods.has(value.method) || typeof value.notes !== 'string' || !instant.test(value.createdAt)) throw invalid()
  return Object.freeze({ ...value })
}
function parseMapping(value) {
  const keys = ['id', 'badgeNo', 'employeeId', 'deviceName', 'createdAt']
  if (!exact(value, keys) || !uuid.test(value.id) || typeof value.badgeNo !== 'string' || !value.badgeNo || !uuid.test(value.employeeId) || typeof value.deviceName !== 'string' || !value.deviceName || !instant.test(value.createdAt)) throw invalid()
  return Object.freeze({ ...value })
}
function parseImport(value) {
  if (!exact(value, ['id', 'acceptedCount', 'duplicateCount', 'rejectedCount', 'outcomes']) || !uuid.test(value.id) || ![value.acceptedCount, value.duplicateCount, value.rejectedCount].every(Number.isInteger) || !Array.isArray(value.outcomes)) throw invalid()
  const parsed = value.outcomes.map((row) => {
    if (!exact(row, ['rowNumber', 'outcome', 'reasonCode', 'clockEventId']) || !Number.isInteger(row.rowNumber) || row.rowNumber < 1 || !outcomes.has(row.outcome) || row.reasonCode !== null && typeof row.reasonCode !== 'string' || row.clockEventId !== null && !uuid.test(row.clockEventId)) throw invalid()
    return Object.freeze({ ...row })
  })
  if (value.acceptedCount + value.duplicateCount + value.rejectedCount !== parsed.length) throw invalid()
  return Object.freeze({ ...value, outcomes: Object.freeze(parsed) })
}
function collection(response, parser) {
  if (!Array.isArray(response.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(response.data.map(parser)), page: page(response.page) })
}
function eventQuery(options) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(options)) {
    if (value === undefined || key === 'signal') continue
    if (!['employeeId', 'from', 'to', 'limit', 'cursor'].includes(key) || key === 'employeeId' && !uuid.test(value) || key === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) throw new TypeError('Invalid clock-event query')
    params.set(key, String(value))
  }
  const encoded = params.toString()
  return encoded ? `?${encoded}` : ''
}

export async function readClockEvents(authentication, branchId, options = {}) {
  const { signal, ...query } = options
  return collection(await authentication.request(`/api/v1/clock-events${eventQuery(query)}`, branchOptions(branchId, { signal })), parseEvent)
}
export async function createManualClockEvent(authentication, branchId, values, { idempotencyKey, signal } = {}) {
  const body = Object.fromEntries(['employeeId', 'eventType', 'eventTime', 'note'].map((key) => [key, values[key]]))
  const response = await authentication.request('/api/v1/clock-events/manual', mutationOptions(branchId, idempotencyKey, { method: 'POST', json: body, signal }))
  return parseEvent(response.data)
}
export async function readBiometricMappings(authentication, branchId, { signal } = {}) {
  return collection(await authentication.request('/api/v1/biometric-mappings', branchOptions(branchId, { signal })), parseMapping)
}
export async function replaceBiometricMapping(authentication, branchId, badgeNo, values, { idempotencyKey, signal } = {}) {
  if (typeof badgeNo !== 'string' || !badgeNo.trim()) throw new TypeError('Invalid badge number')
  const response = await authentication.request(`/api/v1/biometric-mappings/${encodeURIComponent(badgeNo.trim())}`, mutationOptions(branchId, idempotencyKey, { method: 'PUT', json: { employeeId: values.employeeId, deviceName: values.deviceName }, signal }))
  return parseMapping(response.data)
}
export async function deleteBiometricMapping(authentication, branchId, badgeNo, { idempotencyKey, signal } = {}) {
  if (typeof badgeNo !== 'string' || !badgeNo.trim()) throw new TypeError('Invalid badge number')
  await authentication.request(`/api/v1/biometric-mappings/${encodeURIComponent(badgeNo.trim())}`, mutationOptions(branchId, idempotencyKey, { method: 'DELETE', signal }))
}
export async function importBiometricCandidates(authentication, branchId, values, { idempotencyKey, signal } = {}) {
  const response = await authentication.request('/api/v1/biometric-imports', mutationOptions(branchId, idempotencyKey, { method: 'POST', json: { candidates: values.candidates, sourceBytes: values.sourceBytes }, signal }))
  return parseImport(response.data)
}
