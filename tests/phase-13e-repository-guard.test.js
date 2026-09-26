import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  inspectRepository,
  inspectSnapshot,
} from '../scripts/verify-phase-13e-repository-guard.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fixtureDirectory = path.join(repositoryDirectory, 'tests', 'fixtures', 'phase-13e')
const requiredLabel = 'Historical record. Do not run or deploy these files.'

function fixture(relativePath, virtualPath = relativePath) {
  return {
    path: virtualPath,
    content: readFileSync(path.join(fixtureDirectory, relativePath)),
  }
}

function emptyAllowlist() {
  return { version: 1, groups: [], binaryHistory: [] }
}

function expectRejected(relativePath, virtualPath) {
  const report = inspectSnapshot({
    files: [fixture(relativePath, virtualPath)],
    allowlist: emptyAllowlist(),
  })
  assert.equal(report.errors.length, 1, report.errors.join('\n'))
  assert.match(report.errors[0], /not allowlisted/)
}

test('accepts labeled historical files and inert negative sentinels', () => {
  const files = [
    fixture('allowed-history/README.md', 'docs/history/example/README.md'),
    fixture('allowed-history/source.sql', 'docs/history/example/source.sql'),
    fixture('inert-sentinels.json', 'tests/fixtures/example/inert-sentinels.json'),
  ]
  const allowlist = {
    version: 1,
    groups: [
      {
        id: 'example-history',
        kind: 'history',
        labelPath: 'docs/history/example/README.md',
        paths: ['docs/history/example/README.md', 'docs/history/example/source.sql'],
      },
      {
        id: 'example-negative-proof',
        kind: 'negative-proof',
        paths: ['tests/fixtures/example/inert-sentinels.json'],
      },
    ],
    binaryHistory: [],
  }
  const report = inspectSnapshot({ files, allowlist })
  assert.deepEqual(report.errors, [])
  assert.equal(report.inspected, 3)
  assert.equal(report.markerFiles, 3)
  assert.equal(report.referenceFreeFiles, 0)
})

test('rejects direct, dynamic, aliased, and dead-code imports', () => {
  for (const [fixturePath, virtualPath] of [
    ['negative/active-direct.js', 'src/direct.js'],
    ['negative/active-dynamic.js', 'src/dynamic.js'],
    ['negative/active-alias.js', 'vite.config.js'],
    ['negative/active-dead-code.js', 'src/dead-code.js'],
  ]) expectRejected(fixturePath, virtualPath)
})

test('rejects transitive package graph entries', () => {
  expectRejected('negative/transitive-package-lock.json', 'package-lock.json')
})

test('rejects active configuration, endpoints, bootstrap SQL, and copied assets', () => {
  for (const [fixturePath, virtualPath] of [
    ['negative/active-config.env', '.env.example'],
    ['negative/active-endpoint.txt', 'config/runtime.txt'],
    ['negative/active-bootstrap.sql', 'infra/local/postgres/init/99-retired.sql'],
    ['negative/active-copy.js', 'public/copied-runtime.js'],
  ]) expectRejected(fixturePath, virtualPath)
})

test('rejects an unlabeled historical file', () => {
  expectRejected('negative/unlabeled-history.sql', 'docs/history/unlabeled/source.sql')
})

test('rejects concealed dynamic package names without a contiguous marker', () => {
  const report = inspectSnapshot({
    files: [{
      path: 'src/concealed.js',
      content: Buffer.from("import('@' + 'supabase/supabase-js')"),
    }],
    allowlist: emptyAllowlist(),
  })
  assert.equal(report.errors.length, 1)
  assert.match(report.errors[0], /not allowlisted/)
})

test('requires exact paths, one owner, and the standard history label', () => {
  const files = [{
    path: 'docs/history/example.sql',
    content: Buffer.from('select \'supabase\';'),
  }]
  const allowlist = {
    version: 1,
    groups: [
      {
        id: 'broken-history',
        kind: 'history',
        labelPath: 'docs/history/README.md',
        paths: ['docs/history/example.sql'],
      },
      {
        id: 'duplicate',
        kind: 'negative-proof',
        paths: ['docs/history/example.sql'],
      },
    ],
    binaryHistory: [],
  }
  const report = inspectSnapshot({ files, allowlist })
  assert.ok(report.errors.some((error) => error.includes('include its labelPath')))
  assert.ok(report.errors.some((error) => error.includes('allowlisted by both')))
  assert.equal(requiredLabel.length > 0, true)
})

test('runs the repository guard in the always-routed change-classification job', () => {
  const workflow = readFileSync(
    path.join(repositoryDirectory, '.github', 'workflows', 'migration-foundation.yml'),
    'utf8',
  )
  const changesJob = workflow.slice(workflow.indexOf('  changes:'), workflow.indexOf('  backend-quality:'))
  assert.match(changesJob, /name: Verify repository guard\s+run: npm run guard:repository/)
})

test('closes the Part 13E catalogue entries and golden cases', () => {
  const catalogue = JSON.parse(readFileSync(
    path.join(repositoryDirectory, 'docs', 'migration', 'phase-13', 'dependency-catalogue.json'),
    'utf8',
  ))
  assert.deepEqual(catalogue.closures['13E'].dependencies, [
    'P13-HIS-001',
    'P13-HIS-002',
    'P13-HIS-003',
    'P13-DOC-001',
    'P13-DOC-002',
    'P13-DOC-003',
    'P13-DOC-004',
    'P13-TST-001',
    'P13-TST-002',
    'P13-GRD-001',
    'P13-DB-001',
  ])
  assert.deepEqual(catalogue.closures['13E'].goldenCases, [
    '13A-GC-015',
    '13A-GC-016',
    '13A-GC-021',
    '13A-GC-022',
    '13A-GC-023',
    '13A-GC-037',
    '13A-GC-038',
    '13A-GC-039',
  ])
})

test('keeps current instructions on the sole active runtime', () => {
  for (const relativePath of [
    'README.md',
    'ARCHITECTURE.md',
    'CLAUDE.md',
    'FEATURES_ROADMAP.md',
    'MANUAL_TEST_CHECKLIST.md',
    'REMAINING_TESTS.md',
    'backend/README.md',
    'DIGITALOCEAN_MIGRATION_PLAN.md',
  ]) {
    const source = readFileSync(path.join(repositoryDirectory, relativePath), 'utf8')
    assert.doesNotMatch(source, /supabase/i, relativePath)
    assert.match(source, /FastAPI|Keycloak|PostgreSQL|object storage/i, relativePath)
  }
})

test('isolates labeled SQL history and the digest-pinned feature PDF', () => {
  assert.equal(existsSync(path.join(repositoryDirectory, 'sql')), false)
  assert.equal(existsSync(path.join(repositoryDirectory, 'generate_feature_list.py')), false)
  for (const relativePath of [
    'docs/history/legacy-supabase-sql/README.md',
    'docs/history/legacy-feature-list/README.md',
    'backend/HISTORICAL_SOURCE_TERMS.md',
    'docs/migration/HISTORICAL_RECORDS.md',
  ]) {
    assert.match(readFileSync(path.join(repositoryDirectory, relativePath), 'utf8'), new RegExp(requiredLabel))
  }
  assert.equal(existsSync(path.join(
    repositoryDirectory,
    'docs',
    'history',
    'legacy-feature-list',
    'Workloop_Clinic_HRMS_Feature_List.pdf',
  )), true)
})

test('accounts for every inspected file and keeps the Alembic head fixed', () => {
  const report = inspectRepository(repositoryDirectory)
  assert.deepEqual(report.errors, [])
  assert.equal(report.inspected, report.markerFiles + report.referenceFreeFiles)

  const versions = path.join(repositoryDirectory, 'backend', 'alembic', 'versions')
  const revisions = new Set()
  const predecessors = new Set()
  for (const name of readdirSync(versions)) {
    if (!name.endsWith('.py')) continue
    const source = readFileSync(path.join(versions, name), 'utf8')
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    assert.ok(revision, name)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  assert.deepEqual(
    [...revisions].filter((revision) => !predecessors.has(revision)).sort(),
    ['e8a1c3f5b7d9'],
  )
})
