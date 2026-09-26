import assert from 'node:assert/strict'
import { createServer as createNetServer } from 'node:net'
import { readdir, readFile, rm } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build, createServer } from 'vite'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(repositoryDirectory, 'vite.config.js')
const outputDirectory = path.join(repositoryDirectory, 'dist')

async function readOutputFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true })
  const files = await Promise.all(entries.map(async (entry) => {
    const entryPath = path.join(directory, entry.name)
    return entry.isDirectory() ? readOutputFiles(entryPath) : [await readFile(entryPath, 'utf8')]
  }))
  return files.flat()
}

test('builds the canonical production graph without Supabase environment variables', async () => {
  await rm(outputDirectory, { force: true, recursive: true })
  const previousSupabaseUrl = process.env.VITE_SUPABASE_URL
  const previousClientSecret = process.env.VITE_CLIENT_SECRET
  process.env.VITE_SUPABASE_URL = 'https://phase13c.invalid'
  process.env.VITE_CLIENT_SECRET = 'phase13c-secret-sentinel'
  let result
  try {
    result = await build({
      configFile,
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
    if (previousClientSecret === undefined) {
      delete process.env.VITE_CLIENT_SECRET
    } else {
      process.env.VITE_CLIENT_SECRET = previousClientSecret
    }
  }
  const outputs = Array.isArray(result) ? result.flatMap((item) => item.output) : result.output
  const moduleIds = outputs.flatMap((output) => (
    output.type === 'chunk' ? Object.keys(output.modules).map((id) => id.replaceAll('\\', '/')) : []
  ))
  const outputText = (await readOutputFiles(outputDirectory)).join('\n')

  assert.ok(moduleIds.length > 0)
  const normalizedRepository = repositoryDirectory.replaceAll('\\', '/')
  assert.ok(moduleIds.some((id) => id.startsWith(`${normalizedRepository}/src/`)))
  assert.equal(moduleIds.some((id) => id.includes('/migration/')), false)
  assert.equal(moduleIds.some((id) => id.includes('node_modules/@supabase/')), false)
  assert.equal(
    /supabase|auth-token|database_url|phase13c\.invalid|phase13c-secret-sentinel/i
      .test(outputText),
    false,
  )
})

test('runs the canonical server on its registered fixed port', async () => {
  const server = await createServer({
    configFile,
    envFile: false,
    optimizeDeps: { noDiscovery: true },
  })
  try {
    await server.listen()
    const response = await fetch('http://127.0.0.1:5174/')
    assert.equal(response.status, 200)
    assert.equal(response.headers.get('referrer-policy'), 'no-referrer')
    assert.ok(await server.transformRequest('/src/main.jsx'))
  } finally {
    await server.close()
  }
})

test('fails instead of selecting another port when 5174 is occupied', async () => {
  const occupiedPort = createNetServer()
  await new Promise((resolve) => occupiedPort.listen(5174, '127.0.0.1', resolve))
  const server = await createServer({
    configFile,
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
