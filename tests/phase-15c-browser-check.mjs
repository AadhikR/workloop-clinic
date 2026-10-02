import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5175'
const branchId = 'b2000000-0000-4000-8000-000000000002'
const staleBranchId = 'b2000000-0000-4000-8000-000000000099'

const routes = [
  ['/admin', 'Administrator home', '[data-dashboard-kind="admin"]'],
  ['/admin/organization', 'Organization', '.organization-settings'],
  ['/admin/people', 'People', '.employee-directory'],
  ['/admin/leave', 'Leave', 'section.leave-configuration, section[aria-label="Leave configuration"]'],
  ['/admin/attendance', 'Attendance', '.attendance-configuration'],
  ['/admin/roster', 'Roster', '.roster-drafts'],
  ['/admin/payroll', 'Payroll', '.payroll'],
  ['/admin/records', 'Records', '#records-benefits-title'],
  ['/admin/development', 'Development', '#development-assets-title'],
  ['/admin/reports', 'Reports', '.migration-reports'],
]

async function mount(page, options, crossRole = false) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ crossRole: useCrossRole, values }) => {
    const harness = await import('/tests/phase-15c-harness.jsx')
    if (useCrossRole) harness.mountPhase15CCrossRole(values)
    else harness.mountPhase15CAdministrator(values)
  }, { crossRole, values: options })
}

const server = await createServer({ configFile, envFile: false, server: { port: 5175 } })
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  for (const [route, heading, evidenceSelector] of routes) {
    const page = await browser.newPage()
    await mount(page, { path: route, storedBranchId: branchId })
    await page.locator('[data-route-state="ready"]').waitFor()
    assert.equal(new URL(page.url()).pathname, route)
    assert.equal(await page.getByRole('heading', { level: 1 }).textContent(), heading)
    assert.equal(await page.evaluate(() => document.activeElement?.tagName), 'H1')
    assert.equal(await page.locator('[data-selected-branch-name]').textContent(), 'Dubai clinic')
    await page.locator(evidenceSelector).first().waitFor()
    if (route !== '/admin') {
      assert.equal(await page.locator(`[data-administrator-route="${route}"]`).count(), 1)
    }
    await page.close()
  }

  const historyPage = await browser.newPage()
  await mount(historyPage, { path: '/admin/organization', storedBranchId: branchId })
  await historyPage.locator('[data-administrator-route="/admin/organization"]').waitFor()
  await historyPage.getByRole('link', { name: 'People' }).click()
  await historyPage.locator('[data-administrator-route="/admin/people"]').waitFor()
  await historyPage.goBack()
  await historyPage.locator('[data-administrator-route="/admin/organization"]').waitFor()
  await historyPage.getByRole('button', { name: 'Sign out' }).last().click()
  assert.equal(await historyPage.evaluate(() => window.__phase15cLoggedOut), true)
  await historyPage.close()

  const stalePage = await browser.newPage()
  await mount(stalePage, { path: '/admin/records', storedBranchId: staleBranchId })
  await stalePage.locator('[data-route-state="choose-branch"]').waitFor()
  assert.equal(await stalePage.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  assert.equal(await stalePage.locator('[data-administrator-route]').count(), 0)
  await stalePage.getByRole('button', { name: 'Dubai clinic' }).click()
  await stalePage.locator('[data-administrator-route="/admin/records"]').waitFor()
  assert.equal(await stalePage.evaluate(() => sessionStorage.getItem('workloop.branchId')), branchId)
  await stalePage.close()

  const denialPage = await browser.newPage()
  await mount(denialPage, { path: '/admin/payroll' }, true)
  await denialPage.locator('[data-route-state="forbidden"]').waitFor()
  assert.deepEqual(await denialPage.evaluate(() => window.__phase15cCalls), [])
  assert.equal(await denialPage.getByRole('heading', { level: 1 }).textContent(), 'Access denied')
  await denialPage.close()

  process.stdout.write('Phase 15C administrator browser check passed\n')
} finally {
  await browser.close()
  await server.close()
}
