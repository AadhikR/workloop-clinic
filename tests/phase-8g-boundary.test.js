import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-8')
const cutoverDirectory = path.join(phaseDirectory, 'cutover')
const inventoryPath = path.join(phaseDirectory, 'PART_8A_DEPENDENCY_INVENTORY.md')
const reviewPath = path.join(phaseDirectory, 'PART_8G_INDEPENDENT_REVIEW.md')
const planPath = path.join(phaseDirectory, 'SUBPHASE_PLAN.md')
const recordNames = [
  'leave-approval-workflows.json',
  'leave-attachments.json',
  'leave-balances-and-reads.json',
  'leave-configuration.json',
  'leave-request-submission.json',
]
const featureIds = [
  'leave-approval-workflows',
  'leave-attachments',
  'leave-balances-and-reads',
  'leave-configuration',
  'leave-request-submission',
]
const rollbackSteps = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]

function inventoryIds(source) {
  return [...source.matchAll(/\bphase8a-[a-z0-9-]+\b/g)].map((match) => match[0])
}

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(item) : [item]
  })
}

test('traces every Phase 8A dependency exactly once', () => {
  const inventory = readFileSync(inventoryPath, 'utf8')
  const review = readFileSync(reviewPath, 'utf8')
  const ids = inventoryIds(inventory)
  assert.equal(ids.length, 42)
  assert.equal(new Set(ids).size, ids.length)

  const traceSection = review
    .split('## Inventory trace\n', 2)[1]
    .split('\n## ', 1)[0]
  const traced = [...traceSection.matchAll(/^\| `([^`]+)` \|/gm)].map((match) => match[1])
  assert.equal(traced.length, 42)
  assert.deepEqual(traced.sort(), [...ids].sort())
})

test('keeps every Phase 8 cutover complete, current, and single-writer', () => {
  const records = recordNames.map((name) => JSON.parse(
    readFileSync(path.join(cutoverDirectory, name), 'utf8'),
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

    const evidencePath = path.join(repositoryDirectory, record.refresh.lastRefresh.evidence.path)
    assert.equal(statSync(evidencePath).isFile(), true)
  }
})

test('keeps the reverse dependency rollback order explicit', () => {
  const plan = readFileSync(planPath, 'utf8')
  assert.match(
    plan,
    /decisions and delegation, submission and cancellation,\nattachments, balances and reads, then configuration/,
  )
  assert.match(plan, /Never restore a legacy writer while its\nFastAPI counterpart remains writable\./)
})

test('keeps the complete migration source tree free of Supabase calls', () => {
  const migrationSource = path.join(repositoryDirectory, 'migration', 'src')
  const forbidden = /supabase|createClient|@supabase/i
  for (const file of sourceFiles(migrationSource)) {
    assert.doesNotMatch(
      readFileSync(file, 'utf8'),
      forbidden,
      `${path.relative(repositoryDirectory, file)} contains a Supabase path`,
    )
  }
})
