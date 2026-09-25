import assert from 'node:assert/strict'
import test from 'node:test'

import {
  downloadSif,
  parseWps,
  previewSif,
  readNafisSnapshots,
  readSifInput,
  recordSifProjection,
  submitWps,
  updateWpsEntry,
} from '../migration/src/wpsNafisApi.js'

const branchId = '91000000-0000-4000-8000-000000000001'
const runId = '91000000-0000-4000-8000-000000000002'
const entryId = '91000000-0000-4000-8000-000000000003'
const employeeId = '91000000-0000-4000-8000-000000000004'
const now = '2026-09-17T10:00:00.000Z'

const entry = {
  id: entryId,
  employeeId,
  employeeName: 'Synthetic Employee',
  paymentStatus: 'pending',
  rejectionReason: null,
  updatedAt: now,
}
const wps = {
  runId,
  period: '2026-09',
  paymentDate: '2026-09-25',
  status: 'draft',
  submittedAt: null,
  confirmedAt: null,
  referenceNumber: null,
  updatedAt: now,
  entries: [entry],
}
const sif = {
  mode: 'full',
  digest: 'a'.repeat(64),
  header: {
    employerMolId: '9000000816726',
    branchRoutingCode: '999000001',
    periodStart: '2026-09-01',
    periodEnd: '2026-09-30',
    paymentDate: '2026-09-25',
    employeeCount: 1,
    totalIntegerPay: 1202,
  },
  entries: [{
    payrollEntryId: entryId,
    employeeMolId: 'MOL-1',
    bankRoutingCode: '999000001',
    iban: 'AE070331234567890123456',
    periodStart: '2026-09-01',
    periodEnd: '2026-09-30',
    paidDays: 30,
    basicPay: 1001,
    variablePay: 201,
    totalPay: 1202,
  }],
}

function client(data) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return { data, page: Array.isArray(data) ? { limit: 50, nextCursor: null, hasMore: false } : null }
    },
  }
}

test('WPS projections reject omitted and extra financial fields', () => {
  assert.deepEqual(parseWps(wps), wps)
  assert.throws(() => parseWps({ ...wps, actorId: employeeId }), /Invalid WPS/)
  assert.throws(() => parseWps({ ...wps, entries: [{ ...entry, iban: 'unsafe' }] }), /Invalid WPS/)
})

test('SIF input validates independent row and header totals', async () => {
  const api = client(sif)
  const result = await readSifInput(api, branchId, runId)
  assert.equal(result.entries[0].totalPay, 1202)
  assert.equal(api.calls[0].path, `/api/v1/payroll-runs/${runId}/sif-input`)
  await assert.rejects(
    () => readSifInput(client({ ...sif, header: { ...sif.header, totalIntegerPay: 1201 } }), branchId, runId),
    /Invalid SIF input/,
  )
})

test('SIF preview and download share the server scope routes', async () => {
  const preview = {
    filename: '9000000816726260925000000.sif',
    sourceDigest: `sha256:${'a'.repeat(64)}`,
    rendererVersion: 'phase12f-sif-v1',
    byteCount: 200,
    recordCount: 2,
    records: [
      { type: 'EDR', employeeMolId: 'MOL-1' },
      { type: 'SCR', totalPay: 1202 },
    ],
  }
  const previewApi = client(preview)
  assert.deepEqual(await previewSif(previewApi, branchId, runId, true), preview)
  assert.equal(previewApi.calls[0].path, `/api/v1/payroll-runs/${runId}/sif/preview?scope=rejected`)
  const downloadApi = client(null)
  await downloadSif(downloadApi, branchId, runId)
  assert.deepEqual(downloadApi.calls[0], {
    path: `/api/v1/payroll-runs/${runId}/sif?scope=all`,
    options: {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      responseType: 'bytes',
    },
  })
})

test('WPS mutations send idempotency and optimistic timestamps', async () => {
  const projection = client({ ...wps, status: 'sif_generated' })
  await recordSifProjection(projection, branchId, wps)
  assert.deepEqual(projection.calls[0].options.json, { expectedUpdatedAt: now })
  assert.match(projection.calls[0].options.headers['Idempotency-Key'], /^[0-9a-f-]{36}$/)

  const submit = client({ ...wps, status: 'submitted' })
  await submitWps(submit, branchId, wps, '  BANK-1  ')
  assert.deepEqual(submit.calls[0].options.json, {
    expectedUpdatedAt: now,
    referenceNumber: 'BANK-1',
  })

  const paid = client({ ...wps, status: 'submitted', entries: [{ ...entry, paymentStatus: 'paid' }] })
  await updateWpsEntry(paid, branchId, wps, entry, 'paid')
  assert.deepEqual(paid.calls[0].options.json, { expectedUpdatedAt: now })
})

test('Nafis projections reject extra source data', async () => {
  const snapshot = {
    id: entryId,
    period: '2026-09',
    totalHeadcount: 1,
    emiratiCount: 1,
    ratioPercent: '100.00',
    requiredPercent: '2.00',
    compliant: true,
    sourceVersion: 'b'.repeat(64),
    qualifyingWageTotal: '10000.00',
    employees: [{
      employeeId,
      employeeName: 'Synthetic Employee',
      nafisRegistrationNumber: 'NAFIS-1',
      qualifyingBasicWage: '10000.00',
    }],
    generatedAt: now,
  }
  const result = await readNafisSnapshots(client([snapshot]), branchId)
  assert.equal(result.items[0].emiratiCount, 1)
  await assert.rejects(
    () => readNafisSnapshots(client([{ ...snapshot, notificationStatus: 'sent' }]), branchId),
    /Invalid Nafis/,
  )
})
