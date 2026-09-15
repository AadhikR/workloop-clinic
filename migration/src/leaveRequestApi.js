import { parseLeaveRequest } from './leaveBalanceApi.js'
import { parseLeaveType } from './leaveConfigurationApi.js'

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const anyUuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/

function branchHeaders(branchId) {
  if (!anyUuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

function mutationHeaders(branchId, idempotencyKey) {
  if (!uuidPattern.test(idempotencyKey)) throw new TypeError('Invalid idempotency key')
  return {
    ...(branchId === null ? {} : branchHeaders(branchId)),
    'Idempotency-Key': idempotencyKey,
  }
}

export function createLeaveIdempotencyKey() {
  const key = globalThis.crypto.randomUUID()
  if (!uuidPattern.test(key)) throw new Error('Browser did not create a UUIDv4 key')
  return key
}

function validateSubmission(values, admin) {
  const required = [
    'leaveTypeId', 'startDate', 'endDate', 'isHalfDay', 'halfDayPeriod', 'reason',
    'attachmentId', 'relationship', 'deceasedName', 'dateOfDeath', 'childBirthDate',
    'childName', 'expectedDueDate', 'institutionName', 'examDates',
    'substituteEmployeeId',
  ]
  if (admin) required.push('employeeId')
  if (
    values === null
    || typeof values !== 'object'
    || Array.isArray(values)
    || Object.keys(values).length !== required.length
    || required.some((key) => !Object.hasOwn(values, key))
    || !anyUuidPattern.test(values.leaveTypeId)
    || admin && !anyUuidPattern.test(values.employeeId)
    || !datePattern.test(values.startDate)
    || !datePattern.test(values.endDate)
    || values.endDate < values.startDate
    || typeof values.isHalfDay !== 'boolean'
    || values.isHalfDay && !['AM', 'PM'].includes(values.halfDayPeriod)
    || !values.isHalfDay && values.halfDayPeriod !== null
    || typeof values.reason !== 'string'
    || values.reason.trim().length > 2000
  ) throw new TypeError('Invalid leave submission')
  const optionalStrings = {
    deceasedName: 200,
    childName: 200,
    institutionName: 300,
    examDates: 1000,
  }
  for (const [key, maximum] of Object.entries(optionalStrings)) {
    if (
      values[key] !== null
      && (typeof values[key] !== 'string' || values[key].trim().length > maximum)
    ) throw new TypeError('Invalid leave submission')
  }
  if (values.relationship !== null && !['Spouse', 'Parent', 'Child', 'Sibling'].includes(
    values.relationship,
  )) throw new TypeError('Invalid leave submission')
  for (const key of ['dateOfDeath', 'childBirthDate', 'expectedDueDate']) {
    if (values[key] !== null && !datePattern.test(values[key])) {
      throw new TypeError('Invalid leave submission')
    }
  }
  for (const key of ['attachmentId', 'substituteEmployeeId']) {
    if (values[key] !== null && !anyUuidPattern.test(values[key])) {
      throw new TypeError('Invalid leave submission')
    }
  }
  return Object.freeze({
    ...values,
    reason: values.reason.trim(),
    ...Object.fromEntries(Object.keys(optionalStrings).map((key) => [
      key,
      values[key] === null ? null : values[key].trim(),
    ])),
  })
}

async function submit(authentication, path, branchId, values, idempotencyKey, signal) {
  const response = await authentication.request(path, {
    access: 'protected',
    method: 'POST',
    headers: mutationHeaders(branchId, idempotencyKey),
    json: validateSubmission(values, branchId !== null),
    signal,
  })
  return parseLeaveRequest(response.data)
}

export function submitEmployeeLeaveRequest(
  authentication, values, idempotencyKey, { signal } = {},
) {
  return submit(
    authentication,
    '/api/v1/leave/requests/self',
    null,
    values,
    idempotencyKey,
    signal,
  )
}

export function submitAdminLeaveRequest(
  authentication, branchId, values, idempotencyKey, { signal } = {},
) {
  return submit(
    authentication,
    '/api/v1/leave/requests/branch',
    branchId,
    values,
    idempotencyKey,
    signal,
  )
}

async function cancel(authentication, path, branchId, idempotencyKey, signal) {
  const response = await authentication.request(path, {
    access: 'protected',
    method: 'POST',
    headers: mutationHeaders(branchId, idempotencyKey),
    json: {},
    signal,
  })
  return parseLeaveRequest(response.data)
}

export function cancelEmployeeLeaveRequest(
  authentication, requestId, idempotencyKey, { signal } = {},
) {
  if (!anyUuidPattern.test(requestId)) throw new TypeError('Invalid leave request ID')
  return cancel(
    authentication,
    `/api/v1/leave/requests/${requestId}/cancel/self`,
    null,
    idempotencyKey,
    signal,
  )
}

export function cancelAdminLeaveRequest(
  authentication, branchId, requestId, idempotencyKey, { signal } = {},
) {
  if (!anyUuidPattern.test(requestId)) throw new TypeError('Invalid leave request ID')
  return cancel(
    authentication,
    `/api/v1/leave/requests/${requestId}/cancel/branch`,
    branchId,
    idempotencyKey,
    signal,
  )
}

export async function readSubmissionLeaveTypes(authentication, branchId, { signal } = {}) {
  const headers = branchId === null ? undefined : branchHeaders(branchId)
  const rows = []
  let cursor
  do {
    const parameters = new URLSearchParams({ limit: '100' })
    if (cursor) parameters.set('cursor', cursor)
    const response = await authentication.request(`/api/v1/leave/types?${parameters}`, {
      access: 'protected', headers, signal,
    })
    if (!Array.isArray(response.data)) throw new Error('Invalid leave type response')
    rows.push(...response.data.map(parseLeaveType))
    cursor = response.page?.nextCursor ?? null
  } while (cursor)
  return Object.freeze(rows)
}
