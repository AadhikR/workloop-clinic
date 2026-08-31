import assert from 'node:assert/strict'
import { createServer as createHttpServer } from 'node:http'
import { createServer as createNetServer } from 'node:net'
import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build, createServer } from 'vite'

import { migrationIsolationPaths, migrationIsolationPlugin } from '../migration/vite-isolation.js'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const migrationConfigFile = path.join(repositoryDirectory, 'migration', 'vite.migration.config.js')
const migrationOutputDirectory = path.join(repositoryDirectory, 'dist-migration')
const fixtureDirectory = path.join(repositoryDirectory, 'migration', '.phase-3f-fixture')
function assertRejected(source, importer) {
  const plugin = migrationIsolationPlugin()
  assert.throws(
    () => plugin.resolveId(source, importer),
    /Migration build isolation rejected forbidden import/,
  )
}

async function readOutputFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name)
    return entry.isDirectory() ? readOutputFiles(entryPath) : [await readFile(entryPath, 'utf8')]
  }))
  return files.flat()
}

test('rejects direct and transitive Supabase and legacy source imports', async () => {
  const migrationImporter = path.join(migrationIsolationPaths.migrationDirectory, 'src', 'App.jsx')
  const transitiveImporter = path.join(migrationIsolationPaths.migrationDirectory, 'src', 'dependency.jsx')

  assertRejected('@supabase/supabase-js', migrationImporter)
  assertRejected('@supabase/auth-js', transitiveImporter)
  assertRejected('../../src/lib/supabase.js', migrationImporter)
  assertRejected(path.join(migrationIsolationPaths.legacySourceDirectory, 'lib', 'supabase.js'), transitiveImporter)

  await mkdir(fixtureDirectory, { recursive: true })
  try {
    await writeFile(path.join(fixtureDirectory, 'direct.jsx'), "import '../../src/lib/supabase.js'\n")
    await writeFile(path.join(fixtureDirectory, 'entry.jsx'), "import './transitive.jsx'\n")
    await writeFile(path.join(fixtureDirectory, 'transitive.jsx'), "import '@supabase/supabase-js'\n")

    for (const entry of ['direct.jsx', 'entry.jsx']) {
      await assert.rejects(
        build({
          configFile: migrationConfigFile,
          envFile: false,
          root: fixtureDirectory,
          build: {
            rollupOptions: { input: path.join(fixtureDirectory, entry) },
            write: false,
          },
        }),
        /Migration build isolation rejected forbidden import/,
      )
    }
  } finally {
    await rm(fixtureDirectory, { force: true, recursive: true })
  }
})

test('builds an isolated production graph without Supabase environment variables', async () => {
  await rm(migrationOutputDirectory, { force: true, recursive: true })
  const previousSupabaseUrl = process.env.VITE_SUPABASE_URL
  process.env.VITE_SUPABASE_URL = 'https://migration-test.supabase.co'
  let result
  try {
    result = await build({
      configFile: migrationConfigFile,
      mode: 'production',
      envFile: false,
      build: { write: true },
    })
  } finally {
    if (previousSupabaseUrl === undefined) {
      delete process.env.VITE_SUPABASE_URL
    } else {
      process.env.VITE_SUPABASE_URL = previousSupabaseUrl
    }
  }
  const outputs = Array.isArray(result) ? result.flatMap((item) => item.output) : result.output
  const moduleIds = outputs.flatMap((output) => output.type === 'chunk' ? Object.keys(output.modules) : [])
  const outputText = (await readOutputFiles(migrationOutputDirectory)).join('\n')

  assert.ok(moduleIds.length > 0)
  assert.equal(moduleIds.some((id) => id.startsWith(`${migrationIsolationPaths.legacySourceDirectory}${path.sep}`)), false)
  assert.equal(moduleIds.some((id) => id.includes('node_modules/@supabase/')), false)
  assert.equal(/supabase|auth-token|access_token|database_url/i.test(outputText), false)
})

test('runs the migration server on its registered fixed port', async () => {
  const server = await createServer({
    configFile: migrationConfigFile,
    envFile: false,
    optimizeDeps: { noDiscovery: true },
  })
  try {
    await server.listen()
    const response = await fetch('http://127.0.0.1:5174/')
    assert.equal(response.status, 200)
    assert.ok(await server.transformRequest('/src/main.jsx'))
  } finally {
    await server.close()
  }
})

test('fails instead of selecting another port when 5174 is occupied', async () => {
  const occupiedPort = createNetServer()
  await new Promise((resolve) => occupiedPort.listen(5174, '127.0.0.1', resolve))
  const server = await createServer({
    configFile: migrationConfigFile,
    envFile: false,
    optimizeDeps: { noDiscovery: true },
  })
  try {
    await assert.rejects(server.listen(), /Port 5174 is already in use/)
  } finally {
    await server.close()
    await new Promise((resolve) => occupiedPort.close(resolve))
  }
})
