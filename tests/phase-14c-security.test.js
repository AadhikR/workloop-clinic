import assert from 'node:assert/strict'
import test from 'node:test'

import {
  inspectPhase14CSecurity,
  readPhase14CSources,
  validatePhase14CSecurity,
} from '../scripts/verify-phase-14c-security.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14CSources()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14CSources()[key], `mutation did not change ${key}`)
  return validatePhase14CSecurity(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete Phase 14C security contract', () => {
  const report = inspectPhase14CSecurity()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 9)
  assert.equal(report.goldenCases, 6)
  assert.equal(report.databaseRoles, 6)
  assert.equal(report.objectKeys, 4)
  assert.equal(report.operatorRoles, 5)
})

test('14A-GC-007 rejects a shared database role or inherited privileges', () => {
  rejects(mutate('main', 'name       = "workloop_runtime"', 'name       = "workloop_migration"'), 'workloop_runtime exact name')
  rejects(mutate('bootstrap', 'DatabaseRole("workloop_runtime", inherit=False)', 'DatabaseRole("workloop_runtime", inherit=True)'), 'workloop_runtime NOINHERIT')
})

test('14A-GC-008 rejects a shared or over-privileged object key', () => {
  rejects(mutate('main', 'permission = "read"', 'permission = "fullaccess"'), 'file_scanner read grant')
  rejects(mutate('main', 'name  = "workloop-clinic-dev-file-scanner"', 'name  = "workloop-clinic-dev-api"'), 'file_scanner exact object identity name')
})

test('14A-GC-009 rejects a secret or seventh setting in the web build', () => {
  rejects(mutate('main', 'key   = "VITE_OIDC_AUDIENCE"', 'key   = "VITE_CLIENT_SECRET"'), 'exactly six public settings')
  rejects(mutate('main', 'scope = "BUILD_TIME"', 'scope = "BUILD_TIME"\n        type = "SECRET"'), 'secret in web build')
})

test('14A-GC-010 rejects retained bootstrap and synthetic password access', () => {
  rejects(mutate('realm', '"users": []', '"users": [{"username":"bootstrap"}]'), 'cloud realm must not import')
  rejects(mutate('mfa', 'Delete the bootstrap administrator', 'Keep the bootstrap administrator'), 'bootstrap removal control')
})

test('14A-GC-011 rejects an incomplete rotation and revocation contract', () => {
  rejects(mutate('access', 'maximum overlap is 24 hours', 'overlap is open-ended'), 'maximum overlap')
  rejects(mutate('access', '## Revocation', '## Removal'), 'Revocation')
})

test('14A-GC-012 rejects missing operator backup or MFA gates', () => {
  rejects(mutate('main', 'try(var.operator_access.release_reviewer.backup_name, "")', '"backup-not-required"'), 'release_reviewer backup guard')
  rejects(mutate('main', 'try(var.operator_access.security_custodian.primary_mfa, false)', 'true'), 'security_custodian primary MFA guard')
})

test('rejects secret-bearing Terraform output', () => {
  rejects(mutate('outputs', 'value       = local.enabled ? digitalocean_app.shared[0].id : null', 'value       = digitalocean_spaces_key.api[0].secret_key'), 'secret-bearing output')
})
