import assert from 'node:assert/strict'
import test from 'node:test'

import { parseAttendanceCsv } from '../migration/src/attendanceCsv.js'
import {
  createManualClockEvent,
  importBiometricCandidates,
  readBiometricMappings,
  readClockEvents,
  replaceBiometricMapping,
} from '../migration/src/attendanceIngestionApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const employeeId = '40000000-0000-4000-8000-000000000001'
const eventId = '50000000-0000-4000-8000-000000000001'
const mappingId = '70000000-0000-4000-8000-000000000001'
const batchId = '60000000-0000-4000-8000-000000000001'
const key = '80000000-0000-4000-8000-000000000001'
const now = '2026-08-27T08:00:00.000Z'
const event = { id: eventId, employeeId, eventType: 'CLOCK_IN', eventTime: now, method: 'MANUAL', notes: 'Reception correction', createdAt: now }
const mapping = { id: mappingId, badgeNo: 'A-1', employeeId, deviceName: 'Front door', createdAt: now }
const page = { limit: 100, nextCursor: null, hasMore: false }

function client(response) {
  const requests = []
  return { requests, async request(path, options) { requests.push([path, options]); return response } }
}

test('validates exact event and mapping projections', async () => {
  const eventClient = client({ data: [event], page })
  assert.deepEqual(await readClockEvents(eventClient, branchId, { limit: 100 }), { data: [event], page })
  const webEvent = { ...event, method: 'WEB' }
  assert.deepEqual(await readClockEvents(client({ data: [webEvent], page }), branchId), { data: [webEvent], page })
  assert.equal(eventClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)
  await assert.rejects(readClockEvents(client({ data: [{ ...event, eventFingerprint: 'secret' }], page }), branchId), /invalid attendance ingestion response/i)
  assert.deepEqual(await readBiometricMappings(client({ data: [mapping], page }), branchId), { data: [mapping], page })
})

test('sends manual, mapping, and import mutations with exact camelCase bodies', async () => {
  const manualClient = client({ data: event })
  await createManualClockEvent(manualClient, branchId, { employeeId, eventType: 'CLOCK_IN', eventTime: now, note: 'Reception correction' }, { idempotencyKey: key })
  assert.deepEqual(manualClient.requests[0][1].json, { employeeId, eventType: 'CLOCK_IN', eventTime: now, note: 'Reception correction' })
  assert.equal(manualClient.requests[0][1].headers['Idempotency-Key'], key)

  const mappingClient = client({ data: mapping })
  await replaceBiometricMapping(mappingClient, branchId, ' A-1 ', { employeeId, deviceName: 'Front door' }, { idempotencyKey: key })
  assert.match(mappingClient.requests[0][0], /A-1$/)
  assert.deepEqual(mappingClient.requests[0][1].json, { employeeId, deviceName: 'Front door' })

  const imported = { id: batchId, acceptedCount: 1, duplicateCount: 0, rejectedCount: 0, outcomes: [{ rowNumber: 1, outcome: 'accepted', reasonCode: null, clockEventId: eventId }] }
  const importClient = client({ data: imported })
  assert.deepEqual(await importBiometricCandidates(importClient, branchId, { sourceBytes: 60, candidates: [{ badgeNo: 'A-1', eventType: 'CLOCK_IN', eventTime: now, deviceName: 'Front door' }] }, { idempotencyKey: key }), imported)
  assert.equal(importClient.requests[0][1].json.sourceBytes, 60)
})

test('parses bounded normalized CSV and rejects unsafe input', () => {
  const parsed = parseAttendanceCsv('badgeNo,eventType,eventTime,deviceName\nA-1,CLOCK_IN,2026-08-27T08:00:00+04:00,Front door\n')
  assert.equal(parsed.candidates.length, 1)
  assert.equal(parsed.preview.length, 1)
  assert.equal(parsed.candidates[0].deviceName, 'Front door')
  assert.throws(() => parseAttendanceCsv('badgeNo,eventType,eventTime\n=A1,CLOCK_IN,2026-08-27T08:00:00+04:00\n'), /row 2 is invalid/i)
  assert.throws(() => parseAttendanceCsv('badgeNo,eventType,eventTime,extra\nA1,CLOCK_IN,2026-08-27T08:00:00+04:00,x\n'), /headers/i)
  const rows = Array.from({ length: 5_001 }, (_, index) => `A${index},CLOCK_IN,2026-08-27T08:00:00+04:00`).join('\n')
  assert.throws(() => parseAttendanceCsv(`badgeNo,eventType,eventTime\n${rows}`), /5,000/)
})
