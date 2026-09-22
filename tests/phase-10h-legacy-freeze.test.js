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

test('legacy roster publication, payroll input, and personal schedule paths fail closed', () => {
  const expected = new Map([
    ['publishRoster', /publication has moved to the migration roster screen/i],
    ['getOvertimeFromRoster', /payroll input is available only through the migration payroll service/i],
    ['getMyRoster', /personal schedules have moved to the migration employee workspace/i],
  ])
  for (const [symbol, message] of expected) {
    const body = functionBody(attendance, symbol)
    assert.match(body, message)
    assert.doesNotMatch(body, /supabase\s*\.\s*(from|rpc)/)
  }
})
