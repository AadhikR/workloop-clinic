import { createRoot } from 'react-dom/client'

import PortalShell from '../src/PortalShell.jsx'

const branchId = 'b2000000-0000-4000-8000-000000000002'
const companyId = 'b2000000-0000-4000-8000-000000000001'
const managerId = 'b2000000-0000-4000-8000-000000000003'
const reportId = 'b2000000-0000-4000-8000-000000000005'
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

const manager = {
  id: managerId,
  empNo: 'M-001',
  name: 'Synthetic Manager',
  photoUrl: '',
  workEmail: 'manager@example.test',
  jobTitle: 'Clinic manager',
  department: 'Clinical',
  employmentStartDate: '2025-01-02',
  probationEndDate: null,
  employmentStatus: 'active',
  basicSalary: '10000.00',
  housingAllowance: '1000.00',
  transportAllowance: '500.00',
  otherAllowances: '0.00',
  bankName: 'Synthetic Bank',
  updatedAt: timestamp,
  molId: 'MOL-001',
  bankRoutingCode: 'BANK-A',
  iban: 'AE000000000000000000001',
  allowance: '250.00',
  personalEmail: 'manager.personal@example.test',
  phone: '+971500000001',
  dateOfBirth: '1990-01-01',
  gender: 'female',
  maritalStatus: 'single',
  homeCountryAddress: 'Synthetic address',
  emergencyContactName: 'Synthetic Contact',
  emergencyContactRelationship: 'Sibling',
  emergencyContactPhone: '+971500000002',
  probationExtended: false,
  terminationDate: null,
  terminationReason: '',
  otherAllowancesLabel: '',
  bankAccountHolder: 'Synthetic Manager',
  nationality: 'Synthetic',
  visaType: 'employment_visa',
  visaNumber: 'VISA-001',
  visaExpiry: null,
  passportNumber: 'P-001',
  passportExpiry: null,
  emiratesId: '784-0000-0000000-1',
  emiratesIdExpiry: null,
  labourCardNumber: 'LC-001',
  labourCardExpiry: null,
  sponsoringEntity: 'Synthetic clinic',
  workLocationType: 'mainland',
  freeZoneName: '',
  nafisRegistrationNo: '',
  licenceAuthority: 'DHA',
  licenceNumber: 'LIC-001',
  licenceExpiry: null,
  reportingManager: null,
}

const report = {
  id: reportId,
  empNo: 'E-001',
  name: 'Synthetic Direct Report',
  photoUrl: '',
  jobTitle: 'Nurse',
  department: 'Clinical',
  employmentStartDate: '2025-02-03',
  probationEndDate: null,
  employmentStatus: 'active',
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
  if (path === '/api/v1/employees/self') return { data: manager }
  if (path === '/api/v1/employees/direct-reports') {
    return { data: [report], page: { limit: 50, nextCursor: null, hasMore: false } }
  }
  if (path === '/api/v1/expenses/self' || path === '/api/v1/expenses/manager-queue') {
    return { data: [], page: { limit: 50, nextCursor: null, hasMore: false } }
  }
  if (path === '/api/v1/appraisals/self' || path === '/api/v1/appraisals/direct-reports') {
    return { data: [], page: { limit: 50, nextCursor: null, hasMore: false } }
  }
  throw new Error('Synthetic protected service is unavailable')
}

export function mountPhase15DManager({ path = '/manager', storedBranchId = branchId } = {}) {
  document.body.innerHTML = '<div id="phase-15d-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  if (storedBranchId !== null) sessionStorage.setItem('workloop.branchId', storedBranchId)
  window.__phase15dCalls = []
  window.__phase15dLoggedOut = false
  const account = { appUserId, role: 'manager', companyId, employeeId: managerId, branchId }
  const authentication = {
    async logout() { window.__phase15dLoggedOut = true },
    async request(requestPath, options = {}) {
      window.__phase15dCalls.push({
        path: requestPath,
        method: options.method ?? 'GET',
        branch: options.headers?.['X-Workloop-Branch-ID'] ?? null,
      })
      return response(requestPath)
    },
  }
  createRoot(document.getElementById('phase-15d-root')).render(
    <main id="portal-content">
      <PortalShell account={account} authentication={authentication} />
    </main>,
  )
}

export function mountPhase15DAdminRoute({ path = '/admin/payroll' } = {}) {
  document.body.innerHTML = '<div id="phase-15d-root"></div>'
  window.history.replaceState(null, '', path)
  sessionStorage.clear()
  window.__phase15dCalls = []
  const authentication = {
    async logout() {},
    async request(requestPath) {
      window.__phase15dCalls.push({ path: requestPath })
      throw new Error('No protected request expected')
    },
  }
  createRoot(document.getElementById('phase-15d-root')).render(
    <main id="portal-content">
      <PortalShell
        account={{ appUserId, role: 'manager', companyId, employeeId: managerId, branchId }}
        authentication={authentication}
      />
    </main>,
  )
}
