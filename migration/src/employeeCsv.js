import Papa from 'papaparse'

const maximumBytes = 1_048_576
const maximumRows = 500
const moneyPattern = /^(?:0|[1-9]\d{0,9})\.\d{2}$/
const headers = new Map([
  ['empNo', ['emp no', 'employee no', 'employee number', 'no']],
  ['name', ['name', 'employee name']],
  ['molId', ['mol id', 'mol employee id', 'labor card no', 'labour card no']],
  ['bankName', ['bank', 'bank name']],
  ['bankRoutingCode', ['bank / routing code', 'bank/routing code', 'routing code', 'bank routing code']],
  ['iban', ['bank account no', 'iban', 'bank account number']],
  ['basicSalary', ['basic', 'basic salary']],
  ['allowance', ['allowance']],
])

function cleanText(value) {
  const text = String(value ?? '').trim()
  const guarded = text.match(/^="(.*)"$/)
  return (guarded ? guarded[1] : text).replace(/^"+|"+$/g, '').trim()
}

function money(value) {
  const normalized = cleanText(value).replace(/,/g, '')
  if (!normalized) return '0.00'
  const amount = Number(normalized)
  return Number.isFinite(amount) ? amount.toFixed(2) : normalized
}

function diagnostic(rowNumber, field, message) {
  return Object.freeze({ rowNumber, field, message })
}

export function parseEmployeeCsv(source) {
  if (typeof source !== 'string') throw new TypeError('Invalid employee CSV')
  if (new TextEncoder().encode(source).byteLength > maximumBytes) {
    return Object.freeze({
      rows: Object.freeze([]),
      diagnostics: Object.freeze([diagnostic(1, 'file', 'CSV file exceeds 1 MiB')]),
    })
  }
  const parsed = Papa.parse(source, { header: false, skipEmptyLines: 'greedy' })
  const diagnostics = parsed.errors.map((error) => diagnostic(
    (error.row ?? 0) + 1,
    'row',
    'CSV row could not be parsed',
  ))
  if (!parsed.data.length) {
    diagnostics.push(diagnostic(1, 'file', 'CSV file has no header row'))
    return Object.freeze({ rows: Object.freeze([]), diagnostics: Object.freeze(diagnostics) })
  }
  const normalizedHeaders = parsed.data[0].map((value) => cleanText(value).toLowerCase())
  const indexes = Object.fromEntries([...headers].map(([field, aliases]) => [
    field,
    normalizedHeaders.findIndex((value) => aliases.includes(value)),
  ]))
  for (const [field, index] of Object.entries(indexes)) {
    if (index < 0) diagnostics.push(diagnostic(1, field, 'Required CSV column is missing'))
  }
  const inputRows = parsed.data.slice(1)
  if (inputRows.length > maximumRows) {
    diagnostics.push(diagnostic(1, 'rows', 'CSV file contains more than 500 rows'))
  }
  const rows = inputRows.slice(0, maximumRows).map((values, index) => {
    const read = (field) => indexes[field] < 0 ? '' : cleanText(values[indexes[field]])
    const row = Object.freeze({
      rowNumber: index + 2,
      empNo: read('empNo'),
      name: read('name'),
      molId: read('molId'),
      bankName: read('bankName'),
      bankRoutingCode: read('bankRoutingCode'),
      iban: read('iban').replace(/\s/g, '').toUpperCase(),
      basicSalary: money(read('basicSalary')),
      allowance: money(read('allowance')),
    })
    if (!row.empNo) diagnostics.push(diagnostic(row.rowNumber, 'empNo', 'Employee number is required'))
    if (!row.name) diagnostics.push(diagnostic(row.rowNumber, 'name', 'Employee name is required'))
    if (!/^\d{10,15}$/.test(row.molId)) {
      diagnostics.push(diagnostic(row.rowNumber, 'molId', 'MOL ID must contain 10 to 15 digits'))
    }
    if (row.bankRoutingCode && !/^\d{9}$/.test(row.bankRoutingCode)) {
      diagnostics.push(diagnostic(row.rowNumber, 'bankRoutingCode', 'Bank routing code must contain 9 digits'))
    }
    if (row.iban && !/^AE\d{21}$/.test(row.iban)) {
      diagnostics.push(diagnostic(row.rowNumber, 'iban', 'IBAN must be AE followed by 21 digits'))
    }
    for (const field of ['basicSalary', 'allowance']) {
      if (!moneyPattern.test(row[field])) {
        diagnostics.push(diagnostic(row.rowNumber, field, 'Amount must use two decimal places'))
      }
    }
    return row
  })
  diagnostics.sort((left, right) => left.rowNumber - right.rowNumber
    || left.field.localeCompare(right.field)
    || left.message.localeCompare(right.message))
  return Object.freeze({ rows: Object.freeze(rows), diagnostics: Object.freeze(diagnostics) })
}
