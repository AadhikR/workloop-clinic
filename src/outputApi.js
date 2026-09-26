const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const periodPattern = /^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])$/

function request(authentication, branchId, path) {
  if (!uuidPattern.test(branchId)) throw new TypeError('Invalid export branch')
  return authentication.request(path, {
    access: 'protected',
    headers: { 'X-Workloop-Branch-ID': branchId },
    responseType: 'bytes',
  })
}

export const downloadEmployeeTemplate = (authentication, branchId) => (
  request(authentication, branchId, '/api/v1/exports/employees/template.csv')
)

export const downloadEmployees = (authentication, branchId, employeeId = null) => {
  if (employeeId !== null && !uuidPattern.test(employeeId)) throw new TypeError('Invalid employee export')
  const suffix = employeeId ? `?employeeId=${employeeId}` : ''
  return request(authentication, branchId, `/api/v1/exports/employees.csv${suffix}`)
}

export const downloadLeaveBalances = (authentication, branchId, year) => {
  if (!Number.isInteger(year) || year < 1900 || year > 2100) throw new TypeError('Invalid leave export')
  return request(authentication, branchId, `/api/v1/exports/leave-balances.csv?year=${year}`)
}

export const downloadAttendance = (authentication, branchId, periodId) => {
  if (!uuidPattern.test(periodId)) throw new TypeError('Invalid attendance export')
  return request(authentication, branchId, `/api/v1/exports/attendance/${periodId}.csv`)
}

export const downloadRoster = (authentication, branchId, period) => {
  if (!periodPattern.test(period)) throw new TypeError('Invalid roster export')
  return request(authentication, branchId, `/api/v1/exports/roster.csv?period=${period}`)
}

export const downloadNafis = (authentication, branchId, snapshotId) => {
  if (!uuidPattern.test(snapshotId)) throw new TypeError('Invalid Nafis export')
  return request(authentication, branchId, `/api/v1/exports/nafis/${snapshotId}.csv`)
}
