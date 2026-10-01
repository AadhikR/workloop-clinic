import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const digestPattern = /^sha256:[0-9a-f]{64}$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const commitPattern = /^[0-9a-f]{40}$/
const resourceIdPattern = /^[A-Za-z0-9][A-Za-z0-9._:/-]{2,199}$/
const operatorRoles = [
  'infrastructureCustodian',
  'securityCustodian',
  'applicationOperator',
  'incidentOperator',
  'releaseReviewer',
]
const persistenceClasses = [
  'databaseState',
  'keycloakSigningKeyIds',
  'privateObjects',
  'scannerState',
  'reconcilerState',
  'expiryState',
  'releaseIdentity',
]
const requiredPromotionChecks = [
  'alembic-head',
  'repeat-migration',
  'keycloak-mfa',
  'bootstrap-removed',
  'secret-routes',
  'database-least-privilege',
  'object-least-privilege',
  'component-health',
  'worker-controls',
  'safe-logs',
  'provider-native-backup',
  'isolated-recovery',
]
const maximumPreflightAgeMs = 30 * 60 * 1000
const maximumRuntimeHours = 72
const projectedBaseUsageUsd = 6.99
const plannedRuntimeHours = 48
const containerRegistryMonthlyUsd = 5
const billingMonthHours = 672
const fixedMonthlyUsd = 65.15
const targetComponentSignatures = [
  'api|service|apps-s-1vcpu-1gb-fixed|1',
  'database-migrate|pre-deploy-job|apps-s-1vcpu-1gb-fixed|1',
  'expiry|manual-job|apps-s-1vcpu-0.5gb|1',
  'file-scanner|worker|apps-s-1vcpu-0.5gb|1',
  'keycloak|service|apps-s-1vcpu-2gb|1',
  'storage-reconciler|worker|apps-s-1vcpu-0.5gb|1',
  'web|static-site|included|1',
]

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function approvalPayload(manifest) {
  const payload = structuredClone(manifest)
  delete payload.approval
  delete payload.approvalReady
  delete payload.providerMutationEnabled
  delete payload.manifestSha256
  return payload
}

export function manifestSha256(manifest) {
  return `sha256:${createHash('sha256').update(canonical(approvalPayload(manifest))).digest('hex')}`
}

function nonempty(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function exactSet(actual, expected) {
  const values = new Set(actual ?? [])
  return values.size === expected.length && expected.every((value) => values.has(value))
}

function preflightIsCurrent(checkedAt, now) {
  const checked = Date.parse(checkedAt ?? '')
  const current = new Date(now).getTime()
  return Number.isFinite(checked) && Number.isFinite(current) && checked <= current && current - checked <= maximumPreflightAgeMs
}

function containsForbiddenMaterial(value) {
  const forbiddenKeys = new Set([
    'password', 'token', 'privatekey', 'secretkey', 'secretvalue', 'accesskey', 'connectionstring',
    'databaseurl', 'signedurl', 'otpseed', 'recoverycode', 'terraformstate',
  ])
  if (Array.isArray(value)) return value.some(containsForbiddenMaterial)
  if (value !== null && typeof value === 'object') {
    return Object.entries(value).some(([key, item]) => forbiddenKeys.has(key.toLowerCase()) || containsForbiddenMaterial(item))
  }
  if (typeof value !== 'string') return false
  return /-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~-]+|(?:postgres(?:ql)?|mysql):\/\/[^\s]+@/i.test(value)
}

export function validateTargetManifest(manifest, { now = new Date() } = {}) {
  const errors = []
  if (containsForbiddenMaterial(manifest)) errors.push('target manifest contains protected material')
  if (manifest?.schemaVersion !== 1) errors.push('target manifest schema version must be 1')
  if (manifest?.environment?.name !== 'workloop-clinic-dev'
    || manifest?.environment?.purpose !== 'shared-development'
    || manifest?.environment?.dataClass !== 'synthetic-only'
    || manifest?.environment?.customDomain !== false
    || manifest?.environment?.automaticDeployment !== false) errors.push('environment boundary is invalid')
  if (manifest?.repository?.repository !== 'AadhikR/workloop-clinic'
    || manifest?.repository?.branch !== 'migration/fastapi-keycloak'
    || !commitPattern.test(manifest?.repository?.commit ?? '')
    || manifest?.repository?.requiredRun?.status !== 'success'
    || manifest?.repository?.requiredRun?.commit !== manifest?.repository?.commit) errors.push('repository proof is incomplete')
  if (manifest?.target?.project?.name !== 'workloop-clinic-dev'
    || manifest?.target?.project?.id !== '634213f9-2e43-4aea-8f4e-22ddc3ecdac9'
    || manifest?.target?.vpc?.name !== 'fra1-default'
    || manifest?.target?.vpc?.id !== 'b8b6d17b-eae4-47de-b2b5-9d10baabdd2d'
    || manifest?.target?.vpc?.region !== 'fra1'
    || manifest?.target?.vpc?.cidr !== '10.114.0.0/20') errors.push('retained project or VPC identity changed')
  if (manifest?.target?.app?.name !== 'workloop-clinic-dev'
    || manifest?.target?.app?.region !== 'fra'
    || manifest?.target?.database?.name !== 'workloop-clinic-dev-db'
    || manifest?.target?.database?.region !== 'fra1'
    || manifest?.target?.database?.engine !== 'postgresql-16'
    || manifest?.target?.database?.size !== 'db-s-1vcpu-1gb'
    || manifest?.target?.database?.storageGiB !== 10
    || manifest?.target?.bucket?.name !== 'workloop-clinic-dev-634213f9'
    || manifest?.target?.bucket?.region !== 'fra1'
    || manifest?.target?.bucket?.private !== true
    || manifest?.target?.bucket?.versioning !== true) errors.push('target resource manifest changed')
  const componentSignatures = (manifest?.target?.components ?? [])
    .map((item) => `${item.name}|${item.kind}|${item.size}|${item.instances}`)
  if (!exactSet(componentSignatures, targetComponentSignatures)) errors.push('target component set changed')
  if (manifest?.pricing?.currency !== 'USD' || manifest?.pricing?.fixedMonthlyUsd !== 65.15
    || manifest?.pricing?.ceilingUsd !== 70 || manifest?.pricing?.ownerUsageCapUsd !== 15
    || manifest?.pricing?.ownerCapStatus !== 'eligible-timeboxed-manual-cleanup'
    || manifest?.pricing?.maximumRuntimeHours !== maximumRuntimeHours
    || manifest?.pricing?.plannedRuntimeHours !== plannedRuntimeHours
    || manifest?.pricing?.billingMonthHours !== billingMonthHours
    || manifest?.pricing?.projectedBaseUsageUsd !== projectedBaseUsageUsd
    || manifest?.pricing?.duration !== 'maximum-72-hours-manual-cleanup') errors.push('price or duration boundary changed')
  if (manifest?.pricing?.containerRegistry?.provider !== 'DigitalOcean'
    || manifest?.pricing?.containerRegistry?.plan !== 'Basic'
    || manifest?.pricing?.containerRegistry?.region !== 'fra1'
    || manifest?.pricing?.containerRegistry?.monthlyUsd !== containerRegistryMonthlyUsd
    || manifest?.pricing?.containerRegistry?.chargeAssumption !== 'full-month'
    || manifest?.pricing?.containerRegistry?.includedStorageGiB !== 5
    || manifest?.pricing?.containerRegistry?.includedRepositories !== 5) {
    errors.push('private container registry plan or conservative charge assumption changed')
  }
  if (!(manifest?.pricing?.variableCharges ?? []).every((item) => nonempty(item.ownerRole))) {
    errors.push('every variable charge needs an owner role')
  }
  if (manifest?.temporaryRun?.maximumRuntimeHours !== maximumRuntimeHours
    || manifest?.temporaryRun?.manualCleanupOnly !== true
    || manifest?.temporaryRun?.automaticCleanup !== false
    || manifest?.temporaryRun?.ownerDirectsCleanup !== true) errors.push('temporary-run boundary is unsafe')
  if (!exactSet(manifest?.cleanup?.preserved, [
    'workloop-clinic-dev', 'fra1-default', 'workloop-clinic_postgres_data', 'Phase 13 external archive',
  ])) errors.push('preserved resource set changed')
  if (manifest?.cleanup?.automaticDestruction !== false || manifest?.cleanup?.freshApprovalRequired !== true) {
    errors.push('cleanup approval boundary changed')
  }
  if (manifest?.template !== true) {
    if (!preflightIsCurrent(manifest?.preflight?.checkedAt, now)) errors.push('authenticated preflight is missing, future dated, or older than 30 minutes')
    if (!resourceIdPattern.test(manifest?.preflight?.provider?.teamId ?? '')) errors.push('exact provider team is unresolved')
    for (const fact of ['account', 'project', 'vpc', 'resources', 'productAvailability', 'prices', 'budgetAlert']) {
      if (manifest?.preflight?.provider?.[fact] !== 'verified') errors.push(`provider preflight is unresolved: ${fact}`)
    }
    for (const list of ['projectResourceIds', 'vpcResourceIds', 'apps', 'databaseClusters', 'spacesBuckets']) {
      if (!Array.isArray(manifest?.preflight?.provider?.resourceInventory?.[list])) {
        errors.push(`provider resource inventory is unresolved: ${list}`)
      }
    }
    if (manifest?.preflight?.provider?.budgetAlertUsd !== 20
      || !exactSet(manifest?.preflight?.provider?.budgetAlertThresholdPercent, [75, 100])) {
      errors.push('budget alert evidence is unresolved')
    }
    if (manifest?.repository?.appInstallation?.status !== 'verified'
      || manifest?.repository?.appInstallation?.repositoryOnly !== true
      || !exactSet(manifest?.repository?.appInstallation?.repositories, ['AadhikR/workloop-clinic'])) {
      errors.push('DigitalOcean GitHub App scope is not repository only')
    }
    const startsAt = Date.parse(manifest?.temporaryRun?.startsAt ?? '')
    const cleanupDeadlineAt = Date.parse(manifest?.temporaryRun?.cleanupDeadlineAt ?? '')
    if (!Number.isFinite(startsAt) || !Number.isFinite(cleanupDeadlineAt)
      || cleanupDeadlineAt <= startsAt
      || cleanupDeadlineAt - startsAt > plannedRuntimeHours * 60 * 60 * 1000) {
      errors.push('temporary-run timestamps are missing or exceed the approved 48-hour plan')
    }
    const minimumRuntimeProjection = Math.ceil(
      ((fixedMonthlyUsd * plannedRuntimeHours) / billingMonthHours) * 100,
    ) / 100
    const minimumReviewedForecast = Number((
      (manifest?.pricing?.currentAccruedUsageUsd ?? 0)
      + minimumRuntimeProjection
      + containerRegistryMonthlyUsd
      + (manifest?.pricing?.taxAndVariableReserveUsd ?? 0)
    ).toFixed(2))
    if (manifest?.pricing?.runtimeResourceProjectionUsd !== minimumRuntimeProjection
      || typeof manifest?.pricing?.currentAccruedUsageUsd !== 'number'
      || manifest.pricing.currentAccruedUsageUsd < 0
      || typeof manifest?.pricing?.taxAndVariableReserveUsd !== 'number'
      || manifest.pricing.taxAndVariableReserveUsd <= 0
      || typeof manifest?.pricing?.reviewedRunForecastUsd !== 'number'
      || manifest.pricing.reviewedRunForecastUsd < minimumReviewedForecast
      || manifest.pricing.reviewedRunForecastUsd > manifest.pricing.ownerUsageCapUsd) {
      errors.push('temporary-run forecast does not cover accrued usage, 48-hour resources, the full registry charge, and a positive reserve within the USD 15 cap')
    }
    const operator = manifest?.operatorAccess
    if (operator?.model !== 'solo-owner'
      || !nonempty(operator?.operatorName)
      || !nonempty(operator?.routineAccountReference)
      || operator?.routineMfa !== true
      || !nonempty(operator?.emergencyAccountReference)
      || operator?.emergencyMfa !== true
      || operator?.routineAccountReference === operator?.emergencyAccountReference
      || !nonempty(operator?.recoveryMaterialCustodyReference)
      || !datePattern.test(operator?.recoveryTestedOn ?? '')
      || operator?.separateReviewRecord !== true
      || !exactSet(operator?.roleHats, operatorRoles)) {
      errors.push('solo operator access or recovery evidence is incomplete')
    }
    for (const field of ['stateCustodian', 'statePathReference', 'credentialCustodian', 'backupCustodian', 'variableChargeOwner']) {
      if (!nonempty(manifest?.custody?.[field])) errors.push(`custody is unresolved: ${field}`)
    }
    if (!nonempty(manifest?.release?.releaseId)
      || manifest?.release?.gitCommit !== manifest?.repository?.commit
      || manifest?.release?.alembicHead !== 'e8a1c3f5b7d9'
      || !digestPattern.test(manifest?.release?.manifestSha256 ?? '')) errors.push('immutable release manifest is unresolved')
    for (const digest of ['backendImageDigest', 'keycloakImageDigest', 'frontendDigest', 'terraformDigest', 'appSpecDigest']) {
      if (!digestPattern.test(manifest?.release?.[digest] ?? '')) errors.push(`release digest is unresolved: ${digest}`)
    }
  }
  return errors
}

export function assertApplyAuthorized(manifest, { now = new Date() } = {}) {
  const errors = validateTargetManifest(manifest, { now })
  const digest = manifestSha256(manifest)
  if (manifest?.template !== false || manifest?.approvalReady !== true || manifest?.providerMutationEnabled !== true) {
    errors.push('target manifest is not enabled for provider mutation')
  }
  if (!digestPattern.test(manifest?.manifestSha256 ?? '') || manifest.manifestSha256 !== digest) {
    errors.push('target manifest digest does not match its approval payload')
  }
  if (!nonempty(manifest?.approval?.ownerApprovalReference)
    || !datePattern.test(manifest?.approval?.approvedOn ?? '')
    || manifest?.approval?.manifestSha256 !== digest
    || manifest?.approval?.fixedMonthlyUsd !== 65.15
    || manifest?.approval?.ceilingUsd !== 70
    || manifest?.approval?.ownerUsageCapUsd !== 15
    || manifest?.approval?.maximumRuntimeHours !== maximumRuntimeHours
    || manifest?.approval?.plannedRuntimeHours !== plannedRuntimeHours
    || manifest?.approval?.containerRegistryMonthlyUsd !== containerRegistryMonthlyUsd
    || manifest?.approval?.projectedBaseUsageUsd !== projectedBaseUsageUsd
    || manifest?.approval?.reviewedRunForecastUsd !== manifest?.pricing?.reviewedRunForecastUsd) {
    errors.push('dated owner approval does not bind the exact manifest, runtime, and cost')
  }
  if (errors.length) throw new Error(errors.join('\n'))
  return {
    manifestSha256: digest,
    fixedMonthlyUsd: 65.15,
    projectedBaseUsageUsd,
    plannedRuntimeHours,
    containerRegistryMonthlyUsd,
    maximumRuntimeHours,
    ownerUsageCapUsd: 15,
    maintenanceEnabled: true,
    workersEnabled: false,
  }
}

export function validateLiveRecord(record, target) {
  const errors = []
  const digest = manifestSha256(target)
  if (record?.schemaVersion !== 1 || record?.template !== false || record?.providerMutationOccurred !== true) {
    errors.push('live record does not describe an approved provider apply')
  }
  if (record?.targetManifestSha256 !== digest || record?.release?.manifestSha256 !== digest) {
    errors.push('live evidence is not bound to the target manifest')
  }
  for (const id of ['projectId', 'vpcId', 'appId', 'databaseClusterId', 'bucketName']) {
    if (!resourceIdPattern.test(record?.resources?.[id] ?? '')) errors.push(`live resource identity is missing: ${id}`)
  }
  if (!/^https:\/\/[a-z0-9-]+\.ondigitalocean\.app\/?$/.test(record?.resources?.appDefaultUrl ?? '')) {
    errors.push('provider default address is missing or invalid')
  }
  if (record?.initialApply?.maintenanceEnabled !== true || record?.initialApply?.workersEnabled !== false
    || record?.initialApply?.alembicHead !== 'e8a1c3f5b7d9') errors.push('initial apply did not stay in maintenance')
  const checks = new Map((record?.promotionChecks ?? []).map((item) => [item.id, item.status]))
  for (const check of requiredPromotionChecks) {
    if (checks.get(check) !== 'passed') errors.push(`promotion check did not pass: ${check}`)
  }
  for (const stage of ['restart', 'redeploy']) {
    for (const item of persistenceClasses) {
      if (record?.persistence?.[stage]?.[item] !== 'passed') errors.push(`${stage} persistence did not pass: ${item}`)
    }
  }
  for (const journey of ['administrator', 'manager', 'employee']) {
    if (record?.journeys?.[journey] !== 'passed') errors.push(`synthetic journey did not pass: ${journey}`)
  }
  if (!nonempty(record?.providerNativeBackup?.schedule)
    || !Number.isInteger(record?.providerNativeBackup?.retentionDays)
    || record.providerNativeBackup.retentionDays < 1
    || record?.providerNativeBackup?.workloopStatus !== 'passed'
    || record?.providerNativeBackup?.keycloakStatus !== 'passed'
    || record?.providerNativeBackup?.isolatedRestoreStatus !== 'passed'
    || !resourceIdPattern.test(record?.providerNativeBackup?.isolatedRestoreTargetId ?? '')) {
    errors.push('provider-native backup and isolated restore evidence is incomplete')
  }
  if (!digestPattern.test(record?.release?.backendImageDigest ?? '')
    || !digestPattern.test(record?.release?.keycloakImageDigest ?? '')
    || !digestPattern.test(record?.release?.frontendDigest ?? '')
    || record?.release?.alembicHead !== 'e8a1c3f5b7d9') errors.push('release identity is incomplete')
  if (record?.promotion?.approved !== true || !nonempty(record?.promotion?.ownerApprovalReference)
    || !datePattern.test(record?.promotion?.approvedOn ?? '')
    || !nonempty(record?.promotion?.executor) || !nonempty(record?.promotion?.reviewer)
    || !nonempty(record?.promotion?.executionRecordReference)
    || !nonempty(record?.promotion?.reviewRecordReference)
    || record?.promotion?.executionRecordReference === record?.promotion?.reviewRecordReference
    || record?.promotion?.releaseManifestSha256 !== record?.release?.manifestSha256
    || record?.promotion?.maintenanceEnabled !== false || record?.promotion?.workersEnabled !== true) {
    errors.push('promotion approval or final state is incomplete')
  }
  if (!nonempty(record?.temporaryRun?.cleanupDeadlineAt)
    || record?.temporaryRun?.automaticCleanup !== false
    || record?.temporaryRun?.manualCleanupRequired !== true) {
    errors.push('temporary-run cleanup record is incomplete')
  }
  if (record?.rollback?.automaticSchemaDowngrade !== false
    || !nonempty(record?.rollback?.compatibleReleaseId)
    || record?.rollback?.maintenanceFirst !== true || record?.rollback?.workersStoppedFirst !== true) {
    errors.push('rollback point is incomplete')
  }
  return errors
}

export function assertPromotionAuthorized(record, target) {
  const errors = validateLiveRecord(record, target)
  if (errors.length) throw new Error(errors.join('\n'))
  return { releaseId: record.release.releaseId, maintenanceEnabled: false, workersEnabled: true }
}

export function temporaryRunLimitState() {
  return { maintenanceEnabled: true, workersEnabled: false, automaticCleanup: false, ownerActionRequired: true }
}

export function validateRollbackRequest(request, liveRecord) {
  const errors = []
  if (!nonempty(request?.requestedReleaseId) || request?.requestedReleaseId !== liveRecord?.rollback?.compatibleReleaseId) {
    errors.push('rollback requires the exact retained compatible release')
  }
  if (request?.maintenanceEnabled !== true || request?.workersEnabled !== false) {
    errors.push('rollback must enable maintenance and stop workers first')
  }
  if (request?.alembicHead !== 'e8a1c3f5b7d9' || request?.automaticSchemaDowngrade !== false) {
    errors.push('rollback cannot downgrade the schema')
  }
  if (request?.destroyResources !== false) errors.push('runtime rollback cannot destroy resources')
  return errors
}

function option(name) {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function loadJson(name) {
  if (!name) throw new Error('a JSON path is required')
  return JSON.parse(readFileSync(path.resolve(name), 'utf8'))
}

function main() {
  const mode = process.argv[2]
  const target = loadJson(option('--target'))
  if (mode === 'validate-target') {
    const errors = validateTargetManifest(target)
    if (errors.length) throw new Error(errors.join('\n'))
    process.stdout.write(`Target manifest is structurally valid as ${manifestSha256(target)}.\n`)
    return
  }
  if (mode === 'authorize-apply') {
    const result = assertApplyAuthorized(target)
    process.stdout.write(`Apply authorization passed for ${result.manifestSha256}; maintenance remains enabled.\n`)
    return
  }
  const record = loadJson(option('--record'))
  if (mode === 'validate-live') {
    const errors = validateLiveRecord(record, target)
    if (errors.length) throw new Error(errors.join('\n'))
    process.stdout.write('Live provisioning and persistence evidence passed.\n')
    return
  }
  if (mode === 'authorize-promotion') {
    const result = assertPromotionAuthorized(record, target)
    process.stdout.write(`Promotion authorization passed for ${result.releaseId}.\n`)
    return
  }
  throw new Error('use validate-target, authorize-apply, validate-live, or authorize-promotion')
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`Phase 14G control: ${error.message}\n`)
    process.exitCode = 1
  }
}
