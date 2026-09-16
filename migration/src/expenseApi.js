const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const moneyPattern = /^(?:0|[1-9]\d{0,9})\.\d{2}$/
const statuses = new Set([
  'pending', 'manager_approved', 'manager_rejected', 'approved', 'paid', 'rejected',
])

const selfKeys = [
  'id', 'category', 'amount', 'expenseDate', 'description', 'status', 'rejectionReason',
  'hasReceipt', 'payrollPeriod', 'createdAt', 'updatedAt',
]
const queueKeys = [
  ...selfKeys, 'employeeId', 'employeeName', 'managerDecisionAt', 'adminDecisionAt',
  'canDecide', 'managerActorName', 'adminActorName',
]

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function optionalTimestamp(value) {
  return value === null || typeof value === 'string' && timestampPattern.test(value)
}

export function parseExpense(value, queue = false) {
  const expected = queue ? queueKeys : selfKeys
  if (
    !exactKeys(value, expected)
    || !uuidPattern.test(value.id)
    || typeof value.category !== 'string' || value.category.length < 1
    || !moneyPattern.test(value.amount)
    || !datePattern.test(value.expenseDate)
    || typeof value.description !== 'string'
    || !statuses.has(value.status)
    || value.rejectionReason !== null && typeof value.rejectionReason !== 'string'
    || typeof value.hasReceipt !== 'boolean'
    || value.payrollPeriod !== null && !/^\d{4}-\d{2}$/.test(value.payrollPeriod)
    || !timestampPattern.test(value.createdAt) || !timestampPattern.test(value.updatedAt)
  ) throw new Error('Invalid expense response')
  if (queue && (
    !uuidPattern.test(value.employeeId)
    || typeof value.employeeName !== 'string'
    || !optionalTimestamp(value.managerDecisionAt)
    || !optionalTimestamp(value.adminDecisionAt)
    || typeof value.canDecide !== 'boolean'
    || value.managerActorName !== null && typeof value.managerActorName !== 'string'
    || value.adminActorName !== null && typeof value.adminActorName !== 'string'
  )) throw new Error('Invalid expense response')
  return value
}

function queryString(options = {}) {
  const allowed = new Set(['cursor', 'limit', 'status', 'employeeId', 'fromDate', 'toDate'])
  const parameters = new URLSearchParams()
  for (const [name, value] of Object.entries(options)) {
    if (!allowed.has(name) || value === undefined || value === null || value === '') continue
    if (name === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid expense query')
    }
    if (name === 'status' && !statuses.has(value)) throw new TypeError('Invalid expense query')
    if (name === 'employeeId' && !uuidPattern.test(value)) throw new TypeError('Invalid expense query')
    if (['fromDate', 'toDate'].includes(name) && !datePattern.test(value)) {
      throw new TypeError('Invalid expense query')
    }
    parameters.set(name, String(value))
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

function branchHeaders(branchId) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

async function list(authentication, path, options, queue, branchId = null) {
  const response = await authentication.request(`${path}${queryString(options)}`, {
    access: 'protected',
    headers: branchId === null ? undefined : branchHeaders(branchId),
  })
  if (!Array.isArray(response.data) || response.page === null) {
    throw new Error('Invalid expense response')
  }
  return {
    items: response.data.map((item) => parseExpense(item, queue)),
    page: response.page,
  }
}

export function readSelfExpenses(authentication, options = {}) {
  return list(authentication, '/api/v1/expenses/self', options, false)
}

export function readManagerExpenses(authentication, options = {}) {
  return list(authentication, '/api/v1/expenses/manager-queue', options, true)
}

export function readAdminExpenses(authentication, branchId, options = {}) {
  return list(authentication, '/api/v1/expenses', options, true, branchId)
}

function idempotencyHeaders(branchId = null) {
  const headers = { 'Idempotency-Key': crypto.randomUUID() }
  return branchId === null ? headers : { ...headers, ...branchHeaders(branchId) }
}

export async function createExpense(authentication, values) {
  if (
    !exactKeys(values, ['category', 'amount', 'expenseDate', 'description', 'receiptId'])
    || typeof values.category !== 'string' || !moneyPattern.test(values.amount)
    || !datePattern.test(values.expenseDate) || typeof values.description !== 'string'
    || values.receiptId !== null && !uuidPattern.test(values.receiptId)
  ) throw new TypeError('Invalid expense mutation')
  const response = await authentication.request('/api/v1/expenses/self', {
    access: 'protected',
    method: 'POST',
    headers: idempotencyHeaders(),
    json: values,
  })
  return parseExpense(response.data)
}

async function decide(authentication, claim, action, reason, branchId = null) {
  if (!uuidPattern.test(claim?.id) || !timestampPattern.test(claim?.updatedAt)) {
    throw new TypeError('Invalid expense mutation')
  }
  const response = await authentication.request(`/api/v1/expenses/${claim.id}/${action}`, {
    access: 'protected',
    method: 'POST',
    headers: idempotencyHeaders(branchId),
    json: { expectedUpdatedAt: claim.updatedAt, reason },
  })
  return parseExpense(response.data, true)
}

export function managerApproveExpense(authentication, claim) {
  return decide(authentication, claim, 'manager-approve', null)
}

export function managerRejectExpense(authentication, claim, reason) {
  return decide(authentication, claim, 'manager-reject', reason)
}

export function adminApproveExpense(authentication, branchId, claim, reason = null) {
  return decide(authentication, claim, 'approve', reason, branchId)
}

export function adminRejectExpense(authentication, branchId, claim, reason) {
  return decide(authentication, claim, 'reject', reason, branchId)
}

export async function deleteExpense(authentication, claim, branchId = null) {
  if (!uuidPattern.test(claim?.id) || !timestampPattern.test(claim?.updatedAt)) {
    throw new TypeError('Invalid expense mutation')
  }
  const path = branchId === null
    ? `/api/v1/expenses/self/${claim.id}`
    : `/api/v1/expenses/${claim.id}`
  const response = await authentication.request(path, {
    access: 'protected',
    method: 'DELETE',
    headers: idempotencyHeaders(branchId),
    json: { expectedUpdatedAt: claim.updatedAt },
  })
  if (!exactKeys(response.data, ['id', 'deleted']) || response.data.id !== claim.id || response.data.deleted !== true) {
    throw new Error('Invalid expense response')
  }
}

function parseReceipt(value) {
  if (
    !exactKeys(value, ['id', 'fileName', 'contentType', 'sizeBytes', 'sha256', 'uploadedAt', 'expiresAt'])
    || !uuidPattern.test(value.id) || typeof value.fileName !== 'string'
    || !['application/pdf', 'image/png', 'image/jpeg'].includes(value.contentType)
    || !Number.isInteger(value.sizeBytes) || value.sizeBytes < 1 || value.sizeBytes > 10 * 1024 * 1024
    || !/^[0-9a-f]{64}$/.test(value.sha256) || !timestampPattern.test(value.uploadedAt)
    || !optionalTimestamp(value.expiresAt)
  ) throw new Error('Invalid expense receipt response')
  return value
}

export async function uploadExpenseReceipt(authentication, file, branchId = null, employeeId = null) {
  if (!(file instanceof File) || file.size < 1 || file.size > 10 * 1024 * 1024) {
    throw new TypeError('Invalid expense receipt')
  }
  const body = employeeId === null ? { claimId: null, employeeId: null } : { claimId: null, employeeId }
  const intent = await authentication.request('/api/v1/expenses/receipt-submissions', {
    access: 'protected',
    method: 'POST',
    headers: branchId === null ? undefined : branchHeaders(branchId),
    json: body,
  })
  if (
    !exactKeys(intent.data, ['id', 'submissionToken', 'expiresAt'])
    || !uuidPattern.test(intent.data.id) || typeof intent.data.submissionToken !== 'string'
    || !timestampPattern.test(intent.data.expiresAt)
  ) throw new Error('Invalid expense receipt response')
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', await file.arrayBuffer()))]
    .map((value) => value.toString(16).padStart(2, '0')).join('')
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('submissionToken', intent.data.submissionToken)
  form.append('sha256', digest)
  const uploaded = await authentication.request(`/api/v1/expenses/receipt-submissions/${intent.data.id}/file`, {
    access: 'protected',
    method: 'POST',
    headers: branchId === null ? undefined : branchHeaders(branchId),
    form,
  })
  return parseReceipt(uploaded.data)
}

export async function downloadExpenseReceipt(authentication, receiptId, branchId = null) {
  if (!uuidPattern.test(receiptId)) throw new TypeError('Invalid expense receipt ID')
  const response = await authentication.request(`/api/v1/expenses/receipts/${receiptId}/download`, {
    access: 'protected',
    method: 'POST',
    headers: branchId === null ? undefined : branchHeaders(branchId),
  })
  if (
    !exactKeys(response.data, ['url', 'expiresAt'])
    || typeof response.data.url !== 'string' || !timestampPattern.test(response.data.expiresAt)
  ) throw new Error('Invalid expense receipt response')
  return response.data
}
