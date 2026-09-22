import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-10')
const cutoverDirectory = path.join(phaseDirectory, 'cutover')
const inventoryPath = path.join(phaseDirectory, 'PART_10A_DEPENDENCY_INVENTORY.md')
const goldenPath = path.join(phaseDirectory, 'PART_10A_GOLDEN_CASES.md')
const reviewPath = path.join(phaseDirectory, 'PART_10J_COMPLETION.md')
const planPath = path.join(phaseDirectory, 'SUBPHASE_PLAN.md')
const recordNames = [
  'attendance-configuration.json',
  'attendance-event-ingestion.json',
  'attendance-calculation.json',
  'attendance-exceptions.json',
  'attendance-period-close.json',
  'roster-drafting.json',
  'roster-publication.json',
  'shift-swaps.json',
]
const featureIds = [
  'attendance-calculation',
  'attendance-configuration',
  'attendance-event-ingestion',
  'attendance-exceptions',
  'attendance-period-close',
  'roster-drafting',
  'roster-publication',
  'shift-swaps',
]
const rollbackSteps = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]
const phase10Parts = ['10b', '10c', '10d', '10e', '10f', '10g', '10h', '10i']

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

test('traces every Phase 10A dependency exactly once', () => {
  const inventoryIds = tableIds(
    readText(inventoryPath),
    /^\| `(ATT-(?:JS|UI|DB|RPC|EXT)-\d+)` \|/gm,
  )
  const traceSection = readText(reviewPath)
    .split('## Inventory trace\n', 2)[1]
    .split('\n## ', 1)[0]
  const tracedIds = tableIds(traceSection, /^\| `([^`]+)` \|/gm)
  assert.equal(inventoryIds.length, 53)
  assert.equal(new Set(inventoryIds).size, inventoryIds.length)
  assert.equal(tracedIds.length, inventoryIds.length)
  assert.deepEqual(tracedIds.sort(), [...inventoryIds].sort())
})

test('maps every Phase 10 golden case to automated proof', () => {
  const goldenIds = tableIds(
    readText(goldenPath),
    /^\| `((?:CFG|EVT|ATT|MNY|CLS|ROS|PAY10)-\d+)` \|/gm,
  )
  const proofSection = readText(reviewPath)
    .split('## Golden-case proof map\n', 2)[1]
    .split('\n## ', 1)[0]
  const proofIds = tableIds(proofSection, /^\| `([^`]+)` \|/gm)
  assert.equal(goldenIds.length, 59)
  assert.equal(new Set(goldenIds).size, goldenIds.length)
  assert.equal(proofIds.length, goldenIds.length)
  assert.deepEqual(proofIds.sort(), [...goldenIds].sort())
})

test('keeps every Phase 10 cutover complete, immutable, and single-writer', () => {
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
  const inventory = readText(inventoryPath)
  const plan = readText(planPath)
  assert.match(
    inventory,
    /configuration; event ingestion; attendance calculation; exceptions;\nperiod close and projection; roster drafting; roster publication and projection; and shift swaps/,
  )
  assert.match(
    plan,
    /Roll back swaps first, then roster publication and payroll\nprojection, roster drafts and gates, attendance period close and payroll projection, corrections and\napprovals, attendance calculation and reads, clock-event ingestion, and configuration/,
  )
  assert.match(plan, /Never\nrestore a legacy writer while its FastAPI counterpart remains writable/)
})

test('keeps the complete migration source free of Supabase paths', () => {
  for (const file of sourceFiles(path.join(repositoryDirectory, 'migration', 'src'))) {
    assert.doesNotMatch(readText(file), /supabase|createClient|@supabase/i)
  }
})

test('routes every Phase 10 exact predecessor and database verifier', () => {
  const workflow = readText(path.join(
    repositoryDirectory,
    '.github',
    'workflows',
    'migration-foundation.yml',
  ))
  for (const part of phase10Parts) {
    assert.match(workflow, new RegExp(`verify-phase-${part}-revision\\.sh`))
    assert.match(workflow, new RegExp(`verify-phase-${part}-database\\.py`))
  }
  assert.match(workflow, /tests\/phase-10j-boundary\.test\.js/)
})

test('records Phase 10 signoff and the later consolidated Phase 11 authorization', () => {
  const review = readText(reviewPath)
  const plan = readText(planPath)
  assert.match(review, /signed off Phase 10 on 2026-09-22/)
  assert.match(review, /consolidated Phase 11 Parts 11A through 11H/)
  assert.match(plan, /\| 10J \| Independent review, complete cutover proof, and Phase 10 gate \| Complete \|/)
  assert.match(plan, /signed off Phase 10 on 2026-09-22/)
})
