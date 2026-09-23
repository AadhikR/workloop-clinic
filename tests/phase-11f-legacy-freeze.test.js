import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const storage = await readFile(new URL('../src/utils/letterStorage.js', import.meta.url), 'utf8')
const employee = await readFile(new URL('../src/components/employee/EmpRequests.jsx', import.meta.url), 'utf8')

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

test('migration request paths contain no Supabase or browser rendering dependency', async () => {
  for (const path of ['../migration/src/letterRequestsApi.js', '../migration/src/LetterRequests.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|letterTemplates|safePrint|window\.open|document\.write/i)
  }
})

test('legacy request storage reads and writes fail closed', () => {
  assert.match(storage, /Legacy letter and custom request access is disabled/i)
  for (const symbol of [
    'getLetterRequests', 'getPendingLetterCount', 'completeLetterRequest',
    'rejectLetterRequest', 'getMyLetterRequests', 'submitLetterRequest',
  ]) {
    const body = functionBody(storage, symbol)
    assert.match(body, /throw cutoverError\(\)/)
    assert.doesNotMatch(body, /supabase|\.from\(|\.rpc\(/)
  }
})

test('legacy employee submission RPCs are frozen', () => {
  assert.doesNotMatch(employee, /employee_request_letter|employee_request_custom|supabase\.rpc/)
  assert.match(employee, /submitLetterRequest/)
})
