const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const roles = new Set(['admin', 'manager', 'employee'])

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function hasExactKeys(value, expected) {
  if (!isRecord(value)) return false
  const keys = Object.keys(value).sort()
  return keys.length === expected.length
    && keys.every((key, index) => key === [...expected].sort()[index])
}

function invalidSampleResponse() {
  return new Error('Invalid sample response')
}

function isUuid(value) {
  return typeof value === 'string' && uuidPattern.test(value)
}

export async function readPublicStatus(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/public/status', {
    access: 'public',
    signal,
  })
  if (!hasExactKeys(data, ['status']) || data.status !== 'ok') {
    throw invalidSampleResponse()
  }
  return Object.freeze({ status: data.status })
}

export async function readCurrentAccount(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/account/me', {
    access: 'protected',
    signal,
  })
  if (
    !hasExactKeys(data, ['appUserId', 'role', 'companyId', 'employeeId', 'branchId'])
    || !isUuid(data.appUserId)
    || !roles.has(data.role)
    || !isUuid(data.companyId)
    || data.employeeId !== null && !isUuid(data.employeeId)
    || data.branchId !== null && !isUuid(data.branchId)
    || data.role === 'admin' && (data.employeeId !== null || data.branchId !== null)
    || data.role !== 'admin' && (data.employeeId === null || data.branchId === null)
  ) {
    throw invalidSampleResponse()
  }
  return Object.freeze({
    appUserId: data.appUserId,
    role: data.role,
    companyId: data.companyId,
    employeeId: data.employeeId,
    branchId: data.branchId,
  })
}
