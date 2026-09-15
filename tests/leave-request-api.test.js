import assert from 'node:assert/strict'
import test from 'node:test'

import {
  cancelAdminLeaveRequest,
  cancelEmployeeLeaveRequest,
  submitAdminLeaveRequest,
  submitEmployeeLeaveRequest,
} from '../migration/src/leaveRequestApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const employeeId = '21000000-0000-4000-8000-000000000002'
const typeId = '8d000000-0000-4000-8000-000000000001'
const requestId = '7a2fde23-dc8c-560c-937c-4ef631aff6b2'
const key = '8e000000-0000-4000-8000-000000000001'

function requestResponse(changes = {}) {
  return {
    id: requestId,
    branchId,
    employeeId,
    leaveTypeId: typeId,
    startDate: '2026-09-28',
    endDate: '2026-09-28',
    isHalfDay: false,
    halfDayPeriod: null,
    daysRequested: '1.00',
    status: 'Pending',
    reason: 'Appointment',
    attachment: null,
    rejectionReason: '',
    managerRejectionReason: '',
    relationship: '',
    deceasedName: '',
    dateOfDeath: null,
    childBirthDate: null,
    childName: '',
    expectedDueDate: null,
    institutionName: '',
    examDates: '',
    substituteEmployeeId: null,
    approvalLevelRequired: 1,
    approvalComment: '',
    warnings: [],
    submittedAt: '2026-09-15T08:00:00.000Z',
    createdAt: '2026-09-15T08:00:00.000Z',
    updatedAt: '2026-09-15T08:00:00.000Z',
    ...changes,
  }
}

function payload(changes = {}) {
  return {
    leaveTypeId: typeId,
    startDate: '2026-09-28',
    endDate: '2026-09-28',
    isHalfDay: false,
    halfDayPeriod: null,
    reason: ' Appointment ',
    attachmentId: null,
    relationship: null,
    deceasedName: null,
    dateOfDeath: null,
    childBirthDate: null,
    childName: null,
    expectedDueDate: null,
    institutionName: null,
    examDates: null,
    substituteEmployeeId: null,
    ...changes,
  }
}

test('submits self and administrator requests with exact command headers', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return { data: requestResponse() }
    },
  }
  await submitEmployeeLeaveRequest(authentication, payload(), key)
  await submitAdminLeaveRequest(
    authentication, branchId, { ...payload(), employeeId }, key,
  )
  assert.equal(calls[0].path, '/api/v1/leave/requests/self')
  assert.deepEqual(calls[0].options.headers, { 'Idempotency-Key': key })
  assert.equal(calls[0].options.json.reason, 'Appointment')
  assert.equal(calls[1].path, '/api/v1/leave/requests/branch')
  assert.deepEqual(calls[1].options.headers, {
    'X-Workloop-Branch-ID': branchId,
    'Idempotency-Key': key,
  })
  assert.equal(calls[1].options.json.employeeId, employeeId)
})

test('cancels with an empty body and rejects browser-derived authority fields', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return { data: requestResponse({ status: 'Cancelled' }) }
    },
  }
  await cancelEmployeeLeaveRequest(authentication, requestId, key)
  await cancelAdminLeaveRequest(authentication, branchId, requestId, key)
  assert.equal(calls[0].path, `/api/v1/leave/requests/${requestId}/cancel/self`)
  assert.deepEqual(calls[0].options.json, {})
  assert.equal(calls[1].path, `/api/v1/leave/requests/${requestId}/cancel/branch`)
  await assert.rejects(submitEmployeeLeaveRequest(
    authentication,
    { ...payload(), daysRequested: '1.00' },
    key,
  ), /Invalid leave submission/)
})
