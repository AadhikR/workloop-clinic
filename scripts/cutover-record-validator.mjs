import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SYSTEMS = new Set(['legacy-supabase', 'migration-fastapi'])
const STATUSES = new Set(['preparation', 'active-cutover', 'completed', 'rollback'])
const DEPENDENCY_KINDS = new Set(['module', 'configuration', 'data-contract', 'storage'])
const DEPENDENCY_DISPOSITIONS = new Set(['retain', 'replace', 'remove', 'freeze'])
const ROLLBACK_STEP_IDS = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]
const STATUS_TRANSITIONS = new Map([
  ['preparation', new Set(['active-cutover'])],
  ['active-cutover', new Set(['completed', 'rollback'])],
  ['completed', new Set(['rollback'])],
  ['rollback', new Set()],
])
const STABLE_ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const SHA256 = /^sha256:[a-f0-9]{64}$/
const ISO_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/
const defaultRepositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const cutoverRecordSchema = JSON.parse(readFileSync(path.join(
  defaultRepositoryDirectory,
  'docs',
  'migration',
  'phase-6',
  'cutover-record.schema.json',
), 'utf8'))

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value) {
  return typeof value === 'string' && /\S/.test(value)
}

function parseTimestamp(value) {
  if (typeof value !== 'string' || !ISO_TIMESTAMP.test(value)) return null
  const milliseconds = Date.parse(value)
  return Number.isFinite(milliseconds) ? milliseconds : null
}

function digest(buffer) {
  return `sha256:${createHash('sha256').update(buffer).digest('hex')}`
}

function resolveTrackedPath(repositoryDirectory, candidate) {
  if (!isNonEmptyString(candidate) || path.isAbsolute(candidate)) return null
  const resolved = path.resolve(repositoryDirectory, candidate)
  const relative = path.relative(repositoryDirectory, resolved)
  if (relative === '..' || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) return null
  return resolved
}

function sortedUnique(values) {
  return [...new Set(values)].sort()
}

function sameSet(left, right) {
  return JSON.stringify(sortedUnique(left)) === JSON.stringify(sortedUnique(right))
}

function schemaReference(root, reference) {
  if (!reference.startsWith('#/')) return null
  return reference.slice(2).split('/').reduce((value, part) => value?.[part], root)
}

function schemaValueMatchesType(value, type) {
  if (type === 'object') return isObject(value)
  if (type === 'array') return Array.isArray(value)
  if (type === 'string') return typeof value === 'string'
  if (type === 'integer') return Number.isInteger(value)
  return true
}

function validateSchemaNode(schema, value, instancePath, add, root = cutoverRecordSchema) {
  if (schema.$ref) {
    const resolved = schemaReference(root, schema.$ref)
    if (!resolved) {
      add(`schema.${instancePath}.$ref`, 'Schema reference does not resolve.')
      return
    }
    validateSchemaNode(resolved, value, instancePath, add, root)
    return
  }

  if (schema.type && !schemaValueMatchesType(value, schema.type)) {
    add(`schema.${instancePath}.type`, `Value must have type ${schema.type}.`)
    return
  }
  if (Object.hasOwn(schema, 'const') && JSON.stringify(value) !== JSON.stringify(schema.const)) {
    add(`schema.${instancePath}.const`, 'Value does not match the fixed schema value.')
  }
  if (schema.enum && !schema.enum.includes(value)) {
    add(`schema.${instancePath}.enum`, 'Value is not in the schema allowlist.')
  }

  if (schema.type === 'object') {
    for (const requiredName of schema.required ?? []) {
      if (!Object.hasOwn(value, requiredName)) {
        add(
          `schema.${instancePath}.required.${requiredName}`,
          `Required property ${requiredName} is missing.`,
        )
      }
    }
    const properties = schema.properties ?? {}
    if (schema.additionalProperties === false) {
      for (const name of Object.keys(value)) {
        if (!Object.hasOwn(properties, name)) {
          add(
            `schema.${instancePath}.additionalProperties.${name}`,
            `Property ${name} is not allowed.`,
          )
        }
      }
    }
    for (const [name, childSchema] of Object.entries(properties)) {
      if (Object.hasOwn(value, name)) {
        validateSchemaNode(childSchema, value[name], `${instancePath}.${name}`, add, root)
      }
    }
    return
  }

  if (schema.type === 'array') {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      add(`schema.${instancePath}.minItems`, 'Array contains too few items.')
    }
    if (schema.maxItems !== undefined && value.length > schema.maxItems) {
      add(`schema.${instancePath}.maxItems`, 'Array contains too many items.')
    }
    if (schema.uniqueItems === true) {
      const serialized = value.map((item) => JSON.stringify(item))
      if (new Set(serialized).size !== serialized.length) {
        add(`schema.${instancePath}.uniqueItems`, 'Array items must be unique.')
      }
    }
    if (schema.items) {
      value.forEach((item, index) => {
        validateSchemaNode(schema.items, item, `${instancePath}.${index}`, add, root)
      })
    }
    return
  }

  if (schema.type === 'string') {
    if (schema.minLength !== undefined && value.length < schema.minLength) {
      add(`schema.${instancePath}.minLength`, 'String is too short.')
    }
    if (schema.pattern && !(new RegExp(schema.pattern)).test(value)) {
      add(`schema.${instancePath}.pattern`, 'String does not match the required format.')
    }
    if (schema.format === 'date-time' && !Number.isFinite(Date.parse(value))) {
      add(`schema.${instancePath}.format`, 'String is not a valid date-time.')
    }
    return
  }

  if (schema.type === 'integer') {
    if (schema.minimum !== undefined && value < schema.minimum) {
      add(`schema.${instancePath}.minimum`, 'Integer is below the minimum.')
    }
    if (schema.maximum !== undefined && value > schema.maximum) {
      add(`schema.${instancePath}.maximum`, 'Integer is above the maximum.')
    }
  }
}

function checkAuthority(value, prefix, add) {
  if (!isObject(value)) {
    add(prefix, 'Authority must be an object.')
    return false
  }

  const readValid = SYSTEMS.has(value.readSystem)
  const writeValid = SYSTEMS.has(value.writeSystem)
  if (!readValid) add(`${prefix}.readSystem`, 'Authoritative reader must name one supported system.')
  if (!writeValid) add(`${prefix}.writeSystem`, 'Authoritative writer must name one supported system.')

  const writableValid = Array.isArray(value.writableSystems)
    && value.writableSystems.length === 1
    && SYSTEMS.has(value.writableSystems[0])
  if (!writableValid) {
    add(`${prefix}.writableSystems`, 'Exactly one supported system may be writable.')
  } else if (writeValid && value.writableSystems[0] !== value.writeSystem) {
    add(`${prefix}.writableSystems`, 'The sole writable system must match the authoritative writer.')
  }
  return readValid && writeValid && writableValid
}

function checkStatus(record, add) {
  const status = record.status
  if (!isObject(status)) {
    add('status', 'Status must be an object.')
    return
  }
  if (!STATUSES.has(status.current)) add('status.current', 'Current status is not supported.')
  const changedAt = parseTimestamp(status.changedAt)
  if (changedAt === null) add('status.changedAt', 'Status change time must be an ISO UTC timestamp.')
  if (!Array.isArray(status.history) || status.history.length === 0) {
    add('status.history', 'Status history must contain at least one entry.')
    return
  }

  let previousState = null
  let previousAt = null
  for (const [index, entry] of status.history.entries()) {
    const prefix = `status.history.${index}`
    if (!isObject(entry)) {
      add(prefix, 'Status history entry must be an object.')
      continue
    }
    if (!STATUSES.has(entry.state)) add(`${prefix}.state`, 'History state is not supported.')
    const at = parseTimestamp(entry.at)
    if (at === null) add(`${prefix}.at`, 'History time must be an ISO UTC timestamp.')
    if (!isNonEmptyString(entry.reason)) add(`${prefix}.reason`, 'History reason is required.')
    if (index === 0 && entry.state !== 'preparation') {
      add('status.history', 'Status history must start in preparation.')
    }
    if (previousState && STATUSES.has(entry.state) && !STATUS_TRANSITIONS.get(previousState)?.has(entry.state)) {
      add('status.history', `Status cannot move from ${previousState} to ${entry.state}.`)
    }
    if (previousAt !== null && at !== null && at <= previousAt) {
      add('status.history', 'Status history times must increase.')
    }
    previousState = entry.state
    previousAt = at
  }

  const last = status.history.at(-1)
  if (!isObject(last) || status.current !== last.state || status.changedAt !== last.at) {
    add('status.history', 'Current status and change time must match the last history entry.')
  }
}

function checkDependencies(record, add) {
  const dependencies = record.dependencies
  if (!isObject(dependencies)) {
    add('dependencies', 'Dependencies must be an object.')
    return
  }
  if (!isNonEmptyString(dependencies.inventorySource)) {
    add('dependencies.inventorySource', 'Dependency inventory source is required.')
  }
  if (!Array.isArray(dependencies.requiredIds) || dependencies.requiredIds.length === 0) {
    add('dependencies.requiredIds', 'At least one required dependency ID is needed.')
  }
  if (!Array.isArray(dependencies.declared) || dependencies.declared.length === 0) {
    add('dependencies.declared', 'At least one dependency declaration is needed.')
    return
  }

  const requiredIds = Array.isArray(dependencies.requiredIds) ? dependencies.requiredIds : []
  if (requiredIds.some((id) => !STABLE_ID.test(id)) || new Set(requiredIds).size !== requiredIds.length) {
    add('dependencies.requiredIds', 'Required dependency IDs must be unique stable identifiers.')
  }

  const declaredIds = []
  for (const [index, dependency] of dependencies.declared.entries()) {
    const prefix = `dependencies.declared.${index}`
    if (!isObject(dependency)) {
      add(prefix, 'Dependency declaration must be an object.')
      continue
    }
    if (!STABLE_ID.test(dependency.id ?? '')) add(`${prefix}.id`, 'Dependency ID is invalid.')
    else declaredIds.push(dependency.id)
    if (!SYSTEMS.has(dependency.system)) add(`${prefix}.system`, 'Dependency system is invalid.')
    if (!DEPENDENCY_KINDS.has(dependency.kind)) add(`${prefix}.kind`, 'Dependency kind is invalid.')
    if (!isNonEmptyString(dependency.locator)) add(`${prefix}.locator`, 'Dependency locator is required.')
    if (!DEPENDENCY_DISPOSITIONS.has(dependency.cutoverDisposition)) {
      add(`${prefix}.cutoverDisposition`, 'Dependency disposition is invalid.')
    }
  }
  if (new Set(declaredIds).size !== declaredIds.length) {
    add('dependencies.declared', 'Declared dependency IDs must be unique.')
  }
  if (!sameSet(requiredIds, declaredIds)) {
    add('dependencies.incomplete', 'Required and declared dependency IDs must match exactly.')
  }
}

function checkFreeze(record, add) {
  if (!isObject(record.freeze)) {
    add('freeze', 'Freeze rules must be an object.')
    return
  }
  for (const boundary of ['read', 'write']) {
    const rule = record.freeze[boundary]
    const prefix = `freeze.${boundary}`
    if (!isObject(rule)) {
      add(prefix, `${boundary} freeze rule is required.`)
      continue
    }
    if (!SYSTEMS.has(rule.system)) add(`${prefix}.system`, 'Freeze system is invalid.')
    if (!isNonEmptyString(rule.condition)) add(`${prefix}.condition`, 'Freeze condition is required.')
    if (!isNonEmptyString(rule.releaseCondition)) {
      add(`${prefix}.releaseCondition`, 'Freeze release condition is required.')
    }
    if (!isNonEmptyString(rule.verificationCommand)) {
      add(`${prefix}.verificationCommand`, 'Freeze verification command is required.')
    }
    const authorityField = boundary === 'read' ? 'readSystem' : 'writeSystem'
    if (SYSTEMS.has(rule.system) && SYSTEMS.has(record.authority?.[authorityField])
      && rule.system === record.authority[authorityField]) {
      add(`${prefix}.system`, `The authoritative ${boundary} system cannot also be frozen.`)
    }
  }
}

function checkRefresh(record, repositoryDirectory, add) {
  const refresh = record.refresh
  if (!isObject(refresh)) {
    add('refresh', 'Refresh declaration must be an object.')
    return
  }
  if (refresh.mode !== 'synthetic-only') add('refresh.mode', 'Only synthetic refresh declarations are accepted.')
  if (!isNonEmptyString(refresh.command)) add('refresh.command', 'Exact refresh command is required.')

  const source = refresh.source
  if (!isObject(source)) {
    add('refresh.source', 'Refresh source is required.')
  } else {
    if (source.kind !== 'tracked-fixture') add('refresh.source.kind', 'Refresh source must be a tracked fixture.')
    if (!isNonEmptyString(source.locator)) add('refresh.source.locator', 'Refresh source locator is required.')
    if (!SHA256.test(source.digest ?? '')) add('refresh.source.digest', 'Refresh source digest is invalid.')
  }

  const lastRefresh = refresh.lastRefresh
  if (!isObject(lastRefresh)) {
    add('refresh.lastRefresh', 'Last refresh evidence is required.')
    return
  }
  const refreshedAt = parseTimestamp(lastRefresh.timestamp)
  if (refreshedAt === null) add('refresh.lastRefresh.timestamp', 'Last refresh time must be an ISO UTC timestamp.')
  if (!isNonEmptyString(lastRefresh.command)) add('refresh.lastRefresh.command', 'Executed refresh command is required.')
  if (isNonEmptyString(refresh.command) && lastRefresh.command !== refresh.command) {
    add('refresh.lastRefresh.command', 'Executed refresh command must match the declared command.')
  }
  if (!SHA256.test(lastRefresh.sourceDigest ?? '')) {
    add('refresh.lastRefresh.sourceDigest', 'Last refresh source digest is invalid.')
  } else if (isObject(source) && SHA256.test(source.digest ?? '') && lastRefresh.sourceDigest !== source.digest) {
    add('refresh.lastRefresh.sourceDigest', 'Last refresh must use the declared source digest.')
  }

  const asOf = parseTimestamp(record.validation?.asOf)
  const maxAgeHours = record.validation?.refreshMaxAgeHours
  if (asOf !== null && refreshedAt !== null && Number.isInteger(maxAgeHours) && maxAgeHours > 0) {
    const ageMilliseconds = asOf - refreshedAt
    if (ageMilliseconds < 0 || ageMilliseconds > maxAgeHours * 60 * 60 * 1000) {
      add('refresh.lastRefresh.stale', 'Last refresh evidence is outside the allowed age window.')
    }
  }

  const evidence = lastRefresh.evidence
  if (!isObject(evidence)) {
    add('refresh.lastRefresh.evidence', 'Refresh evidence file and digest are required.')
  } else {
    const evidencePath = resolveTrackedPath(repositoryDirectory, evidence.path)
    if (!evidencePath) add('refresh.lastRefresh.evidence.path', 'Evidence path must stay inside the repository.')
    if (!SHA256.test(evidence.sha256 ?? '')) add('refresh.lastRefresh.evidence.sha256', 'Evidence digest is invalid.')
    if (evidencePath && !existsSync(evidencePath)) {
      add('refresh.lastRefresh.evidence.path', 'Evidence file does not exist.')
    } else if (evidencePath) {
      const evidenceBuffer = readFileSync(evidencePath)
      if (SHA256.test(evidence.sha256 ?? '') && digest(evidenceBuffer) !== evidence.sha256) {
        add('refresh.evidence.sha256', 'Evidence file digest does not match the declaration.')
      }
      try {
        const evidenceRecord = JSON.parse(evidenceBuffer.toString('utf8'))
        if (evidenceRecord.featureId !== record.featureId) {
          add('refresh.evidence.featureId', 'Evidence feature ID does not match the record.')
        }
        if (evidenceRecord.command !== lastRefresh.command) {
          add('refresh.evidence.command', 'Evidence command does not match the last refresh.')
        }
        if (evidenceRecord.refreshedAt !== lastRefresh.timestamp) {
          add('refresh.evidence.timestamp', 'Evidence time does not match the last refresh.')
        }
        if (evidenceRecord.sourceDigest !== lastRefresh.sourceDigest) {
          add('refresh.evidence.sourceDigest', 'Evidence source digest does not match the last refresh.')
        }
        if (!Number.isInteger(evidenceRecord.sourceRecordCount)
          || evidenceRecord.sourceRecordCount < 0
          || evidenceRecord.sourceRecordCount !== evidenceRecord.targetRecordCount) {
          add('refresh.evidence.recordCount', 'Evidence source and target record counts must match.')
        }
      } catch (error) {
        if (error instanceof SyntaxError) add('refresh.evidence.json', 'Evidence file must contain valid JSON.')
        else throw error
      }
    }
  }

  if (isObject(source) && isNonEmptyString(source.locator)) {
    const sourcePath = resolveTrackedPath(repositoryDirectory, source.locator)
    if (!sourcePath) add('refresh.source.locator', 'Refresh source path must stay inside the repository.')
    else if (!existsSync(sourcePath)) add('refresh.source.locator', 'Refresh source file does not exist.')
    else if (SHA256.test(source.digest ?? '') && digest(readFileSync(sourcePath)) !== source.digest) {
      add('refresh.source.digest', 'Refresh source digest does not match the source file.')
    }
  }
}

function checkIdentityMapping(record, add) {
  const mapping = record.identityMapping
  if (!isObject(mapping)) {
    add('identityMapping', 'Identity mapping must be an object.')
    return
  }
  if (mapping.mode !== 'synthetic-only') add('identityMapping.mode', 'Only synthetic identity mappings are accepted.')
  if (mapping.legacyIdField !== 'legacySupabaseUserId') {
    add('identityMapping.legacyIdField', 'Legacy identity field is invalid.')
  }
  if (mapping.applicationIdField !== 'applicationUserId') {
    add('identityMapping.applicationIdField', 'Application identity field is invalid.')
  }
  const required = Array.isArray(mapping.requiredLegacyUserIds) ? mapping.requiredLegacyUserIds : []
  if (required.length === 0 || required.some((id) => !UUID.test(id)) || new Set(required).size !== required.length) {
    add('identityMapping.requiredLegacyUserIds', 'Required legacy IDs must be unique UUIDs.')
  }
  if (!Array.isArray(mapping.mappings) || mapping.mappings.length === 0) {
    add('identityMapping.mappings', 'At least one synthetic identity mapping is required.')
    return
  }

  const legacyIds = []
  const applicationIds = []
  for (const [index, entry] of mapping.mappings.entries()) {
    const prefix = `identityMapping.mappings.${index}`
    if (!isObject(entry)) {
      add(prefix, 'Identity mapping entry must be an object.')
      continue
    }
    if (!UUID.test(entry.legacySupabaseUserId ?? '')) add(`${prefix}.legacySupabaseUserId`, 'Legacy ID must be a UUID.')
    else legacyIds.push(entry.legacySupabaseUserId)
    if (!UUID.test(entry.applicationUserId ?? '')) add(`${prefix}.applicationUserId`, 'Application ID must be a UUID.')
    else applicationIds.push(entry.applicationUserId)
    if (entry.synthetic !== true) add(`${prefix}.synthetic`, 'Each mapping must be marked synthetic.')
  }
  if (new Set(legacyIds).size !== legacyIds.length || new Set(applicationIds).size !== applicationIds.length) {
    add('identityMapping.oneToOne', 'Identity mappings must be one-to-one.')
  }
  if (!sameSet(required, legacyIds)) {
    add('identityMapping.incomplete', 'Every required legacy ID must have exactly one mapping.')
  }
}

function checkRollback(record, add) {
  const rollback = record.rollback
  if (!isObject(rollback)) {
    add('rollback', 'Rollback plan must be an object.')
    return
  }
  if (!isNonEmptyString(rollback.trigger)) add('rollback.trigger', 'Rollback trigger is required.')
  if (!isNonEmptyString(rollback.owner)) add('rollback.owner', 'Rollback owner is required.')
  checkAuthority(rollback.targetAuthority, 'rollback.targetAuthority', add)
  if (isObject(rollback.targetAuthority)
    && (rollback.targetAuthority.readSystem !== 'legacy-supabase'
      || rollback.targetAuthority.writeSystem !== 'legacy-supabase')) {
    add('rollback.targetAuthority', 'Rollback must restore legacy Supabase read and write authority.')
  }
  if (!Array.isArray(rollback.steps)) {
    add('rollback.steps', 'Rollback steps are required.')
    return
  }
  const stepIds = []
  for (const [index, step] of rollback.steps.entries()) {
    const prefix = `rollback.steps.${index}`
    if (!isObject(step)) {
      add(prefix, 'Rollback step must be an object.')
      continue
    }
    if (!ROLLBACK_STEP_IDS.includes(step.id)) add(`${prefix}.id`, 'Rollback step ID is invalid.')
    else stepIds.push(step.id)
    if (!isNonEmptyString(step.action)) add(`${prefix}.action`, 'Rollback action is required.')
    if (!isNonEmptyString(step.verificationCommand)) {
      add(`${prefix}.verificationCommand`, 'Rollback verification command is required.')
    }
  }
  if (JSON.stringify(stepIds) !== JSON.stringify(ROLLBACK_STEP_IDS)) {
    add('rollback.steps', 'Rollback steps must be complete and ordered.')
  }
}

function checkValidation(record, add) {
  const validation = record.validation
  if (!isObject(validation)) {
    add('validation', 'Validation settings must be an object.')
    return
  }
  if (parseTimestamp(validation.asOf) === null) add('validation.asOf', 'Validation time must be an ISO UTC timestamp.')
  if (!Number.isInteger(validation.refreshMaxAgeHours)
    || validation.refreshMaxAgeHours < 1
    || validation.refreshMaxAgeHours > 168) {
    add('validation.refreshMaxAgeHours', 'Refresh age limit must be between 1 and 168 hours.')
  }
}

function checkStatusAuthority(record, add) {
  const current = record.status?.current
  const authority = record.authority
  if (!isObject(authority) || !STATUSES.has(current)) return
  if (current === 'preparation' || current === 'rollback') {
    if (authority.readSystem !== 'legacy-supabase' || authority.writeSystem !== 'legacy-supabase') {
      add('status.authority', `${current} requires legacy-supabase read and write authority.`)
    }
    return
  }
  if (authority.readSystem !== 'migration-fastapi'
    && authority.writeSystem !== 'migration-fastapi') {
    add(
      'status.authority',
      `${current} requires at least one migration-fastapi authority boundary.`,
    )
  }
}

export function validateCutoverRecord(record, options = {}) {
  const repositoryDirectory = path.resolve(options.repositoryDirectory ?? defaultRepositoryDirectory)
  const errors = []
  const add = (code, message) => errors.push({ code, message })

  validateSchemaNode(cutoverRecordSchema, record, '$', add)
  if (!isObject(record)) return errors
  if (record.schemaVersion !== 1) add('schemaVersion', 'Schema version must be 1.')
  if (!STABLE_ID.test(record.featureId ?? '')) add('featureId', 'Feature ID must be a stable lowercase identifier.')
  if (record.dataClassification !== 'synthetic') {
    add('dataClassification', 'Phase 6D accepts synthetic declarations only.')
  }

  checkStatus(record, add)
  checkDependencies(record, add)
  checkAuthority(record.authority, 'authority', add)
  checkFreeze(record, add)
  checkValidation(record, add)
  checkRefresh(record, repositoryDirectory, add)
  checkIdentityMapping(record, add)
  checkRollback(record, add)
  checkStatusAuthority(record, add)
  return errors
}

export class CutoverRecordValidationError extends Error {
  constructor(errors) {
    super(errors.map(({ code, message }) => `${code}: ${message}`).join('\n'))
    this.name = 'CutoverRecordValidationError'
    this.errors = errors
  }
}

export function assertValidCutoverRecord(record, options = {}) {
  const errors = validateCutoverRecord(record, options)
  if (errors.length > 0) throw new CutoverRecordValidationError(errors)
  return record
}

function readRecord(recordPath) {
  return JSON.parse(readFileSync(recordPath, 'utf8'))
}

function run() {
  const recordPaths = process.argv.slice(2)
  if (recordPaths.length === 0) {
    console.error('Usage: node scripts/cutover-record-validator.mjs <record.json> [...]')
    process.exitCode = 2
    return
  }
  let failed = false
  for (const recordPath of recordPaths) {
    try {
      assertValidCutoverRecord(readRecord(recordPath))
      console.log(`${recordPath}: valid`)
    } catch (error) {
      failed = true
      console.error(`${recordPath}: invalid`)
      console.error(error.message)
    }
  }
  if (failed) process.exitCode = 1
}

const invokedPath = process.argv[1] ? pathToFileURL(path.resolve(process.argv[1])).href : null
if (invokedPath === import.meta.url) run()
