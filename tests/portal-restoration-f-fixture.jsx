import { createRoot } from 'react-dom/client'
import PortalShell from '../src/PortalShell.jsx'
import '../src/index.css'

const query = new URLSearchParams(location.search)
const part = query.get('part') ?? 'e'
if (!/^[a-e]$/.test(part)) throw new Error('Unknown fixture part')
query.set('fixtureOnly', 'true')
window.history.replaceState(null, '', `${location.pathname}?${query}`)
const { restorationFixture: fixture } = await import(`./portal-restoration-${part}-fixture.jsx`)
const account = fixture.account
const branch = typeof fixture.branch === 'function' ? fixture.branch(true) : fixture.branch
const timestamp = '2026-10-05T08:00:00.000Z'
const changedAt = '2026-10-05T08:01:00.000Z'
const page = { limit: 100, hasMore: false, nextCursor: null }
const id = (number) => `${fixture.branchId.slice(0, 24)}${String(number).padStart(12, '0')}`
const company = { id: account.companyId, name: 'Synthetic Clinic', sector: 'Healthcare', nafisQuotaPercent: '2.00', enableNafis: true, createdAt: timestamp, updatedAt: timestamp }
const archived = new Map()
const cancelled = new Set()
let canonicalAppraisal = null
let trainingRecords = []
window.__restorationFRequests = []
window.__restorationFUnhandled = []
window.__restorationFRelease = query.get('state') !== 'loading'
window.__restorationFReject = null
window.__restorationFPending = 0

const contextRoute = (route) => ['/api/v1/company', '/api/v1/employer', '/api/v1/branches', `/api/v1/branches/${branch.id}`].includes(route)
function emptyResponse(response) {
  const value = structuredClone(response)
  if (Array.isArray(value.data)) value.data = []
  else if (value.data && typeof value.data === 'object') {
    for (const field of ['items', 'rows', 'categories', 'departments', 'appraisals', 'assignments', 'records']) {
      if (Array.isArray(value.data[field])) value.data[field] = []
    }
    if (value.data.counts) for (const field of Object.keys(value.data.counts)) value.data.counts[field] = 0
    if (value.data.counts) { value.data.compliant = 0; value.data.rostered = 0 }
    if ('activeEmployees' in value.data) {
      for (const field of ['activeEmployees', 'payrollRuns', 'draftPayrolls', 'sifGenerated', 'insurancePolicies']) value.data[field] = 0
      for (const field of Object.keys(value.data.alerts)) value.data.alerts[field] = 0
    }
    if (value.data.cards) value.data.cards = value.data.cards.map((card) => ({ ...card, value: typeof card.value === 'number' ? 0 : card.unit === 'AED' || card.unit === 'percent' ? '0.00' : card.value }))
    if (value.data.totals) value.data.totals = { ...value.data.totals, rowCount: 0, values: {} }
  }
  if (value.page) value.page = page
  return value
}

async function responseFor(path, options) {
  const url = new URL(path, location.origin)
  const route = url.pathname
  const method = options.method ?? 'GET'
  const body = options.json ?? {}
  if (route === '/api/v1/company' && method === 'GET') return { data: company }
  if (route === '/api/v1/branches' && method === 'GET') return { data: [branch], page }
  if (route === `/api/v1/branches/${branch.id}` && method === 'GET') return { data: { ...branch, enableStaffingRules: !query.has('staffingDisabled') } }
  if (route === '/api/v1/notifications/unread-count') return { data: { count: 1, asOf: timestamp } }
  if (route === '/api/v1/notifications') return { data: { items: [{ id: id(900), type: 'payslip_available', title: 'Synthetic payslip available', body: 'Your payroll output is ready.', relatedEntityType: 'payslip', relatedEntityId: id(901), readAt: null, createdAt: timestamp }], nextCursor: null, asOf: timestamp, sourceVersion: `sha256:${'a'.repeat(64)}` } }
  if (route === '/api/v1/dashboards/clinical/workforce-summary') return { data: { businessDate: '2026-10-05', counts: { activeStaff: 2, credentialCompliance: 2, coverage: 2, probation: 1, newJoiners: 1, birthdays: 1, onLeaveToday: 1, pendingLeave: 1, onDutyNow: 1 }, compliant: 1, rostered: 1, departments: [{ department: 'Clinical', headcount: 2, credentialled: 1, rostered: 1, minStaff: 2 }] } }
  if (route === '/api/v1/dashboards/clinical/workforce-details') {
    const group = url.searchParams.get('group')
    const count = ['activeStaff', 'credentialCompliance', 'coverage'].includes(group) ? 2 : 1
    return { data: Array.from({ length: count }, (_, index) => ({ id: `${group}:${id(index + 3)}`, employeeId: id(index + 3), employeeName: index ? 'Sam Taylor' : 'Alex Morgan', department: 'Clinical', jobTitle: index ? 'Clinical manager' : 'Registered nurse', status: group === 'onDutyNow' ? 'clocked_in' : 'active', sourceDate: '2026-10-05', sourceTime: group === 'onDutyNow' ? timestamp : null, sourceLabel: group === 'pendingLeave' ? 'Annual Leave' : group === 'credentialCompliance' ? index ? 'Credential missing' : 'Verified credential' : 'Current branch source' })), page }
  }
  if (route === '/api/v1/dashboards/clinical/credentials') return { data: [{ id: `document:${id(910)}`, employeeId: id(3), employeeName: 'Alex Morgan', sourceType: 'professional_licence', expiryDate: url.searchParams.get('status') === 'expired' ? '2026-09-30' : '2026-10-31', status: url.searchParams.get('status') }], page }
  if (route === '/api/v1/retained-records') return { data: [...archived.values()].filter((record) => record.archived && record.entityType === url.searchParams.get('kind')), page }
  if (route.startsWith('/api/v1/retained-records/')) {
    const [, , , , kind, recordId, action] = route.split('/')
    const source = archived.get(recordId)
    const record = { id: recordId, entityType: kind, label: source?.label ?? (kind === 'appraisal' ? 'Alex Morgan · H2 2026' : kind === 'incident_report' ? 'Equipment check near miss' : 'Alex Morgan · Clinical supplies transport'), status: source?.status ?? (kind === 'appraisal' ? 'pending' : kind === 'incident_report' ? 'open' : 'pending'), archived: action === 'archive', updatedAt: changedAt }
    archived.set(recordId, record)
    return { data: record }
  }
  if (route.endsWith('/admin-cancel')) { const recordId = route.split('/')[4]; cancelled.add(recordId); return { data: { id: recordId, entityType: 'salary_advance', label: 'Alex Morgan · Family travel', status: 'cancelled', archived: false, updatedAt: changedAt } } }
  if (route.endsWith('/admin-review')) {
    canonicalAppraisal = { ...canonicalAppraisal, sections: canonicalAppraisal.sections.map((section) => ({ ...section, ...body.sections.find((item) => item.id === section.id), updatedAt: changedAt })), status: 'reviewed', overallRating: '4.0', reviewerComments: body.reviewerComments, developmentPlan: body.developmentPlan, reviewedAt: changedAt, updatedAt: changedAt }
    return { data: canonicalAppraisal }
  }
  if (route === '/api/v1/cme/contributions') {
    const current = trainingRecords[0]
    const completed = { ...current, id: id(930), trainingTitle: 'Verified clinical course', durationHours: '12.00', status: 'completed', passed: true, resultVerified: true, isCme: true }
    return { data: [completed, { ...current, durationHours: '8.00', status: 'in_progress', resultVerified: true, isCme: true }], page }
  }
  if (route.endsWith('/assets/assignments')) {
    const response = await fixture.authentication.request(path, options)
    return { ...response, data: response.data.map((record) => ({ ...record, assignedByName: 'Administrator' })) }
  }
  const response = await fixture.authentication.request(path, options)
  if (route === '/api/v1/advances' && method === 'GET') return { ...response, data: response.data.map((record) => cancelled.has(record.id) ? { ...record, status: 'cancelled', canDecide: false, updatedAt: changedAt } : record) }
  if (route === '/api/v1/training-records' && method === 'GET') trainingRecords = response.data
  if (part === 'a' && route === '/api/v1/appraisal-cycles' && method === 'GET') {
    if (!canonicalAppraisal && response.data[0]?.appraisals[0]) {
      canonicalAppraisal = { ...response.data[0].appraisals[0], cycleStatus: 'active', employeeDepartment: 'Clinical', employeeJobTitle: 'Registered nurse', templateVersion: 'clinic-v1', sections: ['Clinical Competency', 'Patient Care Quality', 'Communication and Teamwork', 'Punctuality and Attendance', 'Professional Development'].map((sectionName, index) => ({ id: id(940 + index), sectionName, weight: ['2.00', '2.00', '1.50', '1.00', '1.00'][index], rating: '4.0', comments: 'Strong progress', sortOrder: (index + 1) * 10, updatedAt: timestamp })) }
    }
    return { ...response, data: response.data.map((cycle) => ({ ...cycle, appraisals: archived.get(canonicalAppraisal.id)?.archived ? [] : [canonicalAppraisal] })) }
  }
  if (['/api/v1/clinical-incidents', '/api/v1/expenses'].includes(route) && method === 'GET') return { ...response, data: response.data.filter((record) => !archived.get(record.id)?.archived) }
  if (route === '/api/v1/tasks' && part === 'd') return { ...response, data: { ...response.data, categories: response.data.categories.map((category) => category.status === 'failed' ? { ...category, status: 'ok', errorCode: null } : category) } }
  return response
}

const authentication = {
  async logout() {},
  async request(path, options = {}) {
    window.__restorationFPending += 1
    try {
    window.__restorationFRequests.push({ path, options })
    const route = new URL(path, location.origin).pathname
    if (!contextRoute(route) && !route.startsWith('/api/v1/notifications')) {
      while (!window.__restorationFRelease) await new Promise((resolve) => setTimeout(resolve, 25))
      if (query.get('state') === 'unavailable') throw new Error('Synthetic source unavailable')
    }
    if (options.method && options.method !== 'GET' && window.__restorationFReject) {
      const code = window.__restorationFReject
      window.__restorationFReject = null
      throw Object.assign(new Error(code === 'conflict' ? 'The source changed. Refresh and retry.' : 'Synthetic rejected write'), { status: code === 'conflict' ? 409 : 503, code })
    }
    try {
      const response = await responseFor(path, options)
      return query.get('state') === 'empty' && !contextRoute(route) && route !== '/api/v1/employees/self' && !route.startsWith('/api/v1/notifications') ? emptyResponse(response) : structuredClone(response)
    } catch (error) {
      if (/Unhandled synthetic route|No synthetic response/.test(error.message)) window.__restorationFUnhandled.push({ path, message: error.message })
      throw error
    }
    } finally { window.__restorationFPending -= 1 }
  },
}
localStorage.setItem('workloop-dark-mode', String(query.has('dark')))
localStorage.setItem('workloop-advanced-features', 'true')
localStorage.setItem(`workloop-${account.role}-sidebar-collapsed`, 'false')
sessionStorage.setItem('workloop.branchId', fixture.branchId)
window.history.replaceState(null, '', query.get('path') ?? `/${account.role}`)
createRoot(document.getElementById('root')).render(<><a className="skip-link" href="#portal-content">Skip to main content</a><main id="portal-content" tabIndex={-1}><PortalShell account={account} authentication={authentication} /></main></>)
