import { createRoot } from 'react-dom/client'

import PortalShell from '../src/PortalShell.jsx'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const companyId = 'b2000000-0000-4000-8000-000000000001'
const employeeId = 'b2000000-0000-4000-8000-000000000003'
const appUserId = 'b2000000-0000-4000-8000-000000000004'
const timestamp = '2026-10-02T08:00:00.000Z'

const adminBranch = {
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

const staffBranch = Object.fromEntries(Object.entries(adminBranch).filter(([name]) => ![
  'molEmployerId', 'defaultBankRoutingCode', 'defaultSalaryDay', 'enableStaffingRules',
  'enableBiometricImport', 'createdAt', 'updatedAt',
].includes(name)))

function response(path, role) {
  if (path === '/api/v1/company') {
    return { data: {
      id: companyId,
      name: 'Synthetic clinic',
      sector: 'Healthcare',
      nafisQuotaPercent: '2.00',
      enableNafis: true,
      createdAt: timestamp,
      updatedAt: timestamp,
    } }
  }
  if (path === '/api/v1/employer') {
    return { data: {
      companyName: 'Synthetic clinic',
      branchName: 'Dubai clinic',
      branchContactEmail: 'clinic@example.test',
      branchAddress: 'Synthetic address',
      workLocationType: 'mainland',
      freeZoneName: '',
      logoUrl: '',
    } }
  }
  if (path === '/api/v1/branches?limit=100') {
    return {
      data: [role === 'admin' ? adminBranch : staffBranch],
      page: { limit: 100, nextCursor: null, hasMore: false },
    }
  }
  throw new Error('Synthetic common entry is unavailable')
}

export function mountPhase15BShell({ path = '/', role = 'admin', storedBranchId = branchId } = {}) {
  document.body.innerHTML = '<div id="phase-15b-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  if (storedBranchId !== null) sessionStorage.setItem('workloop.branchId', storedBranchId)
  window.__phase15bCalls = []
  window.__phase15bLoggedOut = false
  const account = {
    appUserId,
    role,
    companyId,
    employeeId: role === 'admin' ? null : employeeId,
    branchId: role === 'admin' ? null : branchId,
  }
  const authentication = {
    async logout() { window.__phase15bLoggedOut = true },
    async request(requestPath) {
      window.__phase15bCalls.push(requestPath)
      return response(requestPath, role)
    },
  }
  createRoot(document.getElementById('phase-15b-root')).render(
    <>
      <a className="skip-link" href="#portal-content">Skip to main content</a>
      <main id="portal-content">
        <PortalShell account={account} authentication={authentication} />
      </main>
    </>,
  )
}
