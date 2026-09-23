import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')

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

test('employee documents, insurance, and employment contracts use migration APIs', async () => {
  for (const path of [
    '../migration/src/recordsBenefitsApi.js',
    '../migration/src/RecordsBenefits.jsx',
  ]) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|storage_path|document_number/i)
  }
})

test('legacy employee document and employment contract paths fail closed', () => {
  const expected = new Map([
    ['getEmployeeDocuments', /migration records and benefits workspace/i],
    ['uploadEmployeeDocument', /migration records and benefits workspace/i],
    ['deleteEmployeeDocument', /migration records and benefits workspace/i],
    ['verifyEmployeeDocument', /migration records and benefits workspace/i],
    ['rejectEmployeeDocument', /migration records and benefits workspace/i],
    ['getEmployeeContracts', /migration records and benefits workspace/i],
    ['saveEmployeeContract', /migration records and benefits workspace/i],
  ])
  for (const [symbol, message] of expected) {
    const body = functionBody(storage, symbol)
    assert.match(body, message)
    assert.doesNotMatch(body, /supabase\s*\.\s*(from|storage|rpc)/)
  }
})

test('legacy insurance administration writers and employee detail reads fail closed', () => {
  for (const symbol of [
    'saveInsurancePolicy',
    'deleteInsurancePolicy',
    'getEmployeeInsurance',
    'saveEmployeeInsurance',
    'getInsuranceDependants',
    'saveInsuranceDependant',
    'deleteInsuranceDependant',
  ]) {
    const body = functionBody(storage, symbol)
    assert.match(body, /migration records and benefits workspace/i)
    assert.doesNotMatch(body, /supabase\s*\.\s*(from|storage|rpc)/)
  }
  assert.match(functionBody(storage, 'getInsurancePolicies'), /supabase/)
  assert.match(functionBody(storage, 'getAllEmployeeInsurance'), /supabase/)
  assert.match(functionBody(storage, 'getAllEmployeeDocuments'), /supabase/)
})
