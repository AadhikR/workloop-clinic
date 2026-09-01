import { useEffect, useState } from 'react'

import { createAuthenticationSession } from './auth.js'
import { migrationPublicConfig } from './config.js'

let authentication

export function authenticationSession() {
  authentication ??= createAuthenticationSession(migrationPublicConfig)
  return authentication
}

const messages = {
  'account-unavailable': 'Your Workloop account is not active. Contact an administrator.',
  'service-unavailable': 'Workloop could not check your account. Try again shortly.',
  'session-expired': 'Your session ended. Sign in again to continue.',
  error: 'Sign-in could not be completed. No account details were changed.',
  loading: 'Checking your local Keycloak session...',
  'logout-incomplete': 'Keycloak sign-out could not be confirmed. Retry before leaving this browser.',
  'signed-in': 'Keycloak and FastAPI accepted this synthetic account.',
  'signed-out': 'Sign in with a temporary local test account.',
}

export default function App() {
  const [sessionState, setSessionState] = useState({ status: 'loading' })

  useEffect(() => {
    let session
    try {
      session = authenticationSession()
    } catch {
      setSessionState({ status: 'configuration-error' })
      return undefined
    }

    const unsubscribe = session.subscribe(setSessionState)
    session.initialize().catch(() => setSessionState({ status: 'error' }))
    return unsubscribe
  }, [])

  const status = sessionState.status
  const canLogin = ['account-unavailable', 'error', 'session-expired', 'signed-out'].includes(status)
  const canLogout = ['account-unavailable', 'logout-incomplete', 'service-unavailable', 'signed-in'].includes(status)

  return (
    <main data-api-configured={Boolean(migrationPublicConfig.apiBaseUrl)} data-session-status={status}>
      <section className="auth-panel" aria-live="polite">
        <p className="eyebrow">Workloop Clinic</p>
        <h1>Local authentication</h1>
        <p className="status">
          {status === 'configuration-error'
            ? 'The migration frontend is missing its public local configuration.'
            : messages[status]}
        </p>
        <div className="actions">
          {canLogin && (
            <button type="button" onClick={() => authenticationSession().login()}>
              Sign in
            </button>
          )}
          {canLogout && (
            <button type="button" className="secondary" onClick={() => authenticationSession().logout()}>
              {status === 'logout-incomplete' ? 'Retry sign out' : 'Sign out'}
            </button>
          )}
        </div>
        <p className="boundary">Local synthetic identities only. Tokens are kept in memory.</p>
      </section>
    </main>
  )
}
