import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('migration payroll screens have no Supabase or legacy payroll path', async () => {
  for (const path of ['../migration/src/payrollApi.js', '../migration/src/Payroll.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|payrollCalculator|utils\/storage/i)
  }
})

test('legacy payroll draft readers and writers fail closed', async () => {
  const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  for (const name of [
    'cascadeBankRoutingCodeToDrafts',
    'getPayrolls',
    'savePayroll',
    'savePayrolls',
    'deletePayroll',
  ]) {
    assert.match(storage, new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?Payroll drafts have moved to the migration payroll workspace`))
  }
  const component = await readFile(new URL('../src/components/PayrollManager.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(component, /supabase|payrollCalculator|getPayrolls|savePayroll/i)
  assert.match(component, /migration payroll workspace/)
})
