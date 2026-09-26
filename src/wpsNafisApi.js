const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const periodPattern = /^\d{4}-(?:0[1-9]|1[0-2])$/
const moneyPattern = /^(?:0|[1-9]\d{0,9})\.\d{2}$/
const digestPattern = /^[0-9a-f]{64}$/
const sourceDigestPattern = /^sha256:[0-9a-f]{64}$/

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function headers(branchId, mutation = false) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    'X-Workloop-Branch-ID': branchId,
    ...(mutation ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

function parseWpsEntry(value) {
  if (
    !exactKeys(value, ['id', 'employeeId', 'employeeName', 'paymentStatus', 'rejectionReason', 'updatedAt'])
    || !uuidPattern.test(value.id) || !uuidPattern.test(value.employeeId)
    || typeof value.employeeName !== 'string'
    || !['pending', 'paid', 'rejected'].includes(value.paymentStatus)
    || !(value.rejectionReason === null || typeof value.rejectionReason === 'string')
    || !timestampPattern.test(value.updatedAt)
  ) throw new Error('Invalid WPS response')
  return value
}

export function parseWps(value) {
  if (
    !exactKeys(value, [
      'runId', 'period', 'paymentDate', 'status', 'submittedAt', 'confirmedAt',
      'referenceNumber', 'updatedAt', 'entries',
    ])
    || !uuidPattern.test(value.runId) || !periodPattern.test(value.period)
    || !datePattern.test(value.paymentDate)
    || !['draft', 'sif_generated', 'submitted', 'confirmed', 'partial_rejection', 'failed'].includes(value.status)
    || !(value.submittedAt === null || timestampPattern.test(value.submittedAt))
    || !(value.confirmedAt === null || timestampPattern.test(value.confirmedAt))
    || !(value.referenceNumber === null || typeof value.referenceNumber === 'string')
    || !timestampPattern.test(value.updatedAt) || !Array.isArray(value.entries)
  ) throw new Error('Invalid WPS response')
  value.entries.forEach(parseWpsEntry)
  return value
}

function parseSif(value) {
  const headerKeys = [
    'employerMolId', 'branchRoutingCode', 'periodStart', 'periodEnd', 'paymentDate',
    'employeeCount', 'totalIntegerPay',
  ]
  const entryKeys = [
    'payrollEntryId', 'employeeMolId', 'bankRoutingCode', 'iban', 'periodStart',
    'periodEnd', 'paidDays', 'basicPay', 'variablePay', 'totalPay',
  ]
  if (
    !exactKeys(value, ['mode', 'digest', 'header', 'entries'])
    || !['full', 'rejected'].includes(value.mode) || !digestPattern.test(value.digest)
    || !exactKeys(value.header, headerKeys) || !Array.isArray(value.entries)
    || !datePattern.test(value.header.periodStart) || !datePattern.test(value.header.periodEnd)
    || !datePattern.test(value.header.paymentDate) || !Number.isInteger(value.header.employeeCount)
    || !Number.isSafeInteger(value.header.totalIntegerPay)
  ) throw new Error('Invalid SIF input response')
  value.entries.forEach((item) => {
    if (
      !exactKeys(item, entryKeys) || !uuidPattern.test(item.payrollEntryId)
      || ['employeeMolId', 'bankRoutingCode', 'iban'].some((key) => typeof item[key] !== 'string')
      || !datePattern.test(item.periodStart) || !datePattern.test(item.periodEnd)
      || ['paidDays', 'basicPay', 'variablePay', 'totalPay'].some((key) => !Number.isSafeInteger(item[key]))
      || item.totalPay !== item.basicPay + item.variablePay
    ) throw new Error('Invalid SIF input response')
  })
  if (
    value.header.employeeCount !== value.entries.length
    || value.header.totalIntegerPay !== value.entries.reduce((sum, item) => sum + item.totalPay, 0)
  ) throw new Error('Invalid SIF input response')
  return value
}

function parseNafis(value) {
  const keys = [
    'id', 'period', 'totalHeadcount', 'emiratiCount', 'ratioPercent', 'requiredPercent',
    'compliant', 'sourceVersion', 'qualifyingWageTotal', 'employees', 'generatedAt',
  ]
  if (
    !exactKeys(value, keys) || !uuidPattern.test(value.id) || !periodPattern.test(value.period)
    || !Number.isInteger(value.totalHeadcount) || !Number.isInteger(value.emiratiCount)
    || !moneyPattern.test(value.ratioPercent) || !moneyPattern.test(value.requiredPercent)
    || typeof value.compliant !== 'boolean' || !digestPattern.test(value.sourceVersion)
    || !moneyPattern.test(value.qualifyingWageTotal) || !Array.isArray(value.employees)
    || !timestampPattern.test(value.generatedAt)
  ) throw new Error('Invalid Nafis response')
  value.employees.forEach((item) => {
    if (
      !exactKeys(item, ['employeeId', 'employeeName', 'nafisRegistrationNumber', 'qualifyingBasicWage'])
      || !uuidPattern.test(item.employeeId) || typeof item.employeeName !== 'string'
      || !(item.nafisRegistrationNumber === null || typeof item.nafisRegistrationNumber === 'string')
      || !moneyPattern.test(item.qualifyingBasicWage)
    ) throw new Error('Invalid Nafis response')
  })
  return value
}

function runId(value) {
  if (!uuidPattern.test(value)) throw new TypeError('Invalid payroll run ID')
}

async function wpsCommand(authentication, branchId, wps, path, extra = {}) {
  runId(wps?.runId)
  if (!timestampPattern.test(wps?.updatedAt)) throw new TypeError('Invalid WPS command')
  const response = await authentication.request(`/api/v1/payroll-runs/${wps.runId}/wps/${path}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { expectedUpdatedAt: wps.updatedAt, ...extra },
  })
  return parseWps(response.data)
}

export async function readWps(authentication, branchId, payrollRunId) {
  runId(payrollRunId)
  const response = await authentication.request(`/api/v1/payroll-runs/${payrollRunId}/wps`, {
    access: 'protected', headers: headers(branchId),
  })
  return parseWps(response.data)
}

export async function readSifInput(authentication, branchId, payrollRunId, rejected = false) {
  runId(payrollRunId)
  const suffix = rejected ? '?correction=rejected' : ''
  const response = await authentication.request(`/api/v1/payroll-runs/${payrollRunId}/sif-input${suffix}`, {
    access: 'protected', headers: headers(branchId),
  })
  return parseSif(response.data)
}

export async function previewSif(authentication, branchId, payrollRunId, rejected = false) {
  runId(payrollRunId)
  const suffix = rejected ? '?scope=rejected' : '?scope=all'
  const response = await authentication.request(`/api/v1/payroll-runs/${payrollRunId}/sif/preview${suffix}`, {
    access: 'protected', headers: headers(branchId),
  })
  const value = response.data
  if (
    !exactKeys(value, ['filename', 'sourceDigest', 'rendererVersion', 'byteCount', 'recordCount', 'records'])
    || typeof value.filename !== 'string' || !value.filename.endsWith('.sif')
    || !sourceDigestPattern.test(value.sourceDigest)
    || typeof value.rendererVersion !== 'string'
    || !Number.isSafeInteger(value.byteCount) || value.byteCount <= 0
    || !Number.isSafeInteger(value.recordCount) || value.recordCount <= 0
    || !Array.isArray(value.records) || value.records.length !== value.recordCount
    || value.records.at(-1)?.type !== 'SCR'
    || value.records.slice(0, -1).some((record) => record?.type !== 'EDR')
  ) throw new Error('Invalid SIF preview response')
  return value
}

export async function downloadSif(authentication, branchId, payrollRunId, rejected = false) {
  runId(payrollRunId)
  const suffix = rejected ? '?scope=rejected' : '?scope=all'
  return authentication.request(`/api/v1/payroll-runs/${payrollRunId}/sif${suffix}`, {
    access: 'protected', headers: headers(branchId), responseType: 'bytes',
  })
}

export const recordSifProjection = (authentication, branchId, wps) => (
  wpsCommand(authentication, branchId, wps, 'sif-generated')
)

export const submitWps = (authentication, branchId, wps, referenceNumber) => (
  wpsCommand(authentication, branchId, wps, 'submit', { referenceNumber: String(referenceNumber).trim() })
)

export const confirmWps = (authentication, branchId, wps) => (
  wpsCommand(authentication, branchId, wps, 'confirm')
)

export const failWps = (authentication, branchId, wps, reason) => (
  wpsCommand(authentication, branchId, wps, 'fail', { reason: String(reason).trim() })
)

export async function updateWpsEntry(authentication, branchId, wps, entry, action, reason = '') {
  runId(wps?.runId)
  if (!uuidPattern.test(entry?.id) || !timestampPattern.test(entry?.updatedAt)) {
    throw new TypeError('Invalid WPS entry command')
  }
  if (!['paid', 'reject'].includes(action)) throw new TypeError('Invalid WPS entry command')
  const json = { expectedUpdatedAt: entry.updatedAt, ...(action === 'reject' ? { reason: String(reason).trim() } : {}) }
  const response = await authentication.request(`/api/v1/payroll-runs/${wps.runId}/wps/entries/${entry.id}/${action}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json,
  })
  return parseWps(response.data)
}

export async function createComplianceOverride(authentication, branchId, payrollRunId, values) {
  runId(payrollRunId)
  const response = await authentication.request(`/api/v1/payroll-runs/${payrollRunId}/compliance-overrides`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: values,
  })
  const item = response.data
  if (
    !exactKeys(item, ['id', 'payrollRunId', 'payrollEntryId', 'ruleCode', 'reason', 'createdAt'])
    || !uuidPattern.test(item.id) || item.payrollRunId !== payrollRunId
    || !(item.payrollEntryId === null || uuidPattern.test(item.payrollEntryId))
    || typeof item.ruleCode !== 'string' || typeof item.reason !== 'string'
    || !timestampPattern.test(item.createdAt)
  ) throw new Error('Invalid compliance override response')
  return item
}

export async function readNafisSnapshots(authentication, branchId, period) {
  if (period && !periodPattern.test(period)) throw new TypeError('Invalid Nafis period')
  const suffix = period ? `?period=${encodeURIComponent(period)}` : ''
  const response = await authentication.request(`/api/v1/nafis-snapshots${suffix}`, {
    access: 'protected', headers: headers(branchId),
  })
  if (!Array.isArray(response.data) || response.page === null) throw new Error('Invalid Nafis response')
  return { items: response.data.map(parseNafis), page: response.page }
}

export async function replaceNafisSnapshot(authentication, branchId, period, current = null) {
  if (!periodPattern.test(period)) throw new TypeError('Invalid Nafis period')
  const response = await authentication.request(`/api/v1/nafis-snapshots/${period}`, {
    access: 'protected', method: 'PUT', headers: headers(branchId, true),
    json: { expectedGeneratedAt: current?.generatedAt ?? null },
  })
  return parseNafis(response.data)
}
