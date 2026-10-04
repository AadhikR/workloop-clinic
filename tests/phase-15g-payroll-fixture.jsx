import { mountPhase15CAdministrator } from './phase-15c-harness.jsx'

const id = (suffix) => `b2000000-0000-4000-8000-${suffix.padStart(12, '0')}`
const timestamp = '2026-10-04T08:00:00.000Z'
const entry = (suffix, employeeName) => ({
  id: id(suffix), employeeId: id(`1${suffix}`), employeeName,
  basicSalary: '10000.00', housingAllowance: '2000.00', transportAllowance: '500.00',
  fixedAllowance: '250.00', increment: '0.00', bonus: '0.00', otherPay: '0.00',
  variableAllowance: '0.00', leaveDeduction: '0.00', fixedPay: '12750.00',
  grossPay: '12750.00', totalDeductions: '0.00', netPay: '12750.00',
  wpsBasicPay: '10000.00', wpsVariablePay: '2750.00', excluded: false,
  additionalAllowances: [], deductions: [], sourceExplanations: [], sourceFingerprint: 'a'.repeat(64),
})

export function mountPayrollReview({ blocked = true } = {}) {
  const run = {
    id: id('20'), period: '2026-10', paymentDate: '2026-10-28', sequence: '0001',
    runStatus: 'draft', approvalStatus: 'draft', employeeCount: 2, totalAmount: '25500.00',
    validationStatus: blocked ? 'blocking' : 'valid',
    blockingErrors: blocked ? ['payroll_input_not_ready:attendance', 'payroll_input_not_ready:roster'] : [],
    sourceWarnings: blocked ? ['attendance_input_not_ready', 'roster_input_not_ready'] : [],
    createdAt: timestamp, updatedAt: timestamp,
  }
  const detail = { ...run, entries: [entry('21', 'Alex Morgan'), entry('22', 'Sam Taylor')] }
  mountPhase15CAdministrator({
    path: '/admin/payroll',
    responses: {
      '/api/v1/payroll-runs': { data: [run], page: { limit: 50, nextCursor: null, hasMore: false } },
      [`/api/v1/payroll-runs/${run.id}`]: { data: detail },
      [`/api/v1/payroll-runs/${run.id}/approval-history`]: { data: [] },
      [`/api/v1/payroll-runs/${run.id}/entries`]: { data: detail },
    },
  })
}

export function mountLeaveReview() {
  const page = { limit: 100, nextCursor: null, hasMore: false }
  mountPhase15CAdministrator({ path: '/admin/leave', responses: {
    '/api/v1/leave/balances/branch?year=2026&limit=100': { data: [], page },
    '/api/v1/leave/requests/calendar/branch?year=2026&limit=100': { data: [], page },
    '/api/v1/leave/types?limit=100': { data: [], page },
    '/api/v1/employees?limit=100': { data: [], page },
  } })
}
