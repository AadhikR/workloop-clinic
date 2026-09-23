import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')

function functionBody(source, symbol) {
  const start = source.indexOf(`export async function ${symbol}`)
  assert.notEqual(start, -1)
  const bodyStart = source.indexOf(') {', start) + 2
  const end = source.indexOf('}', bodyStart)
  return source.slice(start, end + 1)
}

test('migration offboarding paths contain no Supabase or browser rendering dependency', async () => {
  for (const path of ['../migration/src/offboardingApi.js', '../migration/src/Offboarding.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(
      source,
      /supabase|gratuityCalculator|window\.open|document\.write|jspdf/i,
    )
  }
})

test('legacy offboarding storage reads and writes fail closed', () => {
  assert.match(storage, /Legacy offboarding and gratuity access is disabled/i)
  for (const symbol of [
    'getOffboardingChecklist', 'createOffboardingChecklist', 'getOffboardingTasks',
    'updateOffboardingTask', 'addOffboardingTask', 'deleteOffboardingTask',
    'saveOffboardingVisaStatus', 'completeOffboardingChecklist',
  ]) {
    const body = functionBody(storage, symbol)
    assert.match(body, /throw offboardingCutoverError\(\)/)
    assert.doesNotMatch(body, /supabase|\.from\(|\.rpc\(/)
  }
})
