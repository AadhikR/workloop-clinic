import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-15')

export const cataloguePath = path.join(phaseDirectory, 'integration-catalogue.json')
export const planPath = path.join(phaseDirectory, 'SUBPHASE_PLAN.md')
export const inventoryPath = path.join(phaseDirectory, 'PART_15A_DEPENDENCY_INVENTORY.md')
export const contractPath = path.join(phaseDirectory, 'PART_15A_PORTAL_INTEGRATION_CONTRACT.md')
export const goldenPath = path.join(phaseDirectory, 'PART_15A_GOLDEN_CASES.md')

const expectedParts = ['15A', '15B', '15C', '15D', '15E', '15F', '15G', '15H']
const expectedOwners = expectedParts.slice(1)
const expectedRollback = [...expectedParts].reverse()
const expectedRoles = new Set(['public', 'admin', 'manager', 'employee'])
const expectedClients = new Map([
  ['src/organizationApi.js', ['/api/v1/company', '/api/v1/employer', '/api/v1/branches']],
  ['src/sampleApi.js', ['/api/v1/public/status', '/api/v1/account/me', '/api/v1/architecture-proof/storage']],
  ['src/notificationApi.js', ['/api/v1/notifications']],
  ['src/taskApi.js', ['/api/v1/tasks']],
  ['src/dashboardApi.js', ['/api/v1/dashboards/']],
  ['src/departmentApi.js', ['/api/v1/departments', '/api/v1/department-staffing-rules']],
  ['src/employeeApi.js', ['/api/v1/employees', '/api/v1/employee-imports', '/api/v1/employee-job-history']],
  ['src/leaveConfigurationApi.js', ['/api/v1/leave/settings', '/api/v1/leave/types', '/api/v1/leave/holidays']],
  ['src/leaveBalanceApi.js', ['/api/v1/leave/balances/', '/api/v1/leave/requests/calendar/']],
  ['src/leaveRequestApi.js', ['/api/v1/leave/requests/']],
  ['src/leaveApprovalApi.js', ['/api/v1/leave/approvals/', '/api/v1/leave/delegations/']],
  ['src/leaveAttachmentApi.js', ['/api/v1/leave/attachment-submissions', '/api/v1/leave/attachments/']],
  ['src/attendanceConfigurationApi.js', ['/api/v1/attendance-settings', '/api/v1/shifts', '/api/v1/shift-assignments']],
  ['src/attendanceIngestionApi.js', ['/api/v1/clock-events', '/api/v1/biometric-mappings', '/api/v1/biometric-imports']],
  ['src/attendanceCalculationApi.js', ['/api/v1/attendance-records', '/api/v1/attendance/me', '/api/v1/attendance/calculations']],
  ['src/attendanceExceptionsApi.js', ['/api/v1/attendance/regularisations', '/api/v1/attendance/audit']],
  ['src/attendancePeriodsApi.js', ['/api/v1/attendance/periods']],
  ['src/rosterApi.js', ['/api/v1/roster/months/', '/api/v1/roster/schedules/']],
  ['src/shiftSwapApi.js', ['/api/v1/roster/shift-swaps']],
  ['src/payrollApi.js', ['/api/v1/payroll-runs', '/api/v1/payslips/self']],
  ['src/wpsNafisApi.js', ['/api/v1/payroll-runs/', '/api/v1/nafis-snapshots']],
  ['src/expenseApi.js', ['/api/v1/expenses']],
  ['src/advanceApi.js', ['/api/v1/advances']],
  ['src/recordsBenefitsApi.js', ['/api/v1/employee-documents', '/api/v1/insurance/', '/api/v1/employees/']],
  ['src/developmentAssetsApi.js', ['/api/v1/assets', '/api/v1/training-records', '/api/v1/certifications', '/api/v1/cme/']],
  ['src/appraisalsIncidentsApi.js', ['/api/v1/appraisal-cycles', '/api/v1/appraisals/', '/api/v1/clinical-incidents']],
  ['src/letterRequestsApi.js', ['/api/v1/requests']],
  ['src/offboardingApi.js', ['/api/v1/offboarding']],
  ['src/reportApi.js', ['/api/v1/reports/']],
  ['src/outputApi.js', ['/api/v1/exports/']],
  ['src/renderedOutputApi.js', ['/api/v1/reports/', '/api/v1/payslips/', '/api/v1/requests/', '/api/v1/offboarding/']],
])

function readText(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function exactIds(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1])
}

function addExactSetErrors(errors, actual, expected, label) {
  const duplicate = actual.filter((value, index) => actual.indexOf(value) !== index)
  if (duplicate.length > 0) errors.push(`${label} contains duplicate IDs: ${[...new Set(duplicate)].join(', ')}`)
  const actualSet = new Set(actual)
  const expectedSet = new Set(expected)
  const missing = expected.filter((value) => !actualSet.has(value))
  const unexpected = actual.filter((value) => !expectedSet.has(value))
  if (missing.length > 0) errors.push(`${label} is missing: ${missing.join(', ')}`)
  if (unexpected.length > 0) errors.push(`${label} has unexpected IDs: ${unexpected.join(', ')}`)
}

function alembicHeads(root = repositoryDirectory) {
  const versions = path.join(root, 'backend', 'alembic', 'versions')
  const revisions = new Set()
  const predecessors = new Set()
  for (const name of readdirSync(versions)) {
    if (!name.endsWith('.py')) continue
    const source = readText(path.join(versions, name))
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (!revision) throw new Error(`Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

function indexedAlembicDigest(root = repositoryDirectory) {
  const result = spawnSync('git', ['ls-files', '-s', '-z', 'backend/alembic', ':(exclude)backend/alembic/versions/f1a3c5e7b9d2_add_branch_payroll_routing_command.py', ':(exclude)backend/alembic/versions/e2c4f6a8b0d3_add_training_personal_results.py', ':(exclude)backend/alembic/versions/f3a5c7e9b1d4_add_portal_retained_commands.py'], {
    cwd: root,
    encoding: 'buffer',
  })
  if (result.status !== 0) throw new Error(result.stderr.toString('utf8'))
  return createHash('sha256').update(result.stdout).digest('hex')
}

function validateRoleList(errors, roles, label) {
  if (!Array.isArray(roles) || roles.length === 0) {
    errors.push(`${label} has no roles`)
    return
  }
  for (const role of roles) if (!expectedRoles.has(role)) errors.push(`${label} has invalid role ${role}`)
}

function addDocumentIdErrors(errors, documents, catalogue) {
  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P15-(?:SHL|ADM|MGR|EMP|FIL|VAL)-\d{3})` \|/gm),
    catalogue.inventory.map((entry) => entry.id),
    'prose inventory',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P15-API-\d{3})` \|/gm),
    catalogue.clientContracts.map((entry) => entry.id),
    'prose client contracts',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P15-ROUTE-\d{3})` \|/gm),
    catalogue.routeContracts.map((entry) => entry.id),
    'prose routes',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P15-FLOW-\d{3})` \|/gm),
    catalogue.fileFlows.map((entry) => entry.id),
    'prose file flows',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P15-GAP-\d{3})` \|/gm),
    catalogue.knownGaps.map((entry) => entry.id),
    'prose gaps',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.golden, /^\| `(15A-GC-\d{3})` \|/gm),
    catalogue.goldenCases.map((entry) => entry.id),
    'prose golden cases',
  )
}

export function validatePhase15Catalogue(
  catalogue,
  documents,
  { root = repositoryDirectory, checkRepository = true } = {},
) {
  const errors = []
  if (catalogue.schemaVersion !== 1 || catalogue.phase !== '15' || catalogue.part !== '15A') {
    errors.push('catalogue identity or schema version is invalid')
  }
  if (JSON.stringify(catalogue.partSequence) !== JSON.stringify(expectedParts)) {
    errors.push('part sequence must be exactly 15A through 15H')
  }
  if (JSON.stringify(catalogue.allowedOwners) !== JSON.stringify(expectedOwners)) {
    errors.push('allowed owners must be exactly 15B through 15H')
  }
  if (JSON.stringify(catalogue.rollbackOrder) !== JSON.stringify(expectedRollback)) {
    errors.push('phase rollback order is not the exact reverse part order')
  }
  if (JSON.stringify(catalogue.currentFrontendEntrypoints) !== JSON.stringify(['/', '/oidc/callback'])) {
    errors.push('current frontend entrypoints are not exact')
  }

  const actions = new Set(catalogue.allowedActions)
  const evidenceClasses = new Set(catalogue.allowedEvidenceClasses)
  const inventoryIds = catalogue.inventory.map((entry) => entry.id)
  addExactSetErrors(errors, inventoryIds, [...new Set(inventoryIds)], 'inventory')
  for (const entry of catalogue.inventory) {
    if (!/^P15-(?:SHL|ADM|MGR|EMP|FIL|VAL)-\d{3}$/.test(entry.id)) errors.push(`${entry.id} has an invalid inventory ID`)
    if (!expectedOwners.includes(entry.owner)) errors.push(`${entry.id} has invalid owner ${entry.owner}`)
    if (!actions.has(entry.action)) errors.push(`${entry.id} has invalid action ${entry.action}`)
    for (const key of ['category', 'item', 'currentState']) {
      if (typeof entry[key] !== 'string' || entry[key].trim() === '') errors.push(`${entry.id} has no ${key}`)
    }
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) errors.push(`${entry.id} has no evidence target`)
    if (!Array.isArray(entry.evidenceClasses) || entry.evidenceClasses.length === 0) errors.push(`${entry.id} has no evidence class`)
    for (const evidenceClass of entry.evidenceClasses ?? []) {
      if (!evidenceClasses.has(evidenceClass)) errors.push(`${entry.id} has invalid evidence class ${evidenceClass}`)
    }
    if (checkRepository) {
      for (const target of entry.evidence ?? []) {
        if (!existsSync(path.join(root, target))) errors.push(`${entry.id} has unresolved evidence ${target}`)
      }
    }
  }

  const clientIds = catalogue.clientContracts.map((entry) => entry.id)
  const clientSources = catalogue.clientContracts.map((entry) => entry.source)
  addExactSetErrors(errors, clientIds, [...new Set(clientIds)], 'client contracts')
  addExactSetErrors(errors, clientSources, [...expectedClients.keys()], 'client source inventory')
  for (const client of catalogue.clientContracts) {
    if (!/^P15-API-\d{3}$/.test(client.id)) errors.push(`${client.id} has an invalid client ID`)
    if (!expectedOwners.includes(client.owner)) errors.push(`${client.id} has invalid owner ${client.owner}`)
    validateRoleList(errors, client.roles, client.id)
    const expectedMarkers = expectedClients.get(client.source) ?? []
    if (JSON.stringify(client.sourceMarkers) !== JSON.stringify(expectedMarkers)) {
      errors.push(`${client.id} has an invented or missing endpoint marker`)
    }
    if (!Array.isArray(client.backendSources) || client.backendSources.length === 0) errors.push(`${client.id} has no backend source`)
    if (checkRepository) {
      const source = readText(path.join(root, client.source))
      for (const marker of client.sourceMarkers ?? []) {
        if (!source.includes(marker)) errors.push(`${client.source} is missing ${marker}`)
      }
      for (const backendSource of client.backendSources ?? []) {
        if (!existsSync(path.join(root, backendSource))) errors.push(`${client.id} has missing backend source ${backendSource}`)
      }
    }
  }

  const routeIds = catalogue.routeContracts.map((entry) => entry.id)
  const routePaths = catalogue.routeContracts.map((entry) => entry.path)
  addExactSetErrors(errors, routeIds, [...new Set(routeIds)], 'route contracts')
  addExactSetErrors(errors, routePaths, [...new Set(routePaths)], 'route paths')
  for (const route of catalogue.routeContracts) {
    if (!/^P15-ROUTE-\d{3}$/.test(route.id)) errors.push(`${route.id} has an invalid route ID`)
    if (!route.path.startsWith('/') || route.path.includes('{')) errors.push(`${route.id} has an invalid browser path`)
    validateRoleList(errors, route.roles, route.id)
    const expectedOwner = route.path.startsWith('/admin') ? '15C'
      : route.path.startsWith('/manager') ? '15D'
        : route.path.startsWith('/employee') ? '15E' : '15B'
    if (route.owner !== expectedOwner) errors.push(`${route.id} has invalid route owner ${route.owner}`)
    if (typeof route.result !== 'string' || route.result.trim() === '') errors.push(`${route.id} has no result`)
  }

  const flowIds = catalogue.fileFlows.map((entry) => entry.id)
  addExactSetErrors(errors, flowIds, [...new Set(flowIds)], 'file flows')
  for (const flow of catalogue.fileFlows) {
    if (!/^P15-FLOW-\d{3}$/.test(flow.id)) errors.push(`${flow.id} has an invalid file-flow ID`)
    if (flow.owner !== '15F') errors.push(`${flow.id} has invalid owner ${flow.owner}`)
    validateRoleList(errors, flow.roles, flow.id)
    if (!flow.downloadSource) errors.push(`${flow.id} has no download source`)
    if (checkRepository) {
      for (const target of [flow.uploadSource, flow.downloadSource].filter(Boolean)) {
        if (!existsSync(path.join(root, target))) errors.push(`${flow.id} has missing source ${target}`)
      }
    }
  }

  const gapIds = catalogue.knownGaps.map((entry) => entry.id)
  addExactSetErrors(errors, gapIds, [...new Set(gapIds)], 'known gaps')
  for (const gap of catalogue.knownGaps) {
    if (!/^P15-GAP-\d{3}$/.test(gap.id)) errors.push(`${gap.id} has an invalid gap ID`)
    if (!expectedOwners.includes(gap.owner)) errors.push(`${gap.id} has invalid owner ${gap.owner}`)
    if (!gap.gap || !gap.disposition) errors.push(`${gap.id} is incomplete`)
  }

  const goldenIds = catalogue.goldenCases.map((entry) => entry.id)
  addExactSetErrors(errors, goldenIds, [...new Set(goldenIds)], 'golden cases')
  for (const golden of catalogue.goldenCases) {
    if (!/^15A-GC-\d{3}$/.test(golden.id)) errors.push(`${golden.id} has an invalid golden-case ID`)
    if (!expectedOwners.includes(golden.owner)) errors.push(`${golden.id} has invalid owner ${golden.owner}`)
    if (!golden.area || !golden.expectation) errors.push(`${golden.id} is incomplete`)
    for (const evidenceClass of golden.evidenceClasses ?? []) {
      if (!evidenceClasses.has(evidenceClass)) errors.push(`${golden.id} has invalid evidence class ${evidenceClass}`)
    }
  }
  for (const owner of expectedOwners) {
    if (!catalogue.inventory.some((entry) => entry.owner === owner)) errors.push(`${owner} owns no inventory item`)
    if (!catalogue.goldenCases.some((entry) => entry.owner === owner)) errors.push(`${owner} owns no golden case`)
  }

  const boundary = catalogue.deploymentBoundary
  if (boundary.provider !== 'DigitalOcean' || boundary.automaticDeployment !== false || boundary.liveCostCapUsd !== 15) {
    errors.push('deployment boundary is invalid')
  }
  addExactSetErrors(
    errors,
    boundary.preservedResources,
    ['workloop-clinic-dev', 'fra1-default', 'Phase 13 external archive', 'workloop-clinic_postgres_data'],
    'preserved resources',
  )

  addDocumentIdErrors(errors, documents, catalogue)
  for (const part of expectedParts) {
    if (!documents.plan.includes(`| ${part} |`)) errors.push(`subphase plan does not assign Part ${part}`)
  }
  const normalizedContract = documents.contract.replace(/\s+/g, ' ')
  for (const token of [
    'server authorization remains authoritative',
    'client-side role checks are presentation controls only',
    'No new backend business capability',
    'e8a1c3f5b7d9',
    'Automatic deployment remains disabled',
    'provider-managed App Platform default address',
    'Synthetic identities, rows, and files only',
    'workloop-clinic_postgres_data',
    'P14H-F-001',
  ]) {
    if (!normalizedContract.includes(token)) errors.push(`portal contract is missing ${token}`)
  }

  if (checkRepository) {
    const heads = alembicHeads(root)
    if (heads.length !== 1 || heads[0] !== 'f3a5c7e9b1d4') errors.push(`unexpected Alembic heads: ${heads.join(', ')}`)
    const digest = indexedAlembicDigest(root)
    if (digest !== catalogue.alembicIndexSha256) errors.push(`Alembic index digest changed: ${digest}`)
    const authSource = readText(path.join(root, 'src', 'auth.js'))
    for (const marker of ['response_type: \'code\'', 'InMemoryWebStorage', '/api/v1/auth/token-check']) {
      if (!authSource.includes(marker)) errors.push(`authentication bootstrap is missing ${marker}`)
    }
    const workflow = readText(path.join(root, '.github', 'workflows', 'migration-foundation.yml'))
    if (!workflow.includes('npm run verify:phase15a:contract')) errors.push('GitHub workflow does not route the Phase 15A verifier')
    const packageSource = JSON.parse(readText(path.join(root, 'package.json')))
    if (packageSource.scripts?.['verify:phase15a:contract'] !== 'node scripts/verify-phase-15a-contract.mjs') {
      errors.push('package script does not expose the Phase 15A verifier')
    }
    const roadmap = readText(path.join(root, 'FEATURES_ROADMAP.md'))
    if (!roadmap.includes('Phase 15 is active') || !roadmap.includes('docs/migration/phase-15/SUBPHASE_PLAN.md')) {
      errors.push('roadmap does not point to the active Phase 15 plan')
    }
  }

  return {
    errors,
    inventory: catalogue.inventory.length,
    clients: catalogue.clientContracts.length,
    routes: catalogue.routeContracts.length,
    fileFlows: catalogue.fileFlows.length,
    gaps: catalogue.knownGaps.length,
    goldenCases: catalogue.goldenCases.length,
    owners: expectedOwners.length,
  }
}

export function inspectPhase15Contract(root = repositoryDirectory) {
  const catalogue = JSON.parse(readText(path.join(root, path.relative(repositoryDirectory, cataloguePath))))
  const documents = {
    plan: readText(path.join(root, path.relative(repositoryDirectory, planPath))),
    inventory: readText(path.join(root, path.relative(repositoryDirectory, inventoryPath))),
    contract: readText(path.join(root, path.relative(repositoryDirectory, contractPath))),
    golden: readText(path.join(root, path.relative(repositoryDirectory, goldenPath))),
  }
  return validatePhase15Catalogue(catalogue, documents, { root, checkRepository: true })
}

function main() {
  const report = inspectPhase15Contract()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 15A contract: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Phase 15A contract verification passed: ${report.inventory} inventory items, `
      + `${report.clients} client contracts, ${report.routes} routes, ${report.fileFlows} file flows, `
      + `${report.gaps} owned gaps, ${report.goldenCases} golden cases, and ${report.owners} later-part owners.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
