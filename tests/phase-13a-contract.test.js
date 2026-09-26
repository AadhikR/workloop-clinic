import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-13')
const cataloguePath = path.join(phaseDirectory, 'dependency-catalogue.json')
const inventoryPath = path.join(phaseDirectory, 'PART_13A_DEPENDENCY_INVENTORY.md')
const contractPath = path.join(phaseDirectory, 'PART_13A_PROMOTION_AND_DECOMMISSION_CONTRACT.md')
const goldenPath = path.join(phaseDirectory, 'PART_13A_GOLDEN_CASES.md')

function readText(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function gitOutput(args) {
  const result = spawnSync('git', args, {
    cwd: repositoryDirectory,
    encoding: 'buffer',
  })
  assert.equal(result.status, 0, result.stderr.toString('utf8'))
  return result.stdout
}

function nulPaths(buffer) {
  return buffer.toString('utf8').split('\0').filter(Boolean).map((value) => value.replaceAll('\\', '/'))
}

function selectorMatches(file, selector) {
  if (selector.type === 'exact') return file === selector.value
  if (selector.type === 'prefix') return file.startsWith(selector.value)
  if (selector.type === 'regex') return new RegExp(selector.value).test(file)
  assert.fail(`Unknown selector type ${selector.type}`)
}

function groupMatches(file, group) {
  return group.include.some((selector) => selectorMatches(file, selector))
    && !group.exclude.some((selector) => selectorMatches(file, selector))
}

function markdownInventoryRows(source) {
  return [...source.matchAll(/^\| `(P13-[A-Z]+-\d{3})` \| ([^|]+) \| `([^`]+)` \| (13[B-G]) \|$/gm)]
    .map((match) => ({
      id: match[1],
      item: match[2].trim(),
      disposition: match[3],
      owner: match[4],
    }))
}

function markdownGoldenRows(source) {
  return [...source.matchAll(/^\| `(13A-GC-\d{3})` \| (13[B-G]) \| ([^|]+) \| ([^|]+) \|$/gm)]
    .map((match) => ({
      id: match[1],
      owner: match[2],
      area: match[3].trim(),
      expectation: match[4].trim(),
    }))
}

function alembicHeads() {
  const directory = path.join(repositoryDirectory, 'backend', 'alembic', 'versions')
  const revisions = new Set()
  const predecessors = new Set()
  for (const name of readdirSync(directory)) {
    if (!name.endsWith('.py')) continue
    const source = readText(path.join(directory, name))
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    assert.ok(revision, `Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

test('gives every dependency one allowed disposition and one Part 13 owner', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const dependencies = catalogue.dependencies
  assert.ok(dependencies.length >= 45)
  assert.equal(new Set(dependencies.map((entry) => entry.id)).size, dependencies.length)
  for (const entry of dependencies) {
    assert.match(entry.id, /^P13-[A-Z]+-\d{3}$/)
    assert.ok(catalogue.allowedDispositions.includes(entry.disposition), entry.id)
    assert.ok(catalogue.allowedOwners.includes(entry.owner), entry.id)
    assert.equal(typeof entry.item, 'string')
    assert.ok(entry.item.length > 0)
    assert.ok(Array.isArray(entry.evidence) && entry.evidence.length > 0, entry.id)
  }
})

test('keeps the prose inventory in exact agreement with the catalogue', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const proseRows = markdownInventoryRows(readText(inventoryPath))
  assert.equal(proseRows.length, catalogue.dependencies.length)
  assert.deepEqual(
    proseRows.sort((left, right) => left.id.localeCompare(right.id)),
    catalogue.dependencies
      .map(({ id, item, disposition, owner }) => ({ id, item, disposition, owner }))
      .sort((left, right) => left.id.localeCompare(right.id)),
  )
})

test('covers every tracked file and classifies every Supabase marker exactly once', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const trackedFiles = nulPaths(gitOutput(['ls-files', '-z', '--cached', '--others', '--exclude-standard']))
  const marker = catalogue.trackedFileCoverage.marker.toLowerCase()
  const separatelyInspected = new Set(
    catalogue.trackedFileCoverage.binaryInspected.map((artifact) => artifact.path),
  )
  const markerFiles = trackedFiles.filter((file) => (
    !separatelyInspected.has(file)
    && readFileSync(path.join(repositoryDirectory, file)).toString('utf8').toLowerCase().includes(marker)
  ))
  const markerSet = new Set(markerFiles)
  const dependencyIds = new Set(catalogue.dependencies.map((entry) => entry.id))

  assert.ok(markerFiles.length > 0)
  assert.equal(new Set(trackedFiles).size, trackedFiles.length)
  assert.equal(markerFiles.every((file) => trackedFiles.includes(file)), true)
  for (const group of catalogue.trackedFileCoverage.groups) {
    assert.ok(dependencyIds.has(group.dependencyId), group.id)
  }
  for (const file of markerFiles) {
    const matches = catalogue.trackedFileCoverage.groups.filter((group) => groupMatches(file, group))
    assert.equal(matches.length, 1, `${file} matched ${matches.map((group) => group.id).join(', ') || 'nothing'}`)
  }

  const referenceFreeFiles = trackedFiles.filter((file) => !markerSet.has(file))
  assert.equal(markerFiles.length + referenceFreeFiles.length, trackedFiles.length)
  assert.ok(referenceFreeFiles.length > 0)
})

test('pins every separately inspected binary artifact by digest', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const dependencyIds = new Set(catalogue.dependencies.map((entry) => entry.id))
  assert.ok(catalogue.trackedFileCoverage.binaryInspected.length > 0)
  for (const artifact of catalogue.trackedFileCoverage.binaryInspected) {
    assert.ok(dependencyIds.has(artifact.dependencyId), artifact.path)
    const digest = createHash('sha256')
      .update(gitOutput(['show', `:${artifact.path}`]))
      .digest('hex')
    assert.equal(digest, artifact.sha256, artifact.path)
    assert.equal(artifact.digestSource, 'canonical indexed Git blob')
    assert.match(artifact.finding, /Supabase/)
  }
})

test('keeps all golden cases identical in prose and machine-readable form', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const proseRows = markdownGoldenRows(readText(goldenPath))
  assert.equal(catalogue.goldenCases.length, 42)
  assert.equal(new Set(catalogue.goldenCases.map((entry) => entry.id)).size, 42)
  assert.deepEqual(proseRows, catalogue.goldenCases)
})

test('fixes promotion, no-network, retention, rollback, and approval rules', () => {
  const contract = readText(contractPath)
  for (const token of [
    'npm run dev',
    'npm run build',
    'npm run preview',
    'dist-migration',
    'VITE_API_BASE_URL',
    'VITE_SUPABASE_URL',
    '@supabase/supabase-js',
    'Tables and PostgREST',
    'Realtime',
    'DNS, TCP, TLS, HTTP, HTTPS, WebSocket, PostgreSQL, and object-storage attempts',
    '30 calendar days',
    'exact GitHub repository, environment, and secret entry names',
    'exact DigitalOcean app, component, and secret entry names',
    'Wildcards',
    'External deletion has no repository rollback',
    'workloop-clinic_postgres_data',
  ]) assert.match(contract, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
})

test('keeps the schema unchanged at the Part 12G head', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const indexedAlembic = gitOutput(['ls-files', '-s', '-z', 'backend/alembic'])
  assert.equal(
    createHash('sha256').update(indexedAlembic).digest('hex'),
    catalogue.alembicIndexSha256,
  )
  assert.deepEqual(alembicHeads(), ['e8a1c3f5b7d9'])
})

test('keeps unresolved external names and destructive authority fail closed', () => {
  const catalogue = JSON.parse(readText(cataloguePath))
  const byId = new Map(catalogue.dependencies.map((entry) => [entry.id, entry]))
  for (const id of ['P13-EXT-001', 'P13-EXT-002', 'P13-EXT-003', 'P13-EXT-004', 'P13-EXT-005', 'P13-EXT-006', 'P13-EXT-007', 'P13-EXT-008', 'P13-RET-001', 'P13-RET-002']) {
    assert.equal(byId.get(id).disposition, 'inspect externally')
    assert.equal(byId.get(id).owner, '13G')
  }
  for (const id of ['P13-DEL-001', 'P13-DEL-002', 'P13-DEL-003']) {
    assert.equal(byId.get(id).disposition, 'destroy only after exact owner approval')
    assert.equal(byId.get(id).owner, '13G')
  }
  assert.match(byId.get('P13-EXT-007').evidence.join(' '), /unresolved/)
  assert.match(byId.get('P13-EXT-008').evidence.join(' '), /unresolved/)
})
