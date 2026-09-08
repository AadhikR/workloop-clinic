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

function storageProof(data) {
  if (
    !hasExactKeys(data, ['status', 'sizeBytes', 'sha256'])
    || data.status !== 'persisted'
    || !Number.isInteger(data.sizeBytes)
    || data.sizeBytes < 1
    || !/^[0-9a-f]{64}$/.test(data.sha256)
  ) {
    throw invalidSampleResponse()
  }
  return Object.freeze({
    status: data.status,
    sizeBytes: data.sizeBytes,
    sha256: data.sha256,
  })
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

export async function createStorageProof(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/architecture-proof/storage', {
    access: 'protected',
    method: 'POST',
    signal,
  })
  return storageProof(data)
}

export async function readStorageProof(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/architecture-proof/storage', {
    access: 'protected',
    signal,
  })
  return storageProof(data)
}

export async function deleteStorageProof(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/architecture-proof/storage', {
    access: 'protected',
    method: 'DELETE',
    signal,
  })
  if (data !== null) throw invalidSampleResponse()
}
