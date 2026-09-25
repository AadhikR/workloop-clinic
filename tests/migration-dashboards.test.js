import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { parseDashboard, readDashboard } from '../migration/src/dashboardApi.js'

const branchId = 'c3000000-0000-4000-8000-000000000002'
const now = '2026-09-24T08:00:00.000Z'

const card = (code, target, value = 1) => ({
  code,
  label: code,
  value,
  unit: 'items',
  severity: 'info',
  comparison: null,
  drillDown: { code, target },
})

const cards = {
  admin: [
    card('activeHeadcount', 'employees'), card('finalizedPayroll', 'payroll', '1200.50'),
    card('wpsStatus', 'wps', 'confirmed'), card('nafisRatio', 'nafis', '2.00'),
    card('expiryDue', 'recordsBenefits'),
  ],
  clinical: [
    card('credentialsValid', 'developmentAssets'),
    card('credentialsExpiring', 'developmentAssets'),
    card('credentialsExpired', 'developmentAssets'), card('publishedRoster', 'roster'),
    card('staffingValidation', 'roster', 'passed'), card('onDuty', 'attendance'),
  ],
  self: [
    card('employmentStatus', 'profile', 'Active'), card('leaveBalance', 'leave', '12.50'),
    card('latestPayslip', 'payslips', '1200.50'),
    card('todayAttendance', 'attendance', 'PRESENT'),
    card('assignedAssets', 'developmentAssets'), card('todayShift', 'schedule', 'Day'),
  ],
}

function dashboard(kind) {
  return {
    asOf: now,
    businessDate: '2026-09-24',
    sourceVersion: `sha256:${'a'.repeat(64)}`,
    cards: cards[kind].map((value) => ({ ...value, drillDown: { ...value.drillDown } })),
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

test('dashboard parser enforces fixed cards and server-owned drill-downs', () => {
  assert.deepEqual(parseDashboard('admin', dashboard('admin')), dashboard('admin'))
  const forged = dashboard('admin')
  forged.cards[0] = { ...forged.cards[0], drillDown: { code: 'activeHeadcount', target: 'payroll' } }
  assert.throws(() => parseDashboard('admin', forged), /Invalid dashboard response/)
  assert.throws(
    () => parseDashboard('self', { ...dashboard('self'), employeeId: branchId }),
    /Invalid dashboard response/,
  )
})

test('dashboard client sends branch scope only for administrator dashboards', async () => {
  const admin = client(dashboard('admin'))
  const clinical = client(dashboard('clinical'))
  const self = client(dashboard('self'))
  await readDashboard(admin, 'admin', branchId)
  await readDashboard(clinical, 'clinical', branchId)
  await readDashboard(self, 'self', branchId)
  assert.deepEqual(admin.calls[0], {
    path: '/api/v1/dashboards/admin',
    options: { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId } },
  })
  assert.deepEqual(clinical.calls[0].options.headers, { 'X-Workloop-Branch-ID': branchId })
  assert.deepEqual(self.calls[0].options.headers, {})
})

test('migration dashboard path contains no legacy storage or browser calculations', async () => {
  const files = await Promise.all([
    readFile(new URL('../migration/src/dashboardApi.js', import.meta.url), 'utf8'),
    readFile(new URL('../migration/src/Dashboards.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../migration/src/OrganizationPanel.jsx', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(files.join('\n'), /supabase|payrollCalculator|notificationStorage/)
  assert.match(files[2], /kind="admin"/)
  assert.match(files[2], /kind="clinical"/)
  assert.match(files[2], /kind="self"/)
})
