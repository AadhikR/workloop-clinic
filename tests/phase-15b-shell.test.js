import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { HttpClientError } from '../src/http.js'
import { resolveStaffBranch } from '../src/organizationApi.js'
import {
  createBrowserNavigator,
  focusRouteHeading,
  portalRouteContracts,
  resolvePortalRoute,
  roleHome,
} from '../src/portalRoutes.js'
import { classifyAccountFailure } from '../src/portalSession.js'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const otherBranchId = 'b2000000-0000-4000-8000-000000000003'

function fakeBrowser(pathname = '/') {
  const listeners = new Map()
  const browser = {
    location: { pathname },
    history: {
      pushState(_state, _unused, path) { browser.location.pathname = path },
      replaceState(_state, _unused, path) { browser.location.pathname = path },
    },
    addEventListener(name, listener) { listeners.set(name, listener) },
    removeEventListener(name, listener) {
      if (listeners.get(name) === listener) listeners.delete(name)
    },
    emit(name) { listeners.get(name)?.() },
  }
  return browser
}

test('maps each server role to one home and denies cross-role navigation', () => {
  assert.equal(roleHome('admin'), '/admin')
  assert.equal(roleHome('manager'), '/manager')
  assert.equal(roleHome('employee'), '/employee')
  assert.throws(() => roleHome('owner'), /unsupported account role/i)

  assert.deepEqual(resolvePortalRoute('/', 'manager'), {
    kind: 'redirect', path: '/manager', title: 'Manager home',
  })
  assert.equal(resolvePortalRoute('/manager', 'manager').kind, 'home')
  assert.equal(resolvePortalRoute('/employee', 'manager').kind, 'forbidden')
  assert.equal(resolvePortalRoute('/admin/payroll', 'employee').kind, 'forbidden')
})

test('opens completed role routes and rejects unknown paths', () => {
  assert.equal(resolvePortalRoute('/admin/people', 'admin').kind, 'portal')
  assert.equal(resolvePortalRoute('/manager/time', 'manager').kind, 'portal')
  assert.equal(resolvePortalRoute('/employee/pay', 'employee').kind, 'portal')
  assert.equal(resolvePortalRoute('/unavailable', 'employee').kind, 'unavailable')
  assert.equal(resolvePortalRoute('/forbidden', 'admin').kind, 'forbidden')
  assert.equal(resolvePortalRoute('/unlisted-record/secret', 'admin').kind, 'not-found')
})

test('matches the approved catalogue route paths, roles, and owners', async () => {
  const catalogue = JSON.parse(await readFile(new URL(
    '../docs/migration/phase-15/integration-catalogue.json', import.meta.url,
  )))
  assert.deepEqual(portalRouteContracts, catalogue.routeContracts.map((route) => ({
    id: route.id,
    owner: route.owner,
    path: route.path,
    roles: route.roles,
  })))
})

test('uses browser history for navigation and observes back or forward changes', () => {
  const browser = fakeBrowser()
  const navigator = createBrowserNavigator(browser)
  const visited = []
  const unsubscribe = navigator.subscribe((path) => visited.push(path))

  navigator.go('/admin')
  navigator.go('/unavailable')
  navigator.go('/admin', { replace: true })
  browser.location.pathname = '/forbidden'
  browser.emit('popstate')
  unsubscribe()
  browser.location.pathname = '/admin'
  browser.emit('popstate')

  assert.deepEqual(visited, ['/', '/admin', '/unavailable', '/admin', '/forbidden'])
})

test('moves focus to the route heading without scrolling it twice', () => {
  const calls = []
  const heading = { focus: (options) => calls.push(options) }
  focusRouteHeading(heading)
  focusRouteHeading(null)
  assert.deepEqual(calls, [{ preventScroll: true }])
})

test('classifies account failures without displaying stale portal content', () => {
  assert.equal(classifyAccountFailure(new HttpClientError('expired', {
    kind: 'authentication', status: 401,
  })), 'session-expired')
  assert.equal(classifyAccountFailure(new HttpClientError('inactive', {
    kind: 'authorization', status: 403,
  })), 'account-unavailable')
  assert.equal(classifyAccountFailure(new HttpClientError('offline', {
    kind: 'network', status: null,
  })), 'service-unavailable')
  assert.equal(classifyAccountFailure(new HttpClientError('failed', {
    kind: 'unexpected', status: 500,
  })), 'service-unavailable')
  assert.equal(classifyAccountFailure(new Error('invalid account response')), 'account-unavailable')
})

test('accepts only the server-scoped staff branch', () => {
  const account = { role: 'employee', branchId }
  const branch = { id: branchId, name: 'Main' }
  assert.equal(resolveStaffBranch(account, [branch]), branch)
  assert.throws(() => resolveStaffBranch(account, []), /staff branch response/i)
  assert.throws(
    () => resolveStaffBranch(account, [{ id: otherBranchId, name: 'Foreign' }]),
    /staff branch response/i,
  )
  assert.throws(
    () => resolveStaffBranch(account, [branch, { id: otherBranchId, name: 'Other' }]),
    /staff branch response/i,
  )
})

test('wires the shared shell without the architecture storage proof', async () => {
  const [adminPortal, app, managerPortal, shell, entry] = await Promise.all([
    readFile(new URL('../src/AdministratorPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/App.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/ManagerPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/PortalShell.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../index.html', import.meta.url), 'utf8'),
  ])
  assert.doesNotMatch(app, /StorageProof|createStorageProof|readStorageProof|deleteStorageProof/)
  assert.match(app, /className="skip-link"/)
  assert.match(shell, /aria-current=/)
  assert.match(shell, /<NotificationBell/)
  assert.match(adminPortal, /<Tasks/)
  assert.match(managerPortal, /<Tasks/)
  assert.match(shell, /<Dashboard/)
  assert.match(shell, /ref={headingRef}/)
  assert.match(entry, /history\.replaceState\(null, '', '\/'\)/)
})
