import {
  ErrorResponse,
  InMemoryWebStorage,
  Log,
  UserManager,
  WebStorageStateStore,
} from 'oidc-client-ts'

const callbackPath = '/auth/callback'
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
  if (
    redirect.origin !== location.origin
    || redirect.pathname !== callbackPath
    || redirect.search
    || redirect.hash
    || logout.origin !== location.origin
    || logout.pathname !== '/'
    || logout.search
    || logout.hash
  ) {
    throw new Error('Migration authentication redirect configuration is invalid')
  }

  const api = new URL(config.apiBaseUrl)
  if (
    api.origin !== 'http://127.0.0.1:8000'
    || api.pathname !== '/'
    || api.search
    || api.hash
    || api.username
    || api.password
  ) {
    throw new Error('Migration API configuration is invalid')
  }
  new URL(config.oidcAuthority)
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

function accountState(response) {
  if (response.status === 204) {
    return Object.freeze({ status: 'signed-in' })
  }
  if (response.status === 401) {
    return Object.freeze({ status: 'session-expired' })
  }
  if (response.status === 403) {
    return Object.freeze({ status: 'account-unavailable' })
  }
  if (response.status === 503) {
    return Object.freeze({ status: 'service-unavailable' })
  }
  return Object.freeze({ status: 'error' })
}

function createNonce(crypto) {
  const bytes = crypto.getRandomValues(new Uint8Array(32))
  let value = ''
  for (const byte of bytes) value += String.fromCharCode(byte)
  return btoa(value).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

export class AuthenticationSession {
  constructor({ config, manager, fetch: fetchRequest, history, location, nonce, responseUrl }) {
    this.config = config
    this.manager = manager
    this.fetch = fetchRequest
    this.history = history
    this.location = location
    this.nonce = nonce
    this.responseUrl = responseUrl
    this.listeners = new Set()
    this.state = Object.freeze({ status: 'loading' })
    this.initialization = null

    this.manager.events.addUserLoaded((user) => this.checkAccount(user))
    this.manager.events.addSilentRenewError(() => this.expireSession())
    this.manager.events.addAccessTokenExpired(() => this.expireSession())
  }

  subscribe(listener) {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
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
    this.setState(Object.freeze({ status: 'loading' }))
    await this.manager.signinRedirect({
      nonce: this.nonce(),
      state: { intent: 'interactive' },
    })
  }

  async logout() {
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

  async expireSession() {
    await this.manager.removeUser()
    this.setState(Object.freeze({ status: 'session-expired' }))
  }

  async checkAccount(user) {
    if (!user || user.expired || !user.access_token) {
      await this.expireSession()
      return
    }

    let response
    try {
      response = await this.fetch(new URL('/api/v1/auth/token-check', this.config.apiBaseUrl), {
        method: 'GET',
        headers: { Authorization: `Bearer ${user.access_token}` },
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
      })
    } catch {
      this.setState(Object.freeze({ status: 'service-unavailable' }))
      return
    }

    const nextState = accountState(response)
    if (nextState.status === 'session-expired') {
      await this.manager.removeUser()
    }
    this.setState(nextState)
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
