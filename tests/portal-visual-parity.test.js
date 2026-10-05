import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('shares the historical retained-source layout across administrator, manager, and employee modules', async () => {
  const [administrator, manager, employee, css] = await Promise.all([
    readFile(new URL('../src/AdministratorPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/ManagerPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/EmployeePortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/index.css', import.meta.url), 'utf8'),
  ])

  assert.match(administrator, /className="portal-route administrator-route"/)
  assert.match(manager, /className="portal-route manager-route"/)
  assert.match(employee, /className="portal-route employee-route"/)
  assert.match(css, /Exact historical portal parity/)
  assert.match(css, /\.portal-route \.tabs/)
  assert.match(css, /\.portal-route \.expense-form/)
  assert.match(css, /\.portal-route \.table-wrap/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route \{[\s\S]*?gap: 16px;[\s\S]*?margin: 0;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal\[data-portal-role\] \.page-body \{[\s\S]*?padding: 20px 12px 28px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route \.tab-btn[\s\S]*?padding: 10px 18px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route th \{[\s\S]*?font-size: 11\.5px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route input,[\s\S]*?padding: 9px 13px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal\[data-portal-role\] \.portal-navigation\.sidebar-nav \{[\s\S]*?scrollbar-width: none;/)
  assert.match(css, /data-portal-role='manager'[\s\S]*height: 62px/)
})

test('pins every restored portal module to a current route and API client', async () => {
  const inventory = await readFile(new URL('../docs/migration/phase-15/PORTAL_UI_RESTORATION_INVENTORY.md', import.meta.url), 'utf8')

  assert.match(inventory, /a3b72a22924d1b56b5603ee8e0069ddecee65f43/)
  for (const route of [
    '/admin/payroll', '/admin/advances', '/admin/expenses', '/admin/leave',
    '/admin/attendance', '/admin/roster', '/admin/assets', '/admin/training',
    '/admin/appraisals', '/admin/incidents', '/admin/reports', '/admin/tasks',
    '/manager/leave-queue', '/manager/expense-queue', '/manager/appraisals',
    '/manager/schedule', '/manager/attendance', '/manager/payslips', '/manager/advances',
    '/manager/expenses', '/manager/training', '/manager/documents', '/manager/requests',
    '/manager/profile', '/manager/tasks', '/employee/leave', '/employee/schedule',
    '/employee/attendance', '/employee/payslips', '/employee/advances', '/employee/expenses',
    '/employee/training', '/employee/appraisals', '/employee/documents', '/employee/requests',
    '/employee/profile', '/employee/tasks',
  ]) assert.ok(inventory.includes(`\`${route}\``), `missing restoration inventory route ${route}`)

  for (const client of [
    'payrollApi.js', 'advanceApi.js', 'expenseApi.js', 'leaveRequestApi.js',
    'attendanceExceptionsApi.js', 'rosterApi.js', 'developmentAssetsApi.js',
    'appraisalsIncidentsApi.js', 'recordsBenefitsApi.js', 'letterRequestsApi.js',
    'reportApi.js', 'taskApi.js',
  ]) assert.ok(inventory.includes(`\`${client}\``), `missing restoration inventory client ${client}`)
})

test('restores the historical payroll workspace against FastAPI actions', async () => {
  const payroll = await readFile(new URL('../src/Payroll.jsx', import.meta.url), 'utf8')

  for (const marker of [
    'Payroll Runs', 'Repeat Last Payroll', 'New Payroll Run', 'Payroll History',
    'Payroll Run Details', 'Employee Salary Entries', 'Add allowance', 'Add deduction',
    'Submit for Approval', 'Approval History', 'Download Payslips',
  ]) assert.ok(payroll.includes(marker), `missing payroll structure: ${marker}`)
  assert.match(payroll, /readPayrollRuns/)
  assert.match(payroll, /createPayrollRun/)
  assert.match(payroll, /savePayrollEntries/)
  assert.match(payroll, /submitPayrollRun/)
  assert.match(payroll, /generatePayrollRun/)
  assert.match(payroll, /className="payroll-table table-wrap"/)
  assert.match(payroll, /PortalDialog/)
})

test('keeps advances and expenses as separate role-specific modules', async () => {
  const [advances, expenses] = await Promise.all([
    readFile(new URL('../src/Advances.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/Expenses.jsx', import.meta.url), 'utf8'),
  ])

  for (const marker of ['Pending Requests', 'Active Advances', 'Total Outstanding', 'All Advances', 'Repayment Schedule']) {
    assert.ok(advances.includes(marker), `missing advances structure: ${marker}`)
  }
  for (const marker of ['Pending Claims', 'Approved (Unpaid)', 'Total Paid', 'New Expense Claim', 'Expense Queue']) {
    assert.ok(expenses.includes(marker), `missing expenses structure: ${marker}`)
  }
  assert.doesNotMatch(advances, /Payroll Runs/)
  assert.doesNotMatch(expenses, /Salary Advances/)
  assert.match(advances, /readAdminAdvances/)
  assert.match(advances, /readSelfAdvances/)
  assert.match(expenses, /readAdminExpenses/)
  assert.match(expenses, /readManagerExpenses/)
  assert.match(expenses, /readSelfExpenses/)
})

test('retains each non-financial historical module instead of a generic placeholder', async () => {
  const expectations = new Map([
    ['EmployeeDirectory.jsx', ['Employee directory', 'Employee profile', 'Import employees']],
    ['DepartmentManager.jsx', ['Departments', 'Staffing rules']],
    ['LetterRequests.jsx', ['Letter and custom requests', 'Completed request source']],
    ['LeaveConfiguration.jsx', ['Leave configuration', 'Leave types', 'Public holidays']],
    ['LeaveOverview.jsx', ['Submit leave request', 'Request history', 'Request calendar']],
    ['LeaveApprovals.jsx', ['Approval delegations', 'Branch leave decisions', 'Leave Queue']],
    ['AttendanceConfiguration.jsx', ['Branch rules', 'Effective shift assignment']],
    ['AttendanceIngestion.jsx', ['Manual clock event', 'Recent raw events']],
    ['AttendanceExceptions.jsx', ['Pending corrections', 'Unresolved absences', 'Recent audit']],
    ['RosterDrafts.jsx', ['Monthly roster', 'Publication gates', 'Publication']],
    ['DevelopmentAssets.jsx', ['Asset Register', 'Assignment History', 'Training &amp; Certifications', 'CME targets']],
    ['AppraisalsIncidents.jsx', ['Appraisal cycles', 'Appraisal reviews', 'Incident status']],
    ['RecordsBenefits.jsx', ['Employee documents', 'Insurance administration', 'Employment contracts']],
    ['Offboarding.jsx', ['Offboarding and final settlement', 'Settlement preview']],
    ['Reports.jsx', ['Reports']],
    ['Tasks.jsx', ['Tasks']],
  ])

  for (const [file, markers] of expectations) {
    const source = await readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
    for (const marker of markers) assert.ok(source.includes(marker), `${file} is missing ${marker}`)
  }
})
