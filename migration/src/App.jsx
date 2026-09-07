import { useEffect, useState } from 'react'

import { authenticationSession } from './authSession.js'
import { migrationPublicConfig } from './config.js'
import { readCurrentAccount, readPublicStatus } from './sampleApi.js'

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

function CurrentAccountSample() {
  const [accountSample, setAccountSample] = useState({ status: 'loading' })

  useEffect(() => {
    const controller = new AbortController()
    readCurrentAccount(authenticationSession(), { signal: controller.signal })
      .then((data) => setAccountSample({ status: 'ready', data }))
      .catch(() => {
        if (!controller.signal.aborted) setAccountSample({ status: 'unavailable' })
      })
    return () => controller.abort()
  }, [])

  return (
    <>
      <div>
        <dt>Protected account</dt>
        <dd data-account-api-status={accountSample.status}>
          {accountSample.status === 'ready' ? accountSample.data.role : accountSample.status}
        </dd>
      </div>
      {accountSample.status === 'ready' && (
        <div className="account-sample">
          <div><dt>App user</dt><dd>{accountSample.data.appUserId}</dd></div>
          <div><dt>Company</dt><dd>{accountSample.data.companyId}</dd></div>
          <div><dt>Employee</dt><dd>{accountSample.data.employeeId ?? 'Not linked'}</dd></div>
          <div><dt>Branch</dt><dd>{accountSample.data.branchId ?? 'Not selected'}</dd></div>
        </div>
      )}
    </>
  )
}

export default function App() {
  const [sessionState, setSessionState] = useState({ status: 'loading' })
  const [publicSample, setPublicSample] = useState({ status: 'loading' })

  useEffect(() => {
    let active = true
    let session
    try {
      session = authenticationSession()
    } catch {
      queueMicrotask(() => {
        if (active) setSessionState({ status: 'configuration-error' })
      })
      return () => { active = false }
    }

    const unsubscribe = session.subscribe(setSessionState)
    const controller = new AbortController()
    readPublicStatus(session, { signal: controller.signal })
      .then((data) => setPublicSample({ status: 'ready', data }))
      .catch(() => {
        if (!controller.signal.aborted) setPublicSample({ status: 'unavailable' })
      })
    session.initialize().catch(() => setSessionState({ status: 'error' }))
    return () => {
      active = false
      controller.abort()
      unsubscribe()
    }
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
        <section className="sample-status" aria-label="Migration API sample status">
          <h2>API sample</h2>
          <dl>
            <div>
              <dt>Public status</dt>
              <dd data-public-api-status={publicSample.status}>
                {publicSample.status === 'ready' ? publicSample.data.status : publicSample.status}
              </dd>
            </div>
            {status === 'signed-in' ? (
              <CurrentAccountSample />
            ) : (
              <div>
                <dt>Protected account</dt>
                <dd data-account-api-status="waiting">waiting</dd>
              </div>
            )}
          </dl>
        </section>
        <p className="boundary">Local synthetic identities only. Tokens are kept in memory.</p>
      </section>
    </main>
  )
}
