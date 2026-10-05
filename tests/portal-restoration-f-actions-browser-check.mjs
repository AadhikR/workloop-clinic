import assert from 'node:assert/strict'
import path from 'node:path'
import { mkdir } from 'node:fs/promises'
import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const evidence = path.resolve(process.env.PORTAL_RESTORATION_EVIDENCE_DIR ?? 'docs/migration/phase-15/evidence/restoration-f/actions-f')
const server = await createServer({ envFile: false, server: { host: '127.0.0.1', port: 5190, strictPort: true } })
await server.listen()
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
page.setDefaultTimeout(15000)
page.setDefaultNavigationTimeout(45000)
const errors = []
page.on('pageerror', (error) => errors.push(error.message))
await mkdir(evidence, { recursive: true })
const mount = async (part, module, route) => {
  await page.goto(`http://127.0.0.1:5190/tests/portal-restoration-f.html?${new URLSearchParams({ part, module, path: route, role: 'admin' })}`)
  await page.locator('[data-route-state="ready"]').waitFor()
  await page.waitForFunction(() => window.__restorationFPending === 0)
}
const reject = (code) => page.evaluate((value) => { window.__restorationFReject = value }, code)
const capture = (name) => page.screenshot({ path: path.join(evidence, `${name}.png`), fullPage: true })
const attempts = (suffix) => page.evaluate((value) => window.__restorationFRequests.filter((request) => request.path.endsWith(value)), suffix)
try {
  await mount('d', 'clinical', '/admin/clinical-dashboard')
  for (const group of ['activeStaff', 'credentialCompliance', 'coverage', 'probation', 'newJoiners', 'birthdays', 'onLeaveToday', 'pendingLeave', 'onDutyNow']) {
    await page.locator(`[data-card-code="${group}"] button`).click()
    const details = page.locator('.clinical-workforce-details')
    await details.getByRole('cell', { name: 'Alex Morgan', exact: true }).waitFor()
    assert.equal(await details.locator('tbody tr').count(), ['activeStaff', 'credentialCompliance', 'coverage'].includes(group) ? 2 : 1)
    await capture(`clinical-${group}`)
  }
  for (const group of ['credentialsExpiring', 'credentialsExpired']) {
    await page.locator(`[data-card-code="${group}"] button`).click()
    await page.locator('.clinical-credential-details').getByRole('cell', { name: 'Alex Morgan', exact: true }).waitFor()
    await capture(`clinical-${group}`)
  }
  for (const [part, module, route, kind] of [['a', 'appraisals', '/admin/appraisals', 'appraisal'], ['a', 'incidents', '/admin/incidents', 'incident_report'], ['d', 'expenses', '/admin/expenses', 'expense_claim']]) {
    await mount(part, module, route)
    if (kind === 'appraisal') await page.getByRole('button', { name: 'Reviews', exact: true }).click()
    await page.getByRole('button', { name: 'Remove', exact: true }).click()
    const removal = page.getByRole('dialog', { name: 'Remove record', exact: true })
    await reject('conflict')
    await removal.getByRole('button', { name: 'Remove', exact: true }).click()
    await removal.getByRole('alert').waitFor()
    await capture(`${kind}-conflict`)
    await removal.getByRole('button', { name: 'Remove', exact: true }).click()
    await removal.waitFor({ state: 'detached' })
    const writes = await attempts('/archive')
    assert.deepEqual(writes.at(-1).options, writes.at(-2).options)
    await page.locator('.retained-records summary').click()
    await page.locator('.retained-records').getByRole('button', { name: 'Restore', exact: true }).click()
    const restore = page.getByRole('dialog', { name: 'Restore record', exact: true })
    await reject('unavailable')
    await restore.getByRole('button', { name: 'Restore', exact: true }).click()
    await restore.getByRole('alert').waitFor()
    await restore.getByRole('button', { name: 'Restore', exact: true }).click()
    await restore.waitFor({ state: 'detached' })
    const restores = await attempts('/restore')
    assert.deepEqual(restores.at(-1).options, restores.at(-2).options)
    await page.getByRole('button', { name: 'Remove', exact: true }).waitFor()
    await capture(`${kind}-restored`)
  }
  await mount('d', 'advances', '/admin/advances')
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  const cancellation = page.getByRole('dialog', { name: 'Cancel Pending Advance', exact: true })
  await reject('conflict')
  await cancellation.getByRole('button', { name: 'Cancel Pending Advance', exact: true }).click()
  await page.getByText('The source changed. Refresh and retry.', { exact: true }).waitFor()
  await cancellation.getByRole('button', { name: 'Cancel Pending Advance', exact: true }).click()
  await cancellation.waitFor({ state: 'detached' })
  const cancels = await attempts('/admin-cancel')
  assert.deepEqual(cancels.at(-1).options, cancels.at(-2).options)
  await page.getByRole('cell', { name: 'Cancelled', exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: 'Approve', exact: true }).count(), 0)
  await capture('advance-cancelled')
  await mount('a', 'training', '/admin/training')
  await page.getByRole('tab', { name: 'CME', exact: true }).click()
  await page.getByText('Contributing training records', { exact: true }).click()
  await page.getByText('Verified clinical course', { exact: true }).waitFor()
  assert.equal(await page.locator('.cme-contribution-list li').count(), 2)
  await capture('cme-contributors')
  assert.deepEqual(await page.evaluate(() => window.__restorationFUnhandled), [])
  assert.deepEqual(errors, [])
  console.log('Final restoration actions passed: all clinical groups, retained conflict and restore, cancellation replay, and CME contributors.')
} catch (error) {
  console.error(await page.locator('body').innerText())
  throw error
} finally { await browser.close(); await server.close() }
