export const administratorRouteGroups = Object.freeze([
  Object.freeze({
    path: '/admin',
    description: 'Review administrator dashboards, notifications, and assigned tasks.',
    views: Object.freeze([]),
  }),
  Object.freeze({
    path: '/admin/organization',
    description: 'Manage the company, selected branch, departments, and staffing rules.',
    views: Object.freeze(['OrganizationSettings', 'DepartmentManager']),
  }),
  Object.freeze({
    path: '/admin/people',
    description: 'Manage employees, lifecycle changes, job history, imports, exports, and portal roles.',
    views: Object.freeze(['EmployeeDirectory']),
  }),
  Object.freeze({
    path: '/admin/leave',
    description: 'Manage leave configuration, balances, requests, attachments, approvals, and delegations.',
    views: Object.freeze(['LeaveConfiguration', 'LeaveOverview', 'LeaveApprovals']),
  }),
  Object.freeze({
    path: '/admin/attendance',
    description: 'Manage attendance rules, ingestion, calculations, exceptions, audit, and period close.',
    views: Object.freeze([
      'AttendanceConfiguration',
      'AttendanceIngestion',
      'AttendanceCalculation',
      'AttendanceExceptions',
      'AttendancePeriods',
    ]),
  }),
  Object.freeze({
    path: '/admin/roster',
    description: 'Manage roster drafts, validation, publication, actual hours, overtime, and shift swaps.',
    views: Object.freeze(['RosterDrafts', 'ShiftSwapQueue']),
  }),
  Object.freeze({
    path: '/admin/payroll',
    description: 'Manage payroll, payslips, expenses, advances, WPS, SIF, and Nafis.',
    views: Object.freeze(['Payroll', 'Expenses', 'Advances', 'Payslips', 'WpsNafis']),
  }),
  Object.freeze({
    path: '/admin/records',
    description: 'Manage records, insurance, contracts, letters, offboarding, and authorized files.',
    views: Object.freeze(['RecordsBenefits', 'LetterRequests', 'Offboarding']),
  }),
  Object.freeze({
    path: '/admin/development',
    description: 'Manage assets, training, certifications, CME, appraisals, and incidents.',
    views: Object.freeze(['DevelopmentAssets', 'AppraisalsIncidents']),
  }),
  Object.freeze({
    path: '/admin/reports',
    description: 'Run server-backed reports and download authorized output.',
    views: Object.freeze(['Reports']),
  }),
])

const groupsByPath = new Map(administratorRouteGroups.map((group) => [group.path, group]))

export function administratorRouteGroup(path) {
  return groupsByPath.get(path) ?? null
}
