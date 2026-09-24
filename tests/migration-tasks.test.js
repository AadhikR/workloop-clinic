import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { parseTaskCatalogue, readTasks } from '../migration/src/taskApi.js'

const branchId = 'c3000000-0000-4000-8000-000000000002'
const entityId = 'c3000000-0000-4000-8000-000000000003'
const now = '2026-09-24T08:00:00.000Z'
const task = {
  id: `leaveApproval:${entityId}`,
  entity: 'leaveRequest',
  entityId,
  title: 'Employee name',
  subtitle: 'Annual leave, 2.00 days',
  urgency: 'action',
  dueDate: null,
  createdAt: now,
  navigation: { screen: 'leaveApprovals' },
}

function catalogue(item = task) {
  return {
    categories: [{
      code: 'leaveApprovals', label: 'Leave requests', status: 'ok', count: 1, items: [item],
      errorCode: null,
    }],
    nextCursor: null,
    asOf: now,
    sourceVersion: `sha256:${'a'.repeat(64)}`,
  }
}

function client(response) {
  const calls = []
  return {
    calls,
    async request(path, options) {
      calls.push({ path, options })
      return { data: response }
    },
  }
}

test('task parser enforces the stable safe response shape', () => {
  assert.deepEqual(parseTaskCatalogue(catalogue()), catalogue())
  assert.throws(
    () => parseTaskCatalogue(catalogue({ ...task, employeeId: entityId })),
    /Invalid task response/,
  )
  assert.throws(
    () => parseTaskCatalogue(catalogue({ ...task, navigation: { screen: 'payroll', id: entityId } })),
    /Invalid task response/,
  )
})

test('task client sends only approved filters and derives branch scope by role', async () => {
  const admin = client(catalogue())
  const employee = client(catalogue())
  await readTasks(admin, 'admin', branchId, { category: 'leaveApprovals', limit: 25 })
  await readTasks(employee, 'employee', branchId, { urgency: 'action' })
  assert.equal(admin.calls[0].path, '/api/v1/tasks?category=leaveApprovals&limit=25')
  assert.deepEqual(admin.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
  assert.equal(employee.calls[0].path, '/api/v1/tasks?urgency=action')
  assert.deepEqual(employee.calls[0].options.headers, {})
})

test('migration task screen has no Supabase or retained task storage path', async () => {
  const files = await Promise.all([
    readFile(new URL('../migration/src/taskApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../migration/src/Tasks.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../migration/src/OrganizationPanel.jsx', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(files.join('\n'), /supabase|taskStorage/)
  assert.match(files[2], /<Tasks/)
})
