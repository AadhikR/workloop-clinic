import { createHash } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const phaseDirectory = path.join(repositoryDirectory, 'docs', 'migration', 'phase-14')

export const cataloguePath = path.join(phaseDirectory, 'deployment-catalogue.json')
export const inventoryPath = path.join(phaseDirectory, 'PART_14A_DEPLOYMENT_INVENTORY.md')
export const contractPath = path.join(phaseDirectory, 'PART_14A_OPERATIONS_CONTRACT.md')
export const goldenPath = path.join(phaseDirectory, 'PART_14A_GOLDEN_CASES.md')
export const externalFactsPath = path.join(phaseDirectory, 'PART_14A_EXTERNAL_FACTS.md')

const expectedOwners = ['14B', '14C', '14D', '14E', '14F', '14G', '14H']
const expectedRollback = ['14H', '14G', '14F', '14E', '14D', '14C', '14B', '14A']
const factStatuses = new Set(['verified', 'unknown'])

function readText(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function exactIds(source, pattern) {
  return [...source.matchAll(pattern)].map((match) => match[1])
}

function addExactSetErrors(errors, actual, expected, label) {
  const duplicate = actual.filter((value, index) => actual.indexOf(value) !== index)
  if (duplicate.length > 0) {
    errors.push(`${label} contains duplicate IDs: ${[...new Set(duplicate)].join(', ')}`)
  }
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
    const source = readFileSync(path.join(versions, name), 'utf8')
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (!revision) throw new Error(`Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

function indexedAlembicDigest(root = repositoryDirectory) {
  const result = spawnSync('git', ['ls-files', '-s', '-z', 'backend/alembic'], {
    cwd: root,
    encoding: 'buffer',
  })
  if (result.status !== 0) throw new Error(result.stderr.toString('utf8'))
  return createHash('sha256').update(result.stdout).digest('hex')
}

function evidenceTargetExists(value, catalogue, root) {
  const inventoryIds = new Set(catalogue.inventory.map((entry) => entry.id))
  const factIds = new Set(catalogue.externalFacts.map((entry) => entry.id))
  const backupClasses = new Set(catalogue.contract.backupClasses.map((entry) => entry.class))
  if (inventoryIds.has(value) || factIds.has(value) || backupClasses.has(value)) return true
  if (/^https:\/\//.test(value)) return true
  const literal = value.split('/**')[0]
  return existsSync(path.join(root, literal))
}

export function validatePhase14Catalogue(
  catalogue,
  documents,
  { root = repositoryDirectory, checkRepository = true } = {},
) {
  const errors = []
  if (catalogue.schemaVersion !== 1 || catalogue.phase !== '14' || catalogue.part !== '14A') {
    errors.push('catalogue identity or schema version is invalid')
  }
  if (JSON.stringify(catalogue.allowedOwners) !== JSON.stringify(expectedOwners)) {
    errors.push('allowed owners must be exactly 14B through 14H')
  }
  if (JSON.stringify(catalogue.rollbackOrder) !== JSON.stringify(expectedRollback)) {
    errors.push('phase rollback order is not the exact reverse part order')
  }

  const inventoryIds = catalogue.inventory.map((entry) => entry.id)
  const goldenIds = catalogue.goldenCases.map((entry) => entry.id)
  const factIds = catalogue.externalFacts.map((entry) => entry.id)
  addExactSetErrors(errors, inventoryIds, [...new Set(inventoryIds)], 'inventory')
  addExactSetErrors(errors, goldenIds, [...new Set(goldenIds)], 'golden cases')
  addExactSetErrors(errors, factIds, [...new Set(factIds)], 'external facts')

  const actions = new Set(catalogue.allowedActions)
  const evidenceClasses = new Set(catalogue.allowedEvidenceClasses)
  for (const entry of catalogue.inventory) {
    if (!/^P14-[A-Z]+-\d{3}$/.test(entry.id)) errors.push(`${entry.id} has an invalid inventory ID`)
    if (!expectedOwners.includes(entry.owner)) errors.push(`${entry.id} has invalid owner ${entry.owner}`)
    if (!actions.has(entry.action)) errors.push(`${entry.id} has invalid action ${entry.action}`)
    for (const key of ['category', 'item', 'currentState']) {
      if (typeof entry[key] !== 'string' || entry[key].trim() === '') errors.push(`${entry.id} has no ${key}`)
    }
    if (!Array.isArray(entry.evidenceClasses) || entry.evidenceClasses.length === 0) {
      errors.push(`${entry.id} has no evidence class`)
    }
    for (const evidenceClass of entry.evidenceClasses ?? []) {
      if (!evidenceClasses.has(evidenceClass)) errors.push(`${entry.id} has invalid evidence class ${evidenceClass}`)
    }
    if (!Array.isArray(entry.evidence) || entry.evidence.length === 0) errors.push(`${entry.id} has no evidence target`)
    if (checkRepository) {
      for (const value of entry.evidence ?? []) {
        if (!evidenceTargetExists(value, catalogue, root)) errors.push(`${entry.id} has unresolved evidence ${value}`)
      }
    }
  }
  for (const owner of expectedOwners) {
    if (!catalogue.inventory.some((entry) => entry.owner === owner)) errors.push(`${owner} owns no inventory item`)
    if (!catalogue.goldenCases.some((entry) => entry.owner === owner)) errors.push(`${owner} owns no golden case`)
  }

  for (const entry of catalogue.goldenCases) {
    if (!/^14A-GC-\d{3}$/.test(entry.id)) errors.push(`${entry.id} has an invalid golden-case ID`)
    if (!expectedOwners.includes(entry.owner)) errors.push(`${entry.id} has invalid owner ${entry.owner}`)
    if (!entry.area || !entry.expectation) errors.push(`${entry.id} is incomplete`)
    for (const evidenceClass of entry.evidenceClasses ?? []) {
      if (!evidenceClasses.has(evidenceClass)) errors.push(`${entry.id} has invalid evidence class ${evidenceClass}`)
    }
  }

  for (const fact of catalogue.externalFacts) {
    if (!/^EXT-\d{3}$/.test(fact.id)) errors.push(`${fact.id} has an invalid external-fact ID`)
    if (!factStatuses.has(fact.status)) errors.push(`${fact.id} has invalid status ${fact.status}`)
    if (!fact.fact || !fact.source || fact.checkedOn !== '2026-09-27') errors.push(`${fact.id} is incomplete`)
  }

  const components = catalogue.contract.components.map((entry) => entry.name)
  addExactSetErrors(
    errors,
    components,
    ['database-migrate', 'api', 'keycloak', 'web', 'expiry', 'file-scanner', 'storage-reconciler'],
    'component contract',
  )
  const monthlyTotal = catalogue.contract.costBoundary.monthlyLineItems.reduce(
    (sum, entry) => sum + entry.quantity * entry.unitMonthly,
    0,
  )
  if (Number(monthlyTotal.toFixed(2)) !== catalogue.contract.costBoundary.estimatedFixedMonthly) {
    errors.push('fixed monthly estimate does not equal its line items')
  }
  if (catalogue.contract.costBoundary.configurationCeilingMonthly !== 70) {
    errors.push('configuration ceiling must remain USD 70')
  }
  if (catalogue.contract.artifactIdentity.schemaHead !== catalogue.alembicHead) {
    errors.push('artifact schema head differs from catalogue head')
  }

  addExactSetErrors(
    errors,
    exactIds(documents.inventory, /^\| `(P14-[A-Z]+-\d{3})` \|/gm),
    inventoryIds,
    'prose inventory',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.golden, /^\| `(14A-GC-\d{3})` \|/gm),
    goldenIds,
    'prose golden cases',
  )
  addExactSetErrors(
    errors,
    exactIds(documents.external, /^\| `(EXT-\d{3})` \|/gm),
    factIds,
    'external-fact record',
  )

  const normalizedContract = documents.contract.replace(/\s+/g, ' ')
  for (const token of [
    'synthetic identities, rows, and files only',
    'fra1-default',
    'provider-managed App Platform default address',
    'e8a1c3f5b7d9',
    'USD 65.15',
    'USD 70',
    'maintenance mode',
    'Automatic branch deployment is disabled',
    'workloop-clinic_postgres_data',
    'Never downgrade the schema automatically',
  ]) {
    if (!normalizedContract.includes(token)) errors.push(`operations contract is missing ${token}`)
  }

  if (checkRepository) {
    const heads = alembicHeads(root)
    if (heads.length !== 1 || heads[0] !== catalogue.alembicHead) {
      errors.push(`unexpected Alembic heads: ${heads.join(', ')}`)
    }
    const sourceChecks = new Map([
      ['backend/app/db/cloud_bootstrap.py', ['workloop_migration', 'workloop_runtime', 'workloop_expiry_processing', 'workloop_file_scanner', 'workloop_storage_reconciler', 'keycloak']],
      ['backend/app/storage/scanner_worker.py', ['RETRY_DELAYS', 'LIMIT 1', "interval '15 minutes'", 'attempt_count == 8']],
      ['backend/app/storage/reconciler.py', ['RETRY_DELAYS', 'LIMIT 1', "interval '15 minutes'", 'attempt_count == 8']],
      ['infra/digitalocean/main.tf', ['deploy_on_push = false', 'maintenance', 'workloop-clinic-dev-db']],
      ['keycloak/cloud/workloop-dev-realm.json', ['workloop-migration-web', 'workloop-api']],
    ])
    for (const [relativePath, markers] of sourceChecks) {
      const source = readText(path.join(root, relativePath))
      for (const marker of markers) {
        if (!source.includes(marker)) errors.push(`${relativePath} is missing ${marker}`)
      }
    }
    if (!existsSync(path.join(root, 'backend', 'alembic', 'versions', `${catalogue.alembicHead}_extend_phase12g_output_audit.py`))) {
      errors.push('catalogued Alembic head file is missing')
    }
    const alembicDigest = indexedAlembicDigest(root)
    if (alembicDigest !== catalogue.alembicIndexSha256) {
      errors.push(`Alembic index digest changed: ${alembicDigest}`)
    }
  }

  return {
    errors,
    inventory: catalogue.inventory.length,
    goldenCases: catalogue.goldenCases.length,
    externalFacts: catalogue.externalFacts.length,
    owners: expectedOwners.length,
  }
}

export function inspectPhase14Contract(root = repositoryDirectory) {
  const catalogue = JSON.parse(readText(path.join(root, path.relative(repositoryDirectory, cataloguePath))))
  const documents = {
    inventory: readText(path.join(root, path.relative(repositoryDirectory, inventoryPath))),
    contract: readText(path.join(root, path.relative(repositoryDirectory, contractPath))),
    golden: readText(path.join(root, path.relative(repositoryDirectory, goldenPath))),
    external: readText(path.join(root, path.relative(repositoryDirectory, externalFactsPath))),
  }
  return validatePhase14Catalogue(catalogue, documents, { root, checkRepository: true })
}

function main() {
  const report = inspectPhase14Contract()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14A contract: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Phase 14A contract verification passed: ${report.inventory} inventory items, `
      + `${report.goldenCases} golden cases, ${report.externalFacts} external facts, `
      + `and ${report.owners} later-part owners.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
