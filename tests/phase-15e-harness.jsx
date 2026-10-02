import { createRoot } from 'react-dom/client'

import PortalShell from '../src/PortalShell.jsx'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const companyId = 'b2000000-0000-4000-8000-000000000001'
const employeeId = 'b2000000-0000-4000-8000-000000000003'
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
}

const employee = {
  id: employeeId,
  empNo: 'E-001',
  name: 'Synthetic Employee',
  photoUrl: '',
  workEmail: 'employee@example.test',
  jobTitle: 'Nurse',
  department: 'Clinical',
  employmentStartDate: '2025-02-03',
  probationEndDate: null,
  employmentStatus: 'active',
  basicSalary: '8000.00',
  housingAllowance: '1000.00',
  transportAllowance: '500.00',
  otherAllowances: '0.00',
  bankName: 'Synthetic Bank',
  updatedAt: timestamp,
  molId: 'MOL-002',
  bankRoutingCode: 'BANK-A',
  iban: 'AE000000000000000000002',
  allowance: '250.00',
  personalEmail: 'employee.personal@example.test',
  phone: '+971500000003',
  dateOfBirth: '1992-01-01',
  gender: 'female',
  maritalStatus: 'single',
  homeCountryAddress: 'Synthetic address',
  emergencyContactName: 'Synthetic Contact',
  emergencyContactRelationship: 'Sibling',
  emergencyContactPhone: '+971500000004',
  probationExtended: false,
  terminationDate: null,
  terminationReason: '',
  otherAllowancesLabel: '',
  bankAccountHolder: 'Synthetic Employee',
  nationality: 'Synthetic',
  visaType: 'employment_visa',
  visaNumber: 'VISA-002',
  visaExpiry: null,
  passportNumber: 'P-002',
  passportExpiry: null,
  emiratesId: '784-0000-0000000-2',
  emiratesIdExpiry: null,
  labourCardNumber: 'LC-002',
  labourCardExpiry: null,
  sponsoringEntity: 'Synthetic clinic',
  workLocationType: 'mainland',
  freeZoneName: '',
  nafisRegistrationNo: '',
  licenceAuthority: 'DHA',
  licenceNumber: 'LIC-002',
  licenceExpiry: null,
  reportingManager: null,
}

function response(path) {
  if (path === '/api/v1/employer') {
    return { data: {
      companyName: 'Synthetic clinic',
      branchName: branch.name,
      branchContactEmail: branch.contactEmail,
      branchAddress: branch.address,
      workLocationType: branch.workLocationType,
      freeZoneName: '',
      logoUrl: '',
    } }
  }
  if (path === '/api/v1/branches?limit=100') {
    return { data: [branch], page: { limit: 100, nextCursor: null, hasMore: false } }
  }
  if (path === '/api/v1/employees/self') return { data: employee }
  throw new Error('Synthetic protected service is unavailable')
}

export function mountPhase15EEmployee({ path = '/employee', storedBranchId = branchId } = {}) {
  document.body.innerHTML = '<div id="phase-15e-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  if (storedBranchId !== null) sessionStorage.setItem('workloop.branchId', storedBranchId)
  window.__phase15eCalls = []
  window.__phase15eLoggedOut = false
  window.__phase15eUnhandled = []
  window.addEventListener('unhandledrejection', (event) => {
    window.__phase15eUnhandled.push(String(event.reason))
    event.preventDefault()
  }, { once: true })
  const account = { appUserId, role: 'employee', companyId, employeeId, branchId }
  const authentication = {
    async logout() { window.__phase15eLoggedOut = true },
    async request(requestPath, options = {}) {
      window.__phase15eCalls.push({
        path: requestPath,
        method: options.method ?? 'GET',
        branch: options.headers?.['X-Workloop-Branch-ID'] ?? null,
      })
      return response(requestPath)
    },
  }
  createRoot(document.getElementById('phase-15e-root')).render(
    <main id="portal-content">
      <PortalShell account={account} authentication={authentication} />
    </main>,
  )
}

export function mountPhase15EForbidden({ path = '/admin/people' } = {}) {
  document.body.innerHTML = '<div id="phase-15e-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  window.__phase15eCalls = []
  const authentication = {
    async logout() {},
    async request(requestPath) {
      window.__phase15eCalls.push({ path: requestPath })
      throw new Error('No protected request expected')
    },
  }
  createRoot(document.getElementById('phase-15e-root')).render(
    <main id="portal-content">
      <PortalShell
        account={{ appUserId, role: 'employee', companyId, employeeId, branchId }}
        authentication={authentication}
      />
    </main>,
  )
}
