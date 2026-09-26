import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build, loadConfigFromFile } from 'vite'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const inventoryPath = path.join(
  repositoryDirectory,
  'docs',
  'migration',
  'phase-13',
  'PART_13C_REMOVAL_INVENTORY.json',
)
const inventory = JSON.parse(readFileSync(inventoryPath, 'utf8'))
const canonicalEnvironmentNames = [
  'VITE_API_BASE_URL',
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
  'VITE_OIDC_POST_LOGOUT_REDIRECT_URI',
  'VITE_OIDC_AUDIENCE',
]
const phase13cDependencies = [
  'P13-SRC-001',
  'P13-SRC-002',
  'P13-SRC-003',
  'P13-SRC-004',
  'P13-SRC-005',
  'P13-SVC-001',
  'P13-SVC-002',
  'P13-SVC-003',
  'P13-SVC-005',
]
const phase12Dependencies = [
  'P12-NOT-14',
  'P12-TSK-17',
  'P12-DSH-12',
  'P12-RPT-19',
  'P12-OUT-18',
  'P12-IND-08',
]

function readText(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

function sha256Lines(lines) {
  return createHash('sha256').update(`${lines.join('\n')}\n`).digest('hex')
}

function gitBlobOid(file) {
  const contents = Buffer.from(readFileSync(file, 'utf8').replaceAll('\r\n', '\n'))
  return createHash('sha1')
    .update(Buffer.from(`blob ${contents.length}\0`))
    .update(contents)
    .digest('hex')
}

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const item = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(item) : [item]
  })
}

function outputEntries(result) {
  return (Array.isArray(result) ? result : [result]).flatMap((item) => item.output ?? [])
}

test('accounts for every baseline source, asset, freeze test, and canonical move', () => {
  assert.equal(inventory.baselineCommit, '9127f704089abd5f63d8e146514c1430992544bb')
  for (const pathSet of inventory.removedPathSets) {
    const paths = pathSet.baselinePaths
    assert.deepEqual(paths, [...paths].sort(), `${pathSet.id} path order`)
    assert.equal(paths.every((item) => item.startsWith(pathSet.baselinePrefix)), true)
    if (pathSet.baselinePathPattern) {
      const pattern = new RegExp(pathSet.baselinePathPattern)
      assert.equal(paths.every((item) => pattern.test(item)), true)
    }
    assert.equal(paths.length, pathSet.trackedPathCount, pathSet.id)
    assert.equal(sha256Lines(paths), pathSet.baselinePathSha256, pathSet.id)
  }

  const sourceMove = inventory.canonicalSourceMove
  const canonicalDirectory = path.join(repositoryDirectory, 'src')
  const canonicalFiles = sourceFiles(canonicalDirectory).sort()
  const originalPaths = canonicalFiles.map((file) => (
    `${sourceMove.fromPrefix}${path.relative(canonicalDirectory, file).replaceAll('\\', '/')}`
  ))
  const blobMap = canonicalFiles.map((file) => (
    `${path.relative(canonicalDirectory, file).replaceAll('\\', '/')}\t${gitBlobOid(file)}`
  ))

  assert.equal(originalPaths.length, sourceMove.trackedPathCount)
  assert.equal(sha256Lines(originalPaths), sourceMove.baselinePathSha256)
  assert.equal(
    sourceMove.baselineRelativeBlobMapFormat,
    'relative-path<TAB>git-blob-oid, sorted, LF-terminated',
  )
  assert.equal(sha256Lines(blobMap), sourceMove.baselineRelativeBlobMapSha256)
})

test('leaves one canonical root source tree and no legacy-only path', () => {
  const canonicalFiles = sourceFiles(path.join(repositoryDirectory, 'src'))
  const canonicalPaths = new Set(canonicalFiles.map((file) => (
    path.relative(repositoryDirectory, file).replaceAll('\\', '/')
  )))
  assert.equal(canonicalFiles.length, inventory.canonicalSourceMove.trackedPathCount)
  assert.equal(existsSync(path.join(repositoryDirectory, 'migration')), false)
  assert.equal(existsSync(path.join(repositoryDirectory, 'public')), false)
  for (const pathSet of inventory.removedPathSets) {
    for (const relativePath of pathSet.baselinePaths) {
      if (!canonicalPaths.has(relativePath)) {
        assert.equal(existsSync(path.join(repositoryDirectory, relativePath)), false, relativePath)
      }
    }
  }
  for (const relativePath of inventory.removedExactPaths) {
    assert.equal(existsSync(path.join(repositoryDirectory, relativePath)), false, relativePath)
  }
  assert.equal(
    readdirSync(path.join(repositoryDirectory, 'tests'))
      .filter((name) => /^phase-.*-legacy-freeze\.test\.js$/.test(name))
      .length,
    0,
  )
})

test('uses the canonical commands, configuration, output, and deployment mapping', async () => {
  const packageJson = JSON.parse(readText('package.json'))
  assert.deepEqual(
    {
      dev: packageJson.scripts.dev,
      build: packageJson.scripts.build,
      preview: packageJson.scripts.preview,
    },
    { dev: 'vite', build: 'vite build', preview: 'vite preview' },
  )
  for (const name of inventory.removedPackageScripts) assert.equal(packageJson.scripts[name], undefined)

  const loaded = await loadConfigFromFile(
    { command: 'build', mode: 'production' },
    path.join(repositoryDirectory, 'vite.config.js'),
  )
  assert.ok(loaded)
  assert.deepEqual(Array.from(loaded.config.envPrefix), canonicalEnvironmentNames)
  assert.equal(loaded.config.root, undefined)
  assert.equal(loaded.config.build.outDir, 'dist')
  assert.equal(loaded.config.server.port, 5174)
  assert.equal(loaded.config.server.strictPort, true)
  assert.equal(loaded.config.preview.port, 5174)
  assert.equal(loaded.config.preview.strictPort, true)
  assert.match(readText('infra/digitalocean/main.tf'), /output_dir\s+= "dist"/)
  assert.doesNotMatch(readText('infra/digitalocean/main.tf'), /dist-migration/)
})

test('builds one production graph without legacy modules or Supabase service calls', async () => {
  const result = await build({
    configFile: path.join(repositoryDirectory, 'vite.config.js'),
    envFile: false,
    logLevel: 'silent',
    mode: 'production',
    build: { write: false },
  })
  const entries = outputEntries(result)
  const moduleIds = entries.flatMap((output) => (
    output.type === 'chunk' ? Object.keys(output.modules).map((id) => id.replaceAll('\\', '/')) : []
  ))
  const source = sourceFiles(path.join(repositoryDirectory, 'src'))
    .map((file) => readFileSync(file, 'utf8'))
    .join('\n')
  const output = entries.map((entry) => (
    entry.type === 'chunk' ? entry.code : String(entry.source ?? '')
  )).join('\n')

  assert.ok(moduleIds.some((id) => id.includes('/src/main.jsx')))
  assert.equal(moduleIds.some((id) => id.includes('/migration/src/')), false)
  assert.equal(moduleIds.some((id) => id.includes('/node_modules/@supabase/')), false)
  assert.doesNotMatch(
    source,
    /supabase|createClient|\.auth\.(?:getSession|onAuthStateChange|resetPasswordForEmail|signInWithPassword|signOut|signUp)|\/rest\/v1\/rpc|\/storage\/v1\/|employee_submit_regularisation|employee_submit_document|employee_cancel_leave_request|employee_submit_leave_request|employee_update_contact|link_employee_account|manager_get_expense_queue|manager_get_leave_queue/i,
  )
  assert.doesNotMatch(output, /@supabase|supabase\.co|\/rest\/v1\/rpc|\/storage\/v1\//i)
})

test('removes legacy-only packages but preserves the 13D package and environment boundary', () => {
  const packageJson = JSON.parse(readText('package.json'))
  const packageLock = JSON.parse(readText('package-lock.json'))
  for (const name of inventory.removedDirectPackages) {
    assert.equal(packageJson.dependencies?.[name], undefined, name)
    assert.equal(packageJson.devDependencies?.[name], undefined, name)
    assert.equal(packageLock.packages?.[`node_modules/${name}`], undefined, name)
  }
  assert.equal(
    packageJson.devDependencies[inventory.preservedFor13D.directPackage],
    '^2.106.2',
  )
  for (const name of [
    '@supabase/auth-js',
    '@supabase/functions-js',
    '@supabase/phoenix',
    '@supabase/postgrest-js',
    '@supabase/realtime-js',
    '@supabase/storage-js',
    '@supabase/supabase-js',
  ]) assert.ok(packageLock.packages[`node_modules/${name}`], name)
  for (const relativePath of inventory.preservedFor13D.environmentExamples) {
    assert.equal(existsSync(path.join(repositoryDirectory, relativePath)), true, relativePath)
  }
  assert.match(readText('.env.example'), /VITE_SUPABASE_URL/)
  assert.match(readText('.env.example'), /VITE_SUPABASE_ANON_KEY/)
  assert.match(readText('.env.test.example'), /SUPABASE_SERVICE_ROLE_KEY/)
})

test('closes the assigned Phase 13C and retained Phase 12 catalogue entries', () => {
  const phase13 = JSON.parse(readText('docs/migration/phase-13/dependency-catalogue.json'))
  assert.deepEqual([...phase13.closures['13C'].dependencies].sort(), [...phase13cDependencies].sort())
  assert.deepEqual(
    [...phase13.closures['13C'].goldenCases].sort(),
    ['13A-GC-006', '13A-GC-007', '13A-GC-008', '13A-GC-010'],
  )
  assert.deepEqual(
    [...phase13.closures['13C'].phase12Dependencies].sort(),
    [...phase12Dependencies].sort(),
  )

  const phase12 = JSON.parse(readText('docs/migration/phase-12/cutover/dependency-catalogue.json'))
  const byId = new Map(phase12.dependencies.map((item) => [item.id, item]))
  for (const id of phase12Dependencies) {
    assert.equal(byId.get(id).state, 'retained-for-phase13', id)
    assert.equal(byId.get(id).owner, '13', id)
  }
})
