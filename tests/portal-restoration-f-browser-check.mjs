import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium } from '@playwright/test'
import { createServer } from 'vite'
import { roleNavigation } from '../src/portalRoutes.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const evidence = process.env.PORTAL_RESTORATION_EVIDENCE_DIR ? path.resolve(process.env.PORTAL_RESTORATION_EVIDENCE_DIR) : path.join(root, 'docs/migration/phase-15/evidence/restoration-f/routes')
const server = await createServer({ configFile: path.join(root, 'vite.config.js'), envFile: false, server: { host: '127.0.0.1', port: 5188, strictPort: true } })
await server.listen()
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true })
page.setDefaultTimeout(12000)
page.setDefaultNavigationTimeout(45000)
await mkdir(evidence, { recursive: true })
const errors = []
const records = []
page.on('pageerror', (error) => errors.push(error.message))
const routes = ['admin', 'manager', 'employee'].flatMap((role) => roleNavigation(role).map((route) => ({ ...route, role })))
assert.equal(routes.length, 46)

function source(route) {
  if (route.role !== 'admin') return { part: 'e', module: route.path.split('/')[2] ?? 'home' }
  const module = route.path.split('/')[2] ?? 'dashboard'
  if (['company-settings', 'employees', 'requests'].includes(module)) return { part: 'b', module: module === 'company-settings' ? 'organization' : module }
  if (['leave', 'attendance', 'roster'].includes(module)) return { part: 'c', module }
  if (['assets', 'training', 'appraisals', 'incidents', 'departments'].includes(module)) return { part: 'a', module }
  return { part: 'd', module: module === 'clinical-dashboard' ? 'clinical' : module }
}
async function mount(route, state = 'ready', extra = {}) {
  const chosen = state === 'denied' ? route.role === 'admin' ? { part: 'e', module: 'home', role: 'employee' } : { part: 'd', module: 'dashboard', role: 'admin' } : { ...source(route), role: route.role }
  const query = new URLSearchParams({ ...chosen, path: route.path, state, ...extra })
  await page.goto(`http://127.0.0.1:5188/tests/portal-restoration-f.html?${query}`)
  await page.locator(state === 'denied' ? '[data-route-state="forbidden"]' : '[data-route-state="ready"]').waitFor()
  if (state !== 'loading' && state !== 'denied') {
    await page.waitForFunction(() => window.__restorationFPending === 0)
    if (state === 'ready' || state === 'empty') await page.waitForFunction(() => !/Loading|Retrieving/i.test(document.querySelector('.main-content')?.innerText ?? 'Loading'))
    await page.waitForTimeout(220)
    await page.waitForFunction(() => window.__restorationFPending === 0)
  }
}
async function capture(name) {
  await page.waitForFunction(() => {
    const active = document.querySelector('.portal-navigation [aria-current="page"]')
    const pill = document.querySelector('.nav-pill')
    if (!active || !pill || getComputedStyle(pill).display === 'none') return true
    const a = active.getBoundingClientRect(), b = pill.getBoundingClientRect()
    return Math.abs(a.top - b.top) < 1 && Math.abs(a.height - b.height) < 1
  })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}: viewport overflow`)
  await page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: true })
}
async function assertSources(route) {
  const unhandled = await page.evaluate(() => window.__restorationFUnhandled)
  assert.deepEqual(unhandled, [], `${route.path}: missing populated source`)
  assert.deepEqual(errors, [], `${route.path}: browser error`)
}
const nameFor = (route) => route.path.slice(1).replaceAll('/', '-')
try {
  const firstRoute = process.env.PORTAL_RESTORATION_START_ROUTE ? routes.findIndex((item) => item.path === process.env.PORTAL_RESTORATION_START_ROUTE) : 0
  assert.ok(firstRoute >= 0, 'Unknown first audit route')
  for (const route of routes.slice(firstRoute).filter((item) => !process.env.PORTAL_RESTORATION_ROUTE_FILTER || item.path.includes(process.env.PORTAL_RESTORATION_ROUTE_FILTER))) {
    const name = nameFor(route)
    const record = { path: route.path, role: route.role, title: route.title, screenshots: [], states: [] }
    for (const [viewport, dark] of [['desktop', false], ['mobile', false], ['mobile', true]]) {
      await page.setViewportSize(viewport === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 })
      await mount(route, 'ready', dark ? { dark: 'true' } : {})
      const main = page.locator('.main-content')
      const text = await main.innerText()
      assert.ok(text.length > 60, `${route.path}: populated content is missing`)
      assert.doesNotMatch(text, /unavailable|could not be loaded|Loading (?:dashboard|your dashboard|employees|records|workforce)/i, `${route.path}: source failed or did not settle`)
      await assertSources(route)
      assert.equal(await page.locator('.portal-navigation [aria-current="page"]').getAttribute('href'), route.path)
      await page.locator('.skip-link').focus()
      await page.keyboard.press('Enter')
      assert.equal(await page.evaluate(() => document.activeElement.id), 'portal-content')
      const shot = `${name}-${viewport}${dark ? '-dark' : ''}`
      await capture(shot); record.screenshots.push(`${shot}.png`)
    }
    record.states.push('populated', 'keyboard', 'mobile', 'dark')
    record.sources = await page.evaluate(() => window.__restorationFRequests.map((request) => request.path))
    for (const state of ['empty', 'unavailable', 'loading']) {
      for (const viewport of ['desktop', 'mobile']) {
        await page.setViewportSize(viewport === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 })
        await mount(route, state)
        if (state === 'loading') {
          await page.locator('.main-content').getByText(/Loading|Retrieving/i).filter({ visible: true }).first().waitFor()
        } else if (state === 'unavailable' && route.path !== '/admin/company-settings' && !route.path.endsWith('/profile')) {
          await page.locator('.main-content').getByText(/unavailable|could not|cannot|failed|try again/i).filter({ visible: true }).first().waitFor()
          assert.match(await page.locator('.main-content').innerText(), /unavailable|could not|cannot|failed|try again/i, `${route.path}: missing unavailable state`)
        }
        await assertSources(route)
        const shot = `${name}-${state}-${viewport}`
        await capture(shot); record.screenshots.push(`${shot}.png`)
        if (state === 'loading') await page.evaluate(() => { window.__restorationFRelease = true })
      }
      record.states.push(state)
    }
    for (const viewport of ['desktop', 'mobile']) {
      await page.setViewportSize(viewport === 'desktop' ? { width: 1440, height: 1000 } : { width: 390, height: 844 })
      await mount(route, 'denied')
      await page.getByRole('alert').filter({ hasText: 'cannot open' }).waitFor()
      await capture(`${name}-denied-${viewport}`)
      record.screenshots.push(`${name}-denied-${viewport}.png`)
    }
    record.states.push('denied')
    records.push(record)
    await writeFile(path.join(evidence, 'route-audit.json'), `${JSON.stringify({ complete: records.length === 46, routes: records }, null, 2)}\n`)
    console.log(`${route.path}: populated, responsive, keyboard and main-state checks passed`)
  }
  assert.deepEqual(errors, [])
  console.log(`Portal restoration F route audit passed for ${records.length} views.`)
} catch (error) {
  await page.screenshot({ path: path.join(evidence, 'failure.png'), fullPage: true }).catch(() => {})
  console.error(await page.locator('body').innerText().catch(() => 'No page body'))
  console.error(await page.evaluate(() => window.__restorationFUnhandled).catch(() => []))
  throw error
} finally { await page.close(); await browser.close(); await server.close() }
