import {
  ErrorResponse,
  InMemoryWebStorage,
  Log,
  UserManager,
  WebStorageStateStore,
} from 'oidc-client-ts'

import { HttpClientError, assertApiBaseUrl, createHttpClient } from './http.js'

const callbackPath = '/oidc/callback'
const signedOutState = Object.freeze({ status: 'signed-out' })

function assertPublicConfig(config, location) {
  const required = [
    'apiBaseUrl',
    'oidcAuthority',
    'oidcClientId',
    'oidcRedirectUri',
    'oidcPostLogoutRedirectUri',
    'oidcAudience',
  ]
  if (required.some((name) => !config[name])) {
    throw new Error('Migration authentication configuration is incomplete')
  }

  const redirect = new URL(config.oidcRedirectUri)
  const logout = new URL(config.oidcPostLogoutRedirectUri)
  const authority = new URL(config.oidcAuthority)
  const localAuthorities = new Set([
    'http://127.0.0.1:8080/realms/workloop-dev',
    'http://127.0.0.1:18080/realms/workloop-dev',
    'http://127.0.0.1:28080/realms/workloop-dev',
  ])
  const cloudAuthority = `${location.origin}/auth/realms/workloop-dev`
  if (
    redirect.origin !== location.origin
    || redirect.pathname !== callbackPath
    || redirect.search
    || redirect.hash
    || logout.origin !== location.origin
    || logout.pathname !== '/'
    || logout.search
    || logout.hash
    || (
      location.origin === 'http://127.0.0.1:5174'
        ? !localAuthorities.has(config.oidcAuthority)
        : config.oidcAuthority !== cloudAuthority
    )
    || authority.search
    || authority.hash
  ) {
    throw new Error('Migration authentication redirect configuration is invalid')
  }

  assertApiBaseUrl(config.apiBaseUrl, location.origin)
}

export function createUserManager(config, browser = window) {
  assertPublicConfig(config, browser.location)
  Log.setLevel(Log.NONE)
  return new UserManager({
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    redirect_uri: config.oidcRedirectUri,
    post_logout_redirect_uri: config.oidcPostLogoutRedirectUri,
    response_type: 'code',
    scope: 'openid profile email',
    automaticSilentRenew: true,
    monitorSession: false,
    loadUserInfo: false,
    stateStore: new WebStorageStateStore({
      prefix: 'workloop.oidc.',
      store: browser.sessionStorage,
    }),
    userStore: new WebStorageStateStore({
      prefix: 'workloop.user.',
      store: new InMemoryWebStorage(),
    }),
  })
}

export function createNonce(crypto) {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  let value = ''
  for (const byte of bytes) value += String.fromCharCode(byte)
  return btoa(value).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

export class AuthenticationSession {
  constructor({ config, manager, fetch: fetchRequest, history, location, nonce, responseUrl }) {
    this.manager = manager
    this.history = history
    this.location = location
    this.nonce = nonce
    this.responseUrl = responseUrl
    this.http = createHttpClient({
      apiBaseUrl: config.apiBaseUrl,
      browserOrigin: location.origin,
      fetch: fetchRequest,
      getAccessToken: () => this.currentUser?.access_token ?? null,
    })
    this.listeners = new Set()
    this.state = Object.freeze({ status: 'loading' })
    this.initialization = null
    this.accountChecks = new WeakMap()
    this.accountGeneration = 0
    this.currentUser = null
    this.sessionCleanup = null

    this.manager.events.addUserLoaded((user) => this.checkAccount(user))
    this.manager.events.addSilentRenewError(() => this.expireSession())
    this.manager.events.addAccessTokenExpired(() => this.expireSession())
  }

  subscribe(listener) {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
  }

  request(path, options) {
    return this.http.request(path, options)
  }

  setState(state) {
    this.state = state
    for (const listener of this.listeners) {
      listener(state)
    }
  }

  clearResponseUrl() {
    this.history.replaceState(null, '', '/')
  }

  async initialize() {
    this.initialization ??= this.runInitialization()
    return this.initialization
  }

  async runInitialization() {
    await this.manager.clearStaleState()
    const parameters = new URLSearchParams(this.location.search)

    if (this.responseUrl) {
      try {
        const user = await this.manager.signinRedirectCallback(this.responseUrl)
        await this.checkAccount(user)
      } catch (error) {
        this.invalidateAccountChecks()
        await this.manager.removeUser()
        if (error instanceof ErrorResponse && error.error === 'login_required') {
          this.setState(signedOutState)
        } else {
          this.setState(Object.freeze({ status: 'error' }))
        }
      } finally {
        this.responseUrl = null
      }
      return
    }

    if (parameters.has('state')) {
      const pendingState = await this.manager.settings.stateStore.get(parameters.get('state'))
      if (!pendingState) {
        this.clearResponseUrl()
      } else {
        try {
          await this.manager.signoutRedirectCallback(this.location.href)
        } catch {
          this.setState(Object.freeze({ status: 'logout-incomplete' }))
          return
        } finally {
          this.clearResponseUrl()
        }
        this.setState(signedOutState)
        return
      }
    }

    const user = await this.manager.getUser()
    if (user && !user.expired) {
      await this.checkAccount(user)
      return
    }

    await this.manager.removeUser()
    await this.manager.signinRedirect({
      nonce: this.nonce(),
      prompt: 'none',
      state: { intent: 'restore' },
    })
  }

  async login() {
    this.invalidateAccountChecks()
    this.setState(Object.freeze({ status: 'loading' }))
    await this.manager.signinRedirect({
      nonce: this.nonce(),
      state: { intent: 'interactive' },
    })
  }

  async logout() {
    this.invalidateAccountChecks()
    this.setState(Object.freeze({ status: 'loading' }))
    try {
      await this.manager.signoutRedirect()
    } catch {
      await this.manager.removeUser()
      this.setState(Object.freeze({ status: 'logout-incomplete' }))
    }
  }

  async renew() {
    try {
      const currentUser = await this.manager.getUser()
      if (!currentUser?.refresh_token) {
        await this.expireSession()
        return
      }
      const renewedUser = await this.manager.signinSilent()
      await this.checkAccount(renewedUser)
    } catch {
      await this.expireSession()
    }
  }

  async expireSession(
    expectedGeneration = this.accountGeneration,
    expectedUser = this.currentUser,
  ) {
    if (this.sessionCleanup) {
      await this.sessionCleanup
      return
    }
    if (
      expectedGeneration !== this.accountGeneration
      || expectedUser !== this.currentUser
    ) return
    this.invalidateAccountChecks()
    const expirationGeneration = this.accountGeneration
    const cleanup = this.manager.removeUser()
    this.sessionCleanup = cleanup
    try {
      await cleanup
    } finally {
      if (this.sessionCleanup === cleanup) this.sessionCleanup = null
    }
    if (expirationGeneration === this.accountGeneration && this.currentUser === null) {
      this.setState(Object.freeze({ status: 'session-expired' }))
    }
  }

  invalidateAccountChecks() {
    this.accountGeneration += 1
    this.currentUser = null
  }

  async checkAccount(user) {
    if (user && typeof user === 'object') {
      const existingCheck = this.accountChecks.get(user)
      if (existingCheck) return existingCheck
      const accountCheck = this.prepareAccountCheck(user)
      this.accountChecks.set(user, accountCheck)
      return accountCheck
    }
    return this.runAccountCheck(user, this.accountGeneration)
  }

  async prepareAccountCheck(user) {
    const cleanup = this.sessionCleanup
    if (cleanup) {
      await cleanup
      await this.manager.storeUser(user)
    }
    if (this.currentUser !== user) {
      this.accountGeneration += 1
      this.currentUser = user
    }
    return this.runAccountCheck(user, this.accountGeneration)
  }

  async runAccountCheck(user, generation) {
    if (!user || user.expired || !user.access_token) {
      await this.expireSession(generation, user)
      return
    }

    try {
      await this.http.request('/api/v1/auth/token-check', {
        access: 'protected',
      })
    } catch (error) {
      if (generation !== this.accountGeneration || this.currentUser !== user) return
      if (error instanceof HttpClientError && error.status === 401) {
        await this.expireSession(generation, user)
        return
      }
      if (error instanceof HttpClientError && error.status === 403) {
        this.setState(Object.freeze({ status: 'account-unavailable' }))
        return
      }
      if (
        error instanceof HttpClientError
        && (error.status === 503 || ['network', 'availability'].includes(error.kind)
          || error.kind === 'timeout' && error.status === null)
      ) {
        this.setState(Object.freeze({ status: 'service-unavailable' }))
        return
      }
      this.setState(Object.freeze({ status: 'error' }))
      return
    }

    if (generation !== this.accountGeneration || this.currentUser !== user) return
    this.setState(Object.freeze({ status: 'signed-in' }))
  }
}

export function createAuthenticationSession(config, browser = window) {
  const responseUrl = browser.__workloopOidcResponse ?? null
  delete browser.__workloopOidcResponse
  return new AuthenticationSession({
    config,
    manager: createUserManager(config, browser),
    fetch: browser.fetch.bind(browser),
    history: browser.history,
    location: browser.location,
    nonce: () => createNonce(browser.crypto),
    responseUrl,
  })
}
