import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import {
  initializeLeaveBalances,
  parseLeaveBalance,
  parseLeaveRequest,
  readAdminLeaveBalances,
  readEmployeeLeaveBalances,
  recalculateLeaveBalances,
} from '../src/leaveBalanceApi.js'

const branchId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const employeeId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d1'
const typeId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698e1'
const requestId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698f1'

function balance(changes = {}) {
  return {
    employeeId,
    leaveTypeId: typeId,
    leaveYear: 2026,
    entitledDays: '30.00',
    accruedDays: '22.50',
    usedDays: '3.00',
    pendingDays: '0.50',
    carriedForward: '2.00',
    remainingDays: '21.00',
    sickFullPayUsed: '0.00',
    sickHalfPayUsed: '0.00',
    sickUnpaidUsed: '0.00',
    ...changes,
  }
}

function request(changes = {}) {
  return {
    id: requestId,
    branchId,
    employeeId,
    leaveTypeId: typeId,
    startDate: '2026-09-13',
    endDate: '2026-09-13',
    isHalfDay: true,
    halfDayPeriod: 'AM',
    daysRequested: '0.50',
    status: 'Pending',
    reason: 'Synthetic request',
    attachment: null,
    rejectionReason: '',
    managerRejectionReason: '',
    relationship: '',
    deceasedName: '',
    dateOfDeath: null,
    childBirthDate: null,
    childName: '',
    expectedDueDate: null,
    institutionName: '',
    examDates: '',
    substituteEmployeeId: null,
    approvalLevelRequired: 1,
    approvalComment: '',
    warnings: [],
    submittedAt: '2026-09-13T08:00:00.000Z',
    createdAt: '2026-09-13T08:00:00.000Z',
    updatedAt: '2026-09-13T08:00:00.000Z',
    ...changes,
  }
}

test('balance and request parsers enforce exact Phase 8A projections', () => {
  assert.deepEqual(parseLeaveBalance(balance()), balance())
  assert.deepEqual(parseLeaveRequest(request()), request())
  assert.throws(() => parseLeaveBalance(balance({ id: requestId })))
  assert.throws(() => parseLeaveBalance(balance({ remainingDays: 21 })))
  assert.throws(() => parseLeaveRequest(request({ attachment: 'legacy-url' })))
  assert.throws(() => parseLeaveRequest(request({ status: 'Info Requested' })))
})

test('self reads omit branch headers and administrator reads bind the selected branch', async () => {
  const calls = []
  const authentication = {
    request: async (path, options) => {
      calls.push({ path, options })
      return { data: [balance()], page: { limit: 50, nextCursor: null, hasMore: false } }
    },
  }
  await readEmployeeLeaveBalances(authentication, { year: 2026 })
  await readAdminLeaveBalances(authentication, branchId, { year: 2026 })
  assert.equal(calls[0].path, '/api/v1/leave/balances/self?year=2026')
  assert.equal(calls[0].options.headers, undefined)
  assert.deepEqual(calls[1].options.headers, { 'X-Workloop-Branch-ID': branchId })
})

test('administrator initialization and recalculation send only the selected leave year', async () => {
  const calls = []
  const authentication = {
    request: async (path, options) => {
      calls.push({ path, options })
      return { data: [balance()] }
    },
  }
  await initializeLeaveBalances(authentication, branchId, 2026)
  await recalculateLeaveBalances(authentication, branchId, 2026)
  assert.deepEqual(calls.map(({ path }) => path), [
    '/api/v1/leave/balances/initialize',
    '/api/v1/leave/balances/recalculate',
  ])
  for (const { options } of calls) {
    assert.equal(options.method, 'POST')
    assert.deepEqual(options.json, { leaveYear: 2026 })
    assert.deepEqual(options.headers, { 'X-Workloop-Branch-ID': branchId })
  }
})

test('migration leave code has no Supabase path and exposes read-only employee UI', async () => {
  const files = await Promise.all([
    readFile(new URL('../src/leaveBalanceApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/LeaveOverview.jsx', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(files.join('\n'), /supabase|createClient|@supabase/i)
  assert.match(files[1], /account\.role === 'admin'/)
  assert.match(files[1], /Initialize missing/)
  assert.match(files[1], /Request calendar/)
})
