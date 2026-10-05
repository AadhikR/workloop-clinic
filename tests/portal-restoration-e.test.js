import test from 'node:test'
import assert from 'node:assert/strict'
import { completeOwnTraining, transitionTraining, parseTraining } from '../src/developmentAssetsApi.js'

const id = 'e5000000-0000-4000-8000-000000000030'
const record = { id, updatedAt: '2026-10-05T08:00:00.000Z' }

test('personal training results omit employee, verification, cost, and CME authority', async () => {
  const calls = []
  const authentication = { request: async (path, options) => { calls.push({ path, options }); return { data: training() } } }
  await completeOwnTraining(authentication, record, { endDate: '2026-10-05', durationHours: '8.00', score: '92%', passed: true, isCme: true, employeeId: id, resultVerified: true })
  assert.equal(calls[0].path, `/api/v1/training-records/${id}/self-complete`)
  assert.deepEqual(calls[0].options.json, { endDate: '2026-10-05', durationHours: '8.00', score: '92%', passed: true, expectedUpdatedAt: record.updatedAt })
  assert.equal(Object.hasOwn(calls[0].options.headers, 'X-Workloop-Branch-ID'), false)
  assert.match(calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
})

test('training transitions are named, versioned commands', async () => {
  const calls = []
  const authentication = { request: async (path, options) => { calls.push({ path, options }); return { data: training() } } }
  for (const command of ['start', 'cancel']) await transitionTraining(authentication, null, record, command)
  assert.deepEqual(calls.map((call) => call.path), [`/api/v1/training-records/${id}/start`, `/api/v1/training-records/${id}/cancel`])
  assert.deepEqual(calls[0].options.json, { expectedUpdatedAt: record.updatedAt })
  await assert.rejects(() => transitionTraining(authentication, null, record, 'verify'), /Invalid training transition/)
})

function training() {
  return { id, employeeId: id, trainingTitle: 'Emergency response', trainingType: 'external', provider: 'Synthetic centre', startDate: '2026-10-01', endDate: '2026-10-05', durationHours: '8.00', cost: '0.00', status: 'completed', score: '92%', passed: true, notes: '', isCme: false, resultVerified: false, hasEvidence: false, fileName: null, contentType: null, createdAt: record.updatedAt, updatedAt: record.updatedAt }
}

test('training parser rejects a self result that grants CME credit', () => {
  assert.equal(parseTraining(training()).resultVerified, false)
  assert.throws(() => parseTraining({ ...training(), isCme: true }), /Invalid training response/)
})

test('planned CME training preserves the database provenance constraint', () => {
  for (const status of ['planned', 'in_progress']) {
    assert.equal(parseTraining({ ...training(), status, passed: null, isCme: true, resultVerified: true }).isCme, true)
    assert.throws(() => parseTraining({ ...training(), status, passed: null, isCme: true }), /Invalid training response/)
  }
})
