import { createRoot } from 'react-dom/client'
import PortalShell from '../src/PortalShell.jsx'
import '../src/index.css'

const id = (value) => `b2000000-0000-4000-8000-${String(value).padStart(12, '0')}`
const branchId = id(2)
const timestamp = '2026-10-02T08:00:00.000Z'
const page = { limit: 100, hasMore: false, nextCursor: null }
const employee = (number, name, manager = null) => ({
  id: id(number), empNo: `E-${number}`, name, photoUrl: '', workEmail: `${number}@example.test`,
  jobTitle: manager ? 'Nurse' : 'Clinical manager', department: 'Clinical', reportingManagerId: manager,
  employmentStartDate: '2025-01-01', probationEndDate: null, employmentStatus: 'active', active: true,
  basicSalary: '8000.00', housingAllowance: '1000.00', transportAllowance: '500.00',
  otherAllowances: '0.00', bankName: 'Synthetic bank', updatedAt: timestamp,
})
const employees = [employee(3, 'Alex Morgan', id(4)), employee(4, 'Sam Taylor')]
const asset = { id: id(20), name: 'Clinic laptop', assetCode: 'IT-001', category: 'Laptop',
  brand: 'Example', model: 'Pro', serialNumber: 'SN001', purchaseDate: '2026-01-01',
  purchaseCost: '1250.00', status: 'available', notes: '', createdAt: timestamp, updatedAt: timestamp }
const assignment = { id: id(21), assetId: asset.id, employeeId: employees[0].id, assetName: asset.name,
  assetCode: asset.assetCode, status: 'assigned', assignedDate: '2026-09-01', returnDate: '2026-09-30',
  conditionAtHandover: 'good', conditionAtReturn: 'good', notes: 'Returned to IT', createdAt: timestamp }
const training = { id: id(30), employeeId: employees[0].id, trainingTitle: 'Emergency response', trainingType: 'external',
  provider: 'Training centre', startDate: '2026-10-01', endDate: '2026-10-03', durationHours: '8.00',
  cost: '200.00', status: 'planned', score: '', passed: null, notes: '', isCme: true, hasEvidence: false,
  fileName: null, contentType: null, createdAt: timestamp, updatedAt: timestamp }
const certification = { id: id(31), employeeId: employees[0].id, certificationName: 'Basic life support',
  issuingBody: 'Training centre', certificateNo: 'BLS001', issuedDate: '2026-01-01', expiryDate: '2027-01-01',
  notes: '', status: 'pending_review', hasEvidence: true, fileName: 'bls.pdf', contentType: 'application/pdf',
  reviewedAt: null, createdAt: timestamp, updatedAt: timestamp }
const requirement = { id: id(32), employeeId: employees[0].id, year: 2026, requiredHours: '25.0',
  notes: '', createdAt: timestamp, updatedAt: timestamp }
const appraisal = { id: id(41), cycleId: id(40), cycleName: 'H2 2026', reviewFrom: '2026-07-01', reviewTo: '2026-12-31',
  employeeId: employees[0].id, employeeName: employees[0].name, employeeDepartment: 'Clinical', employeeJobTitle: 'Nurse', cycleStatus: 'active', templateVersion: 'clinic-v1', overallRating: null,
  status: 'pending', reviewerComments: '', developmentPlan: '', reviewedAt: null, reviewedByAppUserId: null,
  createdAt: timestamp, updatedAt: timestamp, sections: ['Clinical Competency', 'Patient Care Quality', 'Communication and Teamwork', 'Punctuality and Attendance', 'Professional Development'].map((sectionName, index) => ({ id: id(42 + index), sectionName,
    weight: ['2.00', '2.00', '1.50', '1.00', '1.00'][index], rating: '4.0', comments: 'Strong progress', sortOrder: (index + 1) * 10, updatedAt: timestamp })) }
const cycle = { id: id(40), name: 'H2 2026', reviewFrom: '2026-07-01', reviewTo: '2026-12-31', status: 'active',
  closedByAppUserId: null, closedAt: null, createdAt: timestamp, updatedAt: timestamp, appraisals: [appraisal] }
const incident = { id: id(50), incidentDate: '2026-10-01', incidentTime: '10:30:00', location: 'Treatment room',
  department: 'Clinical', incidentType: 'near_miss', severity: 'high', description: 'Equipment check near miss',
  reportedById: employees[0].id, reportedByName: employees[0].name, involvedEmpId: employees[1].id,
  involvedEmployeeName: employees[1].name, immediateAction: 'Equipment isolated', rootCause: '',
  correctiveAction: '', status: 'open', closedDate: null, closedByAppUserId: null, notes: '',
  createdAt: timestamp, updatedAt: timestamp }
const departments = [{ id: id(10), name: 'Clinical', parentId: null, headEmployeeId: employees[1].id,
  color: '#6366f1', description: 'Clinical care', sortOrder: 0, createdAt: timestamp }]
const rules = [{ id: id(11), department: 'Clinical', shiftCategory: 'morning', minStaff: 2, effectiveFrom: null, effectiveTo: null }]
const branch = { id: branchId, name: 'Dubai clinic', address: 'Synthetic address', contactEmail: 'clinic@example.test',
  workLocationType: 'mainland', freeZoneName: '', logoUrl: '', molEmployerId: 'MOL-001', defaultBankRoutingCode: 'BANK-A',
  defaultSalaryDay: 28, enableStaffingRules: true, enableBiometricImport: false, createdAt: timestamp, updatedAt: timestamp }
const query = new URLSearchParams(location.search)
const moduleName = query.get('module') ?? 'assets'
if (!query.has('fixtureOnly')) window.history.replaceState(null, '', `/admin/${moduleName}`)
sessionStorage.setItem('workloop.branchId', branchId)
window.__restorationRequests = []
window.__restorationFailNext = false
const fixture = {
  async logout() {},
  async request(path, options = {}) {
    window.__restorationRequests.push({ path, options })
    const url = new URL(path, location.origin)
    const route = url.pathname
    const method = options.method ?? 'GET'
    const body = options.json ?? {}
    if (method !== 'GET' && window.__restorationFailNext) { window.__restorationFailNext = false; throw new Error('Synthetic rejected write') }
    if (route === '/api/v1/company') return { data: { id: id(1), name: 'Synthetic clinic', sector: 'Healthcare', nafisQuotaPercent: '2.00', enableNafis: true, createdAt: timestamp, updatedAt: timestamp } }
    if (route === '/api/v1/branches') return { data: [branch], page }
    if (route === `/api/v1/branches/${branchId}`) return { data: branch }
    if (route === '/api/v1/employees') return { data: employees, page }
    if (route === '/api/v1/departments') {
      if (method === 'POST') { const added = { id: id(12), ...body, createdAt: timestamp }; departments.push(added); return { data: added } }
      return { data: departments, page }
    }
    if (route === '/api/v1/department-staffing-rules') {
      if (method === 'POST') {
        const added = { id: id(13), ...body }
        rules.push(added)
        return { data: added, status: 201, location: `/api/v1/department-staffing-rules/${added.id}` }
      }
      return { data: rules, page }
    }
    if (route.startsWith('/api/v1/department-staffing-rules/')) { Object.assign(rules[0], body); delete rules[0].expected; return { data: rules[0] } }
    if (route === '/api/v1/assets/assignments') return { data: [{ ...assignment, employeeName: employees[0].name }], page }
    if (route === '/api/v1/assets') {
      if (method === 'POST') return { data: { ...asset, ...body } }
      return { data: [asset], page }
    }
    if (route.startsWith(`/api/v1/assets/${asset.id}`)) {
      if (route.endsWith('/assign')) { asset.status = 'assigned'; Object.assign(assignment, { employeeId: body.employeeId, assignedDate: body.assignedDate, returnDate: null, conditionAtHandover: body.conditionAtHandover }); return { data: assignment } }
      if (route.endsWith('/return')) { asset.status = 'available'; Object.assign(assignment, { returnDate: body.returnDate, conditionAtReturn: body.conditionAtReturn }); return { data: assignment } }
      if (method === 'DELETE') throw new Error('Assignment history prevents deletion')
      Object.assign(asset, body); delete asset.expectedUpdatedAt; return { data: asset }
    }
    if (route === '/api/v1/training-records') return method === 'POST' ? { data: { ...training, ...body, id: id(33) } } : { data: [training], page }
    if (route === `/api/v1/training-records/${training.id}/complete`) { Object.assign(training, body, { status: 'completed' }); delete training.expectedUpdatedAt; return { data: training } }
    if (route === '/api/v1/certifications') return { data: [certification], page }
    if (route === `/api/v1/certifications/${certification.id}`) { Object.assign(certification, body, { status: 'pending_review', reviewedAt: null }); delete certification.expectedUpdatedAt; return { data: certification } }
    if (route === `/api/v1/certifications/${certification.id}/reject`) { Object.assign(certification, { status: 'rejected', notes: body.reason, reviewedAt: timestamp }); return { data: certification } }
    if (route === '/api/v1/cme/summary') return { data: [{ employeeId: employees[0].id, employeeName: employees[0].name, department: 'Clinical', year: Number(url.searchParams.get('year')), targetHours: requirement.requiredHours, achievedHours: '12.0', inProgressHours: '8.0', gapHours: '13.0', requirement: { ...requirement, year: Number(url.searchParams.get('year')) } }], page }
    if (route.startsWith('/api/v1/cme/requirements/')) { Object.assign(requirement, body); delete requirement.expectedUpdatedAt; return { data: requirement } }
    if (route === '/api/v1/appraisal-cycles') return { data: [cycle], page }
    if (route === `/api/v1/appraisals/${appraisal.id}/admin-review`) { Object.assign(appraisal, { ...body, sections: appraisal.sections.map((section) => ({ ...section, ...body.sections.find((item) => item.id === section.id) })), status: 'reviewed', overallRating: '4.0', reviewedAt: timestamp, reviewedByAppUserId: id(5) }); delete appraisal.expectedUpdatedAt; return { data: appraisal } }
    if (route === `/api/v1/appraisals/${appraisal.id}/review`) { Object.assign(appraisal, body, { status: 'reviewed', overallRating: '4.0', reviewedAt: timestamp, reviewedByAppUserId: id(5) }); delete appraisal.expectedUpdatedAt; return { data: appraisal } }
    if (route === '/api/v1/clinical-incidents') return { data: [incident], page }
    if (route === `/api/v1/clinical-incidents/${incident.id}`) { Object.assign(incident, body); delete incident.expectedUpdatedAt; return { data: incident } }
    if (route === `/api/v1/clinical-incidents/${incident.id}/investigate`) { Object.assign(incident, { status: 'investigating', rootCause: body.rootCause }); return { data: incident } }
    throw new Error(`No synthetic response for ${method} ${path}`)
  },
}
const authentication = {
  async logout() {},
  async request(...args) { return structuredClone(await fixture.request(...args)) },
}
const account = { role: 'admin', appUserId: id(5), companyId: id(1), employeeId: null, branchId: null }
export const restorationFixture = { account, authentication, branchId, branch }
if (!query.has('fixtureOnly')) createRoot(document.getElementById('root')).render(<PortalShell account={account} authentication={authentication} />)
