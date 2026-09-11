const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const uuid4Pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
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
const initialStatuses = new Set(['active', 'probation', 'on_leave'])

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
const createKeys = [
  'empNo', 'name', 'photoUrl', 'workEmail', 'jobTitle', 'department',
  'reportingManagerId', 'employmentStartDate', 'probationEndDate', 'employmentStatus',
  'basicSalary', 'housingAllowance', 'transportAllowance', 'otherAllowances', 'bankName',
  'molId', 'bankRoutingCode', 'iban', 'allowance', 'personalEmail', 'phone', 'dateOfBirth',
  'gender', 'maritalStatus', 'homeCountryAddress', 'emergencyContactName',
  'emergencyContactRelationship', 'emergencyContactPhone', 'probationExtended',
  'otherAllowancesLabel', 'bankAccountHolder', 'nationality', 'visaType', 'visaNumber',
  'visaExpiry', 'passportNumber', 'passportExpiry', 'emiratesId', 'emiratesIdExpiry',
  'labourCardNumber', 'labourCardExpiry', 'sponsoringEntity', 'workLocationType',
  'freeZoneName', 'nafisRegistrationNo', 'licenceAuthority', 'licenceNumber', 'licenceExpiry',
]
const updateKeys = [
  'expectedUpdatedAt', 'empNo', 'name', 'photoUrl', 'molId', 'bankName',
  'bankRoutingCode', 'bankAccountHolder', 'iban', 'personalEmail', 'phone', 'dateOfBirth',
  'gender', 'maritalStatus', 'homeCountryAddress', 'emergencyContactName',
  'emergencyContactRelationship', 'emergencyContactPhone', 'employmentStartDate',
  'nationality', 'visaType', 'visaNumber', 'visaExpiry', 'passportNumber', 'passportExpiry',
  'emiratesId', 'emiratesIdExpiry', 'labourCardNumber', 'labourCardExpiry',
  'sponsoringEntity', 'workLocationType', 'freeZoneName', 'nafisRegistrationNo',
  'licenceAuthority', 'licenceNumber', 'licenceExpiry',
]
const importKeys = [
  'rowNumber', 'empNo', 'name', 'molId', 'bankName', 'bankRoutingCode', 'iban',
  'basicSalary', 'allowance',
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

function invalidEmployeeMutation() {
  return new TypeError('Invalid employee mutation')
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

function requireMutation(value, allowed, required) {
  if (
    !isRecord(value)
    || Object.keys(value).some((key) => !allowed.includes(key))
    || required.some((key) => !Object.hasOwn(value, key))
  ) throw invalidEmployeeMutation()
}

function validateTextField(value, { empty = true, maximum = 200 } = {}) {
  return typeof value === 'string'
    && value.trim().length <= maximum
    && (empty || Boolean(value.trim()))
}

const mutationTextLimits = new Map([
  ['photoUrl', 2048],
  ['workEmail', 254],
  ['personalEmail', 254],
  ['phone', 100],
  ['homeCountryAddress', 2000],
  ['emergencyContactPhone', 100],
])

const mutationNonTextKeys = new Set([
  'reportingManagerId', 'employmentStartDate', 'probationEndDate', 'employmentStatus',
  'basicSalary', 'housingAllowance', 'transportAllowance', 'otherAllowances', 'allowance',
  'dateOfBirth', 'gender', 'maritalStatus', 'probationExtended', 'visaType', 'visaExpiry',
  'passportExpiry', 'emiratesIdExpiry', 'labourCardExpiry', 'workLocationType',
  'licenceExpiry',
])

function validateMutationText(value, keys, requiredNonempty = new Set()) {
  for (const key of keys) {
    if (!Object.hasOwn(value, key) || mutationNonTextKeys.has(key)) continue
    if (!validateTextField(value[key], {
      empty: !requiredNonempty.has(key),
      maximum: mutationTextLimits.get(key) ?? 200,
    })) throw invalidEmployeeMutation()
  }
}

function validateMutationFormats(value) {
  if (Object.hasOwn(value, 'molId') && !/^\d{10,15}$/.test(value.molId.trim())) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'bankRoutingCode')
    && value.bankRoutingCode.trim() && !/^\d{9}$/.test(value.bankRoutingCode.trim())) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'iban')
    && value.iban.trim() && !/^AE\d{21}$/.test(value.iban.trim())) {
    throw invalidEmployeeMutation()
  }
  for (const key of ['workEmail', 'personalEmail']) {
    if (Object.hasOwn(value, key)
      && value[key].trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value[key].trim())) {
      throw invalidEmployeeMutation()
    }
  }
}

function validateCreateMutation(value) {
  requireMutation(value, createKeys, ['name', 'molId', 'department'])
  validateMutationText(value, createKeys, new Set(['name', 'molId', 'department']))
  validateMutationFormats(value)
  if (Object.hasOwn(value, 'reportingManagerId')
    && value.reportingManagerId !== null && !isUuid(value.reportingManagerId)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'employmentStatus') && !initialStatuses.has(value.employmentStatus)) {
    throw invalidEmployeeMutation()
  }
  for (const key of ['basicSalary', 'housingAllowance', 'transportAllowance', 'otherAllowances', 'allowance']) {
    if (Object.hasOwn(value, key) && !moneyPattern.test(value[key])) throw invalidEmployeeMutation()
  }
  for (const key of [
    'employmentStartDate', 'probationEndDate', 'dateOfBirth', 'visaExpiry', 'passportExpiry',
    'emiratesIdExpiry', 'labourCardExpiry', 'licenceExpiry',
  ]) {
    if (Object.hasOwn(value, key) && !isDate(value[key])) throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'gender') && !genders.has(value.gender)) throw invalidEmployeeMutation()
  if (Object.hasOwn(value, 'maritalStatus') && !maritalStatuses.has(value.maritalStatus)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'visaType') && !visaTypes.has(value.visaType)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'workLocationType') && !workLocationTypes.has(value.workLocationType)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'probationExtended') && typeof value.probationExtended !== 'boolean') {
    throw invalidEmployeeMutation()
  }
}

function validateUpdateMutation(value) {
  requireMutation(value, updateKeys, ['expectedUpdatedAt'])
  if (!instantPattern.test(value.expectedUpdatedAt) || Object.keys(value).length < 2) {
    throw invalidEmployeeMutation()
  }
  validateMutationText(value, updateKeys, new Set(['name', 'molId']))
  validateMutationFormats(value)
  for (const key of [
    'dateOfBirth', 'employmentStartDate', 'visaExpiry', 'passportExpiry', 'emiratesIdExpiry',
    'labourCardExpiry', 'licenceExpiry',
  ]) {
    if (Object.hasOwn(value, key) && !isDate(value[key])) throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'gender') && !genders.has(value.gender)) throw invalidEmployeeMutation()
  if (Object.hasOwn(value, 'maritalStatus') && !maritalStatuses.has(value.maritalStatus)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'visaType') && !visaTypes.has(value.visaType)) {
    throw invalidEmployeeMutation()
  }
  if (Object.hasOwn(value, 'workLocationType') && !workLocationTypes.has(value.workLocationType)) {
    throw invalidEmployeeMutation()
  }
}

function validateImportRow(value) {
  if (!exactKeys(value, importKeys)
    || !Number.isInteger(value.rowNumber) || value.rowNumber < 1
    || !validateTextField(value.empNo, { empty: false })
    || !validateTextField(value.name, { empty: false })
    || !/^\d{10,15}$/.test(value.molId)
    || !validateTextField(value.bankName)
    || !/^(?:|\d{9})$/.test(value.bankRoutingCode)
    || !/^(?:|AE\d{21})$/.test(value.iban)
    || !moneyPattern.test(value.basicSalary)
    || !moneyPattern.test(value.allowance)
  ) throw invalidEmployeeMutation()
}

function parseImportResponse(value, inputRows) {
  if (!exactKeys(value, ['createdCount', 'rows'])
    || !Number.isInteger(value.createdCount)
    || value.createdCount !== inputRows.length
    || !Array.isArray(value.rows)
    || value.rows.length !== inputRows.length) throw invalidEmployeeResponse()
  const expectedRows = new Set(inputRows.map((row) => row.rowNumber))
  const rows = value.rows.map((row) => {
    if (!exactKeys(row, ['rowNumber', 'employeeId'])
      || !expectedRows.delete(row.rowNumber)
      || !isUuid(row.employeeId)) throw invalidEmployeeResponse()
    return Object.freeze({ ...row })
  })
  return Object.freeze({ createdCount: value.createdCount, rows: Object.freeze(rows) })
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

export async function readAllEmployees(authentication, branchId, options = {}) {
  if (Object.keys(options).some((key) => !['search', 'signal', 'sort'].includes(key))) {
    throw new TypeError('Invalid employee query')
  }
  const employees = []
  const identifiers = new Set()
  const cursors = new Set()
  let cursor
  do {
    const page = await readEmployees(authentication, branchId, { ...options, cursor, limit: 100 })
    for (const employee of page.data) {
      if (identifiers.has(employee.id)) throw invalidEmployeeResponse()
      identifiers.add(employee.id)
      employees.push(employee)
    }
    cursor = page.page.nextCursor ?? undefined
    if (cursor !== undefined) {
      if (cursors.has(cursor)) throw invalidEmployeeResponse()
      cursors.add(cursor)
    }
  } while (cursor !== undefined)
  return Object.freeze(employees)
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

export async function createEmployee(
  authentication,
  branchId,
  values,
  { idempotencyKey, signal } = {},
) {
  if (!isUuid(branchId) || !uuid4Pattern.test(idempotencyKey)) throw invalidEmployeeMutation()
  validateCreateMutation(values)
  const response = await authentication.request('/api/v1/employees', {
    access: 'protected',
    method: 'POST',
    headers: {
      'X-Workloop-Branch-ID': branchId,
      'Idempotency-Key': idempotencyKey,
    },
    json: values,
    signal,
  })
  const employee = parseAdminDetail(response.data)
  if (response.status !== 201 || response.location !== `/api/v1/employees/${employee.id}`) {
    throw invalidEmployeeResponse()
  }
  return employee
}

export async function updateEmployee(
  authentication,
  branchId,
  employeeId,
  values,
  { signal } = {},
) {
  if (!isUuid(branchId) || !isUuid(employeeId)) throw invalidEmployeeMutation()
  validateUpdateMutation(values)
  const response = await authentication.request(`/api/v1/employees/${employeeId}`, {
    access: 'protected',
    method: 'PATCH',
    headers: { 'X-Workloop-Branch-ID': branchId },
    json: values,
    signal,
  })
  const employee = parseAdminDetail(response.data)
  if (response.status !== 200 || employee.id !== employeeId) throw invalidEmployeeResponse()
  return employee
}

export async function importEmployees(
  authentication,
  branchId,
  rows,
  { idempotencyKey, signal } = {},
) {
  if (
    !isUuid(branchId)
    || !uuid4Pattern.test(idempotencyKey)
    || !Array.isArray(rows)
    || rows.length < 1
    || rows.length > 500
  ) throw invalidEmployeeMutation()
  rows.forEach(validateImportRow)
  const response = await authentication.request('/api/v1/employee-imports', {
    access: 'protected',
    method: 'POST',
    headers: {
      'X-Workloop-Branch-ID': branchId,
      'Idempotency-Key': idempotencyKey,
    },
    json: { rows },
    signal,
  })
  if (response.status !== 201 || response.location !== null) throw invalidEmployeeResponse()
  return parseImportResponse(response.data, rows)
}
