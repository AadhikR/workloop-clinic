import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'

import { checkFrontendBuildIsolation } from '../scripts/frontend-build-isolation.mjs'
import { legacyIsolationPaths, legacyIsolationPlugin } from '../vite.legacy-isolation.js'

function assertRejected(source, importer) {
  const plugin = legacyIsolationPlugin()
  assert.throws(
    () => plugin.resolveId(source, importer),
    /Legacy build isolation rejected forbidden import/,
  )
}

test('rejects migration authentication and source imports from the legacy build', () => {
  const legacyImporter = path.join(legacyIsolationPaths.repositoryDirectory, 'src', 'App.jsx')
  assertRejected('oidc-client-ts', legacyImporter)
  assertRejected('keycloak-js', legacyImporter)
  assertRejected('../migration/src/http.js', legacyImporter)
  assertRejected(path.join(legacyIsolationPaths.migrationDirectory, 'src', 'auth.js'), legacyImporter)
})

test('builds and scans independent legacy and migration production graphs', async () => {
  const counts = await checkFrontendBuildIsolation({
    repositoryDirectory: legacyIsolationPaths.repositoryDirectory,
  })
  assert.ok(counts.legacyModuleCount > 0)
  assert.ok(counts.migrationModuleCount > 0)
})
