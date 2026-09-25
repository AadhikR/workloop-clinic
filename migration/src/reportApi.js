const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const sourceVersionPattern = /^sha256:[0-9a-f]{64}$/
const cursorPattern = /^[A-Za-z0-9_-]+$/

export const reportDefinitions = Object.freeze({
  headcount: { label: 'Headcount', filters: ['status', 'departmentId'] },
  payrollCost: { label: 'Payroll cost', filters: ['period'] },
  leaveUtilization: { label: 'Leave utilization', filters: ['from', 'to', 'employeeId', 'departmentId'] },
  attendanceSummary: { label: 'Attendance summary', filters: ['period', 'status', 'employeeId', 'departmentId'] },
  overtime: { label: 'Overtime', filters: ['period', 'employeeId', 'departmentId'] },
  documentExpiry: { label: 'Document expiry', filters: ['from', 'to', 'status', 'employeeId', 'departmentId'] },
  salaryMovement: { label: 'Salary movement', filters: ['from', 'to', 'employeeId', 'departmentId'] },
  turnover: { label: 'Turnover', filters: ['from', 'to', 'status', 'departmentId'] },
  staffingCompliance: { label: 'Staffing compliance', filters: ['period', 'departmentId'] },
  wpsCompliance: { label: 'WPS compliance', filters: ['period', 'status', 'employeeId', 'departmentId'] },
  emiratization: { label: 'Emiratization', filters: ['period'] },
  eosLiability: { label: 'EOS liability', filters: ['status', 'employeeId', 'departmentId'] },
  leaveBalance: { label: 'Leave balance', filters: ['from', 'to', 'employeeId', 'departmentId'] },
})

const columnTypes = new Set(['string', 'integer', 'decimal', 'date', 'timestamp', 'boolean'])

function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function exactKeys(value, expected) {
  return record(value) && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function parseColumn(value) {
  if (
    !exactKeys(value, ['key', 'label', 'type', 'scale', 'nullable'])
    || typeof value.key !== 'string'
    || typeof value.label !== 'string'
    || !columnTypes.has(value.type)
    || !(value.scale === null || Number.isInteger(value.scale) && value.scale >= 0 && value.scale <= 8)
    || typeof value.nullable !== 'boolean'
  ) throw new Error('Invalid report response')
  return value
}

function validCell(value, column) {
  if (value === null) return column.nullable
  if (column.type === 'integer') return Number.isInteger(value)
  if (column.type === 'boolean') return typeof value === 'boolean'
  return typeof value === 'string'
}

export function parseReport(reportId, value) {
  if (!reportDefinitions[reportId]) throw new TypeError('Invalid report ID')
  if (
    !exactKeys(value, ['reportId', 'columns', 'rows', 'totals', 'filters', 'asOf', 'sourceVersion', 'nextCursor'])
    || value.reportId !== reportId
    || !Array.isArray(value.columns)
    || value.columns.length === 0
    || !Array.isArray(value.rows)
    || !record(value.filters)
    || !timestampPattern.test(value.asOf)
    || !sourceVersionPattern.test(value.sourceVersion)
    || !(value.nextCursor === null || typeof value.nextCursor === 'string' && cursorPattern.test(value.nextCursor))
    || !exactKeys(value.totals, ['scope', 'rowCount', 'values'])
    || value.totals.scope !== 'filtered'
    || !Number.isInteger(value.totals.rowCount)
    || !record(value.totals.values)
  ) throw new Error('Invalid report response')
  const columns = value.columns.map(parseColumn)
  const keys = columns.map((column) => column.key)
  if (new Set(keys).size !== keys.length) throw new Error('Invalid report response')
  for (const row of value.rows) {
    if (!exactKeys(row, keys)) throw new Error('Invalid report response')
    for (const column of columns) {
      if (!validCell(row[column.key], column)) throw new Error('Invalid report response')
    }
  }
  return { ...value, columns }
}

export async function readReport(authentication, branchId, reportId, filters = {}) {
  const definition = reportDefinitions[reportId]
  if (!definition) throw new TypeError('Invalid report ID')
  if (typeof branchId !== 'string' || branchId.length !== 36 || !record(filters)) {
    throw new TypeError('Invalid report request')
  }
  const allowed = new Set([...definition.filters, 'limit', 'cursor'])
  if (Object.keys(filters).some((key) => !allowed.has(key))) {
    throw new TypeError('Invalid report filter')
  }
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') query.set(key, String(value))
  }
  const suffix = query.size ? `?${query}` : ''
  const envelope = await authentication.request(`/api/v1/reports/${reportId}${suffix}`, {
    access: 'protected',
    headers: { 'X-Workloop-Branch-ID': branchId },
  })
  return parseReport(reportId, envelope.data)
}

export async function downloadReportCsv(authentication, branchId, reportId, filters = {}) {
  const definition = reportDefinitions[reportId]
  if (!definition) throw new TypeError('Invalid report ID')
  if (typeof branchId !== 'string' || branchId.length !== 36 || !record(filters)) {
    throw new TypeError('Invalid report request')
  }
  const allowed = new Set(definition.filters)
  if (Object.keys(filters).some((key) => !allowed.has(key))) {
    throw new TypeError('Invalid report filter')
  }
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') query.set(key, String(value))
  }
  const suffix = query.size ? `?${query}` : ''
  return authentication.request(`/api/v1/reports/${reportId}.csv${suffix}`, {
    access: 'protected',
    headers: { 'X-Workloop-Branch-ID': branchId },
    responseType: 'bytes',
  })
}
