const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const moneyPattern = /^(?:0|[1-9]\d*)\.\d{2}$/
const statuses = new Set(['active', 'probation', 'on_leave', 'terminated'])
const changeTypes = new Set([
  'title_change', 'department_change', 'salary_change', 'status_change',
])
const genders = new Set([null, 'male', 'female', 'other'])
const maritalStatuses = new Set([null, 'single', 'married', 'divorced', 'widowed'])
const visaTypes = new Set([
  null, 'employment_visa', 'investor_visa', 'dependent_visa', 'tourist_temp', 'exempt',
])
const workLocationTypes = new Set(['mainland', 'free_zone'])

const adminListKeys = [
  'id', 'empNo', 'name', 'photoUrl', 'workEmail', 'jobTitle', 'department',
  'reportingManagerId', 'employmentStartDate', 'probationEndDate', 'employmentStatus',
  'active', 'basicSalary', 'housingAllowance', 'transportAllowance', 'otherAllowances',
  'bankName', 'updatedAt',
]
const adminDetailKeys = [
  ...adminListKeys,
  'molId', 'bankRoutingCode', 'iban', 'allowance', 'personalEmail', 'phone', 'dateOfBirth',
  'gender', 'maritalStatus', 'homeCountryAddress', 'emergencyContactName',
  'emergencyContactRelationship', 'emergencyContactPhone', 'probationExtended',
  'terminationDate', 'terminationReason', 'otherAllowancesLabel', 'bankAccountHolder',
  'nationality', 'visaType', 'visaNumber', 'visaExpiry', 'passportNumber', 'passportExpiry',
  'emiratesId', 'emiratesIdExpiry', 'labourCardNumber', 'labourCardExpiry',
  'sponsoringEntity', 'workLocationType', 'freeZoneName', 'nafisRegistrationNo',
  'licenceAuthority', 'licenceNumber', 'licenceExpiry', 'createdAt',
]
const selfKeys = [
  ...adminDetailKeys.filter((key) => ![
    'reportingManagerId', 'active', 'updatedAt', 'createdAt',
  ].includes(key)),
  'reportingManager',
]
const directReportKeys = [
  'id', 'empNo', 'name', 'photoUrl', 'jobTitle', 'department', 'employmentStartDate',
  'probationEndDate', 'employmentStatus',
]
const historyKeys = [
  'id', 'employeeId', 'changedAt', 'changedByAppUserId', 'changeType', 'oldValue',
  'newValue', 'reason',
]

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function exactKeys(value, keys) {
  if (!isRecord(value)) return false
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length
    && actual.every((key, index) => key === expected[index])
}

function isUuid(value) {
  return typeof value === 'string' && uuidPattern.test(value)
}

function isText(value) {
  return typeof value === 'string'
}

function isDate(value) {
  if (value === null) return true
  if (typeof value !== 'string' || !datePattern.test(value)) return false
  const parsed = new Date(`${value}T00:00:00.000Z`)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value
}

function invalidEmployeeResponse() {
  return new Error('Invalid employee response')
}

function validListFields(data) {
  return isUuid(data.id)
    && isText(data.empNo)
    && isText(data.name)
    && isText(data.photoUrl)
    && isText(data.workEmail)
    && isText(data.jobTitle)
    && isText(data.department)
    && (data.reportingManagerId === null || isUuid(data.reportingManagerId))
    && isDate(data.employmentStartDate)
    && isDate(data.probationEndDate)
    && statuses.has(data.employmentStatus)
    && typeof data.active === 'boolean'
    && ['basicSalary', 'housingAllowance', 'transportAllowance', 'otherAllowances']
      .every((field) => typeof data[field] === 'string' && moneyPattern.test(data[field]))
    && isText(data.bankName)
    && instantPattern.test(data.updatedAt)
}

function parseAdminList(data) {
  if (!exactKeys(data, adminListKeys) || !validListFields(data)) {
    throw invalidEmployeeResponse()
  }
  return Object.freeze({ ...data })
}

function validDetailFields(data) {
  return validListFields(data)
    && [
      'molId', 'bankRoutingCode', 'iban', 'personalEmail', 'phone', 'homeCountryAddress',
      'emergencyContactName', 'emergencyContactRelationship', 'emergencyContactPhone',
      'terminationReason', 'otherAllowancesLabel', 'bankAccountHolder', 'nationality',
      'visaNumber', 'passportNumber', 'emiratesId', 'labourCardNumber', 'sponsoringEntity',
      'freeZoneName', 'nafisRegistrationNo', 'licenceAuthority', 'licenceNumber',
    ].every((field) => isText(data[field]))
    && moneyPattern.test(data.allowance)
    && [
      'dateOfBirth', 'terminationDate', 'visaExpiry', 'passportExpiry', 'emiratesIdExpiry',
      'labourCardExpiry', 'licenceExpiry',
    ].every((field) => isDate(data[field]))
    && genders.has(data.gender)
    && maritalStatuses.has(data.maritalStatus)
    && visaTypes.has(data.visaType)
    && workLocationTypes.has(data.workLocationType)
    && typeof data.probationExtended === 'boolean'
    && instantPattern.test(data.createdAt)
}

function parseAdminDetail(data) {
  if (!exactKeys(data, adminDetailKeys) || !validDetailFields(data)) {
    throw invalidEmployeeResponse()
  }
  return Object.freeze({ ...data })
}

function selfAsDetail(data) {
  return {
    ...data,
    reportingManagerId: null,
    active: true,
    updatedAt: '2000-01-01T00:00:00.000Z',
    createdAt: '2000-01-01T00:00:00.000Z',
  }
}

function parseSelf(data) {
  const manager = data?.reportingManager
  if (
    !exactKeys(data, selfKeys)
    || !validDetailFields(selfAsDetail(data))
    || manager !== null && (
      !exactKeys(manager, ['id', 'name', 'jobTitle'])
      || !isUuid(manager.id)
      || !isText(manager.name)
      || !isText(manager.jobTitle)
    )
  ) throw invalidEmployeeResponse()
  return Object.freeze({
    ...data,
    reportingManager: manager === null ? null : Object.freeze({ ...manager }),
  })
}

function parseDirectReport(data) {
  if (
    !exactKeys(data, directReportKeys)
    || !isUuid(data.id)
    || !['empNo', 'name', 'photoUrl', 'jobTitle', 'department']
      .every((field) => isText(data[field]))
    || !isDate(data.employmentStartDate)
    || !isDate(data.probationEndDate)
    || !statuses.has(data.employmentStatus)
  ) throw invalidEmployeeResponse()
  return Object.freeze({ ...data })
}

function parseHistory(data) {
  if (
    !exactKeys(data, historyKeys)
    || !isUuid(data.id)
    || !isUuid(data.employeeId)
    || !instantPattern.test(data.changedAt)
    || data.changedByAppUserId !== null && !isUuid(data.changedByAppUserId)
    || !changeTypes.has(data.changeType)
    || !['oldValue', 'newValue', 'reason'].every((field) => isText(data[field]))
  ) throw invalidEmployeeResponse()
  return Object.freeze({ ...data })
}

function parsePage(page) {
  if (
    !exactKeys(page, ['limit', 'nextCursor', 'hasMore'])
    || !Number.isInteger(page.limit)
    || page.limit < 1
    || page.limit > 100
    || page.nextCursor !== null && (typeof page.nextCursor !== 'string' || !page.nextCursor)
    || typeof page.hasMore !== 'boolean'
    || page.hasMore !== (page.nextCursor !== null)
  ) throw invalidEmployeeResponse()
  return Object.freeze({ ...page })
}

function queryString(options, allowed) {
  if (!isRecord(options) || Object.keys(options).some((key) => !allowed.has(key))) {
    throw new TypeError('Invalid employee query')
  }
  const parameters = new URLSearchParams()
  for (const [key, value] of Object.entries(options)) {
    if (value === undefined || key === 'signal') continue
    if (key === 'limit' && (!Number.isInteger(value) || value < 1 || value > 100)) {
      throw new TypeError('Invalid employee query')
    }
    if (key === 'active' && typeof value !== 'boolean') {
      throw new TypeError('Invalid employee query')
    }
    if (['search', 'department'].includes(key) && (
      typeof value !== 'string'
      || !value.trim()
      || value.trim().length > (key === 'search' ? 100 : 200)
    )) throw new TypeError('Invalid employee query')
    if (key === 'employmentStatus' && !statuses.has(value)) {
      throw new TypeError('Invalid employee query')
    }
    if (key === 'reportingManagerId' && value !== 'null' && !isUuid(value)) {
      throw new TypeError('Invalid employee query')
    }
    if (key === 'employeeId' && !isUuid(value)) throw new TypeError('Invalid employee query')
    if (key === 'changeType' && !changeTypes.has(value)) {
      throw new TypeError('Invalid employee query')
    }
    if (['changedFrom', 'changedTo'].includes(key) && !instantPattern.test(value)) {
      throw new TypeError('Invalid employee query')
    }
    if (['cursor', 'sort'].includes(key) && (typeof value !== 'string' || !value)) {
      throw new TypeError('Invalid employee query')
    }
    const normalized = ['search', 'department'].includes(key)
      ? value.normalize('NFC').trim()
      : String(value)
    parameters.set(key, normalized)
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

function collection(response, parser) {
  if (!Array.isArray(response.data)) throw invalidEmployeeResponse()
  return Object.freeze({
    data: Object.freeze(response.data.map(parser)),
    page: parsePage(response.page),
  })
}

const employeeQueryKeys = new Set([
  'limit', 'cursor', 'search', 'employmentStatus', 'department', 'active',
  'reportingManagerId', 'sort',
])
const directReportQueryKeys = new Set([
  'limit', 'cursor', 'search', 'employmentStatus', 'sort',
])
const branchHistoryQueryKeys = new Set([
  'limit', 'cursor', 'employeeId', 'changeType', 'changedFrom', 'changedTo', 'sort',
])
const employeeHistoryQueryKeys = new Set(['limit', 'cursor', 'sort'])

export async function readEmployees(authentication, branchId, options = {}) {
  if (!isUuid(branchId)) throw new TypeError('Invalid branch ID')
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/employees${queryString(query, employeeQueryKeys)}`,
    {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      signal,
    },
  )
  return collection(response, parseAdminList)
}

export async function readEmployee(authentication, branchId, employeeId, { signal } = {}) {
  if (!isUuid(branchId) || !isUuid(employeeId)) throw new TypeError('Invalid employee ID')
  const { data } = await authentication.request(`/api/v1/employees/${employeeId}`, {
    access: 'protected',
    headers: { 'X-Workloop-Branch-ID': branchId },
    signal,
  })
  const employee = parseAdminDetail(data)
  if (employee.id !== employeeId) throw invalidEmployeeResponse()
  return employee
}

export async function readEmployeeSelf(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/employees/self', {
    access: 'protected', signal,
  })
  return parseSelf(data)
}

export async function readDirectReports(authentication, options = {}) {
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/employees/direct-reports${queryString(query, directReportQueryKeys)}`,
    { access: 'protected', signal },
  )
  return collection(response, parseDirectReport)
}

export async function readBranchJobHistory(authentication, branchId, options = {}) {
  if (!isUuid(branchId)) throw new TypeError('Invalid branch ID')
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/employee-job-history${queryString(query, branchHistoryQueryKeys)}`,
    {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      signal,
    },
  )
  return collection(response, parseHistory)
}

export async function readEmployeeJobHistory(
  authentication,
  branchId,
  employeeId,
  options = {},
) {
  if (!isUuid(branchId) || !isUuid(employeeId)) throw new TypeError('Invalid employee ID')
  const { signal, ...query } = options
  const response = await authentication.request(
    `/api/v1/employees/${employeeId}/job-history${queryString(query, employeeHistoryQueryKeys)}`,
    {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      signal,
    },
  )
  const parsed = collection(response, parseHistory)
  if (parsed.data.some((entry) => entry.employeeId !== employeeId)) {
    throw invalidEmployeeResponse()
  }
  return parsed
}
