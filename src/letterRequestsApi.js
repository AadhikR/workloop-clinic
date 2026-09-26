const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const date = /^\d{4}-\d{2}-\d{2}$/
const money = /^(0|[1-9]\d{0,9})\.\d{2}$/

export const letterTypes = Object.freeze([
  'salary_certificate_bank',
  'salary_certificate_embassy',
  'noc',
  'salary_transfer_letter',
  'employment_confirmation',
])

export const letterTypeLabels = Object.freeze({
  salary_certificate_bank: 'Salary certificate for bank',
  salary_certificate_embassy: 'Salary certificate for embassy',
  noc: 'No objection certificate',
  salary_transfer_letter: 'Salary transfer letter',
  employment_confirmation: 'Employment confirmation',
})

const externalLetterTypes = new Set([
  'salary_certificate_bank', 'salary_certificate_embassy', 'noc', 'salary_transfer_letter',
])

function exact(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}

function headers(branchId = null, idempotent = false) {
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
    throw new Error('Invalid letter request response')
  }
  return response.data.map(parser)
}

const requestKeys = [
  'id', 'employeeId', 'employeeName', 'jobTitle', 'department', 'employmentStartDate',
  'branchName', 'requestKind', 'letterType', 'purpose', 'status', 'notes',
  'rejectionReason', 'requestedAt', 'completedAt', 'actionedAt', 'updatedAt',
]

export function parseLetterRequest(value) {
  if (!exact(value, requestKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || value.employmentStartDate !== null && !date.test(value.employmentStartDate)
    || !['letter', 'custom'].includes(value.requestKind)
    || !['pending', 'completed', 'rejected'].includes(value.status)
    || !instant.test(value.requestedAt) || !instant.test(value.updatedAt)
    || value.completedAt !== null && !instant.test(value.completedAt)
    || value.actionedAt !== null && !instant.test(value.actionedAt)) {
    throw new Error('Invalid letter request response')
  }
  return Object.freeze(value)
}

const printKeys = [
  'requestId', 'requestKind', 'letterType', 'purpose', 'employeeName', 'jobTitle',
  'department', 'employmentStartDate', 'branchName', 'basicSalary', 'allowance',
  'requestedAt', 'completedAt',
]

export function parsePrintSource(value) {
  if (!exact(value, printKeys) || !uuid.test(value.requestId)
    || !['letter', 'custom'].includes(value.requestKind)
    || value.employmentStartDate !== null && !date.test(value.employmentStartDate)
    || value.basicSalary !== null && !money.test(value.basicSalary)
    || value.allowance !== null && !money.test(value.allowance)
    || !instant.test(value.requestedAt) || !instant.test(value.completedAt)) {
    throw new Error('Invalid request print source')
  }
  return Object.freeze(value)
}

export function validateSubmission(values) {
  if (values.requestKind === 'custom') {
    const subject = values.subject.trim()
    const details = values.details.trim()
    if (subject.length < 3 || subject.length > 120) return 'Subject must be 3 to 120 characters.'
    if (details.length < 5 || details.length > 2000) return 'Details must be 5 to 2000 characters.'
    return ''
  }
  if (!letterTypes.includes(values.letterType)) return 'Choose a valid letter type.'
  const purpose = values.purpose.trim()
  if (purpose.length > 500) return 'Purpose cannot exceed 500 characters.'
  if (externalLetterTypes.has(values.letterType) && purpose.length < 5) {
    return 'Purpose must contain at least 5 characters for this letter type.'
  }
  return ''
}

export async function readOwnRequests(authentication, filters = {}) {
  return collection(await authentication.request(`/api/v1/requests/self${query(filters)}`, {
    access: 'protected',
  }), parseLetterRequest)
}

export async function submitRequest(authentication, values) {
  const response = await authentication.request('/api/v1/requests/self', {
    access: 'protected', method: 'POST', headers: headers(null, true), json: values,
  })
  return parseLetterRequest(response.data)
}

export async function readRequestQueue(authentication, branchId, filters = {}) {
  return collection(await authentication.request(`/api/v1/requests${query(filters)}`, {
    access: 'protected', headers: headers(branchId),
  }), parseLetterRequest)
}

export async function decideRequest(authentication, branchId, item, command, reason = '') {
  const response = await authentication.request(`/api/v1/requests/${item.id}/${command}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: {
      expectedRequestedAt: item.requestedAt,
      ...(command === 'reject' ? { reason } : {}),
    },
  })
  return parseLetterRequest(response.data)
}

export async function readPrintSource(authentication, branchId, item) {
  const response = await authentication.request(`/api/v1/requests/${item.id}/print-source`, {
    access: 'protected', headers: headers(branchId),
  })
  return parsePrintSource(response.data)
}

export const letterRequestPatterns = Object.freeze({ uuid, instant, date, money })
