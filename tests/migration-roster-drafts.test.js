import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createRosterDraft,
  createRosterOverride,
  deleteRosterDraft,
  readRosterMonth,
  readRosterValidation,
  replaceRosterDraft,
} from '../migration/src/rosterApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const employeeId = '30000000-0000-4000-8000-000000000001'
const shiftId = '40000000-0000-4000-8000-000000000001'
const assignmentId = '50000000-0000-4000-8000-000000000001'
const overrideId = '60000000-0000-4000-8000-000000000001'
const ruleId = '70000000-0000-4000-8000-000000000001'
const key = '80000000-0000-4000-8000-000000000001'
const violationDigest = `sha256:${'a'.repeat(64)}`
const assignment = {
  id: assignmentId,
  employeeId,
  employeeName: 'Synthetic Employee',
  department: 'Clinical',
  shiftId,
  shiftName: 'Morning',
  shiftCode: 'M',
  shiftCategory: 'morning',
  date: '2026-09-23',
  published: false,
  plannedHours: '8.00',
  notes: '',
  version: 1,
  leaveConflict: false,
  updatedAt: '2026-09-22T02:00:00.000Z',
}
const violation = {
  code: 'staffing_shortfall', department: 'Clinical', date: '2026-09-23',
  shiftCategory: 'morning', required: 2, assigned: 1, deficit: 1, ruleId,
  violationDigest, overridden: false,
}
const page = { limit: 20, nextCursor: null, hasMore: false }

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('reads strict selected-branch roster drafts and publication gates', async () => {
  const monthClient = client({ data: [assignment], page })
  const month = await readRosterMonth(monthClient, branchId, '2026-09', { department: 'Clinical', employeeId, limit: 20 })
  assert.equal(month.data[0].plannedHours, '8.00')
  assert.equal(monthClient.requests[0][0], `/api/v1/roster/months/2026-09?department=Clinical&employeeId=${employeeId}&limit=20`)
  assert.equal(monthClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)

  const validation = await readRosterValidation(client({ data: { period: '2026-09', staffingEnforced: true, leaveConflicts: [], staffingViolations: [violation], ready: false } }), branchId, '2026-09')
  assert.equal(validation.staffingViolations[0].violationDigest, violationDigest)

  const leaveConflict = {
    rosterAssignmentId: assignmentId, employeeId, employeeName: 'Synthetic Employee',
    date: '2026-09-23', leaveRequestId: overrideId, leaveStatus: 'ManagerApproved',
    violationDigest: `sha256:${'b'.repeat(64)}`, overridden: true,
  }
  const leaveValidation = await readRosterValidation(client({ data: { period: '2026-09', staffingEnforced: false, leaveConflicts: [leaveConflict], staffingViolations: null, ready: true } }), branchId, '2026-09')
  assert.equal(leaveValidation.leaveConflicts[0].overridden, true)
})

test('creates, replaces, and deletes drafts with exact idempotent bodies', async () => {
  const values = { employeeId, shiftId, date: '2026-09-23', plannedHours: '8.00', notes: ' coverage ' }
  const createClient = client({ data: assignment })
  await createRosterDraft(createClient, branchId, '2026-09', values, { idempotencyKey: key })
  assert.deepEqual(createClient.requests[0][1].json, { ...values, notes: 'coverage' })
  assert.equal(createClient.requests[0][1].headers['Idempotency-Key'], key)

  const replaceClient = client({ data: { ...assignment, version: 2 } })
  await replaceRosterDraft(replaceClient, branchId, '2026-09', assignmentId, { ...values, expectedVersion: 1 }, { idempotencyKey: key })
  assert.equal(replaceClient.requests[0][1].method, 'PUT')
  assert.equal(replaceClient.requests[0][1].json.expectedVersion, 1)

  const deleteClient = client(undefined)
  await deleteRosterDraft(deleteClient, branchId, '2026-09', assignment, { idempotencyKey: key })
  assert.deepEqual(deleteClient.requests[0][1].json, { expectedVersion: 1 })
})

test('records only a strict immutable staffing override response', async () => {
  const violationSnapshot = {
    code: 'staffing_shortfall', period: '2026-09', branchId, ruleId,
    department: 'Clinical', date: '2026-09-23', shiftCategory: 'morning',
    required: 2, assigned: 1, deficit: 1,
  }
  const response = { id: overrideId, period: '2026-09', ruleCode: 'staffing_shortfall', violationDigest, violationSnapshot, reason: 'Approved synthetic exception', createdAt: '2026-09-22T02:00:00.000Z' }
  const overrideClient = client({ data: response })
  assert.equal((await createRosterOverride(overrideClient, branchId, '2026-09', violationDigest, '  Approved synthetic exception  ', { idempotencyKey: key })).id, overrideId)
  assert.deepEqual(overrideClient.requests[0][1].json, { violationDigest, reason: 'Approved synthetic exception' })
  await assert.rejects(createRosterOverride(client({ data: { ...response, actorId: employeeId } }), branchId, '2026-09', violationDigest, response.reason, { idempotencyKey: key }), /invalid roster response/i)
})

test('rejects malformed queries, hours, readiness, and violation arithmetic', async () => {
  await assert.rejects(readRosterMonth(client({ data: [], page }), branchId, '2026-09', { employeeId: 'unsafe' }), /invalid roster query/i)
  await assert.rejects(createRosterDraft(client({ data: assignment }), branchId, '2026-09', { employeeId, shiftId, date: '2026-09-23', plannedHours: '0.10' }, { idempotencyKey: key }), /invalid roster draft/i)
  await assert.rejects(readRosterValidation(client({ data: { period: '2026-09', staffingEnforced: true, leaveConflicts: [], staffingViolations: [{ ...violation, deficit: 2 }], ready: false } }), branchId, '2026-09'), /invalid roster response/i)
  await assert.rejects(readRosterValidation(client({ data: { period: '2026-09', staffingEnforced: false, leaveConflicts: [], staffingViolations: null, ready: false } }), branchId, '2026-09'), /invalid roster response/i)
})
