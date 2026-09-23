import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const appraisals = await readFile(new URL('../src/utils/appraisalStorage.js', import.meta.url), 'utf8')
const incidents = await readFile(new URL('../src/utils/incidentStorage.js', import.meta.url), 'utf8')

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

test('appraisals and incidents use migration APIs without legacy service access', async () => {
  for (const path of [
    '../migration/src/appraisalsIncidentsApi.js',
    '../migration/src/AppraisalsIncidents.jsx',
  ]) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|\.from\(['"](?:appraisals|incident_reports)/i)
  }
})

test('legacy appraisal functions fail closed', () => {
  assert.match(appraisals, /Legacy appraisal access is disabled/i)
  for (const symbol of [
    'getAppraisalCycles', 'saveAppraisalCycle', 'deleteAppraisalCycle',
    'getAppraisalsForCycle', 'getMyAppraisals', 'getMyTeamAppraisals',
    'managerRateSection', 'createAppraisalsForCycle', 'saveAppraisalReview',
    'calibrateAppraisal', 'deleteAppraisal',
  ]) {
    const body = functionBody(appraisals, symbol)
    assert.match(body, /throw cutoverError\(\)/)
    assert.doesNotMatch(body, /supabase/)
  }
})

test('legacy incident functions fail closed and hard delete stays unavailable', () => {
  assert.match(incidents, /Legacy clinical incident access is disabled/i)
  for (const symbol of ['getIncidents', 'saveIncident', 'deleteIncident']) {
    const body = functionBody(incidents, symbol)
    assert.match(body, /throw cutoverError\(\)/)
    assert.doesNotMatch(body, /supabase|\.delete\(/)
  }
})
