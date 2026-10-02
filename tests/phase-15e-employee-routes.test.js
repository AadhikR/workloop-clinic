import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { employeeRouteGroups } from '../src/employeeRoutes.js'
import { resolvePortalRoute } from '../src/portalRoutes.js'

const expectedRoutes = [
  ['/employee', []],
  ['/employee/profile', ['EmployeeDirectory']],
  ['/employee/leave', ['LeaveOverview']],
  ['/employee/time', ['PersonalAttendance', 'PersonalSchedule']],
  ['/employee/pay', ['Payslips', 'Expenses', 'Advances']],
  ['/employee/records', ['RecordsBenefits']],
  ['/employee/development', ['DevelopmentAssets', 'AppraisalsIncidents']],
  ['/employee/requests', ['LetterRequests']],
]

test('assigns every approved employee route to existing self-service views', () => {
  assert.deepEqual(
    employeeRouteGroups.map(({ path, views }) => [path, views]),
    expectedRoutes,
  )
})

test('opens employee routes and keeps manager and administrator routes denied', () => {
  for (const [path] of expectedRoutes) {
    assert.equal(resolvePortalRoute(path, 'employee').kind, path === '/employee' ? 'home' : 'portal')
    assert.equal(resolvePortalRoute(path, 'admin').kind, 'forbidden')
    assert.equal(resolvePortalRoute(path, 'manager').kind, 'forbidden')
  }
  assert.equal(resolvePortalRoute('/manager/expenses', 'employee').kind, 'forbidden')
  assert.equal(resolvePortalRoute('/admin/people', 'employee').kind, 'forbidden')
})

test('keeps employee composition on self clients and server-produced output', async () => {
  const [composer, employees, leave, attendance, schedule, expenses, records, development, appraisals, letters] = await Promise.all([
    readFile(new URL('../src/EmployeePortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/employeeApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/leaveBalanceApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/attendanceExceptionsApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/rosterApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/expenseApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/recordsBenefitsApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/developmentAssetsApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/appraisalsIncidentsApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/letterRequestsApi.js', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(composer, /fetch\(|XMLHttpRequest|OrganizationSettings|LeaveApprovals|AttendanceConfiguration|RosterDrafts|Payroll|WpsNafis|Offboarding|Reports/)
  assert.doesNotMatch(composer, /Blob\(|createObjectURL|employeeId\s*[=:]/)
  assert.match(employees, /\/api\/v1\/employees\/self/)
  assert.match(leave, /\/api\/v1\/leave\/balances\/self/)
  assert.match(attendance, /\/api\/v1\/attendance\/regularisations\/me/)
  assert.match(schedule, /\/api\/v1\/roster\/schedules\/self/)
  assert.match(expenses, /\/api\/v1\/expenses\/self/)
  assert.match(records, /\/api\/v1\/employee-documents\/self/)
  assert.match(development, /\/api\/v1\/(?:training-records|certifications)\/self/)
  assert.match(appraisals, /role === 'manager' \? 'direct-reports' : 'self'/)
  assert.match(appraisals, /\/api\/v1\/appraisals\/\$\{scope\}/)
  assert.match(letters, /\/api\/v1\/requests\/self/)
})

test('matches the completed 15E catalogue routes and evidence', async () => {
  const catalogue = JSON.parse(await readFile(new URL(
    '../docs/migration/phase-15/integration-catalogue.json', import.meta.url,
  )))
  const routes = catalogue.routeContracts.filter((route) => route.owner === '15E')
  assert.deepEqual(routes.map((route) => route.path), expectedRoutes.map(([path]) => path))
  for (const route of routes) {
    assert.ok(route.evidence?.includes('src/EmployeePortal.jsx'))
    assert.ok(route.evidence?.includes('tests/phase-15e-employee-routes.test.js'))
  }
  for (const record of catalogue.inventory.filter((item) => item.owner === '15E')) {
    assert.ok(record.evidence.includes('src/EmployeePortal.jsx'))
  }
  for (const golden of catalogue.goldenCases.filter((item) => item.owner === '15E')) {
    assert.ok(golden.evidence?.some((item) => [
      'tests/phase-15e-employee-routes.test.js',
      'tests/phase-15e-browser-check.mjs',
    ].includes(item)))
  }
})
