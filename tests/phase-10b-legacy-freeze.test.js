import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const storage = await readFile(new URL('../src/utils/attendanceStorage.js', import.meta.url), 'utf8')

test('legacy configuration writes fail closed after Phase 10B cutover', () => {
  for (const symbol of ['saveAttendanceSettings', 'saveShift', 'deleteShift', 'assignShift']) {
    const start = storage.indexOf(`export async function ${symbol}`)
    assert.notEqual(start, -1)
    const body = storage.slice(start, storage.indexOf('\n}', start) + 2)
    assert.match(body, /moved to the migration attendance configuration screen/i)
    assert.doesNotMatch(body, /supabase\s*\.\s*from/)
  }
})
