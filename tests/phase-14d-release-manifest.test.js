import assert from 'node:assert/strict'
import test from 'node:test'

import { validateReleaseManifest } from '../scripts/phase-14d-release-manifest.mjs'

const digest = `sha256:${'a'.repeat(64)}`

function manifest() {
  return {
    schemaVersion: 1,
    releaseId: 'phase14d-test',
    deployable: true,
    gitCommit: 'b'.repeat(40),
    backendImage: {
      registryType: 'DOCR',
      registry: '',
      repository: 'backend',
      digest,
    },
    keycloakImage: {
      registryType: 'DOCR',
      registry: '',
      repository: 'keycloak',
      digest,
    },
    frontendSha256: digest,
    frontendRootSha256: digest,
    dependencyLockSha256: { frontend: digest, backend: digest, backendDev: digest },
    terraformSha256: digest,
    appSpecSha256: digest,
    alembicHead: 'e8a1c3f5b7d9',
    createdAt: '2026-09-27T12:00:00.000Z',
    reviewedBy: 'synthetic-reviewer',
  }
}

test('accepts one complete digest-bound release manifest', () => {
  assert.deepEqual(validateReleaseManifest(manifest()), [])
})

test('rejects a nondeployable record, short commit, or wrong schema head', () => {
  const value = manifest()
  value.deployable = false
  value.gitCommit = 'migration/fastapi-keycloak'
  value.alembicHead = 'head'
  const errors = validateReleaseManifest(value)
  assert.ok(errors.some((error) => error.includes('not deployable')))
  assert.ok(errors.some((error) => error.includes('full lowercase commit')))
  assert.ok(errors.some((error) => error.includes('incompatible')))
})

test('rejects mutable tags and unrecorded manifest fields', () => {
  const value = manifest()
  value.backendImage.tag = 'latest'
  value.dependencyLockSha256.mutable = digest
  value.providerLabel = 'deployment-123'
  const errors = validateReleaseManifest(value)
  assert.ok(errors.some((error) => error.includes('backendImage has unexpected field tag')))
  assert.ok(errors.some((error) => error.includes('dependencyLockSha256 has unexpected field mutable')))
  assert.ok(errors.some((error) => error.includes('unexpected manifest field providerLabel')))
})

test('rejects malformed or missing artifact digests', () => {
  const value = manifest()
  value.keycloakImage.digest = 'sha256:mutable'
  value.dependencyLockSha256.backend = ''
  const errors = validateReleaseManifest(value)
  assert.ok(errors.some((error) => error.includes('keycloakImage is invalid')))
  assert.ok(errors.some((error) => error.includes('backendLockSha256 is invalid')))
})
