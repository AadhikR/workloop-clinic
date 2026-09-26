import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { downloadReportCsv, parseReport, readReport, reportDefinitions } from '../src/reportApi.js'

const branchId = 'c9000000-0000-4000-8000-000000000002'

function response(reportId = 'headcount') {
  return {
    reportId,
    columns: [
      { key: 'employeeId', label: 'Employee ID', type: 'string', scale: null, nullable: false },
      { key: 'count', label: 'Count', type: 'integer', scale: null, nullable: false },
    ],
    rows: [{ employeeId: branchId, count: 1 }],
    totals: { scope: 'filtered', rowCount: 1, values: {} },
    filters: { limit: 50 },
    asOf: '2026-09-25T08:00:00.000Z',
    sourceVersion: `sha256:${'a'.repeat(64)}`,
    nextCursor: null,
  }
}

test('report catalogue has exactly the 13 approved reports', () => {
  assert.deepEqual(Object.keys(reportDefinitions).sort(), [
    'attendanceSummary', 'documentExpiry', 'emiratization', 'eosLiability', 'headcount',
    'leaveBalance', 'leaveUtilization', 'overtime', 'payrollCost', 'salaryMovement',
    'staffingCompliance', 'turnover', 'wpsCompliance',
  ])
})

test('report parser enforces columns, full-filter totals, and exact row cells', () => {
  assert.deepEqual(parseReport('headcount', response()), response())
  assert.throws(
    () => parseReport('headcount', { ...response(), totals: { scope: 'page', rowCount: 1, values: {} } }),
    /Invalid report response/,
  )
  const missingCell = response()
  missingCell.rows = [{ employeeId: branchId }]
  assert.throws(() => parseReport('headcount', missingCell), /Invalid report response/)
})

test('report client sends only the selected branch and allowlisted filters', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return { data: response('payrollCost') }
    },
  }
  await readReport(authentication, branchId, 'payrollCost', { period: '2026-08', limit: 20 })
  assert.deepEqual(calls[0], {
    path: '/api/v1/reports/payrollCost?period=2026-08&limit=20',
    options: { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId } },
  })
  await assert.rejects(
    readReport(authentication, branchId, 'payrollCost', { employeeId: branchId }),
    /Invalid report filter/,
  )
})

test('migration report path imports no legacy report code or Supabase client', async () => {
  const files = await Promise.all([
    readFile(new URL('../src/reportApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/Reports.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/OrganizationPanel.jsx', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(files.join('\n'), /supabase|reportUtils|utils\/storage|leaveStorage|attendanceStorage/)
  assert.match(files[2], /<Reports authentication=\{authentication\}/)
})

test('report CSV client preserves allowlisted filters and requests bytes', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return { bytes: new Uint8Array([1]) }
    },
  }
  await downloadReportCsv(authentication, branchId, 'payrollCost', { period: '2026-08' })
  assert.deepEqual(calls[0], {
    path: '/api/v1/reports/payrollCost.csv?period=2026-08',
    options: {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      responseType: 'bytes',
    },
  })
})
