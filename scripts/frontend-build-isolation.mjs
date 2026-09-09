import assert from 'node:assert/strict'
import path from 'node:path'
import process from 'node:process'
import { pathToFileURL } from 'node:url'

import { build } from 'vite'

import { migrationIsolationPaths } from '../migration/vite-isolation.js'
import { legacyIsolationPaths } from '../vite.legacy-isolation.js'

const LEGACY_CONFIGURATION_SENTINEL = 'phase-6d-legacy-configuration-sentinel'
const MIGRATION_CONFIGURATION_SENTINEL = 'phase-6d-migration-configuration-sentinel'

function normalizePath(value) {
  return value.replaceAll('\\', '/')
}

function buildOutputs(result) {
  const results = Array.isArray(result) ? result : [result]
  return results.flatMap((item) => item.output ?? [])
}

function moduleIds(result) {
  return buildOutputs(result).flatMap((output) => output.type === 'chunk' ? Object.keys(output.modules) : [])
}

function outputText(result) {
  return buildOutputs(result)
    .filter((output) => output.type === 'chunk' || output.type === 'asset' && typeof output.source === 'string')
    .map((output) => output.type === 'chunk' ? output.code : output.source)
    .join('\n')
}

export function assertFrontendBuildIsolation({ legacyResult, migrationResult }) {
  const legacyModules = moduleIds(legacyResult).map(normalizePath)
  const migrationModules = moduleIds(migrationResult).map(normalizePath)
  const legacyOutput = outputText(legacyResult)
  const migrationOutput = outputText(migrationResult)
  const migrationDirectory = `${normalizePath(legacyIsolationPaths.migrationDirectory)}/`
  const legacySourceDirectory = `${normalizePath(migrationIsolationPaths.legacySourceDirectory)}/`

  assert.ok(legacyModules.length > 0, 'Legacy production graph is empty.')
  assert.ok(migrationModules.length > 0, 'Migration production graph is empty.')
  assert.ok(
    legacyModules.some((id) => id.includes('/node_modules/@supabase/')),
    'Legacy graph must retain its Supabase authority dependency.',
  )
  assert.equal(
    legacyModules.some((id) => id.startsWith(migrationDirectory)
      || id.includes('/node_modules/oidc-client-ts/')
      || id.includes('/node_modules/keycloak-js/')),
    false,
    'Legacy graph contains a migration authentication or client dependency.',
  )
  assert.ok(
    migrationModules.some((id) => id.includes('/node_modules/oidc-client-ts/')),
    'Migration graph must retain its OIDC authority dependency.',
  )
  assert.equal(
    migrationModules.some((id) => id.startsWith(legacySourceDirectory)
      || id.includes('/node_modules/@supabase/')),
    false,
    'Migration graph contains a legacy source or Supabase dependency.',
  )

  assert.match(legacyOutput, new RegExp(LEGACY_CONFIGURATION_SENTINEL))
  assert.doesNotMatch(legacyOutput, new RegExp(MIGRATION_CONFIGURATION_SENTINEL))
  assert.match(migrationOutput, new RegExp(MIGRATION_CONFIGURATION_SENTINEL))
  assert.doesNotMatch(migrationOutput, new RegExp(LEGACY_CONFIGURATION_SENTINEL))

  return {
    legacyModuleCount: legacyModules.length,
    migrationModuleCount: migrationModules.length,
  }
}

function setSentinelEnvironment() {
  const values = {
    VITE_SUPABASE_URL: `https://${LEGACY_CONFIGURATION_SENTINEL}.invalid`,
    VITE_SUPABASE_ANON_KEY: LEGACY_CONFIGURATION_SENTINEL,
    VITE_API_BASE_URL: `https://${MIGRATION_CONFIGURATION_SENTINEL}.invalid`,
    VITE_OIDC_AUTHORITY: `https://${MIGRATION_CONFIGURATION_SENTINEL}.invalid/realms/workloop`,
    VITE_OIDC_CLIENT_ID: MIGRATION_CONFIGURATION_SENTINEL,
    VITE_OIDC_REDIRECT_URI: `https://${MIGRATION_CONFIGURATION_SENTINEL}.invalid/oidc/callback`,
    VITE_OIDC_POST_LOGOUT_REDIRECT_URI: `https://${MIGRATION_CONFIGURATION_SENTINEL}.invalid/`,
    VITE_OIDC_AUDIENCE: MIGRATION_CONFIGURATION_SENTINEL,
  }
  const previous = new Map()
  for (const [name, value] of Object.entries(values)) {
    previous.set(name, process.env[name])
    process.env[name] = value
  }
  return () => {
    for (const [name, value] of previous) {
      if (value === undefined) delete process.env[name]
      else process.env[name] = value
    }
  }
}

export async function checkFrontendBuildIsolation(options = {}) {
  const repositoryDirectory = path.resolve(options.repositoryDirectory ?? process.cwd())
  const restoreEnvironment = setSentinelEnvironment()
  try {
    const legacyResult = await build({
      configFile: path.join(repositoryDirectory, 'vite.config.js'),
      envFile: false,
      logLevel: 'silent',
      mode: 'production',
      build: { write: false },
    })
    const migrationResult = await build({
      configFile: path.join(repositoryDirectory, 'migration', 'vite.migration.config.js'),
      envFile: false,
      logLevel: 'silent',
      mode: 'production',
      build: { write: false },
    })
    return assertFrontendBuildIsolation({ legacyResult, migrationResult })
  } finally {
    restoreEnvironment()
  }
}

async function run() {
  try {
    const counts = await checkFrontendBuildIsolation()
    console.log(`Frontend isolation passed for ${counts.legacyModuleCount} legacy modules and ${counts.migrationModuleCount} migration modules.`)
  } catch (error) {
    console.error(`Frontend isolation failed: ${error.message}`)
    process.exitCode = 1
  }
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null
if (invokedPath === import.meta.url) await run()
