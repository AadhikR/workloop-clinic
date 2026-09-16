import assert from 'node:assert/strict'
import test from 'node:test'

import {
  adminApproveExpense,
  createExpense,
  managerRejectExpense,
  parseExpense,
  readAdminExpenses,
  readManagerExpenses,
  readSelfExpenses,
} from '../migration/src/expenseApi.js'

const branchId = '91000000-0000-4000-8000-000000000001'
const claimId = '91000000-0000-4000-8000-000000000002'
const employeeId = '91000000-0000-4000-8000-000000000003'

const selfClaim = {
  id: claimId,
  category: 'Travel',
  amount: '350.00',
  expenseDate: '2026-08-10',
  description: 'Synthetic airport transfer',
  status: 'pending',
  rejectionReason: null,
  hasReceipt: true,
  payrollPeriod: null,
  createdAt: '2026-09-16T12:00:00.000Z',
  updatedAt: '2026-09-16T12:00:00.000Z',
}
const queueClaim = {
  ...selfClaim,
  employeeId,
  employeeName: 'Synthetic Employee',
  managerDecisionAt: null,
  adminDecisionAt: null,
  canDecide: true,
  managerActorName: null,
  adminActorName: null,
}

function client(data = [selfClaim]) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      if (Array.isArray(data)) {
        return { data, page: { limit: 50, nextCursor: null, hasMore: false } }
      }
      return { data, page: null }
    },
  }
}

test('expense projections reject omitted, extra, or unsafe fields', () => {
  assert.deepEqual(parseExpense(selfClaim), selfClaim)
  assert.throws(() => parseExpense({ ...selfClaim, objectKey: 'private/key' }), /Invalid expense/)
  assert.throws(() => parseExpense({ ...selfClaim, amount: 350 }), /Invalid expense/)
  assert.throws(() => parseExpense({ ...selfClaim, updatedAt: undefined }), /Invalid expense/)
})

test('employee, manager, and administrator reads use separate scoped routes', async () => {
  const self = client([selfClaim])
  const manager = client([queueClaim])
  const admin = client([queueClaim])
  await readSelfExpenses(self, { status: 'pending' })
  await readManagerExpenses(manager)
  await readAdminExpenses(admin, branchId, { employeeId })
  assert.equal(self.calls[0].path, '/api/v1/expenses/self?status=pending')
  assert.equal(manager.calls[0].path, '/api/v1/expenses/manager-queue')
  assert.equal(admin.calls[0].path, `/api/v1/expenses?employeeId=${employeeId}`)
  assert.deepEqual(admin.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
})

test('expense commands send strict bodies, versions, idempotency, and selected branch', async () => {
  const create = client(selfClaim)
  await createExpense(create, {
    category: 'Travel', amount: '350.00', expenseDate: '2026-08-10',
    description: 'Synthetic airport transfer', receiptId: null,
  })
  assert.equal(create.calls[0].path, '/api/v1/expenses/self')
  assert.match(create.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)

  const manager = client(queueClaim)
  await managerRejectExpense(manager, queueClaim, 'Outside policy')
  assert.deepEqual(manager.calls[0].options.json, {
    expectedUpdatedAt: queueClaim.updatedAt,
    reason: 'Outside policy',
  })

  const admin = client({ ...queueClaim, status: 'approved', canDecide: false })
  await adminApproveExpense(admin, branchId, queueClaim)
  assert.equal(admin.calls[0].options.headers['X-Workloop-Branch-ID'], branchId)
})
