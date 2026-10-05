import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import './portal-ui.css'

import AdministratorPortal from './AdministratorPortal.jsx'
import BranchChooser from './BranchChooser.jsx'
import { CompanyProvider } from './CompanyContext.jsx'
import Dashboard from './Dashboards.jsx'
import EmployeePortal from './EmployeePortal.jsx'
import { readEmployeeSelf } from './employeeApi.js'
import ManagerPortal from './ManagerPortal.jsx'
import NotificationBell from './NotificationBell.jsx'
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

function NavigationIcon({ name }) {
  const paths = {
    Attendance: <><circle cx="12" cy="12" r="8" /><path d="M12 7v5l3 2" /></>,
    Advances: <><path d="M6 3h12v18H6z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
    Appraisals: <><path d="m12 3 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8z" /></>,
    Development: <><path d="M4 19V9l8-4 8 4v10" /><path d="M8 19v-6h8v6" /></>,
    Documents: <><path d="M6 3h9l3 3v15H6z" /><path d="M15 3v4h4M9 12h6M9 16h6" /></>,
    Expenses: <><path d="M6 3h12v18H6z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
    Leave: <><path d="M5 5h14v15H5z" /><path d="M8 3v4M16 3v4M5 9h14" /></>,
    Organization: <><path d="M4 21V7h10v14M14 11h6v10" /><path d="M8 11h2M8 15h2M8 19h2M17 15h1M17 19h1" /></>,
    Pay: <><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M8 12h8M12 9v6" /></>,
    Payslips: <><path d="M6 3h12v18H6z" /><path d="M9 8h6M9 12h6M9 16h3" /></>,
    Payroll: <><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h4" /></>,
    People: <><circle cx="9" cy="8" r="3" /><circle cx="17" cy="9" r="2" /><path d="M3 20c0-4 2-6 6-6s6 2 6 6M15 15c3 0 5 2 5 5" /></>,
    Profile: <><circle cx="12" cy="8" r="4" /><path d="M4 21c0-5 3-8 8-8s8 3 8 8" /></>,
    Records: <><path d="M6 3h9l3 3v15H6z" /><path d="M15 3v4h4M9 12h6M9 16h6" /></>,
    Reports: <><path d="M5 20V10M12 20V4M19 20v-7" /></>,
    Requests: <><path d="M5 4h14v16H5z" /><path d="M8 8h8M8 12h8M8 16h5" /></>,
    Roster: <><path d="M4 6h16v14H4z" /><path d="M8 3v6M16 3v6M4 10h16" /></>,
    Schedule: <><path d="M4 6h16v14H4z" /><path d="M8 3v6M16 3v6M4 10h16" /></>,
    Team: <><circle cx="8" cy="8" r="3" /><circle cx="16" cy="8" r="3" /><path d="M2 20c0-4 2-6 6-6s6 2 6 6M10 20c0-4 2-6 6-6s6 2 6 6" /></>,
    Time: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l4 2" /></>,
    Tasks: <><path d="M6 4h12v17H6z" /><path d="m9 9 1.5 1.5L14 7M9 15h5" /></>,
    Training: <><path d="m3 8 9-5 9 5-9 5z" /><path d="M7 11v5c3 2 7 2 10 0v-5" /></>,
  }
  const aliases = {
    'Clinical Dashboard': 'Attendance',
    'Company Settings': 'Organization',
    Dashboard: 'Home',
    Departments: 'Organization',
    Employees: 'People',
    'Expense Queue': 'Expenses',
    Home: 'Home',
    Incidents: 'Records',
    'Leave Queue': 'Leave',
    'My Attendance': 'Attendance',
    'My Leave': 'Leave',
    'Payroll Module': 'Payroll',
  }
  const iconName = aliases[name] ?? name
  const isHome = iconName === 'Home' || name.toLowerCase().endsWith('home')
  return (
    <svg aria-hidden="true" className="nav-icon" viewBox="0 0 24 24">
      {isHome ? <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></> : paths[iconName] ?? paths.Requests}
    </svg>
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
  const navigationRef = useRef(null)
  const [staffIdentity, setStaffIdentity] = useState(null)
  useEffect(() => {
    if (account.role === 'admin') return undefined
    let current = true
    readEmployeeSelf(authentication).then((employee) => { if (current) setStaffIdentity(employee) }).catch(() => { if (current) setStaffIdentity(null) })
    return () => { current = false }
  }, [account.role, account.employeeId, authentication])
  const allNavigation = roleNavigation(account.role)
  const sidebarStorageKey = `workloop-${account.role}-sidebar-collapsed`
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(sidebarStorageKey) === 'true'
    } catch {
      return false
    }
  })
  const [navigationPill, setNavigationPill] = useState({ height: 36, top: 0 })
  const [darkMode, setDarkMode] = useState(() => {
    try {
      return window.localStorage.getItem('workloop-dark-mode') === 'true'
    } catch {
      return false
    }
  })
  const [advancedFeatures, setAdvancedFeatures] = useState(() => {
    try {
      return window.localStorage.getItem('workloop-advanced-features') === 'true'
    } catch {
      return false
    }
  })
  const coreAdministratorPages = new Set([
    'Dashboard', 'Company Settings', 'Employees', 'Payroll Module', 'Advances',
    'Expenses', 'Leave', 'Attendance', 'Reports',
  ])
  const navigation = account.role === 'admin' && !advancedFeatures
    ? allNavigation.filter((item) => coreAdministratorPages.has(item.title) || item.path === route.path)
    : allNavigation

  const toggleSidebar = () => {
    setSidebarCollapsed((collapsed) => {
      const next = !collapsed
      try {
        window.localStorage.setItem(sidebarStorageKey, String(next))
      } catch {
        // The shell still works when browser storage is unavailable.
      }
      return next
    })
  }

  const togglePreference = (name, setter) => {
    setter((current) => {
      const next = !current
      try {
        window.localStorage.setItem(name, String(next))
      } catch {
        // The control remains usable when browser storage is unavailable.
      }
      return next
    })
  }

  const measureNavigationPill = useCallback(() => {
    const navigationElement = navigationRef.current
    const activeItem = navigationElement?.querySelector('[aria-current="page"]')
    if (!navigationElement || !activeItem) return
    const navigationBox = navigationElement.getBoundingClientRect()
    const activeBox = activeItem.getBoundingClientRect()
    setNavigationPill({
      height: activeBox.height,
      top: activeBox.top - navigationBox.top + navigationElement.scrollTop,
    })
  }, [])

  useEffect(
    () => focusRouteHeading(headingRef.current),
    [organization.status, route.path],
  )
  useLayoutEffect(measureNavigationPill, [measureNavigationPill, navigation.length, organization.status, route.path, sidebarCollapsed])
  useEffect(() => {
    const timer = window.setTimeout(measureNavigationPill, 300)
    window.addEventListener('resize', measureNavigationPill)
    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('resize', measureNavigationPill)
    }
  }, [measureNavigationPill, navigation.length, organization.status, route.path, sidebarCollapsed])

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
  const dashboardKind = account.role === 'admin' ? 'admin' : 'self'
  const administratorGroup = account.role === 'admin' ? administratorRouteGroup(route.path) : null
  const employeeGroup = account.role === 'employee' ? employeeRouteGroup(route.path) : null
  const managerGroup = account.role === 'manager' ? managerRouteGroup(route.path) : null
  const description = administratorGroup?.description
    ?? employeeGroup?.description
    ?? managerGroup?.description
    ?? 'Your common work items are ready. Role-specific sections will open as their portal routes are completed.'
  return (
    <div
      className="portal app-layout"
      data-advanced-features={advancedFeatures ? 'true' : 'false'}
      data-portal-role={account.role}
      data-route-path={route.path}
      data-route-state="ready"
      data-theme={darkMode ? 'dark' : 'light'}
    >
      <aside className={`sidebar${sidebarCollapsed ? ' collapsed' : ''}`}>
        <div className="sidebar-logo">
          <div className="sidebar-brand-row">
            <p className="sidebar-brand">{account.role === 'admin' ? 'Workloop' : organizationName}</p>
            <button
              type="button"
              className="sidebar-collapse-btn"
              onClick={toggleSidebar}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <span aria-hidden="true">{sidebarCollapsed ? '›' : '‹'}</span>
            </button>
          </div>
          {account.role !== 'admin' && <p className="staff-portal-label">{account.role === 'manager' ? 'Manager Portal' : 'Employee Portal'}</p>}
          {account.role === 'admin' ? (
            <button
              type="button"
              className="sidebar-branch"
              onClick={organization.clearBranch}
              aria-label="Change branch"
            >
              <span aria-hidden="true" className="branch-symbol">▦</span>
              <span data-selected-branch-name>{branch.name}</span>
              <span aria-hidden="true" className="branch-chevron">⌄</span>
            </button>
          ) : (
            <div className="sidebar-branch" aria-label={`Current branch: ${branch.name}`}>
              <span aria-hidden="true" className="branch-symbol">▦</span>
              <span data-selected-branch-name>{branch.name}</span>
            </div>
          )}
        </div>
        <nav ref={navigationRef} className="portal-navigation sidebar-nav" aria-label="Primary">
          <p className="nav-section-label">Navigation</p>
          <span
            aria-hidden="true"
            className="nav-pill"
            style={{ height: navigationPill.height, transform: `translateY(${navigationPill.top}px)` }}
          />
          {navigation.map((item) => (
            <div className="nav-entry" key={item.path}>
              {item.title === 'Tasks' && <span aria-hidden="true" className="nav-divider" />}
              <PortalLink
                className="nav-item"
                current={item.path === route.path}
                navigator={navigator}
                path={item.path}
              >
                <NavigationIcon name={item.title} />
                <span className="nav-item-label">{item.title}</span>
              </PortalLink>
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span aria-hidden="true" className="user-avatar">{staffIdentity?.name.slice(0, 1) ?? account.role.slice(0, 1).toUpperCase()}</span>
            <span className="sidebar-user-copy">
              <strong>{account.role === 'admin' ? organizationName : staffIdentity?.name ?? 'Your workspace'}</strong>
              <small>{account.role === 'admin' ? 'HR Admin' : staffIdentity?.jobTitle || (account.role === 'manager' ? 'Manager' : 'Employee')}</small>
            </span>
            <NotificationBell account={account} authentication={authentication} branchId={branch.id} />
          </div>
          {account.role === 'admin' && (
            <div className="sidebar-preferences" aria-label="Display preferences">
              <button
                type="button"
                className="sidebar-preference"
                aria-pressed={darkMode}
                onClick={() => togglePreference('workloop-dark-mode', setDarkMode)}
              >
                <span aria-hidden="true">☾</span>
                <span className="sidebar-preference-label">Dark mode</span>
                <span aria-hidden="true" className={`sidebar-switch${darkMode ? ' on' : ''}`}><span /></span>
              </button>
              <button
                type="button"
                className="sidebar-preference"
                aria-pressed={advancedFeatures}
                onClick={() => togglePreference('workloop-advanced-features', setAdvancedFeatures)}
              >
                <span aria-hidden="true">☷</span>
                <span className="sidebar-preference-label">Advanced features</span>
                <span aria-hidden="true" className={`sidebar-switch${advancedFeatures ? ' on' : ''}`}><span /></span>
              </button>
            </div>
          )}
          <button type="button" className="sidebar-signout" onClick={() => authentication.logout()}>
            <span aria-hidden="true">↪</span>
            <span className="sidebar-signout-label">Sign out</span>
          </button>
        </div>
      </aside>
      <div className={`main-content${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
        <header className="page-header portal-header">
          <div>
            <h1 ref={headingRef} tabIndex="-1">{route.title}</h1>
            <p className="route-description">{description}</p>
          </div>
          {account.role === 'admin' && (
            <button type="button" className="btn btn-outline branch-action" onClick={organization.clearBranch}>Change branch</button>
          )}
        </header>
        <div className="page-body">
          {route.path === roleHome(account.role) && account.role === 'admin' && (
            <section className="welcome-banner" aria-label="Welcome">
              <h2>Workloop - UAE Payroll &amp; HRMS</h2>
              <p>Welcome back to {organizationName}</p>
            </section>
          )}
          {account.role === 'admin' && route.path !== '/admin' ? (
            <AdministratorPortal
              account={account}
              authentication={authentication}
              branchId={branch.id}
              clearBranch={organization.clearBranch}
              navigator={navigator}
              path={route.path}
            />
          ) : account.role === 'manager' ? (
            <ManagerPortal
              account={account}
              authentication={authentication}
              branchId={branch.id}
              navigator={navigator}
              path={route.path}
            />
          ) : account.role === 'employee' ? (
            <EmployeePortal
              account={account}
              authentication={authentication}
              branchId={branch.id}
              navigator={navigator}
              path={route.path}
            />
          ) : (
            <div className="portal-columns">
              <Dashboard authentication={authentication} branchId={branch.id} kind={dashboardKind} />
            </div>
          )}
        </div>
      </div>
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
        key={`${account.role}:${account.companyId}:${account.employeeId}`}
        account={account}
        authentication={authentication}
        navigator={navigator}
        route={route}
      />
    </CompanyProvider>
  )
}
