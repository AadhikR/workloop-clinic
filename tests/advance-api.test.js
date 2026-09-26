import assert from 'node:assert/strict'
import test from 'node:test'

import {
  approveAdvance,
  createSelfAdvance,
  parseAdvance,
  readAdminAdvances,
  readSelfAdvances,
  recordAdvanceRepayment,
  replaceAdvanceSchedule,
  settleAdvance,
  withdrawAdvance,
} from '../src/advanceApi.js'

const branchId = '91000000-0000-4000-8000-000000000001'
const advanceId = '91000000-0000-4000-8000-000000000002'
const employeeId = '91000000-0000-4000-8000-000000000003'
const now = '2026-09-16T12:00:00.000Z'

const selfAdvance = {
  id: advanceId,
  amount: '1000.00',
  reason: 'Synthetic emergency',
  status: 'pending',
  repaymentStartPeriod: '2026-09',
  installmentCount: 3,
  monthlyInstallment: '333.33',
  outstandingBalance: '1000.00',
  nextRepaymentPeriod: '2026-09',
  rejectionReason: null,
  createdAt: now,
  updatedAt: now,
}
const adminAdvance = {
  ...selfAdvance,
  employeeId,
  employeeName: 'Synthetic Employee',
  creatorName: 'Synthetic Creator',
  decisionActorName: null,
  disbursedDate: null,
  canDecide: true,
  schedule: [
    { period: '2026-09', scheduledAmount: '333.33', paidAmount: '0.00', remainingAmount: '333.33', status: 'due' },
    { period: '2026-10', scheduledAmount: '333.33', paidAmount: '0.00', remainingAmount: '333.33', status: 'upcoming' },
    { period: '2026-11', scheduledAmount: '333.34', paidAmount: '0.00', remainingAmount: '333.34', status: 'upcoming' },
  ],
  repayments: [],
}

function client(data = selfAdvance) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return Array.isArray(data)
        ? { data, page: { limit: 50, nextCursor: null, hasMore: false } }
        : { data, page: null }
    },
  }
}

test('salary advance projections reject omitted, extra, numeric-money, and unsafe fields', () => {
  assert.deepEqual(parseAdvance(selfAdvance), selfAdvance)
  assert.deepEqual(parseAdvance(adminAdvance, true), adminAdvance)
  assert.throws(() => parseAdvance({ ...selfAdvance, amount: 1000 }), /Invalid salary advance/)
  assert.throws(() => parseAdvance({ ...selfAdvance, actorAppUserId: employeeId }), /Invalid salary advance/)
  assert.throws(() => parseAdvance({ ...selfAdvance, updatedAt: undefined }), /Invalid salary advance/)
})
test('self and administrator lists use separate bounded scoped routes', async () => {
  const self = client([selfAdvance])
  const admin = client([adminAdvance])
  await readSelfAdvances(self, { status: 'pending' })
  await readAdminAdvances(admin, branchId, { employeeId, repaymentStartPeriod: '2026-09' })
  assert.equal(self.calls[0].path, '/api/v1/advances/self?status=pending')
  assert.equal(admin.calls[0].path, `/api/v1/advances?employeeId=${employeeId}&repaymentStartPeriod=2026-09`)
  assert.deepEqual(admin.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
  await assert.rejects(() => readSelfAdvances(client([]), { limit: 101 }), /Invalid salary advance query/)
})

test('all salary advance commands send versions, idempotency keys, and selected branch', async () => {
  const create = client(selfAdvance)
  await createSelfAdvance(create, {
    amount: '1000.00', reason: 'Synthetic emergency', installmentCount: 3,
    repaymentStartPeriod: '2026-09',
  })
  assert.match(create.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)

  const withdraw = client({ ...selfAdvance, status: 'cancelled', nextRepaymentPeriod: null, rejectionReason: 'Withdrawn by employee' })
  await withdrawAdvance(withdraw, selfAdvance)
  assert.deepEqual(withdraw.calls[0].options.json, { expectedUpdatedAt: now })

  for (const invoke of [
    (api) => approveAdvance(api, branchId, adminAdvance),
    (api) => replaceAdvanceSchedule(api, branchId, adminAdvance, { amount: '1000.00', installmentCount: 3, repaymentStartPeriod: '2026-09' }),
    (api) => recordAdvanceRepayment(api, branchId, adminAdvance, '100.00'),
    (api) => settleAdvance(api, branchId, adminAdvance),
  ]) {
    const api = client(adminAdvance)
    await invoke(api)
    assert.equal(api.calls[0].options.headers['X-Workloop-Branch-ID'], branchId)
    assert.match(api.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
    assert.equal(api.calls[0].options.json.expectedUpdatedAt, now)
  }
})
