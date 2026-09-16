import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const migrationFiles = [
  '../migration/src/expenseApi.js',
  '../migration/src/Expenses.jsx',
]

test('migration expense screens have no Supabase or legacy expense-storage path', async () => {
  for (const path of migrationFiles) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase/i)
    assert.doesNotMatch(source, /expenseStorage/)
    assert.doesNotMatch(source, /receipt_url|receiptUrl/)
  }
})

test('legacy expense claim, decision, and receipt paths fail closed', async () => {
  const storage = await readFile(new URL('../src/utils/expenseStorage.js', import.meta.url), 'utf8')
  assert.match(storage, /Expense claims and receipts have moved to the migration expense workspace/)
  for (const name of [
    'getExpenseClaims',
    'approveExpenseClaim',
    'rejectExpenseClaim',
    'deleteExpenseClaim',
    'deleteEmployeeExpense',
    'uploadExpenseReceipt',
    'getExpenseReceiptUrl',
    'getExpenseQueueForManager',
    'managerApproveExpense',
    'managerRejectExpense',
  ]) {
    assert.match(storage, new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?expenseMoved\\(\\)`))
  }

  for (const path of [
    '../src/components/ExpensesManager.jsx',
    '../src/components/manager/ManagerExpenseQueue.jsx',
    '../src/components/employee/EmpExpenses.jsx',
  ]) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|expenseStorage|employee_submit_expense/i)
    assert.match(source, /migration expense workspace/)
  }
})
