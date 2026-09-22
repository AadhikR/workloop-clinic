import assert from 'node:assert/strict'
import test from 'node:test'

import {
  approveRosterOvertime,
  createRosterDraft,
  createRosterOverride,
  deleteRosterDraft,
  publishRosterMonth,
  readAllRosterMonth,
  readPersonalSchedule,
  readRosterColleagues,
  readRosterMonth,
  readRosterPublication,
  readRosterValidation,
  recordRosterActualHours,
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
const sourceVersion = `sha256:${'c'.repeat(64)}`
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

function sequenceClient(responses) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return responses.shift() } }
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

test('reads every roster page before exact publication', async () => {
  const next = 'next-page'
  const pagedClient = sequenceClient([
    { data: [assignment], page: { limit: 100, nextCursor: next, hasMore: true } },
    { data: [{ ...assignment, id: overrideId }], page: { limit: 100, nextCursor: null, hasMore: false } },
  ])
  const result = await readAllRosterMonth(pagedClient, branchId, '2026-09')
  assert.deepEqual(result.map((item) => item.id), [assignmentId, overrideId])
  assert.equal(pagedClient.requests[0][0], '/api/v1/roster/months/2026-09?limit=100')
  assert.equal(pagedClient.requests[1][0], '/api/v1/roster/months/2026-09?limit=100&cursor=next-page')
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

test('publishes an exact version and records actual-hours and overtime evidence', async () => {
  const draftPublication = {
    id: null, period: '2026-09', status: 'draft', version: 0,
    currentVersionId: null, sourceVersion: null, publishedAt: null,
    publishedByAppUserId: null, recordCount: 0,
  }
  assert.equal((await readRosterPublication(client({ data: draftPublication }), branchId, '2026-09')).id, null)

  const publication = {
    id: overrideId, period: '2026-09', status: 'published', version: 3,
    currentVersionId: ruleId, sourceVersion, publishedAt: '2026-09-22T02:00:00.000Z',
    publishedByAppUserId: employeeId, recordCount: 1,
  }
  assert.equal((await readRosterPublication(client({ data: publication }), branchId, '2026-09')).sourceVersion, sourceVersion)

  const publishClient = client({ data: publication })
  await publishRosterMonth(publishClient, branchId, '2026-09', [assignment], null, { idempotencyKey: key })
  assert.deepEqual(publishClient.requests[0][1].json, { assignments: [{ id: assignmentId, expectedVersion: 1 }], expectedSourceVersion: null })

  const actualClient = client({ data: publication })
  await recordRosterActualHours(actualClient, branchId, '2026-09', assignmentId, '12.00', 'timesheet', ' Confirmed timesheet ', sourceVersion, { idempotencyKey: key })
  assert.deepEqual(actualClient.requests[0][1].json, { actualHours: '12.00', evidenceSource: 'timesheet', reason: 'Confirmed timesheet', expectedSourceVersion: sourceVersion })

  const overtimeClient = client({ data: publication })
  await approveRosterOvertime(overtimeClient, branchId, '2026-09', assignmentId, ' Approved overtime ', sourceVersion, [], { idempotencyKey: key })
  assert.deepEqual(overtimeClient.requests[0][1].json, { reason: 'Approved overtime', expectedSourceVersion: sourceVersion, attendanceSourceIds: [] })
})

test('reads only strict personal schedule and safe colleague fields', async () => {
  const schedule = {
    rosterAssignmentId: assignmentId, employeeId, employeeName: 'Synthetic Employee',
    department: 'Clinical', shiftId, shiftName: 'Morning', shiftCode: 'M',
    shiftCategory: 'morning', date: '2026-09-23', plannedHours: '8.00',
    actualHours: '12.00', overtimeHours: '4.00', notes: '', sourceVersion,
    publicationVersion: 3, publishedAt: '2026-09-22T02:00:00.000Z',
  }
  const scheduleClient = client({ data: [schedule], page: { limit: 1, nextCursor: null, hasMore: false } })
  assert.equal((await readPersonalSchedule(scheduleClient, '2026-09'))[0].employeeId, employeeId)
  assert.deepEqual(scheduleClient.requests[0][1], { access: 'protected' })

  const colleague = { employeeId, employeeName: 'Synthetic Employee', rosterAssignmentId: assignmentId, shiftId, shiftName: 'Morning', shiftCode: 'M', shiftCategory: 'morning', date: '2026-09-23' }
  const colleagueClient = client({ data: [colleague], page: { limit: 1, nextCursor: null, hasMore: false } })
  assert.equal((await readRosterColleagues(colleagueClient, '2026-09-23'))[0].employeeName, 'Synthetic Employee')
  await assert.rejects(readPersonalSchedule(client({ data: [{ ...schedule, salary: '12000.00' }], page }), '2026-09'), /invalid roster response/i)
})
