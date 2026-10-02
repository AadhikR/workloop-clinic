import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { administratorRouteGroups } from '../src/administratorRoutes.js'
import { resolvePortalRoute } from '../src/portalRoutes.js'

const expectedRoutes = [
  ['/admin', []],
  ['/admin/organization', ['OrganizationSettings', 'DepartmentManager']],
  ['/admin/people', ['EmployeeDirectory']],
  ['/admin/leave', ['LeaveConfiguration', 'LeaveOverview', 'LeaveApprovals']],
  ['/admin/attendance', [
    'AttendanceConfiguration',
    'AttendanceIngestion',
    'AttendanceCalculation',
    'AttendanceExceptions',
    'AttendancePeriods',
  ]],
  ['/admin/roster', ['RosterDrafts', 'ShiftSwapQueue']],
  ['/admin/payroll', ['Payroll', 'Expenses', 'Advances', 'Payslips', 'WpsNafis']],
  ['/admin/records', ['RecordsBenefits', 'LetterRequests', 'Offboarding']],
  ['/admin/development', ['DevelopmentAssets', 'AppraisalsIncidents']],
  ['/admin/reports', ['Reports']],
]

test('assigns every approved administrator route to its existing views', () => {
  assert.deepEqual(
    administratorRouteGroups.map(({ path, views }) => [path, views]),
    expectedRoutes,
  )
})

test('opens administrator routes while keeping later role routes unavailable', () => {
  for (const [path] of expectedRoutes) {
    assert.equal(resolvePortalRoute(path, 'admin').kind, path === '/admin' ? 'home' : 'portal')
    assert.equal(resolvePortalRoute(path, 'manager').kind, 'forbidden')
    assert.equal(resolvePortalRoute(path, 'employee').kind, 'forbidden')
  }
  assert.equal(resolvePortalRoute('/manager/time', 'manager').kind, 'unavailable')
  assert.equal(resolvePortalRoute('/employee/pay', 'employee').kind, 'unavailable')
})

test('keeps administrator composition on existing clients and server output', async () => {
  const [composer, reports, output, renderedOutput] = await Promise.all([
    readFile(new URL('../src/AdministratorPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/Reports.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/outputApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/renderedOutputApi.js', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(composer, /fetch\(|XMLHttpRequest|Blob\(|createObjectURL/)
  assert.match(reports, /downloadReportCsv/)
  assert.match(reports, /downloadReportPdf/)
  assert.match(output, /\/api\/v1\/exports\//)
  assert.match(renderedOutput, /\/api\/v1\/reports\//)
})

test('matches the completed 15C catalogue routes and evidence', async () => {
  const catalogue = JSON.parse(await readFile(new URL(
    '../docs/migration/phase-15/integration-catalogue.json', import.meta.url,
  )))
  const routes = catalogue.routeContracts.filter((route) => route.owner === '15C')
  assert.deepEqual(routes.map((route) => route.path), expectedRoutes.map(([path]) => path))
  for (const route of routes) {
    assert.ok(route.evidence?.includes('src/AdministratorPortal.jsx'))
    assert.ok(route.evidence?.includes('tests/phase-15c-administrator-routes.test.js'))
  }
  for (const record of catalogue.inventory.filter((item) => item.owner === '15C')) {
    assert.ok(record.evidence.includes('src/AdministratorPortal.jsx'))
  }
  for (const golden of catalogue.goldenCases.filter((item) => item.owner === '15C')) {
    assert.ok(golden.evidence?.some((item) => [
      'tests/phase-15c-administrator-routes.test.js',
      'tests/phase-15c-browser-check.mjs',
    ].includes(item)))
  }
})
