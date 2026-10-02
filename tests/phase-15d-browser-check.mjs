import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5176'
const staleBranchId = 'b2000000-0000-4000-8000-000000000099'

const routes = [
  ['/manager', 'Manager home', '[data-dashboard-kind="self"]', '/api/v1/dashboards/self'],
  ['/manager/team', 'Team', '.employee-directory', '/api/v1/employees/direct-reports'],
  ['/manager/leave', 'Leave', '#leave-overview-title', '/api/v1/leave/approvals/queue?'],
  ['/manager/time', 'Time', '#personal-schedule-title', '/api/v1/roster/schedules/self?'],
  ['/manager/expenses', 'Expenses', '#expenses-title', '/api/v1/expenses/manager-queue'],
  ['/manager/development', 'Development', '#development-assets-title', '/api/v1/appraisals/direct-reports'],
  ['/manager/requests', 'Requests', '#advances-title', '/api/v1/advances/self'],
]

async function mount(page, options, denied = false) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ denied: useDenied, values }) => {
    const harness = await import('/tests/phase-15d-harness.jsx')
    if (useDenied) harness.mountPhase15DAdminRoute(values)
    else harness.mountPhase15DManager(values)
  }, { denied, values: options })
}

const server = await createServer({ configFile, envFile: false, server: { port: 5176 } })
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  for (const [route, heading, evidenceSelector, expectedRequest] of routes) {
    const page = await browser.newPage()
    await mount(page, { path: route, storedBranchId: staleBranchId })
    await page.locator('[data-route-state="ready"]').waitFor()
    assert.equal(new URL(page.url()).pathname, route)
    assert.equal(await page.getByRole('heading', { level: 1 }).textContent(), heading)
    assert.equal(await page.evaluate(() => document.activeElement?.tagName), 'H1')
    assert.equal(await page.locator('[data-selected-branch-name]').textContent(), 'Dubai clinic')
    assert.equal(await page.getByRole('button', { name: 'Change branch' }).count(), 0)
    assert.equal(await page.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
    await page.locator(evidenceSelector).first().waitFor()
    try {
      await page.waitForFunction(
        (requestPath) => window.__phase15dCalls.some((call) => call.path.startsWith(requestPath)),
        expectedRequest,
        { timeout: 5000 },
      )
    } catch {
      const calls = await page.evaluate(() => window.__phase15dCalls)
      throw new Error(`${route} did not call ${expectedRequest}: ${JSON.stringify(calls)}`)
    }
    if (route !== '/manager') {
      assert.equal(await page.locator(`[data-manager-route="${route}"]`).count(), 1)
    }
    assert.equal(await page.locator('[data-administrator-route]').count(), 0)
    const calls = await page.evaluate(() => window.__phase15dCalls)
    assert.equal(calls.some((call) => call.branch !== null), false)
    assert.equal(calls.some((call) => /payroll|wps|departments|clinical-incidents|offboarding|reports\//.test(call.path)), false)
    await page.close()
  }

  const teamPage = await browser.newPage()
  await mount(teamPage, { path: '/manager/team' })
  await teamPage.getByText('Synthetic Manager', { exact: true }).waitFor()
  await teamPage.getByText('Synthetic Direct Report', { exact: true }).waitFor()
  const teamCalls = await teamPage.evaluate(() => window.__phase15dCalls)
  assert.ok(teamCalls.some((call) => call.path === '/api/v1/employees/self' && call.branch === null))
  assert.ok(teamCalls.some((call) => call.path === '/api/v1/employees/direct-reports' && call.branch === null))
  assert.equal(teamCalls.some((call) => call.path.startsWith('/api/v1/employees?')), false)

  await teamPage.getByRole('link', { name: 'Leave' }).click()
  await teamPage.locator('[data-manager-route="/manager/leave"]').waitFor()
  await teamPage.goBack()
  await teamPage.locator('[data-manager-route="/manager/team"]').waitFor()
  assert.equal(await teamPage.evaluate(() => document.activeElement?.tagName), 'H1')
  await teamPage.getByRole('button', { name: 'Sign out' }).last().click()
  assert.equal(await teamPage.evaluate(() => window.__phase15dLoggedOut), true)
  await teamPage.close()

  const denialPage = await browser.newPage()
  await mount(denialPage, { path: '/admin/payroll' }, true)
  await denialPage.locator('[data-route-state="forbidden"]').waitFor()
  assert.deepEqual(await denialPage.evaluate(() => window.__phase15dCalls), [])
  assert.equal(await denialPage.getByRole('heading', { level: 1 }).textContent(), 'Access denied')
  assert.equal(await denialPage.getByText('WPS', { exact: true }).count(), 0)
  await denialPage.close()

  process.stdout.write('Phase 15D manager browser check passed\n')
} finally {
  await browser.close()
  await server.close()
}
