import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  cataloguePath,
  evidencePath,
  inspectPhase15FAcceptance,
  validatePhase15FAcceptance,
} from '../scripts/verify-phase-15f-acceptance.mjs'

function fixture() {
  return {
    catalogue: JSON.parse(readFileSync(cataloguePath, 'utf8')),
    evidence: JSON.parse(readFileSync(evidencePath, 'utf8')),
  }
}

test('accepts the complete Phase 15F local acceptance record', () => {
  const report = inspectPhase15FAcceptance()
  assert.deepEqual(report.errors, [])
  assert.equal(report.routeGroups, 25)
  assert.equal(report.metrics, 6)
})

test('rejects a transfer measurement above its budget', () => {
  const { catalogue, evidence } = fixture()
  evidence.performance.measurements.initialCompressedTransferBytes.value =
    evidence.performance.budgets.initialCompressedTransferBytes + 1
  const report = validatePhase15FAcceptance(catalogue, evidence)
  assert.ok(report.errors.includes('initialCompressedTransferBytes exceeds its budget'))
})

test('rejects missing backend denial scope', () => {
  const { catalogue, evidence } = fixture()
  evidence.denials.scopes = evidence.denials.scopes.filter((scope) => scope !== 'cross-company')
  const report = validatePhase15FAcceptance(catalogue, evidence)
  assert.ok(report.errors.some((error) => error.includes('denial scopes is missing cross-company')))
})

test('rejects an incomplete protected file flow', () => {
  const { catalogue, evidence } = fixture()
  evidence.fileFlows[0].cleanup = 'missing'
  const report = validatePhase15FAcceptance(catalogue, evidence)
  assert.ok(report.errors.includes('P15-FLOW-001 did not pass cleanup'))
})

test('rejects incomplete accessibility coverage', () => {
  const { catalogue, evidence } = fixture()
  evidence.accessibility.checks = evidence.accessibility.checks.filter((check) => check !== 'dialogs')
  const report = validatePhase15FAcceptance(catalogue, evidence)
  assert.ok(report.errors.some((error) => error.includes('accessibility checks is missing dialogs')))
})

test('rejects a broad or wrong cleanup target', () => {
  const { catalogue, evidence } = fixture()
  evidence.cleanup.composeProject = 'workloop-clinic'
  const report = validatePhase15FAcceptance(catalogue, evidence)
  assert.ok(report.errors.includes('cleanup project is not the 15F disposable project'))
})
