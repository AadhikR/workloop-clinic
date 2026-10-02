import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-15')

export const cataloguePath = path.join(phaseDirectory, 'integration-catalogue.json')
export const evidencePath = path.join(phaseDirectory, 'evidence', 'PART_15F_LOCAL_ACCEPTANCE.json')

const ownedInventory = [
  'P15-FIL-001',
  'P15-FIL-002',
  'P15-FIL-003',
  'P15-FIL-004',
  'P15-FIL-005',
  'P15-FIL-006',
  'P15-VAL-001',
  'P15-VAL-002',
  'P15-VAL-003',
]
const ownedGoldenCases = [
  '15A-GC-025',
  '15A-GC-026',
  '15A-GC-027',
  '15A-GC-028',
  '15A-GC-029',
  '15A-GC-030',
]
const expectedFileFlows = [
  'P15-FLOW-001',
  'P15-FLOW-002',
  'P15-FLOW-003',
  'P15-FLOW-004',
  'P15-FLOW-005',
  'P15-FLOW-006',
]
const expectedDenials = [
  'cross-role',
  'cross-company',
  'cross-branch',
  'cross-manager',
  'cross-employee',
  'record',
  'file',
]
const expectedAccessibilityChecks = [
  'keyboard-order',
  'visible-focus',
  'skip-navigation',
  'landmarks',
  'accessible-names',
  'status-updates',
  'dialogs',
  'contrast',
  '200-percent-zoom',
  'reduced-motion',
  'error-recovery',
]
const expectedMetrics = [
  'initialCompressedTransferBytes',
  'laterRouteTransferBytes',
  'largestRouteBundleCompressedBytes',
  'routeChangeP95Ms',
  'formFeedbackP95Ms',
  'representativeApiP95Ms',
]

function exactSet(errors, actual, expected, label) {
  const unique = [...new Set(actual)]
  const missing = expected.filter((value) => !unique.includes(value))
  const unexpected = unique.filter((value) => !expected.includes(value))
  if (unique.length !== actual.length) errors.push(`${label} contains duplicates`)
  if (missing.length > 0) errors.push(`${label} is missing ${missing.join(', ')}`)
  if (unexpected.length > 0) errors.push(`${label} has unexpected values ${unexpected.join(', ')}`)
}

function validateMetric(errors, evidence, name) {
  const budget = evidence.performance?.budgets?.[name]
  const measurement = evidence.performance?.measurements?.[name]
  if (!Number.isFinite(budget) || budget <= 0) errors.push(`${name} has no positive budget`)
  if (!measurement || !Number.isFinite(measurement.value) || measurement.value < 0) {
    errors.push(`${name} has no measurement`)
    return
  }
  if (!Number.isInteger(measurement.sampleCount) || measurement.sampleCount < 1) {
    errors.push(`${name} has no sample count`)
  }
  if (!measurement.percentile || !measurement.cacheState) {
    errors.push(`${name} is missing percentile or cache state`)
  }
  if (Number.isFinite(budget) && measurement.value > budget) {
    errors.push(`${name} exceeds its budget`)
  }
}

export function validatePhase15FAcceptance(catalogue, evidence, { root = repositoryDirectory } = {}) {
  const errors = []
  if (evidence.schemaVersion !== 1 || evidence.phase !== '15' || evidence.part !== '15F') {
    errors.push('acceptance record identity is invalid')
  }
  if (evidence.status !== 'passed') errors.push('acceptance record has not passed')

  const catalogueInventory = catalogue.inventory.filter((entry) => entry.owner === '15F')
  exactSet(errors, catalogueInventory.map((entry) => entry.id), ownedInventory, '15F inventory')
  const catalogueGolden = catalogue.goldenCases.filter((entry) => entry.owner === '15F')
  exactSet(errors, catalogueGolden.map((entry) => entry.id), ownedGoldenCases, '15F golden cases')
  exactSet(errors, catalogue.fileFlows.map((entry) => entry.id), expectedFileFlows, 'file flows')

  for (const entry of [...catalogueInventory, ...catalogueGolden]) {
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) {
      errors.push(`${entry.id} has no 15F evidence`)
      continue
    }
    for (const target of entry.evidence) {
      if (!existsSync(path.join(root, target))) errors.push(`${entry.id} has missing evidence ${target}`)
    }
  }

  exactSet(errors, evidence.journeys?.roles ?? [], ['admin', 'manager', 'employee'], 'role journeys')
  if (evidence.journeys?.routeCount !== 25) errors.push('route journey count is not 25')
  if (evidence.journeys?.syntheticOnly !== true) errors.push('role journeys are not synthetic-only')
  exactSet(errors, evidence.denials?.scopes ?? [], expectedDenials, 'denial scopes')
  if (evidence.denials?.backendAuthoritative !== true) errors.push('backend denial is not authoritative')

  exactSet(
    errors,
    (evidence.fileFlows ?? []).map((entry) => entry.id),
    expectedFileFlows,
    'file-flow evidence',
  )
  for (const flow of evidence.fileFlows ?? []) {
    for (const check of ['type', 'size', 'authorization', 'failure', 'cleanup']) {
      if (flow[check] !== 'passed') errors.push(`${flow.id} did not pass ${check}`)
    }
  }

  exactSet(errors, evidence.accessibility?.checks ?? [], expectedAccessibilityChecks, 'accessibility checks')
  if (evidence.accessibility?.routeGroupCount !== 25) errors.push('accessibility route count is not 25')
  if (evidence.accessibility?.keyboardOnly !== true) errors.push('keyboard-only proof is missing')
  if (evidence.accessibility?.screenReaderSpotCheck !== true) errors.push('screen-reader spot check is missing')

  const profile = evidence.performance?.profile
  for (const field of ['name', 'runner', 'browser', 'network']) {
    if (typeof profile?.[field] !== 'string' || profile[field].trim() === '') {
      errors.push(`performance profile has no ${field}`)
    }
  }
  if (profile?.command !== 'npm run verify:phase15f:performance') {
    errors.push('performance command is not reproducible')
  }
  exactSet(errors, Object.keys(evidence.performance?.budgets ?? {}), expectedMetrics, 'performance budgets')
  exactSet(errors, Object.keys(evidence.performance?.measurements ?? {}), expectedMetrics, 'performance measurements')
  for (const metric of expectedMetrics) validateMetric(errors, evidence, metric)

  if (evidence.restart?.passed !== true) errors.push('restart proof is missing')
  if (evidence.safeLogs?.passed !== true) errors.push('safe-log proof is missing')
  if (evidence.cleanup?.passed !== true || evidence.cleanup?.exactIdentifiers !== true) {
    errors.push('exact cleanup proof is missing')
  }
  if (evidence.cleanup?.composeProject !== 'workloop-phase15f-verify') {
    errors.push('cleanup project is not the 15F disposable project')
  }
  if (evidence.cleanup?.protectedVolume !== 'workloop-clinic_postgres_data') {
    errors.push('protected volume boundary is missing')
  }
  if (evidence.alembicHead !== 'e8a1c3f5b7d9') errors.push('Alembic head changed')

  return { errors, metrics: expectedMetrics.length, routeGroups: evidence.journeys?.routeCount ?? 0 }
}

export function inspectPhase15FAcceptance() {
  const catalogue = JSON.parse(readFileSync(cataloguePath, 'utf8'))
  const evidence = JSON.parse(readFileSync(evidencePath, 'utf8'))
  return validatePhase15FAcceptance(catalogue, evidence)
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = inspectPhase15FAcceptance()
  if (report.errors.length > 0) {
    console.error(report.errors.join('\n'))
    process.exitCode = 1
  } else {
    console.log(`Phase 15F acceptance record passed for ${report.routeGroups} route groups and ${report.metrics} performance metrics.`)
  }
}
