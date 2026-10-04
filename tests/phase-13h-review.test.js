import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  alembicHeads,
  inspectPhase13Review,
  traceIds,
} from '../scripts/verify-phase-13h-review.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function read(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

test('traces every Phase 13 dependency and golden case exactly once', () => {
  const catalogue = JSON.parse(read('docs/migration/phase-13/dependency-catalogue.json'))
  const review = read('docs/migration/phase-13/PART_13H_INDEPENDENT_REVIEW.md')
  const dependencies = traceIds(review, 'Dependency trace', /^\| `(P13-[A-Z]+-\d{3})` \|/gm)
  const goldenCases = traceIds(review, 'Golden-case proof map', /^\| `(13A-GC-\d{3})` \|/gm)
  assert.equal(dependencies.length, 50)
  assert.equal(new Set(dependencies).size, 50)
  assert.deepEqual(dependencies.sort(), catalogue.dependencies.map((entry) => entry.id).sort())
  assert.equal(goldenCases.length, 42)
  assert.equal(new Set(goldenCases).size, 42)
  assert.deepEqual(goldenCases.sort(), catalogue.goldenCases.map((entry) => entry.id).sort())
})

test('closes every owner partition without overlap', () => {
  const catalogue = JSON.parse(read('docs/migration/phase-13/dependency-catalogue.json'))
  const dependencies = catalogue.allowedOwners.flatMap((owner) => catalogue.closures[owner].dependencies)
  const goldenCases = catalogue.allowedOwners.flatMap((owner) => catalogue.closures[owner].goldenCases)
  assert.equal(dependencies.length, 50)
  assert.equal(new Set(dependencies).size, 50)
  assert.equal(goldenCases.length, 42)
  assert.equal(new Set(goldenCases).size, 42)
})

test('passes the complete independent repository review', () => {
  assert.deepEqual(inspectPhase13Review(), {
    errors: [],
    dependencies: 50,
    goldenCases: 42,
    alembicHeads: ['f1a3c5e7b9d2'],
  })
})

test('keeps the closing proof routed through every required layer', () => {
  const workflow = read('.github/workflows/migration-foundation.yml')
  assert.match(workflow, /name: Verify Phase 13H independent review\s+run: npm run verify:phase13h:review/)
  assert.match(workflow, /npm run verify:phase13f:clean/)
  assert.match(workflow, /Verify Phase 13F process guards/)
  assert.match(workflow, /node scripts\/verify-phase-13f-browser\.mjs/)
  assert.match(workflow, /sh scripts\/verify-phase-3h-logs\.sh/)
  assert.match(workflow, /run: docker compose down --volumes/)
})

test('keeps one schema head and the archive-only disposition', () => {
  assert.deepEqual(alembicHeads(), ['f1a3c5e7b9d2'])
  const target = JSON.parse(read('docs/migration/phase-13/PART_13G_TARGET_MANIFEST.json'))
  const approval = JSON.parse(read('docs/migration/phase-13/PART_13G_APPROVAL_MANIFEST.json'))
  assert.equal(target.retention.status, 'indefinite')
  assert.equal(target.retention.disposition, 'retain-external-project')
  assert.equal(approval.status, 'retained')
  assert.deepEqual(approval.approvals, [])
  assert.deepEqual(target.receipts, [])
})
