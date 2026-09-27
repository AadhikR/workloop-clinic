import assert from 'node:assert/strict'
import test from 'node:test'

import {
  inspectPhase14EOperations,
  readPhase14EOperations,
  validatePhase14EOperations,
} from '../scripts/verify-phase-14e-operations.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14EOperations()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14EOperations()[key], `mutation did not change ${key}`)
  return validatePhase14EOperations(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete Phase 14E operations contract', () => {
  const report = inspectPhase14EOperations()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 8)
  assert.equal(report.goldenCases, 5)
  assert.ok(report.signals >= 20)
})

test('14A-GC-021 rejects incomplete safe-log and evidence controls', () => {
  rejects(mutate('logging', /SAFE_LOG_FIELDS/g, 'LOG_FIELDS'), 'safe logger SAFE_LOG_FIELDS')
  rejects(mutate('contract', '"signed URL"', '"public URL"'), 'prohibited signed URL')
})

test('14A-GC-022 rejects a signal missing its assigned response', () => {
  rejects(mutate('contract', '"response":', '"missingResponse":'), 'lacks response')
})

test('14A-GC-023 rejects missing worker conditions', () => {
  rejects(mutate('contract', /"condition":"stale-heartbeat"/g, '"condition":"other"'), 'lacks stale-heartbeat')
  rejects(mutate('scanner', /worker_terminal_failure/g, 'worker_failed'), 'scanner terminal signal')
})

test('14A-GC-024 rejects a higher ceiling or spending-cap claim', () => {
  rejects(mutate('contract', '"configurationCeilingUsd": 70', '"configurationCeilingUsd": 71'), 'USD 70')
  rejects(mutate('contract', '"alertIsSpendingCap": false', '"alertIsSpendingCap": true'), 'must not claim')
  rejects(mutate('variables', 'var.reviewed_monthly_forecast_usd <= var.configuration_ceiling_usd', 'var.reviewed_monthly_forecast_usd <= 80'), 'reviewed forecast fail-closed')
})

test('14A-GC-025 rejects an incomplete incident record', () => {
  rejects(mutate('incidentSchema', '"ownerNotifications",', ''), 'incident schema must require ownerNotifications')
  rejects(mutate('incidentExample', '"template": true', '"template": false'), 'must remain a template')
})

test('rejects active provider mutation or an external alert vendor', () => {
  rejects(mutate('provider', '"providerMutationEnabled": false', '"providerMutationEnabled": true'), 'default to false')
  rejects(mutate('provider', '"vendor": null', '"vendor": "example"'), 'vendor must be absent')
})
