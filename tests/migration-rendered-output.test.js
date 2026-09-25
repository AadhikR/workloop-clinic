import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { openPdf } from '../migration/src/outputDelivery.js'
import {
  downloadFinalSettlementPdf,
  downloadOffboardingLetterPdf,
  downloadPayslipsZip,
  downloadReportPdf,
  downloadRequestLetterPdf,
  downloadSelfPayslipPdf,
} from '../migration/src/renderedOutputApi.js'

const branchId = 'c9000000-0000-4000-8000-000000000002'
const resourceId = 'c9000000-0000-4000-8000-000000000004'

function client() {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return { bytes: new Uint8Array([1]), filename: 'output.pdf', contentType: 'application/pdf' }
    },
  }
}

test('rendered output clients request only protected server bytes', async () => {
  const api = client()
  await downloadReportPdf(api, branchId, 'payrollCost', { period: '2026-08' })
  await downloadSelfPayslipPdf(api, resourceId)
  await downloadPayslipsZip(api, branchId, resourceId)
  await downloadRequestLetterPdf(api, null, resourceId)
  await downloadOffboardingLetterPdf(api, branchId, resourceId, 'noc')
  await downloadFinalSettlementPdf(api, branchId, resourceId)
  assert.deepEqual(api.calls.map((call) => call.path), [
    '/api/v1/reports/payrollCost.pdf?period=2026-08',
    `/api/v1/payslips/self/${resourceId}.pdf`,
    `/api/v1/payroll-runs/${resourceId}/payslips.zip`,
    `/api/v1/requests/${resourceId}/letter.pdf`,
    `/api/v1/offboarding/${resourceId}/letters/noc.pdf`,
    `/api/v1/offboarding/${resourceId}/final-settlement.pdf`,
  ])
  for (const call of api.calls) {
    assert.equal(call.options.access, 'protected')
    assert.equal(call.options.responseType, 'bytes')
  }
})

test('print opens the authorized PDF bytes and revokes the viewer URL later', () => {
  const events = []
  const browser = {
    Blob,
    URL: {
      createObjectURL(blob) { events.push(['create', blob.type]); return 'blob:pdf' },
      revokeObjectURL(url) { events.push(['revoke', url]) },
    },
    open(url, target, features) { events.push(['open', url, target, features]); return {} },
    setTimeout(callback, delay) { events.push(['timeout', delay]); callback() },
  }
  openPdf(
    { bytes: new Uint8Array([1, 2]), filename: 'output.pdf', contentType: 'application/pdf' },
    browser,
  )
  assert.deepEqual(events, [
    ['create', 'application/pdf'],
    ['open', 'blob:pdf', '_blank', 'noopener,noreferrer'],
    ['timeout', 60_000],
    ['revoke', 'blob:pdf'],
  ])
})

test('requested-letter PDF controls stay within the approved role table', async () => {
  const source = await readFile(new URL('../migration/src/LetterRequests.jsx', import.meta.url), 'utf8')
  assert.match(source, /item\.status === 'completed' && account\.role !== 'manager'/)
  assert.match(source, /downloadRequestLetterPdf/)
})
