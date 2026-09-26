import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-12')
const cutoverDirectory = path.join(phaseDirectory, 'cutover')
const inventoryPath = path.join(phaseDirectory, 'PART_12A_DEPENDENCY_INVENTORY.md')
const goldenPath = path.join(phaseDirectory, 'PART_12A_GOLDEN_CASES.md')
const reviewPath = path.join(phaseDirectory, 'PART_12H_INDEPENDENT_REVIEW.md')
const contractPath = path.join(phaseDirectory, 'PART_12A_OUTPUT_AND_DELIVERY_CONTRACT.md')
const recordNames = ['notifications.json', 'phase12-consumers.json']
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

function reviewSection(name) {
  return readText(reviewPath).split(`## ${name}\n`, 2)[1].split('\n## ', 1)[0]
}

test('traces every Phase 12 dependency and upstream assignment exactly once', () => {
  const inventory = readText(inventoryPath)
  const review = readText(reviewPath)
  const inventoryIds = tableIds(
    inventory,
    /^\| `(P12-(?:NOT|TSK|DSH|RPT|OUT|DB|IND)-\d{2})` \|/gm,
  )
  const upstreamIds = tableIds(
    inventory,
    /^\| `(P0-[A-Z-]+|P11-[A-Z]+-\d{2}|phase8a-[a-z-]+|UI-\d{2}|JS-\d{2}|EXT-\d{2}|ATT-(?:UI|EXT)-\d{2})` \|/gm,
  )
  const tracedInventory = tableIds(
    reviewSection('Inventory trace'),
    /^\| `(P12-[^`]+)` \|/gm,
  )
  const tracedUpstream = tableIds(
    reviewSection('Upstream assignment trace'),
    /^\| `([^`]+)` \|/gm,
  )
  assert.equal(inventoryIds.length, 97)
  assert.equal(upstreamIds.length, 52)
  assert.equal(new Set(inventoryIds).size, inventoryIds.length)
  assert.equal(new Set(upstreamIds).size, upstreamIds.length)
  assert.deepEqual(tracedInventory.sort(), [...inventoryIds].sort())
  assert.deepEqual(tracedUpstream.sort(), [...upstreamIds].sort())
  assert.match(
    review,
    /Earlier completion records were treated as\s+context, not as independent proof/,
  )
})

test('maps every Phase 12 golden case to automated proof', () => {
  const goldenIds = tableIds(
    readText(goldenPath),
    /^\| `(12A-GC-\d{3})` \|/gm,
  )
  const proofIds = tableIds(
    reviewSection('Golden-case proof map'),
    /^\| `(12A-GC-\d{3})` \|/gm,
  )
  assert.equal(goldenIds.length, 50)
  assert.equal(new Set(goldenIds).size, goldenIds.length)
  assert.deepEqual(proofIds.sort(), [...goldenIds].sort())
})

test('keeps every Phase 12 cutover complete, evidenced, and single-authority', () => {
  for (const name of recordNames) {
    const record = JSON.parse(readText(path.join(cutoverDirectory, name)))
    assertValidCutoverRecord(record, { repositoryDirectory })
    assert.equal(record.status.current, 'completed')
    assert.equal(record.authority.readSystem, 'migration-fastapi')
    assert.equal(record.authority.writeSystem, 'migration-fastapi')
    assert.deepEqual(record.authority.writableSystems, ['migration-fastapi'])
    assert.deepEqual(record.rollback.steps.map((step) => step.id), rollbackSteps)
    const evidencePath = path.join(repositoryDirectory, record.refresh.lastRefresh.evidence.path)
    const evidenceBytes = readFileSync(evidencePath)
    assert.equal(
      `sha256:${createHash('sha256').update(evidenceBytes).digest('hex')}`,
      record.refresh.lastRefresh.evidence.sha256,
    )
    const evidence = JSON.parse(evidenceBytes)
    assert.equal(evidence.featureId, record.featureId)
    assert.equal(evidence.result, 'completed')
    assert.equal(evidence.sourceDigest, record.refresh.lastRefresh.sourceDigest)
  }

  const catalogue = JSON.parse(readText(path.join(cutoverDirectory, 'dependency-catalogue.json')))
  const items = catalogue.dependencies
  assert.equal(items.length, 97)
  assert.equal(new Set(items.map((item) => item.id)).size, items.length)
  assert.equal(items.filter((item) => item.state === 'completed').length, 90)
  assert.equal(items.filter((item) => item.state === 'retained-for-phase13').length, 6)
  assert.deepEqual(
    items.filter((item) => item.state === 'omitted-fail-closed').map((item) => item.id),
    ['P12-OUT-17'],
  )
})

test('keeps reverse rollback dependency order and evidence retention explicit', () => {
  const contract = readText(contractPath)
  const consumers = JSON.parse(readText(path.join(cutoverDirectory, 'phase12-consumers.json')))
  assert.match(
    contract,
    /Rollback disables 12G output routes, then 12F byte routes, 12E reports, 12D dashboards, 12C tasks,\nand 12B notification producers and inbox routes/,
  )
  assert.match(
    contract,
    /preserves source rows, notifications, read\ntimestamps, audit events, source snapshots, and renderer evidence/,
  )
  assert.match(consumers.freeze.write.releaseCondition, /12G.*12F.*12E.*12D.*12C.*12B/)
  assert.match(consumers.rollback.steps[0].action, /12G.*12F.*12B/)
  assert.match(consumers.rollback.steps[2].action, /12G, 12F, 12E, 12D, 12C, and 12B/)
})

test('keeps the migration build free of Supabase and browser document generators', () => {
  const forbidden = /supabase|createClient|@supabase|jspdf|html2canvas|payslipGenerator|sifGenerator|letterTemplates|reportUtils|window\.print|safePrint|zipSync/i
  for (const file of sourceFiles(path.join(repositoryDirectory, 'src'))) {
    assert.doesNotMatch(readText(file), forbidden, path.relative(repositoryDirectory, file))
  }
})

test('pins the protected audit writer and fixed expiry login', () => {
  const auditRevision = readText(path.join(
    repositoryDirectory,
    'backend',
    'alembic',
    'versions',
    'e8a1c3f5b7d9_extend_phase12g_output_audit.py',
  ))
  const expiry = readText(path.join(repositoryDirectory, 'backend', 'app', 'expiry_command.py'))
  const expiryEnvironment = readText(path.join(repositoryDirectory, 'backend', '.env.expiry.example'))
  for (const token of [
    'SECURITY DEFINER',
    'SET search_path TO pg_catalog, public',
    'REVOKE ALL ON FUNCTION',
    'GRANT EXECUTE ON FUNCTION',
    'workloop_runtime',
  ]) assert.match(auditRevision, new RegExp(token))
  assert.match(expiry, /user != "workloop_expiry_processing"/)
  assert.match(expiry, /EXPIRY_DATABASE_URL/)
  assert.match(expiryEnvironment, /workloop_expiry_processing/)
})

test('routes every Phase 12 proof and the complete three-role browser journey', () => {
  const workflow = readText(path.join(
    repositoryDirectory,
    '.github',
    'workflows',
    'migration-foundation.yml',
  ))
  for (const part of ['12a', '12b', '12c', '12d', '12e', '12f', '12g']) {
    assert.match(workflow, new RegExp(`verify-phase-${part}-(?:contract|boundary)\\.py`))
  }
  for (const part of ['12b', '12c', '12d', '12e', '12f', '12g']) {
    assert.match(workflow, new RegExp(`verify-phase-${part}-database\\.py`))
  }
  assert.match(workflow, /tests\/phase-12h-boundary\.test\.js/)
  assert.match(workflow, /verify-phase-12g-revision\.py predecessor/)
  assert.match(workflow, /verify-phase-12h-rollback\.py prepare/)
  assert.match(workflow, /verify-phase-12h-rollback\.py predecessor/)
  assert.match(workflow, /verify-phase-12h-rollback\.py head/)
  assert.match(workflow, /verify-phase-12h-rollback\.py cleanup/)
  assert.match(workflow, /docs\/migration\/phase-12\/cutover\/\*\.json/)

  const browser = readText(path.join(repositoryDirectory, 'scripts', 'verify-phase-3g-browser.mjs'))
  assert.match(browser, /async function assertPhase12BrowserJourney/)
  assert.match(browser, /await assertPhase12BrowserJourney\(page, persona\)/)
  for (const boundary of [
    'readNotifications',
    'readTasks',
    'readDashboard',
    'readReport',
    'downloadReportCsv',
    'downloadReportPdf',
    'downloadSelfPayslipPdf',
  ]) assert.match(browser, new RegExp(boundary))
})
