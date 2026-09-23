import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-9')
const cutoverDirectory = path.join(phaseDirectory, 'cutover')
const inventoryPath = path.join(phaseDirectory, 'PART_9A_DEPENDENCY_INVENTORY.md')
const goldenPath = path.join(phaseDirectory, 'PART_9A_GOLDEN_CASES.md')
const reviewPath = path.join(phaseDirectory, 'PART_9H_COMPLETION.md')
const contractPath = path.join(phaseDirectory, 'PART_9A_FINANCIAL_CONTRACT.md')
const recordNames = [
  'advances-and-repayments.json',
  'expenses.json',
  'payroll-approval-and-payslips.json',
  'payroll-drafts-and-calculations.json',
  'payroll-inputs.json',
  'wps-and-nafis.json',
]
const featureIds = [
  'advances-and-repayments',
  'expenses',
  'payroll-approval-and-payslips',
  'payroll-drafts-and-calculations',
  'payroll-inputs',
  'wps-and-nafis',
]
const rollbackSteps = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]
const currentHeadVerifierPaths = [
  'scripts/verify-phase-7g-employee-lifecycle.py',
  'scripts/verify-phase-8b-configuration-database.py',
  'scripts/verify-phase-8c-balance-database.py',
  'scripts/verify-phase-8d-database.py',
  'scripts/verify-phase-8e-database.py',
  'scripts/verify-phase-8f-database.py',
  'scripts/verify-phase-9b-database.py',
  'scripts/verify-phase-9c-database.py',
  'scripts/verify-phase-9d-database.py',
  'scripts/verify-phase-9e-database.py',
  'scripts/verify-phase-9f-database.py',
  'scripts/verify-phase-9f-lifecycle.py',
  'scripts/verify-phase-9g-database.py',
  'scripts/verify-phase-9g-lifecycle.py',
  'scripts/verify-phase-10b-database.py',
  'scripts/verify-phase-10c-database.py',
  'scripts/verify-phase-10d-database.py',
  'scripts/verify-phase-10e-database.py',
  'scripts/verify-phase-10f-database.py',
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

test('traces every Phase 9A financial dependency exactly once', () => {
  const inventoryIds = tableIds(
    readText(inventoryPath),
    /^\| (UI-\d+|JS-\d+|DB-\d+|EXT-\d+) \|/gm,
  )
  const traceSection = readText(reviewPath)
    .split('## Inventory trace\n', 2)[1]
    .split('\n## ', 1)[0]
  const tracedIds = tableIds(traceSection, /^\| `([^`]+)` \|/gm)
  assert.equal(inventoryIds.length, 78)
  assert.equal(new Set(inventoryIds).size, inventoryIds.length)
  assert.equal(tracedIds.length, inventoryIds.length)
  assert.deepEqual(tracedIds.sort(), [...inventoryIds].sort())
})

test('maps every approved golden case to automated proof', () => {
  const goldenIds = tableIds(
    readText(goldenPath),
    /^### ((?:PAY|INP|EXP|ADV|APP|WPS|CMP|NAF)-\d+)/gm,
  )
  const proofSection = readText(reviewPath)
    .split('## Golden-case proof map\n', 2)[1]
    .split('\n## ', 1)[0]
  const proofIds = tableIds(proofSection, /^\| `([^`]+)` \|/gm)
  assert.equal(goldenIds.length, 27)
  assert.equal(new Set(goldenIds).size, goldenIds.length)
  assert.equal(proofIds.length, goldenIds.length)
  assert.deepEqual(proofIds.sort(), [...goldenIds].sort())
})

test('keeps all six cutovers complete, immutable, and single-writer', () => {
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

test('keeps the reverse Phase 9 rollback order and writer safety explicit', () => {
  const contract = readText(contractPath)
  assert.match(
    contract,
    /WPS and Nafis, approval and payslips, payroll inputs,\npayroll drafts, advances and repayments, then expenses/,
  )
  assert.match(contract, /Disable the migration writer before\nrestoring the legacy writer\./)
})

test('keeps migration source free of Supabase and legacy payroll aliases', () => {
  for (const file of sourceFiles(path.join(repositoryDirectory, 'migration', 'src'))) {
    const source = readText(file)
    assert.doesNotMatch(source, /supabase|createClient|@supabase/i)
    assert.doesNotMatch(source, /duCost/)
  }
})

test('keeps the legacy payroll converter offline and evidence-producing', () => {
  const converter = readText(path.join(
    repositoryDirectory,
    'backend',
    'app',
    'services',
    'payroll_conversion.py',
  ))
  assert.match(converter, /"legacySourceField": "duCost"/)
  assert.match(converter, /"targetField": "leaveDeduction"/)
  assert.doesNotMatch(converter, /APIRouter|supabase|AsyncConnection/)
})

test('routes exact Phase 9H rollback and tracks the current Alembic head', () => {
  const workflow = readText(path.join(
    repositoryDirectory,
    '.github',
    'workflows',
    'migration-foundation.yml',
  ))
  const revisionScript = readText(path.join(
    repositoryDirectory,
    'scripts',
    'verify-phase-9h-revision.sh',
  ))
  const revisionVerifier = readText(path.join(
    repositoryDirectory,
    'scripts',
    'verify-phase-9h-revision.py',
  ))
  assert.match(workflow, /Verify Phase 9H exact predecessor/)
  assert.match(workflow, /sh scripts\/verify-phase-9h-revision\.sh/)
  assert.match(revisionScript, /downgrade e3a7c9d1f5b2/)
  assert.match(revisionVerifier, /HEAD = "f4b8d2e6a901"/)
  assert.match(revisionVerifier, /PREDECESSOR = "e3a7c9d1f5b2"/)
  for (const verifierPath of currentHeadVerifierPaths) {
    assert.match(readText(path.join(repositoryDirectory, verifierPath)), /a1c3e5f7b9d4/)
  }
})
