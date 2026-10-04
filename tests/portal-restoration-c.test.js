import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8')

test('leave administration restores the historical work areas around current clients', () => {
  const text = source('LeaveManager.jsx')
  for (const label of ['Overview', 'Requests', 'Calendar', 'Balances', 'Settings']) {
    assert.ok(text.includes(label), label)
  }
  for (const component of ['LeaveOverview', 'LeaveApprovals', 'LeaveConfiguration']) {
    assert.ok(text.includes(component), component)
  }
  assert.ok(source('LeaveApprovals.jsx').includes('Approval delegations'))
  assert.ok(source('LeaveConfiguration.jsx').includes('Public holidays'))
})

test('attendance restores focused operational views without biometric controls', () => {
  const text = source('AttendanceManager.jsx')
  for (const label of ['Dashboard', 'Manual Entry', 'Records', 'Absences', 'Overtime', 'Corrections', 'Periods', 'Settings']) {
    assert.ok(text.includes(label), label)
  }
  assert.ok(!source('AttendanceIngestion.jsx').includes('Biometric'))
  assert.ok(!source('AttendanceConfiguration.jsx').includes('Enable biometric API'))
})

test('roster restores shift templates, a monthly grid, publication, and swaps', () => {
  const text = source('RosterManager.jsx')
  for (const label of ['Shift Templates', 'Monthly Roster', 'Swap Requests']) {
    assert.ok(text.includes(label), label)
  }
  const roster = source('RosterDrafts.jsx')
  assert.ok(roster.includes('Monthly roster grid'))
  assert.ok(roster.includes('Publication gates'))
  assert.ok(roster.includes('Publish exact roster'))
  assert.ok(roster.includes('FormDialog'))
})

test('employee job editing uses the effective versioned shift assignment', () => {
  const text = source('EmployeeDirectory.jsx')
  assert.ok(text.includes('Effective default shift'))
  assert.ok(text.includes('readShiftAssignments'))
  assert.ok(text.includes('assignShift'))
  assert.ok(text.includes('expectedCurrentAssignmentId'))
  assert.ok(text.includes('expectedCurrentAssignmentUpdatedAt'))
})

test('department staffing follows the selected branch feature setting', () => {
  const text = source('DepartmentManager.jsx')
  assert.ok(text.includes('readBranch'))
  assert.ok(text.includes('enableStaffingRules'))
  assert.match(text, /enableStaffingRules[\s\S]*Staffing Rules/)
})

test('administrator routes use restored domain workspaces', () => {
  const text = source('AdministratorPortal.jsx')
  for (const component of ['LeaveManager', 'AttendanceManager', 'RosterManager']) {
    assert.ok(text.includes(component), component)
  }
})
