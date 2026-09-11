import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createDepartment,
  createStaffingRule,
  deleteDepartment,
  deleteStaffingRule,
  departmentSnapshot,
  readAllDepartments,
  readDepartments,
  readStaffingRules,
  staffingRuleSnapshot,
  updateDepartment,
  updateStaffingRule,
} from '../migration/src/departmentApi.js'

const branchId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const departmentId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d1'
const ruleId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d2'
const key = '7e000000-0000-4000-8000-000000000001'
const department = {
  id: departmentId,
  name: 'Clinical',
  parentId: null,
  headEmployeeId: null,
  color: '#336699',
  description: 'Patient care',
  sortOrder: 1,
  createdAt: '2026-09-11T08:00:00.000Z',
}
const rule = {
  id: ruleId,
  department: 'Clinical',
  shiftCategory: 'morning',
  minStaff: 3,
  effectiveFrom: '2026-09-01',
  effectiveTo: null,
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

test('parses exact department and staffing projections with branch scope', async () => {
  const departmentClient = client({ data: [department], page })
  assert.deepEqual(await readDepartments(departmentClient, branchId), {
    data: [department], page,
  })
  assert.equal(departmentClient.requests[0][1].headers['X-Workloop-Branch-ID'], branchId)

  const staffingClient = client({ data: [rule], page })
  assert.deepEqual(await readStaffingRules(staffingClient, branchId, {
    department: ' Clinical ', effectiveOn: '2026-09-11',
  }), { data: [rule], page })
  assert.equal(
    staffingClient.requests[0][0],
    '/api/v1/department-staffing-rules?department=Clinical&effectiveOn=2026-09-11',
  )
})

test('rejects leaked, missing, snake case, and malformed fields', async () => {
  for (const value of [
    { ...department, companyId: branchId },
    { ...department, head_employee_id: null },
    { ...department, sortOrder: '1' },
  ]) {
    await assert.rejects(
      readDepartments(client({ data: [value], page }), branchId),
      /invalid department response/i,
    )
  }
  for (const value of [
    { ...rule, branchId },
    { ...rule, shiftCategory: 'day' },
    { ...rule, minStaff: -1 },
  ]) {
    await assert.rejects(
      readStaffingRules(client({ data: [value], page }), branchId),
      /invalid department response/i,
    )
  }
})

test('loads all pages without accepting duplicate rows or cursors', async () => {
  const secondId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698d3'
  const authentication = {
    async request(path) {
      if (path === '/api/v1/departments?limit=100') {
        return { data: [department], page: { limit: 100, nextCursor: 'next', hasMore: true } }
      }
      return {
        data: [{ ...department, id: secondId, name: 'Support' }],
        page: { limit: 100, nextCursor: null, hasMore: false },
      }
    },
  }
  assert.deepEqual((await readAllDepartments(authentication, branchId)).map(({ id }) => id), [
    departmentId, secondId,
  ])
})

test('sends snapshots, rename idempotency, and create-only staffing requests', async () => {
  const createdDepartment = client({
    data: department, status: 201, location: `/api/v1/departments/${departmentId}`,
  })
  await createDepartment(createdDepartment, branchId, {
    name: 'Clinical', parentId: null, headEmployeeId: null,
    color: '#336699', description: 'Patient care', sortOrder: 1,
  })
  assert.equal(createdDepartment.requests[0][1].method, 'POST')

  const renamed = client({ data: { ...department, name: 'Care' }, replayed: false })
  await updateDepartment(renamed, branchId, departmentId, {
    name: 'Care', expected: departmentSnapshot(department),
  }, { idempotencyKey: key })
  assert.equal(renamed.requests[0][1].headers['Idempotency-Key'], key)
  assert.deepEqual(renamed.requests[0][1].json.expected, departmentSnapshot(department))

  const deletedDepartment = client({ data: null, status: 204 })
  await deleteDepartment(deletedDepartment, branchId, department)
  assert.deepEqual(deletedDepartment.requests[0][1].json, {
    expected: departmentSnapshot(department),
  })

  const createdRule = client({
    data: rule, status: 201, location: `/api/v1/department-staffing-rules/${ruleId}`,
  })
  await createStaffingRule(createdRule, branchId, staffingRuleSnapshot(rule))
  assert.equal(createdRule.requests[0][1].method, 'POST')

  const updatedRule = client({ data: { ...rule, minStaff: 4 } })
  await updateStaffingRule(updatedRule, branchId, rule, {
    minStaff: 4, expected: staffingRuleSnapshot(rule),
  })
  assert.deepEqual(updatedRule.requests[0][1].json.expected, staffingRuleSnapshot(rule))

  const deletedRule = client({ data: null, status: 204 })
  await deleteStaffingRule(deletedRule, branchId, rule)
  assert.deepEqual(deletedRule.requests[0][1].json, { expected: staffingRuleSnapshot(rule) })
})

test('rejects malformed queries and mutations before transport', async () => {
  const authentication = client({ data: [department], page })
  await assert.rejects(
    readDepartments(authentication, branchId, { parentId: 'foreign' }),
    /invalid department query/i,
  )
  await assert.rejects(
    readStaffingRules(authentication, branchId, { shiftCategory: 'day' }),
    /invalid staffing query/i,
  )
  await assert.rejects(
    updateDepartment(authentication, branchId, departmentId, {
      name: 'Care', expected: departmentSnapshot(department),
    }),
    /invalid idempotency key/i,
  )
  await assert.rejects(
    createDepartment(authentication, branchId, { companyId: branchId, name: 'Care' }),
    /invalid department mutation/i,
  )
  assert.deepEqual(authentication.requests, [])
})
