import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { managerRouteGroups } from '../src/managerRoutes.js'
import { resolvePortalRoute } from '../src/portalRoutes.js'

const expectedRoutes = [
  ['/manager', []],
  ['/manager/team', ['EmployeeDirectory']],
  ['/manager/leave', ['LeaveOverview', 'LeaveApprovals']],
  ['/manager/time', ['PersonalAttendance', 'PersonalSchedule']],
  ['/manager/expenses', ['Expenses']],
  ['/manager/development', ['DevelopmentAssets', 'AppraisalsIncidents']],
  ['/manager/requests', ['Advances', 'RecordsBenefits', 'LetterRequests']],
]

test('assigns every approved manager route to existing manager or self views', () => {
  assert.deepEqual(
    managerRouteGroups.map(({ path, views }) => [path, views]),
    expectedRoutes,
  )
})

test('opens manager routes and keeps administrator and employee routes denied or unavailable', () => {
  for (const [path] of expectedRoutes) {
    assert.equal(resolvePortalRoute(path, 'manager').kind, path === '/manager' ? 'home' : 'portal')
    assert.equal(resolvePortalRoute(path, 'admin').kind, 'forbidden')
    assert.equal(resolvePortalRoute(path, 'employee').kind, 'forbidden')
  }
  assert.equal(resolvePortalRoute('/admin/payroll', 'manager').kind, 'forbidden')
  assert.equal(resolvePortalRoute('/admin/records', 'manager').kind, 'forbidden')
  assert.equal(resolvePortalRoute('/employee/pay', 'employee').kind, 'unavailable')
})

test('keeps administrator-only views and browser authorization logic out of manager composition', async () => {
  const [composer, employeeApi, leaveApi, expenseApi, developmentApi, appraisalApi] = await Promise.all([
    readFile(new URL('../src/ManagerPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/employeeApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/leaveApprovalApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/expenseApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/developmentAssetsApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/appraisalsIncidentsApi.js', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(composer, /fetch\(|XMLHttpRequest|OrganizationSettings|AttendanceConfiguration|RosterDrafts|Payroll|WpsNafis|Offboarding|Reports/)
  assert.match(employeeApi, /\/api\/v1\/employees\/direct-reports/)
  assert.match(leaveApi, /\/api\/v1\/leave\/approvals\/queue/)
  assert.match(expenseApi, /\/api\/v1\/expenses\/manager-queue/)
  assert.match(developmentApi, /\/api\/v1\/(?:training-records|certifications)\/direct-reports/)
  assert.match(appraisalApi, /direct-reports/)
})

test('matches the completed 15D catalogue routes and evidence', async () => {
  const catalogue = JSON.parse(await readFile(new URL(
    '../docs/migration/phase-15/integration-catalogue.json', import.meta.url,
  )))
  const routes = catalogue.routeContracts.filter((route) => route.owner === '15D')
  assert.deepEqual(routes.map((route) => route.path), expectedRoutes.map(([path]) => path))
  for (const route of routes) {
    assert.ok(route.evidence?.includes('src/ManagerPortal.jsx'))
    assert.ok(route.evidence?.includes('tests/phase-15d-manager-routes.test.js'))
  }
  for (const record of catalogue.inventory.filter((item) => item.owner === '15D')) {
    assert.ok(record.evidence.includes('src/ManagerPortal.jsx'))
  }
  for (const golden of catalogue.goldenCases.filter((item) => item.owner === '15D')) {
    assert.ok(golden.evidence?.some((item) => [
      'tests/phase-15d-manager-routes.test.js',
      'tests/phase-15d-browser-check.mjs',
    ].includes(item)))
  }
})
