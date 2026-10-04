import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { gzipSync } from 'node:zlib'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { performance } from 'node:perf_hooks'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'
import { roleNavigation } from '../src/portalRoutes.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5179'
const apiBaseUrl = (process.env.WORKLOOP_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export const phase15FBudgets = Object.freeze({
  initialCompressedTransferBytes: 225_000,
  laterRouteTransferBytes: 1_024,
  largestRouteBundleCompressedBytes: 210_000,
  routeChangeP95Ms: 300,
  formFeedbackP95Ms: 500,
  representativeApiP95Ms: 500,
})

const roleRoutes = Object.fromEntries(['admin', 'manager', 'employee'].map((role) => [
  role, roleNavigation(role).map(({ path }) => path),
]))

function p95(values) {
  const sorted = [...values].sort((left, right) => left - right)
  return sorted[Math.max(0, Math.ceil(sorted.length * 0.95) - 1)]
}

function compressedBytes(filePath) {
  return gzipSync(readFileSync(filePath), { level: 9 }).length
}

function buildProduction() {
  const command = process.platform === 'win32' ? (process.env.ComSpec ?? 'cmd.exe') : 'npm'
  const args = process.platform === 'win32'
    ? ['/d', '/s', '/c', 'npm', 'run', 'build', '--', '--logLevel', 'silent']
    : ['run', 'build', '--', '--logLevel', 'silent']
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8' })
  if (result.status !== 0) throw new Error(result.stderr || result.stdout || 'production build failed')
}

async function mount(page, role, route) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ role: accountRole, route: pathName }) => {
    localStorage.setItem('workloop-advanced-features', 'true')
    if (accountRole === 'admin') {
      const { mountPhase15CAdministrator } = await import('/tests/phase-15c-harness.jsx')
      mountPhase15CAdministrator({ path: pathName })
    } else if (accountRole === 'manager') {
      const { mountPhase15DManager } = await import('/tests/phase-15d-harness.jsx')
      mountPhase15DManager({ path: pathName })
    } else {
      const { mountPhase15EEmployee } = await import('/tests/phase-15e-harness.jsx')
      mountPhase15EEmployee({ path: pathName })
    }
  }, { role, route })
  await page.locator('[data-route-state="ready"]').waitFor()
}

async function measureBrowser(browser) {
  const routeSamples = []
  const formSamples = []

  for (const [role, routes] of Object.entries(roleRoutes)) {
    const page = await browser.newPage()
    await mount(page, role, routes[0])
    for (const route of [...routes.slice(1), ...routes.slice(1)]) {
      const link = page.locator(`a[href="${route}"]`)
      const started = await page.evaluate(() => performance.now())
      await link.click()
      await page.waitForFunction((pathName) => (
        location.pathname === pathName
        && document.activeElement?.tagName === 'H1'
      ), route)
      const ended = await page.evaluate(() => performance.now())
      routeSamples.push(ended - started)
    }
    await page.close()
  }

  for (let index = 0; index < 10; index += 1) {
    const page = await browser.newPage()
    await mount(page, 'employee', '/employee/profile')
    await page.getByRole('button', { name: 'Edit contact details', exact: true }).click()
    const started = await page.evaluate(() => performance.now())
    await page.getByRole('button', { name: 'Save contact details' }).click()
    await page.getByRole('alert').filter({ hasText: 'Contact details could not be saved.' }).waitFor()
    const ended = await page.evaluate(() => performance.now())
    formSamples.push(ended - started)
    await page.close()
  }

  return { formSamples, routeSamples }
}

async function measureApi() {
  const samples = []
  for (let index = 0; index < 25; index += 1) {
    const started = performance.now()
    const response = await fetch(`${apiBaseUrl}/health`, { cache: 'no-store' })
    const body = await response.json()
    samples.push(performance.now() - started)
    assert.equal(response.status, 200)
    assert.deepEqual(body, { status: 'ok', database: 'ok' })
  }
  return samples
}

buildProduction()
const indexPath = path.join(root, 'dist', 'index.html')
const indexHtml = readFileSync(indexPath, 'utf8')
const assetNames = readdirSync(path.join(root, 'dist', 'assets'))
const chunks = assetNames.filter((name) => name.endsWith('.js'))
const styles = assetNames.filter((name) => name.endsWith('.css'))
const initialAssetNames = [...indexHtml.matchAll(/(?:src|href)="\/([^"?]+)"/g)]
  .map((match) => match[1])
const initialFiles = [
  indexPath,
  ...initialAssetNames.map((name) => path.join(root, 'dist', name)),
]
const initialCompressedTransferBytes = initialFiles.reduce((total, file) => total + compressedBytes(file), 0)
const largestRouteBundleCompressedBytes = Math.max(
  ...chunks.map((chunk) => compressedBytes(path.join(root, 'dist', 'assets', chunk))),
)
const laterRouteFiles = chunks.filter((chunk) => !initialAssetNames.includes(`assets/${chunk}`))
const laterRouteTransferBytes = laterRouteFiles.reduce(
  (total, chunk) => total + compressedBytes(path.join(root, 'dist', 'assets', chunk)),
  0,
)

const server = await createServer({
  configFile,
  envFile: false,
  server: { host: '127.0.0.1', port: 5179, strictPort: true },
})
await server.listen()
const browser = await chromium.launch({ headless: true })
let browserMeasurements
let browserVersion
try {
  browserVersion = browser.version()
  browserMeasurements = await measureBrowser(browser)
} finally {
  await browser.close()
  await server.close()
}
const apiSamples = await measureApi()

const measured = {
  initialCompressedTransferBytes,
  laterRouteTransferBytes,
  largestRouteBundleCompressedBytes,
  routeChangeP95Ms: Number(p95(browserMeasurements.routeSamples).toFixed(2)),
  formFeedbackP95Ms: Number(p95(browserMeasurements.formSamples).toFixed(2)),
  representativeApiP95Ms: Number(p95(apiSamples).toFixed(2)),
}
for (const [name, value] of Object.entries(measured)) {
  assert.ok(value <= phase15FBudgets[name], `${name} ${value} exceeds ${phase15FBudgets[name]}`)
}

const report = {
  profile: {
    name: 'phase15f-local-loopback-chromium',
    runner: `${process.platform}-${process.arch}; Node ${process.version}`,
    browser: `Chromium ${browserVersion}`,
    network: '127.0.0.1 loopback, no throttling',
    command: 'npm run verify:phase15f:performance',
  },
  budgets: phase15FBudgets,
  measurements: {
    initialCompressedTransferBytes: { value: measured.initialCompressedTransferBytes, sampleCount: 1, percentile: 'total', cacheState: 'cold-build' },
    laterRouteTransferBytes: { value: measured.laterRouteTransferBytes, sampleCount: Object.values(roleRoutes).reduce((total, routes) => total + routes.length, 0), percentile: 'total', cacheState: 'warm-route' },
    largestRouteBundleCompressedBytes: { value: measured.largestRouteBundleCompressedBytes, sampleCount: chunks.length + styles.length, percentile: 'maximum', cacheState: 'cold-build' },
    routeChangeP95Ms: { value: measured.routeChangeP95Ms, sampleCount: browserMeasurements.routeSamples.length, percentile: 'p95', cacheState: 'warm-application' },
    formFeedbackP95Ms: { value: measured.formFeedbackP95Ms, sampleCount: browserMeasurements.formSamples.length, percentile: 'p95', cacheState: 'warm-application' },
    representativeApiP95Ms: { value: measured.representativeApiP95Ms, sampleCount: apiSamples.length, percentile: 'p95', cacheState: 'no-store' },
  },
}

process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
