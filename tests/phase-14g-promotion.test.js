import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assertApplyAuthorized,
  manifestSha256,
  temporaryRunLimitState,
  validateRollbackRequest,
  validateTargetManifest,
} from '../scripts/phase-14g-control.mjs'
import {
  inspectPhase14GPromotion,
  readPhase14GPromotion,
  validatePhase14GPromotion,
} from '../scripts/verify-phase-14g-promotion.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14GPromotion()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14GPromotion()[key], `mutation did not change ${key}`)
  return validatePhase14GPromotion(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete Phase 14G preflight control package', () => {
  const report = inspectPhase14GPromotion()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 8)
  assert.equal(report.goldenCases, 5)
})

test('14A-GC-031 keeps unresolved authenticated facts visible', () => {
  rejects(mutate('preflight', '"applyAuthorized": false', '"applyAuthorized": true'), 'preflight must retain unresolved blockers')
  rejects(mutate('preflight', '"fixedMonthlyUsd": 65.15', '"fixedMonthlyUsd": 66.15'), 'preflight price evidence')
  rejects(mutate('preflight', '"ownerUsageCapUsd": 15', '"ownerUsageCapUsd": 16'), 'preflight price evidence')
  rejects(mutate('target', '"approvalReady": false', '"approvalReady": true'), 'committed target example')
})

test('14A-GC-032 binds apply approval to the exact manifest and cost', () => {
  const template = JSON.parse(readPhase14GPromotion().target)
  assert.match(manifestSha256(template), /^sha256:[0-9a-f]{64}$/)
  assert.throws(() => assertApplyAuthorized(template), /not enabled for provider mutation/)
  const errors = validateTargetManifest({ ...template, pricing: { ...template.pricing, fixedMonthlyUsd: 70.01 } })
  assert.ok(errors.includes('price or duration boundary changed'))
  assert.ok(validateTargetManifest({ ...template, pricing: { ...template.pricing, ownerUsageCapUsd: 16 } }).includes('price or duration boundary changed'))
  assert.ok(validateTargetManifest({
    ...template,
    pricing: {
      ...template.pricing,
      containerRegistry: { ...template.pricing.containerRegistry, plan: 'Starter' },
    },
  }).includes('private container registry plan or conservative charge assumption changed'))
  assert.ok(validateTargetManifest({ ...template, token: 'not-allowed' }).includes('target manifest contains protected material'))
  assert.throws(() => assertApplyAuthorized(template), /not enabled for provider mutation/)
})

test('14A-GC-032 budgets the full registry charge inside a 48-hour plan', () => {
  const actual = JSON.parse(readPhase14GPromotion().target)
  actual.template = false
  actual.preflight.checkedAt = '2026-09-29T12:00:00Z'
  actual.temporaryRun.startsAt = '2026-09-29T12:00:00Z'
  actual.temporaryRun.cleanupDeadlineAt = '2026-10-01T12:00:01Z'
  actual.pricing.currentAccruedUsageUsd = 0.95
  actual.pricing.runtimeResourceProjectionUsd = 4.66
  actual.pricing.taxAndVariableReserveUsd = 1.9
  actual.pricing.reviewedRunForecastUsd = 7
  const errors = validateTargetManifest(actual, { now: new Date('2026-09-29T12:05:00Z') })
  assert.ok(errors.includes('temporary-run timestamps are missing or exceed the approved 48-hour plan'))
  assert.ok(errors.includes('temporary-run forecast does not cover accrued usage, 48-hour resources, the full registry charge, and a positive reserve within the USD 15 cap'))
})

test('14A-GC-032 requires the solo operator and recovery model', () => {
  rejects(mutate('target', '"model": "solo-owner"', '"model": "primary-backup"'), 'target solo-operator model changed')
  rejects(mutate('helper', "operator?.model !== 'solo-owner'", "operator?.model !== 'primary-backup'"), 'solo-owner')
  const template = JSON.parse(readPhase14GPromotion().target)
  const actual = structuredClone(template)
  actual.template = false
  actual.operatorAccess = {
    ...template.operatorAccess,
    operatorName: 'owner',
    routineAccountReference: 'routine-account',
    routineMfa: true,
    emergencyAccountReference: 'routine-account',
    emergencyMfa: true,
    recoveryMaterialCustodyReference: 'offline-kit',
    recoveryTestedOn: '2026-09-29',
  }
  assert.ok(validateTargetManifest(actual, { now: new Date('2026-09-29T00:00:00Z') })
    .includes('solo operator access or recovery evidence is incomplete'))
})

test('14A-GC-033 keeps the first apply in maintenance', () => {
  rejects(mutate('liveRecord', '"maintenanceEnabled": true', '"maintenanceEnabled": false'), 'blocked template')
  rejects(mutate('liveRecord', '"workersEnabled": false', '"workersEnabled": true'), 'blocked template')
})

test('14A-GC-034 requires restart and redeploy proof for every state class', () => {
  for (const marker of ['databaseState', 'keycloakSigningKeyIds', 'privateObjects', 'scannerState', 'reconcilerState', 'expiryState', 'releaseIdentity']) {
    rejects(mutate('liveRecord', `"${marker}": "pending"`, `"missing-${marker}": "pending"`), 'live record template lacks')
  }
  rejects(mutate('runbook', 'Then redeploy the same digest-bound release', 'Then deploy another release'), '14G runbook Then redeploy')
})

test('14A-GC-035 requires owner action without automatic cleanup', () => {
  assert.deepEqual(temporaryRunLimitState(), {
    maintenanceEnabled: true,
    workersEnabled: false,
    automaticCleanup: false,
    ownerActionRequired: true,
  })
  rejects(mutate('target', '"automaticCleanup": false', '"automaticCleanup": true'), 'temporary run')
})

test('rollback remains schema compatible and non-destructive', () => {
  const liveRecord = { rollback: { compatibleReleaseId: 'prior-reviewed' } }
  assert.deepEqual(validateRollbackRequest({
    requestedReleaseId: 'prior-reviewed',
    maintenanceEnabled: true,
    workersEnabled: false,
    alembicHead: 'e8a1c3f5b7d9',
    automaticSchemaDowngrade: false,
    destroyResources: false,
  }, liveRecord), [])
  assert.ok(validateRollbackRequest({
    requestedReleaseId: 'prior-reviewed',
    maintenanceEnabled: true,
    workersEnabled: false,
    alembicHead: 'e8a1c3f5b7d9',
    automaticSchemaDowngrade: false,
    destroyResources: true,
  }, liveRecord).includes('runtime rollback cannot destroy resources'))
})
