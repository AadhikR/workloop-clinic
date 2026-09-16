const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const periodPattern = /^\d{4}-(?:0[1-9]|1[0-2])$/
const moneyPattern = /^(?:0|[1-9]\d{0,9})\.\d{2}$/
const statuses = new Set(['pending', 'active', 'settled', 'cancelled'])

const selfKeys = [
  'id', 'amount', 'reason', 'status', 'repaymentStartPeriod', 'installmentCount',
  'monthlyInstallment', 'outstandingBalance', 'nextRepaymentPeriod', 'rejectionReason',
  'createdAt', 'updatedAt',
]
const adminKeys = [
  ...selfKeys, 'employeeId', 'employeeName', 'creatorName', 'decisionActorName',
  'disbursedDate', 'canDecide', 'schedule', 'repayments',
]
const scheduleKeys = ['period', 'scheduledAmount', 'paidAmount', 'remainingAmount', 'status']
const repaymentKeys = [
  'id', 'amount', 'paidDate', 'payrollRunId', 'payrollPeriod', 'repaymentKind', 'createdAt',
]

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function nullable(value, predicate) {
  return value === null || predicate(value)
}

function parseSchedule(value) {
  if (
    !exactKeys(value, scheduleKeys) || !periodPattern.test(value.period)
    || !moneyPattern.test(value.scheduledAmount) || !moneyPattern.test(value.paidAmount)
    || !moneyPattern.test(value.remainingAmount)
    || !['paid', 'partial', 'due', 'upcoming'].includes(value.status)
  ) throw new Error('Invalid salary advance response')
  return value
}

function parseRepayment(value) {
  if (
    !exactKeys(value, repaymentKeys) || !uuidPattern.test(value.id)
    || !moneyPattern.test(value.amount) || !datePattern.test(value.paidDate)
    || !nullable(value.payrollRunId, (item) => uuidPattern.test(item))
    || !nullable(value.payrollPeriod, (item) => periodPattern.test(item))
    || !['manual', 'payroll', 'settlement'].includes(value.repaymentKind)
    || !timestampPattern.test(value.createdAt)
  ) throw new Error('Invalid salary advance response')
  return value
}

export function parseAdvance(value, admin = false) {
  if (
    !exactKeys(value, admin ? adminKeys : selfKeys) || !uuidPattern.test(value.id)
    || !moneyPattern.test(value.amount) || typeof value.reason !== 'string'
    || !statuses.has(value.status) || !periodPattern.test(value.repaymentStartPeriod)
    || !Number.isInteger(value.installmentCount) || value.installmentCount < 1
    || !moneyPattern.test(value.monthlyInstallment)
    || !moneyPattern.test(value.outstandingBalance)
    || !nullable(value.nextRepaymentPeriod, (item) => periodPattern.test(item))
    || !nullable(value.rejectionReason, (item) => typeof item === 'string')
    || !timestampPattern.test(value.createdAt) || !timestampPattern.test(value.updatedAt)
  ) throw new Error('Invalid salary advance response')
  if (admin && (
    !uuidPattern.test(value.employeeId) || typeof value.employeeName !== 'string'
    || typeof value.creatorName !== 'string'
    || !nullable(value.decisionActorName, (item) => typeof item === 'string')
    || !nullable(value.disbursedDate, (item) => datePattern.test(item))
    || typeof value.canDecide !== 'boolean' || !Array.isArray(value.schedule)
    || !Array.isArray(value.repayments)
  )) throw new Error('Invalid salary advance response')
  if (admin) {
    value.schedule.forEach(parseSchedule)
    value.repayments.forEach(parseRepayment)
  }
  return value
}

function branchHeaders(branchId) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

function mutationHeaders(branchId = null) {
  const headers = { 'Idempotency-Key': crypto.randomUUID() }
  return branchId === null ? headers : { ...headers, ...branchHeaders(branchId) }
}

function queryString(options = {}) {
  const allowed = new Set(['cursor', 'limit', 'status', 'employeeId', 'repaymentStartPeriod'])
  const parameters = new URLSearchParams()
  for (const [name, value] of Object.entries(options)) {
    if (!allowed.has(name) || value === undefined || value === null || value === '') continue
    if (name === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid salary advance query')
    }
    if (name === 'status' && !statuses.has(value)) throw new TypeError('Invalid salary advance query')
    if (name === 'employeeId' && !uuidPattern.test(value)) throw new TypeError('Invalid salary advance query')
    if (name === 'repaymentStartPeriod' && !periodPattern.test(value)) throw new TypeError('Invalid salary advance query')
    parameters.set(name, String(value))
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

async function list(authentication, path, options, admin, branchId = null) {
  const response = await authentication.request(`${path}${queryString(options)}`, {
    access: 'protected',
    headers: branchId === null ? undefined : branchHeaders(branchId),
  })
  if (!Array.isArray(response.data) || response.page === null) {
    throw new Error('Invalid salary advance response')
  }
  return { items: response.data.map((item) => parseAdvance(item, admin)), page: response.page }
}

export function readSelfAdvances(authentication, options = {}) {
  return list(authentication, '/api/v1/advances/self', options, false)
}

export function readAdminAdvances(authentication, branchId, options = {}) {
  return list(authentication, '/api/v1/advances', options, true, branchId)
}

function validatePlan(values, admin) {
  const keys = admin
    ? ['employeeId', 'amount', 'reason', 'installmentCount', 'repaymentStartPeriod']
    : ['amount', 'reason', 'installmentCount', 'repaymentStartPeriod']
  if (
    !exactKeys(values, keys) || admin && !uuidPattern.test(values.employeeId)
    || !moneyPattern.test(values.amount) || typeof values.reason !== 'string'
    || !Number.isInteger(values.installmentCount) || values.installmentCount < 1
    || values.installmentCount > 120 || !periodPattern.test(values.repaymentStartPeriod)
  ) throw new TypeError('Invalid salary advance mutation')
}

export async function createSelfAdvance(authentication, values) {
  validatePlan(values, false)
  const response = await authentication.request('/api/v1/advances/self', {
    access: 'protected', method: 'POST', headers: mutationHeaders(), json: values,
  })
  return parseAdvance(response.data)
}

export async function createAdminAdvance(authentication, branchId, values) {
  validatePlan(values, true)
  const response = await authentication.request('/api/v1/advances', {
    access: 'protected', method: 'POST', headers: mutationHeaders(branchId), json: values,
  })
  return parseAdvance(response.data, true)
}

function versionBody(advance, extra = {}) {
  if (!uuidPattern.test(advance?.id) || !timestampPattern.test(advance?.updatedAt)) {
    throw new TypeError('Invalid salary advance mutation')
  }
  return { expectedUpdatedAt: advance.updatedAt, ...extra }
}

async function command(authentication, path, advance, body, branchId = null, method = 'POST', admin = true) {
  const response = await authentication.request(`/api/v1/advances/${path}`, {
    access: 'protected', method, headers: mutationHeaders(branchId), json: versionBody(advance, body),
  })
  return parseAdvance(response.data, admin)
}

export function withdrawAdvance(authentication, advance) {
  return command(authentication, `self/${advance.id}/withdraw`, advance, {}, null, 'POST', false)
}

export function approveAdvance(authentication, branchId, advance) {
  return command(authentication, `${advance.id}/approve`, advance, { reason: null }, branchId)
}

export function rejectAdvance(authentication, branchId, advance, reason) {
  return command(authentication, `${advance.id}/reject`, advance, { reason }, branchId)
}

export function replaceAdvanceSchedule(authentication, branchId, advance, values) {
  validatePlan({ ...values, reason: advance.reason }, false)
  return command(authentication, `${advance.id}/schedule`, advance, values, branchId, 'PUT')
}

export function recordAdvanceRepayment(authentication, branchId, advance, amount) {
  if (!moneyPattern.test(amount)) throw new TypeError('Invalid salary advance mutation')
  return command(authentication, `${advance.id}/repayments`, advance, { amount }, branchId)
}

export function settleAdvance(authentication, branchId, advance) {
  return command(authentication, `${advance.id}/settle`, advance, {}, branchId)
}
