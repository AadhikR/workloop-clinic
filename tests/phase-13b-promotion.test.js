import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build, loadConfigFromFile } from 'vite'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const migrationConfigPath = path.join(repositoryDirectory, 'migration', 'vite.migration.config.js')
const publicEnvironmentNames = [
  'VITE_API_BASE_URL',
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
  'VITE_OIDC_POST_LOGOUT_REDIRECT_URI',
  'VITE_OIDC_AUDIENCE',
]

function readText(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

function outputEntries(result) {
  const results = Array.isArray(result) ? result : [result]
  return results.flatMap((item) => item.output ?? [])
}

function productionBytes(result) {
  return outputEntries(result)
    .map((output) => {
      const contents = output.type === 'chunk' ? output.code : output.source
      const bytes = typeof contents === 'string' ? contents : Array.from(contents ?? [])
      return [output.fileName, bytes]
    })
    .sort(([left], [right]) => left.localeCompare(right))
}

function productionModules(result) {
  return outputEntries(result).flatMap((output) => (
    output.type === 'chunk' ? Object.keys(output.modules).map((id) => id.replaceAll('\\', '/')) : []
  ))
}

test('promotes the migration commands and keeps one explicit legacy rollback build', () => {
  const packageJson = JSON.parse(readText('package.json'))
  assert.deepEqual(
    {
      dev: packageJson.scripts.dev,
      build: packageJson.scripts.build,
      preview: packageJson.scripts.preview,
    },
    {
      dev: 'vite --config migration/vite.migration.config.js',
      build: 'vite build --config migration/vite.migration.config.js',
      preview: 'vite preview --config migration/vite.migration.config.js',
    },
  )
  assert.equal(packageJson.scripts['build:legacy'], 'vite build --config vite.config.js')
  assert.equal(packageJson.scripts['build:migration'], undefined)
  assert.equal(packageJson.scripts['dev:migration'], undefined)

  for (const name of ['dev', 'build', 'preview']) {
    assert.doesNotMatch(packageJson.scripts[name], /legacy|supabase|\|\||&&|\$|%/i)
  }
  for (const [name, command] of Object.entries(packageJson.scripts)) {
    if (/legacy/i.test(command)) assert.match(name, /legacy/i)
  }
})

test('keeps CI and DigitalOcean on the same promoted command and output', () => {
  const workflow = readText('.github/workflows/migration-foundation.yml')
  const terraform = readText('infra/digitalocean/main.tf')

  assert.match(workflow, /- name: Build frontend\n\s+run: npm run build/)
  assert.match(terraform, /build_command\s+= "npm ci && npm run build"/)
  assert.match(terraform, /output_dir\s+= "dist-migration"/)
  assert.doesNotMatch(workflow, /npm run [^\n]*legacy/i)
  assert.doesNotMatch(terraform, /npm run [^"\n]*legacy|build:migration/i)
})

test('keeps the fixed origin and public environment allowlist aligned', async () => {
  const loaded = await loadConfigFromFile(
    { command: 'build', mode: 'production' },
    migrationConfigPath,
  )
  assert.ok(loaded)
  assert.deepEqual(Array.from(loaded.config.envPrefix), publicEnvironmentNames)
  assert.equal(loaded.config.server.host, '127.0.0.1')
  assert.equal(loaded.config.server.port, 5174)
  assert.equal(loaded.config.server.strictPort, true)
  assert.equal(loaded.config.preview.host, '127.0.0.1')
  assert.equal(loaded.config.preview.port, 5174)
  assert.equal(loaded.config.preview.strictPort, true)
  assert.equal(loaded.config.build.outDir, '../dist-migration')

  const migrationEnvironment = readText('migration/.env.example')
  const backendEnvironment = readText('backend/.env.example')
  const localEnvironmentBuilder = readText('scripts/new-local-postgres-env.ps1')
  const backendOrigin = readText('backend/app/http/middleware.py')
  const browserJourney = readText('scripts/verify-phase-3g-browser.mjs')

  for (const name of publicEnvironmentNames) {
    assert.match(migrationEnvironment, new RegExp(`^${name}=`, 'm'))
  }
  assert.deepEqual(
    [...migrationEnvironment.matchAll(/^VITE_[A-Z_]+=/gm)].map((match) => match[0].slice(0, -1)),
    publicEnvironmentNames,
  )
  assert.match(migrationEnvironment, /VITE_OIDC_REDIRECT_URI=http:\/\/127\.0\.0\.1:5174\/oidc\/callback/)
  assert.match(migrationEnvironment, /VITE_OIDC_POST_LOGOUT_REDIRECT_URI=http:\/\/127\.0\.0\.1:5174\//)
  assert.match(backendEnvironment, /^FRONTEND_URL=http:\/\/127\.0\.0\.1:5174$/m)
  assert.match(localEnvironmentBuilder, /"FRONTEND_URL=http:\/\/127\.0\.0\.1:5174"/)
  assert.match(backendOrigin, /ALLOWED_ORIGIN = "http:\/\/127\.0\.0\.1:5174"/)
  assert.match(browserJourney, /page\.goto\('http:\/\/127\.0\.0\.1:5174\/'\)/)
})

test('matches the previous migration production graph and bytes', async () => {
  const buildCommand = JSON.parse(readText('package.json')).scripts.build
  const configArgument = buildCommand.match(/--config ([^ ]+)$/)
  assert.ok(configArgument)
  const promotedConfigPath = path.join(repositoryDirectory, configArgument[1])
  const promotedResult = await build({
    configFile: promotedConfigPath,
    envFile: false,
    logLevel: 'silent',
    mode: 'production',
    build: { write: false },
  })
  const previousMigrationResult = await build({
    configFile: migrationConfigPath,
    envFile: false,
    logLevel: 'silent',
    mode: 'production',
    build: { write: false },
  })
  const modules = productionModules(promotedResult)

  assert.deepEqual(productionBytes(promotedResult), productionBytes(previousMigrationResult))
  assert.ok(modules.some((id) => id.includes('/node_modules/oidc-client-ts/')))
  assert.equal(modules.some((id) => id.includes('/node_modules/@supabase/')), false)
  assert.equal(modules.some((id) => id.startsWith(`${repositoryDirectory.replaceAll('\\', '/')}/src/`)), false)
})
