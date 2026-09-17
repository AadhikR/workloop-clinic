import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('legacy payroll approval and payslip writers are frozen', async () => {
  const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  for (const name of [
    'createPayslipRecords',
    'submitPayrollForApproval',
    'approvePayroll',
    'rejectPayroll',
    'recallPayrollApproval',
    'getPayrollApprovalLog',
  ]) {
    assert.match(storage, new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?migration payroll workspace`))
  }
  const employee = await readFile(new URL('../src/components/employee/EmpPayslips.jsx', import.meta.url), 'utf8')
  assert.doesNotMatch(employee, /supabase|getMyPayslips|payslipGenerator|downloadPayslip/i)
  assert.match(employee, /migration employee workspace/)
})
