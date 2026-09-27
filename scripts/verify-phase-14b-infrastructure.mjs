import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const relativeFiles = {
  main: 'infra/digitalocean/main.tf',
  variables: 'infra/digitalocean/variables.tf',
  outputs: 'infra/digitalocean/outputs.tf',
  versions: 'infra/digitalocean/versions.tf',
  example: 'infra/digitalocean/shared-development.tfvars.example',
  readme: 'infra/digitalocean/README.md',
  realm: 'keycloak/cloud/workloop-dev-realm.json',
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
}

const expectedCosts = new Map([
  ['api', 10],
  ['keycloak', 25],
  ['file_scanner', 5],
  ['storage_reconciler', 5],
  ['managed_postgresql', 15.15],
  ['spaces_standard', 5],
  ['web_static_site', 0],
])

const approvalFields = [
  'target_manifest_id',
  'owner_approval_reference',
  'approved_on',
  'price_reviewed_on',
  'retention_review_due_on',
  'state_custodian',
  'state_path_reference',
  'credential_custodian',
  'infrastructure_owner',
  'security_owner',
  'application_owner',
  'incident_owner',
  'release_reviewer',
  'backup_custodian',
  'variable_charge_owner',
  'cleanup_manifest_id',
]

function readText(root, relativePath) {
  return readFileSync(path.join(root, relativePath), 'utf8').replaceAll('\r\n', '\n')
}

export function readPhase14BSources(root = repositoryDirectory) {
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

function resourceIsDisabled(source, declaration) {
  const escaped = declaration.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(`${escaped}\\s*\\{\\s*count\\s*=\\s*local\\.enabled \\? 1 : 0`).test(source)
}

function parseCosts(source) {
  const match = source.match(/fixed_monthly_costs\s*=\s*\{([\s\S]*?)\n\s*\}/)
  if (!match) return null
  const costs = new Map()
  for (const entry of match[1].matchAll(/^\s*([a-z_]+)\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*$/gm)) {
    costs.set(entry[1], Number(entry[2]))
  }
  return costs
}

export function validatePhase14BInfrastructure(sources) {
  const errors = []
  const { main, variables, outputs, versions, example, readme, realm } = sources
  const catalogue = JSON.parse(sources.catalogue)

  for (const [name, value, label] of [
    ['project_name', 'workloop-clinic-dev', 'project name'],
    ['project_id', '634213f9-2e43-4aea-8f4e-22ddc3ecdac9', 'project ID'],
    ['app_name', 'workloop-clinic-dev', 'app name'],
    ['database_cluster_name', 'workloop-clinic-dev-db', 'database cluster name'],
    ['spaces_bucket_name', 'workloop-clinic-dev-634213f9', 'bucket name'],
    ['app_region', 'fra', 'App Platform region'],
    ['resource_region', 'fra1', 'provider resource region'],
    ['vpc_name', 'fra1-default', 'VPC name'],
    ['vpc_id', 'b8b6d17b-eae4-47de-b2b5-9d10baabdd2d', 'VPC ID'],
    ['vpc_cidr', '10.114.0.0/20', 'VPC CIDR'],
  ]) {
    if (!new RegExp(`\\b${name}\\s*=\\s*"${value.replaceAll('.', '\\.') }"`).test(main)) {
      errors.push(`missing ${label}`)
    }
  }
  requireText(errors, main, 'name       = "workloop"', 'application database')
  requireText(errors, main, 'name       = "keycloak"', 'identity database')

  const components = [
    ['database-migrate', 'apps-s-1vcpu-1gb-fixed'],
    ['api', 'apps-s-1vcpu-1gb-fixed'],
    ['keycloak', 'apps-s-1vcpu-2gb'],
    ['web', null],
    ['expiry', 'apps-s-1vcpu-0.5gb'],
    ['file-scanner', 'apps-s-1vcpu-0.5gb'],
    ['storage-reconciler', 'apps-s-1vcpu-0.5gb'],
  ]
  for (const [name, size] of components) {
    const componentStart = main.indexOf(`name               = "${name}"`)
      === -1 ? main.indexOf(`name           = "${name}"`) : main.indexOf(`name               = "${name}"`)
    if (componentStart === -1) {
      errors.push(`missing component ${name}`)
      continue
    }
    const componentSource = main.slice(componentStart, componentStart + 900)
    if (name !== 'web' && !componentSource.includes('instance_count     = 1')) {
      errors.push(`${name} must have one instance`)
    }
    if (size && !componentSource.includes(`instance_size_slug = "${size}"`)) {
      errors.push(`${name} has the wrong fixed size`)
    }
    const immutableImage = componentSource.includes('image {')
      && componentSource.includes('digest        = var.release_manifest.')
      && !componentSource.includes('github {')
      && !componentSource.includes('tag')
    if (!componentSource.includes('deploy_on_push = false') && !immutableImage) {
      errors.push(`${name} must disable automatic deployment`)
    }
  }

  const declarations = [
    'data "digitalocean_project" "shared"',
    'data "digitalocean_vpc" "default"',
    'resource "terraform_data" "phase_14_guard"',
    'resource "digitalocean_database_cluster" "shared"',
    'resource "digitalocean_database_db" "workloop"',
    'resource "digitalocean_database_db" "keycloak"',
    'resource "digitalocean_spaces_bucket" "shared"',
    'resource "digitalocean_app" "shared"',
    'resource "digitalocean_database_firewall" "app_only"',
    'resource "digitalocean_project_resources" "shared"',
  ]
  for (const declaration of declarations) {
    if (!resourceIsDisabled(main, declaration)) {
      errors.push(`${declaration} must be absent from disabled plans`)
    }
  }

  for (const [value, label] of [
    ['id    = local.vpc_id', 'VPC lookup by verified ID'],
    ['data.digitalocean_vpc.default[0].name == local.vpc_name', 'VPC name assertion'],
    ['data.digitalocean_vpc.default[0].region == local.resource_region', 'VPC region assertion'],
    ['data.digitalocean_vpc.default[0].ip_range == local.vpc_cidr', 'VPC CIDR assertion'],
    ['data.digitalocean_vpc.default[0].default', 'default VPC assertion'],
    ['private_network_uuid = data.digitalocean_vpc.default[0].id', 'private database VPC binding'],
    ['id = data.digitalocean_vpc.default[0].id', 'private app VPC binding'],
    ['type  = "app"', 'app-only database firewall'],
    ['value = digitalocean_app.shared[0].id', 'database firewall app identity'],
  ]) requireText(errors, main, value, label)
  rejectText(errors, main, 'resource "digitalocean_vpc"', 'managed default VPC')
  rejectText(errors, main, 'type  = "ip_addr"', 'public database firewall source')
  rejectText(errors, main, 'type  = "cidr"', 'CIDR database firewall source')

  for (const [value, label] of [
    ['acl           = "private"', 'private bucket ACL'],
    ['force_destroy = false', 'non-destructive bucket setting'],
    ['enabled = true', 'bucket versioning'],
  ]) requireText(errors, main, value, label)
  rejectText(errors, main, 'cors_rule {', 'bucket CORS rule')
  rejectText(errors, main, 'force_destroy = true', 'forced bucket deletion')
  rejectText(errors, main, 'acl           = "public-read"', 'public bucket ACL')

  for (const [key, value] of [
    ['environment', 'shared-development'],
    ['data_class', 'synthetic-only'],
    ['managed_by', 'terraform'],
    ['owner_role', 'infrastructure-custodian'],
  ]) {
    if (!new RegExp(`\\b${key}\\s*=\\s*"${value}"`).test(main)) errors.push(`missing ownership label ${key}`)
  }
  requireText(errors, main, 'tags                 = local.ownership_tags', 'database ownership tags')
  requireText(errors, main, 'key   = "WORKLOOP_INFRASTRUCTURE_OWNER"', 'app ownership label')
  requireText(errors, main, 'digitalocean_spaces_bucket.shared[0].urn', 'bucket project assignment')
  requireText(errors, main, 'digitalocean_database_cluster.shared[0].urn', 'database project assignment')
  requireText(errors, main, 'digitalocean_app.shared[0].urn', 'app project assignment')

  rejectText(errors, main, 'autoscaling {', 'component autoscaling')
  rejectText(errors, main, 'enabled       = true', 'database storage autoscaling')
  rejectText(errors, main, 'deploy_on_push = true', 'automatic branch deployment')
  rejectText(errors, main, 'domain {', 'custom domain')
  rejectText(errors, main, 'domains =', 'custom domains')
  if (/\*/.test(main) || JSON.stringify(JSON.parse(realm)).includes('*')) {
    errors.push('wildcard origin, callback, source, or route is forbidden')
  }
  requireText(errors, realm, '${WORKLOOP_PUBLIC_URL}/oidc/callback', 'exact OIDC callback')
  const realmDocument = JSON.parse(realm)
  const browserClient = realmDocument.clients.find((client) => client.clientId === 'workloop-migration-web')
  if (JSON.stringify(browserClient?.webOrigins) !== JSON.stringify(['${WORKLOOP_PUBLIC_URL}'])) {
    errors.push('missing exact web origin')
  }

  const costs = parseCosts(main)
  if (!costs) {
    errors.push('missing fixed monthly cost map')
  } else {
    const actualEntries = [...costs.entries()]
    if (JSON.stringify(actualEntries) !== JSON.stringify([...expectedCosts.entries()])) {
      errors.push('fixed monthly cost items are not exact')
    }
    const total = actualEntries.reduce((sum, [, value]) => sum + value, 0)
    if (Number(total.toFixed(2)) !== 65.15) errors.push('fixed monthly cost must total USD 65.15')
  }
  if (!/estimated_monthly_usd\s*=\s*sum\(values\(local\.fixed_monthly_costs\)\)/.test(main)) {
    errors.push('missing calculated monthly estimate')
  }
  requireText(errors, main, 'configuration_ceiling_usd = 70', 'USD 70 configuration ceiling')
  requireText(errors, main, 'local.estimated_monthly_usd <= var.configuration_ceiling_usd', 'cost ceiling guard')
  requireText(errors, variables, 'default     = 70', 'default USD 70 ceiling')

  requireText(errors, variables, 'variable "provisioning_authorized"', 'provisioning switch')
  requireText(errors, variables, 'default     = false', 'disabled provisioning default')
  requireText(errors, variables, 'variable "approval"', 'approval input object')
  requireText(errors, variables, 'default   = null', 'missing approval default')
  requireText(errors, variables, '!var.provisioning_authorized || alltrue([', 'input validation for incomplete approval')
  for (const field of approvalFields) {
    requireText(errors, variables, `${field}`, `approval field ${field}`)
    requireText(errors, main, `try(var.approval.${field}, "")`, `approval guard ${field}`)
    if (variables.split(`try(var.approval.${field}, "")`).length !== 2) {
      errors.push(`approval input validation must check ${field}`)
    }
  }
  requireText(errors, main, 'var.provisioning_authorized && local.approval_complete', 'enabled-plan approval guard')
  if (!/provisioning_authorized\s*=\s*false/.test(example)) errors.push('missing disabled example')
  rejectText(errors, variables + example + main, 'teardown_deadline', 'proof teardown deadline')
  rejectText(errors, variables + example + main, 'test_window_hours', 'proof test window')
  rejectText(errors, variables + example + main, 'synthetic_user_password', 'synthetic password injection')
  rejectText(errors, variables + example + main, 'keycloak_bootstrap_admin_password', 'bootstrap password injection')
  rejectText(errors, variables + example + main, 'phase_6g', 'Phase 6G identifier')
  rejectText(errors, variables + example + main, 'Phase 6G', 'Phase 6G prose')

  requireText(errors, main, 'storage_autoscale {', 'explicit database storage limit')
  requireText(errors, main, 'enabled = false', 'disabled database storage autoscaling')
  if (!/storage_size_mib\s*=\s*"10240"/.test(main)) errors.push('missing fixed 10 GiB database storage')
  requireText(errors, main, 'maintenance_window {', 'database maintenance window')
  requireText(errors, readme, 'provider-managed native backups', 'native backup policy')
  requireText(errors, readme, 'restricted owner-controlled storage', 'external state custody')
  requireText(errors, versions, 'backend "local" {}', 'local backend boundary')
  requireText(errors, versions, 'version = "2.100.0"', 'pinned DigitalOcean provider')

  const secretOutputPattern = /output\s+"[^"]+"[\s\S]*?(password|secret|token|private_uri|uri|connection)/i
  if (secretOutputPattern.test(outputs)) errors.push('secret-bearing output is forbidden')
  rejectText(errors, outputs, 'sensitive = true', 'sensitive output')
  for (const outputName of ['app_url', 'app_id', 'database_cluster_id', 'spaces_bucket_name', 'estimated_monthly_usd', 'configuration_ceiling_usd']) {
    requireText(errors, outputs, `output "${outputName}"`, `output ${outputName}`)
  }

  const ownedInventory = catalogue.inventory.filter((entry) => entry.owner === '14B').map((entry) => entry.id)
  const ownedGolden = catalogue.goldenCases.filter((entry) => entry.owner === '14B').map((entry) => entry.id)
  if (JSON.stringify(ownedInventory) !== JSON.stringify(Array.from({ length: 10 }, (_, index) => `P14-INF-${String(index + 1).padStart(3, '0')}`))) {
    errors.push('14B inventory ownership changed')
  }
  if (JSON.stringify(ownedGolden) !== JSON.stringify(Array.from({ length: 6 }, (_, index) => `14A-GC-${String(index + 1).padStart(3, '0')}`))) {
    errors.push('14B golden-case ownership changed')
  }

  return { errors, inventory: ownedInventory.length, goldenCases: ownedGolden.length, approvalFields: approvalFields.length }
}

export function inspectPhase14BInfrastructure(root = repositoryDirectory) {
  return validatePhase14BInfrastructure(readPhase14BSources(root))
}

function main() {
  const report = inspectPhase14BInfrastructure()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14B infrastructure: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Phase 14B infrastructure verification passed: ${report.inventory} inventory items, `
      + `${report.goldenCases} golden cases, and ${report.approvalFields} required approval fields.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
