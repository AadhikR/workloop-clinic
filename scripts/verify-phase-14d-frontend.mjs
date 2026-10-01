import { createHash } from 'node:crypto'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sha256Pattern = /^sha256:[0-9a-f]{64}$/

function filesBelow(directory) {
  return readdirSync(directory).flatMap((name) => {
    const entry = path.join(directory, name)
    return statSync(entry).isDirectory() ? filesBelow(entry) : [entry]
  })
}

export function digestFile(file) {
  return `sha256:${createHash('sha256').update(readFileSync(file)).digest('hex')}`
}

export function digestDirectory(directory) {
  const hash = createHash('sha256')
  for (const file of filesBelow(directory).sort()) {
    hash.update(path.relative(directory, file).replaceAll('\\', '/'))
    hash.update('\0')
    hash.update(readFileSync(file))
  }
  return `sha256:${hash.digest('hex')}`
}

function option(name) {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

export async function verifyFrontend({
  directory = path.join(repositoryDirectory, 'dist'),
  expected = option('--expected') ?? process.env.WORKLOOP_FRONTEND_SHA256,
  rootExpected = option('--root-expected') ?? process.env.WORKLOOP_FRONTEND_ROOT_SHA256,
  url = option('--url') ?? process.env.WORKLOOP_WEB_HEALTH_URL,
} = {}) {
  if (!sha256Pattern.test(expected ?? '') || !sha256Pattern.test(rootExpected ?? '')) {
    throw new Error('recorded frontend digests are required')
  }
  if (!existsSync(path.join(directory, 'index.html'))) throw new Error('dist/index.html is missing')
  const actual = digestDirectory(directory)
  const rootActual = digestFile(path.join(directory, 'index.html'))
  if (actual !== expected || rootActual !== rootExpected) {
    throw new Error(`frontend digest mismatch: output ${actual}; root ${rootActual}`)
  }
  if (url) {
    const response = await fetch(url, { redirect: 'error' })
    if (!(response.status === 200)) throw new Error('frontend root did not return HTTP 200')
    const body = Buffer.from(await response.arrayBuffer())
    const delivered = `sha256:${createHash('sha256').update(body).digest('hex')}`
    if (delivered !== rootExpected) throw new Error('delivered frontend root digest mismatch')
  }
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) {
  verifyFrontend().then(
    () => process.stdout.write('Phase 14D frontend digest verification passed.\n'),
    (error) => {
      process.stderr.write(`Phase 14D frontend: ${error.message}\n`)
      process.exitCode = 1
    },
  )
}
