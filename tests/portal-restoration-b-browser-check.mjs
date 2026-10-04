import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdir } from 'node:fs/promises'
import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const evidence = path.join(root, 'docs/migration/phase-15/evidence/restoration-b')
const server = await createServer({ configFile: path.join(root, 'vite.config.js'), envFile: false, server: { host: '127.0.0.1', port: 5184, strictPort: true } })
await server.listen()
const browser = await chromium.launch({ headless: true })
await mkdir(evidence, { recursive: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const mount = async (module) => { await page.goto(`http://127.0.0.1:5184/tests/portal-restoration-b.html?module=${module}`); await page.locator('main').waitFor() }
try {
  await mount('organization')
  await page.getByRole('heading', { name: 'Employer information' }).waitFor()
  assert.equal(await page.getByText('Enable biometric import').count(), 0)
  await page.screenshot({ path: path.join(evidence, 'organization-desktop.png'), fullPage: true })
  await mount('employees')
  await page.getByRole('button', { name: 'Alex Morgan' }).click()
  await page.getByRole('tab', { name: 'Job and contract' }).click()
  await page.getByRole('heading', { name: 'Offboarding and final settlement', exact: true }).waitFor()
  await page.screenshot({ path: path.join(evidence, 'employee-editor-desktop.png'), fullPage: true })
  await page.getByRole('tab', { name: 'Personal' }).click()
  await page.getByLabel('Name', { exact: true }).fill('Alex Morgan-Smith')
  await page.evaluate(() => { window.__restorationFailNext = true })
  await page.getByRole('button', { name: 'Save employee profile' }).click()
  await page.getByText('Employee profile could not be saved.').waitFor()
  assert.equal(await page.getByLabel('Name', { exact: true }).inputValue(), 'Alex Morgan-Smith')
  await page.getByRole('button', { name: 'Save employee profile' }).click()
  await page.getByText('Employee profile saved.').waitFor()
  const write = await page.evaluate(() => window.__restorationRequests.filter((item) => item.path.endsWith('/profile-save')).at(-1))
  assert.equal(write.options.json.profile.name, 'Alex Morgan-Smith')
  assert.equal(write.options.json.basicSalary, '8000.00')
  assert.ok(write.options.headers['Idempotency-Key'])
  await mount('requests')
  await page.getByRole('tab', { name: /Completed/ }).click()
  assert.equal(await page.getByRole('button', { name: 'View source' }).count(), 1)
  await page.screenshot({ path: path.join(evidence, 'requests-desktop.png'), fullPage: true })
  await mount('manager-requests')
  assert.equal(await page.getByRole('button', { name: 'Print PDF' }).count(), 1)
  await page.setViewportSize({ width: 390, height: 844 })
  for (const module of ['organization', 'employees', 'requests']) {
    await mount(module)
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${module} overflows`)
    await page.screenshot({ path: path.join(evidence, `${module}-mobile.png`), fullPage: true })
  }
  console.log('Portal restoration B populated checks passed.')
} finally { await page.close(); await browser.close(); await server.close() }
