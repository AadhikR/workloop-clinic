import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  inspectNetworkAttempt,
  installNodeNetworkGuard,
} from '../scripts/phase-13f-network-guard.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fixture = JSON.parse(readFileSync(
  path.join(repositoryDirectory, 'tests', 'fixtures', 'phase-13e', 'inert-sentinels.json'),
  'utf8',
))
const dependencies = ['P13-NET-001', 'P13-NET-002', 'P13-NET-003', 'P13-NET-004']
const goldenCases = [
  '13A-GC-011',
  '13A-GC-012',
  '13A-GC-013',
  '13A-GC-014',
  '13A-GC-017',
  '13A-GC-018',
  '13A-GC-019',
  '13A-GC-020',
  '13A-GC-035',
  '13A-GC-040',
  '13A-GC-041',
  '13A-GC-042',
]

function read(relativePath) {
  return readFileSync(path.join(repositoryDirectory, relativePath), 'utf8')
}

function alembicHeads() {
  const revisions = new Set()
  const predecessors = new Set()
  const versions = path.join(repositoryDirectory, 'backend', 'alembic', 'versions')
  for (const name of readdirSync(versions)) {
    if (!name.endsWith('.py')) continue
    const source = read(path.join('backend', 'alembic', 'versions', name))
    const revision = source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    assert.ok(revision, name)
    revisions.add(revision[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

test('rejects every named protocol before resolution or connection handling', () => {
  assert.deepEqual(fixture.attempts.map(({ protocol, target }) => (
    inspectNetworkAttempt(protocol, target).forbidden
  )), fixture.attempts.map(() => true))
  assert.deepEqual(fixture.allowedAttempts.map(({ protocol, target }) => (
    inspectNetworkAttempt(protocol, target).forbidden
  )), fixture.allowedAttempts.map(() => false))
})

test('intercepts concrete Node DNS, TCP, TLS, HTTP, HTTPS, and WebSocket attempts', async () => {
  installNodeNetworkGuard('focused-node-fixture')
  const target = fixture.attempts[0].target
  const dns = await import('node:dns')
  const http = await import('node:http')
  const https = await import('node:https')
  const net = await import('node:net')
  const tls = await import('node:tls')

  assert.throws(() => dns.lookup(target, () => {}), /blocked a forbidden dns attempt/)
  assert.throws(() => net.connect({ host: target, port: 5432 }), /blocked a forbidden tcp attempt/)
  assert.throws(() => tls.connect({ host: target, port: 443 }), /blocked a forbidden tls attempt/)
  assert.throws(() => http.get(`http://${target}/rest/v1`), /blocked a forbidden http attempt/)
  assert.throws(() => https.get(`https://${target}/auth/v1`), /blocked a forbidden https attempt/)
  assert.throws(() => new WebSocket(`wss://${target}/realtime/v1`), /blocked a forbidden websocket attempt/)
})

test('installs the Python guard before DNS and socket entry points', () => {
  const source = read('scripts/phase13f_sitecustomize.py')
  assert.match(source, /GUARD_ACTIVE = True/)
  assert.match(source, /socket\.getaddrinfo = _wrap\(socket\.getaddrinfo, "dns"\)/)
  assert.match(source, /socket\.create_connection = _wrap\(socket\.create_connection, "tcp"\)/)
  assert.match(source, /socket\.socket\.connect = _wrap\(socket\.socket\.connect, "tcp"\)/)
  assert.match(source, /os\.environ\[_name\] = _value/)
})

test('keeps the 13E allowlist byte-for-byte fixed', () => {
  const digest = createHash('sha256')
    .update(readFileSync(path.join(repositoryDirectory, 'scripts', 'phase-13e-retired-runtime-allowlist.json')))
    .digest('hex')
  assert.equal(digest, '9ebd61b461d3080a96111dd5e7b6ed49e47e41b410578f1fa9f0e4d6dc1d4176')
})

test('covers builds, browsers, backend processes, workers, and test helpers', () => {
  const overlay = read('docker-compose.phase13f.yml')
  for (const service of ['migrate', 'backend', 'storage-reconciler', 'expiry', 'file-scanner']) {
    assert.match(overlay, new RegExp(`  ${service}:\\n    <<: \\*phase13f-python-guard`))
  }
  assert.match(read('scripts/verify-phase-3g-browser.mjs'), /installBrowserNetworkGuard/)
  assert.match(read('scripts/verify-phase-3g-browser.mjs'), /--new-password="\$password"/)
  assert.match(read('scripts/verify-phase-13f-browser.mjs'), /WORKLOOP_PHASE13F_NETWORK_GUARD/)
  assert.match(read('scripts/verify-phase-13f-clean-setup.mjs'), /'ci', '--ignore-scripts', '--no-audit'/)
})

test('routes the disposable proof and never names the preserved project for cleanup', () => {
  const workflow = read('.github/workflows/migration-foundation.yml')
  assert.match(workflow, /COMPOSE_PROJECT_NAME: workloop-phase13f-verify/)
  assert.match(workflow, /docker-compose\.phase13f\.yml/)
  assert.match(workflow, /npm run verify:phase13f:clean/)
  assert.match(workflow, /node scripts\/verify-phase-13f-browser\.mjs/)
  assert.match(workflow, /run: docker compose down --volumes/)
  assert.doesNotMatch(workflow, /docker (?:compose|volume)[^\n]*(?:down|rm)[^\n]*workloop-clinic_postgres_data/)
})

test('closes the Part 13F catalogue boundary and keeps one schema head', () => {
  const catalogue = JSON.parse(read('docs/migration/phase-13/dependency-catalogue.json'))
  const closure = catalogue.closures['13F']
  assert.equal(closure.status, 'completed')
  assert.deepEqual(closure.dependencies, dependencies)
  assert.deepEqual(closure.goldenCases, goldenCases)
  assert.ok(closure.evidence.includes('scripts/verify-phase-13f-clean-setup.mjs'))
  assert.ok(closure.evidence.includes('scripts/phase-13f-network-guard.mjs'))
  assert.ok(closure.evidence.includes('docs/migration/phase-13/PART_13F_COMPLETION.md'))
  assert.deepEqual(alembicHeads(), ['e8a1c3f5b7d9'])
})
