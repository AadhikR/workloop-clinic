import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const submissionMoved = 'Leave request submission has moved to the migration leave screen.'
const cancellationMoved = 'Leave request cancellation has moved to the migration leave screen.'

const retiredOperations = Object.freeze({
  employee_submit_leave_request: ['submitLeaveRequest', submissionMoved],
  employee_cancel_leave_request: ['cancelLeaveRequest', cancellationMoved],
})

test('freezes legacy leave submission and cancellation entry points', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  for (const [name, message] of Object.values(retiredOperations)) {
    const match = source.match(new RegExp(`export async function ${name}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))
    assert.ok(match, `${name} is missing`)
    assert.match(match[1], new RegExp(message.replaceAll('.', '\\.')))
    assert.doesNotMatch(match[1], /supabase|leave_requests/i)
  }
})

test('keeps request reads while later approval decisions fail closed', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  const requestRead = source.match(new RegExp('export async function getLeaveRequests\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}'))
  assert.ok(requestRead, 'getLeaveRequests is missing')
  assert.doesNotMatch(requestRead[1], /has moved/)
  for (const name of [
    'updateLeaveRequestStatus',
    'approveLeaveAsManager',
    'rejectLeaveAsManager',
  ]) {
    const match = source.match(new RegExp(`export async function ${name}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))
    assert.ok(match, `${name} is missing`)
    assert.match(match[1], /(?:has|have) moved to the migration approval queue/)
  }
})
