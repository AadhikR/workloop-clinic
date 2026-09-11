import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createEmployee,
  importEmployees,
  readBranchJobHistory,
  readDirectReports,
  readEmployee,
  readEmployeeJobHistory,
  readEmployees,
  readEmployeeSelf,
  updateEmployee,
} from '../migration/src/employeeApi.js'

const branchId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const employeeId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c3'
const managerId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c4'
const historyId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c5'
const idempotencyKey = '7f000000-0000-4000-8000-000000000002'

const listEmployee = {
  id: employeeId,
  empNo: 'E-001',
  name: 'Synthetic Employee',
  photoUrl: '',
  workEmail: 'employee@example.test',
  jobTitle: 'Nurse',
  department: 'Clinical',
  reportingManagerId: managerId,
  employmentStartDate: '2025-01-02',
  probationEndDate: null,
  employmentStatus: 'active',
  active: true,
  basicSalary: '10000.00',
  housingAllowance: '1000.00',
  transportAllowance: '500.00',
  otherAllowances: '0.00',
  bankName: 'Synthetic Bank',
  updatedAt: '2026-09-10T12:30:45.123Z',
}

const detail = {
  ...listEmployee,
  molId: 'MOL-001',
  bankRoutingCode: 'BANK-A',
  iban: 'AE000000000000000000001',
  allowance: '250.00',
  personalEmail: 'personal@example.test',
  phone: '+971500000001',
  dateOfBirth: '1990-01-01',
  gender: 'female',
  maritalStatus: 'single',
  homeCountryAddress: 'Synthetic address',
  emergencyContactName: 'Synthetic Contact',
  emergencyContactRelationship: 'Sibling',
  emergencyContactPhone: '+971500000002',
  probationExtended: false,
  terminationDate: null,
  terminationReason: '',
  otherAllowancesLabel: '',
  bankAccountHolder: 'Synthetic Employee',
  nationality: 'Synthetic',
  visaType: 'employment_visa',
  visaNumber: 'VISA-001',
  visaExpiry: null,
  passportNumber: 'P-001',
  passportExpiry: null,
  emiratesId: '784-0000-0000000-1',
  emiratesIdExpiry: null,
  labourCardNumber: 'LC-001',
  labourCardExpiry: null,
  sponsoringEntity: 'Horizon Clinic',
  workLocationType: 'mainland',
  freeZoneName: '',
  nafisRegistrationNo: '',
  licenceAuthority: 'DHA',
  licenceNumber: 'LIC-001',
  licenceExpiry: null,
  createdAt: '2026-09-10T12:30:45.123Z',
}

const self = {
  ...detail,
  reportingManager: { id: managerId, name: 'Synthetic Manager', jobTitle: 'Manager' },
}
delete self.reportingManagerId
delete self.active
delete self.updatedAt
delete self.createdAt

const report = {
  id: employeeId,
  empNo: 'E-001',
  name: 'Synthetic Employee',
  photoUrl: '',
  jobTitle: 'Nurse',
  department: 'Clinical',
  employmentStartDate: '2025-01-02',
  probationEndDate: null,
  employmentStatus: 'active',
}

const history = {
  id: historyId,
  employeeId,
  changedAt: '2026-09-10T12:30:45.123Z',
  changedByAppUserId: null,
  changeType: 'title_change',
  oldValue: 'Assistant nurse',
  newValue: 'Nurse',
  reason: 'Synthetic promotion',
}

const page = { limit: 50, nextCursor: null, hasMore: false }

function client(response) {
  const requests = []
  return {
    requests,
    async request(path, options) {
      requests.push([path, options])
      return response
    },
  }
}

test('parses each exact employee projection and sends the canonical scope header', async () => {
  const controller = new AbortController()
  const listing = client({ data: [listEmployee], page })
  assert.deepEqual(
    await readEmployees(listing, branchId, { signal: controller.signal, search: ' Employee ' }),
    { data: [listEmployee], page },
  )
  assert.deepEqual(listing.requests, [[
    '/api/v1/employees?search=Employee',
    {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': branchId },
      signal: controller.signal,
    },
  ]])

  assert.deepEqual(await readEmployee(client({ data: detail }), branchId, employeeId), detail)
  assert.deepEqual(await readEmployeeSelf(client({ data: self })), self)
  assert.deepEqual(await readDirectReports(client({ data: [report], page })), {
    data: [report], page,
  })
  assert.deepEqual(await readBranchJobHistory(client({ data: [history], page }), branchId), {
    data: [history], page,
  })
  assert.deepEqual(
    await readEmployeeJobHistory(client({ data: [history], page }), branchId, employeeId),
    { data: [history], page },
  )
})

test('keeps staff reads selector-free and binds admin filters to the server request', async () => {
  const reportsClient = client({ data: [report], page })
  await readDirectReports(reportsClient, {
    employmentStatus: 'active', search: 'Nurse', sort: 'name',
  })
  assert.deepEqual(reportsClient.requests[0][1].headers, undefined)
  assert.equal(
    reportsClient.requests[0][0],
    '/api/v1/employees/direct-reports?employmentStatus=active&search=Nurse&sort=name',
  )

  const historyClient = client({ data: [history], page })
  await readBranchJobHistory(historyClient, branchId, {
    employeeId, changeType: 'title_change', changedFrom: '2026-09-01T00:00:00.000Z',
  })
  assert.match(historyClient.requests[0][0], /employeeId=de0fb0c1/)
  assert.match(historyClient.requests[0][0], /changeType=title_change/)
})

test('rejects snake case, leaked fields, missing fields, and silently altered types', async () => {
  const invalid = [
    { ...listEmployee, employee_id: employeeId },
    Object.fromEntries(Object.entries(listEmployee).filter(([key]) => key !== 'bankName')),
    { ...listEmployee, basicSalary: 10000 },
    { ...listEmployee, employmentStatus: 'Active' },
    { ...report, phone: '+971500000001' },
    { ...history, changed_by: 'admin@example.test' },
  ]
  await assert.rejects(
    readEmployees(client({ data: [invalid[0]], page }), branchId),
    /invalid employee response/i,
  )
  await assert.rejects(
    readEmployees(client({ data: [invalid[1]], page }), branchId),
    /invalid employee response/i,
  )
  await assert.rejects(
    readEmployees(client({ data: [invalid[2]], page }), branchId),
    /invalid employee response/i,
  )
  await assert.rejects(
    readEmployees(client({ data: [invalid[3]], page }), branchId),
    /invalid employee response/i,
  )
  await assert.rejects(
    readDirectReports(client({ data: [invalid[4]], page })),
    /invalid employee response/i,
  )
  await assert.rejects(
    readBranchJobHistory(client({ data: [invalid[5]], page }), branchId),
    /invalid employee response/i,
  )
})

test('rejects unknown and malformed employee queries before transport', async () => {
  const authentication = client({ data: [listEmployee], page })
  await assert.rejects(
    readEmployees(authentication, branchId, { companyId: branchId }),
    /invalid employee query/i,
  )
  await assert.rejects(
    readEmployees(authentication, branchId, { employmentStatus: 'Active' }),
    /invalid employee query/i,
  )
  await assert.rejects(
    readBranchJobHistory(authentication, branchId, { changedFrom: '2026-09-10' }),
    /invalid employee query/i,
  )
  await assert.rejects(
    readEmployeeJobHistory(authentication, branchId, employeeId, { employeeId }),
    /invalid employee query/i,
  )
  assert.deepEqual(authentication.requests, [])
})

test('rejects a detail or job-history response for a different employee', async () => {
  const otherId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c9'
  await assert.rejects(
    readEmployee(client({ data: { ...detail, id: otherId } }), branchId, employeeId),
    /invalid employee response/i,
  )
  await assert.rejects(
    readEmployeeJobHistory(
      client({ data: [{ ...history, employeeId: otherId }], page }),
      branchId,
      employeeId,
    ),
    /invalid employee response/i,
  )
})

test('sends strict employee create, edit, and import mutations', async () => {
  const created = client({
    data: detail,
    status: 201,
    location: `/api/v1/employees/${employeeId}`,
  })
  await createEmployee(created, branchId, {
    name: 'Synthetic Employee',
    molId: '10003048635715',
    department: 'Clinical',
    workEmail: 'employee@example.test',
    basicSalary: '10000.00',
  }, { idempotencyKey })
  assert.deepEqual(created.requests[0][1].headers, {
    'X-Workloop-Branch-ID': branchId,
    'Idempotency-Key': idempotencyKey,
  })

  const updated = client({ data: detail, status: 200, location: null })
  await updateEmployee(updated, branchId, employeeId, {
    expectedUpdatedAt: detail.updatedAt,
    name: 'Synthetic Employee',
  })
  assert.equal(updated.requests[0][1].method, 'PATCH')

  const rows = [{
    rowNumber: 2,
    empNo: 'E-001',
    name: 'Synthetic Employee',
    molId: '10003048635715',
    bankName: 'Synthetic Bank',
    bankRoutingCode: '123456789',
    iban: 'AE000000000000000000001',
    basicSalary: '10000.00',
    allowance: '250.00',
  }]
  const imported = client({
    data: { createdCount: 1, rows: [{ rowNumber: 2, employeeId }] },
    status: 201,
    location: null,
  })
  assert.deepEqual(await importEmployees(imported, branchId, rows, { idempotencyKey }), {
    createdCount: 1,
    rows: [{ rowNumber: 2, employeeId }],
  })
})

test('rejects unsupported employee writes before transport', async () => {
  const authentication = client({ data: detail, status: 200, location: null })
  await assert.rejects(
    createEmployee(authentication, branchId, {
      name: 'Synthetic Employee', molId: '10003048635715', department: 'Clinical', active: true,
    }, { idempotencyKey }),
    /invalid employee mutation/i,
  )
  await assert.rejects(
    createEmployee(authentication, branchId, {
      name: 'Synthetic Employee', molId: 'not-a-mol-id', department: 'Clinical',
      bankRoutingCode: '12',
    }, { idempotencyKey }),
    /invalid employee mutation/i,
  )
  await assert.rejects(
    updateEmployee(authentication, branchId, employeeId, {
      expectedUpdatedAt: detail.updatedAt, jobTitle: 'Director',
    }),
    /invalid employee mutation/i,
  )
  await assert.rejects(
    updateEmployee(authentication, branchId, employeeId, {
      expectedUpdatedAt: detail.updatedAt, personalEmail: 'invalid',
    }),
    /invalid employee mutation/i,
  )
  await assert.rejects(
    importEmployees(authentication, branchId, [], { idempotencyKey }),
    /invalid employee mutation/i,
  )
  assert.deepEqual(authentication.requests, [])
})
