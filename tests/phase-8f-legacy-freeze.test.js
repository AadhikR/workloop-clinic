import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('legacy approval queue, decision, delegation, and audit paths fail closed', async () => {
  const source = await readFile(new URL('../src/utils/leaveStorage.js', import.meta.url), 'utf8')
  for (const name of [
    'getLeaveQueueForManager',
    'approveLeaveAsManager',
    'rejectLeaveAsManager',
    'updateLeaveRequestStatus',
    'getLeaveApprovalDelegates',
    'saveLeaveApprovalDelegate',
    'deleteLeaveApprovalDelegate',
    'getLeaveAuditLog',
  ]) {
    const match = source.match(new RegExp(`export async function ${name}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))
    assert.ok(match, `${name} is missing`)
    assert.match(match[1], /moved to (?:the migration|FastAPI)/)
    assert.doesNotMatch(match[1], /supabase\.|\.rpc\(/)
  }
})
