import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const configFile = path.join(root, 'vite.config.js')
const baseUrl = 'http://127.0.0.1:5181'
const evidenceDirectory = path.join(root, 'docs', 'migration', 'phase-15', 'evidence')

async function mount(page, role, route) {
  await page.goto(baseUrl)
  await page.evaluate(async ({ accountRole, pathName }) => {
    const modules = {
      admin: '/tests/phase-15c-harness.jsx',
      employee: '/tests/phase-15e-harness.jsx',
    }
    const exports = {
      admin: 'mountPhase15CAdministrator',
      employee: 'mountPhase15EEmployee',
    }
    const harness = await import(modules[accountRole])
    harness[exports[accountRole]]({ path: pathName })
  }, { accountRole: role, pathName: route })
  await page.locator('[data-route-state="ready"]').waitFor()
}

const server = await createServer({
  configFile,
  envFile: false,
  server: { host: '127.0.0.1', port: 5181, strictPort: true },
})
await server.listen()
const browser = await chromium.launch({ headless: true })

try {
  const desktop = await browser.newPage({ viewport: { width: 1880, height: 900 } })
  await mount(desktop, 'admin', '/admin')
  const desktopLayout = await desktop.evaluate(() => {
    const style = (selector) => getComputedStyle(document.querySelector(selector))
    const rect = (selector) => document.querySelector(selector).getBoundingClientRect()
    return {
      activeBackground: style('.nav-item[aria-current="page"]').backgroundImage,
      bodyBackground: style('body').backgroundColor,
      cardRadius: style('.card').borderRadius,
      headerTop: rect('.page-header').top,
      sidebarBackground: style('.sidebar').backgroundColor,
      sidebarLeft: rect('.sidebar').left,
      sidebarWidth: rect('.sidebar').width,
    }
  })
  assert.equal(desktopLayout.sidebarWidth, 240)
  assert.equal(desktopLayout.sidebarLeft, 12)
  assert.equal(desktopLayout.headerTop, 12)
  assert.equal(desktopLayout.sidebarBackground, 'rgb(8, 18, 46)')
  assert.equal(desktopLayout.bodyBackground, 'rgb(238, 242, 247)')
  assert.equal(desktopLayout.cardRadius, '22px')
  assert.match(desktopLayout.activeBackground, /linear-gradient/)
  await desktop.screenshot({ path: path.join(evidenceDirectory, 'phase15g-restored-desktop.png') })
  await desktop.close()

  const mobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await mount(mobile, 'employee', '/employee/records')
  const mobileLayout = await mobile.evaluate(() => ({
    marginLeft: getComputedStyle(document.querySelector('.main-content')).marginLeft,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    sidebarPosition: getComputedStyle(document.querySelector('.sidebar')).position,
    visibleNavigation: document.querySelector('.portal-navigation').checkVisibility(),
  }))
  assert.equal(mobileLayout.marginLeft, '0px')
  assert.ok(mobileLayout.overflow <= 1, `mobile layout overflows by ${mobileLayout.overflow}px`)
  assert.equal(mobileLayout.sidebarPosition, 'relative')
  assert.equal(mobileLayout.visibleNavigation, true)
  await mobile.screenshot({ path: path.join(evidenceDirectory, 'phase15g-restored-mobile.png'), fullPage: true })
  await mobile.close()

  process.stdout.write('Phase 15G restored visual layout passed desktop and mobile checks.\n')
} finally {
  await browser.close()
  await server.close()
}
