const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const date = /^\d{4}-\d{2}-\d{2}$/
const money = /^(?:0|[1-9]\d{0,9})\.\d{2}$/

function headers(branchId, idempotent = false) {
  if (branchId !== null && !uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    ...(branchId === null ? {} : { 'X-Workloop-Branch-ID': branchId }),
    ...(idempotent ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}

function collection(response, parser) {
  if (!Array.isArray(response?.data) || !exact(response.page, ['limit', 'nextCursor', 'hasMore'])) {
    throw new Error('Invalid records response')
  }
  return { items: response.data.map(parser), page: response.page }
}

const documentKeys = [
  'id', 'employeeId', 'documentType', 'status', 'rejectionReason', 'fileName',
  'sizeBytes', 'contentType', 'expiryDate', 'notes', 'reviewerName', 'uploadedAt',
  'reviewedAt', 'updatedAt',
]

export function parseEmployeeDocument(value) {
  if (
    !exact(value, documentKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || typeof value.documentType !== 'string'
    || !['pending_verification', 'verified', 'rejected'].includes(value.status)
    || typeof value.fileName !== 'string' || !Number.isInteger(value.sizeBytes)
    || !['application/pdf', 'image/png', 'image/jpeg'].includes(value.contentType)
    || value.expiryDate !== null && !date.test(value.expiryDate)
    || !instant.test(value.uploadedAt) || !instant.test(value.updatedAt)
    || value.reviewedAt !== null && !instant.test(value.reviewedAt)
    || 'documentNumber' in value || 'storagePath' in value || 'sha256' in value
  ) throw new Error('Invalid employee document response')
  return Object.freeze(value)
}

function documentQuery(values = {}) {
  const query = new URLSearchParams()
  for (const [name, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== '') query.set(name, String(value))
  }
  return query.size ? `?${query}` : ''
}

export async function readEmployeeDocuments(authentication, branchId, employeeId, options = {}) {
  if (!uuid.test(employeeId)) throw new TypeError('Invalid employee ID')
  const response = await authentication.request(
    `/api/v1/employee-documents${documentQuery({ employeeId, ...options })}`,
    { access: 'protected', headers: headers(branchId) },
  )
  return collection(response, parseEmployeeDocument)
}

export async function readSelfEmployeeDocuments(authentication, options = {}) {
  return collection(
    await authentication.request(`/api/v1/employee-documents/self${documentQuery(options)}`, { access: 'protected' }),
    parseEmployeeDocument,
  )
}

export async function uploadEmployeeDocument(authentication, branchId, values, file) {
  if (!(file instanceof File) || file.size < 1 || file.size > 10 * 1024 * 1024) {
    throw new TypeError('Invalid employee document file')
  }
  const intent = await authentication.request('/api/v1/employee-documents/submissions', {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: values,
  })
  if (!exact(intent?.data, ['id', 'submissionToken', 'expiresAt']) || !uuid.test(intent.data.id)) {
    throw new Error('Invalid employee document response')
  }
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))]
    .map((value) => value.toString(16).padStart(2, '0')).join('')
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('submissionToken', intent.data.submissionToken)
  form.append('sha256', digest)
  const response = await authentication.request(
    `/api/v1/employee-documents/submissions/${intent.data.id}/file`,
    { access: 'protected', method: 'POST', headers: headers(branchId), form },
  )
  return parseEmployeeDocument(response.data)
}

async function documentDecision(authentication, branchId, document, action, reason = null) {
  const response = await authentication.request(`/api/v1/employee-documents/${document.id}/${action}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { expectedUpdatedAt: document.updatedAt, reason },
  })
  return parseEmployeeDocument(response.data)
}

export const verifyEmployeeDocument = (authentication, branchId, document) => (
  documentDecision(authentication, branchId, document, 'verify')
)
export const rejectEmployeeDocument = (authentication, branchId, document, reason) => (
  documentDecision(authentication, branchId, document, 'reject', reason)
)

export async function downloadEmployeeDocument(authentication, branchId, documentId) {
  const response = await authentication.request(`/api/v1/employee-documents/${documentId}/download`, {
    access: 'protected', method: 'POST', headers: headers(branchId),
  })
  if (!exact(response?.data, ['url', 'expiresAt']) || typeof response.data.url !== 'string') {
    throw new Error('Invalid employee document download')
  }
  return response.data
}

export async function deleteEmployeeDocument(authentication, branchId, document) {
  const response = await authentication.request(`/api/v1/employee-documents/${document.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: document.updatedAt },
  })
  if (!exact(response?.data, ['id', 'cleanupPending']) || response.data.id !== document.id) {
    throw new Error('Invalid employee document cleanup')
  }
  return response.data
}

const policyKeys = [
  'id', 'insurerName', 'policyNumber', 'tierName', 'annualPremium', 'renewalDate',
  'brokerName', 'brokerContact', 'notes', 'createdAt', 'updatedAt',
]
export function parseInsurancePolicy(value) {
  if (!exact(value, policyKeys) || !uuid.test(value.id) || !money.test(value.annualPremium)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid insurance policy response')
  }
  return Object.freeze(value)
}

export async function readInsurancePolicies(authentication, branchId, options = {}) {
  return collection(await authentication.request(`/api/v1/insurance/policies${documentQuery(options)}`, {
    access: 'protected', headers: headers(branchId),
  }), parseInsurancePolicy)
}

export async function saveInsurancePolicy(authentication, branchId, values, current = null) {
  const path = current === null ? '/api/v1/insurance/policies' : `/api/v1/insurance/policies/${current.id}`
  const response = await authentication.request(path, {
    access: 'protected', method: current === null ? 'POST' : 'PATCH', headers: headers(branchId, true),
    json: current === null ? values : { ...values, expectedUpdatedAt: current.updatedAt },
  })
  return parseInsurancePolicy(response.data)
}

export function deleteInsurancePolicy(authentication, branchId, policy) {
  return authentication.request(`/api/v1/insurance/policies/${policy.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: policy.updatedAt },
  })
}

export async function replaceEmployeeCoverage(authentication, branchId, employeeId, values) {
  const response = await authentication.request(`/api/v1/insurance/employees/${employeeId}/coverage`, {
    access: 'protected', method: 'PUT', headers: headers(branchId, true), json: values,
  })
  return parseEmployeeCoverage(response.data)
}

const coverageKeys = [
  'id', 'employeeId', 'policyId', 'memberId', 'cardNumber', 'effectiveDate',
  'expiryDate', 'tierName', 'insurerName', 'createdAt', 'updatedAt',
]

export function parseEmployeeCoverage(value) {
  if (!exact(value, coverageKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || !uuid.test(value.policyId) || typeof value.memberId !== 'string'
    || typeof value.cardNumber !== 'string' || !date.test(value.effectiveDate)
    || value.expiryDate !== null && !date.test(value.expiryDate)
    || typeof value.tierName !== 'string' || typeof value.insurerName !== 'string'
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)) {
    throw new Error('Invalid employee coverage response')
  }
  return Object.freeze(value)
}

export async function readSelfInsurance(authentication) {
  const response = await authentication.request('/api/v1/insurance/self', { access: 'protected' })
  const value = response?.data
  if (!exact(value, ['policyId', 'insurerName', 'tierName', 'effectiveDate', 'expiryDate'])
    || !uuid.test(value.policyId) || !date.test(value.effectiveDate)
    || 'annualPremium' in value || 'brokerName' in value || 'cardNumber' in value) {
    throw new Error('Invalid self insurance response')
  }
  return Object.freeze(value)
}

export async function readInsuranceDependants(authentication, branchId, employeeId, options = {}) {
  const response = await authentication.request(`/api/v1/insurance/employees/${employeeId}/dependants${documentQuery(options)}`, {
    access: 'protected', headers: headers(branchId),
  })
  return collection(response, parseInsuranceDependant)
}

const dependantKeys = [
  'id', 'employeeId', 'name', 'relationship', 'dateOfBirth', 'cardNumber',
  'createdAt', 'updatedAt',
]

export function parseInsuranceDependant(value) {
  if (!exact(value, dependantKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || typeof value.name !== 'string' || typeof value.relationship !== 'string'
    || value.dateOfBirth !== null && !date.test(value.dateOfBirth)
    || typeof value.cardNumber !== 'string' || !instant.test(value.createdAt)
    || !instant.test(value.updatedAt)) throw new Error('Invalid insurance dependant response')
  return Object.freeze(value)
}

export async function createInsuranceDependant(authentication, branchId, employeeId, values) {
  const response = await authentication.request(`/api/v1/insurance/employees/${employeeId}/dependants`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: values,
  })
  return parseInsuranceDependant(response.data)
}

export async function updateInsuranceDependant(authentication, branchId, dependant, values) {
  const response = await authentication.request(`/api/v1/insurance/dependants/${dependant.id}`, {
    access: 'protected', method: 'PATCH', headers: headers(branchId, true),
    json: { ...values, expectedUpdatedAt: dependant.updatedAt },
  })
  return parseInsuranceDependant(response.data)
}

export function deleteInsuranceDependant(authentication, branchId, dependant) {
  return authentication.request(`/api/v1/insurance/dependants/${dependant.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true),
    json: { expectedUpdatedAt: dependant.updatedAt },
  })
}

export async function readEmployeeContracts(authentication, branchId, employeeId, options = {}) {
  if (!uuid.test(employeeId)) throw new TypeError('Invalid employee ID')
  const response = await authentication.request(`/api/v1/employees/${employeeId}/contracts${documentQuery(options)}`, {
    access: 'protected', headers: headers(branchId),
  })
  return collection(response, parseEmployeeContract)
}

const contractKeys = [
  'id', 'employeeId', 'contractType', 'startDate', 'endDate', 'action', 'notes',
  'actorName', 'createdAt',
]

export function parseEmployeeContract(value) {
  if (!exact(value, contractKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || !['Limited', 'Unlimited'].includes(value.contractType)
    || value.startDate !== null && !date.test(value.startDate)
    || value.endDate !== null && !date.test(value.endDate)
    || !['new', 'renewed', 'converted', 'not_renewed'].includes(value.action)
    || typeof value.notes !== 'string'
    || value.actorName !== null && typeof value.actorName !== 'string'
    || !instant.test(value.createdAt)) throw new Error('Invalid employee contract response')
  return Object.freeze(value)
}

export async function recordEmployeeContract(authentication, branchId, employeeId, action, values) {
  if (!['new', 'renew', 'convert', 'not-renewed'].includes(action)) {
    throw new TypeError('Invalid contract action')
  }
  const response = await authentication.request(`/api/v1/employees/${employeeId}/contracts/${action}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: values,
  })
  return parseEmployeeContract(response.data)
}

export const recordsBenefitsPatterns = Object.freeze({ uuid, instant, date, money })
