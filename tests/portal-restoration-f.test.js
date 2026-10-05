import assert from 'node:assert/strict'
import test from 'node:test'
import { readCollectionPages } from '../src/collectionPages.js'
import { readOwnAdvanceProgress, parseExpirySource, parseLeaveAction, readClinicalWorkforceSummary, readClinicalWorkforceDetails, readEmployeeDirectoryDetails, workforceGroups, readAdminWorkspaceSummary, adminAlertCodes } from '../src/portalProjectionsApi.js'
import { readAllDirectReports } from '../src/employeeApi.js'
import { readCurrentEmployeeContract } from '../src/recordsBenefitsApi.js'

test('administrator summaries reject private fields, missing warnings, and contradictory payroll counts', async () => {
  const source = { businessDate: '2026-10-05', activeEmployees: 2, payrollRuns: 2, draftPayrolls: 1, sifGenerated: 1, insurancePolicies: 1, alerts: Object.fromEntries(adminAlertCodes.map((code) => [code, 1])) }
  const authentication = (data) => ({ request: async () => ({ data }) })
  assert.deepEqual(await readAdminWorkspaceSummary(authentication(source), 'f3000000-0000-4000-8000-000000000001'), source)
  for (const data of [{ ...source, draftPayrolls: 3 }, { ...source, alerts: {} }, { ...source, bankAccount: 'private' }, { ...source, activeEmployees: -1 }]) {
    await assert.rejects(readAdminWorkspaceSummary(authentication(data), 'f3000000-0000-4000-8000-000000000001'))
  }
})

test('contract editor reads the authoritative current state without accepting write authority', async () => {
  const current = { employeeUpdatedAt: '2026-10-05T10:00:00.123Z', currentContractType: 'Unlimited', currentContractEndDate: null, latestContractEventId: null }
  const requests = []
  const authentication = { request: async (path, options) => { requests.push({ path, options }); return { data: current } } }
  const branch = 'f3000000-0000-4000-8000-000000000001'
  assert.deepEqual(await readCurrentEmployeeContract(authentication, branch, branch), current)
  assert.equal(requests[0].options.headers['X-Workloop-Branch-ID'], branch)
  assert.ok(requests[0].path.endsWith('/contracts/current'))
  await assert.rejects(readCurrentEmployeeContract({ request: async () => ({ data: { ...current, actorId: branch } }) }, branch, branch))
})

test('collection traversal loads every page before publishing a summary', async () => {
  const requested = []
  const result = await readCollectionPages(async (cursor) => {
    requested.push(cursor)
    return cursor === null
      ? { items: [{ id: 'a' }], page: { limit: 1, hasMore: true, nextCursor: 'a' } }
      : { items: [{ id: 'b' }], page: { limit: 1, hasMore: false, nextCursor: null } }
  })
  assert.deepEqual(requested, [null, 'a'])
  assert.deepEqual(result, [{ id: 'a' }, { id: 'b' }])
})

const advanceId = 'f3000000-0000-4000-8000-000000000001'
const stamp = '2026-10-05T10:00:00.000Z'
const summary = {
  advanceId, amount: '30.00', totalPaid: '30.00', outstandingBalance: '0.00', status: 'settled',
  updatedAt: stamp, sourceVersion: `sha256:${'a'.repeat(64)}`,
  schedule: [{ period: '2026-10', scheduledAmount: '30.00', paidAmount: '30.00', remainingAmount: '0.00', status: 'paid' }],
}

function repayment(index, amount) {
  return { id: `f3000000-0000-4000-8000-${String(index).padStart(12, '0')}`, amount,
    paidDate: '2026-10-01', payrollPeriod: null, createdAt: stamp }
}

test('own advance totals agree with complete payments and installments across pages', async () => {
  const authentication = { request: async (path) => path.includes('cursor=')
    ? { summary, data: [repayment(3, '20.00')], page: { limit: 100, hasMore: false, nextCursor: null } }
    : { summary, data: [repayment(2, '10.00')], page: { limit: 100, hasMore: true, nextCursor: repayment(2, '10.00').id } } }
  const result = await readOwnAdvanceProgress(authentication, advanceId)
  assert.equal(result.payments.length, 2)
  assert.equal(result.summary.totalPaid, '30.00')
})

test('own repayment detail rejects changed sources, mismatched totals and private fields', async () => {
  for (const replacement of [{ ...summary, totalPaid: '29.00' }, { ...summary, payrollRunId: advanceId }]) {
    await assert.rejects(readOwnAdvanceProgress({ request: async () => ({ summary: replacement, data: [], page: { limit: 100, hasMore: false, nextCursor: null } }) }, advanceId))
  }
  await assert.rejects(readOwnAdvanceProgress({ request: async (path) => path.includes('cursor=')
    ? { summary: { ...summary, sourceVersion: `sha256:${'b'.repeat(64)}` }, data: [repayment(3, '20.00')], page: { limit: 100, hasMore: false, nextCursor: null } }
    : { summary, data: [repayment(2, '10.00')], page: { limit: 100, hasMore: true, nextCursor: repayment(2, '10.00').id } } }, advanceId), /source changed/)
})

test('expiry and action projections reject private or unknown fields', () => {
  const source = { id: `document:${advanceId}`, employeeId: advanceId, employeeName: 'Synthetic employee', sourceType: 'passport', expiryDate: '2026-10-01', status: 'expired' }
  assert.equal(parseExpirySource(source).status, 'expired')
  assert.throws(() => parseExpirySource({ ...source, storagePath: 'private' }))
  const action = { id: advanceId, requestId: advanceId, employeeId: advanceId, employeeName: 'Synthetic employee', leaveType: 'Annual', startDate: '2026-10-01', endDate: '2026-10-02', action: 'approved', reason: 'Approved', actorName: 'You', actionAt: stamp }
  assert.equal(parseLeaveAction(action).actorName, 'You')
  assert.throws(() => parseLeaveAction({ ...action, subject: 'private' }))
})

test('a failed later page never returns an incomplete collection', async () => {
  await assert.rejects(readCollectionPages(async (cursor) => {
    if (cursor) throw new Error('Unavailable')
    return { items: [{ id: 'a' }], page: { limit: 1, hasMore: true, nextCursor: 'a' } }
  }), /Unavailable/)
})

test('malformed cursors, repeated rows and incomplete terminal pages fail closed', async () => {
  for (const page of [
    { limit: 1, hasMore: true, nextCursor: null },
    { limit: 1, hasMore: false, nextCursor: 'a' },
    { limit: 0, hasMore: false, nextCursor: null },
  ]) await assert.rejects(readCollectionPages(async () => ({ items: [{ id: 'a' }], page })))
  await assert.rejects(readCollectionPages(async () => ({
    items: [{ id: 'a' }], page: { limit: 1, hasMore: true, nextCursor: 'a' },
  })), /Collection changed/)
})

test('manager report collections traverse pages without sending a branch selector', async () => {
  const report = { id: advanceId, empNo: 'F-001', name: 'Synthetic report', photoUrl: '', jobTitle: 'Nurse', department: 'Clinical', employmentStartDate: '2025-01-01', probationEndDate: null, employmentStatus: 'active' }
  const second = { ...report, id: repayment(2, '0.00').id }
  const requested = []
  const authentication = { request: async (path, options) => {
    requested.push({ path, options })
    return path.includes('cursor=')
      ? { data: [second], page: { limit: 100, hasMore: false, nextCursor: null } }
      : { data: [report], page: { limit: 100, hasMore: true, nextCursor: report.id } }
  } }
  assert.deepEqual(await readAllDirectReports(authentication), [report, second])
  assert.equal(requested.length, 2)
  assert.equal(requested[0].options.headers, undefined)
  assert.match(requested[0].path, /limit=100/)
  await assert.rejects(readAllDirectReports(authentication, { branchId: advanceId }))
})

function workforceSummary() {
  return { businessDate: '2026-10-05', counts: Object.fromEntries(workforceGroups.map((group) => [group, ['activeStaff', 'credentialCompliance', 'coverage'].includes(group) ? 1 : 0])), compliant: 1, rostered: 1,
    departments: [{ department: 'Clinical', headcount: 1, credentialled: 1, rostered: 1, minStaff: 1 }] }
}

test('clinical workforce totals reject partial, inconsistent and private projections', async () => {
  const read = (data) => readClinicalWorkforceSummary({ request: async () => ({ data }) }, advanceId)
  assert.deepEqual(await read(workforceSummary()), workforceSummary())
  for (const data of [
    { ...workforceSummary(), compliant: 2 },
    { ...workforceSummary(), departments: [] },
    { ...workforceSummary(), counts: { ...workforceSummary().counts, coverage: 2 } },
    { ...workforceSummary(), employeeIds: [advanceId] },
    { ...workforceSummary(), departments: [...workforceSummary().departments, ...workforceSummary().departments] },
  ]) await assert.rejects(read(data))
})

test('directory and clinical detail traverse safe pages and reject private fields', async () => {
  const directory = { id: advanceId, molId: 'Synthetic MOL', allowance: '0.00', visaExpiry: null, emiratesIdExpiry: null }
  const detail = { id: advanceId, employeeId: advanceId, employeeName: 'Synthetic employee', department: 'Clinical', jobTitle: 'Nurse', status: 'active', sourceDate: null, sourceTime: null, sourceLabel: '' }
  const authentication = (data) => ({ request: async () => ({ data: [data], page: { limit: 100, hasMore: false, nextCursor: null } }) })
  assert.deepEqual(await readEmployeeDirectoryDetails(authentication(directory), advanceId), [directory])
  assert.deepEqual(await readClinicalWorkforceDetails(authentication(detail), advanceId, 'activeStaff'), [detail])
  await assert.rejects(readEmployeeDirectoryDetails(authentication({ ...directory, iban: 'private' }), advanceId))
  await assert.rejects(readClinicalWorkforceDetails(authentication({ ...detail, storagePath: 'private' }), advanceId, 'activeStaff'))
  assert.throws(() => readClinicalWorkforceDetails(authentication(detail), advanceId, 'unapproved'))
})
