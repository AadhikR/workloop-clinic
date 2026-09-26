import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build } from 'vite'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const forbiddenPackagePrefix = '@supabase/'
const forbiddenEnvironmentNames = [
  'VITE_SUPABASE_URL',
  'VITE_SUPABASE_ANON_KEY',
  'SUPABASE_SERVICE_ROLE_KEY',
]
const phase13dDependencies = [
  'P13-SVC-004',
  'P13-PKG-001',
  'P13-PKG-002',
  'P13-ENV-001',
  'P13-ENV-002',
  'P13-ENV-003',
]

function readText(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

function filesBelow(relativeDirectory) {
  const directory = path.join(repositoryDirectory, relativeDirectory)
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const relativePath = path.join(relativeDirectory, entry.name)
    return entry.isDirectory() ? filesBelow(relativePath) : [relativePath]
  })
}

function outputEntries(result) {
  return (Array.isArray(result) ? result : [result]).flatMap((item) => item.output ?? [])
}

function alembicHeads() {
  const revisions = new Set()
  const predecessors = new Set()
  for (const name of readdirSync(path.join(repositoryDirectory, 'backend', 'alembic', 'versions'))) {
    if (!name.endsWith('.py')) continue
    const source = readText(path.join('backend', 'alembic', 'versions', name))
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    assert.ok(revision, `Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

test('removes every direct and transitive Supabase package from the locked graph', () => {
  const packageJson = JSON.parse(readText('package.json'))
  const packageLock = JSON.parse(readText('package-lock.json'))
  const declaredPackages = {
    ...packageJson.dependencies,
    ...packageJson.devDependencies,
    ...packageJson.optionalDependencies,
  }

  assert.deepEqual(
    Object.keys(declaredPackages).filter((name) => name.startsWith(forbiddenPackagePrefix)),
    [],
  )
  assert.deepEqual(
    Object.keys(packageLock.packages ?? {})
      .filter((name) => name.startsWith(`node_modules/${forbiddenPackagePrefix}`)),
    [],
  )
  assert.equal(JSON.stringify(packageLock).includes('registry.npmjs.org/@supabase/'), false)
})

test('removes forbidden environment names from active configuration inputs', () => {
  const activeConfigurationFiles = [
    '.env.example',
    '.env.test.example',
    'vite.config.js',
    'docker-compose.yml',
    'docker-compose.phase5h.yml',
    'scripts/new-local-postgres-env.ps1',
    ...filesBelow('.github'),
    ...filesBelow('infra'),
  ]

  for (const relativePath of activeConfigurationFiles) {
    const source = readText(relativePath)
    for (const name of forbiddenEnvironmentNames) {
      assert.equal(source.includes(name), false, `${relativePath} contains ${name}`)
    }
    assert.doesNotMatch(source, /https?:\/\/[^\s'"`]*supabase\.co/i, relativePath)
  }
})

test('keeps hostile Supabase values out of production modules and emitted bytes', async () => {
  const sentinels = {
    VITE_SUPABASE_URL: 'https://phase13d-hostile.invalid',
    VITE_SUPABASE_ANON_KEY: 'phase13d-public-hostile-sentinel',
    SUPABASE_SERVICE_ROLE_KEY: 'phase13d-private-hostile-sentinel',
  }
  const previousValues = new Map()
  for (const [name, value] of Object.entries(sentinels)) {
    previousValues.set(name, process.env[name])
    process.env[name] = value
  }

  let result
  try {
    result = await build({
      configFile: path.join(repositoryDirectory, 'vite.config.js'),
      envFile: false,
      logLevel: 'silent',
      mode: 'production',
      build: { write: false },
    })
  } finally {
    for (const [name, value] of previousValues) {
      if (value === undefined) delete process.env[name]
      else process.env[name] = value
    }
  }

  const entries = outputEntries(result)
  const moduleIds = entries.flatMap((output) => (
    output.type === 'chunk' ? Object.keys(output.modules).map((id) => id.replaceAll('\\', '/')) : []
  ))
  const emittedBytes = entries.map((entry) => (
    entry.type === 'chunk' ? entry.code : String(entry.source ?? '')
  )).join('\n')

  assert.ok(moduleIds.length > 0)
  assert.equal(moduleIds.some((id) => id.includes('/node_modules/@supabase/')), false)
  assert.equal(moduleIds.some((id) => /realtime-js|\/node_modules\/@supabase\/phoenix/.test(id)), false)
  assert.doesNotMatch(emittedBytes, /@supabase|supabase\.co|\/realtime\/v1|phase13d-hostile/i)
})

test('closes the Part 13D catalogue boundary without changing the schema head', () => {
  const catalogue = JSON.parse(readText('docs/migration/phase-13/dependency-catalogue.json'))
  const closure = catalogue.closures['13D']

  assert.equal(closure.status, 'completed')
  assert.deepEqual([...closure.dependencies].sort(), [...phase13dDependencies].sort())
  assert.deepEqual(closure.goldenCases, ['13A-GC-009'])
  assert.ok(closure.evidence.includes('tests/phase-13d-runtime-removal.test.js'))
  assert.ok(closure.evidence.includes('docs/migration/phase-13/PART_13D_COMPLETION.md'))
  assert.deepEqual(alembicHeads(), ['e8a1c3f5b7d9'])
})
