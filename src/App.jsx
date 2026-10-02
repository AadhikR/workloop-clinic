import { useEffect, useState } from 'react'

import { authenticationSession } from './authSession.js'
import { migrationPublicConfig } from './config.js'
import PortalShell from './PortalShell.jsx'
import { classifyAccountFailure } from './portalSession.js'
import { readCurrentAccount, readPublicStatus } from './sampleApi.js'

const stateContent = {
  'account-unavailable': {
    detail: 'Your Workloop account is inactive or incomplete. Contact an administrator.',
    title: 'Account unavailable',
  },
  'configuration-error': {
    detail: 'Workloop is missing required public sign-in settings.',
    title: 'Configuration unavailable',
  },
  error: {
    detail: 'Sign-in could not be completed. No account details were changed.',
    title: 'Sign-in failed',
  },
  loading: {
    detail: 'Checking your session and account.',
    title: 'Loading Workloop',
  },
  'logout-incomplete': {
    detail: 'Sign-out could not be confirmed. Retry before leaving this browser.',
    title: 'Sign-out incomplete',
  },
  'service-unavailable': {
    detail: 'Workloop could not check your account. Try again shortly.',
    title: 'Service unavailable',
  },
  'session-expired': {
    detail: 'Your session ended. Sign in again to continue.',
    title: 'Session expired',
  },
  'signed-out': {
    detail: 'Sign in to open your Workloop portal.',
    title: 'Welcome to Workloop',
  },
}

function SessionState({ authentication, status }) {
  const content = stateContent[status] ?? stateContent.error
  const canLogin = ['account-unavailable', 'error', 'session-expired', 'signed-out'].includes(status)
  const canLogout = ['account-unavailable', 'logout-incomplete', 'service-unavailable'].includes(status)
  return (
    <section className="session-state" aria-live="polite">
      <p className="eyebrow">Workloop Clinic</p>
      <h1 tabIndex="-1">{content.title}</h1>
      <p className={status === 'error' ? 'route-alert' : 'route-detail'} role={status === 'error' ? 'alert' : 'status'}>
        {content.detail}
      </p>
      <div className="route-actions">
        {canLogin && authentication && (
          <button type="button" onClick={() => authentication.login()}>
            Sign in
          </button>
        )}
        {canLogout && authentication && (
          <button type="button" className="secondary" onClick={() => authentication.logout()}>
            {status === 'logout-incomplete' ? 'Retry sign out' : 'Sign out'}
          </button>
        )}
      </div>
    </section>
  )
}

export default function App() {
  const [bootstrap] = useState(() => {
    try {
      return { authentication: authenticationSession(), error: false }
    } catch {
      return { authentication: null, error: true }
    }
  })
  const authentication = bootstrap.authentication
  const [sessionState, setSessionState] = useState({ status: 'loading' })
  const [accountState, setAccountState] = useState({ status: 'idle' })
  const [publicStatus, setPublicStatus] = useState('loading')

  useEffect(() => {
    let active = true
    if (bootstrap.error) {
      queueMicrotask(() => {
        if (active) setSessionState({ status: 'configuration-error' })
      })
      return () => { active = false }
    }

    const session = authentication
    const unsubscribe = session.subscribe((state) => {
      if (state.status !== 'signed-in') setAccountState({ status: 'idle' })
      setSessionState(state)
    })
    const controller = new AbortController()
    readPublicStatus(session, { signal: controller.signal })
      .then(() => setPublicStatus('ready'))
      .catch(() => {
        if (!controller.signal.aborted) setPublicStatus('unavailable')
      })
    session.initialize().catch(() => setSessionState({ status: 'error' }))
    return () => {
      active = false
      controller.abort()
      unsubscribe()
    }
  }, [authentication, bootstrap.error])

  useEffect(() => {
    if (!authentication || sessionState.status !== 'signed-in') {
      return undefined
    }
    const controller = new AbortController()
    readCurrentAccount(authentication, { signal: controller.signal })
      .then((account) => {
        if (!controller.signal.aborted) setAccountState({ status: 'ready', account })
      })
      .catch(async (error) => {
        if (controller.signal.aborted) return
        const status = classifyAccountFailure(error)
        if (status === 'cancelled') return
        setAccountState({ status })
        if (status === 'session-expired') await authentication.expireSession()
      })
    return () => controller.abort()
  }, [authentication, sessionState.status])

  let status = sessionState.status
  if (status === 'signed-in' && accountState.status !== 'ready') {
    status = accountState.status === 'idle' ? 'loading' : accountState.status
  }

  return (
    <>
      <a className="skip-link" href="#portal-content">Skip to main content</a>
      <main
        data-api-configured={Boolean(migrationPublicConfig.apiBaseUrl)}
        data-public-api-status={publicStatus}
        data-session-status={status}
        id="portal-content"
        tabIndex="-1"
      >
        {status === 'signed-in' ? (
          <PortalShell account={accountState.account} authentication={authentication} />
        ) : (
          <SessionState authentication={authentication} status={status} />
        )}
      </main>
    </>
  )
}
