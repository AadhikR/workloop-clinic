import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  calculateAttendance,
  calculateAttendanceBatch,
  readAttendanceRecords,
  readPersonalAttendance,
  readPersonalAttendanceHistory,
} from '../migration/src/attendanceCalculationApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const employeeId = '40000000-0000-4000-8000-000000000001'
const recordId = '50000000-0000-4000-8000-000000000001'
const key = '70000000-0000-4000-8000-000000000001'
const now = '2026-08-27T08:00:00.000Z'
const record = { id: recordId, employeeId, date: '2026-08-27', shiftId: null, clockInTime: now, clockOutTime: now, totalHours: '8.00', expectedHours: '8.00', status: 'PRESENT', lateMinutes: 0, earlyDepartureMinutes: 0, overtimeHours: '0.00', overtimeType: null, overtimeAmount: '0.00', absenceDeduction: '0.00', lateDeduction: '0.00', workedOnRestDay: false, restDaySubstitute: false, missingClockOut: false, isRamadanDay: false, periodClosed: false, evidenceFlags: [], sourceDigest: 'a'.repeat(64), sourceStale: false, calculationVersion: 1, updatedAt: now }
const page = { limit: 20, nextCursor: null, hasMore: false }
const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('validates administrator attendance records and calculation body', async () => {
  assert.deepEqual(await readAttendanceRecords(client({ data: [record], page }), branchId, { limit: 20 }), { data: [record], page })
  const calculationClient = client({ data: record })
  await calculateAttendance(calculationClient, branchId, { employeeId, attendanceDate: '2026-08-27', expectedSourceDigest: record.sourceDigest, expectedCalculationVersion: record.calculationVersion }, { idempotencyKey: key })
  assert.deepEqual(calculationClient.requests[0][1].json, { employeeId, attendanceDate: '2026-08-27', expectedSourceDigest: record.sourceDigest, expectedCalculationVersion: record.calculationVersion })
  assert.equal(calculationClient.requests[0][1].headers['Idempotency-Key'], key)
  const batchClient = client({ data: [record] })
  assert.deepEqual(await calculateAttendanceBatch(batchClient, branchId, [{ employeeId, attendanceDate: '2026-08-27' }], { idempotencyKey: key }), [record])
  assert.equal(batchClient.requests[0][0], '/api/v1/attendance/calculations/batch')
})

test('validates self-only today and history responses', async () => {
  const today = { record, rawEventFallback: 'none', rawEvents: [] }
  assert.deepEqual(await readPersonalAttendance(client({ data: today })), today)
  assert.deepEqual(await readPersonalAttendanceHistory(client({ data: [record], page }), { limit: 20 }), { data: [record], page })
})

test('rejects unexpected calculated-record response fields', async () => {
  await assert.rejects(readAttendanceRecords(client({ data: [{ ...record, internalSnapshot: {} }], page }), branchId), /invalid attendance calculation response/i)
})

test('routes Phase 10D rollback and isolates the historical Phase 10C revision', () => {
  const workflow = readFileSync(path.join(repositoryDirectory, '.github', 'workflows', 'migration-foundation.yml'), 'utf8')
  const phase10c = readFileSync(path.join(repositoryDirectory, 'scripts', 'verify-phase-10c-revision.sh'), 'utf8')
  const phase10d = readFileSync(path.join(repositoryDirectory, 'scripts', 'verify-phase-10d-revision.sh'), 'utf8')
  assert.match(workflow, /sh scripts\/verify-phase-10d-revision\.sh/)
  assert.match(phase10d, /downgrade b7d9e1f3a5c6/)
  assert.match(phase10c, /downgrade b7d9e1f3a5c6/)
  assert.match(phase10c, /upgrade b7d9e1f3a5c6/)
})
