import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const moved = 'Leave configuration has moved to the migration settings screen.'
const functions = [
  'getLeaveSettings',
  'saveLeaveSettings',
  'getLeaveTypes',
  'seedDefaultLeaveTypes',
  'saveLeaveType',
  'deleteLeaveType',
  'getPublicHolidays',
  'seedPublicHolidays',
  'seedPublicHolidaysForYear',
  'savePublicHoliday',
  'deletePublicHoliday',
]

test('freezes every legacy leave configuration entry point', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  for (const name of functions) {
    const pattern = new RegExp(
      `export async function ${name}\\([^)]*\\) \\{[\\s\\S]*?throw new Error\\('${moved.replace('.', '\\.')}'\\);[\\s\\S]*?\\n\\}`,
    )
    assert.match(source, pattern, `${name} must direct callers to the migration settings screen`)
  }
})

test('keeps legacy request, balance, and attachment functions outside the 8B freeze', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  for (const name of [
    'uploadLeaveAttachment', 'getLeaveRequests', 'submitLeaveRequest', 'getLeaveBalances',
  ]) assert.match(source, new RegExp(`export async function ${name}\\(`))
})
