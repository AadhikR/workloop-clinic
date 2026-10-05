import { readCollectionPages } from './collectionPages.js'

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const date = /^\d{4}-\d{2}-\d{2}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const money = /^(?:0|[1-9]\d{0,11})\.\d{2}$/

export const adminAlertCodes = ['probation', 'contracts', 'certifications', 'requests', 'appraisals', 'documents', 'insurance', 'policyRenewals', 'payrollApproval', 'wpsOverdue']

export async function readAdminWorkspaceSummary(authentication, branchId) {
  const response = await authentication.request('/api/v1/dashboards/admin/workspace-summary', { access: 'protected', headers: headers(branchId) })
  const value = response?.data
  const counts = ['activeEmployees', 'payrollRuns', 'draftPayrolls', 'sifGenerated', 'insurancePolicies']
  if (!exact(value, ['businessDate', ...counts, 'alerts']) || !date.test(value.businessDate)
    || counts.some((key) => !Number.isInteger(value[key]) || value[key] < 0)
    || !exact(value.alerts, adminAlertCodes)
    || adminAlertCodes.some((key) => !Number.isInteger(value.alerts[key]) || value.alerts[key] < 0)
    || value.draftPayrolls > value.payrollRuns || value.sifGenerated > value.payrollRuns) throw new Error('Invalid administrator workspace summary')
  return value
}

function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}

function headers(branchId, key) {
  if (branchId !== null && !uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return { ...(branchId === null ? {} : { 'X-Workloop-Branch-ID': branchId }),
    ...(key ? { 'Idempotency-Key': key } : {}) }
}

async function pages(authentication, path, branchId, parser, options = {}) {
  return readCollectionPages(async (cursor) => {
    const query = new URLSearchParams({ ...options, limit: '100', ...(cursor ? { cursor } : {}) })
    const response = await authentication.request(`${path}?${query}`, {
      access: 'protected', headers: headers(branchId),
    })
    if (!Array.isArray(response?.data)) throw new Error('Invalid portal projection')
    return { items: response.data.map(parser), page: response.page }
  })
}

export function parseExpirySource(value) {
  if (!exact(value, ['id', 'employeeId', 'employeeName', 'sourceType', 'expiryDate', 'status'])
    || typeof value.id !== 'string' || !value.id || !uuid.test(value.employeeId)
    || typeof value.employeeName !== 'string' || typeof value.sourceType !== 'string'
    || value.expiryDate !== null && !date.test(value.expiryDate)
    || !['valid', 'expiring', 'expired'].includes(value.status)) throw new Error('Invalid expiry source')
  return Object.freeze(value)
}

export function readBranchExpiry(authentication, branchId) {
  return pages(authentication, '/api/v1/employees/expiry-summary', branchId, parseExpirySource)
}

export function readEmployeeDirectoryDetails(authentication, branchId) {
  return pages(authentication, '/api/v1/employees/directory-details', branchId, (value) => {
    if (!exact(value, ['id', 'molId', 'allowance', 'visaExpiry', 'emiratesIdExpiry'])
      || !uuid.test(value.id) || typeof value.molId !== 'string' || !money.test(value.allowance)
      || [value.visaExpiry, value.emiratesIdExpiry].some((item) => item !== null && !date.test(item))) {
      throw new Error('Invalid employee directory detail')
    }
    return Object.freeze(value)
  })
}

export function readClinicalCredentials(authentication, branchId, status) {
  if (!['valid', 'expiring', 'expired'].includes(status)) throw new TypeError('Invalid credential status')
  return pages(authentication, '/api/v1/dashboards/clinical/credentials', branchId, parseExpirySource, { status })
}

export const workforceGroups = Object.freeze(['activeStaff', 'credentialCompliance', 'coverage', 'probation', 'newJoiners', 'birthdays', 'onLeaveToday', 'pendingLeave', 'onDutyNow'])

export async function readClinicalWorkforceSummary(authentication, branchId) {
  const { data } = await authentication.request('/api/v1/dashboards/clinical/workforce-summary', {
    access: 'protected', headers: headers(branchId),
  })
  const count = (value) => Number.isInteger(value) && value >= 0
  if (!exact(data, ['businessDate', 'counts', 'compliant', 'rostered', 'departments'])
    || !date.test(data.businessDate) || !exact(data.counts, workforceGroups)
    || !Object.values(data.counts).every(count) || !count(data.compliant) || !count(data.rostered)
    || data.compliant > data.counts.credentialCompliance || data.rostered > data.counts.activeStaff
    || data.counts.coverage !== data.counts.activeStaff || !Array.isArray(data.departments)) {
    throw new Error('Invalid clinical workforce summary')
  }
  const seen = new Set()
  for (const item of data.departments) {
    if (!exact(item, ['department', 'headcount', 'credentialled', 'rostered', 'minStaff'])
      || typeof item.department !== 'string' || seen.has(item.department)
      || ![item.headcount, item.credentialled, item.rostered, item.minStaff].every(count)
      || item.credentialled > item.headcount || item.rostered > item.headcount) {
      throw new Error('Invalid clinical department summary')
    }
    seen.add(item.department)
  }
  if (data.departments.reduce((total, item) => total + item.headcount, 0) !== data.counts.activeStaff
    || data.departments.reduce((total, item) => total + item.credentialled, 0) !== data.compliant
    || data.departments.reduce((total, item) => total + item.rostered, 0) !== data.rostered) {
    throw new Error('Clinical department totals do not agree')
  }
  return data
}

export function readClinicalWorkforceDetails(authentication, branchId, group) {
  if (!workforceGroups.includes(group)) throw new TypeError('Invalid clinical workforce group')
  return pages(authentication, '/api/v1/dashboards/clinical/workforce-details', branchId, (value) => {
    if (!exact(value, ['id', 'employeeId', 'employeeName', 'department', 'jobTitle', 'status', 'sourceDate', 'sourceTime', 'sourceLabel'])
      || typeof value.id !== 'string' || !value.id || !uuid.test(value.employeeId)
      || !['employeeName', 'department', 'jobTitle', 'status', 'sourceLabel'].every((field) => typeof value[field] === 'string')
      || value.sourceDate !== null && !date.test(value.sourceDate)
      || value.sourceTime !== null && !instant.test(value.sourceTime)) throw new Error('Invalid clinical workforce detail')
    return Object.freeze(value)
  }, { group })
}

export function parseLeaveAction(value) {
  if (!exact(value, ['id', 'requestId', 'employeeId', 'employeeName', 'leaveType', 'startDate',
    'endDate', 'action', 'reason', 'actorName', 'actionAt'])
    || ![value.id, value.requestId, value.employeeId].every((id) => uuid.test(id))
    || ![value.employeeName, value.leaveType, value.reason, value.actorName].every((item) => typeof item === 'string')
    || !date.test(value.startDate) || !date.test(value.endDate) || !instant.test(value.actionAt)
    || !['approved', 'rejected', 'manager_approved', 'manager_rejected'].includes(value.action)) {
    throw new Error('Invalid leave action history')
  }
  return Object.freeze(value)
}

export function readRecentLeaveActions(authentication) {
  return pages(authentication, '/api/v1/leave/approvals/recent', null, parseLeaveAction)
}

function cents(value) {
  if (!money.test(value)) throw new Error('Invalid repayment amount')
  return BigInt(value.replace('.', ''))
}

export async function readOwnAdvanceProgress(authentication, advanceId) {
  if (!uuid.test(advanceId)) throw new TypeError('Invalid advance ID')
  let summary = null
  const payments = await readCollectionPages(async (cursor) => {
    const query = new URLSearchParams({ limit: '100', ...(cursor ? { cursor } : {}) })
    const response = await authentication.request(`/api/v1/advances/${advanceId}/self-progress?${query}`, { access: 'protected' })
    const current = response?.summary
    if (!exact(current, ['advanceId', 'amount', 'totalPaid', 'outstandingBalance', 'status', 'updatedAt', 'sourceVersion', 'schedule'])
      || current.advanceId !== advanceId || !instant.test(current.updatedAt)
      || !/^sha256:[0-9a-f]{64}$/.test(current.sourceVersion) || !Array.isArray(current.schedule)
      || !['pending', 'active', 'settled', 'cancelled'].includes(current.status)
      || cents(current.amount) !== cents(current.totalPaid) + cents(current.outstandingBalance)
      || !Array.isArray(response.data)) throw new Error('Invalid advance progress')
    if (summary !== null && current.sourceVersion !== summary.sourceVersion) throw new Error('The repayment source changed. Refresh the advance.')
    summary = current
    const items = response.data.map((value) => {
      if (!exact(value, ['id', 'amount', 'paidDate', 'payrollPeriod', 'createdAt'])
        || !uuid.test(value.id) || !date.test(value.paidDate) || !instant.test(value.createdAt)
        || value.payrollPeriod !== null && !/^\d{4}-\d{2}$/.test(value.payrollPeriod)) throw new Error('Invalid own repayment')
      cents(value.amount)
      return Object.freeze(value)
    })
    return { items, page: response.page }
  })
  const schedule = summary.schedule.map((row) => {
    if (!exact(row, ['period', 'scheduledAmount', 'paidAmount', 'remainingAmount', 'status'])
      || !/^\d{4}-\d{2}$/.test(row.period) || !['paid', 'partial', 'due', 'upcoming'].includes(row.status)
      || cents(row.scheduledAmount) !== cents(row.paidAmount) + cents(row.remainingAmount)) throw new Error('Invalid own installment')
    return Object.freeze(row)
  })
  if (payments.reduce((sum, row) => sum + cents(row.amount), 0n) !== cents(summary.totalPaid)
    || schedule.reduce((sum, row) => sum + cents(row.scheduledAmount), 0n) !== cents(summary.amount)
    || schedule.reduce((sum, row) => sum + cents(row.paidAmount), 0n) !== cents(summary.totalPaid)
    || schedule.reduce((sum, row) => sum + cents(row.remainingAmount), 0n) !== cents(summary.outstandingBalance)) {
    throw new Error('Repayment detail does not match the advance balance')
  }
  return Object.freeze({ summary: Object.freeze({ ...summary, schedule }), payments })
}

export function parseRetainedRecord(value) {
  if (!exact(value, ['id', 'entityType', 'label', 'status', 'archived', 'updatedAt'])
    || !uuid.test(value.id) || !['appraisal', 'incident_report', 'expense_claim', 'salary_advance'].includes(value.entityType)
    || typeof value.label !== 'string' || typeof value.status !== 'string'
    || typeof value.archived !== 'boolean' || !instant.test(value.updatedAt)) throw new Error('Invalid retained record')
  return Object.freeze(value)
}

export function readRetainedRecords(authentication, branchId, kind) {
  return pages(authentication, '/api/v1/retained-records', branchId, parseRetainedRecord, { kind })
}

export async function setRecordArchived(authentication, branchId, kind, record, archived, key = crypto.randomUUID()) {
  const response = await authentication.request(`/api/v1/retained-records/${kind}/${record.id}/${archived ? 'archive' : 'restore'}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, key), json: { expectedUpdatedAt: record.updatedAt },
  })
  return parseRetainedRecord(response.data)
}

export async function cancelPendingAdminAdvance(authentication, branchId, record, key = crypto.randomUUID()) {
  const response = await authentication.request(`/api/v1/advances/${record.id}/admin-cancel`, {
    access: 'protected', method: 'POST', headers: headers(branchId, key), json: { expectedUpdatedAt: record.updatedAt },
  })
  return parseRetainedRecord(response.data)
}
