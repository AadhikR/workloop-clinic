import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  digestManifest,
  validateRetainedBoundary,
} from './verify-phase-13g-decommission.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const reviewPath = 'docs/migration/phase-13/PART_13H_INDEPENDENT_REVIEW.md'
const cataloguePath = 'docs/migration/phase-13/dependency-catalogue.json'
const targetManifestPath = 'docs/migration/phase-13/PART_13G_TARGET_MANIFEST.json'
const approvalManifestPath = 'docs/migration/phase-13/PART_13G_APPROVAL_MANIFEST.json'
const currentDocuments = [
  'README.md',
  'ARCHITECTURE.md',
  'CLAUDE.md',
  'DIGITALOCEAN_MIGRATION_PLAN.md',
  'FEATURES_ROADMAP.md',
  'MANUAL_TEST_CHECKLIST.md',
  'REMAINING_TESTS.md',
  'backend/README.md',
]
const forbiddenActivePattern = /supabase|@supabase|dist-migration|migration\/src|build:legacy|dev:legacy|preview:legacy/i

function read(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

function readJson(relativePath) {
  return JSON.parse(read(relativePath))
}

function section(source, name) {
  const marker = `## ${name}\n`
  const start = source.indexOf(marker)
  if (start === -1) return ''
  const body = source.slice(start + marker.length)
  const next = body.indexOf('\n## ')
  return next === -1 ? body : body.slice(0, next)
}

export function traceIds(source, sectionName, pattern) {
  return [...section(source, sectionName).matchAll(pattern)].map((match) => match[1])
}

export function alembicHeads(root = repositoryDirectory) {
  const revisions = new Set()
  const predecessors = new Set()
  const directory = path.join(root, 'backend', 'alembic', 'versions')
  for (const name of readdirSync(directory)) {
    if (!name.endsWith('.py')) continue
    const source = readFileSync(path.join(directory, name), 'utf8')
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (!revision) throw new Error(`Missing revision declaration in ${name}`)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
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

function verifyCatalogueClosures(errors, catalogue) {
  const closedDependencies = []
  const closedCases = []
  for (const part of catalogue.allowedOwners) {
    const closure = catalogue.closures?.[part]
    if (!closure || closure.status !== 'completed') {
      errors.push(`${part} has no completed catalogue closure`)
      continue
    }
    for (const id of closure.dependencies ?? []) {
      const dependency = catalogue.dependencies.find((entry) => entry.id === id)
      if (!dependency) errors.push(`${part} closes unknown dependency ${id}`)
      else if (dependency.owner !== part) errors.push(`${part} closes ${id}, owned by ${dependency.owner}`)
      closedDependencies.push(id)
    }
    for (const id of closure.goldenCases ?? []) {
      const goldenCase = catalogue.goldenCases.find((entry) => entry.id === id)
      if (!goldenCase) errors.push(`${part} closes unknown golden case ${id}`)
      else if (goldenCase.owner !== part) errors.push(`${part} closes ${id}, owned by ${goldenCase.owner}`)
      closedCases.push(id)
    }
    for (const evidence of closure.evidence ?? []) {
      if (!evidence.includes('*') && !evidence.includes('**') && !evidence.match(/^[A-Z0-9-]+$/)
        && !readablePath(evidence)) {
        errors.push(`${part} closure evidence does not exist: ${evidence}`)
      }
    }
  }
  addExactSetErrors(errors, closedDependencies, catalogue.dependencies.map((entry) => entry.id), 'catalogue dependency closures')
  addExactSetErrors(errors, closedCases, catalogue.goldenCases.map((entry) => entry.id), 'catalogue golden-case closures')
}

function readablePath(relativePath) {
  try {
    readFileSync(path.join(repositoryDirectory, relativePath))
    return true
  } catch {
    return false
  }
}

function verifyCanonicalRuntime(errors) {
  const packageManifest = readJson('package.json')
  if (packageManifest.scripts.dev !== 'vite'
    || packageManifest.scripts.build !== 'vite build'
    || packageManifest.scripts.preview !== 'vite preview') {
    errors.push('ordinary frontend commands do not select the canonical Vite application')
  }
  const packageText = read('package.json') + read('package-lock.json')
  if (/@supabase/i.test(packageText)) errors.push('frontend package graph contains a retired package')
  for (const relativePath of ['package.json', 'package-lock.json', 'vite.config.js', 'index.html', '.env.example', '.env.test.example']) {
    if (forbiddenActivePattern.test(read(relativePath))) errors.push(`${relativePath} contains a retired active-runtime marker`)
  }
  const sourceDirectory = path.join(repositoryDirectory, 'src')
  const stack = [sourceDirectory]
  while (stack.length > 0) {
    const current = stack.pop()
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const item = path.join(current, entry.name)
      if (entry.isDirectory()) stack.push(item)
      else if (forbiddenActivePattern.test(readFileSync(item, 'utf8'))) {
        errors.push(`${path.relative(repositoryDirectory, item)} contains a retired active-runtime marker`)
      }
    }
  }
  const vite = read('vite.config.js')
  for (const value of ['VITE_API_BASE_URL', 'VITE_OIDC_AUTHORITY', 'VITE_OIDC_CLIENT_ID', 'VITE_OIDC_REDIRECT_URI', 'VITE_OIDC_POST_LOGOUT_REDIRECT_URI', 'VITE_OIDC_AUDIENCE']) {
    if (!vite.includes(`'${value}'`)) errors.push(`vite.config.js omits ${value}`)
  }
  for (const token of ["outDir: 'dist'", "host: '127.0.0.1'", 'port: 5174', 'strictPort: true']) {
    if (!vite.includes(token)) errors.push(`vite.config.js omits ${token}`)
  }
}

function verifyDocumentsAndHistory(errors) {
  for (const relativePath of currentDocuments) {
    if (/supabase/i.test(read(relativePath))) errors.push(`${relativePath} contains a retired runtime instruction`)
  }
  const label = 'Historical record. Do not run or deploy these files.'
  for (const relativePath of [
    'docs/history/legacy-supabase-sql/README.md',
    'docs/history/legacy-feature-list/README.md',
    'backend/HISTORICAL_SOURCE_TERMS.md',
    'docs/migration/HISTORICAL_RECORDS.md',
  ]) {
    if (!read(relativePath).includes(label)) errors.push(`${relativePath} lacks the required history label`)
  }
}

function verifyClosingWorkflow(errors) {
  const workflow = read('.github/workflows/migration-foundation.yml')
  const required = [
    'npm run guard:repository',
    'npm run verify:phase13h:review',
    'npm run verify:phase13f:clean',
    'npm run test:unit',
    'npm run build',
    'docker compose --profile tools run --rm migrate',
    'Verify Phase 13F process guards',
    'sh scripts/verify-phase-3h-logs.sh',
    'node scripts/verify-phase-13f-browser.mjs',
    'docker compose down --volumes',
  ]
  for (const token of required) {
    if (!workflow.includes(token)) errors.push(`closing workflow omits ${token}`)
  }
  if (/down --volumes[^\n]*workloop-clinic_postgres_data/i.test(workflow)) {
    errors.push('closing workflow targets the protected volume for cleanup')
  }
}

function verifyRetainedArchive(errors) {
  const target = readJson(targetManifestPath)
  const approval = readJson(approvalManifestPath)
  errors.push(...validateRetainedBoundary(target, approval).map((error) => `retained archive: ${error}`))
  if (approval.targetManifestSha256 !== digestManifest(target)) errors.push('approval manifest is not bound to the settled target manifest')
  if (target.discovery.externalProject.projectId !== 'dabphibgpamsfoxfhwmu'
    || target.discovery.externalProject.organizationId !== 'otqemcwkpkyhpncmxldm') {
    errors.push('retained archive does not name the settled Workloop project')
  }
  if (target.retention.status !== 'indefinite' || approval.status !== 'retained' || approval.approvals.length !== 0) {
    errors.push('retained archive does not keep every destructive action denied')
  }
  if (!target.cleanup.disposableRestoreContainerRemoved
    || !target.cleanup.encryptedArtifactsRetained
    || target.cleanup.plaintextDownloadCopiesRemoved !== 2
    || target.receipts.length !== 0) {
    errors.push('retained archive cleanup evidence is incomplete')
  }
}

export function inspectPhase13Review() {
  const errors = []
  const catalogue = readJson(cataloguePath)
  const review = read(reviewPath)
  const dependencyIds = traceIds(review, 'Dependency trace', /^\| `(P13-[A-Z]+-\d{3})` \|/gm)
  const goldenCaseIds = traceIds(review, 'Golden-case proof map', /^\| `(13A-GC-\d{3})` \|/gm)
  addExactSetErrors(errors, dependencyIds, catalogue.dependencies.map((entry) => entry.id), 'independent dependency trace')
  addExactSetErrors(errors, goldenCaseIds, catalogue.goldenCases.map((entry) => entry.id), 'independent golden-case trace')
  verifyCatalogueClosures(errors, catalogue)
  verifyCanonicalRuntime(errors)
  verifyDocumentsAndHistory(errors)
  verifyClosingWorkflow(errors)
  verifyRetainedArchive(errors)
  const heads = alembicHeads()
  if (heads.length !== 1 || heads[0] !== 'e8a1c3f5b7d9') errors.push(`unexpected Alembic heads: ${heads.join(', ')}`)
  const contract = read('docs/migration/phase-13/PART_13A_PROMOTION_AND_DECOMMISSION_CONTRACT.md')
  if (!/1\. Stop the 13F disposable proof[\s\S]*2\. Revert the 13E guard[\s\S]*3\. Restore the 13D package[\s\S]*4\. Restore the 13C legacy tree[\s\S]*5\. Restore the 13B command mapping/.test(contract)) {
    errors.push('repository rollback order is incomplete or out of order')
  }
  return {
    errors,
    dependencies: dependencyIds.length,
    goldenCases: goldenCaseIds.length,
    alembicHeads: heads,
  }
}

function main() {
  const report = inspectPhase13Review()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 13H review: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(`Phase 13H independent review passed: ${report.dependencies} dependencies and ${report.goldenCases} golden cases traced with one Alembic head.\n`)
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
