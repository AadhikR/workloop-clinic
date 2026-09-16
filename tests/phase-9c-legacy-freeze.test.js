import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('migration advance screens have no Supabase or legacy advance path', async () => {
  for (const path of ['../migration/src/advanceApi.js', '../migration/src/Advances.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|from ['"].*advanceSchedule|utils\/storage/i)
  }
})

test('legacy advance writers fail closed while the payroll advance read remains available', async () => {
  const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  assert.match(storage, /Salary advance changes have moved to the migration advance workspace/)
  for (const name of [
    'withdrawEmployeeAdvance',
    'saveAdvance',
    'updateAdvanceBalance',
    'getAdvanceRepayments',
    'saveAdvanceRepayment',
  ]) {
    assert.match(storage, new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?advanceWritesMoved\\(\\)`))
  }
  assert.match(storage, /function getAdvances\([^)]*\) \{[\s\S]*?from\('salary_advances'\)/)
  for (const path of [
    '../src/components/AdvancesManager.jsx',
    '../src/components/employee/EmpAdvances.jsx',
  ]) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|advanceSchedule|getAdvances|saveAdvance/i)
    assert.match(source, /migration advance workspace/)
  }
})
