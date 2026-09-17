const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const periodPattern = /^\d{4}-(?:0[1-9]|1[0-2])$/
const moneyPattern = /^-?(?:0|[1-9]\d{0,9})\.\d{2}$/
const automaticCodePattern = /^(?:AUTO_|LEAVE_|ATTENDANCE_|ROSTER_|EXPENSE_|ADVANCE_)/

const runKeys = [
  'id', 'period', 'paymentDate', 'sequence', 'runStatus', 'approvalStatus',
  'employeeCount', 'totalAmount', 'validationStatus', 'blockingErrors', 'sourceWarnings',
  'createdAt', 'updatedAt',
]
const adjustmentKeys = ['id', 'code', 'label', 'amount', 'recurrence', 'note']
const entryKeys = [
  'id', 'employeeId', 'employeeName', 'basicSalary', 'housingAllowance',
  'transportAllowance', 'fixedAllowance', 'increment', 'bonus', 'otherPay',
  'variableAllowance', 'leaveDeduction', 'fixedPay', 'grossPay', 'totalDeductions',
  'netPay', 'wpsBasicPay', 'wpsVariablePay', 'excluded', 'additionalAllowances',
  'deductions', 'sourceExplanations', 'sourceFingerprint',
]
const historyKeys = ['id', 'action', 'actorName', 'reason', 'createdAt']
const payslipKeys = [
  'id', 'period', 'paymentDate', 'employeeName', 'earnings', 'deductions', 'grossPay',
  'totalDeductions', 'netPay', 'wpsBasicPay', 'wpsVariablePay', 'issuedAt',
]
const lineKeys = ['label', 'amount']

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function adjustment(value) {
  if (
    !exactKeys(value, adjustmentKeys) || !uuidPattern.test(value.id)
    || !/^[A-Z][A-Z0-9_]{0,39}$/.test(value.code) || typeof value.label !== 'string'
    || !moneyPattern.test(value.amount) || !['one_time', 'recurring'].includes(value.recurrence)
    || !(value.note === null || typeof value.note === 'string')
  ) throw new Error('Invalid payroll response')
  return value
}

function entry(value) {
  const moneyKeys = [
    'basicSalary', 'housingAllowance', 'transportAllowance', 'fixedAllowance', 'increment',
    'bonus', 'otherPay', 'variableAllowance', 'leaveDeduction', 'fixedPay', 'grossPay',
    'totalDeductions', 'netPay', 'wpsBasicPay', 'wpsVariablePay',
  ]
  if (
    !exactKeys(value, entryKeys) || !uuidPattern.test(value.id) || !uuidPattern.test(value.employeeId)
    || typeof value.employeeName !== 'string' || moneyKeys.some((key) => !moneyPattern.test(value[key]))
    || typeof value.excluded !== 'boolean' || !Array.isArray(value.additionalAllowances)
    || !Array.isArray(value.deductions) || !Array.isArray(value.sourceExplanations)
    || value.sourceExplanations.some((item) => typeof item !== 'string')
    || !/^[0-9a-f]{64}$/.test(value.sourceFingerprint)
  ) throw new Error('Invalid payroll response')
  value.additionalAllowances.forEach(adjustment)
  value.deductions.forEach(adjustment)
  return value
}

export function parsePayrollRun(value, detail = false) {
  const expected = detail ? [...runKeys, 'entries'] : runKeys
  if (
    !exactKeys(value, expected) || !uuidPattern.test(value.id) || !periodPattern.test(value.period)
    || !datePattern.test(value.paymentDate) || typeof value.sequence !== 'string'
    || !['draft', 'generated'].includes(value.runStatus)
    || !['draft', 'pending_approval', 'approved'].includes(value.approvalStatus)
    || !Number.isInteger(value.employeeCount) || value.employeeCount < 0
    || !moneyPattern.test(value.totalAmount) || !['valid', 'blocking'].includes(value.validationStatus)
    || !Array.isArray(value.blockingErrors) || value.blockingErrors.some((item) => typeof item !== 'string')
    || !Array.isArray(value.sourceWarnings) || value.sourceWarnings.some((item) => typeof item !== 'string')
    || !timestampPattern.test(value.createdAt) || !timestampPattern.test(value.updatedAt)
    || detail && !Array.isArray(value.entries)
  ) throw new Error('Invalid payroll response')
  if (detail) value.entries.forEach(entry)
  return value
}

function headers(branchId, mutation = false) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    'X-Workloop-Branch-ID': branchId,
    ...(mutation ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

function queryString(options = {}) {
  const allowed = new Set(['cursor', 'limit', 'period', 'status', 'approvalStatus'])
  const parameters = new URLSearchParams()
  for (const [name, value] of Object.entries(options)) {
    if (!allowed.has(name) || value === undefined || value === null || value === '') continue
    if (name === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid payroll query')
    }
    if (name === 'period' && !periodPattern.test(value)) throw new TypeError('Invalid payroll query')
    if (name === 'status' && !['draft', 'generated'].includes(value)) throw new TypeError('Invalid payroll query')
    if (name === 'approvalStatus' && !['draft', 'pending_approval', 'approved'].includes(value)) {
      throw new TypeError('Invalid payroll query')
    }
    parameters.set(name, String(value))
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

export async function readPayrollRuns(authentication, branchId, options = {}) {
  const response = await authentication.request(`/api/v1/payroll-runs${queryString(options)}`, {
    access: 'protected', headers: headers(branchId),
  })
  if (!Array.isArray(response.data) || response.page === null) throw new Error('Invalid payroll response')
  return { items: response.data.map((item) => parsePayrollRun(item)), page: response.page }
}

export async function readPayrollRun(authentication, branchId, runId) {
  if (!uuidPattern.test(runId)) throw new TypeError('Invalid payroll run ID')
  const response = await authentication.request(`/api/v1/payroll-runs/${runId}`, {
    access: 'protected', headers: headers(branchId),
  })
  return parsePayrollRun(response.data, true)
}

function plan(values) {
  if (
    !exactKeys(values, ['period', 'paymentDate']) || !periodPattern.test(values.period)
    || !datePattern.test(values.paymentDate)
  ) throw new TypeError('Invalid payroll mutation')
}

export async function createPayrollRun(authentication, branchId, values) {
  plan(values)
  const response = await authentication.request('/api/v1/payroll-runs', {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: values,
  })
  return parsePayrollRun(response.data, true)
}

function version(run, extra = {}) {
  if (!uuidPattern.test(run?.id) || !timestampPattern.test(run?.updatedAt)) {
    throw new TypeError('Invalid payroll mutation')
  }
  return { expectedUpdatedAt: run.updatedAt, ...extra }
}

export async function repeatPayrollRun(authentication, branchId, run, values) {
  plan(values)
  const response = await authentication.request(`/api/v1/payroll-runs/${run.id}/repeat`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: version(run, values),
  })
  return parsePayrollRun(response.data, true)
}

export async function refreshPayrollRun(authentication, branchId, run) {
  const response = await authentication.request(`/api/v1/payroll-runs/${run.id}/refresh`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true), json: version(run),
  })
  return parsePayrollRun(response.data, true)
}

function cents(value) {
  return Math.round(Number(value) * 100)
}

function fixed(value) {
  return (value / 100).toFixed(2)
}

export function payrollPreview(value) {
  const additions = value.additionalAllowances.reduce((sum, item) => sum + cents(item.amount), 0)
  const deductions = value.deductions.reduce((sum, item) => sum + cents(item.amount), 0)
  const basic = cents(value.basicSalary)
  const fixedPay = basic + cents(value.housingAllowance) + cents(value.transportAllowance) + cents(value.fixedAllowance)
  const gross = fixedPay + cents(value.increment) + cents(value.bonus) + cents(value.otherPay)
    + cents(value.variableAllowance) + additions
  const totalDeductions = cents(value.leaveDeduction) + deductions
  const net = gross - totalDeductions
  return {
    basicSalary: value.basicSalary,
    housingAllowance: value.housingAllowance,
    transportAllowance: value.transportAllowance,
    fixedAllowance: value.fixedAllowance,
    fixedPay: fixed(fixedPay),
    grossPay: fixed(gross),
    totalDeductions: fixed(totalDeductions),
    netPay: fixed(net),
    wpsBasicPay: value.basicSalary,
    wpsVariablePay: fixed(net - basic),
  }
}

export async function savePayrollEntries(authentication, branchId, run, entries) {
  if (!Array.isArray(entries)) throw new TypeError('Invalid payroll mutation')
  const bodyEntries = entries.map((item) => ({
    employeeId: item.employeeId,
    increment: item.increment,
    bonus: item.bonus,
    otherPay: item.otherPay,
    variableAllowance: item.variableAllowance,
    additionalAllowances: item.additionalAllowances.filter((value) => !automaticCodePattern.test(value.code)),
    deductions: item.deductions.filter((value) => !automaticCodePattern.test(value.code)),
    excluded: item.excluded,
    preview: payrollPreview(item),
  }))
  const response = await authentication.request(`/api/v1/payroll-runs/${run.id}/entries`, {
    access: 'protected', method: 'PUT', headers: headers(branchId, true),
    json: version(run, { entries: bodyEntries }),
  })
  return parsePayrollRun(response.data, true)
}

export async function deletePayrollRun(authentication, branchId, run) {
  const response = await authentication.request(`/api/v1/payroll-runs/${run.id}`, {
    access: 'protected', method: 'DELETE', headers: headers(branchId, true), json: version(run),
  })
  if (!exactKeys(response.data, ['id', 'deleted']) || response.data.id !== run.id || response.data.deleted !== true) {
    throw new Error('Invalid payroll response')
  }
  return response.data
}

function reason(value) {
  const trimmed = String(value ?? '').trim()
  if (trimmed.length < 1 || trimmed.length > 500) throw new TypeError('A reason is required')
  return trimmed
}

async function lifecycleCommand(authentication, branchId, run, action, reasonValue) {
  if (!['submit', 'recall', 'approve', 'reject', 'generate'].includes(action)) {
    throw new TypeError('Invalid payroll command')
  }
  const extra = ['recall', 'reject'].includes(action) ? { reason: reason(reasonValue) } : {}
  const response = await authentication.request(`/api/v1/payroll-runs/${run.id}/${action}`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: version(run, extra),
  })
  return parsePayrollRun(response.data, true)
}

export const submitPayrollRun = (authentication, branchId, run) => lifecycleCommand(authentication, branchId, run, 'submit')
export const recallPayrollRun = (authentication, branchId, run, value) => lifecycleCommand(authentication, branchId, run, 'recall', value)
export const approvePayrollRun = (authentication, branchId, run) => lifecycleCommand(authentication, branchId, run, 'approve')
export const rejectPayrollRun = (authentication, branchId, run, value) => lifecycleCommand(authentication, branchId, run, 'reject', value)
export const generatePayrollRun = (authentication, branchId, run) => lifecycleCommand(authentication, branchId, run, 'generate')

export async function readPayrollApprovalHistory(authentication, branchId, runId) {
  if (!uuidPattern.test(runId)) throw new TypeError('Invalid payroll run ID')
  const response = await authentication.request(`/api/v1/payroll-runs/${runId}/approval-history`, {
    access: 'protected', headers: headers(branchId),
  })
  if (!Array.isArray(response.data)) throw new Error('Invalid payroll history response')
  return response.data.map((item) => {
    if (
      !exactKeys(item, historyKeys) || !uuidPattern.test(item.id)
      || !['submitted', 'recalled', 'approved', 'rejected'].includes(item.action)
      || typeof item.actorName !== 'string' || !(item.reason === null || typeof item.reason === 'string')
      || !timestampPattern.test(item.createdAt)
    ) throw new Error('Invalid payroll history response')
    return item
  })
}

function payslipLine(item) {
  if (!exactKeys(item, lineKeys) || typeof item.label !== 'string' || !moneyPattern.test(item.amount)) {
    throw new Error('Invalid payslip response')
  }
  return item
}

export function parsePayslip(item) {
  if (
    !exactKeys(item, payslipKeys) || !uuidPattern.test(item.id) || !periodPattern.test(item.period)
    || !datePattern.test(item.paymentDate) || typeof item.employeeName !== 'string'
    || !Array.isArray(item.earnings) || !Array.isArray(item.deductions)
    || ['grossPay', 'totalDeductions', 'netPay', 'wpsBasicPay', 'wpsVariablePay']
      .some((key) => !moneyPattern.test(item[key]))
    || !timestampPattern.test(item.issuedAt)
  ) throw new Error('Invalid payslip response')
  item.earnings.forEach(payslipLine)
  item.deductions.forEach(payslipLine)
  return item
}

export async function readSelfPayslips(authentication, options = {}) {
  const parameters = new URLSearchParams()
  if (options.limit !== undefined) {
    if (!Number.isInteger(options.limit) || options.limit < 1 || options.limit > 100) {
      throw new TypeError('Invalid payslip query')
    }
    parameters.set('limit', String(options.limit))
  }
  if (options.cursor) parameters.set('cursor', String(options.cursor))
  const suffix = parameters.size ? `?${parameters}` : ''
  const response = await authentication.request(`/api/v1/payslips/self${suffix}`, { access: 'protected' })
  if (!Array.isArray(response.data) || response.page === null) throw new Error('Invalid payslip response')
  return { items: response.data.map(parsePayslip), page: response.page }
}

export async function readSelfPayslip(authentication, payslipId) {
  if (!uuidPattern.test(payslipId)) throw new TypeError('Invalid payslip ID')
  const response = await authentication.request(`/api/v1/payslips/self/${payslipId}`, { access: 'protected' })
  return parsePayslip(response.data)
}
