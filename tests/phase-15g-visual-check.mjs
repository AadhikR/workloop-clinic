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
      manager: '/tests/phase-15d-harness.jsx',
    }
    const exports = {
      admin: 'mountPhase15CAdministrator',
      employee: 'mountPhase15EEmployee',
      manager: 'mountPhase15DManager',
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
  await mount(desktop, 'admin', '/admin/payroll')
  const desktopLayout = await desktop.evaluate(() => {
    const style = (selector) => getComputedStyle(document.querySelector(selector))
    const rect = (selector) => document.querySelector(selector).getBoundingClientRect()
    return {
      buttonPadding: style('.module-toolbar button').padding,
      bodyBackground: style('body').backgroundColor,
      cardRadius: style('.payroll-history-card').borderRadius,
      headingSize: style('.module-toolbar h2').fontSize,
      headerTop: rect('.module-toolbar').top,
      firstStatTop: rect('.payroll-list-stats .stat-card:first-child').top,
      secondStatTop: rect('.payroll-list-stats .stat-card:nth-child(2)').top,
      panelLeft: rect('.payroll-history-card').left,
      panelRight: rect('.payroll-history-card').right,
      pillBackground: style('.nav-pill').backgroundImage,
      headerLeft: rect('.module-toolbar').left,
      headerRight: rect('.module-toolbar').right,
      sidebarBackground: style('.sidebar').backgroundColor,
      sidebarLeft: rect('.sidebar').left,
      sidebarWidth: rect('.sidebar').width,
      wpsVisibleByDefault: document.querySelector('#wps-nafis-title') !== null,
    }
  })
  assert.equal(desktopLayout.sidebarWidth, 240)
  assert.equal(desktopLayout.sidebarLeft, 12)
  assert.ok(desktopLayout.headerTop > 12)
  assert.equal(desktopLayout.sidebarBackground, 'rgb(8, 18, 46)')
  assert.equal(desktopLayout.bodyBackground, 'rgb(238, 242, 247)')
  assert.equal(desktopLayout.cardRadius, '22px')
  assert.equal(desktopLayout.headingSize, '18px')
  assert.equal(desktopLayout.buttonPadding, '8px 16px')
  assert.equal(desktopLayout.firstStatTop, desktopLayout.secondStatTop)
  assert.equal(desktopLayout.wpsVisibleByDefault, false)
  assert.ok(Math.abs(desktopLayout.headerLeft - desktopLayout.panelLeft) <= 1)
  assert.ok(Math.abs(desktopLayout.headerRight - desktopLayout.panelRight) <= 1)
  assert.match(desktopLayout.pillBackground, /linear-gradient/)
  await desktop.screenshot({ path: path.join(evidenceDirectory, 'phase15g-restored-desktop.png') })
  await desktop.close()

  const manager = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await mount(manager, 'manager', '/manager/expenses')
  const managerLayout = await manager.evaluate(() => ({
    panelRadius: getComputedStyle(document.querySelector('.portal-route > section')).borderRadius,
    sidebarWidth: document.querySelector('.sidebar').getBoundingClientRect().width,
  }))
  assert.equal(managerLayout.sidebarWidth, 228)
  assert.equal(managerLayout.panelRadius, '22px')
  await manager.close()

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
  assert.equal(mobileLayout.sidebarPosition, 'fixed')
  assert.equal(mobileLayout.visibleNavigation, true)
  await mobile.screenshot({ path: path.join(evidenceDirectory, 'phase15g-restored-mobile.png'), fullPage: true })
  await mobile.close()

  process.stdout.write('Phase 15G restored visual layout passed desktop and mobile checks.\n')
} finally {
  await browser.close()
  await server.close()
}
