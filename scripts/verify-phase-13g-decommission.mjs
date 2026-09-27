import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const targetManifestPath = path.join(
  repositoryDirectory,
  'docs',
  'migration',
  'phase-13',
  'PART_13G_TARGET_MANIFEST.json',
)
const approvalManifestPath = path.join(
  repositoryDirectory,
  'docs',
  'migration',
  'phase-13',
  'PART_13G_APPROVAL_MANIFEST.json',
)

const requiredDiscoverySections = [
  'externalProject',
  'auth',
  'database',
  'realtime',
  'storage',
  'apiKeys',
  'github',
  'digitalOcean',
]

const targetCollections = {
  'api-key': 'apiKeys',
  'github-secret': 'githubSecrets',
  'digitalocean-secret': 'digitalOceanSecrets',
  'storage-set': 'storageSets',
  project: 'projects',
}

function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, canonicalValue(value[key])]),
    )
  }
  return value
}

function canonicalText(value) {
  return JSON.stringify(canonicalValue(value))
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

export function digestManifest(manifest) {
  return sha256(canonicalText(manifest))
}

export function digestEvidence(manifest) {
  return sha256(canonicalText({
    auth: manifest.discovery.auth,
    database: manifest.discovery.database,
    storage: manifest.discovery.storage,
  }))
}

function validSha256(value) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value)
}

function validUtc(value) {
  return typeof value === 'string'
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)
    && !Number.isNaN(Date.parse(value))
}

function hasBroadSelector(value) {
  if (Array.isArray(value)) return value.some(hasBroadSelector)
  if (value && typeof value === 'object') return Object.values(value).some(hasBroadSelector)
  if (typeof value !== 'string') return false
  return /[*?]/.test(value) || /^(?:all|everything old|phase 13)$/i.test(value.trim())
}

function exactMatch(left, right) {
  return canonicalText(left) === canonicalText(right)
}

function addDays(utc, days) {
  const value = new Date(utc)
  value.setUTCDate(value.getUTCDate() + days)
  return value
}

function validateResolvedEvidence(manifest) {
  const reasons = []
  for (const section of requiredDiscoverySections) {
    if (manifest.discovery?.[section]?.status !== 'resolved') {
      reasons.push(`discovery section ${section} is not resolved`)
    }
  }

  const project = manifest.discovery?.externalProject
  if (!project?.organizationId || !project?.projectId) {
    reasons.push('external project identifiers are incomplete')
  }

  const auth = manifest.discovery?.auth
  if (!Number.isInteger(auth?.userCount) || !Number.isInteger(auth?.metadataRecordCount)) {
    reasons.push('Auth metadata counts are incomplete')
  }

  const database = manifest.discovery?.database
  if (!Array.isArray(database?.schemaObjects)
    || typeof database?.tableRowCounts !== 'object'
    || !Array.isArray(database?.rpcNames)
    || !validSha256(database?.exportSha256)) {
    reasons.push('database schema, count, RPC, or digest evidence is incomplete')
  }

  const storage = manifest.discovery?.storage
  if (!Array.isArray(storage?.buckets)
    || storage.buckets.some((bucket) => (
      !bucket.name
      || !Number.isInteger(bucket.objectCount)
      || !Number.isInteger(bucket.byteCount)
      || !validSha256(bucket.manifestSha256)
    ))) {
    reasons.push('storage count, size, or digest evidence is incomplete')
  }

  const evidenceSha256 = digestEvidence(manifest)
  if (manifest.export?.status !== 'verified'
    || !manifest.export.externalLocation
    || !manifest.export.custodian
    || !manifest.export.encryptionOwner
    || manifest.export.evidenceSha256 !== evidenceSha256
    || !Array.isArray(manifest.export.artifactDigests)
    || manifest.export.artifactDigests.length === 0
    || manifest.export.artifactDigests.some((digest) => !validSha256(digest))) {
    reasons.push('encrypted export evidence is incomplete or does not match discovery')
  }

  if (manifest.restore?.status !== 'passed'
    || !validUtc(manifest.restore.completedAt)
    || manifest.restore.sourceEvidenceSha256 !== evidenceSha256
    || manifest.restore.restoredEvidenceSha256 !== evidenceSha256
    || manifest.restore.countsAndDigestsMatch !== true) {
    reasons.push('isolated restore evidence is incomplete or does not match discovery')
  }

  const retention = manifest.retention
  if (!['active', 'indefinite'].includes(retention?.status)
    || retention.minimumCalendarDays !== 30
    || retention.startsAt !== manifest.restore?.completedAt) {
    reasons.push('retention evidence is incomplete or did not start at restore completion')
  } else if (retention.status === 'active') {
    if (!validUtc(retention.deadline)) {
      reasons.push('retention deadline is missing')
    } else if (new Date(retention.deadline) < addDays(retention.startsAt, 30)) {
      reasons.push('retention deadline is shorter than 30 calendar days')
    }
  } else if (!validUtc(retention.minimumDeadline)
    || new Date(retention.minimumDeadline) < addDays(retention.startsAt, 30)
    || retention.deadline !== null
    || !validUtc(retention.decisionAt)
    || retention.decidedBy !== 'project-owner'
    || retention.disposition !== 'retain-external-project') {
    reasons.push('indefinite retention decision is incomplete')
  }

  return reasons
}

export function evaluateAction({ targetManifest, approvalManifest, action, now }) {
  const reasons = validateResolvedEvidence(targetManifest)
  if (targetManifest.retention?.status === 'indefinite') {
    reasons.push('project owner retained target; destructive actions are prohibited')
  }
  const collectionName = targetCollections[action?.kind]
  if (!collectionName) reasons.push('action kind is not allowed')
  if (hasBroadSelector(action?.target)) reasons.push('wildcard or broad target is not allowed')

  const collection = collectionName ? targetManifest.destructiveTargets?.[collectionName] : undefined
  const targetMatches = Array.isArray(collection)
    ? collection.filter((target) => exactMatch(target, action?.target))
    : []
  if (targetMatches.length !== 1) reasons.push('action target is not one exact settled target')

  const preflightDigest = action?.target ? sha256(canonicalText(action.target)) : null
  if (action?.preflightTargetSha256 !== preflightDigest) {
    reasons.push('immediate preflight target digest does not match')
  }

  const settledDigest = digestManifest(targetManifest)
  if (approvalManifest?.status !== 'approved') reasons.push('approval manifest is not approved')
  if (approvalManifest?.targetManifestSha256 !== settledDigest) {
    reasons.push('approval is not bound to the settled target manifest')
  }

  const approvals = Array.isArray(approvalManifest?.approvals)
    ? approvalManifest.approvals.filter((approval) => (
      approval.targetKind === action?.kind
      && exactMatch(approval.target, action?.target)
    ))
    : []
  if (approvals.length !== 1) {
    reasons.push('one fresh exact approval is required for the action target')
  } else {
    const [approval] = approvals
    if (approval.approvedBy !== 'project-owner') reasons.push('approval owner identity is uncertain')
    if (!validUtc(approval.approvedAt)
      || new Date(approval.approvedAt) < new Date(targetManifest.settledAt)) {
      reasons.push('approval predates the settled target manifest')
    }
    if (!validUtc(approval.approvedAt)
      || !validUtc(targetManifest.retention?.deadline)
      || new Date(approval.approvedAt) < new Date(targetManifest.retention.deadline)) {
      reasons.push('approval predates the elapsed retention deadline')
    }
    if (approval.targetManifestSha256 !== settledDigest) {
      reasons.push('target approval has a stale manifest binding')
    }
    if (!validUtc(action?.preflightObservedAt)
      || new Date(action.preflightObservedAt) < new Date(approval.approvedAt)
      || !validUtc(now)
      || new Date(now) < new Date(action.preflightObservedAt)
      || new Date(now) - new Date(action.preflightObservedAt) > 15 * 60 * 1000) {
      reasons.push('immediate preflight observation is missing or stale')
    }
  }

  if (!validUtc(now) || !validUtc(targetManifest.retention?.deadline)
    || new Date(now) < new Date(targetManifest.retention?.deadline)) {
    reasons.push('retention deadline has not elapsed')
  }

  return { allowed: reasons.length === 0, reasons: [...new Set(reasons)] }
}

export function validateRetainedBoundary(targetManifest, approvalManifest) {
  const errors = []
  if (targetManifest.version !== 1 || targetManifest.mode !== 'read-only') {
    errors.push('target manifest must be a version 1 read-only record')
  }
  if (targetManifest.discovery?.github?.status !== 'resolved') {
    errors.push('GitHub discovery must be resolved')
  }
  for (const section of requiredDiscoverySections.filter((name) => name !== 'github')) {
    if (!['blocked', 'resolved'].includes(targetManifest.discovery?.[section]?.status)) {
      errors.push(`discovery section ${section} has no fail-closed status`)
    }
  }
  if (!targetManifest.blockers?.length) errors.push('at least one blocker must be recorded')
  const exportStatus = targetManifest.export?.status
  if (!['not-started', 'verified-artifacts', 'verified'].includes(exportStatus)) {
    errors.push('export must be absent, retained after a failed restore, or fully verified')
  }
  if (exportStatus === 'verified-artifacts'
    && (!targetManifest.export.externalLocation
      || !targetManifest.export.custodian
      || !targetManifest.export.encryptionOwner
      || targetManifest.export.evidenceSha256 !== null
      || targetManifest.export.decryptionRoundTripVerified !== true
      || !Array.isArray(targetManifest.export.artifactDigests)
      || targetManifest.export.artifactDigests.length === 0
      || targetManifest.export.artifactDigests.some((digest) => !validSha256(digest)))) {
    errors.push('failed-restore boundary has incomplete encrypted artifact evidence')
  }

  const targets = Object.values(targetManifest.destructiveTargets ?? {}).flat()
  const restoreStatus = targetManifest.restore?.status
  if (!['not-started', 'failed', 'passed'].includes(restoreStatus)) {
    errors.push('restore must be unstarted, failed, or passed')
  } else if (restoreStatus === 'passed') {
    for (const reason of validateResolvedEvidence(targetManifest)) errors.push(reason)
    if (targets.length === 0) errors.push('passed restore must settle exact destructive targets')
  } else {
    if (restoreStatus === 'failed'
      && (targetManifest.restore.completedAt !== null
        || targetManifest.restore.countsAndDigestsMatch !== false
        || !Array.isArray(targetManifest.restore.mismatches)
        || targetManifest.restore.mismatches.length === 0)) {
      errors.push('failed restore must keep completion unset and record exact mismatches')
    }
    if (targetManifest.retention?.status !== 'not-started'
      || targetManifest.retention.startsAt !== null
      || targetManifest.retention.deadline !== null) {
      errors.push('retention must remain unstarted before a passing restore')
    }
    if (targets.length !== 0) errors.push('unverified restore must not prepare a destructive target')
  }
  if (targetManifest.receipts?.length !== 0) errors.push('prepared boundary must not record action receipts')
  if (targetManifest.retention?.status !== 'indefinite') {
    errors.push('retention must record the owner\'s indefinite-retention decision')
  }
  if (approvalManifest.status !== 'retained' || approvalManifest.approvals?.length !== 0) {
    errors.push('approval manifest must record retention and contain no approvals')
  }
  if (approvalManifest.targetManifestSha256 !== digestManifest(targetManifest)) {
    errors.push('approval manifest digest does not bind the target manifest')
  }
  return errors
}

function main() {
  const targetManifest = JSON.parse(readFileSync(targetManifestPath, 'utf8'))
  const approvalManifest = JSON.parse(readFileSync(approvalManifestPath, 'utf8'))
  const errors = validateRetainedBoundary(targetManifest, approvalManifest)
  if (errors.length > 0) {
    for (const error of errors) process.stderr.write(`Part 13G boundary: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write('Part 13G retention boundary passed: the verified external archive is retained and every destructive action remains denied.\n')
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
