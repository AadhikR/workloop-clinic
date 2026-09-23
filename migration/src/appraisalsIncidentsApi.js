const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const date = /^\d{4}-\d{2}-\d{2}$/
const rating = /^[1-5]\.\d$/
const weight = /^\d+\.\d{2}$/

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
    throw new Error('Invalid appraisals and incidents response')
  }
  return response.data.map(parser)
}

const sectionKeys = [
  'id', 'sectionName', 'weight', 'rating', 'comments', 'sortOrder', 'updatedAt',
]

export function parseAppraisalSection(value) {
  if (!exact(value, sectionKeys) || !uuid.test(value.id) || !weight.test(value.weight)
    || value.rating !== null && !rating.test(value.rating) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid appraisal section response')
  }
  return Object.freeze(value)
}

const appraisalKeys = [
  'id', 'cycleId', 'cycleName', 'reviewFrom', 'reviewTo', 'employeeId', 'employeeName',
  'templateVersion', 'overallRating', 'status', 'reviewerComments', 'developmentPlan',
  'reviewedAt', 'reviewedByAppUserId', 'createdAt', 'updatedAt', 'sections',
]

export function parseAppraisal(value) {
  if (!exact(value, appraisalKeys) || !uuid.test(value.id) || !uuid.test(value.cycleId)
    || !uuid.test(value.employeeId) || !date.test(value.reviewFrom) || !date.test(value.reviewTo)
    || value.overallRating !== null && !rating.test(value.overallRating)
    || !['pending', 'reviewed', 'calibrated'].includes(value.status)
    || value.reviewedAt !== null && !instant.test(value.reviewedAt)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)
    || !Array.isArray(value.sections)) throw new Error('Invalid appraisal response')
  return Object.freeze({ ...value, sections: value.sections.map(parseAppraisalSection) })
}

const cycleKeys = [
  'id', 'name', 'reviewFrom', 'reviewTo', 'status', 'closedByAppUserId', 'closedAt',
  'createdAt', 'updatedAt', 'appraisals',
]

export function parseAppraisalCycle(value) {
  if (!exact(value, cycleKeys) || !uuid.test(value.id) || !date.test(value.reviewFrom)
    || !date.test(value.reviewTo) || !['draft', 'active', 'closed'].includes(value.status)
    || value.closedAt !== null && !instant.test(value.closedAt) || !instant.test(value.createdAt)
    || !instant.test(value.updatedAt) || !Array.isArray(value.appraisals)) {
    throw new Error('Invalid appraisal cycle response')
  }
  return Object.freeze({ ...value, appraisals: value.appraisals.map(parseAppraisal) })
}

export async function readAppraisalCycles(authentication, branchId) {
  return collection(await authentication.request('/api/v1/appraisal-cycles', {
    access: 'protected', headers: headers(branchId),
  }), parseAppraisalCycle)
}

export async function saveAppraisalCycle(authentication, branchId, values, current = null) {
  const path = current === null ? '/api/v1/appraisal-cycles' : `/api/v1/appraisal-cycles/${current.id}`
  const response = await authentication.request(path, {
    access: 'protected', method: current === null ? 'POST' : 'PATCH', headers: headers(branchId, true),
    json: current === null ? values : { ...values, expectedUpdatedAt: current.updatedAt },
  })
  return parseAppraisalCycle(response.data)
}

export async function appraisalCycleCommand(authentication, branchId, cycle, command) {
  const response = await authentication.request(`/api/v1/appraisal-cycles/${cycle.id}/${command}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { expectedUpdatedAt: cycle.updatedAt },
  })
  if (command === 'generate') return response.data
  return parseAppraisalCycle(response.data)
}

export function deleteAppraisalCycle(authentication, branchId, cycle) {
  return authentication.request(`/api/v1/appraisal-cycles/${cycle.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: cycle.updatedAt },
  })
}

export async function readAppraisals(authentication, role) {
  const scope = role === 'manager' ? 'direct-reports' : 'self'
  return collection(await authentication.request(`/api/v1/appraisals/${scope}`, {
    access: 'protected',
  }), parseAppraisal)
}

export async function rateAppraisalSection(authentication, appraisal, section, values) {
  const response = await authentication.request(`/api/v1/appraisals/${appraisal.id}/sections/${section.id}`, {
    access: 'protected', method: 'PUT', headers: headers(null, true),
    json: { ...values, expectedUpdatedAt: appraisal.updatedAt },
  })
  return parseAppraisal(response.data)
}

export async function reviewAppraisal(authentication, branchId, appraisal, values) {
  const response = await authentication.request(`/api/v1/appraisals/${appraisal.id}/review`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: appraisal.updatedAt },
  })
  return parseAppraisal(response.data)
}

export async function calibrateAppraisal(authentication, branchId, appraisal, finalRating) {
  const response = await authentication.request(`/api/v1/appraisals/${appraisal.id}/calibrate`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { finalRating, expectedUpdatedAt: appraisal.updatedAt },
  })
  return parseAppraisal(response.data)
}

const incidentKeys = [
  'id', 'incidentDate', 'incidentTime', 'location', 'department', 'incidentType', 'severity',
  'description', 'reportedById', 'reportedByName', 'involvedEmpId', 'involvedEmployeeName',
  'immediateAction', 'rootCause', 'correctiveAction', 'status', 'closedDate',
  'closedByAppUserId', 'notes', 'createdAt', 'updatedAt',
]

export function parseIncident(value) {
  if (!exact(value, incidentKeys) || !uuid.test(value.id) || !date.test(value.incidentDate)
    || !['low', 'moderate', 'high', 'critical'].includes(value.severity)
    || !['open', 'investigating', 'closed'].includes(value.status)
    || value.closedDate !== null && !date.test(value.closedDate)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid clinical incident response')
  }
  return Object.freeze(value)
}

export async function readIncidents(authentication, branchId, filters = {}) {
  return collection(await authentication.request(`/api/v1/clinical-incidents${query(filters)}`, {
    access: 'protected', headers: headers(branchId),
  }), parseIncident)
}

export async function saveIncident(authentication, branchId, values, current = null) {
  const path = current === null ? '/api/v1/clinical-incidents' : `/api/v1/clinical-incidents/${current.id}`
  const response = await authentication.request(path, {
    access: 'protected', method: current === null ? 'POST' : 'PATCH', headers: headers(branchId, true),
    json: current === null ? values : { ...values, expectedUpdatedAt: current.updatedAt },
  })
  return parseIncident(response.data)
}

export async function incidentCommand(authentication, branchId, incident, command, values = {}) {
  const response = await authentication.request(`/api/v1/clinical-incidents/${incident.id}/${command}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: incident.updatedAt },
  })
  return parseIncident(response.data)
}

export const appraisalsIncidentsPatterns = Object.freeze({ uuid, instant, date, rating, weight })
