import assert from 'node:assert/strict'
import { Buffer } from 'node:buffer'
import test from 'node:test'

import {
  openPortableExport,
  sealPortableExport,
  selectRollbackManifest,
} from '../scripts/phase-14f-recovery.mjs'
import {
  inspectPhase14FRecovery,
  readPhase14FRecovery,
  validatePhase14FRecovery,
} from '../scripts/verify-phase-14f-recovery.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14FRecovery()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14FRecovery()[key], `mutation did not change ${key}`)
  return validatePhase14FRecovery(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete Phase 14F recovery contract', () => {
  const report = inspectPhase14FRecovery()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 7)
  assert.equal(report.goldenCases, 5)
  assert.equal(report.backupClasses, 5)
})

test('14A-GC-026 rejects a missing database comparison or plaintext export', () => {
  rejects(mutate('record', '"encrypted": true', '"encrypted": false'), 'encrypted portable export is missing')
  rejects(mutate('record', '"id": "signing-key-id-digest"', '"id": "missing-signing-key-id-digest"'), 'signing-key-id-digest')
})

test('14A-GC-027 rejects object count, byte, version, key, or content gaps', () => {
  for (const id of ['object-version-count', 'object-opaque-key-digest', 'object-count', 'object-byte-count', 'object-content-digest']) {
    rejects(mutate('record', `"id": "${id}"`, `"id": "missing-${id}"`), id)
  }
})

test('14A-GC-028 rejects writes, workers, or journeys before every comparison passes', () => {
  rejects(mutate('record', '"applicationWritesEnabled": false', '"applicationWritesEnabled": true'), 'write block')
  rejects(mutate('record', '"workers": "passed"', '"workers": "blocked"'), 'workers')
  rejects(mutate('record', '"status": "passed"', '"status": "failed"'), 'recovery comparison')
  rejects(mutate('record', '"id": "configuration-value-digest"', '"id": "missing-configuration-value-digest"'), 'configuration-value-digest')
  rejects(mutate('contract', '"recordValues": false', '"recordValues": true'), 'protected configuration continuity')
})

test('14A-GC-029 requires an explicit schema-compatible reviewed rollback manifest', () => {
  const digest = `sha256:${'a'.repeat(64)}`
  const currentManifest = { releaseId: 'current', alembicHead: 'e8a1c3f5b7d9' }
  const candidateManifest = {
    releaseId: 'prior', deployable: true, reviewedBy: 'reviewer', alembicHead: 'e8a1c3f5b7d9',
    backendImage: { digest }, keycloakImage: { digest },
  }
  assert.equal(selectRollbackManifest({ currentManifest, candidateManifest, requestedReleaseId: 'prior' }), candidateManifest)
  assert.throws(() => selectRollbackManifest({ currentManifest, candidateManifest }), /explicit release ID/)
  assert.throws(() => selectRollbackManifest({
    currentManifest,
    candidateManifest: { ...candidateManifest, alembicHead: 'd8f0a2c4e6b1' },
    requestedReleaseId: 'prior',
  }), /not schema compatible/)
  rejects(mutate('contract', '"automaticSchemaDowngrade": false', '"automaticSchemaDowngrade": true'), 'rollback contract is unsafe')
})

test('14A-GC-030 rejects broad cleanup or missing retained evidence', () => {
  rejects(mutate('record', '"retained": true', '"retained": false'), 'retained evidence')
  rejects(mutate(
    'record',
    '"workloop-phase14f-restore_postgres_data",\n      "workloop-phase14f-restore_storage_data"',
    '"workloop-clinic_postgres_data",\n      "workloop-phase14f-restore_storage_data"',
  ), 'cleanup target allowlist')
  rejects(mutate('contract', '"exactTargetsOnly": true', '"exactTargetsOnly": false'), 'cleanup contract is unsafe')
  rejects(mutate('evidence', '"disposableVolumesRemaining": 0', '"disposableVolumesRemaining": 1'), 'retained local recovery evidence')
})

test('portable database exports are authenticated and target bound', () => {
  const key = Buffer.alloc(32, 7)
  const plaintext = Buffer.from('synthetic pg dump')
  const sealed = sealPortableExport({
    plaintext,
    database: 'workloop',
    releaseId: 'phase14f-test',
    keyId: '14f00001',
    key,
    nonce: Buffer.alloc(12, 3),
  })
  assert.match(sealed.sha256, /^sha256:[0-9a-f]{64}$/)
  assert.deepEqual(openPortableExport({
    payload: sealed.payload,
    expectedDatabase: 'workloop',
    expectedReleaseId: 'phase14f-test',
    keys: { '14f00001': key },
  }), plaintext)
  assert.throws(() => openPortableExport({
    payload: sealed.payload,
    expectedDatabase: 'keycloak',
    expectedReleaseId: 'phase14f-test',
    keys: { '14f00001': key },
  }), /does not match/)
  const changed = Buffer.from(sealed.payload)
  changed[changed.length - 1] ^= 1
  assert.throws(() => openPortableExport({
    payload: changed,
    expectedDatabase: 'workloop',
    expectedReleaseId: 'phase14f-test',
    keys: { '14f00001': key },
  }), /authentication failed/)
})

test('provider-native proof remains an explicit Part 14G dependency', () => {
  rejects(mutate('contract', '"status": "pending-14g-provider-live"', '"status": "verified"'), 'provider-live backup evidence')
  rejects(mutate('record', '"sharedPromotionAllowed": false', '"sharedPromotionAllowed": true'), 'provider-live dependency')
})
