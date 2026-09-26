import { readFileSync } from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { pathToFileURL } from 'node:url'

const repositoryDirectory = path.resolve(import.meta.dirname, '..')
const fixture = JSON.parse(readFileSync(
  path.join(repositoryDirectory, 'tests', 'fixtures', 'phase-13e', 'inert-sentinels.json'),
  'utf8',
))
const guardUrl = pathToFileURL(path.join(repositoryDirectory, 'scripts', 'phase-13f-network-guard.mjs')).href
const result = spawnSync(process.execPath, ['scripts/verify-phase-3g-browser.mjs'], {
  cwd: repositoryDirectory,
  encoding: 'utf8',
  env: {
    ...process.env,
    ...fixture.environment,
    NODE_OPTIONS: `--import=${guardUrl}`,
    WORKLOOP_PHASE13F_NETWORK_GUARD: '1',
    WORKLOOP_PHASE13F_NETWORK_SOURCE: 'browser-test-helper',
  },
  stdio: 'inherit',
})

if (result.error) throw result.error
process.exitCode = result.status ?? 1
