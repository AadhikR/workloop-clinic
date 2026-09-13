import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('freezes legacy balance readers and writers without freezing request workflows', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  const moved = /ha(?:s|ve) moved to the migration leave view/
  for (const name of [
    'getLeaveBalances',
    'getAllLeaveBalances',
    'upsertLeaveBalance',
    'recalculateAllBalances',
  ]) {
    const match = source.match(new RegExp(`export async function ${name}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))
    assert.ok(match, `${name} is missing`)
    assert.match(match[1], moved)
    assert.doesNotMatch(match[1], /supabase|leave_balances/i)
  }

  for (const name of [
    'getLeaveRequests',
    'submitLeaveRequest',
    'cancelLeaveRequest',
    'updateLeaveRequestStatus',
    'uploadLeaveAttachment',
  ]) {
    const match = source.match(new RegExp(`export async function ${name}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))
    assert.ok(match, `${name} is missing`)
    assert.doesNotMatch(match[1], moved)
  }
})
