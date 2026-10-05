import { createRoot } from 'react-dom/client'

import AttendanceManager from '../src/AttendanceManager.jsx'
import DepartmentManager from '../src/DepartmentManager.jsx'
import LeaveManager from '../src/LeaveManager.jsx'
import RosterManager from '../src/RosterManager.jsx'
import '../src/index.css'
import '../src/portal-ui.css'

const id = (value) => `c3000000-0000-4000-8000-${String(value).padStart(12, '0')}`
const branchId = id(2)
const employeeId = id(3)
const managerId = id(4)
const shiftId = id(10)
const timestamp = '2026-10-04T08:00:00.000Z'
const digest = `sha256:${'a'.repeat(64)}`
const sourceDigest = 'b'.repeat(64)
const page = { limit: 100, hasMore: false, nextCursor: null }
const account = { role: 'admin', appUserId: id(5), companyId: id(1), employeeId: null, branchId: null }
const employee = (number, name, manager = null) => ({ id: id(number), empNo: `E-${number}`, name, photoUrl: '', workEmail: `${number}@example.test`, jobTitle: manager ? 'Registered nurse' : 'Clinical manager', department: 'Clinical', reportingManagerId: manager, employmentStartDate: '2025-01-01', probationEndDate: null, employmentStatus: 'active', active: true, basicSalary: '8000.00', housingAllowance: '1000.00', transportAllowance: '500.00', otherAllowances: '0.00', bankName: 'Synthetic bank', updatedAt: timestamp })
const employees = [employee(3, 'Alex Morgan', managerId), employee(4, 'Sam Taylor')]
const branch = (enabled) => ({ id: branchId, name: 'Dubai clinic', address: 'Synthetic address', contactEmail: 'clinic@example.test', workLocationType: 'mainland', freeZoneName: '', logoUrl: '', molEmployerId: 'MOL-001', defaultBankRoutingCode: '123456789', defaultSalaryDay: 28, enableStaffingRules: enabled, enableBiometricImport: false, createdAt: timestamp, updatedAt: timestamp })
const department = { id: id(20), name: 'Clinical', parentId: null, headEmployeeId: managerId, color: '#6366f1', description: 'Clinical care', sortOrder: 0, createdAt: timestamp }
const staffingRule = { id: id(21), department: 'Clinical', shiftCategory: 'morning', minStaff: 2, effectiveFrom: null, effectiveTo: null }
const leaveSettings = { id: id(30), branchId, leaveYearType: 'calendar', weekendDefinition: 'fri-sat', carryForwardEnabled: true, carryForwardMaxDays: 15, approvalChain: '2-level', ramadanActive: false, ramadanStart: null, ramadanEnd: null, createdAt: timestamp, updatedAt: timestamp }
const leaveType = { id: id(31), branchId, code: 'ANNUAL', name: 'Annual Leave', color: '#2563eb', isPaid: true, isUnlimited: false, requiresApproval: true, requiresAttachment: false, requiresReason: true, minNoticeDays: 7, annualEntitlementDays: '30.00', accrualType: 'monthly', dayCountType: 'calendar', autoApprove: false, carryForwardAllowed: true, carryForwardMaxDays: 15, genderRestriction: null, minServiceMonths: 0, oncePerCareer: false, notDeductedFromAnnual: false, affectsPayroll: true, lawReference: 'UAE Labour Law Article 29', isActive: true, sortOrder: 1, probationEligible: true, createdAt: timestamp, updatedAt: timestamp }
const holiday = { id: id(32), branchId, date: '2026-12-02', name: 'National Day', type: 'federal', year: 2026, createdAt: timestamp }
const leaveBalance = { employeeId, leaveTypeId: leaveType.id, leaveYear: 2026, entitledDays: '30.00', accruedDays: '22.50', usedDays: '5.00', pendingDays: '2.00', carriedForward: '3.00', remainingDays: '26.00', sickFullPayUsed: '0.00', sickHalfPayUsed: '0.00', sickUnpaidUsed: '0.00' }
let leaveRequest = { id: id(33), branchId, employeeId, leaveTypeId: leaveType.id, startDate: '2026-10-04', endDate: '2026-10-05', isHalfDay: false, halfDayPeriod: null, daysRequested: '2.00', status: 'Pending', reason: 'Family commitment', attachment: null, rejectionReason: '', managerRejectionReason: '', relationship: '', deceasedName: '', dateOfDeath: null, childBirthDate: null, childName: '', expectedDueDate: null, institutionName: '', examDates: '', substituteEmployeeId: null, approvalLevelRequired: 2, approvalComment: '', warnings: [], submittedAt: timestamp, createdAt: timestamp, updatedAt: timestamp }
let submittedLeaveRequest = null
const delegation = { id: id(34), branchId, approverEmployeeId: managerId, delegateEmployeeId: employeeId, fromDate: '2026-10-10', toDate: '2026-10-20', createdAt: timestamp, updatedAt: timestamp }
const attendanceSettings = { id: id(40), workingDays: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu'], weekendDays: ['Fri', 'Sat'], defaultHoursPerDay: '8.00', lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10, overtimeRequiresApproval: true, maxDailyOvertimeHours: '2.00', lateDeductionPolicy: 'none', lateDeductionAmount: '0.00', wfhEnabled: true, regularisationMaxDaysPerMonth: 2, regularisationWindowDays: 7, biometricApiEnabled: false, biometricApiKeyConfigured: false, createdAt: timestamp, updatedAt: timestamp }
const shift = { id: shiftId, name: 'Morning clinic', code: 'MC', shiftType: 'fixed', shiftCategory: 'morning', startTime: '08:00:00', endTime: '17:00:00', splitStartTime: null, splitEndTime: null, breakMinutes: 60, expectedHours: '8.00', lateGraceMinutes: 10, earlyDepartureGraceMinutes: 10, isOvernight: false, minHoursFlexible: null, isActive: true, color: '#6366F1', minStaff: 2, createdAt: timestamp, updatedAt: timestamp }
const attendanceRecord = { id: id(41), employeeId, date: '2026-10-04', shiftId, clockInTime: '2026-10-04T04:05:00.000Z', clockOutTime: '2026-10-04T13:30:00.000Z', totalHours: '8.50', expectedHours: '8.00', status: 'LATE', resolutionType: null, lateMinutes: 5, earlyDepartureMinutes: 0, overtimeHours: '0.50', overtimeType: 'STANDARD', overtimeAmount: '25.00', overtimeApproved: false, absenceDeduction: '0.00', lateDeduction: '0.00', workedOnRestDay: false, restDaySubstitute: false, missingClockOut: false, isRamadanDay: false, periodClosed: false, evidenceFlags: [], sourceDigest, sourceStale: false, calculationVersion: 1, updatedAt: timestamp }
let clockEvent = { id: id(42), employeeId, eventType: 'CLOCK_IN', eventTime: '2026-10-04T04:05:00.000Z', method: 'MANUAL', notes: 'Synthetic check-in', createdAt: timestamp }
let rosterAssignment = { id: id(50), employeeId, employeeName: 'Alex Morgan', department: 'Clinical', shiftId, shiftName: shift.name, shiftCode: shift.code, shiftCategory: 'morning', date: '2026-10-04', published: false, plannedHours: '8.00', notes: 'Front desk cover', version: 1, leaveConflict: false, updatedAt: timestamp }
let publication = { id: null, period: '2026-10', status: 'draft', version: 0, currentVersionId: null, sourceVersion: null, publishedAt: null, publishedByAppUserId: null, recordCount: 0 }
const swap = { id: id(51), requesterEmployeeId: employeeId, requesterEmployeeName: 'Alex Morgan', targetEmployeeId: managerId, targetEmployeeName: 'Sam Taylor', requesterDate: '2026-10-04', targetDate: '2026-10-05', reason: 'Family appointment', status: 'pending', rejectionReason: '', expectedSourceVersion: digest, requesterAssignmentId: id(50), targetAssignmentId: id(52), requesterAssignmentVersion: 1, targetAssignmentVersion: 1, approvedPublicationVersionId: null, decidedAt: null, decidedByAppUserId: null, createdAt: timestamp, updatedAt: timestamp, version: 1 }

const query = new URLSearchParams(location.search)
const moduleName = query.get('module') ?? 'leave'
const staffingEnabled = query.get('staffing') !== 'off'
window.__restorationRequests = []
window.__restorationFailNext = false
const authentication = {
  async request(path, options = {}) {
    window.__restorationRequests.push({ path, options })
    const url = new URL(path, location.origin)
    const route = url.pathname
    const method = options.method ?? 'GET'
    const body = options.json ?? {}
    if (method !== 'GET' && window.__restorationFailNext) { window.__restorationFailNext = false; throw new Error('Synthetic rejected write') }
    if (route === `/api/v1/branches/${branchId}`) return { data: branch(staffingEnabled) }
    if (route === '/api/v1/departments') return { data: [department], page }
    if (route === '/api/v1/department-staffing-rules') return { data: staffingEnabled ? [staffingRule] : [], page }
    if (route === '/api/v1/employees') return { data: employees, page }
    if (route.endsWith('/portal-role')) return { data: { employeeId: route.includes(managerId) ? managerId : employeeId, activated: true, role: route.includes(managerId) ? 'manager' : 'employee' }, status: 200 }
    if (route === '/api/v1/leave/settings') return { data: leaveSettings }
    if (route === '/api/v1/leave/types') return { data: [leaveType], page }
    if (route === '/api/v1/leave/holidays') return { data: [holiday], page }
    if (route === '/api/v1/leave/balances/branch') return { data: [leaveBalance], page }
    if (route === '/api/v1/leave/requests/calendar/branch' && method === 'GET') return { data: [leaveRequest, submittedLeaveRequest].filter(Boolean), page }
    if (route === '/api/v1/leave/requests/branch' && method === 'POST') {
      submittedLeaveRequest = {
        ...leaveRequest,
        id: id(35),
        employeeId: body.employeeId,
        leaveTypeId: body.leaveTypeId,
        startDate: body.startDate,
        endDate: body.endDate,
        isHalfDay: body.isHalfDay,
        halfDayPeriod: body.halfDayPeriod,
        daysRequested: '1.00',
        status: 'Pending',
        reason: body.reason,
        relationship: body.relationship ?? '',
        deceasedName: body.deceasedName ?? '',
        dateOfDeath: body.dateOfDeath,
        childBirthDate: body.childBirthDate,
        childName: body.childName ?? '',
        expectedDueDate: body.expectedDueDate,
        institutionName: body.institutionName ?? '',
        examDates: body.examDates ?? '',
        substituteEmployeeId: body.substituteEmployeeId,
        submittedAt: timestamp,
        createdAt: timestamp,
        updatedAt: timestamp,
        warnings: [],
      }
      return { data: submittedLeaveRequest, status: 201, location: `/api/v1/leave/requests/${submittedLeaveRequest.id}` }
    }
    if (route === '/api/v1/leave/approvals/branch') return { data: [{ request: leaveRequest, employee: { id: employeeId, employeeNumber: 'E-3', name: 'Alex Morgan', jobTitle: 'Registered nurse', department: 'Clinical' }, leaveType, balance: leaveBalance, canDecide: true, visibleBecause: 'administrator' }], page }
    if (route === '/api/v1/leave/delegations/branch') return { data: [delegation] }
    if (route.includes('/leave/approvals/') && route.endsWith('/decision/branch')) { leaveRequest = { ...leaveRequest, status: body.decision === 'approve' ? 'Approved' : 'Rejected', updatedAt: '2026-10-04T09:00:00.000Z' }; return { data: leaveRequest } }
    if (route === '/api/v1/attendance-settings') return { data: attendanceSettings }
    if (route === '/api/v1/shifts') return { data: [shift], page }
    if (route === '/api/v1/attendance-records') return { data: [attendanceRecord], page }
    if (route === '/api/v1/clock-events') return { data: [clockEvent], page }
    if (route === '/api/v1/clock-events/manual') { clockEvent = { ...clockEvent, id: id(43), employeeId: body.employeeId, eventType: body.eventType, eventTime: '2026-10-04T10:00:00.000Z', notes: body.note }; return { data: clockEvent, status: 201, location: `/api/v1/clock-events/${clockEvent.id}` } }
    if (route === '/api/v1/attendance/regularisations') return { data: [], page }
    if (route === '/api/v1/attendance/audit') return { data: [], page }
    if (route === '/api/v1/attendance/periods') return { data: [], page }
    if (route === '/api/v1/roster/months/2026-10') return { data: [rosterAssignment], page }
    if (route === '/api/v1/roster/months/2026-10/validation') return { data: { period: '2026-10', staffingEnforced: staffingEnabled, leaveConflicts: [], staffingViolations: staffingEnabled ? [] : null, ready: true } }
    if (route === '/api/v1/roster/months/2026-10/publication') return { data: publication }
    if (route === '/api/v1/roster/months/2026-10/drafts') { rosterAssignment = { ...rosterAssignment, id: id(53), employeeId: body.employeeId, shiftId: body.shiftId, date: body.date, plannedHours: String(Number(body.plannedHours).toFixed(2)), notes: body.notes, version: 1, updatedAt: '2026-10-04T09:00:00.000Z' }; return { data: rosterAssignment } }
    if (route.startsWith('/api/v1/roster/months/2026-10/drafts/')) { rosterAssignment = { ...rosterAssignment, ...body, version: rosterAssignment.version + 1, updatedAt: '2026-10-04T09:00:00.000Z' }; delete rosterAssignment.expectedVersion; return { data: rosterAssignment } }
    if (route === '/api/v1/roster/months/2026-10/publish') { publication = { id: id(54), period: '2026-10', status: 'published', version: 1, currentVersionId: id(55), sourceVersion: digest, publishedAt: timestamp, publishedByAppUserId: id(5), recordCount: 1 }; rosterAssignment = { ...rosterAssignment, published: true }; return { data: publication } }
    if (route === '/api/v1/roster/shift-swaps') return { data: [swap], page }
    throw new Error(`No synthetic response for ${method} ${path}`)
  },
}

const shared = { account, authentication, branchId }
let content
if (moduleName === 'leave') content = <LeaveManager {...shared} />
else if (moduleName === 'attendance') content = <AttendanceManager {...shared} />
else if (moduleName === 'roster') content = <RosterManager {...shared} />
else content = <DepartmentManager authentication={authentication} branchId={branchId} clearBranch={() => {}} />
export const restorationFixture = { account, authentication, branchId, branch: branch(staffingEnabled) }
if (!query.has('fixtureOnly')) createRoot(document.getElementById('root')).render(<main className="portal-main"><div className="portal-route">{content}</div></main>)
