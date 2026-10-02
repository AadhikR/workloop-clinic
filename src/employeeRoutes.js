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

export function employeeRouteGroup(path) {
  return groupsByPath.get(path) ?? null
}
