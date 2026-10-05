import assert from 'node:assert/strict'
import test from 'node:test'

import {
  inspectPhase14DDeployment,
  readPhase14DSources,
  validatePhase14DDeployment,
} from '../scripts/verify-phase-14d-deployment.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14DSources()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14DSources()[key], `mutation did not change ${key}`)
  return validatePhase14DDeployment(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete Phase 14D deployment contract', () => {
  const report = inspectPhase14DDeployment()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 10)
  assert.equal(report.goldenCases, 8)
  assert.equal(report.components, 7)
})

test('14A-GC-013 rejects a missing release digest', () => {
  rejects(mutate('releaseSchema', '"terraformSha256",', ''), 'release schema must require terraformSha256')
})

test('14A-GC-014 rejects a migration that does not verify the exact head', () => {
  rejects(mutate('cloudMigrate', 'EXPECTED_ALEMBIC_HEAD = "f3a5c7e9b1d4"', 'EXPECTED_ALEMBIC_HEAD = "head"'), 'migration EXPECTED_ALEMBIC_HEAD')
})

test('14A-GC-015 rejects an incomplete component health rule', () => {
  rejects(mutate('main', 'timeout_seconds       = 5', 'timeout_seconds       = 10'), 'API health rule')
  rejects(mutate('frontendVerifier', 'response.status === 200', 'response.ok'), 'web HTTP 200 check')
})

test('14A-GC-016 rejects scanner concurrency drift', () => {
  rejects(mutate('scanner', 'LIMIT 1', 'LIMIT 2'), 'single-row claim')
  rejects(mutate('scanner', "interval '15 minutes'", "interval '30 minutes'"), '15-minute lease')
  rejects(
    mutate('main', 'key   = "MALWARE_SCANNER_BACKEND"', 'key   = "MALWARE_SCANNER_DISABLED"'),
    'file-scanner malware backend',
  )
})

test('14A-GC-017 rejects reconciler lease or retry drift', () => {
  rejects(mutate('reconciler', /attempt_count < 8/g, 'attempt_count < 9'), 'eight-attempt limit')
  rejects(mutate('reconciler', /RETRY_DELAYS/g, 'RETRY_WINDOWS'), 'bounded retries')
})

test('14A-GC-018 rejects removal of the expiry advisory lock', () => {
  rejects(mutate('expiry', 'pg_advisory_xact_lock', 'pg_sleep'), 'expiry advisory lock')
})

test('keeps disabled expiry deployments successful without enabling processing', () => {
  rejects(
    mutate('main', 'if [ \\"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\\" = false ]; then exit 0', 'exit 0'),
    'disabled expiry deployment exit',
  )
  rejects(
    mutate('main', 'if [ \\"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\\" != true ]; then exit 1', 'exit 1'),
    'invalid expiry deployment gate',
  )
})

test('14A-GC-019 rejects a worker without termination release', () => {
  rejects(mutate('workerControl', /release_claim/g, 'abandon_claim'), 'worker control release_claim')
  rejects(mutate('main', 'grace_period_seconds = 120', 'grace_period_seconds = 30'), 'termination window')
})

test('14A-GC-020 rejects an unreviewed or automatic branch deployment', () => {
  rejects(mutate('main', 'github_branch         = "migration/fastapi-keycloak"', 'github_branch         = "main"'), 'web reviewed branch')
  rejects(mutate('main', 'branch         = local.github_branch', 'branch         = var.release_manifest.git_commit'), 'web reviewed branch source')
  rejects(mutate('main', 'deploy_on_push = false', 'deploy_on_push = true'), 'automatic deployment')
  rejects(mutate('main', 'digest        = var.release_manifest.backend_image.digest', 'tag           = "latest"'), 'backend digest')
  rejects(mutate('workflow', 'npm run build', 'doctl apps create-deployment'), 'workflow deployment command')
})
