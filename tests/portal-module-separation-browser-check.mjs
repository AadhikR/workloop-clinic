import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5181'

async function mount(page, role, route) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ accountRole, pathName }) => {
    if (accountRole === 'admin') {
      const harness = await import('/tests/phase-15c-harness.jsx')
      harness.mountPhase15CAdministrator({ path: pathName })
      return
    }
    const harness = await import('/tests/phase-15d-harness.jsx')
    harness.mountPhase15DManager({ path: pathName })
  }, { accountRole: role, pathName: route })
  await page.locator('[data-route-state="ready"]').waitFor()
}

async function assertAligned(page) {
  const edges = await page.evaluate(() => {
    const header = document.querySelector('.page-header.portal-header').getBoundingClientRect()
    const panel = document.querySelector('.portal-route > section').getBoundingClientRect()
    return { headerLeft: header.left, headerRight: header.right, panelLeft: panel.left, panelRight: panel.right }
  })
  assert.ok(Math.abs(edges.headerLeft - edges.panelLeft) <= 1, JSON.stringify(edges))
  assert.ok(Math.abs(edges.headerRight - edges.panelRight) <= 1, JSON.stringify(edges))
}

const server = await createServer({ configFile, envFile: false, server: { port: 5181 } })
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  const adminCases = [
    ['/admin/payroll', '#payroll-title', ['#expenses-title', '#advances-title']],
    ['/admin/expenses', '#expenses-title', ['#payroll-title', '#advances-title']],
    ['/admin/advances', '#advances-title', ['#payroll-title', '#expenses-title']],
  ]
  for (const [route, expected, absent] of adminCases) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
    await mount(page, 'admin', route)
    await page.locator(expected).waitFor()
    for (const selector of absent) assert.equal(await page.locator(selector).count(), 0)
    await assertAligned(page)
    await page.close()
  }

  const managerCases = [
    ['/manager/expense-queue', 'Expense Queue'],
    ['/manager/expenses', 'Expenses'],
    ['/manager/advances', 'Salary advances'],
  ]
  for (const [route, moduleHeading] of managerCases) {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
    await mount(page, 'manager', route)
    await page.getByRole('heading', { name: moduleHeading, exact: true }).last().waitFor()
    await assertAligned(page)
    if (route === '/manager/expense-queue') {
      assert.equal(await page.getByRole('heading', { name: 'Submit an expense claim' }).count(), 0)
    }
    if (route === '/manager/expenses') {
      assert.equal(await page.getByRole('heading', { name: 'Direct-report queue' }).count(), 0)
    }
    await page.close()
  }
} finally {
  await browser.close()
  await server.close()
}

console.log('Portal module separation and panel alignment passed.')
