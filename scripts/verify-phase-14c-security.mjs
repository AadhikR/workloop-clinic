import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const relativeFiles = {
  main: 'infra/digitalocean/main.tf',
  variables: 'infra/digitalocean/variables.tf',
  outputs: 'infra/digitalocean/outputs.tf',
  example: 'infra/digitalocean/shared-development.tfvars.example',
  readme: 'infra/digitalocean/README.md',
  bootstrap: 'backend/app/db/cloud_bootstrap.py',
  cloudMigrate: 'backend/app/db/cloud_migrate.py',
  postgresInit: 'infra/local/postgres/init/01-create-databases.sh',
  hardeningSql: 'scripts/harden-phase-14c-extension.sql',
  databaseWrapper: 'scripts/verify-phase-14c-database.sh',
  rlsVerifier: 'scripts/verify-phase-5e-rls.py',
  realm: 'keycloak/cloud/workloop-dev-realm.json',
  mfa: 'keycloak/cloud/arm-admin-totp.sh',
  access: 'docs/migration/phase-14/PART_14C_ACCESS_CONTROL.md',
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
}

const databaseRoles = [
  'workloop_migration',
  'workloop_runtime',
  'workloop_expiry_processing',
  'workloop_file_scanner',
  'workloop_storage_reconciler',
  'keycloak',
]

const objectKeys = new Map([
  ['api', 'readwrite'],
  ['file_scanner', 'read'],
  ['storage_reconciler', 'readwrite'],
  ['object_backup', 'read'],
])

const operatorRoles = [
  'infrastructure_custodian',
  'security_custodian',
  'application_operator',
  'incident_operator',
  'release_reviewer',
]

const publicFrontendSettings = [
  'VITE_API_BASE_URL',
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
  'VITE_OIDC_POST_LOGOUT_REDIRECT_URI',
  'VITE_OIDC_AUDIENCE',
]

function readText(root, relativePath) {
  return readFileSync(path.join(root, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

export function readPhase14CSources(root = repositoryDirectory) {
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
  let searchFrom = 0
  while (searchFrom < source.length) {
    const start = source.indexOf(`    ${kind} {`, searchFrom)
    if (start === -1) return ''
    const block = extractBlock(source.slice(start), `${kind} {`)
    if (new RegExp(`name\\s*=\\s*"${name}"`).test(block)) return block
    searchFrom = start + 1
  }
  return ''
}

function extractBlocks(source, marker) {
  const blocks = []
  let searchFrom = 0
  while (searchFrom < source.length) {
    const start = source.indexOf(marker, searchFrom)
    if (start === -1) break
    const block = extractBlock(source.slice(start), marker)
    if (!block) break
    blocks.push(block)
    searchFrom = start + block.length
  }
  return blocks
}

function environmentKeys(block) {
  return extractBlocks(block, 'env {')
    .map((value) => value.match(/key\s*=\s*"([A-Z0-9_]+)"/)?.[1])
    .filter((value) => value !== undefined)
}

function secretEnvironmentKeys(block) {
  return extractBlocks(block, 'env {')
    .filter((value) => /type\s*=\s*"SECRET"/.test(value))
    .map((value) => value.match(/key\s*=\s*"([A-Z0-9_]+)"/)?.[1])
    .filter((value) => value !== undefined)
    .sort()
}

function requireSecretRoute(errors, block, key, component) {
  const envBlocks = extractBlocks(block, 'env {')
  const route = envBlocks.find((value) => new RegExp(`key\\s*=\\s*"${key}"`).test(value))
  if (!route || !/scope\s*=\s*"RUN_TIME"/.test(route) || !/type\s*=\s*"SECRET"/.test(route)) {
    errors.push(`${component} must own encrypted runtime setting ${key}`)
  }
}

export function validatePhase14CSecurity(sources) {
  const errors = []
  const {
    main,
    variables,
    outputs,
    example,
    readme,
    bootstrap,
    cloudMigrate,
    postgresInit,
    hardeningSql,
    databaseWrapper,
    rlsVerifier,
    realm,
    mfa,
    access,
  } = sources
  const normalizedBootstrap = bootstrap.replace(/"\s*"/g, '')
  const catalogue = JSON.parse(sources.catalogue)

  const ownedInventory = catalogue.inventory.filter((entry) => entry.owner === '14C').map((entry) => entry.id)
  const ownedGolden = catalogue.goldenCases.filter((entry) => entry.owner === '14C').map((entry) => entry.id)
  const expectedInventory = Array.from({ length: 9 }, (_, index) => `P14-SEC-${String(index + 1).padStart(3, '0')}`)
  const expectedGolden = Array.from({ length: 6 }, (_, index) => `14A-GC-${String(index + 7).padStart(3, '0')}`)
  if (JSON.stringify(ownedInventory) !== JSON.stringify(expectedInventory)) errors.push('14C inventory ownership changed')
  if (JSON.stringify(ownedGolden) !== JSON.stringify(expectedGolden)) errors.push('14C golden-case ownership changed')

  for (const role of databaseRoles) {
    const resource = extractBlock(main, `resource "digitalocean_database_user" "${role}"`)
    if (!resource) {
      errors.push(`missing database identity ${role}`)
      continue
    }
    requireText(errors, resource, 'count      = local.enabled ? 1 : 0', `${role} disabled-plan guard`)
    requireText(errors, resource, `name       = "${role}"`, `${role} exact name`)
    requireText(errors, resource, 'cluster_id = digitalocean_database_cluster.shared[0].id', `${role} cluster binding`)
  }
  requireText(
    errors,
    rlsVerifier,
    '("workloop_runtime", False, False, False, False, True, False, False)',
    'historical runtime NOINHERIT expectation',
  )
  for (const role of databaseRoles) {
    requireText(errors, bootstrap, `DatabaseRole("${role}", inherit=False)`, `${role} NOINHERIT bootstrap`)
    if (!new RegExp(`CREATE ROLE ${role} LOGIN[^\\n]*NOINHERIT`).test(postgresInit)) {
      errors.push(`${role} local role must use NOINHERIT`)
    }
  }
  for (const value of [
    'REVOKE ALL ON DATABASE {} FROM PUBLIC',
    'REVOKE ALL ON SCHEMA public FROM PUBLIC',
    'ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC',
    'ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public REVOKE ALL ON SEQUENCES FROM PUBLIC',
    'ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
  ]) requireText(errors, normalizedBootstrap, value, `cloud grant control ${value}`)
  requireText(errors, postgresInit, 'ALTER DEFAULT PRIVILEGES FOR ROLE workloop_migration', 'local application default privileges')
  requireText(errors, postgresInit, 'ALTER DEFAULT PRIVILEGES FOR ROLE keycloak', 'local Keycloak default privileges')
  requireText(errors, bootstrap, "extension.extname = 'btree_gist'", 'cloud extension function scope')
  requireText(errors, bootstrap, 'ALTER FUNCTION %s OWNER TO workloop_migration', 'cloud extension function ownership')
  requireText(errors, bootstrap, 'REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', 'cloud extension PUBLIC revocation')
  rejectText(errors, bootstrap, 'CREATE EXTENSION IF NOT EXISTS btree_gist', 'administrator-owned cloud extension')
  requireText(
    errors,
    cloudMigrate,
    'upgrade_schema()\n    cloud_bootstrap.harden_migrated_schema(workloop_admin_url())',
    'cloud post-migration hardening',
  )
  requireText(
    errors,
    postgresInit,
    'SET ROLE workloop_migration;\nCREATE EXTENSION IF NOT EXISTS btree_gist;\nRESET ROLE;',
    'local extension migration ownership',
  )
  requireText(errors, postgresInit, "extension.extname = 'btree_gist'", 'local extension function scope')
  requireText(errors, postgresInit, 'ALTER FUNCTION %s OWNER TO workloop_migration', 'local extension function ownership')
  requireText(errors, postgresInit, 'REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', 'local extension PUBLIC revocation')
  requireText(errors, hardeningSql, 'ALTER FUNCTION %s OWNER TO workloop_migration', 'post-downgrade extension ownership')
  requireText(errors, hardeningSql, 'REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', 'post-downgrade PUBLIC revocation')
  requireText(
    errors,
    databaseWrapper,
    'harden-phase-14c-extension.sql',
    'database proof post-migration hardening',
  )

  for (const [name, permission] of objectKeys) {
    const resource = extractBlock(main, `resource "digitalocean_spaces_key" "${name}"`)
    if (!resource) {
      errors.push(`missing object identity ${name}`)
      continue
    }
    requireText(errors, resource, 'count = local.enabled ? 1 : 0', `${name} disabled-plan guard`)
    requireText(errors, resource, `name  = "workloop-clinic-dev-${name.replaceAll('_', '-')}"`, `${name} exact object identity name`)
    requireText(errors, resource, 'bucket     = digitalocean_spaces_bucket.shared[0].name', `${name} bucket scope`)
    requireText(errors, resource, `permission = "${permission}"`, `${name} ${permission} grant`)
    rejectText(errors, resource, 'fullaccess', `${name} full bucket-account access`)
  }

  const components = new Map([
    ['database-migrate', componentBlock(main, 'job', 'database-migrate')],
    ['api', componentBlock(main, 'service', 'api')],
    ['keycloak', componentBlock(main, 'service', 'keycloak')],
    ['web', componentBlock(main, 'static_site', 'web')],
    ['expiry', componentBlock(main, 'job', 'expiry')],
    ['file-scanner', componentBlock(main, 'worker', 'file-scanner')],
    ['storage-reconciler', componentBlock(main, 'worker', 'storage-reconciler')],
  ])
  for (const [name, block] of components) if (!block) errors.push(`missing component block ${name}`)

  for (const key of ['CLOUD_ADMIN_WORKLOOP_DATABASE_URL', 'CLOUD_ADMIN_KEYCLOAK_DATABASE_URL', 'MIGRATION_DATABASE_URL']) {
    requireSecretRoute(errors, components.get('database-migrate') ?? '', key, 'database-migrate')
  }
  for (const key of ['DATABASE_URL', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY', 'STORAGE_SIGNING_KEY', 'ATTACHMENT_OBJECT_KEY_HMAC_KEY', 'CURSOR_SIGNING_KEY', 'IDEMPOTENCY_RECOVERY_CURRENT_KEY', 'IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS']) {
    requireSecretRoute(errors, components.get('api') ?? '', key, 'api')
  }
  requireSecretRoute(errors, components.get('keycloak') ?? '', 'KC_DB_PASSWORD', 'keycloak')
  requireSecretRoute(errors, components.get('expiry') ?? '', 'EXPIRY_DATABASE_URL', 'expiry')
  for (const key of ['DATABASE_URL', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY', 'MALWARE_SCANNER_SIGNING_KEY']) {
    requireSecretRoute(errors, components.get('file-scanner') ?? '', key, 'file-scanner')
  }
  for (const key of ['DATABASE_URL', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY']) {
    requireSecretRoute(errors, components.get('storage-reconciler') ?? '', key, 'storage-reconciler')
  }

  const exactSecretRoutes = new Map([
    ['database-migrate', ['CLOUD_ADMIN_KEYCLOAK_DATABASE_URL', 'CLOUD_ADMIN_WORKLOOP_DATABASE_URL', 'MIGRATION_DATABASE_URL']],
    ['api', ['ATTACHMENT_OBJECT_KEY_HMAC_KEY', 'CURSOR_SIGNING_KEY', 'DATABASE_URL', 'IDEMPOTENCY_RECOVERY_CURRENT_KEY', 'IDEMPOTENCY_RECOVERY_PREVIOUS_KEYS', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY', 'STORAGE_SIGNING_KEY']],
    ['keycloak', ['KC_DB_PASSWORD']],
    ['web', []],
    ['expiry', ['EXPIRY_DATABASE_URL']],
    ['file-scanner', ['DATABASE_URL', 'MALWARE_SCANNER_SIGNING_KEY', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY']],
    ['storage-reconciler', ['DATABASE_URL', 'SPACES_ACCESS_KEY', 'SPACES_SECRET_KEY']],
  ])
  for (const [component, expected] of exactSecretRoutes) {
    const actual = secretEnvironmentKeys(components.get(component) ?? '')
    if (JSON.stringify(actual) !== JSON.stringify([...expected].sort())) {
      errors.push(`${component} encrypted runtime settings are not exact`)
    }
  }
  for (const [component, value, label] of [
    ['database-migrate', '$${workloop-migration.DATABASE_PRIVATE_URL}', 'migration database URL'],
    ['api', '$${workloop-runtime.DATABASE_PRIVATE_URL}', 'runtime database URL'],
    ['expiry', '$${workloop-expiry.DATABASE_PRIVATE_URL}', 'expiry database URL'],
    ['file-scanner', '$${workloop-file-scanner.DATABASE_PRIVATE_URL}', 'scanner database URL'],
    ['storage-reconciler', '$${workloop-storage-reconciler.DATABASE_PRIVATE_URL}', 'reconciler database URL'],
    ['api', 'digitalocean_spaces_key.api[0].secret_key', 'API object secret'],
    ['file-scanner', 'digitalocean_spaces_key.file_scanner[0].secret_key', 'scanner object secret'],
    ['storage-reconciler', 'digitalocean_spaces_key.storage_reconciler[0].secret_key', 'reconciler object secret'],
  ]) requireText(errors, components.get(component) ?? '', value, label)

  const web = components.get('web') ?? ''
  const webKeys = environmentKeys(web).sort()
  if (JSON.stringify(webKeys) !== JSON.stringify([...publicFrontendSettings].sort())) {
    errors.push('web build must receive exactly six public settings')
  }
  if (/type\s*=\s*"SECRET"/.test(web)) errors.push('secret in web build')
  rejectText(errors, realm, 'WORKLOOP_SYNTHETIC_USER_PASSWORD', 'synthetic password realm injection')
  const realmDocument = JSON.parse(realm)
  if ((realmDocument.users ?? []).length !== 0) errors.push('cloud realm must not import a synthetic password user')

  requireText(errors, variables, 'variable "operator_access"', 'operator access input')
  requireText(errors, variables, 'variable "runtime_secrets"', 'runtime secret input')
  requireText(errors, variables, 'sensitive = true', 'sensitive runtime secret input')
  requireText(errors, main, 'var.provisioning_authorized && local.approval_complete && local.operator_access_complete && local.runtime_secrets_complete', 'complete enabled-plan guard')
  for (const role of operatorRoles) {
    requireText(errors, variables, `${role} = object({`, `${role} operator record`)
    requireText(errors, main, `try(var.operator_access.${role}.primary_name, "")`, `${role} primary guard`)
    requireText(errors, main, `try(var.operator_access.${role}.primary_account_reference, "")`, `${role} primary least-privilege account guard`)
    requireText(errors, main, `try(var.operator_access.${role}.backup_name, "")`, `${role} backup guard`)
    requireText(errors, main, `try(var.operator_access.${role}.backup_account_reference, "")`, `${role} backup least-privilege account guard`)
    requireText(errors, main, `try(var.operator_access.${role}.primary_mfa, false)`, `${role} primary MFA guard`)
    requireText(errors, main, `try(var.operator_access.${role}.backup_mfa, false)`, `${role} backup MFA guard`)
  }
  if (!/operator_access\s*=\s*null/.test(example)) errors.push('missing fail-closed missing operator example')
  if (!/runtime_secrets\s*=\s*null/.test(example)) errors.push('missing absent credential example')

  for (const outputName of ['database_identity_names', 'object_identity_names', 'operator_access_ready']) {
    requireText(errors, outputs, `output "${outputName}"`, `safe output ${outputName}`)
  }
  const secretOutputPattern = /output\s+"[^"]+"[\s\S]*?(password|secret_key|access_key|database_url|token|private_key)/i
  if (secretOutputPattern.test(outputs)) errors.push('secret-bearing output is forbidden')

  for (const value of [
    'Delete the bootstrap administrator',
    "grep -Fx 'otp'",
    'Password-only bootstrap access still succeeds',
  ]) requireText(errors, mfa, value, `bootstrap removal control ${value}`)
  for (const value of [
    '## Rotation',
    '## Revocation',
    '## Break-glass access',
    '## Safe evidence',
    'maximum overlap is 24 hours',
    'named primary',
    'named backup',
  ]) requireText(errors, access, value, `access rule ${value}`)
  rejectText(errors, readme, 'synthetic password injection', 'obsolete synthetic password route')

  return {
    errors,
    inventory: ownedInventory.length,
    goldenCases: ownedGolden.length,
    databaseRoles: databaseRoles.length,
    objectKeys: objectKeys.size,
    operatorRoles: operatorRoles.length,
  }
}

export function inspectPhase14CSecurity(root = repositoryDirectory) {
  return validatePhase14CSecurity(readPhase14CSources(root))
}

function main() {
  const report = inspectPhase14CSecurity()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14C security: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Phase 14C security verification passed: ${report.inventory} inventory items, `
      + `${report.goldenCases} golden cases, ${report.databaseRoles} database roles, `
      + `${report.objectKeys} object keys, and ${report.operatorRoles} operator roles.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
