import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const attendance = await readFile(new URL('../src/utils/attendanceStorage.js', import.meta.url), 'utf8')
const biometric = await readFile(new URL('../src/utils/biometricStorage.js', import.meta.url), 'utf8')

function functionBody(source, symbol) {
  const start = source.indexOf(`export async function ${symbol}`)
  assert.notEqual(start, -1)
  return source.slice(start, source.indexOf('\n}', start) + 2)
}

test('legacy manual clock-event writers fail closed after Phase 10C cutover', () => {
  for (const symbol of ['recordClockEvent', 'recordManualClockEvent']) {
    const body = functionBody(attendance, symbol)
    assert.match(body, /moved to the migration attendance ingestion screen/i)
    assert.doesNotMatch(body, /supabase\s*\.\s*from/)
  }
})

test('legacy biometric mapping and import writers fail closed after Phase 10C cutover', () => {
  for (const symbol of ['saveBiometricMapping', 'deleteBiometricMapping', 'importBiometricPunches']) {
    const body = functionBody(biometric, symbol)
    assert.match(body, /moved to the migration attendance ingestion screen/i)
    assert.doesNotMatch(body, /supabase\s*\.\s*from/)
  }
})
