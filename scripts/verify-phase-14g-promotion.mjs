import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { validateTargetManifest } from './phase-14g-control.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const relativeFiles = {
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
  target: 'infra/digitalocean/phase-14g-target-manifest.example.json',
  liveRecord: 'infra/digitalocean/phase-14g-live-record.example.json',
  preflight: 'docs/migration/phase-14/evidence/PART_14G_PREFLIGHT.json',
  liveEvidence: 'docs/migration/phase-14/evidence/PART_14G_LIVE.json',
  completion: 'docs/migration/phase-14/PART_14G_COMPLETION.md',
  runbook: 'docs/migration/phase-14/PART_14G_RUNBOOK.md',
  readme: 'infra/digitalocean/README.md',
  helper: 'scripts/phase-14g-control.mjs',
  variables: 'infra/digitalocean/variables.tf',
  main: 'infra/digitalocean/main.tf',
  recovery: 'infra/digitalocean/recovery-contract.json',
}

const expectedInventory = Array.from({ length: 8 }, (_, index) => `P14-PRM-${String(index + 1).padStart(3, '0')}`)
const expectedGolden = Array.from({ length: 5 }, (_, index) => `14A-GC-${String(index + 31).padStart(3, '0')}`)

function readText(root, relativePath) {
  const absolute = path.join(root, relativePath)
  return existsSync(absolute) ? readFileSync(absolute, 'utf8').replaceAll('\r\n', '\n') : ''
}

export function readPhase14GPromotion(root = repositoryDirectory) {
  return Object.fromEntries(Object.entries(relativeFiles).map(([key, value]) => [key, readText(root, value)]))
}

function parseJson(errors, source, label, required = true) {
  if (!source && !required) return null
  try {
    return JSON.parse(source)
  } catch {
    errors.push(`missing or invalid ${label}`)
    return {}
  }
}

function requireText(errors, source, marker, label) {
  if (!source.includes(marker)) errors.push(`missing ${label}`)
}

export function validatePhase14GPromotion(sources, { final = false } = {}) {
  const errors = []
  const catalogue = parseJson(errors, sources.catalogue, 'deployment catalogue')
  const target = parseJson(errors, sources.target, 'target manifest example')
  const liveRecord = parseJson(errors, sources.liveRecord, 'live record example')
  const preflight = parseJson(errors, sources.preflight, 'preflight evidence')
  const recovery = parseJson(errors, sources.recovery, 'recovery contract')
  const inventory = (catalogue.inventory ?? []).filter((entry) => entry.owner === '14G').map((entry) => entry.id)
  const goldenCases = (catalogue.goldenCases ?? []).filter((entry) => entry.owner === '14G').map((entry) => entry.id)
  if (JSON.stringify(inventory) !== JSON.stringify(expectedInventory)) errors.push('14G inventory ownership changed')
  if (JSON.stringify(goldenCases) !== JSON.stringify(expectedGolden)) errors.push('14G golden-case ownership changed')
  if (target.schemaVersion !== 1 || target.template !== true || target.approvalReady !== false
    || target.providerMutationEnabled !== false || target.approval !== null) {
    errors.push('committed target example must remain unapproved and fail closed')
  }
  errors.push(...validateTargetManifest(target).map((error) => `target example: ${error}`))
  if (target.environment?.dataClass !== 'synthetic-only'
    || target.environment?.customDomain !== false || target.environment?.automaticDeployment !== false) {
    errors.push('target environment boundary changed')
  }
  if (target.pricing?.fixedMonthlyUsd !== 65.15 || target.pricing?.ceilingUsd !== 70
    || target.pricing?.ownerUsageCapUsd !== 15
    || target.pricing?.ownerCapStatus !== 'eligible-timeboxed-manual-cleanup'
    || target.pricing?.maximumRuntimeHours !== 72
    || target.pricing?.plannedRuntimeHours !== 48
    || target.pricing?.projectedBaseUsageUsd !== 6.99) errors.push('target cost boundary changed')
  if (target.pricing?.containerRegistry?.provider !== 'DigitalOcean'
    || target.pricing?.containerRegistry?.plan !== 'Basic'
    || target.pricing?.containerRegistry?.region !== 'fra1'
    || target.pricing?.containerRegistry?.monthlyUsd !== 5
    || target.pricing?.containerRegistry?.chargeAssumption !== 'full-month') {
    errors.push('target registry cost boundary changed')
  }
  if (target.operatorAccess?.model !== 'solo-owner'
    || target.operatorAccess?.separateReviewRecord !== true
    || JSON.stringify(target.operatorAccess?.roleHats) !== JSON.stringify([
      'infrastructureCustodian',
      'securityCustodian',
      'applicationOperator',
      'incidentOperator',
      'releaseReviewer',
    ])) errors.push('target solo-operator model changed')
  if (target.temporaryRun?.maximumRuntimeHours !== 72
    || target.temporaryRun?.manualCleanupOnly !== true
    || target.temporaryRun?.automaticCleanup !== false
    || target.temporaryRun?.ownerDirectsCleanup !== true) errors.push('temporary run must require manual owner cleanup')
  const preserved = new Set(target.cleanup?.preserved ?? [])
  for (const name of ['workloop-clinic-dev', 'fra1-default', 'workloop-clinic_postgres_data', 'Phase 13 external archive']) {
    if (!preserved.has(name)) errors.push(`target cleanup does not preserve ${name}`)
  }
  if (liveRecord.schemaVersion !== 1 || liveRecord.template !== true || liveRecord.providerMutationOccurred !== false
    || liveRecord.initialApply?.maintenanceEnabled !== true || liveRecord.initialApply?.workersEnabled !== false
    || liveRecord.promotion?.approved !== false || liveRecord.promotion?.maintenanceEnabled !== true
    || liveRecord.promotion?.workersEnabled !== false) errors.push('committed live record must remain a blocked template')
  for (const stage of ['restart', 'redeploy']) {
    for (const item of ['databaseState', 'keycloakSigningKeyIds', 'privateObjects', 'scannerState', 'reconcilerState', 'expiryState', 'releaseIdentity']) {
      if (liveRecord.persistence?.[stage]?.[item] !== 'pending') errors.push(`live record template lacks ${stage} ${item}`)
    }
  }
  if (preflight.schemaVersion !== 1 || preflight.providerMutationOccurred !== false
    || preflight.paidResourceCreated !== false || preflight.publicExposureChanged !== false) {
    errors.push('preflight evidence crossed the read-only boundary')
  }
  if (preflight.repository?.branch !== 'migration/fastapi-keycloak'
    || preflight.repository?.commit !== 'cf6465c8b29d8fbd4ea2db06f9c0042c4e61ebb6'
    || preflight.repository?.requiredRun?.status !== 'success') errors.push('preflight repository evidence is incomplete')
  if (preflight.pricing?.fixedMonthlyUsd !== 65.15 || preflight.pricing?.ceilingUsd !== 70
    || preflight.pricing?.ownerUsageCapUsd !== 15
    || preflight.pricing?.ownerCapStatus !== 'eligible-timeboxed-manual-cleanup'
    || preflight.pricing?.maximumRuntimeHours !== 72
    || preflight.pricing?.projectedBaseUsageUsd !== 6.99) {
    errors.push('preflight price evidence is incomplete')
  }
  if (preflight.readiness?.applyAuthorized !== false || preflight.readiness?.promotionAuthorized !== false
    || !(preflight.readiness?.blockers ?? []).length) errors.push('preflight must retain unresolved blockers')
  if (recovery.providerNativeBackup?.status !== 'pending-14g-provider-live'
    || recovery.providerNativeBackup?.requiredForPromotion !== true) errors.push('provider-native recovery dependency changed')
  for (const marker of [
    'validateTargetManifest', 'assertApplyAuthorized', 'validateLiveRecord', 'assertPromotionAuthorized',
    'temporaryRunLimitState', 'validateRollbackRequest', 'manifestSha256', '30 * 60 * 1000',
    "operator?.model !== 'solo-owner'", 'recoveryMaterialCustodyReference', 'separateReviewRecord',
    'containerRegistryMonthlyUsd', 'plannedRuntimeHours',
  ]) requireText(errors, sources.helper, marker, `14G control helper ${marker}`)
  for (const marker of [
    'Repeat the authenticated preflight', 'named solo operator', 'maintenance', 'provider-native', 'administrator, manager, and employee',
    'Restart the existing deployment', 'Then redeploy the same digest-bound release', '72 hours', 'manual cleanup',
    'Basic private registry', '48-hour planned run',
  ]) requireText(errors, sources.runbook, marker, `14G runbook ${marker}`)
  for (const marker of [
    'var.provisioning_authorized && local.approval_complete', 'maintenance {',
    'enabled = !var.release_promoted', 'prevent_destroy = true',
    'local.projected_base_usage_usd <= local.owner_usage_cap_usd',
  ]) requireText(errors, sources.main, marker, `Terraform guard ${marker}`)
  for (const marker of [
    'owner_approval_reference', 'approved_on', 'retention_review_due_on',
    'release_promotion_approved', 'operator_access', 'reviewed_monthly_forecast_usd',
    'reviewed_run_forecast_usd', 'maximum_runtime_hours', 'owner_usage_cap_usd',
  ]) requireText(errors, sources.variables, marker, `Terraform approval input ${marker}`)
  for (const marker of ['phase-14g-target-manifest.example.json', '30-minute authenticated preflight', 'authorize-promotion']) {
    requireText(errors, sources.readme, marker, `14G infrastructure guide ${marker}`)
  }
  if (final) {
    const liveEvidence = parseJson(errors, sources.liveEvidence, 'live evidence')
    requireText(errors, sources.completion, '# Part 14G completion', 'Part 14G completion record')
    if (liveEvidence?.part !== '14G' || liveEvidence?.result !== 'passed'
      || liveEvidence?.promotion?.approved !== true || liveEvidence?.promotion?.maintenanceEnabled !== false
      || liveEvidence?.promotion?.workersEnabled !== true) errors.push('final live evidence is incomplete')
  }
  return { errors, inventory: inventory.length, goldenCases: goldenCases.length, final }
}

export function inspectPhase14GPromotion(root = repositoryDirectory, options = {}) {
  return validatePhase14GPromotion(readPhase14GPromotion(root), options)
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const report = inspectPhase14GPromotion(repositoryDirectory, { final: process.argv.includes('--final') })
  if (report.errors.length) {
    for (const error of report.errors) process.stderr.write(`Phase 14G promotion: ${error}\n`)
    process.exitCode = 1
  } else {
    const mode = report.final ? 'final' : 'preflight'
    process.stdout.write(`Phase 14G ${mode} verification passed: ${report.inventory} inventory items and ${report.goldenCases} golden cases.\n`)
  }
}
