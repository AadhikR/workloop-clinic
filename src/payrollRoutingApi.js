import { parseBranch } from './organizationApi.js'

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
function parse(value, branchId, field) {
  if (!value || Object.keys(value).sort().join('|') !== ['branch', field].sort().join('|')) throw new Error('Invalid routing response')
  const branch = parseBranch(value.branch)
  if (branch.id !== branchId || !instant.test(branch.updatedAt) || !Array.isArray(value[field])) throw new Error('Invalid routing response')
  const drafts = value[field]
  for (const item of drafts) {
    if (Object.keys(item).sort().join('|') !== 'expectedUpdatedAt|id|sourceDigest' || !uuid.test(item.id) || !instant.test(item.expectedUpdatedAt) || !/^(?:[0-9a-f]{64})?$/.test(item.sourceDigest)) throw new Error('Invalid routing response')
  }
  if (new Set(drafts.map((item) => item.id)).size !== drafts.length) throw new Error('Invalid routing response')
  return { branch, [field]: drafts }
}
export async function readPayrollRouting(authentication, branchId) {
  if (!uuid.test(branchId)) throw new TypeError('Invalid branch')
  const result = await authentication.request(`/api/v1/branches/${branchId}/payroll-routing`, { access: 'protected', headers: { 'X-Workloop-Branch-ID': branchId } })
  return parse(result.data, branchId, 'drafts')
}
export async function changePayrollRouting(authentication, snapshot, routingCode, key) {
  if (!/^[0-9]{9}$/.test(routingCode) || !uuid.test(key)) throw new TypeError('Enter a nine-digit routing code.')
  parse(snapshot, snapshot.branch.id, 'drafts')
  const branchId = snapshot.branch.id
  const result = await authentication.request(`/api/v1/branches/${branchId}/payroll-routing`, {
    access: 'protected', method: 'POST', headers: { 'X-Workloop-Branch-ID': branchId, 'Idempotency-Key': key },
    json: { expectedUpdatedAt: snapshot.branch.updatedAt, routingCode, drafts: snapshot.drafts },
  })
  return parse(result.data, branchId, 'changedRuns')
}
