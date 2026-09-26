import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { build, loadConfigFromFile } from 'vite'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const frontendConfigPath = path.join(repositoryDirectory, 'vite.config.js')
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

function productionModules(result) {
  return outputEntries(result).flatMap((output) => (
    output.type === 'chunk' ? Object.keys(output.modules).map((id) => id.replaceAll('\\', '/')) : []
  ))
}

test('keeps the promoted application on the canonical commands', () => {
  const packageJson = JSON.parse(readText('package.json'))
  assert.deepEqual(
    {
      dev: packageJson.scripts.dev,
      build: packageJson.scripts.build,
      preview: packageJson.scripts.preview,
    },
    {
      dev: 'vite',
      build: 'vite build',
      preview: 'vite preview',
    },
  )
  assert.equal(packageJson.scripts['build:legacy'], undefined)
  assert.equal(packageJson.scripts['build:dist'], undefined)
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
  assert.match(terraform, /output_dir\s+= "dist"/)
  assert.doesNotMatch(terraform, /dist-migration/)
  assert.doesNotMatch(workflow, /npm run [^\n]*legacy/i)
  assert.doesNotMatch(terraform, /npm run [^"\n]*legacy|build:migration/i)
})

test('keeps the fixed origin and public environment allowlist aligned', async () => {
  const loaded = await loadConfigFromFile(
    { command: 'build', mode: 'production' },
    frontendConfigPath,
  )
  assert.ok(loaded)
  assert.deepEqual(Array.from(loaded.config.envPrefix), publicEnvironmentNames)
  assert.equal(loaded.config.server.host, '127.0.0.1')
  assert.equal(loaded.config.server.port, 5174)
  assert.equal(loaded.config.server.strictPort, true)
  assert.equal(loaded.config.preview.host, '127.0.0.1')
  assert.equal(loaded.config.preview.port, 5174)
  assert.equal(loaded.config.preview.strictPort, true)
  assert.equal(loaded.config.build.outDir, 'dist')

  const frontendEnvironment = readText('.env.example')
  const backendEnvironment = readText('backend/.env.example')
  const localEnvironmentBuilder = readText('scripts/new-local-postgres-env.ps1')
  const backendOrigin = readText('backend/app/http/middleware.py')
  const browserJourney = readText('scripts/verify-phase-3g-browser.mjs')

  for (const name of publicEnvironmentNames) {
    assert.match(frontendEnvironment, new RegExp(`^${name}=`, 'm'))
  }
  assert.match(frontendEnvironment, /VITE_OIDC_REDIRECT_URI=http:\/\/127\.0\.0\.1:5174\/oidc\/callback/)
  assert.match(frontendEnvironment, /VITE_OIDC_POST_LOGOUT_REDIRECT_URI=http:\/\/127\.0\.0\.1:5174\//)
  assert.match(backendEnvironment, /^FRONTEND_URL=http:\/\/127\.0\.0\.1:5174$/m)
  assert.match(localEnvironmentBuilder, /"FRONTEND_URL=http:\/\/127\.0\.0\.1:5174"/)
  assert.match(backendOrigin, /ALLOWED_ORIGIN = "http:\/\/127\.0\.0\.1:5174"/)
  assert.match(browserJourney, /page\.goto\('http:\/\/127\.0\.0\.1:5174\/'\)/)
})

test('keeps OIDC in the canonical production graph without Supabase', async () => {
  const result = await build({
    configFile: frontendConfigPath,
    envFile: false,
    logLevel: 'silent',
    mode: 'production',
    build: { write: false },
  })
  const modules = productionModules(result)

  assert.ok(modules.some((id) => id.includes('/node_modules/oidc-client-ts/')))
  assert.equal(modules.some((id) => id.includes('/node_modules/@supabase/')), false)
  assert.ok(modules.some((id) => id.startsWith(`${repositoryDirectory.replaceAll('\\', '/')}/src/`)))
  assert.equal(modules.some((id) => id.includes('/migration/src/')), false)
})
