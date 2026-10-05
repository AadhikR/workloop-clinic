import assert from 'node:assert/strict'
import test from 'node:test'

import {
  inspectPhase14HReview,
  readPhase14HReview,
  validatePhase14HReview,
} from '../scripts/verify-phase-14h-review.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14HReview()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14HReview()[key], `mutation did not change ${key}`)
  return validatePhase14HReview(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('traces every Phase 14 inventory item and golden case exactly once', () => {
  const report = inspectPhase14HReview()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 57)
  assert.equal(report.goldenCases, 38)
  assert.deepEqual(report.alembicHeads, ['f3a5c7e9b1d4'])
})

test('rejects trace omissions, duplicates, owner drift, and missing evidence', () => {
  rejects(mutate('trace', '"id": "P14-INF-001"', '"id": "P14-INF-002"'), 'inventory trace contains duplicate IDs')
  rejects(mutate('trace', '"owner": "14B"', '"owner": "14H"'), 'owner does not match the catalogue')
  rejects(mutate('trace', '"source": [', '"missingSource": ['), '14B evidence set lacks source')
})

test('rejects boundary, rollback, live, and protected-evidence drift', () => {
  rejects(mutate('trace', '"automaticDeployment": "passed"', '"automaticDeployment": "failed"'), 'phase boundary did not pass')
  rejects(mutate('trace', '"14H", "14G", "14F"', '"14G", "14H", "14F"'), 'phase rollback order changed')
  rejects(mutate('live', '"customDomain": false', '"customDomain": true'), 'closing live target boundary changed')
  rejects(mutate('live', '"identitiesRemoved": 3', '"identitiesRemoved": 2'), 'closing synthetic cleanup is incomplete')
  rejects(mutate('live', '"integratedPortal": false', '"integratedPortal": true'), 'closing architecture boundary changed')
  rejects(mutate('releaseIdentity', '"liveChangeRequired": false', '"liveChangeRequired": true'), 'release-identity correction decision changed')
  rejects(mutate('trace', '"reviewedBaselineCommit"', '"privateKey"'), 'prohibited evidence field')
})

test('keeps the complete Part 14 verifier set and closing workflow route', () => {
  rejects(mutate('workflow', 'name: Verify Phase 14H independent review', 'name: Skip Phase 14H independent review'), 'closing workflow')
  rejects(mutate('catalogue', '"rollbackOrder": ["14H", "14G"', '"rollbackOrder": ["14G", "14H"'), 'phase rollback order changed')
})
