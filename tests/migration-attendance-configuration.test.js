import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assignShift,
  createShift,
  deactivateShift,
  readAttendanceSettings,
  readShiftAssignments,
  readShifts,
  updateAttendanceSettings,
  updateShift,
} from '../src/attendanceConfigurationApi.js'

const branchId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const employeeId = '21000000-0000-4000-8000-000000000002'
const shiftId = '31000000-0000-4000-8000-000000000001'
const assignmentId = '32000000-0000-4000-8000-000000000001'
const key = '7e000000-0000-4000-8000-000000000001'
const now = '2026-09-18T08:00:00.000Z'
const settings = {
  id: '33000000-0000-4000-8000-000000000001',
  workingDays: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu'], weekendDays: ['Fri', 'Sat'],
  defaultHoursPerDay: '8.00', lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10,
  overtimeRequiresApproval: true, maxDailyOvertimeHours: '2.00',
  lateDeductionPolicy: 'none', lateDeductionAmount: '0.00', wfhEnabled: false,
  regularisationMaxDaysPerMonth: 2, regularisationWindowDays: 7,
  biometricApiEnabled: false, biometricApiKeyConfigured: false,
  createdAt: now, updatedAt: now,
}
const shift = {
  id: shiftId, name: 'Morning', code: 'M', shiftType: 'fixed', shiftCategory: 'morning',
  startTime: '08:00:00', endTime: '17:00:00', splitStartTime: null, splitEndTime: null,
  breakMinutes: 60, expectedHours: '8.00', lateGraceMinutes: 10,
  earlyDepartureGraceMinutes: 10, isOvernight: false, minHoursFlexible: null,
  isActive: true, color: '#6366F1', minStaff: 1, createdAt: now, updatedAt: now,
}
const assignment = {
  id: assignmentId, employeeId, shiftId, effectiveFrom: '2026-09-20', effectiveTo: null,
  createdAt: now, updatedAt: now,
}

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('parses exact redacted settings and shift projections', async () => {
  const settingsClient = client({ data: settings })
  assert.deepEqual(await readAttendanceSettings(settingsClient, branchId), settings)
  assert.equal(settingsClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)
  await assert.rejects(
    readAttendanceSettings(client({ data: { ...settings, biometricApiKey: 'secret' } }), branchId),
    /invalid attendance configuration response/i,
  )
  assert.deepEqual(await readShifts(client({ data: [shift], page: { limit: 50, nextCursor: null, hasMore: false } }), branchId), { data: [shift], page: { limit: 50, nextCursor: null, hasMore: false } })
})

test('sends guarded settings, shift, deactivation, and assignment mutations', async () => {
  const settingsClient = client({ data: { ...settings, wfhEnabled: true }, replayed: false })
  await updateAttendanceSettings(settingsClient, branchId, { ...settings, wfhEnabled: true, biometricApiKey: null }, { idempotencyKey: key })
  assert.equal(settingsClient.requests[0][1].method, 'PUT')
  assert.equal(settingsClient.requests[0][1].headers['Idempotency-Key'], key)
  assert.equal(settingsClient.requests[0][1].json.expectedUpdatedAt, now)

  const createClient = client({ data: shift, status: 201, location: `/api/v1/shifts/${shiftId}` })
  await createShift(createClient, branchId, { ...shift, id: undefined, createdAt: undefined, updatedAt: undefined }, { idempotencyKey: key })
  assert.equal(createClient.requests[0][1].method, 'POST')

  const updateClient = client({ data: { ...shift, color: '#112233' } })
  await updateShift(updateClient, branchId, shift, { color: '#112233' }, { idempotencyKey: key })
  assert.equal(updateClient.requests[0][1].json.expectedUpdatedAt, now)

  const deactivateClient = client({ data: { ...shift, isActive: false }, replayed: false })
  await deactivateShift(deactivateClient, branchId, shift, { idempotencyKey: key })
  assert.equal(deactivateClient.requests[0][1].json.expectedUpdatedAt, now)

  const assignmentClient = client({ data: assignment, status: 201, location: `/api/v1/shift-assignments/${assignmentId}` })
  await assignShift(assignmentClient, branchId, { employeeId, shiftId, effectiveFrom: '2026-09-20', expectedCurrentAssignmentId: null, expectedCurrentAssignmentUpdatedAt: null }, { idempotencyKey: key })
  assert.equal(assignmentClient.requests[0][1].method, 'POST')
})

test('validates assignment filters and exact responses before accepting data', async () => {
  const response = { data: [assignment], page: { limit: 50, nextCursor: null, hasMore: false } }
  const assignmentClient = client(response)
  assert.deepEqual(await readShiftAssignments(assignmentClient, branchId, { employeeId }), response)
  assert.match(assignmentClient.requests[0][0], /employeeId=/)
  await assert.rejects(readShiftAssignments(client(response), branchId, {}), /invalid assignment query/i)
  await assert.rejects(readShiftAssignments(client({ ...response, data: [{ ...assignment, companyId: branchId }] }), branchId, { employeeId }), /invalid attendance configuration response/i)
})
