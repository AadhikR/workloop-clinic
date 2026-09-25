import { reportDefinitions } from './reportApi.js'

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

function byteRequest(authentication, path, branchId = null) {
  if (branchId !== null && !uuid.test(branchId)) throw new TypeError('Invalid output branch')
  return authentication.request(path, {
    access: 'protected',
    ...(branchId === null ? {} : { headers: { 'X-Workloop-Branch-ID': branchId } }),
    responseType: 'bytes',
  })
}

function reportPath(reportId, filters) {
  const definition = reportDefinitions[reportId]
  if (!definition || !filters || typeof filters !== 'object' || Array.isArray(filters)) {
    throw new TypeError('Invalid report output')
  }
  if (Object.keys(filters).some((key) => !definition.filters.includes(key))) {
    throw new TypeError('Invalid report output filter')
  }
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') query.set(key, String(value))
  }
  return `/api/v1/reports/${reportId}.pdf${query.size ? `?${query}` : ''}`
}

export const downloadReportPdf = (authentication, branchId, reportId, filters = {}) => (
  byteRequest(authentication, reportPath(reportId, filters), branchId)
)

export const downloadSelfPayslipPdf = (authentication, payslipId) => {
  if (!uuid.test(payslipId)) throw new TypeError('Invalid payslip ID')
  return byteRequest(authentication, `/api/v1/payslips/self/${payslipId}.pdf`)
}

export const downloadPayslipPdf = (authentication, branchId, payslipId) => {
  if (!uuid.test(payslipId)) throw new TypeError('Invalid payslip ID')
  return byteRequest(authentication, `/api/v1/payslips/${payslipId}.pdf`, branchId)
}

export const downloadPayslipsZip = (authentication, branchId, runId) => {
  if (!uuid.test(runId)) throw new TypeError('Invalid payroll run ID')
  return byteRequest(authentication, `/api/v1/payroll-runs/${runId}/payslips.zip`, branchId)
}

export const downloadRequestLetterPdf = (authentication, branchId, requestId) => {
  if (!uuid.test(requestId)) throw new TypeError('Invalid request ID')
  return byteRequest(authentication, `/api/v1/requests/${requestId}/letter.pdf`, branchId)
}

export const downloadOffboardingLetterPdf = (
  authentication, branchId, checklistId, letterKind,
) => {
  if (!uuid.test(checklistId) || !['noc', 'experience'].includes(letterKind)) {
    throw new TypeError('Invalid offboarding letter request')
  }
  return byteRequest(
    authentication,
    `/api/v1/offboarding/${checklistId}/letters/${letterKind}.pdf`,
    branchId,
  )
}

export const downloadFinalSettlementPdf = (authentication, branchId, checklistId) => {
  if (!uuid.test(checklistId)) throw new TypeError('Invalid offboarding checklist ID')
  return byteRequest(
    authentication, `/api/v1/offboarding/${checklistId}/final-settlement.pdf`, branchId,
  )
}

export const renderedOutputPatterns = Object.freeze({ uuid })
