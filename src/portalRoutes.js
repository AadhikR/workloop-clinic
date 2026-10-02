const routeDefinitions = [
  ['P15-ROUTE-001', '/', ['public', 'admin', 'manager', 'employee'], '15B', 'Sign in'],
  ['P15-ROUTE-002', '/oidc/callback', ['public'], '15B', 'Signing in'],
  ['P15-ROUTE-003', '/forbidden', ['admin', 'manager', 'employee'], '15B', 'Access denied'],
  ['P15-ROUTE-004', '/unavailable', ['admin', 'manager', 'employee'], '15B', 'Page unavailable'],
  ['P15-ROUTE-005', '/admin', ['admin'], '15C', 'Administrator home'],
  ['P15-ROUTE-006', '/admin/organization', ['admin'], '15C', 'Organization'],
  ['P15-ROUTE-007', '/admin/people', ['admin'], '15C', 'People'],
  ['P15-ROUTE-008', '/admin/leave', ['admin'], '15C', 'Leave'],
  ['P15-ROUTE-009', '/admin/attendance', ['admin'], '15C', 'Attendance'],
  ['P15-ROUTE-010', '/admin/roster', ['admin'], '15C', 'Roster'],
  ['P15-ROUTE-011', '/admin/payroll', ['admin'], '15C', 'Payroll'],
  ['P15-ROUTE-012', '/admin/records', ['admin'], '15C', 'Records'],
  ['P15-ROUTE-013', '/admin/development', ['admin'], '15C', 'Development'],
  ['P15-ROUTE-014', '/admin/reports', ['admin'], '15C', 'Reports'],
  ['P15-ROUTE-015', '/manager', ['manager'], '15D', 'Manager home'],
  ['P15-ROUTE-016', '/manager/team', ['manager'], '15D', 'Team'],
  ['P15-ROUTE-017', '/manager/leave', ['manager'], '15D', 'Leave'],
  ['P15-ROUTE-018', '/manager/time', ['manager'], '15D', 'Time'],
  ['P15-ROUTE-019', '/manager/expenses', ['manager'], '15D', 'Expenses'],
  ['P15-ROUTE-020', '/manager/development', ['manager'], '15D', 'Development'],
  ['P15-ROUTE-021', '/manager/requests', ['manager'], '15D', 'Requests'],
  ['P15-ROUTE-022', '/employee', ['employee'], '15E', 'Employee home'],
  ['P15-ROUTE-023', '/employee/profile', ['employee'], '15E', 'Profile'],
  ['P15-ROUTE-024', '/employee/leave', ['employee'], '15E', 'Leave'],
  ['P15-ROUTE-025', '/employee/time', ['employee'], '15E', 'Time'],
  ['P15-ROUTE-026', '/employee/pay', ['employee'], '15E', 'Pay'],
  ['P15-ROUTE-027', '/employee/records', ['employee'], '15E', 'Records'],
  ['P15-ROUTE-028', '/employee/development', ['employee'], '15E', 'Development'],
  ['P15-ROUTE-029', '/employee/requests', ['employee'], '15E', 'Requests'],
]

export const portalRouteContracts = Object.freeze(routeDefinitions.map(
  ([id, path, roles, owner]) => Object.freeze({
    id, path, roles: Object.freeze([...roles]), owner,
  }),
))

const routes = new Map(routeDefinitions.map(
  ([id, path, roles, owner, title]) => [path, Object.freeze({ id, path, roles, owner, title })],
))

const homes = Object.freeze({ admin: '/admin', employee: '/employee', manager: '/manager' })

export function roleHome(role) {
  const path = homes[role]
  if (!path) throw new TypeError('Unsupported account role')
  return path
}

export function roleNavigation(role) {
  roleHome(role)
  return Object.freeze(routeDefinitions
    .filter(([, path, roles]) => path.startsWith(`/${role}`) && roles.includes(role))
    .map(([, path, , , title]) => Object.freeze({ path, title })))
}

export function resolvePortalRoute(path, role) {
  const home = roleHome(role)
  if (path === '/') {
    return Object.freeze({ kind: 'redirect', path: home, title: routes.get(home).title })
  }
  const route = routes.get(path)
  if (!route) return Object.freeze({ kind: 'not-found', path, title: 'Page not found' })
  if (path === '/forbidden') return Object.freeze({ kind: 'forbidden', path, title: route.title })
  if (path === '/unavailable') return Object.freeze({ kind: 'unavailable', path, title: route.title })
  if (path === '/oidc/callback') {
    return Object.freeze({ kind: 'redirect', path: home, title: routes.get(home).title })
  }
  if (!route.roles.includes(role)) {
    return Object.freeze({ kind: 'forbidden', path, title: 'Access denied' })
  }
  if (path === home) return Object.freeze({ kind: 'home', path, title: route.title })
  if (
    route.owner === '15C' && role === 'admin'
    || route.owner === '15D' && role === 'manager'
  ) {
    return Object.freeze({ kind: 'portal', path, title: route.title })
  }
  return Object.freeze({ kind: 'unavailable', path, title: route.title })
}

export function createBrowserNavigator(browser) {
  const listeners = new Set()
  const notify = () => {
    for (const listener of listeners) listener(browser.location.pathname)
  }
  const popstate = () => notify()
  return Object.freeze({
    current: () => browser.location.pathname,
    go(path, { replace = false } = {}) {
      const method = replace ? 'replaceState' : 'pushState'
      browser.history[method](null, '', path)
      notify()
    },
    subscribe(listener) {
      if (listeners.size === 0) browser.addEventListener('popstate', popstate)
      listeners.add(listener)
      listener(browser.location.pathname)
      return () => {
        listeners.delete(listener)
        if (listeners.size === 0) browser.removeEventListener('popstate', popstate)
      }
    },
  })
}

export function focusRouteHeading(heading) {
  heading?.focus({ preventScroll: true })
}
