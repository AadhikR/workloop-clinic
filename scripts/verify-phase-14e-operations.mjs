import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

const relativeFiles = {
  catalogue: 'docs/migration/phase-14/deployment-catalogue.json',
  contract: 'infra/digitalocean/operations-signals.json',
  provider: 'infra/digitalocean/operations-alerts.json',
  incidentSchema: 'infra/digitalocean/incident-record.schema.json',
  incidentExample: 'infra/digitalocean/incident-record.example.json',
  runbook: 'docs/migration/phase-14/PART_14E_OPERATIONS_RUNBOOK.md',
  evidenceTool: 'scripts/phase-14e-evidence.mjs',
  logging: 'backend/app/core/logging.py',
  workerControl: 'backend/app/storage/worker_control.py',
  scanner: 'backend/app/storage/scanner_worker.py',
  reconciler: 'backend/app/storage/reconciler.py',
  expiry: 'backend/app/expiry_command.py',
  terraform: 'infra/digitalocean/main.tf',
  variables: 'infra/digitalocean/variables.tf',
  terraformVerifier: 'scripts/verify-phase-14e-terraform.sh',
}

const expectedInventory = Array.from({ length: 8 }, (_, index) => `P14-OPS-${String(index + 1).padStart(3, '0')}`)
const expectedGolden = Array.from({ length: 5 }, (_, index) => `14A-GC-${String(index + 21).padStart(3, '0')}`)
const requiredComponents = [
  'frontend', 'api', 'authorization', 'rate-limits', 'keycloak', 'postgresql',
  'private-objects', 'expiry', 'file-scanner', 'storage-reconciler', 'deployments',
  'backups', 'cost',
]
const requiredWorkerConditions = ['stale-heartbeat', 'queue-age', 'expired-lease', 'retry', 'terminal-failure']
const requiredSignalFields = ['id', 'component', 'owner', 'severity', 'threshold', 'response', 'retentionDays', 'testMethod']

function readText(root, relativePath) {
  const absolutePath = path.join(root, relativePath)
  return existsSync(absolutePath) ? readFileSync(absolutePath, 'utf8').replaceAll('\r\n', '\n') : ''
}

export function readPhase14EOperations(root = repositoryDirectory) {
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

function requireText(errors, source, value, label) {
  if (!source.includes(value)) errors.push(`missing ${label}`)
}

export function validatePhase14EOperations(sources) {
  const errors = []
  const catalogue = parseJson(errors, sources.catalogue, 'deployment catalogue')
  const contract = parseJson(errors, sources.contract, 'operations signal contract')
  const provider = parseJson(errors, sources.provider, 'provider alert configuration')
  const incidentSchema = parseJson(errors, sources.incidentSchema, 'incident record schema')
  const incidentExample = parseJson(errors, sources.incidentExample, 'incident record example')

  const inventory = (catalogue.inventory ?? []).filter((entry) => entry.owner === '14E').map((entry) => entry.id)
  const goldenCases = (catalogue.goldenCases ?? []).filter((entry) => entry.owner === '14E').map((entry) => entry.id)
  if (JSON.stringify(inventory) !== JSON.stringify(expectedInventory)) errors.push('14E inventory ownership changed')
  if (JSON.stringify(goldenCases) !== JSON.stringify(expectedGolden)) errors.push('14E golden-case ownership changed')

  const signals = contract.signals ?? []
  const ids = signals.map((signal) => signal.id)
  if (signals.length === 0 || new Set(ids).size !== ids.length) errors.push('signal IDs must be present and unique')
  for (const signal of signals) {
    for (const field of requiredSignalFields) {
      if (signal[field] === undefined || signal[field] === '') errors.push(`signal ${signal.id ?? '<missing>'} lacks ${field}`)
    }
    if (!Number.isInteger(signal.retentionDays) || signal.retentionDays < 1) errors.push(`signal ${signal.id ?? '<missing>'} has invalid retentionDays`)
  }
  for (const component of requiredComponents) {
    if (!signals.some((signal) => signal.component === component)) errors.push(`signal contract lacks ${component}`)
  }
  for (const condition of requiredWorkerConditions) {
    if (!signals.some((signal) => signal.condition === condition)) errors.push(`worker signal contract lacks ${condition}`)
  }

  if (provider.providerMutationEnabled !== false) errors.push('provider mutation must default to false')
  if ((provider.alertFixtures ?? []).length === 0) errors.push('provider alert fixtures are missing')
  for (const fixture of provider.alertFixtures ?? []) {
    if (!ids.includes(fixture.signalId)) errors.push(`provider fixture references unknown signal ${fixture.signalId}`)
  }
  if (provider.delivery?.vendor !== null) errors.push('external alert delivery vendor must be absent')

  if (contract.cost?.configurationCeilingUsd !== 70) errors.push('cost ceiling must stay at USD 70')
  if (contract.cost?.blockNewWorkAboveCeiling !== true) errors.push('cost contract must block new work above the ceiling')
  if (contract.cost?.alertIsSpendingCap !== false) errors.push('cost alert must not claim to cap spending')
  requireText(errors, sources.terraform, 'local.estimated_monthly_usd <= var.configuration_ceiling_usd', 'Terraform cost fail-closed check')
  requireText(errors, sources.variables, 'variable "reviewed_monthly_forecast_usd"', 'reviewed forecast input')
  requireText(errors, sources.variables, 'var.reviewed_monthly_forecast_usd <= var.configuration_ceiling_usd', 'reviewed forecast fail-closed check')
  requireText(errors, sources.terraformVerifier, "reviewed_monthly_forecast_usd=70.01", 'forecast rejection fixture')

  for (const value of ['token', 'password', 'connection string', 'private key', 'object secret', 'signed URL', 'document content']) {
    if (!(contract.evidence?.prohibitedContent ?? []).includes(value)) errors.push(`evidence contract lacks prohibited ${value}`)
  }
  for (const marker of ['allowedFields', 'protectedValue', 'sanitizeEvidenceRecord', "flag: 'wx'"]) {
    requireText(errors, sources.evidenceTool, marker, `evidence capture ${marker}`)
  }
  for (const marker of ['SAFE_LOG_FIELDS', 'validate_safe_log_value', 'SafeLogValueError']) {
    requireText(errors, sources.logging, marker, `safe logger ${marker}`)
  }
  for (const marker of ['worker_heartbeat', 'worker_queue_observed', 'worker_lease_expired']) {
    requireText(errors, sources.workerControl, marker, `worker signal ${marker}`)
  }
  requireText(errors, sources.scanner, 'worker_retry_scheduled', 'scanner retry signal')
  requireText(errors, sources.scanner, 'worker_terminal_failure', 'scanner terminal signal')
  requireText(errors, sources.reconciler, 'worker_retry_scheduled', 'reconciler retry signal')
  requireText(errors, sources.reconciler, 'worker_terminal_failure', 'reconciler terminal signal')
  requireText(errors, sources.expiry, 'expiry_completed', 'expiry completion signal')

  const incidentRequired = incidentSchema.required ?? []
  for (const field of ['incidentId', 'openedAt', 'maintenance', 'ownerNotifications', 'evidence', 'rollbackSelection', 'recovery', 'operators']) {
    if (!incidentRequired.includes(field)) errors.push(`incident schema must require ${field}`)
  }
  if (incidentExample.template !== true) errors.push('committed incident example must remain a template')
  for (const marker of ['maintenance', 'owner notification', 'sanitized evidence', 'rollback', 'recovery', 'named operator']) {
    requireText(errors, sources.runbook.toLowerCase(), marker, `runbook ${marker}`)
  }

  return { errors, inventory: inventory.length, goldenCases: goldenCases.length, signals: signals.length }
}

export function inspectPhase14EOperations(root = repositoryDirectory) {
  return validatePhase14EOperations(readPhase14EOperations(root))
}

function main() {
  const report = inspectPhase14EOperations()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`Phase 14E operations: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(`Phase 14E operations verification passed: ${report.inventory} inventory items, ${report.goldenCases} golden cases, and ${report.signals} signals.\n`)
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
