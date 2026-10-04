import { readReport } from './reportApi.js'

export async function readDashboardPanel(authentication, branchId, reportId, filters = {}) {
  let result = await readReport(authentication, branchId, reportId, { ...filters, limit: 200 })
  const seen = new Set()
  while (result.nextCursor) {
    if (seen.has(result.nextCursor)) throw new Error('Dashboard pagination repeated')
    seen.add(result.nextCursor)
    const next = await readReport(authentication, branchId, reportId, { ...filters, limit: 200, cursor: result.nextCursor })
    if (next.sourceVersion !== result.sourceVersion) throw new Error('Dashboard source changed')
    result = { ...next, rows: [...result.rows, ...next.rows] }
  }
  return result
}
