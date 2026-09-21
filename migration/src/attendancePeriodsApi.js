const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const periodPattern = /^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const sourceVersion = /^sha256:[0-9a-f]{64}$/
const statuses = new Set(['open', 'closed'])
const blockerCodes = new Set(['ambiguous_events', 'missing_calculation_days', 'missing_clock_outs', 'pending_corrections', 'salary_source_changed', 'stale_source_snapshots', 'unapproved_overtime', 'unresolved_absences'])

function invalid() { return new Error('Invalid attendance period response') }
function exact(value, keys) { return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).sort().join('|') === [...keys].sort().join('|') }
function nullable(value, predicate) { return value === null || predicate(value) }
function options(branchId, init = {}) { if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID'); return { access: 'protected', ...init, headers: { ...init.headers, 'X-Workloop-Branch-ID': branchId } } }
function page(value) { if (!exact(value, ['limit', 'nextCursor', 'hasMore']) || !Number.isInteger(value.limit) || value.limit < 1 || value.limit > 100 || !nullable(value.nextCursor, (item) => typeof item === 'string' && item.length > 0) || value.hasMore !== (value.nextCursor !== null)) throw invalid(); return Object.freeze({ ...value }) }

function parsePeriod(value) {
  const keys = ['id', 'period', 'status', 'payrollReady', 'version', 'blockerCount', 'blockers', 'sourceVersion', 'closedAt', 'closedByActorName', 'amendmentReason']
  if (!exact(value, keys) || !uuid.test(value.id) || !periodPattern.test(value.period) || !statuses.has(value.status) || typeof value.payrollReady !== 'boolean' || !Number.isInteger(value.version) || value.version < 0 || !Number.isInteger(value.blockerCount) || value.blockerCount < 0 || !Array.isArray(value.blockers) || !nullable(value.sourceVersion, (item) => sourceVersion.test(item)) || !nullable(value.closedAt, (item) => instant.test(item)) || !nullable(value.closedByActorName, (item) => typeof item === 'string' && item.length > 0) || !nullable(value.amendmentReason, (item) => typeof item === 'string' && item.length >= 3)) throw invalid()
  const blockers = value.blockers.map((item) => {
    if (!exact(item, ['code', 'count']) || !blockerCodes.has(item.code) || !Number.isInteger(item.count) || item.count < 1) throw invalid()
    return Object.freeze({ ...item })
  })
  if (blockers.reduce((total, item) => total + item.count, 0) !== value.blockerCount || value.payrollReady !== (value.status === 'closed' && value.version > 0 && value.sourceVersion !== null)) throw invalid()
  return Object.freeze({ ...value, blockers: Object.freeze(blockers) })
}

export async function readAttendancePeriods(authentication, branchId, query = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (!['limit', 'cursor'].includes(key)) throw new TypeError('Invalid attendance period query')
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const result = await authentication.request(`/api/v1/attendance/periods${params.size ? `?${params}` : ''}`, options(branchId))
  if (!exact(result, ['data', 'page']) || !Array.isArray(result.data)) throw invalid()
  return Object.freeze({ data: Object.freeze(result.data.map(parsePeriod)), page: page(result.page) })
}

export async function readAttendancePeriod(authentication, branchId, period) {
  if (!periodPattern.test(period)) throw new TypeError('Invalid attendance period')
  const result = await authentication.request(`/api/v1/attendance/periods/${period}`, options(branchId))
  if (!exact(result, ['data'])) throw invalid()
  return parsePeriod(result.data)
}

export async function closeAttendancePeriod(authentication, branchId, period, values = {}, { idempotencyKey } = {}) {
  if (!periodPattern.test(period) || !uuid4.test(idempotencyKey ?? '')) throw new TypeError('Invalid attendance period close')
  const expectedVersion = values.expectedVersion ?? 0
  const amendmentReason = values.amendmentReason === undefined || values.amendmentReason === null ? null : String(values.amendmentReason).trim()
  if (!Number.isInteger(expectedVersion) || expectedVersion < 0 || expectedVersion === 0 && amendmentReason !== null || expectedVersion > 0 && (amendmentReason === null || amendmentReason.length < 3 || amendmentReason.length > 500)) throw new TypeError('Invalid attendance period close')
  const result = await authentication.request(`/api/v1/attendance/periods/${period}/close`, options(branchId, { method: 'POST', json: { expectedVersion, amendmentReason }, headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': idempotencyKey } }))
  if (!exact(result, ['data'])) throw invalid()
  return parsePeriod(result.data)
}
