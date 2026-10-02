import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5174'
const branchId = 'b2000000-0000-4000-8000-000000000002'
const staleBranchId = 'b2000000-0000-4000-8000-000000000099'

async function mount(page, options) {
  await page.goto(baseUrl)
  await page.evaluate(async (values) => {
    const { mountPhase15BShell } = await import('/tests/phase-15b-harness.jsx')
    mountPhase15BShell(values)
  }, options)
}

const server = await createServer({ configFile, envFile: false })
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  const adminPage = await browser.newPage()
  await mount(adminPage, { path: '/admin', role: 'admin', storedBranchId: branchId })
  await adminPage.locator('[data-route-state="ready"]').waitFor()
  assert.equal(await adminPage.getByRole('heading', { level: 1 }).textContent(), 'Administrator home')
  assert.equal(await adminPage.getByRole('link', { name: 'Administrator home' }).getAttribute('aria-current'), 'page')
  assert.equal(await adminPage.evaluate(() => document.activeElement?.tagName), 'H1')
  assert.equal(await adminPage.locator('main').count(), 1)
  assert.equal(await adminPage.locator('.skip-link').count(), 1)

  await adminPage.getByRole('link', { name: 'People' }).click()
  await adminPage.locator('[data-route-state="unavailable"]').waitFor()
  assert.equal(new URL(adminPage.url()).pathname, '/admin/people')
  assert.equal(await adminPage.evaluate(() => document.activeElement?.tagName), 'H1')
  await adminPage.goBack()
  await adminPage.locator('[data-route-state="ready"]').waitFor()
  assert.equal(new URL(adminPage.url()).pathname, '/admin')

  await adminPage.waitForTimeout(50)
  const requestsBeforeDenial = await adminPage.evaluate(() => [...window.__phase15bCalls])
  await adminPage.evaluate(() => {
    history.pushState(null, '', '/employee')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await adminPage.locator('[data-route-state="forbidden"]').waitFor()
  assert.deepEqual(await adminPage.evaluate(() => window.__phase15bCalls), requestsBeforeDenial)
  assert.equal(await adminPage.getByRole('heading', { level: 1 }).textContent(), 'Access denied')
  await adminPage.close()

  const stalePage = await browser.newPage()
  await mount(stalePage, { path: '/admin', role: 'admin', storedBranchId: staleBranchId })
  await stalePage.locator('[data-route-state="choose-branch"]').waitFor()
  assert.equal(await stalePage.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  assert.equal(await stalePage.locator('nav[aria-label="Primary"]').count(), 0)
  await stalePage.getByRole('button', { name: 'Dubai clinic' }).click()
  await stalePage.locator('[data-route-state="ready"]').waitFor()
  assert.equal(await stalePage.evaluate(() => sessionStorage.getItem('workloop.branchId')), branchId)
  await stalePage.close()

  const employeePage = await browser.newPage()
  await mount(employeePage, { path: '/employee', role: 'employee', storedBranchId: staleBranchId })
  await employeePage.locator('[data-route-state="ready"]').waitFor()
  assert.equal(await employeePage.getByRole('button', { name: 'Change branch' }).count(), 0)
  assert.equal(await employeePage.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  assert.equal(await employeePage.locator('[data-selected-branch-name]').textContent(), 'Dubai clinic')
  await employeePage.close()

  process.stdout.write('Phase 15B shell browser check passed\n')
} finally {
  await browser.close()
  await server.close()
}
