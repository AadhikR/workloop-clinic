import assert from 'node:assert/strict'
import test from 'node:test'

import {
  deleteDepartment,
  getDepartments,
  saveDepartment,
} from '../src/utils/departmentStorage.js'
import {
  deleteDeptStaffingRule,
  getDeptStaffingRules,
  saveDeptStaffingRule,
} from '../src/utils/staffingStorage.js'

const moved = /have moved to the migration settings screen/

test('freezes every legacy department reader and writer', async () => {
  await assert.rejects(getDepartments(), moved)
  await assert.rejects(saveDepartment({ name: 'Clinical' }), moved)
  await assert.rejects(deleteDepartment('synthetic-department'), moved)
})

test('freezes every legacy staffing reader and writer', async () => {
  await assert.rejects(getDeptStaffingRules(), moved)
  await assert.rejects(saveDeptStaffingRule({ department: 'Clinical' }), moved)
  await assert.rejects(deleteDeptStaffingRule('synthetic-rule'), moved)
})
