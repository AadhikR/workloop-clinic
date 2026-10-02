import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5177'
const staleBranchId = 'b2000000-0000-4000-8000-000000000099'

const routes = [
  ['/employee', 'Employee home', '[data-dashboard-kind="self"]', '/api/v1/dashboards/self'],
  ['/employee/profile', 'Profile', '.employee-directory', '/api/v1/employees/self'],
  ['/employee/leave', 'Leave', '#leave-overview-title', '/api/v1/leave/balances/self'],
  ['/employee/time', 'Time', '#personal-attendance-title', '/api/v1/attendance/me/today'],
  ['/employee/pay', 'Pay', '#payslips-title', '/api/v1/payslips/self'],
  ['/employee/records', 'Records', '#records-benefits-title', '/api/v1/employee-documents/self'],
  ['/employee/development', 'Development', '#development-assets-title', '/api/v1/assets/self'],
  ['/employee/requests', 'Requests', '#letter-requests-title', '/api/v1/requests/self'],
]

async function mount(page, options, forbidden = false) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ forbidden: useForbidden, values }) => {
    const harness = await import('/tests/phase-15e-harness.jsx')
    if (useForbidden) harness.mountPhase15EForbidden(values)
    else harness.mountPhase15EEmployee(values)
  }, { forbidden, values: options })
}

const server = await createServer({ configFile, envFile: false, server: { port: 5177 } })
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
    await page.waitForFunction(
      (requestPath) => window.__phase15eCalls.some((call) => call.path.startsWith(requestPath)),
      expectedRequest,
      { timeout: 5000 },
    )
    if (route !== '/employee') {
      assert.equal(await page.locator(`[data-employee-route="${route}"]`).count(), 1)
    }
    assert.equal(await page.locator('[data-administrator-route], [data-manager-route]').count(), 0)
    const calls = await page.evaluate(() => window.__phase15eCalls)
    assert.equal(calls.some((call) => call.branch !== null), false)
    assert.equal(calls.some((call) => /manager-queue|direct-reports|\/employees\?|\/payroll-runs|\/clinical-incidents|\/reports\//.test(call.path)), false)
    assert.deepEqual(await page.evaluate(() => window.__phase15eUnhandled), [])
    await page.close()
  }

  const profilePage = await browser.newPage()
  await mount(profilePage, { path: '/employee/profile' })
  await profilePage.getByText('Synthetic Employee', { exact: true }).waitFor()
  assert.equal(await profilePage.locator('[data-employee-self-contact-form]').count(), 1)
  assert.equal(await profilePage.getByText('Direct reports', { exact: true }).count(), 0)

  await profilePage.getByRole('link', { name: 'Leave' }).click()
  await profilePage.locator('[data-employee-route="/employee/leave"]').waitFor()
  await profilePage.goBack()
  await profilePage.locator('[data-employee-route="/employee/profile"]').waitFor()
  assert.equal(await profilePage.evaluate(() => document.activeElement?.tagName), 'H1')
  await profilePage.getByRole('button', { name: 'Sign out' }).last().click()
  assert.equal(await profilePage.evaluate(() => window.__phase15eLoggedOut), true)
  await profilePage.close()

  for (const forbiddenPath of ['/admin/people', '/manager/expenses']) {
    const denialPage = await browser.newPage()
    await mount(denialPage, { path: forbiddenPath }, true)
    await denialPage.locator('[data-route-state="forbidden"]').waitFor()
    assert.deepEqual(await denialPage.evaluate(() => window.__phase15eCalls), [])
    assert.equal(await denialPage.getByRole('heading', { level: 1 }).textContent(), 'Access denied')
    assert.equal(await denialPage.getByText('Employee directory', { exact: true }).count(), 0)
    await denialPage.close()
  }

  const unknownPage = await browser.newPage()
  await mount(unknownPage, { path: '/employee/pay/b2000000-0000-4000-8000-000000000099' }, true)
  await unknownPage.locator('[data-route-state="not-found"]').waitFor()
  assert.deepEqual(await unknownPage.evaluate(() => window.__phase15eCalls), [])
  assert.equal(await unknownPage.getByRole('heading', { level: 1 }).textContent(), 'Page not found')
  assert.equal((await unknownPage.textContent('body')).includes('b2000000-0000-4000-8000-000000000099'), false)
  await unknownPage.close()

  process.stdout.write('Phase 15E employee browser check passed\n')
} finally {
  await browser.close()
  await server.close()
}
