import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultAllowlistPath = 'scripts/phase-13e-retired-runtime-allowlist.json'
const historyLabel = 'Historical record. Do not run or deploy these files.'
const marker = 'supabase'

const concealedMarkerPatterns = [
  /["'`]supa["'`]\s*\+\s*["'`]base/i,
  /["'`]@["'`]\s*\+\s*["'`]supabase(?:\/|["'`])/i,
  /String\.raw\s*`[^`]*supa\$\{[^}]*\}base/i,
]

function normalizePath(value) {
  return value.replaceAll('\\', '/')
}

function gitFiles(root) {
  const result = spawnSync(
    'git',
    ['ls-files', '-z', '--cached', '--others', '--exclude-standard'],
    { cwd: root, encoding: 'buffer' },
  )
  if (result.status !== 0) {
    throw new Error(result.stderr.toString('utf8'))
  }
  return result.stdout
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .map(normalizePath)
    .filter((relativePath) => existsSync(path.join(root, relativePath)))
}

function loadFiles(root, paths) {
  return paths.map((relativePath) => ({
    path: normalizePath(relativePath),
    content: readFileSync(path.join(root, relativePath)),
  }))
}

function hasMarker(content) {
  const source = content.toString('utf8')
  return source.toLowerCase().includes(marker)
    || concealedMarkerPatterns.some((pattern) => pattern.test(source))
}

function digest(content) {
  return createHash('sha256').update(content).digest('hex')
}

function validateAllowlist(allowlist, filesByPath) {
  const errors = []
  const owners = new Map()

  if (allowlist.version !== 1 || !Array.isArray(allowlist.groups)) {
    return ['allowlist must declare version 1 and a groups array']
  }

  for (const group of allowlist.groups) {
    if (!['history', 'negative-proof', 'phase-record'].includes(group.kind)) {
      errors.push(`${group.id ?? '<unnamed>'}: invalid allowlist kind`)
      continue
    }
    if (!Array.isArray(group.paths) || group.paths.length === 0) {
      errors.push(`${group.id ?? '<unnamed>'}: paths must be a non-empty array`)
      continue
    }
    if (group.kind === 'history') {
      if (!group.labelPath || !group.paths.includes(group.labelPath)) {
        errors.push(`${group.id}: history group must include its labelPath`)
      } else {
        const labelFile = filesByPath.get(group.labelPath)
        if (!labelFile || !labelFile.content.toString('utf8').includes(historyLabel)) {
          errors.push(`${group.id}: missing required history label in ${group.labelPath}`)
        }
      }
    } else if (group.labelPath) {
      errors.push(`${group.id}: only history groups may declare labelPath`)
    }

    for (const allowedPath of group.paths) {
      const normalized = normalizePath(allowedPath)
      if (normalized !== allowedPath || path.isAbsolute(allowedPath) || allowedPath.includes('..')) {
        errors.push(`${group.id}: path is not a normalized repository-relative path: ${allowedPath}`)
        continue
      }
      const priorOwner = owners.get(allowedPath)
      if (priorOwner) errors.push(`${allowedPath}: allowlisted by both ${priorOwner} and ${group.id}`)
      owners.set(allowedPath, group.id)
      if (!filesByPath.has(allowedPath)) errors.push(`${group.id}: missing allowlisted file ${allowedPath}`)
    }
  }

  for (const artifact of allowlist.binaryHistory ?? []) {
    const priorOwner = owners.get(artifact.path)
    if (priorOwner) errors.push(`${artifact.path}: allowlisted by both ${priorOwner} and binary-history`)
    owners.set(artifact.path, 'binary-history')
    const file = filesByPath.get(artifact.path)
    if (!file) {
      errors.push(`binary-history: missing file ${artifact.path}`)
    } else if (digest(file.content) !== artifact.sha256) {
      errors.push(`binary-history: digest mismatch for ${artifact.path}`)
    }
  }

  return { errors, owners }
}

export function inspectSnapshot({ files, allowlist }) {
  const filesByPath = new Map(files.map((file) => [normalizePath(file.path), file]))
  const validation = validateAllowlist(allowlist, filesByPath)
  if (Array.isArray(validation)) {
    return { errors: validation, inspected: files.length, markerFiles: 0, referenceFreeFiles: files.length }
  }

  const errors = [...validation.errors]
  const markerFiles = []
  for (const file of files) {
    const relativePath = normalizePath(file.path)
    if (!hasMarker(file.content)) continue
    markerFiles.push(relativePath)
    if (!validation.owners.has(relativePath)) {
      errors.push(`${relativePath}: retired runtime marker is not allowlisted`)
    }
  }

  for (const [allowedPath, groupId] of validation.owners) {
    if (groupId === 'binary-history') continue
    const file = filesByPath.get(allowedPath)
    if (file && !hasMarker(file.content)) {
      errors.push(`${allowedPath}: stale allowlist entry has no retired runtime marker`)
    }
  }

  return {
    errors,
    inspected: files.length,
    markerFiles: markerFiles.length,
    referenceFreeFiles: files.length - markerFiles.length,
  }
}

export function inspectRepository(root = defaultRoot, allowlistRelativePath = defaultAllowlistPath) {
  const paths = gitFiles(root)
  const files = loadFiles(root, paths)
  const allowlist = JSON.parse(readFileSync(path.join(root, allowlistRelativePath), 'utf8'))
  return inspectSnapshot({ files, allowlist })
}

function main() {
  const report = inspectRepository()
  if (report.errors.length > 0) {
    for (const error of report.errors) process.stderr.write(`repository guard: ${error}\n`)
    process.exitCode = 1
    return
  }
  process.stdout.write(
    `Repository guard passed: ${report.inspected} files inspected, ${report.markerFiles} classified, ${report.referenceFreeFiles} reference-free.\n`,
  )
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
