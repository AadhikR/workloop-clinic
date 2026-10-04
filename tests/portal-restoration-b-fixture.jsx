import { createRoot } from 'react-dom/client'
import { CompanyProvider } from '../src/CompanyContext.jsx'
import EmployeeDirectory from '../src/EmployeeDirectory.jsx'
import LetterRequests from '../src/LetterRequests.jsx'
import OrganizationSettings from '../src/OrganizationSettings.jsx'
import '../src/index.css'

const id = (value) => `b2000000-0000-4000-8000-${String(value).padStart(12, '0')}`
const branchId = id(2)
const timestamp = '2026-10-02T08:00:00.000Z'
const page = { limit: 100, hasMore: false, nextCursor: null }
const account = { role: 'admin', appUserId: id(5), companyId: id(1), employeeId: null, branchId: null }
const detail = (number, name, overrides = {}) => ({
  id: id(number), empNo: `E-${number}`, name, photoUrl: '', workEmail: `${number}@example.test`,
  jobTitle: 'Registered nurse', department: 'Clinical', reportingManagerId: id(4),
  employmentStartDate: '2025-01-01', probationEndDate: '2025-06-30', employmentStatus: 'active', active: true,
  basicSalary: '8000.00', housingAllowance: '1000.00', transportAllowance: '500.00', otherAllowances: '250.00',
  bankName: 'Synthetic bank', updatedAt: timestamp, molId: '1234567890', bankRoutingCode: '123456789',
  iban: 'AE070331234567890123456', allowance: '300.00', personalEmail: `${number}@personal.test`, phone: '+971501234567',
  dateOfBirth: '1990-01-01', gender: 'female', maritalStatus: 'single', homeCountryAddress: 'Synthetic address',
  emergencyContactName: 'Morgan Lee', emergencyContactRelationship: 'Sibling', emergencyContactPhone: '+971501111111',
  probationExtended: false, terminationDate: null, terminationReason: '', otherAllowancesLabel: 'Clinical allowance',
  bankAccountHolder: name, nationality: 'Emirati', visaType: 'employment_visa', visaNumber: 'VISA-1',
  visaExpiry: '2027-01-31', passportNumber: 'P123456', passportExpiry: '2027-02-28', emiratesId: '784-0000-0000000-0',
  emiratesIdExpiry: '2026-10-31', labourCardNumber: 'LC-1', labourCardExpiry: '2027-03-31',
  sponsoringEntity: 'Synthetic clinic', workLocationType: 'mainland', freeZoneName: '', nafisRegistrationNo: 'NAFIS-1',
  licenceAuthority: 'DHA', licenceNumber: 'DHA-1', licenceExpiry: '2027-04-30', createdAt: timestamp, ...overrides,
})
let employees = [detail(3, 'Alex Morgan'), detail(4, 'Sam Taylor', { reportingManagerId: null, jobTitle: 'Clinical manager' })]
const listEmployee = (employee) => {
  const detailOnly = ['molId', 'bankRoutingCode', 'iban', 'allowance', 'personalEmail', 'phone', 'dateOfBirth', 'gender', 'maritalStatus', 'homeCountryAddress', 'emergencyContactName', 'emergencyContactRelationship', 'emergencyContactPhone', 'probationExtended', 'terminationDate', 'terminationReason', 'otherAllowancesLabel', 'bankAccountHolder', 'nationality', 'visaType', 'visaNumber', 'visaExpiry', 'passportNumber', 'passportExpiry', 'emiratesId', 'emiratesIdExpiry', 'labourCardNumber', 'labourCardExpiry', 'sponsoringEntity', 'workLocationType', 'freeZoneName', 'nafisRegistrationNo', 'licenceAuthority', 'licenceNumber', 'licenceExpiry', 'createdAt']
  return Object.fromEntries(Object.entries(employee).filter(([key]) => !detailOnly.includes(key)))
}
const company = { id: id(1), name: 'Synthetic clinic', sector: 'Healthcare', nafisQuotaPercent: '2.00', enableNafis: true, createdAt: timestamp, updatedAt: timestamp }
let branch = { id: branchId, name: 'Dubai clinic', address: 'Synthetic address', contactEmail: 'clinic@example.test', workLocationType: 'mainland', freeZoneName: '', logoUrl: '', molEmployerId: '1234567890123', defaultBankRoutingCode: '123456789', defaultSalaryDay: 28, enableStaffingRules: true, enableBiometricImport: false, createdAt: timestamp, updatedAt: timestamp }
const policy = { id: id(20), insurerName: 'Example Health', policyNumber: 'POL-1', tierName: 'Gold', annualPremium: '4500.00', renewalDate: '2027-01-01', brokerName: 'Example Broker', brokerContact: 'broker@example.test', notes: '', createdAt: timestamp, updatedAt: timestamp }
const documentRecord = { id: id(21), employeeId: id(3), documentType: 'Emirates ID', status: 'verified', rejectionReason: null, fileName: 'emirates-id.pdf', sizeBytes: 1200, contentType: 'application/pdf', expiryDate: '2026-10-31', notes: '', reviewerName: 'Admin User', uploadedAt: timestamp, reviewedAt: timestamp, updatedAt: timestamp }
const dependant = { id: id(22), employeeId: id(3), name: 'Jamie Morgan', relationship: 'Child', dateOfBirth: '2018-01-01', cardNumber: 'CARD-2', createdAt: timestamp, updatedAt: timestamp }
const contract = { id: id(23), employeeId: id(3), contractType: 'Limited', startDate: '2025-01-01', endDate: '2027-01-01', action: 'new', notes: '', actorName: 'Admin User', createdAt: timestamp }
const request = (number, kind, status) => ({ id: id(number), employeeId: id(3), employeeName: 'Alex Morgan', jobTitle: 'Registered nurse', department: 'Clinical', employmentStartDate: '2025-01-01', branchName: 'Dubai clinic', requestKind: kind, letterType: kind === 'letter' ? 'employment_confirmation' : 'Shift change request', purpose: kind === 'letter' ? 'Housing application' : 'Please review the proposed shift change.', status, notes: '', rejectionReason: '', requestedAt: timestamp, completedAt: status === 'completed' ? timestamp : null, actionedAt: status === 'pending' ? null : timestamp, updatedAt: timestamp })
let requests = [request(30, 'letter', 'completed'), request(31, 'custom', 'completed'), request(32, 'letter', 'pending'), request(33, 'custom', 'rejected')]

const query = new URLSearchParams(location.search)
const moduleName = query.get('module') ?? 'organization'
sessionStorage.setItem('workloop.branchId', branchId)
window.__restorationRequests = []
window.__restorationFailNext = false
const authentication = {
  async logout() {},
  async request(path, options = {}) {
    window.__restorationRequests.push({ path, options })
    const url = new URL(path, location.origin)
    const route = url.pathname
    const method = options.method ?? 'GET'
    const body = options.json ?? {}
    if (method !== 'GET' && window.__restorationFailNext) { window.__restorationFailNext = false; throw new Error('Synthetic rejected write') }
    if (route === '/api/v1/company') { if (method === 'PATCH') Object.assign(company, body); delete company.expectedUpdatedAt; return { data: structuredClone(company) } }
    if (route === '/api/v1/branches') return { data: [structuredClone(branch)], page }
    if (route === `/api/v1/branches/${branchId}`) { Object.assign(branch, body, { updatedAt: '2026-10-02T09:00:00.000Z' }); delete branch.expectedUpdatedAt; return { data: structuredClone(branch) } }
    if (route === '/api/v1/idempotency-recovery-namespaces') return { data: { current: 'restoration-b', accepted: ['restoration-b'] } }
    if (route === '/api/v1/departments') return { data: [{ id: id(10), name: 'Clinical', parentId: null, headEmployeeId: id(4), color: '#6366f1', description: 'Clinical care', sortOrder: 0, createdAt: timestamp }], page }
    if (route === '/api/v1/employees') return { data: employees.map(listEmployee), page }
    if (route === '/api/v1/employee-job-history') return { data: [], page }
    if (/^\/api\/v1\/employees\/[0-9a-f-]+$/.test(route)) return { data: structuredClone(employees.find((item) => route.endsWith(item.id))) }
    if (route.endsWith('/job-history')) return { data: [{ id: id(40), employeeId: id(3), changedAt: timestamp, changedByAppUserId: id(5), changeType: 'title_change', oldValue: 'Nurse', newValue: 'Registered nurse', reason: 'Promotion' }], page }
    if (route.endsWith('/profile-save')) { const current = employees.find((item) => route.includes(item.id)); Object.assign(current, body.profile, body, { updatedAt: '2026-10-02T09:00:00.000Z' }); delete current.expectedUpdatedAt; delete current.profile; delete current.reason; return { data: structuredClone(current), status: 200 } }
    if (route.endsWith('/portal-role')) return { data: { employeeId: id(3), activated: true, role: 'employee' } }
    if (route === '/api/v1/offboarding') return { data: [{ id: id(41), employeeId: id(3), employeeName: 'Alex Morgan', employmentStatus: 'active', status: 'in_progress', visaCancellationStatus: 'not_started', visaCancellationDate: null, finalSettlementId: null, createdAt: timestamp, updatedAt: timestamp, completedAt: null, tasks: [{ id: id(42), taskName: 'Return clinic property', completed: false, completedAt: null, notes: '', sortOrder: 1, source: 'template', templateId: id(43), updatedAt: timestamp }] }], page }
    if (route === '/api/v1/employee-documents') return { data: [documentRecord], page }
    if (route === '/api/v1/insurance/policies') return { data: [policy], page }
    if (route.endsWith('/dependants')) return { data: [dependant], page }
    if (route.endsWith('/contracts')) return { data: [contract], page }
    if (route === '/api/v1/requests' || route === '/api/v1/requests/self') return { data: requests, page }
    if (route.endsWith('/print-source')) return { data: { requestId: id(30), requestKind: 'letter', letterType: 'employment_confirmation', purpose: 'Housing application', employeeName: 'Alex Morgan', jobTitle: 'Registered nurse', department: 'Clinical', employmentStartDate: '2025-01-01', branchName: 'Dubai clinic', basicSalary: null, allowance: null, requestedAt: timestamp, completedAt: timestamp } }
    if (route.endsWith('/complete')) { requests = requests.map((item) => route.includes(item.id) ? { ...item, status: 'completed', completedAt: timestamp, actionedAt: timestamp } : item); return { data: requests.find((item) => route.includes(item.id)) } }
    throw new Error(`No synthetic response for ${method} ${path}`)
  },
}

let content
if (moduleName === 'organization') content = <CompanyProvider account={account} authentication={authentication}><OrganizationSettings authentication={authentication} /></CompanyProvider>
else if (moduleName === 'employees') content = <EmployeeDirectory account={account} authentication={authentication} branchId={branchId} clearBranch={() => {}} />
else content = <LetterRequests account={{ ...account, role: moduleName === 'manager-requests' ? 'manager' : 'admin', employeeId: moduleName === 'manager-requests' ? id(3) : null, branchId: moduleName === 'manager-requests' ? branchId : null }} authentication={authentication} branchId={branchId} />
createRoot(document.getElementById('root')).render(<main className="portal-main"><div className="portal-route">{content}</div></main>)
