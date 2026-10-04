import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8')

test('company settings restore grouped cards, logo controls, and insurance policies', () => {
  const text = source('OrganizationSettings.jsx')
  for (const label of [
    'Employer information',
    'Payroll settings',
    'Work location and jurisdiction',
    'Modules and features',
    'Medical insurance policies',
    'WPS and SIF file reference',
    'Upload logo',
    'Remove logo',
  ]) assert.ok(text.includes(label), label)
  assert.ok(!text.includes('Enable biometric import'))
})

test('employee administration keeps child records in the selected employee editor', () => {
  const text = source('EmployeeDirectory.jsx')
  for (const label of [
    'Employee list',
    'Document expiry',
    'Terminated employees',
    'Personal',
    'Job and contract',
    'Salary and bank',
    'UAE compliance',
    'Documents',
    'Insurance',
    'Contracts',
    'Job history',
    'Offboarding',
  ]) assert.ok(text.includes(label), label)
  assert.ok(text.includes('saveEmployeeProfile'))
  assert.ok(text.includes('EmployeeRecordsEditor'))
})

test('new employee forms hide child tabs until creation succeeds', () => {
  const text = source('EmployeeDirectory.jsx')
  assert.match(text, /employee\?\.id\s*\?\s*employeeTabs/)
})

test('letter output is limited to completed standard letters for every staff role', () => {
  const text = source('LetterRequests.jsx')
  assert.match(text, /item\.requestKind === 'letter'/)
  assert.ok(!text.includes("account.role !== 'manager'"))
  assert.ok(text.includes('Request filters'))
})

test('records and offboarding accept selected employee context', () => {
  assert.ok(source('RecordsBenefits.jsx').includes('selectedEmployeeId'))
  assert.ok(source('Offboarding.jsx').includes('selectedEmployeeId'))
})

test('historical browser journey targets the restored branch settings form', () => {
  const text = readFileSync(new URL('../scripts/verify-phase-3g-browser.mjs', import.meta.url), 'utf8')
  assert.ok(text.includes('form.restoration-settings-sections'))
  assert.ok(!text.includes("name: 'Selected branch'"))
})
