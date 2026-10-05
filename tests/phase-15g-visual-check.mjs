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
  if (route === '/admin/payroll') await page.locator('.payroll-history-card').waitFor()
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

  const review = await browser.newPage({ viewport: { width: 1644, height: 1000 } })
  await review.goto(baseUrl)
  await review.evaluate(async () => {
    const fixture = await import('/tests/phase-15g-payroll-fixture.jsx')
    fixture.mountPayrollReview()
  })
  await review.getByRole('button', { name: 'Open 2026-10', exact: true }).click()
  await review.getByRole('heading', { name: 'Employee Salary Entries' }).waitFor()
  await review.getByText('All changes saved', { exact: true }).waitFor()
  await review.waitForFunction(() => Math.abs(document.querySelector('.nav-pill').getBoundingClientRect().top - document.querySelector('.nav-item[aria-current="page"]').getBoundingClientRect().top) < 1)
  const populatedLayout = await review.evaluate(() => {
    const rect = (selector) => document.querySelector(selector).getBoundingClientRect()
    const table = document.querySelector('.payroll-table table')
    return {
      columnCounts: [...table.querySelectorAll('tr')].map((row) => [...row.children].reduce((sum, cell) => sum + cell.colSpan, 0)),
      fieldTops: [...document.querySelectorAll('.payroll-meta-grid input')].map((input) => input.getBoundingClientRect().top),
      statSize: getComputedStyle(document.querySelector('.payroll-summary-grid .stat-value')).fontSize,
      statLabelCase: getComputedStyle(document.querySelector('.stat-label')).textTransform,
      formHeight: rect('.payroll-run-details').height,
      tableOverflow: rect('.payroll-table').right - rect('.payroll-entries-card').right,
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      badgeBorder: getComputedStyle(document.querySelector('.payroll-detail-heading .badge')).borderTopStyle,
      rawCodesVisible: /payroll_input_not_ready|attendance_input_not_ready|roster_input_not_ready/.test(document.body.innerText),
      issueCount: document.querySelectorAll('.payroll-validation-summary').length,
    }
  })
  assert.deepEqual(populatedLayout.columnCounts, [15, 15, 15, 15])
  assert.equal(new Set(populatedLayout.fieldTops).size, 1)
  assert.equal(populatedLayout.statSize, '28px')
  assert.equal(populatedLayout.statLabelCase, 'uppercase')
  assert.ok(populatedLayout.formHeight < 190)
  assert.ok(populatedLayout.tableOverflow <= 1)
  assert.ok(populatedLayout.pageOverflow <= 1)
  assert.equal(populatedLayout.badgeBorder, 'solid')
  assert.equal(populatedLayout.rawCodesVisible, false)
  assert.equal(populatedLayout.issueCount, 1)
  assert.equal(await review.getByRole('button', { name: 'Submit for Approval' }).isEnabled(), false)
  await review.screenshot({ path: path.join(evidenceDirectory, 'phase15g-payroll-review-desktop-final.png'), fullPage: true })

  await review.getByRole('button', { name: 'Review issues' }).click()
  assert.equal(await review.locator('.payroll-readiness-list li').count(), 2)
  await review.keyboard.press('Escape')
  assert.equal(await review.getByRole('dialog').count(), 0)
  await review.getByRole('button', { name: 'Alex Morgan', exact: true }).click()
  await review.getByRole('heading', { name: 'Alex Morgan', exact: true }).waitFor()
  assert.match(await review.locator('.payroll-net-result').innerText(), /12,750\.00/)
  assert.ok(await review.locator('.payroll-detail-drawer').isVisible())
  await review.screenshot({ path: path.join(evidenceDirectory, 'phase15g-payroll-breakdown.png') })
  await review.keyboard.press('Escape')
  await review.getByRole('textbox', { name: 'Search payroll employees' }).fill('Sam')
  assert.equal(await review.locator('.payroll-table tbody tr').count(), 1)
  assert.match(await review.locator('.payroll-table tfoot').innerText(), /25,500\.00/)
  await review.getByRole('textbox', { name: 'Search payroll employees' }).fill('')
  await review.getByRole('spinbutton', { name: 'Alex Morgan increment', exact: true }).fill('125')
  assert.match(await review.locator('.payroll-grand-total .stat-value').innerText(), /25,625\.00/)
  assert.equal(await review.getByRole('button', { name: 'Refresh inputs', exact: true }).isEnabled(), false)
  await review.getByRole('combobox', { name: 'Filter payroll employees' }).selectOption('changed')
  assert.equal(await review.locator('.payroll-table tbody tr').count(), 1)
  await review.getByRole('combobox', { name: 'Filter payroll employees' }).selectOption('all')
  await review.getByRole('checkbox', { name: 'Include Sam Taylor' }).uncheck()
  assert.match(await review.locator('.payroll-grand-total .stat-value').innerText(), /12,875\.00/)
  await review.getByRole('button', { name: '← Back', exact: true }).click()
  await review.getByRole('button', { name: 'Keep editing' }).click()
  await review.getByRole('button', { name: 'Save Draft', exact: true }).click()
  await review.getByText('Payroll entries saved.', { exact: true }).waitFor()
  const saveRequest = await review.evaluate(() => window.__phase15cRequests.find((request) => request.options?.method === 'PUT'))
  assert.equal(saveRequest.options.json.entries[0].increment, '125.00')
  assert.equal(saveRequest.options.json.entries[1].excluded, true)
  assert.equal(saveRequest.options.json.entries[0].preview.netPay, '12875.00')
  await review.close()

  const payrollMobile = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await payrollMobile.goto(baseUrl)
  await payrollMobile.evaluate(async () => {
    const fixture = await import('/tests/phase-15g-payroll-fixture.jsx')
    fixture.mountPayrollReview({ blocked: false })
  })
  await payrollMobile.getByRole('button', { name: 'Open 2026-10', exact: true }).click()
  await payrollMobile.getByRole('heading', { name: 'Employee Salary Entries' }).waitFor()
  await payrollMobile.getByText('All changes saved', { exact: true }).waitFor()
  const mobileReview = await payrollMobile.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    formColumns: getComputedStyle(document.querySelector('.payroll-meta-grid')).gridTemplateColumns.split(' ').length,
    tableWidth: document.querySelector('.payroll-table').clientWidth,
    scrollWidth: document.querySelector('.payroll-table').scrollWidth,
    sidebarWidth: document.querySelector('.sidebar').getBoundingClientRect().width,
    pillVisible: document.querySelector('.nav-pill').checkVisibility(),
    skipLinkBottom: document.querySelector('.skip-link').getBoundingClientRect().bottom,
  }))
  assert.ok(mobileReview.overflow <= 1)
  assert.ok(mobileReview.skipLinkBottom <= 0)
  assert.equal(mobileReview.formColumns, 1)
  assert.equal(mobileReview.sidebarWidth, 370)
  assert.equal(mobileReview.pillVisible, false)
  assert.ok(mobileReview.scrollWidth > mobileReview.tableWidth)
  assert.equal(await payrollMobile.getByRole('button', { name: 'Submit for Approval' }).isEnabled(), true)
  await payrollMobile.screenshot({ path: path.join(evidenceDirectory, 'phase15g-payroll-review-mobile-viewport.png') })
  await payrollMobile.getByRole('button', { name: 'Add allowance for Alex Morgan' }).click()
  await payrollMobile.getByRole('dialog').waitFor()
  const modalOverflow = await payrollMobile.evaluate(() => document.querySelector('.modal').getBoundingClientRect().right > innerWidth)
  assert.equal(modalOverflow, false)
  await payrollMobile.keyboard.press('Escape')
  await payrollMobile.close()

  const leaveReview = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await leaveReview.goto(baseUrl)
  await leaveReview.evaluate(async () => {
    const fixture = await import('/tests/phase-15g-payroll-fixture.jsx')
    fixture.mountLeaveReview()
  })
  await leaveReview.getByRole('button', { name: 'Request Leave', exact: true }).waitFor()
  await leaveReview.getByRole('tab', { name: 'Balances', exact: true }).click()
  assert.equal(await leaveReview.getByRole('heading', { name: 'Request history' }).count(), 0)
  await leaveReview.getByRole('tab', { name: 'Calendar', exact: true }).click()
  assert.equal(await leaveReview.getByRole('grid').count(), 1)
  await leaveReview.getByRole('button', { name: 'Request Leave', exact: true }).click()
  await leaveReview.getByRole('dialog').waitFor()
  assert.ok(await leaveReview.getByRole('button', { name: 'Submit request', exact: true }).isVisible())
  await leaveReview.keyboard.press('Escape')
  await leaveReview.getByRole('tab', { name: 'Settings', exact: true }).click()
  await leaveReview.locator('section[aria-label="Leave configuration"]').waitFor()
  await leaveReview.getByRole('tab', { name: 'Overview', exact: true }).click()
  assert.equal(await leaveReview.getByRole('tab', { name: 'Overview', exact: true }).getAttribute('aria-selected'), 'true')
  assert.equal(await leaveReview.getByRole('grid').isVisible(), false)
  assert.equal(await leaveReview.locator('section[aria-label="Leave configuration"]').isVisible(), false)
  await leaveReview.getByRole('tab', { name: 'Calendar', exact: true }).click()
  assert.ok(await leaveReview.getByRole('grid').isVisible())
  await leaveReview.getByRole('tab', { name: 'Overview', exact: true }).click()
  await leaveReview.screenshot({ path: path.join(evidenceDirectory, 'phase15g-leave-workspace.png') })
  await leaveReview.close()

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
  await mobile.screenshot({ path: path.join(evidenceDirectory, 'phase15g-redesigned-employee-mobile.png'), fullPage: true })
  await mobile.close()

  process.stdout.write('Phase 15G restored visual layout passed desktop and mobile checks.\n')
} finally {
  await browser.close()
  await server.close()
}
