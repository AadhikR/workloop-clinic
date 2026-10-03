import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { employeeParityRoutes } from '../src/employeeRoutes.js'
import { resolvePortalRoute, roleNavigation } from '../src/portalRoutes.js'

const expectedNavigation = [
  ['/employee', 'Home'],
  ['/employee/leave', 'Leave'],
  ['/employee/schedule', 'Schedule'],
  ['/employee/attendance', 'Attendance'],
  ['/employee/payslips', 'Payslips'],
  ['/employee/advances', 'Advances'],
  ['/employee/expenses', 'Expenses'],
  ['/employee/training', 'Training'],
  ['/employee/appraisals', 'Appraisals'],
  ['/employee/documents', 'Documents'],
  ['/employee/tasks', 'Tasks'],
  ['/employee/requests', 'Requests'],
  ['/employee/profile', 'Profile'],
]

test('uses the historical employee module order and dedicated routes', () => {
  assert.deepEqual(roleNavigation('employee').map(({ path, title }) => [path, title]), expectedNavigation)
  assert.deepEqual(employeeParityRoutes.map(({ path }) => path), expectedNavigation.slice(2, 11).map(([path]) => path))
  for (const [path] of expectedNavigation) {
    assert.notEqual(resolvePortalRoute(path, 'employee').kind, 'not-found')
    assert.equal(resolvePortalRoute(path, 'admin').kind, 'forbidden')
    assert.equal(resolvePortalRoute(path, 'manager').kind, 'forbidden')
  }
})

test('keeps employee pages on self-scoped clients and excludes retired controls', async () => {
  const [portal, attendance, home, profile, tasks] = await Promise.all([
    readFile(new URL('../src/EmployeePortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/PersonalAttendance.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/EmployeeHome.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/EmployeeProfile.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/Tasks.jsx', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(portal, /AttendanceIngestion|AttendanceConfiguration|LeaveApprovals|Payroll|RosterDrafts/)
  assert.doesNotMatch(attendance, /<button[^>]*>Clock (?:In|Out)<|biometric/i)
  assert.match(home, /readEmployeeSelf|readDashboard|readSelfAssets/)
  assert.match(profile, /updateEmployeeSelfContact/)
  assert.match(tasks, /personalAttendance: '\/employee\/attendance'/)
})

test('includes responsive, reduced-motion, and print rules for the employee shell', async () => {
  const css = await readFile(new URL('../src/index.css', import.meta.url), 'utf8')
  assert.match(css, /data-portal-role='employee'[\s\S]*height: 62px/)
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/)
  assert.match(css, /@media print/)
})

test('keeps employee modules and leave history on the shared polished layout', async () => {
  const [css, leave] = await Promise.all([
    readFile(new URL('../src/index.css', import.meta.url), 'utf8'),
    readFile(new URL('../src/LeaveOverview.jsx', import.meta.url), 'utf8'),
  ])
  assert.match(css, /Employee portal visual refinement/)
  assert.match(css, /\.employee-route \.tabs/)
  assert.match(css, /\.employee-route \.expense-form/)
  assert.match(css, /\.leave-request-table/)
  assert.match(leave, /className="employee-module-toolbar leave-toolbar"/)
  assert.match(leave, /className="employee-panel leave-history-panel"/)
  assert.match(leave, /className="leave-request-table"/)
})
