import assert from 'node:assert/strict'
import test from 'node:test'

import {
  inspectPhase14BInfrastructure,
  readPhase14BSources,
  validatePhase14BInfrastructure,
} from '../scripts/verify-phase-14b-infrastructure.mjs'

function mutate(key, pattern, replacement) {
  const sources = readPhase14BSources()
  sources[key] = sources[key].replace(pattern, replacement)
  assert.notEqual(sources[key], readPhase14BSources()[key], `mutation did not change ${key}`)
  return validatePhase14BInfrastructure(sources).errors
}

function rejects(errors, message) {
  assert.ok(errors.some((error) => error.includes(message)), errors.join('\n'))
}

test('accepts the complete disabled Phase 14B infrastructure contract', () => {
  const report = inspectPhase14BInfrastructure()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 10)
  assert.equal(report.goldenCases, 6)
  assert.equal(report.approvalFields, 16)
})

test('14A-GC-001 rejects a resource that enters a disabled plan', () => {
  rejects(mutate('main', 'count = local.enabled ? 1 : 0', 'count = 1'), 'must be absent from disabled plans')
})

test('14A-GC-002 rejects a contracted name change', () => {
  rejects(mutate('main', /app_name\s*=\s*"workloop-clinic-dev"/, 'app_name = "other"'), 'app name')
})

test('14A-GC-003 rejects a managed replacement VPC', () => {
  rejects(mutate('main', 'data "digitalocean_vpc" "default"', 'resource "digitalocean_vpc" "default"'), 'managed default VPC')
})

test('14A-GC-004 rejects public or destructive object storage', () => {
  rejects(mutate('main', 'acl           = "private"', 'acl           = "public-read"'), 'private bucket ACL')
  rejects(mutate('main', 'force_destroy = false', 'force_destroy = true'), 'non-destructive bucket setting')
  rejects(mutate('main', 'enabled = true', 'enabled = false'), 'bucket versioning')
})

test('14A-GC-005 rejects custom or wildcard addresses', () => {
  rejects(mutate('main', 'spec {', 'spec {\n    domain { name = "clinic.example" }'), 'custom domain')
  rejects(mutate('realm', '${WORKLOOP_PUBLIC_URL}/oidc/callback', '*/oidc/callback'), 'wildcard')
})

test('14A-GC-006 rejects cost drift and a missing ceiling guard', () => {
  rejects(mutate('main', /api\s*=\s*10/, 'api = 11'), 'fixed monthly cost items')
  rejects(mutate('main', 'configuration_ceiling_usd = 70', 'configuration_ceiling_usd = 80'), 'USD 70 configuration ceiling')
})

test('rejects unbounded scaling and automatic deployment', () => {
  rejects(mutate('main', 'service {', 'service {\n      autoscaling {'), 'component autoscaling')
  rejects(mutate('main', 'deploy_on_push = false', 'deploy_on_push = true'), 'automatic branch deployment')
})

test('rejects public or wildcard database sources', () => {
  rejects(mutate('main', 'type  = "app"', 'type  = "ip_addr"'), 'public database firewall source')
  rejects(mutate('main', 'type  = "app"', 'type  = "cidr"'), 'CIDR database firewall source')
})

test('rejects secret outputs', () => {
  rejects(mutate('outputs', 'value       = local.enabled ? digitalocean_app.shared[0].id : null', 'value       = digitalocean_database_cluster.shared[0].password'), 'secret-bearing output')
})

test('rejects a missing ownership label', () => {
  rejects(mutate('main', /owner_role\s*=\s*"infrastructure-custodian"/, 'owner_role = ""'), 'ownership label owner_role')
})

test('rejects an enabled plan guard with a missing approval input', () => {
  rejects(mutate('main', 'try(var.approval.release_reviewer, "")', '"reviewer-not-required"'), 'approval guard release_reviewer')
})
