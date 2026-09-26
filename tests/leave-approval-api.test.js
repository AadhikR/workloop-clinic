import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createDelegation,
  decideLeave,
  deleteDelegation,
  readDelegations,
  updateDelegation,
} from '../src/leaveApprovalApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const requestId = '8f000000-0000-4000-8000-000000000101'
const employeeId = '21000000-0000-4000-8000-000000000001'
const delegateId = '21000000-0000-4000-8000-000000000002'
const delegationId = '8f000000-0000-4000-8000-000000000401'
const typeId = '8f000000-0000-4000-8000-000000000010'
const key = '8f000000-0000-4000-8000-000000000301'
const updatedAt = '2026-09-15T08:00:00.000Z'

function requestResponse() {
  return {
    id: requestId,
    branchId,
    employeeId: delegateId,
    leaveTypeId: typeId,
    startDate: '2026-10-01',
    endDate: '2026-10-01',
    isHalfDay: false,
    halfDayPeriod: null,
    daysRequested: '1.00',
    status: 'Approved',
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
    approvalComment: 'Coverage confirmed',
    warnings: [],
    submittedAt: updatedAt,
    createdAt: updatedAt,
    updatedAt,
  }
}

function delegationResponse() {
  return {
    id: delegationId,
    branchId,
    approverEmployeeId: employeeId,
    delegateEmployeeId: delegateId,
    fromDate: '2026-09-16',
    toDate: '2026-09-18',
    createdAt: updatedAt,
    updatedAt,
  }
}

test('sends staff and administrator decisions with snapshots and idempotency keys', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return { data: requestResponse() }
    },
  }
  await decideLeave(authentication, null, requestId, 'approve', '', updatedAt, key)
  await decideLeave(
    authentication, branchId, requestId, 'reject', ' No coverage ', updatedAt, key,
  )
  assert.equal(calls[0].path, `/api/v1/leave/approvals/${requestId}/decision`)
  assert.deepEqual(calls[0].options.headers, { 'Idempotency-Key': key })
  assert.equal(calls[1].path, `/api/v1/leave/approvals/${requestId}/decision/branch`)
  assert.deepEqual(calls[1].options.json, {
    decision: 'reject', reason: 'No coverage', expectedUpdatedAt: updatedAt,
  })
  assert.equal(calls[1].options.headers['X-Workloop-Branch-ID'], branchId)
})

test('uses branch-scoped delegation commands with optimistic snapshots', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return path.endsWith('/branch') && options?.method === undefined
        ? { data: [delegationResponse()] }
        : { data: delegationResponse() }
    },
  }
  const values = {
    approverEmployeeId: employeeId,
    delegateEmployeeId: delegateId,
    fromDate: '2026-09-16',
    toDate: '2026-09-18',
  }
  assert.equal((await readDelegations(authentication, branchId)).length, 1)
  await createDelegation(authentication, branchId, values)
  await updateDelegation(authentication, branchId, delegationId, {
    ...values, expectedUpdatedAt: updatedAt,
  })
  await deleteDelegation(authentication, branchId, delegationId, updatedAt)
  assert.deepEqual(calls.map((call) => call.options.method ?? 'GET'), [
    'GET', 'POST', 'PUT', 'DELETE',
  ])
  assert.deepEqual(calls[3].options.json, { expectedUpdatedAt: updatedAt })
  assert.ok(calls.every((call) => call.options.headers['X-Workloop-Branch-ID'] === branchId))
})
