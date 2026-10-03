export const employeeRouteGroups = Object.freeze([
  Object.freeze({
    path: '/employee',
    description: 'Review your dashboard, notifications, and assigned tasks.',
    views: Object.freeze([]),
  }),
  Object.freeze({
    path: '/employee/profile',
    description: 'Review your profile and update the contact fields available to your account.',
    views: Object.freeze(['EmployeeDirectory']),
  }),
  Object.freeze({
    path: '/employee/leave',
    description: 'Review balances and the leave calendar, then manage your requests and attachments.',
    views: Object.freeze(['LeaveOverview']),
  }),
  Object.freeze({
    path: '/employee/time',
    description: 'Review your attendance and published schedule, then manage corrections and shift swaps.',
    views: Object.freeze(['PersonalAttendance', 'PersonalSchedule']),
  }),
  Object.freeze({
    path: '/employee/pay',
    description: 'Review your payslips and manage your expense, receipt, and advance requests.',
    views: Object.freeze(['Payslips', 'Expenses', 'Advances']),
  }),
  Object.freeze({
    path: '/employee/records',
    description: 'Manage your documents and review your insurance and assigned assets.',
    views: Object.freeze(['RecordsBenefits']),
  }),
  Object.freeze({
    path: '/employee/development',
    description: 'Review your training, certifications, CME progress, and appraisals.',
    views: Object.freeze(['DevelopmentAssets', 'AppraisalsIncidents']),
  }),
  Object.freeze({
    path: '/employee/requests',
    description: 'Submit letter and custom requests, then open authorized completed output.',
    views: Object.freeze(['LetterRequests']),
  }),
])

const groupsByPath = new Map(employeeRouteGroups.map((group) => [group.path, group]))

export const employeeParityRoutes = Object.freeze([
  Object.freeze({ path: '/employee/schedule', description: 'Review published shifts and request a shift swap.', views: Object.freeze(['PersonalSchedule']) }),
  Object.freeze({ path: '/employee/attendance', description: 'Review personal attendance and submit correction requests.', views: Object.freeze(['PersonalAttendance']) }),
  Object.freeze({ path: '/employee/payslips', description: 'Review issued payslips and open the server-rendered PDF.', views: Object.freeze(['Payslips']) }),
  Object.freeze({ path: '/employee/advances', description: 'Request and track salary advances and their repayment schedules.', views: Object.freeze(['Advances']) }),
  Object.freeze({ path: '/employee/expenses', description: 'Submit and track personal expense claims.', views: Object.freeze(['Expenses']) }),
  Object.freeze({ path: '/employee/training', description: 'Manage personal training, certifications, and CME progress.', views: Object.freeze(['DevelopmentAssets']) }),
  Object.freeze({ path: '/employee/appraisals', description: 'Review appraisal results and development plans.', views: Object.freeze(['AppraisalsIncidents']) }),
  Object.freeze({ path: '/employee/documents', description: 'Submit and review personal documents.', views: Object.freeze(['RecordsBenefits']) }),
  Object.freeze({ path: '/employee/tasks', description: 'Review personal work items and open the related module.', views: Object.freeze(['Tasks']) }),
])

const parityRoutesByPath = new Map(employeeParityRoutes.map((group) => [group.path, group]))

export function employeeRouteGroup(path) {
  return groupsByPath.get(path) ?? parityRoutesByPath.get(path) ?? null
}
