import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createPayrollRun,
  deletePayrollRun,
  parsePayrollRun,
  payrollPreview,
  readPayrollRuns,
  refreshPayrollRun,
  savePayrollEntries,
} from '../migration/src/payrollApi.js'

const branchId = '91000000-0000-4000-8000-000000000001'
const runId = '91000000-0000-4000-8000-000000000002'
const entryId = '91000000-0000-4000-8000-000000000003'
const employeeId = '91000000-0000-4000-8000-000000000004'
const now = '2026-09-17T10:00:00.000Z'

const entry = {
  id: entryId,
  employeeId,
  employeeName: 'Synthetic Employee',
  basicSalary: '10000.00',
  housingAllowance: '0.00',
  transportAllowance: '0.00',
  fixedAllowance: '0.00',
  increment: '0.00',
  bonus: '0.00',
  otherPay: '0.00',
  variableAllowance: '0.00',
  leaveDeduction: '0.00',
  fixedPay: '10000.00',
  grossPay: '10000.00',
  totalDeductions: '0.00',
  netPay: '10000.00',
  wpsBasicPay: '10000.00',
  wpsVariablePay: '0.00',
  excluded: false,
  additionalAllowances: [],
  deductions: [],
  sourceExplanations: [],
  sourceFingerprint: 'a'.repeat(64),
}
const run = {
  id: runId,
  period: '2026-09',
  paymentDate: '2026-09-25',
  sequence: '0001',
  runStatus: 'draft',
  approvalStatus: 'draft',
  employeeCount: 1,
  totalAmount: '10000.00',
  validationStatus: 'valid',
  blockingErrors: [],
  sourceWarnings: [],
  createdAt: now,
  updatedAt: now,
}
const detail = { ...run, entries: [entry] }

function client(data = detail) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      if (Array.isArray(data)) return { data, page: { limit: 50, nextCursor: null, hasMore: false } }
      if (path === `/api/v1/payroll-runs/${runId}` && options.method === 'DELETE') {
        return { data: { id: runId, deleted: true }, page: null }
      }
      return { data, page: null }
    },
  }
}

test('payroll projections reject omitted, extra, numeric-money, and sensitive fields', () => {
  assert.deepEqual(parsePayrollRun(run), run)
  assert.deepEqual(parsePayrollRun(detail, true), detail)
  assert.throws(() => parsePayrollRun({ ...run, totalAmount: 10000 }), /Invalid payroll/)
  assert.throws(() => parsePayrollRun({ ...run, actorAppUserId: employeeId }), /Invalid payroll/)
  assert.throws(() => parsePayrollRun({ ...detail, entries: [{ ...entry, iban: 'unsafe' }] }, true), /Invalid payroll/)
})

test('payroll lists bind the selected branch and use bounded filters', async () => {
  const api = client([run])
  await readPayrollRuns(api, branchId, { period: '2026-09', status: 'draft' })
  assert.equal(api.calls[0].path, '/api/v1/payroll-runs?period=2026-09&status=draft')
  assert.deepEqual(api.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
  await assert.rejects(() => readPayrollRuns(client([]), branchId, { limit: 101 }), /Invalid payroll query/)
})

test('payroll commands send idempotency, selected branch, and optimistic timestamps', async () => {
  const create = client()
  await createPayrollRun(create, branchId, { period: '2026-09', paymentDate: '2026-09-25' })
  assert.match(create.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)
  assert.equal(create.calls[0].options.headers['X-Workloop-Branch-ID'], branchId)

  const refresh = client()
  await refreshPayrollRun(refresh, branchId, detail)
  assert.deepEqual(refresh.calls[0].options.json, { expectedUpdatedAt: now })

  const save = client()
  const automatic = {
    id: runId,
    code: 'EXPENSE_91000000000040008000000000000002',
    label: 'Expense reimbursement',
    amount: '350.00',
    recurrence: 'one_time',
    note: null,
  }
  const entryWithAutomaticInput = {
    ...entry,
    additionalAllowances: [automatic],
    grossPay: '10350.00',
    netPay: '10350.00',
    wpsVariablePay: '350.00',
  }
  await savePayrollEntries(save, branchId, detail, [entryWithAutomaticInput])
  assert.equal(save.calls[0].options.json.expectedUpdatedAt, now)
  assert.deepEqual(save.calls[0].options.json.entries[0].preview, payrollPreview(entryWithAutomaticInput))
  assert.deepEqual(save.calls[0].options.json.entries[0].additionalAllowances, [])

  const remove = client()
  await deletePayrollRun(remove, branchId, detail)
  assert.deepEqual(remove.calls[0].options.json, { expectedUpdatedAt: now })
})

test('browser payroll arithmetic is a preview with exact fixed-decimal output', () => {
  const calculated = payrollPreview({
    ...entry,
    additionalAllowances: [
      { id: entryId, code: 'SHIFT', label: 'Shift', amount: '250.25', recurrence: 'recurring', note: null },
      { id: runId, code: 'PROJECT', label: 'Project', amount: '499.75', recurrence: 'one_time', note: null },
    ],
    deductions: [
      { id: branchId, code: 'PARKING', label: 'Parking', amount: '100.00', recurrence: 'recurring', note: null },
      { id: employeeId, code: 'EQUIPMENT', label: 'Equipment', amount: '50.00', recurrence: 'one_time', note: null },
    ],
  })
  assert.equal(calculated.grossPay, '10750.00')
  assert.equal(calculated.totalDeductions, '150.00')
  assert.equal(calculated.netPay, '10600.00')
})
