import { parseLeaveRequest } from './leaveBalanceApi.js'
import { parseLeaveType } from './leaveConfigurationApi.js'
import { createLeaveIdempotencyKey } from './leaveRequestApi.js'

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/

function branchHeaders(branchId) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

function parseEmployee(value) {
  if (
    value === null || typeof value !== 'object' || Array.isArray(value)
    || !uuidPattern.test(value.id) || typeof value.employeeNumber !== 'string'
    || typeof value.name !== 'string' || typeof value.jobTitle !== 'string'
    || typeof value.department !== 'string'
  ) throw new Error('Invalid queue employee')
  return Object.freeze({ ...value })
}

function parseBalance(value) {
  if (value === null) return null
  if (
    typeof value !== 'object' || Array.isArray(value)
    || !uuidPattern.test(value.employeeId) || !uuidPattern.test(value.leaveTypeId)
    || !Number.isInteger(value.leaveYear)
  ) throw new Error('Invalid queue balance')
  return Object.freeze({ ...value })
}

function parseQueueItem(value) {
  if (
    value === null || typeof value !== 'object' || Array.isArray(value)
    || typeof value.canDecide !== 'boolean'
    || !['directReport', 'activeDelegation', 'administrator'].includes(value.visibleBecause)
  ) throw new Error('Invalid leave queue item')
  return Object.freeze({
    request: parseLeaveRequest(value.request),
    employee: parseEmployee(value.employee),
    leaveType: parseLeaveType(value.leaveType),
    balance: parseBalance(value.balance),
    canDecide: value.canDecide,
    visibleBecause: value.visibleBecause,
  })
}

async function readAllQueue(authentication, branchId, signal) {
  const rows = []
  let cursor
  do {
    const parameters = new URLSearchParams({ limit: '100' })
    if (cursor) parameters.set('cursor', cursor)
    const path = branchId
      ? `/api/v1/leave/approvals/branch?${parameters}`
      : `/api/v1/leave/approvals/queue?${parameters}`
    const response = await authentication.request(path, {
      access: 'protected', headers: branchId ? branchHeaders(branchId) : undefined, signal,
    })
    if (!Array.isArray(response.data)) throw new Error('Invalid leave queue')
    rows.push(...response.data.map(parseQueueItem))
    cursor = response.page?.nextCursor ?? null
  } while (cursor)
  return Object.freeze(rows)
}

export function readApproverQueue(authentication, { signal } = {}) {
  return readAllQueue(authentication, null, signal)
}

export function readAdminApprovalQueue(authentication, branchId, { signal } = {}) {
  return readAllQueue(authentication, branchId, signal)
}

export async function decideLeave(
  authentication, branchId, requestId, decision, reason, expectedUpdatedAt,
  idempotencyKey = createLeaveIdempotencyKey(), { signal } = {},
) {
  if (
    !uuidPattern.test(requestId) || !['approve', 'reject'].includes(decision)
    || typeof reason !== 'string' || reason.trim().length > 2000
    || !timestampPattern.test(expectedUpdatedAt)
  ) throw new TypeError('Invalid leave decision')
  const path = branchId
    ? `/api/v1/leave/approvals/${requestId}/decision/branch`
    : `/api/v1/leave/approvals/${requestId}/decision`
  const response = await authentication.request(path, {
    access: 'protected',
    method: 'POST',
    headers: {
      ...(branchId ? branchHeaders(branchId) : {}),
      'Idempotency-Key': idempotencyKey,
    },
    json: { decision, reason: reason.trim(), expectedUpdatedAt },
    signal,
  })
  return parseLeaveRequest(response.data)
}

function parseDelegation(value) {
  if (
    value === null || typeof value !== 'object' || Array.isArray(value)
    || !uuidPattern.test(value.id) || !uuidPattern.test(value.branchId)
    || !uuidPattern.test(value.approverEmployeeId) || !uuidPattern.test(value.delegateEmployeeId)
    || typeof value.fromDate !== 'string' || typeof value.toDate !== 'string'
    || !timestampPattern.test(value.createdAt) || !timestampPattern.test(value.updatedAt)
  ) throw new Error('Invalid leave delegation')
  return Object.freeze({ ...value })
}

export async function readDelegations(authentication, branchId, { signal } = {}) {
  const response = await authentication.request('/api/v1/leave/delegations/branch', {
    access: 'protected', headers: branchHeaders(branchId), signal,
  })
  if (!Array.isArray(response.data)) throw new Error('Invalid leave delegations')
  return Object.freeze(response.data.map(parseDelegation))
}

export async function createDelegation(authentication, branchId, values, { signal } = {}) {
  const response = await authentication.request('/api/v1/leave/delegations/branch', {
    access: 'protected', method: 'POST', headers: branchHeaders(branchId), json: values, signal,
  })
  return parseDelegation(response.data)
}

export async function updateDelegation(
  authentication, branchId, delegationId, values, { signal } = {},
) {
  if (!uuidPattern.test(delegationId)) throw new TypeError('Invalid delegation ID')
  const response = await authentication.request(
    `/api/v1/leave/delegations/${delegationId}/branch`,
    {
      access: 'protected', method: 'PUT', headers: branchHeaders(branchId), json: values, signal,
    },
  )
  return parseDelegation(response.data)
}

export async function deleteDelegation(
  authentication, branchId, delegationId, expectedUpdatedAt, { signal } = {},
) {
  if (!uuidPattern.test(delegationId) || !timestampPattern.test(expectedUpdatedAt)) {
    throw new TypeError('Invalid delegation delete')
  }
  await authentication.request(`/api/v1/leave/delegations/${delegationId}/branch`, {
    access: 'protected',
    method: 'DELETE',
    headers: branchHeaders(branchId),
    json: { expectedUpdatedAt },
    signal,
  })
}

function parseAuditEntry(value) {
  if (
    value === null || typeof value !== 'object' || Array.isArray(value)
    || !uuidPattern.test(value.id) || !uuidPattern.test(value.leaveRequestId)
    || typeof value.action !== 'string' || typeof value.reason !== 'string'
    || typeof value.oldStatus !== 'string' || typeof value.newStatus !== 'string'
    || !timestampPattern.test(value.createdAt)
  ) throw new Error('Invalid leave audit entry')
  return Object.freeze({ ...value })
}

export async function readLeaveAudit(authentication, branchId, requestId, { signal } = {}) {
  if (!uuidPattern.test(requestId)) throw new TypeError('Invalid leave request ID')
  const path = branchId
    ? `/api/v1/leave/approvals/${requestId}/audit/branch`
    : `/api/v1/leave/approvals/${requestId}/audit`
  const response = await authentication.request(path, {
    access: 'protected', headers: branchId ? branchHeaders(branchId) : undefined, signal,
  })
  if (!Array.isArray(response.data)) throw new Error('Invalid leave audit')
  return Object.freeze(response.data.map(parseAuditEntry))
}
