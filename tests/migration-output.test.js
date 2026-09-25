import assert from 'node:assert/strict'
import test from 'node:test'

import { createHttpClient } from '../migration/src/http.js'
import {
  downloadAttendance,
  downloadEmployeeTemplate,
  downloadEmployees,
  downloadLeaveBalances,
  downloadNafis,
  downloadRoster,
} from '../migration/src/outputApi.js'
import { saveDownload } from '../migration/src/outputDelivery.js'

const branchId = 'c9000000-0000-4000-8000-000000000002'
const resourceId = 'c9000000-0000-4000-8000-000000000004'
const correlationId = '00f202d5-2ef0-4d6f-9553-830e5dcfb833'

function client() {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return { bytes: new Uint8Array([1]), filename: 'output.csv', contentType: 'text/csv; charset=utf-8' }
    },
  }
}

test('named compatibility clients use only protected server byte routes', async () => {
  const api = client()
  await downloadEmployeeTemplate(api, branchId)
  await downloadEmployees(api, branchId, resourceId)
  await downloadLeaveBalances(api, branchId, 2026)
  await downloadAttendance(api, branchId, resourceId)
  await downloadRoster(api, branchId, '2026-09')
  await downloadNafis(api, branchId, resourceId)
  assert.deepEqual(api.calls.map((call) => call.path), [
    '/api/v1/exports/employees/template.csv',
    `/api/v1/exports/employees.csv?employeeId=${resourceId}`,
    '/api/v1/exports/leave-balances.csv?year=2026',
    `/api/v1/exports/attendance/${resourceId}.csv`,
    '/api/v1/exports/roster.csv?period=2026-09',
    `/api/v1/exports/nafis/${resourceId}.csv`,
  ])
  for (const call of api.calls) {
    assert.deepEqual(call.options, {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      responseType: 'bytes',
    })
  }
})

test('binary HTTP responses require every delivery header and exact length', async () => {
  const bytes = new TextEncoder().encode('A,B\r\n1,2\r\n')
  const http = createHttpClient({
    apiBaseUrl: 'http://127.0.0.1:8000',
    browserOrigin: 'http://127.0.0.1:5174',
    getAccessToken: async () => 'token',
    fetch: async (_url, options) => {
      assert.equal(options.headers.get('Accept'), 'application/octet-stream, text/csv')
      return new Response(bytes, {
        headers: {
          'Cache-Control': 'no-store',
          'Content-Disposition': 'attachment; filename="report.csv"; filename*=UTF-8\'\'report.csv',
          'Content-Length': String(bytes.byteLength),
          'Content-Type': 'text/csv; charset=utf-8',
          Digest: `sha-256=${'A'.repeat(43)}=`,
          ETag: `"${'a'.repeat(64)}"`,
          Pragma: 'no-cache',
          Vary: 'Authorization',
          'X-Content-Type-Options': 'nosniff',
          'X-Correlation-ID': correlationId,
          'X-Request-ID': correlationId,
        },
      })
    },
  })
  const result = await http.request('/api/v1/reports/headcount.csv', {
    access: 'protected', responseType: 'bytes',
  })
  assert.deepEqual(result.bytes, bytes)
  assert.equal(result.filename, 'report.csv')
})

test('download delivery creates one browser object URL and revokes it', () => {
  const events = []
  const browser = {
    Blob,
    URL: {
      createObjectURL(blob) { events.push(['create', blob.type, blob.size]); return 'blob:test' },
      revokeObjectURL(url) { events.push(['revoke', url]) },
    },
    document: {
      createElement() {
        return {
          click() { events.push(['click', this.href, this.download, this.rel]) },
        }
      },
    },
  }
  saveDownload({ bytes: new Uint8Array([1, 2]), filename: 'report.csv', contentType: 'text/csv' }, browser)
  assert.deepEqual(events, [
    ['create', 'text/csv', 2],
    ['click', 'blob:test', 'report.csv', 'noopener'],
    ['revoke', 'blob:test'],
  ])
})
