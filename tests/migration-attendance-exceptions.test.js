import assert from 'node:assert/strict'
import test from 'node:test'

import {
  approveOvertime,
  decideRegularisation,
  readAttendanceAudit,
  readPersonalRegularisations,
  readRegularisationQueue,
  resolveAbsence,
  submitRegularisation,
} from '../migration/src/attendanceExceptionsApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const employeeId = '40000000-0000-4000-8000-000000000001'
const requestId = '50000000-0000-4000-8000-000000000001'
const recordId = '60000000-0000-4000-8000-000000000001'
const auditId = '70000000-0000-4000-8000-000000000001'
const key = '80000000-0000-4000-8000-000000000001'
const now = '2026-09-21T08:00:00.000Z'
const page = { limit: 20, nextCursor: null, hasMore: false }
const regularisation = { id: requestId, employeeId, attendanceDate: '2026-09-20', correctClockIn: now, correctClockOut: '2026-09-21T16:00:00.000Z', reason: 'Missed biometric punch', status: 'Pending', rejectionReason: null, submittedAt: now, decidedAt: null, version: 1 }
const exceptionRecord = { id: recordId, employeeId, date: '2026-09-20', status: 'OVERTIME', resolutionType: null, absenceDeduction: '0.00', overtimeHours: '2.00', overtimeType: 'STANDARD', overtimeAmount: '120.00', overtimeApproved: true, overtimeApprovedAt: now, overtimeApprovalSourceDigest: 'a'.repeat(64), resolvedAt: null, resolutionSourceDigest: null, calculationVersion: 1 }
const audit = { id: auditId, employeeId, attendanceDate: '2026-09-20', action: 'OVERTIME_APPROVED', occurredAt: now }

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('uses self-only correction history and strict submission bodies', async () => {
  const historyClient = client({ status: 200, data: [regularisation], correlationId: key, location: null, page, replayed: false })
  assert.deepEqual(await readPersonalRegularisations(historyClient, { status: 'Pending', limit: 20 }), { data: [regularisation], page })
  assert.equal(historyClient.requests[0][0], '/api/v1/attendance/regularisations/me?status=Pending&limit=20')

  const submissionClient = client({ status: 201, data: regularisation, correlationId: key, location: `/api/v1/attendance/regularisations/${requestId}`, page: null, replayed: false })
  await submitRegularisation(submissionClient, { attendanceDate: '2026-09-20', correctClockIn: '2026-09-20T08:00:00+04:00', correctClockOut: '2026-09-20T17:00:00+04:00', reason: '  Missed biometric punch  ' }, { idempotencyKey: key })
  assert.deepEqual(submissionClient.requests[0][1].json, { attendanceDate: '2026-09-20', correctClockIn: '2026-09-20T08:00:00+04:00', correctClockOut: '2026-09-20T17:00:00+04:00', reason: 'Missed biometric punch' })
  assert.equal(submissionClient.requests[0][1].headers['Idempotency-Key'], key)
})

test('uses selected-branch queue, decisions, resolutions, overtime, and safe audit', async () => {
  const queueClient = client({ data: [regularisation], page })
  assert.deepEqual(await readRegularisationQueue(queueClient, branchId, { status: 'Pending', limit: 20 }), { data: [regularisation], page })
  assert.equal(queueClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)

  const decisionClient = client({ data: regularisation })
  await decideRegularisation(decisionClient, branchId, requestId, 'approve', 1, null, { idempotencyKey: key })
  assert.deepEqual(decisionClient.requests[0][1].json, { expectedVersion: 1, rejectionReason: null })

  const resolutionClient = client({ data: { ...exceptionRecord, status: 'PRESENT_REMOTE', resolutionType: 'WFH', overtimeApproved: false, overtimeApprovedAt: null, overtimeApprovalSourceDigest: null, resolvedAt: now, resolutionSourceDigest: 'b'.repeat(64) } })
  await resolveAbsence(resolutionClient, branchId, recordId, { expectedCalculationVersion: 1, resolutionType: 'WFH', reason: 'Remote work evidence confirmed' }, { idempotencyKey: key })
  assert.equal(resolutionClient.requests[0][1].json.resolutionType, 'WFH')

  const overtimeClient = client({ data: exceptionRecord })
  assert.equal((await approveOvertime(overtimeClient, branchId, recordId, 1, { idempotencyKey: key })).overtimeApproved, true)

  const auditClient = client({ data: [audit], page })
  assert.deepEqual(await readAttendanceAudit(auditClient, branchId, { action: 'OVERTIME_APPROVED', limit: 20 }), { data: [audit], page })
})

test('rejects unknown response fields and invalid mutation inputs', async () => {
  await assert.rejects(readRegularisationQueue(client({ data: [{ ...regularisation, approvedBy: 'hidden' }], page }), branchId), /invalid attendance exception response/i)
  await assert.rejects(submitRegularisation(client({ data: regularisation }), { attendanceDate: '2026-09-20', correctClockIn: '2026-09-20T17:00:00+04:00', correctClockOut: '2026-09-20T08:00:00+04:00', reason: 'Bad order' }, { idempotencyKey: key }), /invalid attendance correction/i)
  await assert.rejects(resolveAbsence(client({ data: exceptionRecord }), branchId, recordId, { expectedCalculationVersion: 1, resolutionType: 'OTHER', reason: 'Invalid resolution' }, { idempotencyKey: key }), /invalid absence resolution/i)
})
