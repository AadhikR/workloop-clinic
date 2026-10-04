export const managerRouteGroups = Object.freeze([
  Object.freeze({
    path: '/manager',
    description: 'Review your dashboard, notifications, and assigned tasks.',
    views: Object.freeze([]),
  }),
  Object.freeze({
    path: '/manager/team',
    description: 'Review your profile and the direct reports returned for your account.',
    views: Object.freeze(['EmployeeDirectory']),
  }),
  Object.freeze({
    path: '/manager/leave',
    description: 'Manage your leave and the approval queue assigned to you.',
    views: Object.freeze(['LeaveOverview', 'LeaveApprovals']),
  }),
  Object.freeze({
    path: '/manager/time',
    description: 'Review your attendance, corrections, published schedule, colleagues, and shift swaps.',
    views: Object.freeze(['PersonalAttendance', 'PersonalSchedule']),
  }),
  Object.freeze({
    path: '/manager/expenses',
    description: 'Submit personal claims and review the direct-report expense queue assigned to you.',
    views: Object.freeze(['Expenses']),
  }),
  Object.freeze({
    path: '/manager/development',
    description: 'Manage supported self and direct-report development and appraisal work.',
    views: Object.freeze(['DevelopmentAssets', 'AppraisalsIncidents']),
  }),
  Object.freeze({
    path: '/manager/requests',
    description: 'Use the supported self-service advance, record, benefit, letter, and custom request paths.',
    views: Object.freeze(['Advances', 'RecordsBenefits', 'LetterRequests']),
  }),
])

export const managerParityRouteGroups = Object.freeze([
  Object.freeze({ path: '/manager', title: 'Home', description: 'Review your work summary, notifications, and current priorities.', views: Object.freeze(['Dashboard']) }),
  Object.freeze({ path: '/manager/leave-queue', title: 'Leave Queue', description: 'Review leave requests assigned to you or delegated to you.', views: Object.freeze(['LeaveApprovals']) }),
  Object.freeze({ path: '/manager/expense-queue', title: 'Expense Queue', description: 'Review direct-report expense claims assigned to you.', views: Object.freeze(['Expenses']) }),
  Object.freeze({ path: '/manager/appraisals', title: 'Appraisals', description: 'Review direct-report appraisals and your own appraisal results.', views: Object.freeze(['AppraisalsIncidents']) }),
  Object.freeze({ path: '/manager/leave', title: 'My Leave', description: 'Submit and track your leave, balances, and calendar.', views: Object.freeze(['LeaveOverview']) }),
  Object.freeze({ path: '/manager/schedule', title: 'Schedule', description: 'Review your published shifts and request shift swaps.', views: Object.freeze(['PersonalSchedule']) }),
  Object.freeze({ path: '/manager/attendance', title: 'My Attendance', description: 'Review your attendance and submit correction requests.', views: Object.freeze(['PersonalAttendance']) }),
  Object.freeze({ path: '/manager/payslips', title: 'Payslips', description: 'Review your issued payslips and authorized PDF files.', views: Object.freeze(['Payslips']) }),
  Object.freeze({ path: '/manager/advances', title: 'Advances', description: 'Request and track your salary advances and repayment schedules.', views: Object.freeze(['Advances']) }),
  Object.freeze({ path: '/manager/expenses', title: 'Expenses', description: 'Submit and track your own expense claims.', views: Object.freeze(['Expenses']) }),
  Object.freeze({ path: '/manager/training', title: 'Training', description: 'Manage supported team training and your personal development records.', views: Object.freeze(['DevelopmentAssets']) }),
  Object.freeze({ path: '/manager/documents', title: 'Documents', description: 'Submit and review your personal documents.', views: Object.freeze(['RecordsBenefits']) }),
  Object.freeze({ path: '/manager/requests', title: 'Requests', description: 'Submit and track your letter and custom requests.', views: Object.freeze(['LetterRequests']) }),
  Object.freeze({ path: '/manager/profile', title: 'Profile', description: 'Review your employment details and update permitted contact fields.', views: Object.freeze(['EmployeeProfile']) }),
  Object.freeze({ path: '/manager/tasks', title: 'Tasks', description: 'Review personal and authorized team work items.', views: Object.freeze(['Tasks']) }),
])

const groupsByPath = new Map([
  ...managerRouteGroups.map((group) => [group.path, group]),
  ...managerParityRouteGroups.map((group) => [group.path, group]),
])

export function managerRouteGroup(path) {
  return groupsByPath.get(path) ?? null
}
