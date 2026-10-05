import { createRoot } from 'react-dom/client'
import PortalShell from '../src/PortalShell.jsx'
import '../src/index.css'
import '../src/portal-ui.css'
const id = (number) => `e5000000-0000-4000-8000-${String(number).padStart(12, '0')}`
const query = new URLSearchParams(location.search)
const role = query.get('role') ?? 'employee'
const branchId = id(2), companyId = id(1), employeeId = role === 'manager' ? id(4) : id(3), managerId = id(4), shiftId = id(10)
const timestamp = '2026-10-05T08:00:00.000Z', nextTimestamp = '2026-10-05T08:01:00.000Z'
const digest = `sha256:${'a'.repeat(64)}`, sourceDigest = 'b'.repeat(64)
const page = { limit: 100, hasMore: false, nextCursor: null }
const account = { role, appUserId: id(5), companyId, employeeId, branchId }
let employee = {
  id: employeeId,
  empNo: 'E-001',
  name: role === 'manager' ? 'Sam Taylor' : 'Alex Morgan',
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

const staff = employee
let training = { id: id(30), employeeId: employeeId, trainingTitle: 'Emergency response', trainingType: 'external',
  provider: 'Training centre', startDate: '2026-10-01', endDate: '2026-10-03', durationHours: '8.00',
  cost: '200.00', status: 'planned', score: '', passed: null, notes: '', isCme: true, hasEvidence: false,
  fileName: null, contentType: null, createdAt: timestamp, updatedAt: timestamp }
let certification = { id: id(31), employeeId, certificationName: 'Basic life support',
  issuingBody: 'Training centre', certificateNo: 'BLS001', issuedDate: '2026-01-01', expiryDate: '2027-01-01',
  notes: '', status: 'pending_review', hasEvidence: true, fileName: 'bls.pdf', contentType: 'application/pdf',
  reviewedAt: null, createdAt: timestamp, updatedAt: timestamp }
training = { ...training, resultVerified: true, isCme: false }
let appraisal = { id: id(41), cycleId: id(40), cycleName: 'H2 2026', reviewFrom: '2026-07-01', reviewTo: '2026-12-31',
  employeeId: employeeId, employeeName: employee.name, templateVersion: 'clinic-v1', cycleStatus: 'active', overallRating: null,
  status: 'pending', reviewerComments: '', developmentPlan: '', reviewedAt: null, reviewedByAppUserId: null,
  employeeDepartment: 'Clinical', employeeJobTitle: 'Nurse',
  createdAt: timestamp, updatedAt: timestamp, sections: [
    ['Clinical Competency', '2.00'], ['Patient Care Quality', '2.00'], ['Communication and Teamwork', '1.50'], ['Punctuality and Attendance', '1.00'], ['Professional Development', '1.00'],
  ].map(([sectionName, weight], index) => ({ id: id(42 + index), sectionName, weight, rating: '4.0', comments: 'Strong progress', sortOrder: (index + 1) * 10, updatedAt: timestamp })) }
const leaveSettings = { id: id(30), branchId, leaveYearType: 'calendar', weekendDefinition: 'fri-sat', carryForwardEnabled: true, carryForwardMaxDays: 15, approvalChain: '2-level', ramadanActive: false, ramadanStart: null, ramadanEnd: null, createdAt: timestamp, updatedAt: timestamp }
const leaveType = { id: id(31), branchId, code: 'ANNUAL', name: 'Annual Leave', color: '#2563eb', isPaid: true, isUnlimited: false, requiresApproval: true, requiresAttachment: false, requiresReason: true, minNoticeDays: 7, annualEntitlementDays: '30.00', accrualType: 'monthly', dayCountType: 'calendar', autoApprove: false, carryForwardAllowed: true, carryForwardMaxDays: 15, genderRestriction: null, minServiceMonths: 0, oncePerCareer: false, notDeductedFromAnnual: false, affectsPayroll: true, lawReference: 'UAE Labour Law Article 29', isActive: true, sortOrder: 1, probationEligible: true, createdAt: timestamp, updatedAt: timestamp }
const holiday = { id: id(32), branchId, date: '2026-12-02', name: 'National Day', type: 'federal', year: 2026, createdAt: timestamp }
const leaveBalance = { employeeId, leaveTypeId: leaveType.id, leaveYear: 2026, entitledDays: '30.00', accruedDays: '22.50', usedDays: '5.00', pendingDays: '2.00', carriedForward: '3.00', remainingDays: '26.00', sickFullPayUsed: '0.00', sickHalfPayUsed: '0.00', sickUnpaidUsed: '0.00' }
let leaveRequest = { id: id(33), branchId, employeeId, leaveTypeId: leaveType.id, startDate: '2026-10-04', endDate: '2026-10-05', isHalfDay: false, halfDayPeriod: null, daysRequested: '2.00', status: 'Pending', reason: 'Family commitment', attachment: null, rejectionReason: '', managerRejectionReason: '', relationship: '', deceasedName: '', dateOfDeath: null, childBirthDate: null, childName: '', expectedDueDate: null, institutionName: '', examDates: '', substituteEmployeeId: null, approvalLevelRequired: 2, approvalComment: '', warnings: [], submittedAt: timestamp, createdAt: timestamp, updatedAt: timestamp }
const attendanceRecord = { id: id(41), employeeId, date: '2026-10-04', shiftId, clockInTime: '2026-10-04T04:05:00.000Z', clockOutTime: '2026-10-04T13:30:00.000Z', totalHours: '8.50', expectedHours: '8.00', status: 'LATE', resolutionType: null, lateMinutes: 5, earlyDepartureMinutes: 0, overtimeHours: '0.50', overtimeType: 'STANDARD', overtimeAmount: '25.00', overtimeApproved: false, absenceDeduction: '0.00', lateDeduction: '0.00', workedOnRestDay: false, restDaySubstitute: false, missingClockOut: false, isRamadanDay: false, periodClosed: false, evidenceFlags: [], sourceDigest, sourceStale: false, calculationVersion: 1, updatedAt: timestamp }
let swap = { id: id(51), requesterEmployeeId: employeeId, requesterEmployeeName: 'Alex Morgan', targetEmployeeId: managerId, targetEmployeeName: 'Sam Taylor', requesterDate: '2026-10-04', targetDate: '2026-10-05', reason: 'Family appointment', status: 'pending', rejectionReason: '', expectedSourceVersion: digest, requesterAssignmentId: id(50), targetAssignmentId: id(52), requesterAssignmentVersion: 1, targetAssignmentVersion: 1, approvedPublicationVersionId: null, decidedAt: null, decidedByAppUserId: null, createdAt: timestamp, updatedAt: timestamp, version: 1 }
let advance = { id: id(20), employeeId, employeeName: staff.name, creatorName: 'Administrator', decisionActorName: null, disbursedDate: null, canDecide: true, amount: '1000.00', reason: 'Family travel', status: 'pending', repaymentStartPeriod: '2026-10', installmentCount: 2, monthlyInstallment: '500.00', outstandingBalance: '1000.00', nextRepaymentPeriod: '2026-10', rejectionReason: null, schedule: [{ period: '2026-10', scheduledAmount: '500.00', paidAmount: '0.00', remainingAmount: '500.00', status: 'due' }], repayments: [], createdAt: timestamp, updatedAt: timestamp }
let claim = { id: id(21), employeeId, employeeName: staff.name, category: 'travel', amount: '350.00', expenseDate: '2026-10-04', description: 'Clinical supplies transport', status: 'pending', rejectionReason: null, hasReceipt: true, payrollPeriod: null, managerDecisionAt: null, adminDecisionAt: null, canDecide: true, managerActorName: null, adminActorName: null, createdAt: timestamp, updatedAt: timestamp }
let notification = { id: id(30), type: 'payslip_available', title: 'October payslip available', body: 'Your payroll output is ready.', relatedEntityType: 'payslip', relatedEntityId: id(31), readAt: null, createdAt: timestamp }
let documentRecord = { id: id(21), employeeId: id(3), documentType: 'Emirates ID', status: 'verified', rejectionReason: null, fileName: 'emirates-id.pdf', sizeBytes: 1200, contentType: 'application/pdf', expiryDate: '2026-10-31', notes: '', reviewerName: 'Admin User', uploadedAt: timestamp, reviewedAt: timestamp, updatedAt: timestamp }
const request = (number, kind, status) => ({ id: id(number), employeeId: id(3), employeeName: 'Alex Morgan', jobTitle: 'Registered nurse', department: 'Clinical', employmentStartDate: '2025-01-01', branchName: 'Dubai clinic', requestKind: kind, letterType: kind === 'letter' ? 'employment_confirmation' : 'Shift change request', purpose: kind === 'letter' ? 'Housing application' : 'Please review the proposed shift change.', status, notes: '', rejectionReason: '', requestedAt: timestamp, completedAt: status === 'completed' ? timestamp : null, actionedAt: status === 'pending' ? null : timestamp, updatedAt: timestamp })

let requests = [request(80, 'letter', 'completed'), request(81, 'custom', 'completed'), request(82, 'custom', 'rejected')]
const personalAdvance = (item) => Object.fromEntries(Object.entries(item).filter(([key]) => !['employeeId', 'employeeName', 'creatorName', 'decisionActorName', 'disbursedDate', 'canDecide', 'schedule', 'repayments'].includes(key)))
const personalExpense = (item) => Object.fromEntries(Object.entries(item).filter(([key]) => !['employeeId', 'employeeName', 'managerDecisionAt', 'adminDecisionAt', 'canDecide', 'managerActorName', 'adminActorName'].includes(key)))
const report = { id: id(6), empNo: 'E-006', name: 'Jamie Lee', photoUrl: '', jobTitle: 'Nurse', department: 'Clinical', employmentStartDate: '2025-01-01', probationEndDate: null, employmentStatus: 'active' }
const employer = { companyName: 'Synthetic Clinic', branchName: 'Dubai clinic', branchContactEmail: 'clinic@example.test', branchAddress: 'Synthetic address', workLocationType: 'mainland', freeZoneName: '', logoUrl: '' }
const branch = { id: branchId, name: 'Dubai clinic', address: 'Synthetic address', contactEmail: 'clinic@example.test', workLocationType: 'mainland', freeZoneName: '', logoUrl: '' }
const payslip = { id: id(90), period: '2026-09', paymentDate: '2026-09-25', employeeName: employee.name, earnings: [{ label: 'Basic salary', amount: '8000.00' }, { label: 'Allowances', amount: '1750.00' }], deductions: [{ label: 'Advance repayment', amount: '500.00' }], grossPay: '9750.00', totalDeductions: '500.00', netPay: '9250.00', wpsBasicPay: '8000.00', wpsVariablePay: '1250.00', issuedAt: timestamp }
const schedule = { rosterAssignmentId: id(91), employeeId, employeeName: employee.name, department: 'Clinical', shiftId, shiftName: 'Morning clinic', shiftCode: 'MC', shiftCategory: 'morning', date: '2026-10-12', plannedHours: '8.00', actualHours: null, overtimeHours: '0.00', notes: 'Front desk cover', sourceVersion: digest, publicationVersion: 1, publishedAt: timestamp }
let corrections = [{ id: id(92), employeeId, attendanceDate: '2026-10-04', correctClockIn: '2026-10-04T04:00:00.000Z', correctClockOut: '2026-10-04T13:00:00.000Z', reason: 'Missing punch', status: 'Rejected', rejectionReason: 'Please check the date', submittedAt: timestamp, decidedAt: timestamp, version: 1 }]
window.__restorationRequests = []
window.__restorationFailNext = false
window.__restorationUnavailable = query.get('unavailable') === 'true'
window.__restorationUnhandled = []
const authentication = {
  async logout() { window.__restorationLoggedOut = true },
  async request(path, options = {}) {
    window.__restorationRequests.push({ path, options: { ...options, form: options.form ? [...options.form.keys()] : undefined } })
    const url = new URL(path, location.origin), route = url.pathname, method = options.method ?? 'GET', body = options.json ?? {}
    if (window.__restorationUnavailable && !['/api/v1/employer', '/api/v1/branches', '/api/v1/employees/self', '/api/v1/notifications/unread-count'].includes(route)) throw new Error('Synthetic unavailable service')
    if (window.__restorationFailNext && (method !== 'GET' || options.responseType === 'bytes' || route.endsWith('/download'))) { window.__restorationFailNext = false; throw new Error('Synthetic rejected write') }
    const response = (data) => ({ data: structuredClone(data), page, status: 200, location: null })
    if (route === '/api/v1/employer') return response(employer)
    if (route === '/api/v1/branches') return response([branch])
    if (route === '/api/v1/employees/self') return response(employee)
    if (route === '/api/v1/employees/self/contact') { const { expectedUpdatedAt, ...contact } = body; if (!expectedUpdatedAt) throw new Error('Expected version missing'); employee = { ...employee, ...contact, updatedAt: nextTimestamp }; return response(employee) }
    if (route === '/api/v1/employees/direct-reports') return response([report])
    if (route === '/api/v1/notifications/unread-count') return response({ count: notification.readAt ? 0 : 1, asOf: timestamp })
    if (route === '/api/v1/notifications') return response({ items: [notification], nextCursor: null, asOf: timestamp, sourceVersion: digest })
    if (route.endsWith('/read-all')) { notification.readAt = nextTimestamp; return response({ changedCount: 1, unreadCount: 0, asOf: nextTimestamp }) }
    if (route.endsWith('/read')) { notification.readAt = nextTimestamp; return response(notification) }
    if (route === '/api/v1/dashboards/self') return response({ asOf: timestamp, businessDate: '2026-10-05', sourceVersion: digest, cards: [['employmentStatus', 'Employment', 'active', 'status', 'profile'], ['leaveBalance', 'Annual leave available', '26.00', 'days', 'leave'], ['latestPayslip', 'Latest payslip', '9250.00', 'AED', 'payslips'], ['todayAttendance', 'Today attendance', 'LATE', 'status', 'attendance'], ['assignedAssets', 'Assigned assets', 1, 'assets', 'developmentAssets'], ['todayShift', 'Today shift', 'Morning clinic', 'shift', 'schedule']].map(([code, label, value, unit, target]) => ({ code, label, value, unit, severity: 'info', comparison: code === 'latestPayslip' ? { label: 'Payroll period', value: '2026-09', unit: 'period' } : null, drillDown: { code, target } })) })
    if (route === '/api/v1/assets/self') return response([{ id: id(95), assetId: id(96), employeeId, assetName: 'Clinic laptop', assetCode: 'IT-001', status: 'assigned', assignedDate: '2026-09-01', returnDate: null, conditionAtHandover: 'good', conditionAtReturn: null, notes: '', createdAt: timestamp }])
    if (route === '/api/v1/leave/settings') return response(leaveSettings)
    if (route === '/api/v1/leave/types') return response([leaveType])
    if (route === '/api/v1/leave/holidays') return response([holiday])
    if (route === '/api/v1/leave/balances/self') return response([leaveBalance])
    if (route === '/api/v1/leave/requests/calendar/self') return response([{ ...leaveRequest, employeeId }])
    if (route === '/api/v1/leave/requests/self') { leaveRequest = { ...leaveRequest, ...body, id: id(97), daysRequested: '2.00', updatedAt: nextTimestamp }; delete leaveRequest.expectedUpdatedAt; return response(leaveRequest) }
    if (route.endsWith('/cancel') && route.includes('/leave/requests/')) { leaveRequest.status = 'Cancelled'; return response(leaveRequest) }
    if (route === '/api/v1/leave/approvals/queue') return response(leaveRequest.status === 'Pending' ? [{ request: { ...leaveRequest, employeeId: report.id }, employee: { id: report.id, employeeNumber: report.empNo, name: report.name, jobTitle: report.jobTitle, department: report.department }, leaveType, balance: { ...leaveBalance, employeeId: report.id }, canDecide: true, visibleBecause: 'directReport' }] : [])
    if (route === '/api/v1/leave/approvals/recent') return response([{ id: id(110), requestId: id(111), employeeId: report.id, employeeName: report.name, leaveType: 'Annual Leave', startDate: '2026-09-20', endDate: '2026-09-21', action: 'manager_approved', reason: 'Coverage confirmed', actorName: 'You', actionAt: timestamp }])
    if (route.includes('/leave/approvals/') && route.endsWith('/decision')) { leaveRequest.status = body.decision === 'reject' ? 'ManagerRejected' : 'ManagerApproved'; return response(leaveRequest) }
    if (route.endsWith('/audit')) return response([])
    if (route === '/api/v1/attendance/me/today') return response({ record: { ...attendanceRecord, employeeId }, rawEventFallback: 'none', rawEvents: [] })
    if (route === '/api/v1/attendance/me') return response([{ ...attendanceRecord, employeeId }])
    if (route === '/api/v1/attendance/regularisations/me') return response(corrections)
    if (route === '/api/v1/attendance/regularisations') { const item = { ...corrections[0], ...body, id: id(98), status: 'Pending', rejectionReason: null, decidedAt: null }; corrections.push(item); return response(item) }
    if (route === '/api/v1/roster/schedules/self') return response([schedule])
    if (route === '/api/v1/roster/schedules/colleagues') return response([{ employeeId: report.id, employeeName: report.name, rosterAssignmentId: id(99), shiftId, shiftName: 'Evening clinic', shiftCode: 'EC', shiftCategory: 'evening', date: url.searchParams.get('date') }])
    if (route === '/api/v1/roster/shift-swaps/self') return response([swap])
    if (route === '/api/v1/roster/shift-swaps') { swap = { ...swap, ...body, requesterEmployeeId: employeeId, targetEmployeeName: report.name, updatedAt: nextTimestamp }; return response(swap) }
    if (route.includes('/shift-swaps/') && route.endsWith('/cancel')) { swap = { ...swap, status: 'cancelled', version: 2 }; return response(swap) }
    if (route === '/api/v1/payslips/self') return response([payslip])
    if (route === `/api/v1/payslips/self/${payslip.id}`) return response(payslip)
    if (options.responseType === 'bytes') return { bytes: new TextEncoder().encode('%PDF-1.4\nSynthetic protected output\n%%EOF'), contentType: 'application/pdf', filename: 'synthetic.pdf' }
    if (route === '/api/v1/advances/self' && method === 'GET') return response([personalAdvance(advance), personalAdvance({ ...advance, id: id(100), status: 'active' })])
    if (route.endsWith('/self-progress')) return { summary: { advanceId: id(100), amount: advance.amount, totalPaid: '0.00', outstandingBalance: advance.outstandingBalance, status: 'active', updatedAt: advance.updatedAt, sourceVersion: digest, schedule: ['2026-10', '2026-11'].map((period) => ({ period, scheduledAmount: '500.00', paidAmount: '0.00', remainingAmount: '500.00', status: period === '2026-10' ? 'due' : 'upcoming' })) }, data: [], page }
    if (route === '/api/v1/advances/self' && method === 'POST') { advance = { ...advance, ...body, employeeId, updatedAt: nextTimestamp }; return response(personalAdvance(advance)) }
    if (route.includes('/advances/') && route.endsWith('/withdraw')) { advance = { ...advance, status: 'cancelled', updatedAt: nextTimestamp }; return response(personalAdvance(advance)) }
    if (route === '/api/v1/expenses/self' && method === 'GET') return response([personalExpense(claim)])
    if (route === '/api/v1/expenses/manager-queue') return response([{ ...claim, employeeId: report.id, employeeName: report.name }])
    if (route.endsWith('/receipt-download')) return response({ url: 'https://receipt.example.test/synthetic', expiresAt: nextTimestamp })
    if (route === '/api/v1/expenses/self' && method === 'POST') { claim = { ...claim, ...body, employeeId, updatedAt: nextTimestamp }; return response(personalExpense(claim)) }
    if (route.startsWith('/api/v1/expenses/')) { claim = { ...claim, status: route.endsWith('/manager-approve') ? 'manager_approved' : 'manager_rejected', updatedAt: nextTimestamp }; return method === 'DELETE' ? response({ id: claim.id, deleted: true }) : response(claim) }
    if (route.endsWith('/training-records/self') || route.endsWith('/training-records/direct-reports')) { const target = route.endsWith('/direct-reports') ? report.id : employeeId; if (method === 'POST') { const fields = { ...body }; delete fields.employeeId; training = { ...training, ...fields, employeeId: target, id: id(101), updatedAt: nextTimestamp } } return response(method === 'GET' ? [{ ...training, employeeId: target }] : training) }
    if (route.startsWith('/api/v1/training-records/')) { const command = route.split('/').at(-1); const fields = { ...body }; delete fields.expectedUpdatedAt; if (command === 'self-complete') training = { ...training, ...fields, status: 'completed', resultVerified: false, isCme: false }; else if (command === 'complete') training = { ...training, ...fields, status: 'completed', resultVerified: true }; else if (['start', 'cancel'].includes(command)) training.status = command === 'start' ? 'in_progress' : 'cancelled'; else if (method === 'PATCH') Object.assign(training, fields); training.updatedAt = nextTimestamp; return response(training) }
    if (route.endsWith('/certifications/self') || route.endsWith('/certifications/direct-reports')) { const target = route.endsWith('/direct-reports') ? report.id : employeeId; if (method === 'POST') { const fields = { ...body }; delete fields.employeeId; certification = { ...certification, ...fields, employeeId: target, updatedAt: nextTimestamp } } return response(method === 'GET' ? [{ ...certification, employeeId: target }] : certification) }
    if (route.endsWith('/cme/self')) return response({ year: 2026, targetHours: '25.0', achievedHours: '8.0', gapHours: '17.0' })
    if (route.endsWith('/appraisals/self') || route.endsWith('/appraisals/direct-reports')) return response([{ ...appraisal, employeeId: route.endsWith('/direct-reports') ? report.id : employeeId, employeeName: route.endsWith('/direct-reports') ? report.name : employee.name }])
    if (route.endsWith('/manager-review')) { appraisal = { ...appraisal, status: 'reviewed', overallRating: '4.0', reviewedAt: nextTimestamp, updatedAt: nextTimestamp, sections: appraisal.sections.map((section) => ({ ...section, ...body.sections.find((item) => item.id === section.id), updatedAt: nextTimestamp })) }; return response(appraisal) }
    if (route.includes('/appraisals/') && route.includes('/sections/') && method === 'PUT') { appraisal = { ...appraisal, updatedAt: nextTimestamp, sections: appraisal.sections.map((item) => ({ ...item, rating: body.rating, comments: body.comments, updatedAt: nextTimestamp })) }; return response(appraisal) }
    if (route === '/api/v1/employee-documents/self') return response([{ ...documentRecord, employeeId }])
    if (route === '/api/v1/employee-documents/submissions') return response({ id: id(105), submissionToken: 'synthetic-token', expiresAt: nextTimestamp })
    if (route.endsWith('/file')) { documentRecord = { ...documentRecord, status: 'pending_verification', reviewedAt: null }; return response({ ...documentRecord, employeeId }) }
    if (route.includes('/employee-documents/') && route.endsWith('/download')) return response({ url: 'https://documents.example.test/synthetic', expiresAt: nextTimestamp })
    if (route === '/api/v1/insurance/self') return response({ policyId: id(104), insurerName: 'Synthetic insurer', tierName: 'Clinical', effectiveDate: '2026-01-01', expiryDate: '2026-12-31' })
    if (route === '/api/v1/requests/self') { if (method === 'POST') { const item = { ...requests[0], requestKind: body.requestKind, letterType: body.requestKind === 'custom' ? body.subject : body.letterType, purpose: body.requestKind === 'custom' ? body.details : body.purpose, employeeId, status: 'pending', completedAt: null, actionedAt: null, id: id(106) }; requests.push(item); return response(item) } return response(requests.map((item) => ({ ...item, employeeId, employeeName: employee.name }))) }
    if (route.endsWith('/print-source')) return response({ requestId: id(80), requestKind: 'letter', letterType: 'employment_confirmation', purpose: 'Housing application', employeeName: employee.name, jobTitle: employee.jobTitle, department: 'Clinical', employmentStartDate: '2025-01-01', branchName: 'Dubai clinic', basicSalary: null, allowance: null, requestedAt: timestamp, completedAt: timestamp })
    if (route === '/api/v1/tasks') return response({ asOf: timestamp, sourceVersion: digest, nextCursor: null, categories: [{ code: 'requests', label: 'My HR requests', count: 1, status: 'ok', errorCode: null, items: [{ id: 'request:' + id(80), entity: 'letter_request', entityId: id(80), title: 'Employment confirmation ready', subtitle: 'Housing application', urgency: 'info', dueDate: null, createdAt: timestamp, navigation: { screen: 'requests' } }] }] })
    window.__restorationUnhandled.push(`${method} ${path}`)
    throw new Error(`Unhandled synthetic route ${method} ${path}`)
  },
}
export const restorationFixture = { account, authentication, branchId, branch }
if (!query.has('fixtureOnly')) window.history.replaceState(null, '', `/${role}${query.get('module') === 'home' || !query.get('module') ? '' : '/' + query.get('module')}`)
localStorage.setItem('workloop-dark-mode', query.get('dark') === 'true' ? 'true' : 'false')
if (!query.has('fixtureOnly')) createRoot(document.getElementById('root')).render(<PortalShell account={account} authentication={authentication} />)
