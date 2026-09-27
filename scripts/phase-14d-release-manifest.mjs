import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { digestDirectory, digestFile } from './verify-phase-14d-frontend.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sha256Pattern = /^sha256:[0-9a-f]{64}$/
const commitPattern = /^[0-9a-f]{40}$/
const releasePattern = /^[a-z0-9][a-z0-9._-]{2,79}$/
const registryTypes = new Set(['DOCR', 'DOCKER_HUB'])

function filesBelow(directory, predicate = () => true) {
  return readdirSync(directory).flatMap((name) => {
    const entry = path.join(directory, name)
    if (name === '.terraform') return []
    return statSync(entry).isDirectory() ? filesBelow(entry, predicate) : predicate(entry) ? [entry] : []
  })
}

function digestFiles(root, files) {
  const hash = createHash('sha256')
  for (const file of files.sort()) {
    hash.update(path.relative(root, file).replaceAll('\\', '/'))
    hash.update('\0')
    hash.update(readFileSync(file))
  }
  return `sha256:${hash.digest('hex')}`
}

export function sourceDigests(root = repositoryDirectory) {
  const terraformDirectory = path.join(root, 'infra', 'digitalocean')
  const terraformFiles = filesBelow(
    terraformDirectory,
    (file) => /(?:\.tf|\.hcl|app-spec\.contract\.json)$/.test(file),
  )
  return {
    frontendSha256: digestDirectory(path.join(root, 'dist')),
    frontendRootSha256: digestFile(path.join(root, 'dist', 'index.html')),
    dependencyLockSha256: {
      frontend: digestFile(path.join(root, 'package-lock.json')),
      backend: digestFile(path.join(root, 'backend', 'requirements.lock')),
      backendDev: digestFile(path.join(root, 'backend', 'requirements-dev.lock')),
    },
    terraformSha256: digestFiles(terraformDirectory, terraformFiles),
    appSpecSha256: digestFile(path.join(terraformDirectory, 'app-spec.contract.json')),
  }
}

function validImage(image) {
  return image && registryTypes.has(image.registryType) && typeof image.registry === 'string'
    && (image.registryType === 'DOCR' ? image.registry === '' : image.registry.length > 0)
    && typeof image.repository === 'string'
    && image.repository.length > 0 && sha256Pattern.test(image.digest ?? '')
}

export function validateReleaseManifest(manifest, { requireDeployable = true } = {}) {
  const errors = []
  const manifestFields = new Set([
    'schemaVersion',
    'releaseId',
    'deployable',
    'gitCommit',
    'backendImage',
    'keycloakImage',
    'frontendSha256',
    'frontendRootSha256',
    'dependencyLockSha256',
    'terraformSha256',
    'appSpecSha256',
    'alembicHead',
    'createdAt',
    'reviewedBy',
  ])
  for (const name of Object.keys(manifest)) {
    if (!manifestFields.has(name)) errors.push(`unexpected manifest field ${name}`)
  }
  if (manifest.schemaVersion !== 1) errors.push('schemaVersion must be 1')
  if (!releasePattern.test(manifest.releaseId ?? '')) errors.push('releaseId is invalid')
  if (requireDeployable && manifest.deployable !== true) errors.push('manifest is not deployable')
  if (!commitPattern.test(manifest.gitCommit ?? '')) errors.push('gitCommit must be a full lowercase commit')
  if (!validImage(manifest.backendImage)) errors.push('backendImage is invalid')
  if (!validImage(manifest.keycloakImage)) errors.push('keycloakImage is invalid')
  for (const [name, imageValue] of [
    ['backendImage', manifest.backendImage],
    ['keycloakImage', manifest.keycloakImage],
  ]) {
    for (const field of Object.keys(imageValue ?? {})) {
      if (!['registryType', 'registry', 'repository', 'digest'].includes(field)) {
        errors.push(`${name} has unexpected field ${field}`)
      }
    }
  }
  for (const [name, value] of Object.entries({
    frontendSha256: manifest.frontendSha256,
    frontendRootSha256: manifest.frontendRootSha256,
    terraformSha256: manifest.terraformSha256,
    appSpecSha256: manifest.appSpecSha256,
    frontendLockSha256: manifest.dependencyLockSha256?.frontend,
    backendLockSha256: manifest.dependencyLockSha256?.backend,
    backendDevLockSha256: manifest.dependencyLockSha256?.backendDev,
  })) if (!sha256Pattern.test(value ?? '')) errors.push(`${name} is invalid`)
  for (const field of Object.keys(manifest.dependencyLockSha256 ?? {})) {
    if (!['frontend', 'backend', 'backendDev'].includes(field)) {
      errors.push(`dependencyLockSha256 has unexpected field ${field}`)
    }
  }
  if (manifest.alembicHead !== 'e8a1c3f5b7d9') errors.push('alembicHead is incompatible')
  if (typeof manifest.createdAt !== 'string' || Number.isNaN(Date.parse(manifest.createdAt))) {
    errors.push('createdAt is invalid')
  }
  if (typeof manifest.reviewedBy !== 'string' || manifest.reviewedBy.trim() === '') errors.push('reviewedBy is required')
  return errors
}

export function verifySourceDigests(manifest, root = repositoryDirectory) {
  const actual = sourceDigests(root)
  const errors = []
  for (const name of ['frontendSha256', 'frontendRootSha256', 'terraformSha256', 'appSpecSha256']) {
    if (manifest[name] !== actual[name]) errors.push(`${name} does not match the reviewed source`)
  }
  for (const name of ['frontend', 'backend', 'backendDev']) {
    if (manifest.dependencyLockSha256?.[name] !== actual.dependencyLockSha256[name]) {
      errors.push(`dependencyLockSha256.${name} does not match the reviewed source`)
    }
  }
  return errors
}

function option(name) {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function image(prefix) {
  return {
    registryType: option(`--${prefix}-registry-type`),
    registry: option(`--${prefix}-registry`),
    repository: option(`--${prefix}-repository`),
    digest: option(`--${prefix}-digest`),
  }
}

function currentCommit() {
  return execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repositoryDirectory, encoding: 'utf8' }).trim()
}

function createManifest() {
  const status = execFileSync('git', ['status', '--porcelain'], { cwd: repositoryDirectory, encoding: 'utf8' })
  if (status.trim()) throw new Error('release creation requires a clean working tree')
  const manifest = {
    schemaVersion: 1,
    releaseId: option('--release-id'),
    deployable: true,
    gitCommit: currentCommit(),
    backendImage: image('backend'),
    keycloakImage: image('keycloak'),
    ...sourceDigests(),
    alembicHead: 'e8a1c3f5b7d9',
    createdAt: new Date().toISOString(),
    reviewedBy: option('--reviewed-by'),
  }
  const errors = validateReleaseManifest(manifest)
  if (errors.length) throw new Error(errors.join('; '))
  const output = option('--output')
  if (!output) throw new Error('--output is required')
  writeFileSync(path.resolve(output), `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' })
}

function validateManifest() {
  const file = process.argv[3]
  if (!file || !existsSync(file)) throw new Error('manifest path is required')
  const manifest = JSON.parse(readFileSync(file, 'utf8'))
  const errors = [...validateReleaseManifest(manifest), ...verifySourceDigests(manifest)]
  if (errors.length) throw new Error(errors.join('; '))
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv[2] === 'create') createManifest()
    else if (process.argv[2] === 'validate') validateManifest()
    else throw new Error('use create or validate')
    process.stdout.write('Phase 14D release manifest verification passed.\n')
  } catch (error) {
    process.stderr.write(`Phase 14D release manifest: ${error.message}\n`)
    process.exitCode = 1
  }
}
