import { createCipheriv, createDecipheriv, createHash } from 'node:crypto'
import { Buffer } from 'node:buffer'
import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const magic = Buffer.from('WLP14F1\0', 'ascii')
const keyIdPattern = /^[0-9a-f]{8}$/
const releaseIdPattern = /^[a-z0-9][a-z0-9._-]{2,79}$/
const digestPattern = /^sha256:[0-9a-f]{64}$/
const databases = new Set(['workloop', 'keycloak'])

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`
  }
  return JSON.stringify(value)
}

function requireKey(key) {
  if (!Buffer.isBuffer(key) || key.length !== 32) throw new Error('recovery key must contain 32 bytes')
}

export function sealPortableExport({ plaintext, database, releaseId, keyId, key, nonce }) {
  requireKey(key)
  if (!Buffer.isBuffer(plaintext) || plaintext.length === 0) throw new Error('portable export is empty')
  if (!databases.has(database)) throw new Error('portable export database is invalid')
  if (!releaseIdPattern.test(releaseId ?? '')) throw new Error('portable export release ID is invalid')
  if (!keyIdPattern.test(keyId ?? '')) throw new Error('portable export key ID is invalid')
  if (!Buffer.isBuffer(nonce) || nonce.length !== 12) throw new Error('portable export nonce must contain 12 bytes')
  const metadata = Buffer.from(canonical({ database, releaseId }), 'utf8')
  const header = Buffer.concat([magic, Buffer.from(keyId, 'ascii'), Buffer.from([metadata.length]), metadata, nonce])
  const cipher = createCipheriv('aes-256-gcm', key, nonce)
  cipher.setAAD(header)
  const ciphertext = Buffer.concat([cipher.update(plaintext), cipher.final()])
  const payload = Buffer.concat([header, cipher.getAuthTag(), ciphertext])
  return {
    payload,
    sha256: `sha256:${createHash('sha256').update(payload).digest('hex')}`,
  }
}

export function openPortableExport({ payload, expectedDatabase, expectedReleaseId, keys }) {
  if (!Buffer.isBuffer(payload) || payload.length < magic.length + 8 + 1 + 12 + 16 + 1) {
    throw new Error('portable export envelope is invalid')
  }
  if (!payload.subarray(0, magic.length).equals(magic)) throw new Error('portable export envelope is invalid')
  let offset = magic.length
  const keyId = payload.subarray(offset, offset + 8).toString('ascii')
  offset += 8
  const metadataLength = payload[offset]
  offset += 1
  const metadataBytes = payload.subarray(offset, offset + metadataLength)
  offset += metadataLength
  const nonce = payload.subarray(offset, offset + 12)
  offset += 12
  const header = payload.subarray(0, offset)
  const tag = payload.subarray(offset, offset + 16)
  const ciphertext = payload.subarray(offset + 16)
  let metadata
  try {
    metadata = JSON.parse(metadataBytes.toString('utf8'))
  } catch {
    throw new Error('portable export metadata is invalid')
  }
  if (metadata.database !== expectedDatabase || metadata.releaseId !== expectedReleaseId) {
    throw new Error('portable export target does not match the request')
  }
  const key = keys[keyId]
  requireKey(key)
  try {
    const decipher = createDecipheriv('aes-256-gcm', key, nonce)
    decipher.setAAD(header)
    decipher.setAuthTag(tag)
    return Buffer.concat([decipher.update(ciphertext), decipher.final()])
  } catch {
    throw new Error('portable export authentication failed')
  }
}

export function selectRollbackManifest({ currentManifest, candidateManifest, requestedReleaseId }) {
  if (!requestedReleaseId) throw new Error('rollback requires an explicit release ID')
  if (candidateManifest?.releaseId !== requestedReleaseId) throw new Error('rollback release does not match the request')
  if (candidateManifest.releaseId === currentManifest?.releaseId) throw new Error('rollback release must be prior')
  if (candidateManifest.deployable !== true || !candidateManifest.reviewedBy) throw new Error('rollback release is not reviewed')
  if (candidateManifest.alembicHead !== currentManifest?.alembicHead) throw new Error('rollback release is not schema compatible')
  if (candidateManifest.alembicHead !== 'e8a1c3f5b7d9') throw new Error('rollback release has an unexpected schema head')
  for (const image of [candidateManifest.backendImage, candidateManifest.keycloakImage]) {
    if (!digestPattern.test(image?.digest ?? '') || Object.hasOwn(image ?? {}, 'tag')) {
      throw new Error('rollback release contains a mutable artifact')
    }
  }
  return candidateManifest
}

export function validateRecoveryRecord(record, contract) {
  const errors = []
  if (record.schemaVersion !== 1 || record.template !== true) errors.push('record must remain a version 1 template')
  if (record.environment !== 'isolated-local') errors.push('record must use the isolated local environment')
  if (record.alembicHead !== contract.alembicHead) errors.push('record has an incompatible Alembic head')
  if (record.source?.composeProject !== contract.isolatedTargets.sourceComposeProject) errors.push('source project changed')
  if (record.restore?.composeProject !== contract.isolatedTargets.restoreComposeProject) errors.push('restore project changed')
  if (record.restore?.postgresVolume !== contract.isolatedTargets.restorePostgresVolume) errors.push('restore PostgreSQL volume changed')
  if (record.restore?.storageVolume !== contract.isolatedTargets.restoreStorageVolume) errors.push('restore storage volume changed')
  if (record.restore?.s3Volume !== contract.isolatedTargets.restoreS3Volume) errors.push('restore S3 volume changed')
  if (record.restore?.objectBucket !== contract.isolatedTargets.restoreObjectBucket) errors.push('restore object bucket changed')
  if (record.restore?.publicNetworkExposure !== false) errors.push('restore target must not have public exposure')
  if (record.restore?.maintenanceEnabled !== true || record.restore?.applicationWritesEnabled !== false
    || record.restore?.workerProcessingEnabled !== false) errors.push('restore write block is incomplete')
  const exportNames = new Set((record.portableExports ?? []).filter((item) => item.encrypted === true
    && keyIdPattern.test(item.keyId ?? '') && digestPattern.test(item.sha256 ?? '')).map((item) => item.database))
  for (const database of contract.isolatedTargets.databases) {
    if (!exportNames.has(database)) errors.push(`encrypted portable export is missing for ${database}`)
  }
  const comparisons = new Map((record.comparisons ?? []).map((item) => [item.id, item]))
  for (const comparison of contract.requiredComparisons) {
    if (comparisons.get(comparison)?.status !== 'passed') errors.push(`recovery comparison did not pass: ${comparison}`)
  }
  for (const result of ['authentication', 'authorization', 'privateFiles', 'workers', 'administrator', 'manager', 'employee']) {
    if (record.journeys?.[result] !== 'passed') errors.push(`recovery journey did not pass: ${result}`)
  }
  if (record.providerNativeEvidence?.status !== 'pending-14g-provider-live'
    || record.providerNativeEvidence?.sharedPromotionAllowed !== false) errors.push('provider-live dependency must remain fail closed')
  if (record.rollback?.requestedReleaseId !== record.rollback?.selectedReleaseId
    || record.rollback?.schemaCompatible !== true
    || record.rollback?.alembicHead !== contract.alembicHead
    || record.rollback?.automaticSchemaDowngrade !== false
    || record.rollback?.result !== 'passed') errors.push('rollback proof is incomplete')
  if (record.evidence?.retained !== true || record.evidence?.sanitized !== true
    || !digestPattern.test(record.evidence?.sha256 ?? '')) errors.push('sanitized retained evidence is incomplete')
  const expectedCleanup = new Set([
    contract.isolatedTargets.restorePostgresVolume,
    contract.isolatedTargets.restoreStorageVolume,
    contract.isolatedTargets.restoreS3Volume,
    contract.isolatedTargets.restoreObjectBucket,
  ])
  const actualCleanup = new Set(record.cleanup?.verifiedTargets ?? [])
  if (actualCleanup.size !== expectedCleanup.size || [...actualCleanup].some((target) => !expectedCleanup.has(target))) {
    errors.push('cleanup target allowlist changed')
  }
  if (record.cleanup?.completed !== true || record.cleanup?.idempotent !== true) errors.push('cleanup proof is incomplete')
  if (record.localRehearsalResult !== 'passed' || record.sharedPromotionAllowed !== false) errors.push('rehearsal result must stay local and fail closed')
  return errors
}

function option(name) {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function recoveryKey() {
  const encoded = process.env.WORKLOOP_RECOVERY_KEY_BASE64
  if (!encoded) throw new Error('WORKLOOP_RECOVERY_KEY_BASE64 is required')
  return Buffer.from(encoded, 'base64')
}

function inputBytes(input) {
  if (!input) throw new Error('--input is required')
  return input === '-' ? readFileSync(0) : readFileSync(path.resolve(input))
}

function outputBytes(output, bytes) {
  if (!output) throw new Error('--output is required')
  if (output === '-') process.stdout.write(bytes)
  else writeFileSync(path.resolve(output), bytes, { flag: 'wx', mode: 0o600 })
}

function main() {
  const mode = process.argv[2]
  const key = recoveryKey()
  const database = option('--database')
  const releaseId = option('--release-id')
  if (mode === 'seal') {
    const nonce = Buffer.from(option('--nonce-hex') ?? '', 'hex')
    const result = sealPortableExport({
      plaintext: inputBytes(option('--input')),
      database,
      releaseId,
      keyId: option('--key-id'),
      key,
      nonce,
    })
    outputBytes(option('--output'), result.payload)
    if (option('--output') !== '-') process.stdout.write(`Portable ${database} export sealed as ${result.sha256}.\n`)
    return
  }
  if (mode === 'open') {
    const payload = inputBytes(option('--input'))
    outputBytes(option('--output'), openPortableExport({
      payload,
      expectedDatabase: database,
      expectedReleaseId: releaseId,
      keys: { [option('--key-id')]: key },
    }))
    return
  }
  throw new Error('use seal or open')
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`Phase 14F recovery: ${error.message}\n`)
    process.exitCode = 1
  }
}
