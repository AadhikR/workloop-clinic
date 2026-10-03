import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(root, 'docs', 'migration', 'phase-15')

export const cataloguePath = path.join(phaseDirectory, 'integration-catalogue.json')
export const preflightPath = path.join(phaseDirectory, 'evidence', 'PART_15G_PREFLIGHT.json')
export const releasePath = path.join(phaseDirectory, 'evidence', 'PART_15G_RELEASE_BINDING.json')
export const livePath = path.join(phaseDirectory, 'evidence', 'PART_15G_LIVE_ACCEPTANCE.json')

const ownedInventory = ['P15-VAL-004', 'P15-VAL-005', 'P15-VAL-006', 'P15-VAL-007']
const ownedGaps = ['P15-GAP-006', 'P15-GAP-007']
const ownedGoldenCases = [
  '15A-GC-031',
  '15A-GC-032',
  '15A-GC-033',
  '15A-GC-034',
  '15A-GC-035',
  '15A-GC-036',
]
const components = [
  'database-migrate',
  'api',
  'keycloak',
  'web',
  'expiry',
  'file-scanner',
  'storage-reconciler',
]
const fileFlows = [
  'P15-FLOW-001',
  'P15-FLOW-002',
  'P15-FLOW-003',
  'P15-FLOW-004',
  'P15-FLOW-005',
  'P15-FLOW-006',
]
const denialScopes = [
  'cross-role',
  'cross-company',
  'cross-branch',
  'cross-manager',
  'cross-employee',
  'record',
  'file',
]
const performanceMetrics = [
  'availabilityP95Ms',
  'initialCompressedTransferBytes',
  'laterRouteTransferBytes',
  'routeChangeP95Ms',
  'interactionP95Ms',
  'representativeApiP95Ms',
]
const preservedResources = [
  'workloop-clinic-dev',
  'fra1-default',
  'Phase 13 external archive',
  'workloop-clinic_postgres_data',
]
const digestPattern = /^sha256:[0-9a-f]{64}$/
const defaultAddress = 'https://workloop-clinic-dev-e9uk5.ondigitalocean.app'
const reviewedCommit = '94edc0ca2d9e1a2073d4027d7bc50b985b23159b'

function exactSet(errors, actual, expected, label) {
  const unique = [...new Set(actual)]
  const missing = expected.filter((value) => !unique.includes(value))
  const unexpected = unique.filter((value) => !expected.includes(value))
  if (unique.length !== actual.length) errors.push(`${label} contains duplicates`)
  if (missing.length) errors.push(`${label} is missing ${missing.join(', ')}`)
  if (unexpected.length) errors.push(`${label} has unexpected values ${unexpected.join(', ')}`)
}

function validateDigest(errors, value, label) {
  if (!digestPattern.test(value ?? '')) errors.push(`${label} is not a SHA-256 digest`)
}

export function validatePhase15GPromotion(catalogue, preflight, release, live, { final = true } = {}) {
  const errors = []
  exactSet(errors, catalogue.inventory.filter((entry) => entry.owner === '15G').map((entry) => entry.id), ownedInventory, '15G inventory')
  exactSet(errors, catalogue.knownGaps.filter((entry) => entry.owner === '15G').map((entry) => entry.id), ownedGaps, '15G gaps')
  exactSet(errors, catalogue.goldenCases.filter((entry) => entry.owner === '15G').map((entry) => entry.id), ownedGoldenCases, '15G golden cases')

  if (preflight.schemaVersion !== 1 || preflight.phase !== '15' || preflight.part !== '15G' || preflight.status !== 'passed') {
    errors.push('provider preflight did not pass')
  }
  if (preflight.repository?.branch !== 'migration/fastapi-keycloak'
    || preflight.repository?.commit !== reviewedCommit
    || preflight.repository?.upstreamAhead !== 0
    || preflight.repository?.upstreamBehind !== 0) errors.push('repository preflight is not clean and synchronized at the reviewed commit')
  if (preflight.provider?.project?.id !== '634213f9-2e43-4aea-8f4e-22ddc3ecdac9'
    || preflight.provider?.project?.name !== 'workloop-clinic-dev') errors.push('retained project identity changed')
  if (preflight.provider?.network?.id !== 'b8b6d17b-eae4-47de-b2b5-9d10baabdd2d'
    || preflight.provider?.network?.name !== 'fra1-default'
    || preflight.provider?.network?.resourceCount !== 2) errors.push('retained network identity or membership changed')
  if (preflight.provider?.application?.id !== '02b3a86a-707f-4608-9e73-4c994bef7138'
    || preflight.provider?.application?.defaultAddress !== defaultAddress
    || preflight.provider?.application?.automaticDeployment !== false
    || preflight.provider?.application?.customDomains?.length !== 0) errors.push('application exposure boundary changed')
  exactSet(errors, preflight.provider?.application?.components?.map((entry) => entry.name) ?? [], components, 'provider components')
  if (preflight.provider?.database?.backup?.pointInTimeRestoreAvailable !== true
    || preflight.provider?.database?.backup?.retentionDays !== 7) errors.push('provider backup evidence is incomplete')
  const billing = preflight.provider?.billing
  if (!Number.isFinite(billing?.monthToDateUsageUsd)
    || billing?.ownerCapUsd !== 15
    || billing?.withinCap !== true
    || billing?.reviewedRunForecastUsd > billing?.ownerCapUsd
    || billing?.availableUnderCapUsd !== Number((billing.ownerCapUsd - billing.monthToDateUsageUsd).toFixed(2))) {
    errors.push('provider usage or cap evidence is invalid')
  }
  if (preflight.decision?.promotionAllowed !== true) errors.push('preflight did not allow promotion')

  if (release.schemaVersion !== 1 || release.phase !== '15' || release.part !== '15G' || release.status !== 'passed') {
    errors.push('release binding did not pass')
  }
  if (release.reviewedCommit !== reviewedCommit || release.frontend?.providerBuild?.sourceCommit !== reviewedCommit) {
    errors.push('release binding does not use the reviewed commit')
  }
  for (const [label, value] of [
    ['frontend local build', release.frontend?.localBuild?.sha256],
    ['frontend local root', release.frontend?.localBuild?.rootSha256],
    ['frontend provider build', release.frontend?.providerBuild?.expectedSha256],
    ['frontend provider root', release.frontend?.providerBuild?.expectedRootSha256],
    ['frontend public settings', release.frontend?.publicSettings?.sha256],
    ['backend image', release.backendImage?.digest],
    ['Keycloak image', release.keycloakImage?.digest],
    ['Terraform', release.terraform?.sha256],
    ['app spec', release.appSpec?.sha256],
  ]) validateDigest(errors, value, label)
  if (release.frontend?.localBuild?.sha256 !== release.frontend?.providerBuild?.expectedSha256
    || release.frontend?.localBuild?.rootSha256 !== release.frontend?.providerBuild?.expectedRootSha256) {
    errors.push('provider frontend expectation does not match the reviewed local build')
  }
  if (release.frontend?.providerBuild?.automaticDeployment !== false
    || release.promotion?.manualOnly !== true
    || release.promotion?.automaticDeployment !== false
    || release.promotion?.defaultAddressOnly !== true
    || release.promotion?.allowed !== true) errors.push('release promotion boundary is unsafe')
  if (release.backendImage?.sourceChangedSincePhase14 !== false
    || release.keycloakImage?.sourceChangedSincePhase14 !== false
    || release.terraform?.sourceChangedSincePhase14 !== false
    || release.appSpec?.sourceChangedSincePhase14 !== false) errors.push('unchanged Phase 14 artifact reuse is not explicit')
  if (release.alembicHead !== 'e8a1c3f5b7d9') errors.push('Alembic head changed')

  if (!final) return { errors, final, owned: ownedInventory.length + ownedGaps.length + ownedGoldenCases.length }

  if (live.schemaVersion !== 1 || live.phase !== '15' || live.part !== '15G' || live.status !== 'passed') {
    errors.push('live acceptance did not pass')
  }
  if (live.releaseId !== release.releaseId || live.reviewedCommit !== reviewedCommit) errors.push('live acceptance is not bound to the reviewed release')
  if (live.provider?.defaultAddress !== defaultAddress
    || live.provider?.automaticDeployment !== false
    || live.provider?.customDomains?.length !== 0
    || !live.provider?.promotedDeploymentId) errors.push('live provider identity or exposure boundary is incomplete')
  for (const role of ['administrator', 'manager', 'employee']) {
    if (live.journeys?.[role] !== 'passed') errors.push(`${role} live journey did not pass`)
  }
  if (live.journeys?.syntheticOnly !== true || live.journeys?.routeGroups !== 25
    || live.journeys?.logout !== 'passed' || live.journeys?.expiry !== 'passed') errors.push('live journey coverage is incomplete')
  exactSet(errors, live.fileFlows?.map((entry) => entry.id) ?? [], fileFlows, 'live file flows')
  for (const flow of live.fileFlows ?? []) if (flow.status !== 'passed') errors.push(`${flow.id} live file flow did not pass`)
  exactSet(errors, live.denials?.scopes ?? [], denialScopes, 'live denial scopes')
  if (live.denials?.backendAuthoritative !== true || live.denials?.status !== 'passed') errors.push('live backend denial proof is incomplete')
  if (live.safeLogs?.status !== 'passed' || live.safeLogs?.protectedMatches !== 0
    || live.safeLogs?.unexpectedSevereMarkers !== 0) errors.push('live safe-log proof is incomplete')
  exactSet(errors, Object.keys(live.performance?.budgets ?? {}), performanceMetrics, 'live performance budgets')
  exactSet(errors, Object.keys(live.performance?.measurements ?? {}), performanceMetrics, 'live performance measurements')
  for (const metric of performanceMetrics) {
    const budget = live.performance?.budgets?.[metric]
    const measurement = live.performance?.measurements?.[metric]
    if (!Number.isFinite(budget) || budget <= 0 || !Number.isFinite(measurement?.value)
      || !Number.isInteger(measurement?.sampleCount) || measurement.sampleCount < 1
      || !measurement?.percentile || !measurement?.cacheState) errors.push(`${metric} measurement is incomplete`)
    else if (measurement.value > budget) errors.push(`${metric} exceeds its budget`)
  }
  for (const field of ['restart', 'rollback', 'recovery', 'databaseState', 'keycloakSigningKeyIds', 'privateObjects', 'routeBehavior', 'authorizationBehavior']) {
    if (live.resilience?.[field] !== 'passed') errors.push(`${field} resilience proof did not pass`)
  }
  if (live.resilience?.automaticSchemaDowngrade !== false) errors.push('rollback allowed an automatic schema downgrade')
  if (live.cleanup?.status !== 'passed' || live.cleanup?.exactIdentifiers !== true || live.cleanup?.remaining !== 0) {
    errors.push('exact live cleanup proof is incomplete')
  }
  if (live.resources?.newPaidResources !== 0 || live.resources?.withinCap !== true
    || live.resources?.ownerCapUsd !== 15 || live.resources?.monthToDateUsageUsd > 15) errors.push('live resource or cost boundary failed')
  exactSet(errors, live.resources?.preserved ?? [], preservedResources, 'preserved resources')

  for (const entry of [
    ...catalogue.inventory.filter((item) => item.owner === '15G'),
    ...catalogue.knownGaps.filter((item) => item.owner === '15G'),
    ...catalogue.goldenCases.filter((item) => item.owner === '15G'),
  ]) {
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) errors.push(`${entry.id} has no 15G evidence`)
    for (const target of entry.evidence ?? []) if (!existsSync(path.join(root, target))) errors.push(`${entry.id} has missing evidence ${target}`)
  }

  return { errors, final, owned: ownedInventory.length + ownedGaps.length + ownedGoldenCases.length }
}

export function inspectPhase15GPromotion({ final = true } = {}) {
  const read = (file) => JSON.parse(readFileSync(file, 'utf8'))
  return validatePhase15GPromotion(read(cataloguePath), read(preflightPath), read(releasePath), read(livePath), { final })
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const final = !process.argv.includes('--preflight')
  const report = inspectPhase15GPromotion({ final })
  if (report.errors.length) {
    console.error(report.errors.join('\n'))
    process.exitCode = 1
  } else {
    console.log(`Phase 15G ${final ? 'final' : 'preflight'} verification passed for ${report.owned} owned records.`)
  }
}
