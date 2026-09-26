import { createHash } from 'node:crypto'
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'

const repositoryDirectory = path.resolve(import.meta.dirname, '..')
const fixturePath = path.join(repositoryDirectory, 'tests', 'fixtures', 'phase-13e', 'inert-sentinels.json')
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'))
const forbiddenNames = Object.keys(fixture.environment)
const forbiddenValues = Object.values(fixture.environment)
const marker = fixture.marker

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    encoding: 'utf8',
    env: options.env,
    maxBuffer: 16 * 1024 * 1024,
  })
  if (result.status !== 0) {
    const output = `${result.stdout ?? ''}\n${result.stderr ?? ''}`
    const redacted = forbiddenValues.reduce(
      (value, forbidden) => value.replaceAll(forbidden, '[redacted]'),
      output,
    )
    const cause = result.error instanceof Error ? `: ${result.error.message}` : ''
    throw new Error(`${command} failed with status ${result.status}${cause}\n${redacted}`)
  }
  return result
}

function copyRepository(target) {
  const files = run(
    'git',
    ['ls-files', '-z', '--cached', '--others', '--exclude-standard'],
    { cwd: repositoryDirectory },
  ).stdout.split('\0').filter(Boolean)
  for (const relativePath of files) {
    const destination = path.join(target, relativePath)
    mkdirSync(path.dirname(destination), { recursive: true })
    cpSync(path.join(repositoryDirectory, relativePath), destination)
  }
}

function filesBelow(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = path.join(directory, entry.name)
    return entry.isDirectory() ? filesBelow(entryPath) : [entryPath]
  })
}

function digestOutput(directory) {
  const hash = createHash('sha256')
  for (const file of filesBelow(directory).sort()) {
    hash.update(path.relative(directory, file).replaceAll('\\', '/'))
    hash.update(readFileSync(file))
  }
  return hash.digest('hex')
}

function assertReferenceFree(directory, label) {
  const lowerMarker = marker.toLowerCase()
  for (const file of filesBelow(directory)) {
    const source = readFileSync(file)
    const text = source.toString('utf8').toLowerCase()
    if (text.includes(lowerMarker)) throw new Error(`${label} contains a forbidden marker`)
    for (const value of forbiddenValues) {
      if (source.includes(Buffer.from(value))) throw new Error(`${label} contains a hostile value`)
    }
  }
}

function installedPackageNames(directory) {
  const names = []
  for (const file of filesBelow(directory)) {
    if (path.basename(file) !== 'package.json') continue
    const packageJson = JSON.parse(readFileSync(file, 'utf8'))
    if (typeof packageJson.name === 'string') names.push(packageJson.name)
  }
  return names
}

function cleanEnvironment() {
  const environment = { ...process.env }
  for (const name of forbiddenNames) delete environment[name]
  delete environment.NODE_OPTIONS
  environment.WORKLOOP_PHASE13F_NETWORK_GUARD = '1'
  environment.WORKLOOP_PHASE13F_NETWORK_SOURCE = 'frontend-build'
  return environment
}

function build(directory, environment) {
  const guardUrl = pathToFileURL(path.join(directory, 'scripts', 'phase-13f-network-guard.mjs')).href
  run(process.execPath, ['node_modules/vite/bin/vite.js', 'build', '--logLevel', 'silent'], {
    cwd: directory,
    env: { ...environment, NODE_OPTIONS: `--import=${guardUrl}` },
  })
  return digestOutput(path.join(directory, 'dist'))
}

const disposableDirectory = mkdtempSync(path.join(tmpdir(), 'workloop-phase13f-'))
try {
  copyRepository(disposableDirectory)
  const environment = cleanEnvironment()
  const npmCommand = process.platform === 'win32' ? (process.env.ComSpec ?? 'cmd.exe') : 'npm'
  const npmArguments = process.platform === 'win32'
    ? ['/d', '/s', '/c', 'npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund']
    : ['ci', '--ignore-scripts', '--no-audit', '--no-fund']
  run(npmCommand, npmArguments, {
    cwd: disposableDirectory,
    env: environment,
  })

  const packageLock = readFileSync(path.join(disposableDirectory, 'package-lock.json'), 'utf8')
  if (packageLock.toLowerCase().includes(marker.toLowerCase())) {
    throw new Error('The locked graph contains a forbidden package or tarball')
  }
  const forbiddenPackages = installedPackageNames(path.join(disposableDirectory, 'node_modules'))
    .filter((name) => name.toLowerCase().includes(marker.toLowerCase()))
  if (forbiddenPackages.length > 0) throw new Error('The installed graph contains a forbidden package')

  const absentDigest = build(disposableDirectory, environment)
  assertReferenceFree(path.join(disposableDirectory, 'dist'), 'Absent-environment output')
  rmSync(path.join(disposableDirectory, 'dist'), { force: true, recursive: true })

  const hostileEnvironment = { ...environment, ...fixture.environment }
  const hostileDigest = build(disposableDirectory, hostileEnvironment)
  assertReferenceFree(path.join(disposableDirectory, 'dist'), 'Hostile-environment output')
  if (absentDigest !== hostileDigest) throw new Error('Hostile environment changed production output')

  process.stdout.write('Phase 13F clean locked install and deterministic production graph passed.\n')
} finally {
  rmSync(disposableDirectory, { force: true, recursive: true })
}
