import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  cataloguePath,
  livePath,
  preflightPath,
  releasePath,
  validatePhase15GPromotion,
} from '../scripts/verify-phase-15g-promotion.mjs'

function fixture() {
  const read = (file) => JSON.parse(readFileSync(file, 'utf8'))
  return {
    catalogue: read(cataloguePath),
    preflight: read(preflightPath),
    release: read(releasePath),
    live: read(livePath),
  }
}

test('accepts the reviewed Phase 15G preflight and release binding', () => {
  const values = fixture()
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live, { final: false })
  assert.deepEqual(report.errors, [])
  assert.equal(report.owned, 12)
})

test('rejects automatic deployment before promotion', () => {
  const values = fixture()
  values.preflight.provider.application.automaticDeployment = true
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live, { final: false })
  assert.ok(report.errors.includes('application exposure boundary changed'))
})

test('rejects a forecast above the owner cap', () => {
  const values = fixture()
  values.preflight.provider.billing.reviewedRunForecastUsd = 15.01
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live, { final: false })
  assert.ok(report.errors.includes('provider usage or cap evidence is invalid'))
})

test('rejects a provider build that is not the reviewed local build', () => {
  const values = fixture()
  values.release.frontend.providerBuild.expectedSha256 = `sha256:${'0'.repeat(64)}`
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live, { final: false })
  assert.ok(report.errors.includes('provider frontend expectation does not match the reviewed local build'))
})

test('requires live acceptance in final mode', () => {
  const values = fixture()
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live)
  assert.ok(report.errors.includes('live acceptance did not pass'))
})

test('rejects a live performance measurement above budget', () => {
  const values = fixture()
  values.live.status = 'passed'
  values.live.performance.measurements = Object.fromEntries(Object.entries(values.live.performance.budgets).map(([name, value]) => [name, {
    value,
    sampleCount: 1,
    percentile: 'p95',
    cacheState: 'cold',
  }]))
  values.live.performance.measurements.availabilityP95Ms.value += 1
  const report = validatePhase15GPromotion(values.catalogue, values.preflight, values.release, values.live)
  assert.ok(report.errors.includes('availabilityP95Ms exceeds its budget'))
})
