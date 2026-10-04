import { createRoot } from 'react-dom/client'
import Dashboard from '../src/Dashboards.jsx'
import Reports from '../src/Reports.jsx'
import Tasks from '../src/Tasks.jsx'
import NotificationBell from '../src/NotificationBell.jsx'
import Payroll from '../src/Payroll.jsx'
import Advances from '../src/Advances.jsx'
import Expenses from '../src/Expenses.jsx'
import WpsNafis from '../src/WpsNafis.jsx'
import OrganizationSettings from '../src/OrganizationSettings.jsx'
import { CompanyProvider } from '../src/CompanyContext.jsx'
import '../src/index.css'
import '../src/portal-ui.css'

const id = (number) => `d4000000-0000-4000-8000-${String(number).padStart(12, '0')}`
const branchId = id(2)
const employeeId = id(3)
const timestamp = '2026-10-05T08:00:00.000Z'
const nextTimestamp = '2026-10-05T08:01:00.000Z'
const sourceDigest = 'a'.repeat(64)
const sourceVersion = `sha256:${sourceDigest}`
const page = { limit: 100, hasMore: false, nextCursor: null }
const query = new URLSearchParams(location.search)
const role = query.get('role') ?? 'admin'
const account = { role, appUserId: id(5), companyId: id(1), employeeId: role === 'admin' ? null : employeeId, branchId: role === 'admin' ? null : branchId }
const company = { id: id(1), name: 'Synthetic Clinic', sector: 'Healthcare', nafisQuotaPercent: '2.00', enableNafis: true, createdAt: timestamp, updatedAt: timestamp }
let branch = { id: branchId, name: 'Dubai clinic', molEmployerId: '9000000816726', defaultBankRoutingCode: '123456789', address: 'Synthetic address', contactEmail: 'clinic@example.test', defaultSalaryDay: 25, workLocationType: 'mainland', freeZoneName: '', logoUrl: '', enableStaffingRules: true, enableBiometricImport: false, createdAt: timestamp, updatedAt: timestamp }
const department = { id: id(4), name: 'Clinical', parentId: null, headEmployeeId: null, color: '#6366f1', description: '', sortOrder: 0, createdAt: timestamp }
const staff = { id: employeeId, empNo: 'E-003', name: 'Alex Morgan', photoUrl: '', workEmail: 'alex@example.test', jobTitle: 'Registered nurse', department: 'Clinical', reportingManagerId: null, employmentStartDate: '2025-01-01', probationEndDate: '2025-06-30', employmentStatus: 'active', active: true, basicSalary: '8000.00', housingAllowance: '1000.00', transportAllowance: '500.00', otherAllowances: '250.00', bankName: 'Synthetic bank', updatedAt: timestamp }
let run = { id: id(10), period: '2026-10', paymentDate: '2026-10-25', sequence: '0001', runStatus: 'draft', approvalStatus: 'draft', employeeCount: 1, totalAmount: '10000.00', validationStatus: 'valid', blockingErrors: [], sourceWarnings: [], createdAt: timestamp, updatedAt: timestamp }
let entry = { id: id(11), employeeId, employeeName: staff.name, basicSalary: '10000.00', housingAllowance: '0.00', transportAllowance: '0.00', fixedAllowance: '0.00', increment: '0.00', bonus: '0.00', otherPay: '0.00', variableAllowance: '0.00', leaveDeduction: '0.00', fixedPay: '10000.00', grossPay: '10000.00', totalDeductions: '0.00', netPay: '10000.00', wpsBasicPay: '10000.00', wpsVariablePay: '0.00', excluded: false, additionalAllowances: [], deductions: [], sourceExplanations: ['Approved overtime from attendance'], sourceFingerprint: sourceDigest }
let advance = { id: id(20), employeeId, employeeName: staff.name, creatorName: 'Administrator', decisionActorName: null, disbursedDate: null, canDecide: true, amount: '1000.00', reason: 'Family travel', status: 'pending', repaymentStartPeriod: '2026-10', installmentCount: 2, monthlyInstallment: '500.00', outstandingBalance: '1000.00', nextRepaymentPeriod: '2026-10', rejectionReason: null, schedule: [{ period: '2026-10', scheduledAmount: '500.00', paidAmount: '0.00', remainingAmount: '500.00', status: 'due' }], repayments: [], createdAt: timestamp, updatedAt: timestamp }
let claim = { id: id(21), employeeId, employeeName: staff.name, category: 'travel', amount: '350.00', expenseDate: '2026-10-04', description: 'Clinical supplies transport', status: 'pending', rejectionReason: null, hasReceipt: true, payrollPeriod: null, managerDecisionAt: null, adminDecisionAt: null, canDecide: true, managerActorName: null, adminActorName: null, createdAt: timestamp, updatedAt: timestamp }
let notification = { id: id(30), type: 'payslip_available', title: 'October payslip available', body: 'Your payroll output is ready.', relatedEntityType: 'payslip', relatedEntityId: id(31), readAt: null, createdAt: timestamp }
let wps = { runId: run.id, period: run.period, paymentDate: run.paymentDate, status: 'draft', submittedAt: null, confirmedAt: null, referenceNumber: null, updatedAt: timestamp, entries: [{ id: entry.id, employeeId, employeeName: staff.name, paymentStatus: 'pending', rejectionReason: null, updatedAt: timestamp }] }
const sif = { filename: 'synthetic-payroll.sif', sourceDigest: sourceVersion, rendererVersion: 'sif-v1', byteCount: 240, recordCount: 2, records: [{ type: 'EDR', employeeMolId: 'MOL-003', bankRoutingCode: '123456789', iban: 'AE070331234567890123456', periodStart: '2026-10-01', periodEnd: '2026-10-31', paidDays: 31, basicPay: 10000, variablePay: 0, leaveDays: 0 }, { type: 'SCR', employerMolId: '9000000816726', bankRoutingCode: '123456789', paymentDate: '2026-10-25', sequence: '0001', period: '2026-10', employeeCount: 1, totalPay: 10000, currency: 'AED', description: 'October salaries' }] }
const columns = (keys) => keys.map(([key, label, type = 'string']) => ({ key, label, type, scale: type === 'decimal' ? 2 : null, nullable: false }))
const reports = {
  headcount: { columns: columns([['employeeName', 'Employee'], ['department', 'Department'], ['nationality', 'Nationality']]), rows: [{ employeeName: staff.name, department: 'Clinical', nationality: 'Emirati' }] },
  payrollCost: { columns: columns([['period', 'Period'], ['paymentDate', 'Payment date', 'date'], ['employeeCount', 'Employees', 'integer'], ['net', 'Net pay', 'decimal']]), rows: [{ period: '2026-10', paymentDate: '2026-10-25', employeeCount: 1, net: '10000.00' }], totals: { net: '10000.00', employeeCount: 1 } },
  emiratization: { columns: columns([['period', 'Period'], ['ratioPercent', 'Current rate', 'decimal'], ['compliant', 'Compliant', 'boolean']]), rows: [{ period: '2026-10', ratioPercent: '5.00', compliant: true }] },
  staffingCompliance: { columns: columns([['department', 'Department'], ['required', 'Required', 'integer'], ['assigned', 'Assigned', 'integer'], ['shortage', 'Shortage', 'integer']]), rows: [{ department: 'Clinical', required: 2, assigned: 1, shortage: 1 }], totals: { required: 2, assigned: 1, shortage: 1 } },
  documentExpiry: { columns: columns([['employeeName', 'Employee'], ['documentType', 'Document type'], ['expiryDate', 'Expiry date', 'date']]), rows: [{ employeeName: staff.name, documentType: 'Professional licence', expiryDate: '2026-10-31' }] },
  salaryMovement: { columns: columns([['employeeName', 'Employee'], ['oldSalary', 'Old salary', 'decimal'], ['newSalary', 'New salary', 'decimal']]), rows: [{ employeeName: staff.name, oldSalary: '7500.00', newSalary: '8000.00' }] },
  turnover: { columns: columns([['employeeName', 'Employee'], ['eventType', 'Event type'], ['eventDate', 'Event date', 'date']]), rows: [{ employeeName: staff.name, eventType: 'joined', eventDate: '2025-01-01' }] },
  eosLiability: { columns: columns([['employeeName', 'Employee'], ['department', 'Department'], ['liability', 'Liability', 'decimal']]), rows: [{ employeeName: staff.name, department: 'Clinical', liability: '4200.00' }], totals: { liability: '4200.00' } },
  leaveUtilization: { columns: columns([['employeeName', 'Employee'], ['leaveType', 'Leave type'], ['days', 'Days', 'decimal']]), rows: [{ employeeName: staff.name, leaveType: 'Annual', days: '5.00' }], totals: { days: '5.00' } },
  leaveBalance: { columns: columns([['employeeName', 'Employee'], ['leaveType', 'Leave type'], ['remaining', 'Remaining', 'decimal']]), rows: [{ employeeName: staff.name, leaveType: 'Annual', remaining: '25.00' }], totals: { remaining: '25.00' } },
  attendanceSummary: { columns: columns([['employeeName', 'Employee'], ['department', 'Department'], ['present', 'Present', 'integer'], ['hours', 'Hours', 'decimal']]), rows: [{ employeeName: staff.name, department: 'Clinical', present: 20, hours: '160.00' }], totals: { present: 20, hours: '160.00' } },
  overtime: { columns: columns([['employeeName', 'Employee'], ['department', 'Department'], ['hours', 'Approved hours', 'decimal'], ['amount', 'Approved amount', 'decimal']]), rows: [{ employeeName: staff.name, department: 'Clinical', hours: '4.00', amount: '200.00' }], totals: { hours: '4.00', amount: '200.00' } },
  wpsCompliance: { columns: columns([['employeeName', 'Employee'], ['period', 'Period'], ['entryStatus', 'Entry status']]), rows: [{ employeeName: staff.name, period: '2026-10', entryStatus: 'pending' }] },
}
const cards = {
  admin: [['activeHeadcount', 'Active employees', 12, 'employees', 'success', 'employees'], ['finalizedPayroll', 'Latest finalized payroll', '10000.00', 'AED', 'info', 'payroll'], ['wpsStatus', 'WPS status', 'submitted', 'status', 'warning', 'wps'], ['nafisRatio', 'Nafis ratio', '5.00', 'percent', 'success', 'nafis'], ['expiryDue', 'Expiry alerts', 1, 'items', 'warning', 'recordsBenefits']],
  clinical: [['credentialsValid', 'Valid credentials', 10, 'credentials', 'success', 'developmentAssets'], ['credentialsExpiring', 'Expiring credentials', 1, 'credentials', 'warning', 'developmentAssets'], ['credentialsExpired', 'Expired credentials', 1, 'credentials', 'critical', 'developmentAssets'], ['publishedRoster', 'Published roster today', 4, 'assignments', 'success', 'roster'], ['staffingValidation', 'Staffing validation', 'passed', 'status', 'success', 'roster'], ['onDuty', 'On duty today', 4, 'employees', 'info', 'attendance']],
}
window.__restorationRequests = []
window.__restorationFailNext = false
function syntheticPdf() {
  const stream = 'BT /F1 12 Tf 40 740 Td (Synthetic protected report) Tj ET'
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>', '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>', `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`]
  let source = '%PDF-1.4\n'
  const offsets = [0]
  objects.forEach((object, index) => { offsets.push(source.length); source += `${index + 1} 0 obj\n${object}\nendobj\n` })
  const start = source.length
  source += `xref\n0 ${offsets.length}\n0000000000 65535 f \n${offsets.slice(1).map((offset) => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${offsets.length} /Root 1 0 R >>\nstartxref\n${start}\n%%EOF\n`
  return source
}
const authentication = { async request(path, options = {}) {
  window.__restorationRequests.push({ path, options })
  const url = new URL(path, location.origin)
  const route = url.pathname
  const method = options.method ?? 'GET'
  if (window.__restorationFailNext && (method !== 'GET' || route.includes('/sif') || options.responseType === 'bytes')) { window.__restorationFailNext = false; throw new Error('Synthetic rejected write') }
  if (options.responseType === 'bytes') return { bytes: new Uint8Array(new TextEncoder().encode(route.endsWith('.pdf') ? syntheticPdf() : route.endsWith('.csv') ? 'Employee,Amount\r\nAlex,10000\r\n' : 'SIF synthetic bytes\r\n')), contentType: route.endsWith('.pdf') ? 'application/pdf' : route.endsWith('.csv') ? 'text/csv' : 'text/plain', filename: route.endsWith('.pdf') ? 'synthetic.pdf' : route.endsWith('.csv') ? 'synthetic.csv' : 'synthetic.sif' }
  if (route === '/api/v1/company') return { data: company }
  if (route === '/api/v1/branches') return { data: [branch], page }
  if (route.endsWith('/payroll-routing')) {
    if (method === 'GET') return { data: { branch, drafts: [{ id: run.id, expectedUpdatedAt: run.updatedAt, sourceDigest }] } }
    branch = { ...branch, defaultBankRoutingCode: options.json.routingCode, updatedAt: nextTimestamp }
    run = { ...run, updatedAt: nextTimestamp }
    return { data: { branch, changedRuns: [{ id: run.id, expectedUpdatedAt: run.updatedAt, sourceDigest }] } }
  }
  if (route === `/api/v1/branches/${branchId}`) return { data: branch }
  if (route === '/api/v1/employees') return { data: [staff], page }
  if (route === '/api/v1/departments') return { data: [department], page }
  if (route.startsWith('/api/v1/dashboards/')) { const kind = route.split('/').at(-1); return { data: { asOf: timestamp, businessDate: '2026-10-05', sourceVersion, cards: cards[kind].map(([code, label, value, unit, severity, target]) => ({ code, label, value, unit, severity, comparison: null, drillDown: { code, target } })) } } }
  if (route.startsWith('/api/v1/reports/')) { const reportId = route.split('/').at(-1); const value = reports[reportId] ?? reports.headcount; return { data: { reportId, columns: value.columns, rows: query.get('empty') ? [] : value.rows, totals: { scope: 'filtered', rowCount: query.get('empty') ? 0 : value.rows.length, values: value.totals ?? {} }, filters: {}, asOf: timestamp, sourceVersion, nextCursor: null } } }
  if (route === '/api/v1/tasks') return { data: { asOf: timestamp, sourceVersion, nextCursor: null, categories: [{ code: 'expenses', label: 'Expense decisions', count: 1, status: 'ok', errorCode: null, items: [{ id: `expense:${claim.id}`, entity: 'expense', entityId: claim.id, title: 'Review Alex Morgan expense', subtitle: 'AED 350.00', urgency: 'action', dueDate: '2026-10-06', createdAt: timestamp, navigation: { screen: role === 'employee' ? 'expenses' : 'expenses' } }] }, { code: 'credentials', label: 'Credential alerts', status: 'failed', count: 0, items: [], errorCode: 'task_source_unavailable' }] } }
  if (route === '/api/v1/notifications/unread-count') return { data: { count: notification.readAt ? 0 : 1, asOf: timestamp } }
  if (route === '/api/v1/notifications') return { data: { items: [notification], nextCursor: null, asOf: timestamp, sourceVersion } }
  if (route.endsWith('/read')) { notification = { ...notification, readAt: nextTimestamp }; return { data: notification } }
  if (route.endsWith('/read-all')) { notification = { ...notification, readAt: nextTimestamp }; return { data: { changedCount: 1, unreadCount: 0, asOf: nextTimestamp } } }
  if (route === '/api/v1/payroll-runs') return { data: [query.get('module') === 'wps' ? { ...run, runStatus: 'generated', approvalStatus: 'approved' } : run], page }
  if (route.endsWith('/approval-history')) return { data: [], page }
  if (route.endsWith('/sif/preview')) return { data: sif }
  if (route.endsWith('/wps')) return { data: wps }
  if (route.includes('/wps/')) { wps = { ...wps, status: route.endsWith('/sif-generated') ? 'sif_generated' : 'submitted', updatedAt: nextTimestamp }; return { data: wps } }
  if (route === '/api/v1/nafis-snapshots') return { data: [], page }
  if (route.startsWith('/api/v1/payroll-runs/')) { if (method === 'PUT') { entry = { ...entry, ...options.json.entries[0] }; run = { ...run, updatedAt: nextTimestamp } } return { data: { ...run, entries: [entry] } } }
  if (route === '/api/v1/advances') { if (method === 'POST') advance = { ...advance, ...options.json, updatedAt: nextTimestamp }; return { data: method === 'GET' ? [advance] : advance, page: method === 'GET' ? page : null } }
  if (route.startsWith('/api/v1/advances/')) { advance = { ...advance, status: route.endsWith('/approve') ? 'active' : 'cancelled', updatedAt: nextTimestamp }; return { data: advance } }
  if (route === '/api/v1/expenses') return { data: [claim], page }
  if (route.endsWith('/receipt-download')) return { data: { url: 'https://receipt.example.test/synthetic', expiresAt: nextTimestamp } }
  if (route.startsWith('/api/v1/expenses/')) { claim = { ...claim, status: route.endsWith('/approve') ? 'approved' : 'rejected', updatedAt: nextTimestamp }; return { data: claim } }
  if (route.includes('insurance')) return { data: [], page }
  throw new Error(`Unhandled synthetic route ${method} ${route}`)
} }
const props = { account, authentication, branchId }
const moduleName = query.get('module') ?? 'dashboard'
const content = { dashboard: <Dashboard {...props} kind="admin" />, clinical: <Dashboard {...props} kind="clinical" />, reports: <Reports {...props} />, tasks: <Tasks {...props} />, notifications: <NotificationBell {...props} />, payroll: <Payroll {...props} />, advances: <Advances {...props} />, expenses: <Expenses {...props} />, wps: <WpsNafis {...props} />, settings: <CompanyProvider account={account} authentication={authentication}><OrganizationSettings authentication={authentication} /></CompanyProvider> }[moduleName]
sessionStorage.setItem('workloop.branchId', branchId)
createRoot(document.getElementById('root')).render(<main className="portal" data-portal-role={role} data-theme={query.get('dark') ? 'dark' : 'light'} style={{ padding: 20, maxWidth: 1400, margin: '0 auto' }}><div className="portal-route">{content}</div></main>)
