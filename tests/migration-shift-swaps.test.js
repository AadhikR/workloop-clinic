import assert from 'node:assert/strict'
import test from 'node:test'

import {
  approveShiftSwap,
  cancelShiftSwap,
  readAdminShiftSwaps,
  readPersonalShiftSwaps,
  rejectShiftSwap,
  submitShiftSwap,
} from '../migration/src/shiftSwapApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const requesterId = '30000000-0000-4000-8000-000000000001'
const targetId = '30000000-0000-4000-8000-000000000002'
const requesterAssignmentId = '40000000-0000-4000-8000-000000000001'
const targetAssignmentId = '40000000-0000-4000-8000-000000000002'
const swapId = '50000000-0000-4000-8000-000000000001'
const publicationId = '60000000-0000-4000-8000-000000000001'
const key = '70000000-0000-4000-8000-000000000001'
const sourceVersion = `sha256:${'a'.repeat(64)}`
const swap = {
  id: swapId,
  requesterEmployeeId: requesterId,
  requesterEmployeeName: 'Ravi Test',
  targetEmployeeId: targetId,
  targetEmployeeName: 'Fatima Test',
  requesterDate: '2026-10-05',
  targetDate: '2026-10-06',
  reason: 'Family appointment',
  status: 'pending',
  rejectionReason: '',
  expectedSourceVersion: sourceVersion,
  requesterAssignmentId,
  targetAssignmentId,
  requesterAssignmentVersion: 2,
  targetAssignmentVersion: 2,
  approvedPublicationVersionId: null,
  decidedAt: null,
  decidedByAppUserId: null,
  createdAt: '2026-09-22T06:00:00.000Z',
  updatedAt: '2026-09-22T06:00:00.000Z',
  version: 1,
}

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('reads strict personal and selected-branch swap collections', async () => {
  const personal = client({ data: [swap], page: { limit: 100, nextCursor: null, hasMore: false } })
  assert.equal((await readPersonalShiftSwaps(personal))[0].id, swapId)
  assert.equal(personal.requests[0][0], '/api/v1/roster/shift-swaps/self?limit=100')

  const admin = client({ data: [swap], page: { limit: 20, nextCursor: null, hasMore: false } })
  await readAdminShiftSwaps(admin, branchId, { status: 'pending', limit: 20 })
  assert.equal(admin.requests[0][0], '/api/v1/roster/shift-swaps?limit=20&status=pending')
  assert.equal(admin.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)
})

test('submits and cancels only exact personal swap commands', async () => {
  const submitClient = client({ data: swap })
  await submitShiftSwap(submitClient, {
    requesterDate: swap.requesterDate,
    targetEmployeeId: targetId,
    targetDate: swap.targetDate,
    reason: ' Family appointment ',
    expectedSourceVersion: sourceVersion,
  }, { idempotencyKey: key })
  assert.deepEqual(submitClient.requests[0][1].json, {
    requesterDate: swap.requesterDate,
    targetEmployeeId: targetId,
    targetDate: swap.targetDate,
    reason: 'Family appointment',
    expectedSourceVersion: sourceVersion,
  })
  assert.equal(submitClient.requests[0][1].headers['Idempotency-Key'], key)

  const cancelled = { ...swap, status: 'cancelled', decidedAt: '2026-09-22T06:05:00.000Z', decidedByAppUserId: requesterId, updatedAt: '2026-09-22T06:05:00.000Z', version: 2 }
  const cancelClient = client({ data: cancelled })
  await cancelShiftSwap(cancelClient, swap, { idempotencyKey: key })
  assert.deepEqual(cancelClient.requests[0][1].json, { expectedVersion: 1, reason: null })
})

test('rejects and approves with selected-branch expected versions', async () => {
  const rejected = { ...swap, status: 'rejected', rejectionReason: 'Coverage is required', decidedAt: '2026-09-22T06:05:00.000Z', decidedByAppUserId: requesterId, updatedAt: '2026-09-22T06:05:00.000Z', version: 2 }
  const rejectClient = client({ data: rejected })
  await rejectShiftSwap(rejectClient, branchId, swap, ' Coverage is required ', { idempotencyKey: key })
  assert.deepEqual(rejectClient.requests[0][1].json, { expectedVersion: 1, reason: 'Coverage is required' })

  const approved = { ...swap, status: 'approved', approvedPublicationVersionId: publicationId, decidedAt: '2026-09-22T06:05:00.000Z', decidedByAppUserId: requesterId, updatedAt: '2026-09-22T06:05:00.000Z', version: 2 }
  const approveClient = client({ data: approved })
  await approveShiftSwap(approveClient, branchId, swap, { idempotencyKey: key })
  assert.deepEqual(approveClient.requests[0][1].json, { expectedVersion: 1, expectedSourceVersion: sourceVersion })
})

test('rejects malformed responses, unsafe queries, and changed command shapes', async () => {
  await assert.rejects(readPersonalShiftSwaps(client({ data: [{ ...swap, salary: '10000.00' }], page: { limit: 100, nextCursor: null, hasMore: false } })), /invalid shift swap response/i)
  await assert.rejects(readPersonalShiftSwaps(client({ data: [], page: { limit: 100, nextCursor: null, hasMore: false } }), { status: 'unsafe' }), /invalid shift swap query/i)
  await assert.rejects(submitShiftSwap(client({ data: swap }), { requesterDate: swap.requesterDate, targetEmployeeId: targetId, targetDate: swap.requesterDate, reason: swap.reason, expectedSourceVersion: sourceVersion }, { idempotencyKey: key }), /invalid shift swap request/i)
  await assert.rejects(approveShiftSwap(client({ data: swap }), branchId, { ...swap, expectedSourceVersion: 'changed' }, { idempotencyKey: key }), /invalid shift swap approval/i)
})
