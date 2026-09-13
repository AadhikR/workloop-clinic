function branchHeaders(branchId) {
  if (typeof branchId !== 'string' || !/^[0-9a-f-]{36}$/.test(branchId)) throw new TypeError('Invalid branch ID')
  return { 'X-Workloop-Branch-ID': branchId }
}

export function readLeaveConfiguration(authentication, branchId, { signal } = {}) {
  const headers = branchHeaders(branchId)
  return Promise.all([
    authentication.request('/api/v1/leave/settings', { access: 'protected', headers, signal }),
    authentication.request('/api/v1/leave/types', { access: 'protected', headers, signal }),
    authentication.request('/api/v1/leave/holidays', { access: 'protected', headers, signal }),
  ]).then(([settings, types, holidays]) => ({
    settings: settings.data,
    types: types.data,
    holidays: holidays.data,
  }))
}

export function seedLeaveTypes(authentication, branchId, { signal } = {}) {
  return authentication.request('/api/v1/leave/types/seed', {
    access: 'protected',
    method: 'POST',
    headers: branchHeaders(branchId),
    signal,
  }).then((response) => response.data)
}

export function seedPublicHolidays(authentication, branchId, year, holidays, { signal } = {}) {
  return authentication.request('/api/v1/leave/holidays/seed', {
    access: 'protected',
    method: 'POST',
    headers: branchHeaders(branchId),
    body: { year, holidays },
    signal,
  }).then((response) => response.data)
}
