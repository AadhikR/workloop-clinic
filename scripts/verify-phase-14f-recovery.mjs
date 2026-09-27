import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { validateRecoveryRecord } from './phase-14f-recovery.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const relativeFiles = {
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
  contract: 'infra/digitalocean/recovery-contract.json',
  record: 'infra/digitalocean/recovery-record.example.json',
  evidence: 'docs/migration/phase-14/evidence/PART_14F_LOCAL_RECOVERY.json',
  runbook: 'docs/migration/phase-14/PART_14F_RECOVERY_RUNBOOK.md',
  helper: 'scripts/phase-14f-recovery.mjs',
  databaseHelper: 'scripts/phase-14f-database-recovery.sh',
  databaseCompare: 'scripts/phase-14f-database-compare.sh',
  releaseHelper: 'scripts/phase-14d-release-manifest.mjs',
  objectRecovery: 'backend/app/storage/recovery.py',
  objectRehearsal: 'scripts/verify-phase-14f-object-recovery.py',
}

const expectedInventory = Array.from({ length: 7 }, (_, index) => `P14-REC-${String(index + 1).padStart(3, '0')}`)
const expectedGolden = Array.from({ length: 5 }, (_, index) => `14A-GC-${String(index + 26).padStart(3, '0')}`)
const requiredBackupClasses = ['DB-NATIVE', 'DB-PORTABLE', 'OBJECT-VERSIONS', 'RELEASE', 'RECOVERY-EVIDENCE']

function readText(root, relativePath) {
  const absolute = path.join(root, relativePath)
  return existsSync(absolute) ? readFileSync(absolute, 'utf8').replaceAll('\r\n', '\n') : ''
}

export function readPhase14FRecovery(root = repositoryDirectory) {
  return Object.fromEntries(Object.entries(relativeFiles).map(([key, value]) => [key, readText(root, value)]))
}

function parseJson(errors, source, label) {
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

export function validatePhase14FRecovery(sources) {
  const errors = []
  const catalogue = parseJson(errors, sources.catalogue, 'deployment catalogue')
  const contract = parseJson(errors, sources.contract, 'recovery contract')
  const record = parseJson(errors, sources.record, 'recovery record')
  const evidence = parseJson(errors, sources.evidence, 'local recovery evidence')
  const inventory = (catalogue.inventory ?? []).filter((entry) => entry.owner === '14F').map((entry) => entry.id)
  const goldenCases = (catalogue.goldenCases ?? []).filter((entry) => entry.owner === '14F').map((entry) => entry.id)
  if (JSON.stringify(inventory) !== JSON.stringify(expectedInventory)) errors.push('14F inventory ownership changed')
  if (JSON.stringify(goldenCases) !== JSON.stringify(expectedGolden)) errors.push('14F golden-case ownership changed')
  if (contract.providerMutationEnabled !== false) errors.push('provider mutation must remain disabled')
  if (contract.alembicHead !== 'e8a1c3f5b7d9') errors.push('recovery contract has an incompatible Alembic head')
  if (contract.providerNativeBackup?.status !== 'pending-14g-provider-live'
    || contract.providerNativeBackup?.requiredForPromotion !== true) errors.push('provider-live backup evidence must remain a promotion dependency')
  const backupClasses = new Set((contract.backupClasses ?? []).map((entry) => entry.class))
  for (const backupClass of requiredBackupClasses) {
    if (!backupClasses.has(backupClass)) errors.push(`recovery contract lacks ${backupClass}`)
  }
  if (contract.isolatedTargets?.restoreComposeProject !== 'workloop-phase14f-restore'
    || contract.isolatedTargets?.publicNetworkExposure !== false) errors.push('isolated restore target changed')
  if (contract.writeBlock?.applicationWritesEnabled !== false
    || contract.writeBlock?.workerProcessingEnabled !== false
    || contract.writeBlock?.unlockRequiresEveryComparison !== true) errors.push('write block is incomplete')
  if (contract.configurationContinuity?.recordValues !== false
    || contract.configurationContinuity?.requiredClasses?.length !== 6
    || contract.configurationContinuity?.evidence !== 'digest of canonical configuration names and values') {
    errors.push('protected configuration continuity is incomplete')
  }
  if (contract.rollback?.selectionMode !== 'explicit-reviewed-release-id'
    || contract.rollback?.requireSchemaCompatible !== true
    || contract.rollback?.automaticSchemaDowngrade !== false) errors.push('rollback contract is unsafe')
  if (contract.cleanup?.exactTargetsOnly !== true || contract.cleanup?.idempotent !== true
    || !(contract.cleanup?.forbiddenTargets ?? []).includes('workloop-clinic_postgres_data')) errors.push('cleanup contract is unsafe')
  errors.push(...validateRecoveryRecord(record, contract))
  if (evidence.alembicHead !== contract.alembicHead
    || evidence.restore?.initialDatabaseComparison !== 'passed'
    || evidence.restore?.reconciliation !== 'passed'
    || evidence.writeBlock?.comparisonsPassedBeforeApiStart !== true
    || evidence.journeys?.administrator !== 'passed'
    || evidence.journeys?.manager !== 'passed'
    || evidence.journeys?.employee !== 'passed'
    || evidence.rollback?.automaticSchemaDowngrade !== false
    || evidence.providerNativeEvidence?.status !== 'pending-14g-provider-live'
    || evidence.providerNativeEvidence?.sharedPromotionAllowed !== false
    || evidence.cleanup?.exactTargetCleanup !== 'passed'
    || evidence.cleanup?.disposableVolumesRemaining !== 0) {
    errors.push('retained local recovery evidence is incomplete')
  }
  for (const marker of ['createCipheriv', 'aes-256-gcm', "flag: 'wx'", 'selectRollbackManifest', 'explicit release ID']) {
    requireText(errors, sources.helper, marker, `recovery helper ${marker}`)
  }
  for (const marker of ['pg_dump', 'pg_restore', 'workloop-phase14f-source', 'workloop-phase14f-restore', '--clean', '--if-exists', '--exit-on-error']) {
    requireText(errors, sources.databaseHelper, marker, `database helper ${marker}`)
  }
  for (const marker of ['workloop-identity-count', 'workloop-row-count', 'keycloak-identity-count', 'keycloak-row-count', 'signing-key-id-digest', 'sha256sum']) {
    requireText(errors, sources.databaseCompare, marker, `database comparison ${marker}`)
  }
  for (const marker of ['target contains an', 'pending-14g-provider-live', 'Automatic downgrade is', 'administrator, manager, and employee']) {
    requireText(errors, sources.runbook, marker, `runbook ${marker}`)
  }
  for (const marker of ['frontendSha256', 'backendImage', 'keycloakImage', 'alembicHead']) {
    requireText(errors, sources.releaseHelper, marker, `release compatibility ${marker}`)
  }
  for (const marker of ['AESGCM', 'restore target is not empty', 'stored object integrity mismatch']) {
    requireText(errors, sources.objectRecovery, marker, `object recovery ${marker}`)
  }
  for (const marker of ['workloop-phase14f-restore-objects', 'exact restore bucket already exists', 'opaque_key_digest', 'reconciliation=passed']) {
    requireText(errors, sources.objectRehearsal, marker, `object rehearsal ${marker}`)
  }
  return { errors, inventory: inventory.length, goldenCases: goldenCases.length, backupClasses: backupClasses.size }
}

export function inspectPhase14FRecovery(root = repositoryDirectory) {
  return validatePhase14FRecovery(readPhase14FRecovery(root))
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const report = inspectPhase14FRecovery()
  if (report.errors.length) {
    for (const error of report.errors) process.stderr.write(`Phase 14F recovery: ${error}\n`)
    process.exitCode = 1
  } else {
    process.stdout.write(`Phase 14F recovery verification passed: ${report.inventory} inventory items, ${report.goldenCases} golden cases, and ${report.backupClasses} backup classes.\n`)
  }
}
