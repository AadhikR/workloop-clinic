import { useEffect, useMemo, useRef, useState } from 'react'

import AdministratorPortal from './AdministratorPortal.jsx'
import BranchChooser from './BranchChooser.jsx'
import { CompanyProvider } from './CompanyContext.jsx'
import Dashboard from './Dashboards.jsx'
import EmployeePortal from './EmployeePortal.jsx'
import ManagerPortal from './ManagerPortal.jsx'
import NotificationBell from './NotificationBell.jsx'
import Tasks from './Tasks.jsx'
import { useCompanyContext } from './companyContextState.js'
import { administratorRouteGroup } from './administratorRoutes.js'
import { employeeRouteGroup } from './employeeRoutes.js'
import { managerRouteGroup } from './managerRoutes.js'
import {
  createBrowserNavigator,
  focusRouteHeading,
  resolvePortalRoute,
  roleHome,
  roleNavigation,
} from './portalRoutes.js'

function usePortalNavigator() {
  const navigator = useMemo(() => createBrowserNavigator(window), [])
  const [path, setPath] = useState(navigator.current())
  useEffect(() => navigator.subscribe(setPath), [navigator])
  return { navigator, path }
}

function PortalLink({ children, className, current = false, navigator, path }) {
  const follow = (event) => {
    if (
      event.button !== 0
      || event.metaKey
      || event.ctrlKey
      || event.shiftKey
      || event.altKey
    ) return
    event.preventDefault()
    navigator.go(path)
  }
  return (
    <a
      aria-current={current ? 'page' : undefined}
      className={className}
      href={path}
      onClick={follow}
    >
      {children}
    </a>
  )
}

function RouteState({ action, detail, kind, title }) {
  const headingRef = useRef(null)
  useEffect(() => focusRouteHeading(headingRef.current), [kind, title])
  return (
    <section className="route-state" data-route-state={kind} aria-live="polite">
      <p className="eyebrow">Workloop Clinic</p>
      <h1 ref={headingRef} tabIndex="-1">{title}</h1>
      <p className={kind === 'forbidden' ? 'route-alert' : 'route-detail'} role={kind === 'forbidden' ? 'alert' : undefined}>
        {detail}
      </p>
      {action}
    </section>
  )
}

function ProtectedRouteState({ account, authentication, kind, navigator, title }) {
  const details = {
    forbidden: 'This account cannot open that page.',
    'not-found': 'The requested page does not exist.',
    unavailable: 'This page is not available in the portal yet.',
  }
  return (
    <RouteState
      action={(
        <div className="route-actions">
          <PortalLink className="button-link" navigator={navigator} path={roleHome(account.role)}>
            Return home
          </PortalLink>
          <button type="button" className="secondary" onClick={() => authentication.logout()}>
            Sign out
          </button>
        </div>
      )}
      detail={details[kind]}
      kind={kind}
      title={title}
    />
  )
}

function PortalHome({ account, authentication, navigator, route }) {
  const organization = useCompanyContext()
  const headingRef = useRef(null)
  useEffect(
    () => focusRouteHeading(headingRef.current),
    [organization.status, route.path],
  )

  if (organization.status === 'loading') {
    return <RouteState detail="Loading your company and branch context." kind="loading" title="Loading workspace" />
  }
  if (organization.status === 'cancelled') return null
  if (organization.status === 'unavailable') {
    return <RouteState detail="Workloop could not load your organization. Try again shortly." kind="service-unavailable" title="Service unavailable" />
  }
  if (organization.status === 'choose-branch') {
    return (
      <section className="branch-gate" data-route-state="choose-branch">
        <p className="eyebrow">Workloop Clinic</p>
        <h1 ref={headingRef} tabIndex="-1">Choose a branch</h1>
        <BranchChooser />
        <button type="button" className="secondary" onClick={() => authentication.logout()}>Sign out</button>
      </section>
    )
  }

  const branch = organization.selectedBranch
  const organizationName = organization.company?.name ?? organization.employer?.companyName
  const navigation = roleNavigation(account.role)
  const dashboardKind = account.role === 'admin' ? 'admin' : 'self'
  const administratorGroup = account.role === 'admin' ? administratorRouteGroup(route.path) : null
  const employeeGroup = account.role === 'employee' ? employeeRouteGroup(route.path) : null
  const managerGroup = account.role === 'manager' ? managerRouteGroup(route.path) : null
  const description = administratorGroup?.description
    ?? employeeGroup?.description
    ?? managerGroup?.description
    ?? 'Your common work items are ready. Role-specific sections will open as their portal routes are completed.'
  return (
    <div className="portal" data-portal-role={account.role} data-route-state="ready">
      <header className="portal-header">
        <div>
          <p className="eyebrow">Workloop Clinic</p>
          <p className="organization-name">{organizationName}</p>
          <p className="branch-name" data-selected-branch-name>{branch.name}</p>
        </div>
        <div className="header-actions">
          <NotificationBell account={account} authentication={authentication} branchId={branch.id} />
          {account.role === 'admin' && (
            <button type="button" className="secondary" onClick={organization.clearBranch}>Change branch</button>
          )}
          <button type="button" className="secondary" onClick={() => authentication.logout()}>Sign out</button>
        </div>
      </header>
      <nav className="portal-navigation" aria-label="Primary">
        {navigation.map((item) => (
          <PortalLink
            current={item.path === route.path}
            key={item.path}
            navigator={navigator}
            path={item.path}
          >
            {item.title}
          </PortalLink>
        ))}
      </nav>
      <div className="page-heading">
        <p className="current-page">Current page: {route.title}</p>
        <h1 ref={headingRef} tabIndex="-1">{route.title}</h1>
        <p>{description}</p>
      </div>
      {account.role === 'admin' && route.path !== '/admin' ? (
        <AdministratorPortal
          account={account}
          authentication={authentication}
          branchId={branch.id}
          clearBranch={organization.clearBranch}
          path={route.path}
        />
      ) : account.role === 'manager' && route.path !== '/manager' ? (
        <ManagerPortal
          account={account}
          authentication={authentication}
          branchId={branch.id}
          path={route.path}
        />
      ) : account.role === 'employee' && route.path !== '/employee' ? (
        <EmployeePortal
          account={account}
          authentication={authentication}
          branchId={branch.id}
          path={route.path}
        />
      ) : (
        <div className="portal-columns">
          <Dashboard authentication={authentication} branchId={branch.id} kind={dashboardKind} />
          {account.role === 'admin' && (
            <Dashboard authentication={authentication} branchId={branch.id} kind="clinical" />
          )}
          <Tasks account={account} authentication={authentication} branchId={branch.id} />
        </div>
      )}
    </div>
  )
}

export default function PortalShell({ account, authentication }) {
  const { navigator, path } = usePortalNavigator()
  const route = resolvePortalRoute(path, account.role)

  useEffect(() => {
    document.title = `${route.title} | Workloop`
  }, [route.title])

  useEffect(() => {
    if (route.kind === 'redirect') navigator.go(route.path, { replace: true })
  }, [navigator, route.kind, route.path])

  if (route.kind === 'redirect') {
    return <RouteState detail="Opening your home page." kind="loading" title="Loading workspace" />
  }
  if (!['home', 'portal'].includes(route.kind)) {
    return (
      <ProtectedRouteState
        account={account}
        authentication={authentication}
        kind={route.kind}
        navigator={navigator}
        title={route.title}
      />
    )
  }
  return (
    <CompanyProvider account={account} authentication={authentication}>
      <PortalHome
        account={account}
        authentication={authentication}
        navigator={navigator}
        route={route}
      />
    </CompanyProvider>
  )
}
