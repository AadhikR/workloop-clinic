import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const attendance = await readFile(new URL('../src/utils/attendanceStorage.js', import.meta.url), 'utf8')

function functionBody(source, symbol) {
  const start = source.indexOf(`export async function ${symbol}`)
  assert.notEqual(start, -1)
  const bodyStart = source.indexOf(') {', start) + 2
  let depth = 0
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}' && --depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not parse ${symbol}`)
}

test('legacy calculated attendance reads and writes fail closed after Phase 10D cutover', () => {
  for (const symbol of ['getAttendanceRecords', 'upsertAttendanceRecord', 'computeAndSaveAttendance']) {
    const body = functionBody(attendance, symbol)
    assert.match(body, /moved to the migration attendance calculation screen/i)
    assert.doesNotMatch(body, /supabase\s*\.\s*from/)
  }
})
