import assert from 'node:assert/strict'
import test from 'node:test'

import {
  closeAttendancePeriod,
  readAttendancePeriod,
  readAttendancePeriods,
} from '../migration/src/attendancePeriodsApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const periodId = '40000000-0000-4000-8000-000000000001'
const key = '50000000-0000-4000-8000-000000000001'
const closed = {
  id: periodId,
  period: '2026-08',
  status: 'closed',
  payrollReady: true,
  version: 1,
  blockerCount: 0,
  blockers: [],
  sourceVersion: `sha256:${'a'.repeat(64)}`,
  closedAt: '2026-09-21T20:00:00.000Z',
  closedByActorName: 'Administrator',
  amendmentReason: null,
}
const open = {
  ...closed,
  status: 'open',
  payrollReady: false,
  version: 0,
  blockerCount: 2,
  blockers: [{ code: 'missing_calculation_days', count: 2 }],
  sourceVersion: null,
  closedAt: null,
  closedByActorName: null,
}
const page = { limit: 20, nextCursor: null, hasMore: false }

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('reads strict selected-branch period readiness and detail', async () => {
  const listClient = client({ data: [open, closed], page })
  assert.deepEqual(await readAttendancePeriods(listClient, branchId, { limit: 20 }), { data: [open, closed], page })
  assert.equal(listClient.requests[0][0], '/api/v1/attendance/periods?limit=20')
  assert.equal(listClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)

  const detailClient = client({ data: closed })
  assert.equal((await readAttendancePeriod(detailClient, branchId, '2026-08')).sourceVersion, closed.sourceVersion)
})

test('closes and amends only with exact versioned idempotent bodies', async () => {
  const closeClient = client({ data: closed })
  await closeAttendancePeriod(closeClient, branchId, '2026-08', { expectedVersion: 0 }, { idempotencyKey: key })
  assert.deepEqual(closeClient.requests[0][1].json, { expectedVersion: 0, amendmentReason: null })
  assert.equal(closeClient.requests[0][1].headers['Idempotency-Key'], key)

  const amended = { ...closed, version: 2, amendmentReason: 'Approved late evidence', sourceVersion: `sha256:${'b'.repeat(64)}` }
  const amendmentClient = client({ data: amended })
  await closeAttendancePeriod(amendmentClient, branchId, '2026-08', { expectedVersion: 1, amendmentReason: '  Approved late evidence  ' }, { idempotencyKey: key })
  assert.deepEqual(amendmentClient.requests[0][1].json, { expectedVersion: 1, amendmentReason: 'Approved late evidence' })
})

test('rejects malformed periods, inconsistent blockers, and unsafe response fields', async () => {
  await assert.rejects(readAttendancePeriod(client({ data: closed }), branchId, '2026-8'), /invalid attendance period/i)
  await assert.rejects(readAttendancePeriods(client({ data: [{ ...open, blockerCount: 1 }], page }), branchId), /invalid attendance period response/i)
  await assert.rejects(readAttendancePeriod(client({ data: { ...closed, actorId: periodId } }), branchId, '2026-08'), /invalid attendance period response/i)
  await assert.rejects(closeAttendancePeriod(client({ data: closed }), branchId, '2026-08', { expectedVersion: 1 }, { idempotencyKey: key }), /invalid attendance period close/i)
})
