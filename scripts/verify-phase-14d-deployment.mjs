import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const relativeFiles = {
  main: 'infra/digitalocean/main.tf',
  variables: 'infra/digitalocean/variables.tf',
  outputs: 'infra/digitalocean/outputs.tf',
  readme: 'infra/digitalocean/README.md',
  releaseSchema: 'infra/digitalocean/release-manifest.schema.json',
  releaseExample: 'infra/digitalocean/release-manifest.example.json',
  appSpec: 'infra/digitalocean/app-spec.contract.json',
  releaseTool: 'scripts/phase-14d-release-manifest.mjs',
  frontendVerifier: 'scripts/verify-phase-14d-frontend.mjs',
  cloudMigrate: 'backend/app/db/cloud_migrate.py',
  api: 'backend/app/main.py',
  expiry: 'backend/app/expiry_command.py',
  scanner: 'backend/app/storage/scanner_worker.py',
  reconciler: 'backend/app/storage/reconciler.py',
  workerControl: 'backend/app/storage/worker_control.py',
  backendDockerfile: 'backend/Dockerfile',
  keycloakDockerfile: 'keycloak/Dockerfile',
  workflow: '.github/workflows/migration-foundation.yml',
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
}

const components = [
  ['job', 'database-migrate'],
  ['service', 'api'],
  ['service', 'keycloak'],
  ['static_site', 'web'],
  ['job', 'expiry'],
  ['worker', 'file-scanner'],
  ['worker', 'storage-reconciler'],
]

function readText(root, relativePath) {
  const absolutePath = path.join(root, relativePath)
  return existsSync(absolutePath) ? readFileSync(absolutePath, 'utf8').replaceAll('\r\n', '\n') : ''
}

export function readPhase14DSources(root = repositoryDirectory) {
  return Object.fromEntries(
    Object.entries(relativeFiles).map(([key, relativePath]) => [key, readText(root, relativePath)]),
  )
}

function requireText(errors, source, value, label) {
  if (!source.includes(value)) errors.push(`missing ${label}`)
}

function rejectText(errors, source, value, label) {
  if (source.includes(value)) errors.push(`forbidden ${label}`)
}

function extractBlock(source, marker) {
  const start = source.indexOf(marker)
  if (start === -1) return ''
  const open = source.indexOf('{', start)
  if (open === -1) return ''
  let depth = 0
  for (let index = open; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}') depth -= 1
    if (depth === 0) return source.slice(start, index + 1)
  }
  return ''
}

function componentBlock(source, kind, name) {
  let offset = 0
  while (offset < source.length) {
    const start = source.indexOf(`    ${kind} {`, offset)
    if (start === -1) return ''
    const block = extractBlock(source.slice(start), `${kind} {`)
    if (new RegExp(`name\\s*=\\s*"${name}"`).test(block)) return block
    offset = start + 1
  }
  return ''
}

function parseJson(errors, source, label) {
  try {
    return JSON.parse(source)
  } catch {
    errors.push(`missing or invalid ${label}`)
    return {}
  }
}

export function validatePhase14DDeployment(sources) {
  const errors = []
  const catalogue = parseJson(errors, sources.catalogue, 'deployment catalogue')
  const schema = parseJson(errors, sources.releaseSchema, 'release manifest schema')
  const example = parseJson(errors, sources.releaseExample, 'release manifest example')
  const appSpec = parseJson(errors, sources.appSpec, 'app spec contract')

  const ownedInventory = (catalogue.inventory ?? []).filter((entry) => entry.owner === '14D').map((entry) => entry.id)
  const ownedGolden = (catalogue.goldenCases ?? []).filter((entry) => entry.owner === '14D').map((entry) => entry.id)
  const expectedInventory = Array.from({ length: 10 }, (_, index) => `P14-DEP-${String(index + 1).padStart(3, '0')}`)
  const expectedGolden = Array.from({ length: 8 }, (_, index) => `14A-GC-${String(index + 13).padStart(3, '0')}`)
  if (JSON.stringify(ownedInventory) !== JSON.stringify(expectedInventory)) errors.push('14D inventory ownership changed')
  if (JSON.stringify(ownedGolden) !== JSON.stringify(expectedGolden)) errors.push('14D golden-case ownership changed')

  for (const field of [
    'releaseId',
    'gitCommit',
    'backendImage',
    'keycloakImage',
    'frontendSha256',
    'frontendRootSha256',
    'dependencyLockSha256',
    'terraformSha256',
    'appSpecSha256',
    'alembicHead',
  ]) {
    if (!(schema.required ?? []).includes(field)) errors.push(`release schema must require ${field}`)
  }
  requireText(errors, sources.releaseSchema, '^[0-9a-f]{40}$', 'full commit pattern')
  requireText(errors, sources.releaseSchema, '^sha256:[0-9a-f]{64}$', 'SHA-256 pattern')
  if (example.deployable !== false) errors.push('committed release example must stay non-deployable')
  if (example.alembicHead !== 'e8a1c3f5b7d9') errors.push('release example must bind the approved Alembic head')
  if (JSON.stringify((appSpec.components ?? []).map((entry) => entry.name))
    !== JSON.stringify(components.map(([, name]) => name))) errors.push('app spec must name the seven components exactly')

  for (const marker of [
    'validateReleaseManifest',
    'dependencyLockSha256',
    'terraformSha256',
    'appSpecSha256',
    'frontendSha256',
  ]) requireText(errors, sources.releaseTool, marker, `release tool ${marker}`)
  requireText(errors, sources.frontendVerifier, 'WORKLOOP_FRONTEND_SHA256', 'frontend digest input')
  requireText(errors, sources.frontendVerifier, 'dist', 'frontend dist digest')

  requireText(errors, sources.variables, 'variable "release_manifest"', 'release manifest Terraform input')
  requireText(errors, sources.variables, 'default   = null', 'absent release manifest default')
  requireText(errors, sources.main, 'release_manifest_complete', 'release manifest completeness guard')
  requireText(errors, sources.main, 'release_manifest_compatible', 'release compatibility guard')
  requireText(errors, sources.main, 'local.release_manifest_complete', 'enabled-plan manifest gate')
  requireText(errors, sources.main, 'local.release_manifest_compatible', 'promotion compatibility gate')
  requireText(errors, sources.main, '!var.release_promoted || length(var.expiry_scopes) > 0', 'promotion expiry-scope gate')
  requireText(errors, sources.main, 'worker_processing_enabled = var.release_promoted', 'worker promotion gate')
  requireText(errors, sources.main, 'expiry_processing_enabled = local.worker_processing_enabled', 'expiry scope gate')
  requireText(errors, sources.outputs, 'output "release_identity"', 'safe release identity output')

  const blocks = new Map(components.map(([kind, name]) => [name, componentBlock(sources.main, kind, name)]))
  for (const [name, block] of blocks) if (!block) errors.push(`missing component block ${name}`)
  for (const name of ['database-migrate', 'api', 'expiry', 'file-scanner', 'storage-reconciler']) {
    const block = blocks.get(name) ?? ''
    requireText(errors, block, 'image {', `${name} immutable image source`)
    requireText(errors, block, 'digest        = var.release_manifest.backend_image.digest', `${name} backend digest`)
    rejectText(errors, block, 'github {', `${name} source rebuild`)
    rejectText(errors, block, 'tag', `${name} mutable tag`)
  }
  const keycloak = blocks.get('keycloak') ?? ''
  requireText(errors, keycloak, 'image {', 'Keycloak immutable image source')
  requireText(errors, keycloak, 'digest        = var.release_manifest.keycloak_image.digest', 'Keycloak digest')
  rejectText(errors, keycloak, 'github {', 'Keycloak source rebuild')
  rejectText(errors, keycloak, 'tag', 'Keycloak mutable tag')
  const web = blocks.get('web') ?? ''
  requireText(errors, sources.main, 'github_branch         = "migration/fastapi-keycloak"', 'web reviewed branch')
  requireText(errors, web, 'branch         = local.github_branch', 'web reviewed branch source')
  requireText(errors, web, 'deploy_on_push = false', 'web automatic deployment block')
  requireText(errors, web, 'verify-phase-14d-frontend.mjs', 'web output digest check')
  rejectText(errors, sources.main, 'deploy_on_push = true', 'automatic deployment')
  for (const marker of ['digitalocean/action-doctl', 'apps create-deployment', 'terraform apply']) {
    rejectText(errors, sources.workflow, marker, `workflow deployment command ${marker}`)
  }

  const migration = blocks.get('database-migrate') ?? ''
  requireText(errors, migration, 'kind               = "PRE_DEPLOY"', 'pre-deploy migration kind')
  requireText(errors, migration, 'WORKLOOP_ALEMBIC_HEAD', 'migration manifest head')
  for (const marker of ['EXPECTED_ALEMBIC_HEAD = "e8a1c3f5b7d9"', 'verify_schema_head', 'already_current']) {
    requireText(errors, sources.cloudMigrate, marker, `migration ${marker}`)
  }

  const api = blocks.get('api') ?? ''
  for (const marker of ['http_path             = "/health"', 'port                  = 8000', 'timeout_seconds       = 5']) {
    requireText(errors, api, marker, `API health rule ${marker}`)
  }
  requireText(errors, sources.api, 'HealthResponse(status="ok", database="ok")', 'API health payload')
  for (const marker of ['http_path             = "/management/health/ready"', 'port                  = 9000']) {
    requireText(errors, keycloak, marker, `Keycloak health rule ${marker}`)
  }
  requireText(errors, sources.frontendVerifier, 'response.status === 200', 'web HTTP 200 check')

  const expiry = blocks.get('expiry') ?? ''
  requireText(errors, expiry, 'kind               = "UNSPECIFIED"', 'manual expiry job kind')
  requireText(
    errors,
    expiry,
    'if [ \\"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\\" = false ]; then exit 0',
    'disabled expiry deployment exit',
  )
  requireText(
    errors,
    expiry,
    'if [ \\"$WORKLOOP_EXPIRY_PROCESSING_ENABLED\\" != true ]; then exit 1',
    'invalid expiry deployment gate',
  )
  requireText(errors, expiry, 'WORKLOOP_EXPIRY_SCOPES_JSON', 'approved expiry scopes')
  requireText(errors, expiry, 'local.expiry_processing_enabled', 'expiry processing gate')
  requireText(errors, sources.expiry, 'pg_advisory_xact_lock', 'expiry advisory lock')
  requireText(errors, sources.expiry, 'business_date', 'expiry business-date record')
  requireText(errors, sources.expiry, 'ZoneInfo("Asia/Dubai")', 'expiry Dubai business date')

  for (const [name, source] of [['file-scanner', sources.scanner], ['storage-reconciler', sources.reconciler]]) {
    const block = blocks.get(name) ?? ''
    requireText(errors, block, 'instance_count     = 1', `${name} single instance`)
    requireText(errors, block, 'grace_period_seconds = 120', `${name} termination window`)
    requireText(errors, block, 'WORKLOOP_WORKER_PROCESSING_ENABLED', `${name} maintenance gate`)
    requireText(errors, block, 'local.worker_processing_enabled', `${name} promotion gate`)
    requireText(errors, source, 'LIMIT 1', `${name} single-row claim`)
    requireText(errors, source, "interval '15 minutes'", `${name} 15-minute lease`)
    requireText(errors, source, 'attempt_count < 8', `${name} eight-attempt limit`)
    requireText(errors, source, 'RETRY_DELAYS', `${name} bounded retries`)
    requireText(errors, source, 'release_', `${name} shutdown lease release`)
    requireText(errors, source, 'run_claim_loop', `${name} controlled worker loop`)
  }
  const scanner = blocks.get('file-scanner') ?? ''
  requireText(errors, scanner, 'key   = "MALWARE_SCANNER_BACKEND"', 'file-scanner malware backend')
  requireText(errors, scanner, 'value = "synthetic"', 'file-scanner synthetic malware backend')
  for (const marker of [
    'IDLE_POLL_SECONDS = 5',
    'HEARTBEAT_SECONDS = 60',
    'DRAIN_SECONDS = 105',
    'processing_enabled',
    'stop_event',
    'release_claim',
  ]) requireText(errors, sources.workerControl, marker, `worker control ${marker}`)

  for (const dockerfile of [sources.backendDockerfile, sources.keycloakDockerfile]) {
    requireText(errors, dockerfile, '@sha256:', 'digest-pinned base image')
  }
  requireText(errors, sources.readme, 'release-manifest.example.json', 'release manifest operator instructions')
  requireText(errors, sources.readme, 'Automatic branch deployment stays disabled', 'automatic deployment policy')

  return {
    errors,
    inventory: ownedInventory.length,
    goldenCases: ownedGolden.length,
    components: blocks.size,
  }
}

export function inspectPhase14DDeployment(root = repositoryDirectory) {
  return validatePhase14DDeployment(readPhase14DSources(root))
}

function main() {
  const report = inspectPhase14DDeployment()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14D deployment: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Phase 14D deployment verification passed: ${report.inventory} inventory items, `
      + `${report.goldenCases} golden cases, and ${report.components} components.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
