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

const groupsByPath = new Map(managerRouteGroups.map((group) => [group.path, group]))

export function managerRouteGroup(path) {
  return groupsByPath.get(path) ?? null
}
