import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5178'

const routeGroups = [
  ['admin', '/admin', 'Administrator home'],
  ['admin', '/admin/organization', 'Organization'],
  ['admin', '/admin/people', 'People'],
  ['admin', '/admin/leave', 'Leave'],
  ['admin', '/admin/attendance', 'Attendance'],
  ['admin', '/admin/roster', 'Roster'],
  ['admin', '/admin/payroll', 'Payroll'],
  ['admin', '/admin/records', 'Records'],
  ['admin', '/admin/development', 'Development'],
  ['admin', '/admin/reports', 'Reports'],
  ['manager', '/manager', 'Manager home'],
  ['manager', '/manager/team', 'Team'],
  ['manager', '/manager/leave', 'Leave'],
  ['manager', '/manager/time', 'Time'],
  ['manager', '/manager/expenses', 'Expenses'],
  ['manager', '/manager/development', 'Development'],
  ['manager', '/manager/requests', 'Requests'],
  ['employee', '/employee', 'Employee home'],
  ['employee', '/employee/profile', 'Profile'],
  ['employee', '/employee/leave', 'Leave'],
  ['employee', '/employee/time', 'Time'],
  ['employee', '/employee/pay', 'Pay'],
  ['employee', '/employee/records', 'Records'],
  ['employee', '/employee/development', 'Development'],
  ['employee', '/employee/requests', 'Requests'],
]

async function mount(page, role, route) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ role: accountRole, route: pathName }) => {
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

async function assertNamedControls(page, route) {
  const unnamed = await page.locator('button, a, input, select, textarea').evaluateAll((elements) => (
    elements.filter((element) => {
      const label = element.labels?.[0]?.textContent
      const name = element.getAttribute('aria-label')
        || element.getAttribute('aria-labelledby')
        || label
        || element.textContent
        || element.getAttribute('title')
      return !String(name ?? '').trim()
    }).map((element) => element.outerHTML.slice(0, 160))
  ))
  assert.deepEqual(unnamed, [], `${route} has unnamed controls`)
}

async function assertContrast(page, route) {
  const failures = await page.locator('.page-heading p, .portal-navigation a, button').evaluateAll((elements) => {
    const rgb = (value) => {
      const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
      return match ? match.slice(1).map(Number) : null
    }
    const luminance = (color) => color.map((part) => {
      const value = part / 255
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
    }).reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0)
    const background = (element) => {
      for (let current = element; current; current = current.parentElement) {
        const value = getComputedStyle(current).backgroundColor
        if (value && value !== 'rgba(0, 0, 0, 0)' && value !== 'transparent') return rgb(value)
      }
      return rgb(getComputedStyle(document.documentElement).backgroundColor)
    }
    return elements.filter((element) => {
      if (!element.checkVisibility() || element.disabled) return false
      const foreground = rgb(getComputedStyle(element).color)
      const backdrop = background(element)
      if (!foreground || !backdrop) return false
      const light = Math.max(luminance(foreground), luminance(backdrop))
      const dark = Math.min(luminance(foreground), luminance(backdrop))
      return (light + 0.05) / (dark + 0.05) < 4.5
    }).map((element) => ({
      contrast: getComputedStyle(element).color,
      html: element.outerHTML.slice(0, 160),
    }))
  })
  assert.deepEqual(failures, [], `${route} has low-contrast text controls`)
}

async function assertFocusAndMotion(page, route) {
  assert.equal(await page.evaluate(() => document.activeElement?.tagName), 'H1')
  await page.keyboard.press('Tab')
  const focused = page.locator(':focus')
  assert.equal(await focused.count(), 1, `${route} has no next keyboard target`)
  const outline = await focused.evaluate((element) => getComputedStyle(element).outlineStyle)
  assert.notEqual(outline, 'none', `${route} hides keyboard focus`)
  assert.equal(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches), true)
  const moving = await page.locator('*').evaluateAll((elements) => elements.filter((element) => {
    const style = getComputedStyle(element)
    return style.animationDuration !== '0s' || style.transitionDuration !== '0s'
  }).map((element) => element.tagName))
  assert.deepEqual(moving, [], `${route} keeps motion under reduced-motion preference`)
}

async function assertZoom(page, client) {
  await client.send('Emulation.setPageScaleFactor', { pageScaleFactor: 2 })
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  assert.ok(overflow <= 1, `200 percent zoom creates ${overflow}px of page overflow`)
  await client.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 })
}

const server = await createServer({
  configFile,
  envFile: false,
  server: { host: '127.0.0.1', port: 5178, strictPort: true },
})
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  for (const [role, route, heading] of routeGroups) {
    const context = await browser.newContext({
      reducedMotion: 'reduce',
      viewport: { width: 1280, height: 900 },
    })
    const page = await context.newPage()
    const client = await context.newCDPSession(page)
    await mount(page, role, route)
    assert.equal(new URL(page.url()).pathname, route)
    assert.equal(await page.getByRole('heading', { level: 1 }).textContent(), heading)
    assert.equal(await page.locator('main').count(), 1)
    assert.equal(await page.getByRole('navigation', { name: 'Primary' }).count(), 1)
    assert.equal(await page.getByRole('link', { name: heading }).getAttribute('aria-current'), 'page')
    await assertNamedControls(page, route)
    await assertContrast(page, route)
    await assertFocusAndMotion(page, route)
    await assertZoom(page, client)
    await context.close()
  }

  const keyboardContext = await browser.newContext({ reducedMotion: 'reduce' })
  const keyboardPage = await keyboardContext.newPage()
  await mount(keyboardPage, 'admin', '/admin')
  const firstFocusable = await keyboardPage.evaluate(() => (
    [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')]
      .find((element) => !element.disabled && element.tabIndex >= 0)?.className
  ))
  assert.equal(firstFocusable, 'skip-link')
  await keyboardPage.locator('.skip-link').focus()
  assert.equal(await keyboardPage.locator(':focus').getAttribute('class'), 'skip-link')
  await keyboardPage.keyboard.press('Enter')
  assert.equal(await keyboardPage.evaluate(() => document.activeElement?.id), 'portal-content')

  const toggle = keyboardPage.getByRole('button', { name: /^Notifications/ })
  await toggle.click()
  const dialog = keyboardPage.getByRole('dialog', { name: 'Notification inbox' })
  await dialog.waitFor()
  assert.equal(await dialog.locator(':focus').count(), 1)
  await keyboardPage.keyboard.press('Escape')
  assert.equal(await dialog.count(), 0)
  assert.equal(await toggle.evaluate((element) => element === document.activeElement), true)
  await keyboardContext.close()

  const recoveryContext = await browser.newContext({ reducedMotion: 'reduce' })
  const recoveryPage = await recoveryContext.newPage()
  await mount(recoveryPage, 'employee', '/employee/profile')
  await recoveryPage.getByRole('button', { name: 'Save contact details' }).click()
  await recoveryPage.getByRole('status').filter({ hasText: 'Contact details could not be saved.' }).waitFor()
  await recoveryPage.getByRole('link', { name: 'Leave' }).click()
  await recoveryPage.locator('[data-employee-route="/employee/leave"]').waitFor()
  assert.equal(await recoveryPage.evaluate(() => document.activeElement?.tagName), 'H1')
  await recoveryContext.close()

  process.stdout.write('Phase 15F route accessibility and recovery check passed for 25 route groups.\n')
} finally {
  await browser.close()
  await server.close()
}
