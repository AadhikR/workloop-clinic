const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const date = /^\d{4}-\d{2}-\d{2}$/
const money = /^(?:0|[1-9]\d{0,9})\.\d{2}$/
const hours = /^(?:0|[1-9]\d{0,3})\.\d{2}$/
const cmeHours = /^(?:0|[1-9]\d{0,3})\.\d$/

function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}

function headers(branchId, idempotent = false) {
  if (branchId !== null && !uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    ...(branchId === null ? {} : { 'X-Workloop-Branch-ID': branchId }),
    ...(idempotent ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

function query(values = {}) {
  const result = new URLSearchParams()
  for (const [name, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== '') result.set(name, String(value))
  }
  return result.size ? `?${result}` : ''
}

function collection(response, parser) {
  if (!Array.isArray(response?.data) || !exact(response.page, ['limit', 'nextCursor', 'hasMore'])) {
    throw new Error('Invalid development response')
  }
  return { items: response.data.map(parser), page: response.page }
}

const assetKeys = [
  'id', 'name', 'assetCode', 'category', 'brand', 'model', 'serialNumber',
  'purchaseDate', 'purchaseCost', 'status', 'notes', 'createdAt', 'updatedAt',
]

export function parseAsset(value) {
  if (!exact(value, assetKeys) || !uuid.test(value.id) || typeof value.name !== 'string'
    || typeof value.assetCode !== 'string' || value.assetCode !== value.assetCode.toUpperCase()
    || value.purchaseDate !== null && !date.test(value.purchaseDate)
    || value.purchaseCost !== null && !money.test(value.purchaseCost)
    || !['available', 'assigned', 'under_repair', 'retired', 'lost'].includes(value.status)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid asset response')
  }
  return Object.freeze(value)
}

const assignmentKeys = [
  'id', 'assetId', 'employeeId', 'assetName', 'assetCode', 'status', 'assignedDate',
  'returnDate', 'conditionAtHandover', 'conditionAtReturn', 'notes', 'createdAt',
]

export function parseAssetAssignment(value) {
  if (!exact(value, assignmentKeys) || !uuid.test(value.id) || !uuid.test(value.assetId)
    || !uuid.test(value.employeeId) || !date.test(value.assignedDate)
    || value.returnDate !== null && !date.test(value.returnDate) || !instant.test(value.createdAt)) {
    throw new Error('Invalid asset assignment response')
  }
  return Object.freeze(value)
}

export async function readAssets(authentication, branchId, options = {}) {
  return collection(await authentication.request(`/api/v1/assets${query(options)}`, {
    access: 'protected', headers: headers(branchId),
  }), parseAsset)
}

export async function readSelfAssets(authentication) {
  return collection(await authentication.request('/api/v1/assets/self', { access: 'protected' }), parseAssetAssignment)
}

export async function saveAsset(authentication, branchId, values, current = null) {
  const response = await authentication.request(current === null ? '/api/v1/assets' : `/api/v1/assets/${current.id}`, {
    access: 'protected', method: current === null ? 'POST' : 'PATCH', headers: headers(branchId, true),
    json: current === null ? values : { ...values, expectedUpdatedAt: current.updatedAt },
  })
  return parseAsset(response.data)
}

export async function changeAssetStatus(authentication, branchId, asset, status) {
  const response = await authentication.request(`/api/v1/assets/${asset.id}/status`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { status, expectedUpdatedAt: asset.updatedAt },
  })
  return parseAsset(response.data)
}

export async function assignAsset(authentication, branchId, asset, values) {
  return parseAssetAssignment((await authentication.request(`/api/v1/assets/${asset.id}/assign`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: asset.updatedAt },
  })).data)
}

export async function returnAsset(authentication, branchId, asset, values) {
  return parseAssetAssignment((await authentication.request(`/api/v1/assets/${asset.id}/return`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: asset.updatedAt },
  })).data)
}

export function deleteAsset(authentication, branchId, asset) {
  return authentication.request(`/api/v1/assets/${asset.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: asset.updatedAt },
  })
}

const trainingKeys = [
  'id', 'employeeId', 'trainingTitle', 'trainingType', 'provider', 'startDate', 'endDate',
  'durationHours', 'cost', 'status', 'score', 'passed', 'notes', 'isCme', 'hasEvidence',
  'fileName', 'contentType', 'createdAt', 'updatedAt',
]

export function parseTraining(value) {
  if (!exact(value, trainingKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || typeof value.trainingTitle !== 'string' || value.startDate !== null && !date.test(value.startDate)
    || value.endDate !== null && !date.test(value.endDate)
    || value.durationHours !== null && !hours.test(value.durationHours) || !money.test(value.cost)
    || !['planned', 'in_progress', 'completed', 'cancelled'].includes(value.status)
    || typeof value.hasEvidence !== 'boolean' || !instant.test(value.createdAt)
    || !instant.test(value.updatedAt) || 'sizeBytes' in value) {
    throw new Error('Invalid training response')
  }
  return Object.freeze(value)
}

const certificationKeys = [
  'id', 'employeeId', 'certificationName', 'issuingBody', 'certificateNo', 'issuedDate',
  'expiryDate', 'notes', 'status', 'hasEvidence', 'fileName', 'contentType', 'reviewedAt',
  'createdAt', 'updatedAt',
]

export function parseCertification(value) {
  if (!exact(value, certificationKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || value.issuedDate !== null && !date.test(value.issuedDate)
    || value.expiryDate !== null && !date.test(value.expiryDate)
    || !['pending_review', 'verified', 'rejected'].includes(value.status)
    || typeof value.hasEvidence !== 'boolean' || value.reviewedAt !== null && !instant.test(value.reviewedAt)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt) || 'sizeBytes' in value) {
    throw new Error('Invalid certification response')
  }
  return Object.freeze(value)
}

function scopedPath(resource, role, employeeId = null) {
  if (role === 'admin') return `/api/v1/${resource}${query({ employeeId })}`
  if (role === 'manager' && employeeId) return `/api/v1/${resource}/direct-reports${query({ employeeId })}`
  return `/api/v1/${resource}/self`
}

export async function readTraining(authentication, branchId, role, employeeId = null) {
  return collection(await authentication.request(scopedPath('training-records', role, employeeId), {
    access: 'protected', headers: headers(role === 'admin' ? branchId : null),
  }), parseTraining)
}

export async function createTraining(authentication, branchId, role, employeeId, values) {
  const path = role === 'admin' ? '/api/v1/training-records'
    : role === 'manager' && employeeId ? '/api/v1/training-records/direct-reports'
      : '/api/v1/training-records/self'
  const staffValues = {
    trainingTitle: values.trainingTitle,
    trainingType: values.trainingType,
    provider: values.provider,
    startDate: values.startDate,
    endDate: values.endDate,
    durationHours: values.durationHours,
    notes: values.notes,
  }
  const response = await authentication.request(path, {
    access: 'protected', method: 'POST', headers: headers(role === 'admin' ? branchId : null, true),
    json: role === 'admin' ? { ...values, employeeId }
      : role === 'manager' && employeeId ? { ...staffValues, employeeId } : staffValues,
  })
  return parseTraining(response.data)
}

export async function updateTraining(authentication, branchId, role, record, values) {
  const response = await authentication.request(`/api/v1/training-records/${record.id}`, {
    access: 'protected', method: 'PATCH', headers: headers(role === 'admin' ? branchId : null, true),
    json: { ...values, expectedUpdatedAt: record.updatedAt },
  })
  return parseTraining(response.data)
}

export async function completeTraining(authentication, branchId, record, values) {
  return parseTraining((await authentication.request(`/api/v1/training-records/${record.id}/complete`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: record.updatedAt },
  })).data)
}

export function deleteTraining(authentication, branchId, record) {
  return authentication.request(`/api/v1/training-records/${record.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: record.updatedAt },
  })
}

export async function readCertifications(authentication, branchId, role, employeeId = null) {
  return collection(await authentication.request(scopedPath('certifications', role, employeeId), {
    access: 'protected', headers: headers(role === 'admin' ? branchId : null),
  }), parseCertification)
}

export async function createCertification(authentication, branchId, role, employeeId, values) {
  const path = role === 'admin' ? '/api/v1/certifications'
    : role === 'manager' && employeeId ? '/api/v1/certifications/direct-reports'
      : '/api/v1/certifications/self'
  const response = await authentication.request(path, {
    access: 'protected', method: 'POST', headers: headers(role === 'admin' ? branchId : null, true),
    json: role === 'admin' || role === 'manager' && employeeId ? { ...values, employeeId } : values,
  })
  return parseCertification(response.data)
}

export async function decideCertification(authentication, branchId, certification, action, reason = null) {
  const response = await authentication.request(`/api/v1/certifications/${certification.id}/${action}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { expectedUpdatedAt: certification.updatedAt, reason },
  })
  return parseCertification(response.data)
}

export function deleteCertification(authentication, branchId, certification) {
  return authentication.request(`/api/v1/certifications/${certification.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: certification.updatedAt },
  })
}

export async function uploadEvidence(authentication, branchId, kind, item, file) {
  if (!(file instanceof File) || file.size < 1 || file.size > 10 * 1024 * 1024) {
    throw new TypeError('Invalid evidence file')
  }
  const form = new FormData()
  form.append('file', file, file.name)
  const resource = kind === 'training' ? 'training-files' : 'certification-files'
  const response = await authentication.request(`/api/v1/${resource}/${item.id}`, {
    access: 'protected', method: 'POST', headers: headers(branchId), form,
  })
  return kind === 'training' ? parseTraining(response.data) : parseCertification(response.data)
}

export async function downloadEvidence(authentication, branchId, kind, item) {
  const resource = kind === 'training' ? 'training-files' : 'certification-files'
  const response = await authentication.request(`/api/v1/${resource}/${item.id}/download`, {
    access: 'protected', method: 'POST', headers: headers(branchId),
  })
  if (!exact(response?.data, ['url', 'expiresAt']) || typeof response.data.url !== 'string'
    || !instant.test(response.data.expiresAt)) throw new Error('Invalid evidence download')
  return response.data
}

export function deleteEvidence(authentication, branchId, kind, item) {
  const resource = kind === 'training' ? 'training-files' : 'certification-files'
  return authentication.request(`/api/v1/${resource}/${item.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: item.updatedAt },
  })
}

export async function readSelfCme(authentication, year) {
  const value = (await authentication.request(`/api/v1/cme/self?year=${year}`, { access: 'protected' })).data
  if (!exact(value, ['year', 'targetHours', 'achievedHours', 'gapHours'])
    || value.year !== year || !cmeHours.test(value.targetHours)
    || !cmeHours.test(value.achievedHours) || !cmeHours.test(value.gapHours)) {
    throw new Error('Invalid CME response')
  }
  return Object.freeze(value)
}

function parseCmeRequirement(value) {
  if (!exact(value, ['id', 'employeeId', 'year', 'requiredHours', 'notes', 'createdAt', 'updatedAt'])
    || !uuid.test(value.id) || !uuid.test(value.employeeId) || !cmeHours.test(value.requiredHours)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid CME requirement response')
  }
  return Object.freeze(value)
}

export async function readCmeRequirement(authentication, branchId, employeeId, year) {
  const response = await authentication.request(`/api/v1/cme/requirements/${employeeId}/${year}`, {
    access: 'protected', headers: headers(branchId),
  })
  return parseCmeRequirement(response.data)
}

export async function saveCmeRequirement(authentication, branchId, employeeId, year, values, current = null) {
  const response = await authentication.request(`/api/v1/cme/requirements/${employeeId}/${year}`, {
    access: 'protected', method: 'PUT', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: current?.updatedAt ?? null },
  })
  return parseCmeRequirement(response.data)
}

export function deleteCmeRequirement(authentication, branchId, employeeId, year, current) {
  return authentication.request(`/api/v1/cme/requirements/${employeeId}/${year}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: current.updatedAt },
  })
}

export const developmentAssetsPatterns = Object.freeze({ uuid, instant, date, money, hours, cmeHours })
