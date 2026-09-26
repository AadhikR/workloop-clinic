import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-11')
const cutoverDirectory = path.join(phaseDirectory, 'cutover')
const inventoryPath = path.join(phaseDirectory, 'PART_11A_DEPENDENCY_INVENTORY.md')
const goldenPath = path.join(phaseDirectory, 'PART_11A_GOLDEN_CASES.md')
const reviewPath = path.join(phaseDirectory, 'PART_11H_INDEPENDENT_REVIEW.md')
const planPath = path.join(phaseDirectory, 'SUBPHASE_PLAN.md')
const recordNames = [
  'appraisals.json',
  'assets.json',
  'clinical-incidents.json',
  'common-storage-recovery.json',
  'employee-documents.json',
  'employment-contracts.json',
  'insurance.json',
  'letter-requests.json',
  'offboarding-final-settlement.json',
  'training-certifications-cme.json',
]
const featureIds = recordNames.map((name) => name.replace('.json', '')).sort()
const rollbackSteps = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]

function readText(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function tableIds(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1])
}

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(item) : [item]
  })
}

test('traces every Phase 11A dependency exactly once', () => {
  const inventoryIds = tableIds(
    readText(inventoryPath),
    /^\| `(P11-(?:STO|DOC|INS|CON|AST|TRN|APP|INC|REQ|OFF|LTR)-\d+)` \|/gm,
  )
  const traceSection = readText(reviewPath)
    .split('## Inventory trace\n', 2)[1]
    .split('\n## ', 1)[0]
  const tracedIds = tableIds(traceSection, /^\| `([^`]+)` \|/gm)
  assert.equal(inventoryIds.length, 59)
  assert.equal(new Set(inventoryIds).size, inventoryIds.length)
  assert.equal(tracedIds.length, inventoryIds.length)
  assert.deepEqual(tracedIds.sort(), [...inventoryIds].sort())
})

test('maps every Phase 11 golden case to automated proof', () => {
  const goldenIds = tableIds(
    readText(goldenPath),
    /^\| `(11A-G-(?:STO|DOC|INS|CON|AST|TRN|CERT|CME|APP|INC|REQ|OFF|SET)-\d+)` \|/gm,
  )
  const proofSection = readText(reviewPath)
    .split('## Golden-case proof map\n', 2)[1]
    .split('\n## ', 1)[0]
  const proofIds = tableIds(proofSection, /^\| `([^`]+)` \|/gm)
  assert.equal(goldenIds.length, 50)
  assert.equal(new Set(goldenIds).size, goldenIds.length)
  assert.equal(proofIds.length, goldenIds.length)
  assert.deepEqual(proofIds.sort(), [...goldenIds].sort())
})

test('keeps every Phase 11 cutover complete, valid, and single-writer', () => {
  const records = recordNames.map((name) => JSON.parse(
    readText(path.join(cutoverDirectory, name)),
  ))
  assert.deepEqual(records.map((record) => record.featureId).sort(), featureIds)
  for (const record of records) {
    assertValidCutoverRecord(record, { repositoryDirectory })
    assert.equal(record.status.current, 'completed')
    assert.equal(record.authority.readSystem, 'migration-fastapi')
    assert.equal(record.authority.writeSystem, 'migration-fastapi')
    assert.deepEqual(record.authority.writableSystems, ['migration-fastapi'])
    assert.equal(record.freeze.read.system, 'legacy-supabase')
    assert.equal(record.freeze.write.system, 'legacy-supabase')
    assert.deepEqual(record.rollback.steps.map((step) => step.id), rollbackSteps)
  }
})

test('keeps reverse rollback order and writer safety explicit', () => {
  const plan = readText(planPath)
  assert.match(
    plan,
    /Roll back offboarding first, then requests,\nincidents, appraisals, training and certifications, assets, contracts, insurance, and employee\ndocuments/,
  )
  assert.match(plan, /Roll back the common storage adapter last/)
  assert.match(plan, /Never restore a legacy writer while its FastAPI counterpart is\nwritable/)
})

test('keeps the complete migration source free of Supabase paths', () => {
  for (const file of sourceFiles(path.join(repositoryDirectory, 'src'))) {
    assert.doesNotMatch(readText(file), /supabase|createClient|@supabase/i)
  }
})

test('routes every Phase 11 verifier and the closing boundary review', () => {
  const workflow = readText(path.join(
    repositoryDirectory,
    '.github',
    'workflows',
    'migration-foundation.yml',
  ))
  assert.match(workflow, /verify-phase-11b-storage\.py/)
  assert.match(workflow, /verify-phase-11b-restart\.py/)
  for (const part of ['11b', '11c', '11d', '11e', '11f', '11g']) {
    assert.match(workflow, new RegExp(`verify-phase-${part}-revision\\.py`))
    assert.match(workflow, new RegExp(`verify-phase-${part}-database\\.py`))
  }
  assert.match(workflow, /tests\/phase-11h-boundary\.test\.js/)
})

test('runs an explicit three-role Phase 11 browser journey and cleanup proof', () => {
  const browser = readText(path.join(repositoryDirectory, 'scripts', 'verify-phase-3g-browser.mjs'))
  assert.match(browser, /async function assertPhase11BrowserJourney/)
  assert.match(browser, /await assertPhase11BrowserJourney\(page, persona\)/)
  for (const table of [
    'final_settlements', 'offboarding_tasks', 'offboarding_checklists', 'letter_requests',
  ]) {
    assert.match(browser, new RegExp(`SELECT count\\(\\*\\) FROM ${table}`))
  }
})
