import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { inspectPhase14Contract } from './verify-phase-14a-contract.mjs'
import { inspectPhase14BInfrastructure } from './verify-phase-14b-infrastructure.mjs'
import { inspectPhase14CSecurity } from './verify-phase-14c-security.mjs'
import { inspectPhase14DDeployment } from './verify-phase-14d-deployment.mjs'
import { inspectPhase14EOperations } from './verify-phase-14e-operations.mjs'
import { inspectPhase14FRecovery } from './verify-phase-14f-recovery.mjs'
import { inspectPhase14GPromotion } from './verify-phase-14g-promotion.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const relativeFiles = {
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
  trace: 'docs/migration/phase-14/evidence/PART_14H_INDEPENDENT_TRACE.json',
  live: 'docs/migration/phase-14/evidence/PART_14H_CLOSING_LIVE.json',
  releaseIdentity: 'docs/migration/phase-14/evidence/PART_14H_RELEASE_IDENTITY.json',
  review: 'docs/migration/phase-14/PART_14H_INDEPENDENT_REVIEW.md',
  partCompletion: 'docs/migration/phase-14/PART_14H_COMPLETION.md',
  phaseCompletion: 'docs/migration/phase-14/PHASE_14_COMPLETION.md',
  workflow: '.github/workflows/migration-foundation.yml',
}
const rollbackOrder = ['14H', '14G', '14F', '14E', '14D', '14C', '14B', '14A']
const requiredEvidenceSections = {
  '14B': ['source', 'terraform', 'tests', 'completion'],
  '14C': ['source', 'terraform', 'tests', 'completion'],
  '14D': ['source', 'releaseArtifacts', 'tests', 'completion'],
  '14E': ['source', 'operatingRecords', 'logs', 'cost', 'tests', 'completion'],
  '14F': ['source', 'backupRestore', 'tests', 'completion'],
  '14G': ['providerState', 'releaseArtifacts', 'cost', 'logs', 'cleanup', 'completion'],
  '14H': ['trace', 'review', 'liveCheck', 'releaseIdentity', 'workflow', 'completion'],
}
const forbiddenEvidenceKey = /(?:password|token|connection.?string|private.?key|secret.?value|signed.?url|object.?key|console.?payload)/i

function readText(root, relativePath) {
  const absolute = path.join(root, relativePath)
  return existsSync(absolute) ? readFileSync(absolute, 'utf8').replaceAll('\r\n', '\n') : ''
}

function parseJson(errors, source, label) {
  try {
    return JSON.parse(source)
  } catch {
    errors.push(`missing or invalid ${label}`)
    return {}
  }
}

function addExactSetErrors(errors, actual, expected, label) {
  const duplicates = actual.filter((value, index) => actual.indexOf(value) !== index)
  if (duplicates.length > 0) errors.push(`${label} contains duplicate IDs: ${[...new Set(duplicates)].join(', ')}`)
  const actualSet = new Set(actual)
  const missing = expected.filter((value) => !actualSet.has(value))
  const unexpected = actual.filter((value) => !expected.includes(value))
  if (missing.length > 0) errors.push(`${label} is missing: ${missing.join(', ')}`)
  if (unexpected.length > 0) errors.push(`${label} has unexpected IDs: ${unexpected.join(', ')}`)
}

function alembicHeads(root) {
  const revisions = new Set()
  const predecessors = new Set()
  for (const name of readdirSync(path.join(root, 'backend', 'alembic', 'versions'))) {
    if (!name.endsWith('.py')) continue
    const source = readFileSync(path.join(root, 'backend', 'alembic', 'versions', name), 'utf8')
    const revision = source.match(/^revision:[^=]+=[ ]*['\"]([^'\"]+)['\"]/m)
    if (!revision) throw new Error(`Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['\"]([^'\"]+)['\"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

function inspectProtectedKeys(value, location = 'trace') {
  const errors = []
  if (Array.isArray(value)) {
    value.forEach((entry, index) => errors.push(...inspectProtectedKeys(entry, `${location}[${index}]`)))
  } else if (value && typeof value === 'object') {
    for (const [key, entry] of Object.entries(value)) {
      if (forbiddenEvidenceKey.test(key)) errors.push(`${location}.${key} uses a prohibited evidence field`)
      errors.push(...inspectProtectedKeys(entry, `${location}.${key}`))
    }
  }
  return errors
}

function validateTraceEntry(errors, entry, catalogueEntry, evidenceSets, label) {
  if (!catalogueEntry) return
  if (entry.owner !== catalogueEntry.owner) errors.push(`${label} ${entry.id} owner does not match the catalogue`)
  if (entry.evidenceSet !== catalogueEntry.owner) errors.push(`${label} ${entry.id} does not use its owner evidence set`)
  if (entry.result !== 'passed') errors.push(`${label} ${entry.id} is not passed`)
  if (!evidenceSets[entry.evidenceSet]) errors.push(`${label} ${entry.id} names an unknown evidence set`)
}

function validateEvidenceSets(errors, trace, root) {
  for (const [owner, sections] of Object.entries(requiredEvidenceSections)) {
    const evidenceSet = trace.evidenceSets?.[owner]
    if (!evidenceSet) {
      errors.push(`missing ${owner} evidence set`)
      continue
    }
    for (const section of sections) {
      const paths = evidenceSet[section]
      if (!Array.isArray(paths) || paths.length === 0) {
        errors.push(`${owner} evidence set lacks ${section}`)
        continue
      }
      for (const relativePath of paths) {
        if (!existsSync(path.join(root, relativePath))) errors.push(`${owner} evidence path does not exist: ${relativePath}`)
      }
    }
  }
}

function validateLiveEvidence(errors, live) {
  if (live.schemaVersion !== 1 || live.part !== '14H' || live.result !== 'passed') errors.push('closing live evidence is incomplete')
  if (live.target?.defaultUrl !== 'https://workloop-clinic-dev-e9uk5.ondigitalocean.app'
    || live.target?.customDomain !== false || live.target?.automaticDeployment !== false
    || live.target?.dataClass !== 'synthetic-only'
    || live.target?.presentation !== 'architecture-proof') errors.push('closing live target boundary changed')
  for (const name of ['providerReadOnly', 'publicWeb', 'publicHealth', 'administrator', 'manager', 'employee', 'fileFlow', 'safeLogs']) {
    if (live.checks?.[name] !== 'passed') errors.push(`closing live check did not pass: ${name}`)
  }
  if (live.syntheticCleanup?.status !== 'passed' || live.syntheticCleanup?.namedFixturesOnly !== true
    || live.syntheticCleanup?.identitiesRemoved !== 3 || live.syntheticCleanup?.databaseRowsRemoved !== 7) {
    errors.push('closing synthetic cleanup is incomplete')
  }
  if (live.providerMutation?.journeyOnly !== true || live.providerMutation?.infrastructureChanged !== false) {
    errors.push('closing live check crossed the provider mutation boundary')
  }
  if (live.cost?.monthToDateUsageUsd !== 1.81 || live.cost?.reviewedRunForecastUsd !== 13.63
    || live.cost?.ownerUsageCapUsd !== 15
    || live.cost?.withinCap !== true) errors.push('closing cost evidence changed')
  if (live.architectureBoundary?.integratedPortal !== false
    || live.architectureBoundary?.productionReady !== false
    || live.architectureBoundary?.phase15Authorized !== false) {
    errors.push('closing architecture boundary changed')
  }
  for (const name of ['workloop-clinic-dev', 'fra1-default', 'Phase 13 external archive', 'workloop-clinic_postgres_data']) {
    if (!live.preservedResources?.includes(name)) errors.push(`closing live evidence does not preserve ${name}`)
  }
}

function validateReleaseIdentity(errors, identity) {
  if (identity.schemaVersion !== 1 || identity.part !== '14H'
    || identity.result !== 'passed-with-correction' || identity.findingId !== 'P14H-F-001') {
    errors.push('release-identity correction is incomplete')
  }
  if (identity.releaseId !== 'phase-14g-dc6e54a'
    || identity.reviewedCommit !== 'dc6e54afb4e16665a62b933999d85b83a57cb40a'
    || identity.originalManifest?.sha256 !== 'sha256:5330f3253763598793250530dead62830e4ec783115b32f4d15300716538166c') {
    errors.push('release-identity correction is not bound to the Phase 14G record')
  }
  if (identity.deployedFrontend?.providerSourceCommit !== 'ba12774e30539093d8f71d75cd010f64aa4ca777'
    || identity.deployedFrontend?.sourceMatchesReviewedCommit !== true
    || identity.deployedFrontend?.frontendSha256 !== 'sha256:75c0d4e932cab5dc937e68dc47dc0e30d107fdacf39912d355ac97e53ebf65d2'
    || identity.deployedFrontend?.frontendRootSha256 !== 'sha256:68a681042c29e4be17c4d7d05d68a043087c087a6b765aa9b4eaedfddb7657e5'
    || identity.deployedFrontend?.deliveredRootSha256 !== identity.deployedFrontend?.frontendRootSha256
    || identity.deployedFrontend?.deliveredRootStatus !== 200
    || identity.deployedFrontend?.automaticDeployment !== false) {
    errors.push('deployed frontend identity is incomplete')
  }
  if (identity.decision?.liveChangeRequired !== false || identity.decision?.ownerSignoffRequired !== true) {
    errors.push('release-identity correction decision changed')
  }
}

function validateDocuments(errors, sources) {
  for (const [key, marker] of [
    ['review', '# Part 14H independent review'],
    ['partCompletion', '# Part 14H completion'],
    ['phaseCompletion', '# Phase 14 completion'],
  ]) {
    if (!sources[key].includes(marker)) errors.push(`missing ${marker}`)
  }
  for (const marker of ['P14-REV-001', 'P14-REV-005', '14A-GC-036', '14A-GC-038']) {
    if (!sources.review.includes(marker)) errors.push(`independent review omits ${marker}`)
  }
  if (!sources.workflow.includes('name: Verify Phase 14H independent review\n        run: npm run verify:phase14h:review')) {
    errors.push('closing workflow does not route the Phase 14H verifier')
  }
}

function validatePriorParts(errors, root) {
  const reports = [
    ['14A', inspectPhase14Contract(root)],
    ['14B', inspectPhase14BInfrastructure(root)],
    ['14C', inspectPhase14CSecurity(root)],
    ['14D', inspectPhase14DDeployment(root)],
    ['14E', inspectPhase14EOperations(root)],
    ['14F', inspectPhase14FRecovery(root)],
    ['14G', inspectPhase14GPromotion(root, { final: true })],
  ]
  for (const [part, report] of reports) {
    for (const error of report.errors ?? []) errors.push(`${part}: ${error}`)
  }
}

export function readPhase14HReview(root = repositoryDirectory) {
  return Object.fromEntries(Object.entries(relativeFiles).map(([key, value]) => [key, readText(root, value)]))
}

export function validatePhase14HReview(sources, root = repositoryDirectory) {
  const errors = []
  const catalogue = parseJson(errors, sources.catalogue, 'deployment catalogue')
  const trace = parseJson(errors, sources.trace, 'independent trace')
  const live = parseJson(errors, sources.live, 'closing live evidence')
  const releaseIdentity = parseJson(errors, sources.releaseIdentity, 'release-identity correction')
  const inventoryTrace = trace.inventory ?? []
  const goldenTrace = trace.goldenCases ?? []
  addExactSetErrors(errors, inventoryTrace.map((entry) => entry.id), (catalogue.inventory ?? []).map((entry) => entry.id), 'inventory trace')
  addExactSetErrors(errors, goldenTrace.map((entry) => entry.id), (catalogue.goldenCases ?? []).map((entry) => entry.id), 'golden-case trace')
  const inventoryById = new Map((catalogue.inventory ?? []).map((entry) => [entry.id, entry]))
  const goldenById = new Map((catalogue.goldenCases ?? []).map((entry) => [entry.id, entry]))
  for (const entry of inventoryTrace) validateTraceEntry(errors, entry, inventoryById.get(entry.id), trace.evidenceSets ?? {}, 'inventory')
  for (const entry of goldenTrace) validateTraceEntry(errors, entry, goldenById.get(entry.id), trace.evidenceSets ?? {}, 'golden case')
  validateEvidenceSets(errors, trace, root)
  errors.push(...inspectProtectedKeys(trace))
  if (JSON.stringify(trace.rollbackOrder) !== JSON.stringify(rollbackOrder)
    || JSON.stringify(catalogue.rollbackOrder) !== JSON.stringify(rollbackOrder)) errors.push('phase rollback order changed')
  for (const [name, status] of Object.entries(trace.boundaries ?? {})) {
    if (status !== 'passed') errors.push(`phase boundary did not pass: ${name}`)
  }
  for (const name of ['realData', 'customDomain', 'externalDelivery', 'automaticDeployment', 'secondProviderWork', 'phase13ArchiveChange', 'unapprovedResource', 'committedProtectedMaterial', 'unreviewedPublicPath']) {
    if (!(name in (trace.boundaries ?? {}))) errors.push(`phase boundary is missing: ${name}`)
  }
  validateLiveEvidence(errors, live)
  validateReleaseIdentity(errors, releaseIdentity)
  validateDocuments(errors, sources)
  validatePriorParts(errors, root)
  const heads = alembicHeads(root)
  if (heads.length !== 1 || heads[0] !== 'e8a1c3f5b7d9') errors.push(`unexpected Alembic heads: ${heads.join(', ')}`)
  return {
    errors,
    inventory: inventoryTrace.length,
    goldenCases: goldenTrace.length,
    alembicHeads: heads,
  }
}

export function inspectPhase14HReview(root = repositoryDirectory) {
  return validatePhase14HReview(readPhase14HReview(root), root)
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  const report = inspectPhase14HReview()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14H review: ${error}\n`)
    process.exitCode = 1
  } else {
    process.stdout.write(`Phase 14H independent review passed: ${report.inventory} inventory items and ${report.goldenCases} golden cases traced with one Alembic head.\n`)
  }
}
