import { createRoot } from 'react-dom/client'

import PortalShell from '../src/PortalShell.jsx'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const companyId = 'b2000000-0000-4000-8000-000000000001'
const appUserId = 'b2000000-0000-4000-8000-000000000004'
const timestamp = '2026-10-02T08:00:00.000Z'

const branch = {
  id: branchId,
  name: 'Dubai clinic',
  address: 'Synthetic address',
  contactEmail: 'clinic@example.test',
  workLocationType: 'mainland',
  freeZoneName: '',
  logoUrl: '',
  molEmployerId: 'synthetic-employer',
  defaultBankRoutingCode: 'synthetic-bank',
  defaultSalaryDay: 28,
  enableStaffingRules: false,
  enableBiometricImport: false,
  createdAt: timestamp,
  updatedAt: timestamp,
}

function commonResponse(path) {
  if (path === '/api/v1/company') {
    return {
      data: {
        id: companyId,
        name: 'Synthetic clinic',
        sector: 'Healthcare',
        nafisQuotaPercent: '2.00',
        enableNafis: true,
        createdAt: timestamp,
        updatedAt: timestamp,
      },
    }
  }
  if (path === '/api/v1/branches?limit=100') {
    return { data: [branch], page: { limit: 100, nextCursor: null, hasMore: false } }
  }
  throw new Error('Synthetic protected service is unavailable')
}

export function mountPhase15CAdministrator({ path = '/admin', storedBranchId = branchId, responses = {} } = {}) {
  document.body.innerHTML = '<div id="phase-15c-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  if (storedBranchId !== null) sessionStorage.setItem('workloop.branchId', storedBranchId)
  window.__phase15cCalls = []
  window.__phase15cRequests = []
  window.__phase15cLoggedOut = false
  const account = {
    appUserId,
    role: 'admin',
    companyId,
    employeeId: null,
    branchId: null,
  }
  const authentication = {
    async logout() { window.__phase15cLoggedOut = true },
    async request(requestPath, options) {
      window.__phase15cCalls.push(requestPath)
      window.__phase15cRequests.push({ path: requestPath, options })
      if (Object.hasOwn(responses, requestPath)) return structuredClone(responses[requestPath])
      return commonResponse(requestPath)
    },
  }
  createRoot(document.getElementById('phase-15c-root')).render(
    <>
      <a className="skip-link" href="#portal-content">Skip to main content</a>
      <main id="portal-content" tabIndex="-1">
        <PortalShell account={account} authentication={authentication} />
      </main>
    </>,
  )
}

export function mountPhase15CCrossRole({ path = '/admin/payroll' } = {}) {
  document.body.innerHTML = '<div id="phase-15c-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  window.__phase15cCalls = []
  const authentication = {
    async logout() {},
    async request(requestPath) {
      window.__phase15cCalls.push(requestPath)
      throw new Error('No protected request expected')
    },
  }
  createRoot(document.getElementById('phase-15c-root')).render(
    <main id="portal-content" tabIndex="-1">
      <PortalShell
        account={{
          appUserId,
          role: 'manager',
          companyId,
          employeeId: 'b2000000-0000-4000-8000-000000000003',
          branchId,
        }}
        authentication={authentication}
      />
    </main>,
  )
}
