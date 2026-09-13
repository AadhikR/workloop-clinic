import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createLeaveType,
  deletePublicHoliday,
  parseLeaveSettings,
  parseLeaveType,
  parsePublicHoliday,
  readAllLeaveTypes,
  readLeaveTypes,
  seedPublicHolidays,
  updateLeaveSettings,
  updateLeaveType,
  updatePublicHoliday,
} from '../migration/src/leaveConfigurationApi.js'

const branchId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const typeId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d1'
const holidayId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d2'
const instant = '2026-09-13T08:00:00.000Z'
const settings = {
  id: 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d3',
  branchId,
  leaveYearType: 'calendar',
  weekendDefinition: 'fri-sat',
  carryForwardEnabled: true,
  carryForwardMaxDays: 15,
  approvalChain: '1-level',
  ramadanActive: false,
  ramadanStart: null,
  ramadanEnd: null,
  createdAt: instant,
  updatedAt: instant,
}
const leaveType = {
  id: typeId,
  branchId,
  code: 'ANNUAL',
  name: 'Annual Leave',
  color: '#1a56db',
  isPaid: true,
  isUnlimited: false,
  requiresApproval: true,
  requiresAttachment: false,
  requiresReason: false,
  minNoticeDays: 14,
  annualEntitlementDays: '30.00',
  accrualType: 'monthly',
  dayCountType: 'calendar',
  autoApprove: false,
  carryForwardAllowed: true,
  carryForwardMaxDays: 15,
  genderRestriction: null,
  minServiceMonths: 0,
  oncePerCareer: false,
  notDeductedFromAnnual: false,
  affectsPayroll: false,
  lawReference: 'Article 29',
  isActive: true,
  sortOrder: 0,
  probationEligible: false,
  createdAt: instant,
  updatedAt: instant,
}
const holiday = {
  id: holidayId,
  branchId,
  date: '2027-01-01',
  name: 'New Year',
  type: 'federal',
  year: 2027,
  createdAt: instant,
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

test('accepts only exact camelCase leave configuration projections', () => {
  assert.deepEqual(parseLeaveSettings(settings), settings)
  assert.deepEqual(parseLeaveType(leaveType), leaveType)
  assert.deepEqual(parsePublicHoliday(holiday), holiday)

  for (const malformed of [
    { ...settings, companyId: branchId },
    { ...settings, carry_forward_enabled: true },
    { ...settings, carryForwardMaxDays: '15' },
  ]) assert.throws(() => parseLeaveSettings(malformed), /invalid leave configuration response/i)

  assert.throws(
    () => parseLeaveType({ ...leaveType, annualEntitlementDays: 30 }),
    /invalid leave configuration response/i,
  )
  assert.throws(
    () => parsePublicHoliday({ ...holiday, year: 2026 }),
    /invalid leave configuration response/i,
  )
})

test('enforces branch scope and follows cursor pages without duplicates', async () => {
  const scoped = client({ data: [{ ...leaveType, branchId: holidayId }], page })
  await assert.rejects(readLeaveTypes(scoped, branchId), /invalid leave configuration response/i)

  const secondId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d4'
  const authentication = {
    async request(path) {
      if (path === '/api/v1/leave/types?limit=100') {
        return { data: [leaveType], page: { limit: 100, nextCursor: 'next', hasMore: true } }
      }
      return {
        data: [{ ...leaveType, id: secondId, code: 'SICK', name: 'Sick Leave' }],
        page: { limit: 100, nextCursor: null, hasMore: false },
      }
    },
  }
  assert.deepEqual((await readAllLeaveTypes(authentication, branchId)).map(({ id }) => id), [
    typeId, secondId,
  ])
})

test('sends optimistic versions and strict leave-type mutations as JSON', async () => {
  const settingsClient = client({ data: { ...settings, carryForwardMaxDays: 20 } })
  await updateLeaveSettings(settingsClient, branchId, {
    expectedUpdatedAt: instant,
    leaveYearType: 'calendar',
    weekendDefinition: 'fri-sat',
    carryForwardEnabled: true,
    carryForwardMaxDays: 20,
    approvalChain: '1-level',
    ramadanActive: false,
    ramadanStart: null,
    ramadanEnd: null,
  })
  assert.equal(settingsClient.requests[0][1].json.expectedUpdatedAt, instant)

  const createClient = client({ data: leaveType, status: 201 })
  await createLeaveType(createClient, branchId, {
    code: 'ANNUAL', name: 'Annual Leave', annualEntitlementDays: '30.00',
  })
  assert.equal(createClient.requests[0][1].method, 'POST')

  const updateClient = client({ data: { ...leaveType, name: 'Annual' } })
  await updateLeaveType(updateClient, branchId, typeId, {
    expectedUpdatedAt: instant, name: 'Annual',
  })
  assert.deepEqual(updateClient.requests[0][1].json, {
    expectedUpdatedAt: instant, name: 'Annual',
  })

  await assert.rejects(
    updateLeaveType(updateClient, branchId, typeId, { name: 'Annual' }),
    /invalid leave configuration mutation/i,
  )
  await assert.rejects(
    createLeaveType(createClient, branchId, {
      companyId: branchId, code: 'SICK', name: 'Sick', annualEntitlementDays: '90.00',
    }),
    /invalid leave configuration mutation/i,
  )
})

test('sends holiday snapshots and named seed payloads through JSON', async () => {
  const updateClient = client({ data: { ...holiday, name: 'New Year Day' } })
  await updatePublicHoliday(updateClient, branchId, holiday, { name: 'New Year Day' })
  assert.deepEqual(updateClient.requests[0][1].json, {
    expected: { date: holiday.date, name: holiday.name, type: holiday.type },
    name: 'New Year Day',
  })

  const deleteClient = client({ data: null, status: 204 })
  await deletePublicHoliday(deleteClient, branchId, holiday)
  assert.match(deleteClient.requests[0][0], /expectedDate=2027-01-01/)
  assert.match(deleteClient.requests[0][0], /expectedName=New\+Year/)
  assert.equal(deleteClient.requests[0][1].method, 'DELETE')

  const seedClient = client({ data: [holiday] })
  await seedPublicHolidays(seedClient, branchId, 2027, [{
    date: '2027-01-01', name: 'New Year', type: 'federal',
  }])
  assert.deepEqual(seedClient.requests[0][1].json, {
    year: 2027,
    holidays: [{ date: '2027-01-01', name: 'New Year', type: 'federal' }],
  })
  assert.equal(Object.hasOwn(seedClient.requests[0][1], 'body'), false)
})
