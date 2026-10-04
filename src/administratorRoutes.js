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

export const administratorParityRouteGroups = Object.freeze([
  Object.freeze({ path: '/admin', title: 'Dashboard', description: 'Review payroll, workforce, compliance, and pending work.', views: Object.freeze(['Dashboard']) }),
  Object.freeze({ path: '/admin/clinical-dashboard', title: 'Clinical Dashboard', description: 'Review clinical staffing and professional compliance.', views: Object.freeze(['Dashboard']) }),
  Object.freeze({ path: '/admin/company-settings', title: 'Company Settings', description: 'Manage the company, selected branch, payroll settings, and employer details.', views: Object.freeze(['OrganizationSettings']) }),
  Object.freeze({ path: '/admin/employees', title: 'Employees', description: 'Manage employee records, documents, benefits, contracts, and offboarding.', views: Object.freeze(['EmployeeDirectory', 'RecordsBenefits', 'Offboarding']) }),
  Object.freeze({ path: '/admin/departments', title: 'Departments', description: 'Manage the department hierarchy and staffing rules.', views: Object.freeze(['DepartmentManager']) }),
  Object.freeze({ path: '/admin/requests', title: 'Requests', description: 'Review and complete employee letter and custom requests.', views: Object.freeze(['LetterRequests']) }),
  Object.freeze({ path: '/admin/payroll', title: 'Payroll Module', description: 'Build, approve, generate, and export payroll and WPS files.', views: Object.freeze(['Payroll', 'WpsNafis']) }),
  Object.freeze({ path: '/admin/advances', title: 'Advances', description: 'Create, approve, reject, schedule, and settle salary advances.', views: Object.freeze(['Advances']) }),
  Object.freeze({ path: '/admin/expenses', title: 'Expenses', description: 'Review, decide, and track selected-branch expense claims.', views: Object.freeze(['Expenses']) }),
  Object.freeze({ path: '/admin/leave', title: 'Leave', description: 'Manage leave settings, balances, requests, decisions, and delegations.', views: Object.freeze(['LeaveConfiguration', 'LeaveOverview', 'LeaveApprovals']) }),
  Object.freeze({ path: '/admin/attendance', title: 'Attendance', description: 'Manage rules, imports, calculations, corrections, audit, and period close.', views: Object.freeze(['AttendanceConfiguration', 'AttendanceIngestion', 'AttendanceCalculation', 'AttendanceExceptions', 'AttendancePeriods']) }),
  Object.freeze({ path: '/admin/assets', title: 'Assets', description: 'Manage the asset register, assignments, returns, and asset state.', views: Object.freeze(['DevelopmentAssets']) }),
  Object.freeze({ path: '/admin/training', title: 'Training', description: 'Manage training, certifications, evidence, reviews, and CME.', views: Object.freeze(['DevelopmentAssets']) }),
  Object.freeze({ path: '/admin/appraisals', title: 'Appraisals', description: 'Manage appraisal cycles, ratings, review, calibration, and closure.', views: Object.freeze(['AppraisalsIncidents']) }),
  Object.freeze({ path: '/admin/roster', title: 'Roster', description: 'Manage roster drafts, validation, publication, actual hours, and shift swaps.', views: Object.freeze(['RosterDrafts', 'ShiftSwapQueue']) }),
  Object.freeze({ path: '/admin/incidents', title: 'Incidents', description: 'Record, investigate, correct, and close workplace incidents.', views: Object.freeze(['AppraisalsIncidents']) }),
  Object.freeze({ path: '/admin/reports', title: 'Reports', description: 'Run server-backed reports and download authorized output.', views: Object.freeze(['Reports']) }),
  Object.freeze({ path: '/admin/tasks', title: 'Tasks', description: 'Review administrator work items and open the related module.', views: Object.freeze(['Tasks']) }),
])

const groupsByPath = new Map([
  ...administratorRouteGroups.map((group) => [group.path, group]),
  ...administratorParityRouteGroups.map((group) => [group.path, group]),
])

export function administratorRouteGroup(path) {
  return groupsByPath.get(path) ?? null
}
