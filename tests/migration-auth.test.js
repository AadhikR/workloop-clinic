import assert from 'node:assert/strict'
import test from 'node:test'

import { ErrorResponse } from 'oidc-client-ts'

import { AuthenticationSession, createUserManager } from '../migration/src/auth.js'

const config = {
  apiBaseUrl: 'http://127.0.0.1:8000',
  oidcAuthority: 'http://127.0.0.1:8080/realms/workloop-dev',
  oidcClientId: 'workloop-migration-web',
  oidcRedirectUri: 'http://127.0.0.1:5174/auth/callback',
  oidcPostLogoutRedirectUri: 'http://127.0.0.1:5174/',
  oidcAudience: 'workloop-api',
}

class MemoryStorage {
  constructor() {
    this.values = new Map()
  }

  get length() {
    return this.values.size
  }

  clear() {
    this.values.clear()
  }

  getItem(key) {
    return this.values.get(key) ?? null
  }

  key(index) {
    return [...this.values.keys()][index] ?? null
  }

  removeItem(key) {
    this.values.delete(key)
  }

  setItem(key, value) {
    this.values.set(key, value)
  }
}

function fakeManager(overrides = {}) {
  const callbacks = {}
  const calls = []
  return {
    callbacks,
    calls,
    events: {
      addAccessTokenExpired(callback) { callbacks.expired = callback },
      addSilentRenewError(callback) { callbacks.renewError = callback },
      addUserLoaded(callback) { callbacks.loaded = callback },
    },
    settings: {
      stateStore: {
        async get() { return 'pending-transaction' },
      },
    },
    async clearStaleState() { calls.push(['clearStaleState']) },
    async getUser() { calls.push(['getUser']); return null },
    async removeUser() { calls.push(['removeUser']) },
    async signinRedirect(args) { calls.push(['signinRedirect', args]) },
    async signinRedirectCallback() { throw new Error('not implemented') },
    async signoutRedirect() { calls.push(['signoutRedirect']) },
    async signoutRedirectCallback() { calls.push(['signoutRedirectCallback']) },
    ...overrides,
  }
}

function session(overrides = {}) {
  const manager = overrides.manager ?? fakeManager()
  const replacements = []
  const location = overrides.location ?? {
    href: 'http://127.0.0.1:5174/',
    origin: 'http://127.0.0.1:5174',
    pathname: '/',
    search: '',
  }
  const authentication = new AuthenticationSession({
    config,
    manager,
    fetch: overrides.fetch ?? (async () => ({ status: 204 })),
    history: { replaceState: (...args) => replacements.push(args) },
    location,
    nonce: () => 'test-nonce',
    responseUrl: overrides.responseUrl
      ?? (location.pathname === '/auth/callback' ? location.href : null),
  })
  return { authentication, manager, replacements }
}

test('keeps user tokens in memory and redirect state in session storage', async () => {
  const sessionStorage = new MemoryStorage()
  const manager = createUserManager(config, {
    location: { origin: 'http://127.0.0.1:5174' },
    sessionStorage,
  })

  await manager.settings.userStore.set('user-proof', 'sensitive-user-value')
  assert.equal(sessionStorage.length, 0)
  assert.equal(await manager.settings.userStore.get('user-proof'), 'sensitive-user-value')

  await manager.settings.stateStore.set('state-proof', 'temporary-state-value')
  assert.equal(sessionStorage.length, 1)
  assert.equal(sessionStorage.getItem('workloop.oidc.state-proof'), 'temporary-state-value')
})

test('rejects an API token destination outside the approved local origin', () => {
  assert.throws(
    () => createUserManager(
      { ...config, apiBaseUrl: 'https://unapproved.example.test' },
      {
        location: { origin: 'http://127.0.0.1:5174' },
        sessionStorage: new MemoryStorage(),
      },
    ),
    /Migration API configuration is invalid/,
  )
})

test('uses one top-level prompt-none redirect when no in-memory user exists', async () => {
  const { authentication, manager } = session()

  await Promise.all([authentication.initialize(), authentication.initialize()])

  assert.deepEqual(manager.calls, [
    ['clearStaleState'],
    ['getUser'],
    ['removeUser'],
    ['signinRedirect', { nonce: 'test-nonce', prompt: 'none', state: { intent: 'restore' } }],
  ])
})

test('checks the FastAPI account after a validated callback and clears its URL', async () => {
  const manager = fakeManager({
    async signinRedirectCallback() {
      return { access_token: 'not-a-real-token', expired: false }
    },
  })
  const requests = []
  const { authentication, replacements } = session({
    manager,
    fetch: async (...args) => { requests.push(args); return { status: 204 } },
    location: {
      href: 'http://127.0.0.1:5174/auth/callback?code=redacted&state=redacted',
      origin: 'http://127.0.0.1:5174',
      pathname: '/auth/callback',
      search: '?code=redacted&state=redacted',
    },
  })

  await authentication.initialize()

  assert.equal(authentication.state.status, 'signed-in')
  assert.equal(requests.length, 1)
  assert.equal(requests[0][0].toString(), 'http://127.0.0.1:8000/api/v1/auth/token-check')
  assert.equal(requests[0][1].cache, 'no-store')
  assert.equal(requests[0][1].credentials, 'omit')
  assert.deepEqual(replacements, [])
})

test('fails closed for callback replay and prompt-none login_required', async () => {
  for (const [error, expected] of [
    [new Error('No matching state found in storage'), 'error'],
    [new ErrorResponse({ error: 'login_required' }), 'signed-out'],
  ]) {
    const manager = fakeManager({
      async signinRedirectCallback() { throw error },
    })
    const { authentication, replacements } = session({
      manager,
      location: {
        href: 'http://127.0.0.1:5174/auth/callback?state=invalid',
        origin: 'http://127.0.0.1:5174',
        pathname: '/auth/callback',
        search: '?state=invalid',
      },
    })

    await authentication.initialize()

    assert.equal(authentication.state.status, expected)
    assert.equal(manager.calls.some(([name]) => name === 'removeUser'), true)
    assert.deepEqual(replacements, [])
  }
})

test('maps account states without reading response bodies and clears rejected tokens', async () => {
  for (const [status, expected, removesUser] of [
    [401, 'session-expired', true],
    [403, 'account-unavailable', false],
    [503, 'service-unavailable', false],
    [500, 'error', false],
  ]) {
    const { authentication, manager } = session({ fetch: async () => ({ status }) })
    await authentication.checkAccount({ access_token: 'not-a-real-token', expired: false })
    assert.equal(authentication.state.status, expected)
    assert.equal(manager.calls.some(([name]) => name === 'removeUser'), removesUser)
  }
})

test('removes in-memory tokens when renewal fails or the access token expires', async () => {
  const { authentication, manager } = session()

  await manager.callbacks.renewError()
  assert.equal(authentication.state.status, 'session-expired')
  await manager.callbacks.expired()
  assert.equal(authentication.state.status, 'session-expired')
  assert.equal(manager.calls.filter(([name]) => name === 'removeUser').length, 2)
})

test('processes the logout callback without starting session restoration', async () => {
  const { authentication, manager, replacements } = session({
    location: {
      href: 'http://127.0.0.1:5174/?state=logout-state',
      origin: 'http://127.0.0.1:5174',
      pathname: '/',
      search: '?state=logout-state',
    },
  })

  await authentication.initialize()

  assert.equal(authentication.state.status, 'signed-out')
  assert.equal(manager.calls.some(([name]) => name === 'signoutRedirectCallback'), true)
  assert.equal(manager.calls.some(([name]) => name === 'signinRedirect'), false)
  assert.deepEqual(replacements, [[null, '', '/']])
})

test('does not claim logout success when the provider request or callback fails', async () => {
  const requestManager = fakeManager({
    async signoutRedirect() { throw new Error('provider unavailable') },
  })
  const request = session({ manager: requestManager })
  await request.authentication.logout()
  assert.equal(request.authentication.state.status, 'logout-incomplete')

  const callbackManager = fakeManager({
    settings: { stateStore: { async get() { return null } } },
    async getUser() { return { access_token: 'still-in-memory', expired: false } },
    async signoutRedirectCallback() { throw new Error('invalid logout state') },
  })
  const callback = session({
    manager: callbackManager,
    location: {
      href: 'http://127.0.0.1:5174/?state=invalid',
      origin: 'http://127.0.0.1:5174',
      pathname: '/',
      search: '?state=invalid',
    },
  })
  await callback.authentication.initialize()
  assert.equal(callbackManager.calls.some(([name]) => name === 'signinRedirect'), false)
  assert.equal(callback.authentication.state.status, 'signed-in')
  assert.equal(callbackManager.calls.some(([name]) => name === 'removeUser'), false)
})

test('renews only with an in-memory refresh token and fails closed on renewal errors', async () => {
  const manager = fakeManager({
    async getUser() { return { refresh_token: 'in-memory-only' } },
    async signinSilent() {
      return { access_token: 'renewed-access-token', expired: false }
    },
  })
  const { authentication } = session({ manager })
  await authentication.renew()
  assert.equal(authentication.state.status, 'signed-in')

  manager.signinSilent = async () => { throw new Error('refresh rejected') }
  await authentication.renew()
  assert.equal(authentication.state.status, 'session-expired')
})
