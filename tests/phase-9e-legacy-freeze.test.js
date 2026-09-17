import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('migration payroll owns automatic input refresh without Supabase', async () => {
  for (const path of ['../migration/src/payrollApi.js', '../migration/src/Payroll.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|leaveEngine|attendanceEngine|RosterManager|expenseStorage|advanceSchedule/i)
  }

  const api = await readFile(new URL('../migration/src/payrollApi.js', import.meta.url), 'utf8')
  assert.match(api, /automaticCodePattern/)
  assert.match(api, /sourceExplanations/)
})

test('legacy payroll automatic input readers are frozen', async () => {
  const component = await readFile(new URL('../src/components/PayrollEditor.jsx', import.meta.url), 'utf8')
  assert.match(component, /Automatic payroll inputs have moved to the migration payroll workspace/)
  for (const marker of [
    'getLeaveRequests()',
    'getAttendancePayrollData(payroll.period)',
    'getPublishedRosterForMonth(payroll.period)',
    'getApprovedUnpaidExpensesForPayroll',
    'getAdvancesDueForPayroll',
  ]) {
    assert.doesNotMatch(component, new RegExp(marker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})
