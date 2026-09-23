const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const instant = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const money = /^(0|[1-9]\d{0,11})\.\d{2}$/
const digest = /^sha256:[0-9a-f]{64}$/

function exact(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...keys].sort().join('|')
}

function headers(branchId, idempotent = false) {
  if (!uuid.test(branchId)) throw new TypeError('Invalid branch ID')
  return {
    'X-Workloop-Branch-ID': branchId,
    ...(idempotent ? { 'Idempotency-Key': crypto.randomUUID() } : {}),
  }
}

const taskKeys = [
  'id', 'taskName', 'completed', 'completedAt', 'notes', 'sortOrder', 'source',
  'templateId', 'updatedAt',
]

function parseTask(value) {
  if (!exact(value, taskKeys) || !uuid.test(value.id)
    || !['template', 'custom'].includes(value.source)
    || value.templateId !== null && !uuid.test(value.templateId)
    || value.completedAt !== null && !instant.test(value.completedAt)
    || !instant.test(value.updatedAt)) throw new Error('Invalid offboarding task')
  return Object.freeze(value)
}

const checklistKeys = [
  'id', 'employeeId', 'employeeName', 'employmentStatus', 'status',
  'visaCancellationStatus', 'visaCancellationDate', 'finalSettlementId', 'createdAt',
  'updatedAt', 'completedAt', 'tasks',
]

export function parseChecklist(value) {
  if (!exact(value, checklistKeys) || !uuid.test(value.id) || !uuid.test(value.employeeId)
    || !['in_progress', 'completed'].includes(value.status)
    || !['not_started', 'initiated', 'submitted_gdrfa', 'cancelled'].includes(value.visaCancellationStatus)
    || value.finalSettlementId !== null && !uuid.test(value.finalSettlementId)
    || !instant.test(value.createdAt) || !instant.test(value.updatedAt)
    || value.completedAt !== null && !instant.test(value.completedAt)
    || !Array.isArray(value.tasks)) throw new Error('Invalid offboarding checklist')
  return Object.freeze({ ...value, tasks: value.tasks.map(parseTask) })
}

const amountKeys = [
  'finalSalary', 'leaveEncashment', 'gratuity', 'noticePay', 'otherEarnings',
  'advanceDeduction', 'assetDeduction', 'noticeDeduction', 'otherDeductions',
  'grossAmount', 'totalDeductions', 'netAmount',
]
const previewKeys = [
  ...amountKeys, 'policyVersion', 'policyDigest', 'sourceDigest', 'sourceCapturedAt',
  'serviceDays', 'gratuityDays', 'leaveDays',
]

export function parsePreview(value) {
  if (!exact(value, previewKeys) || amountKeys.some((key) => !money.test(value[key]))
    || !digest.test(value.policyDigest) || !digest.test(value.sourceDigest)
    || !instant.test(value.sourceCapturedAt)) throw new Error('Invalid settlement preview')
  return Object.freeze(value)
}

function collection(response) {
  if (!Array.isArray(response?.data) || !exact(response.page, ['limit', 'nextCursor', 'hasMore'])) {
    throw new Error('Invalid offboarding collection')
  }
  return response.data.map(parseChecklist)
}

export async function readChecklists(authentication, branchId) {
  return collection(await authentication.request('/api/v1/offboarding', {
    access: 'protected', headers: headers(branchId),
  }))
}

export async function initializeChecklist(authentication, branchId, employeeId) {
  if (!uuid.test(employeeId)) throw new TypeError('Invalid employee ID')
  const response = await authentication.request(`/api/v1/offboarding/${employeeId}/initialize`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
  })
  return parseChecklist(response.data)
}

export async function changeTask(authentication, branchId, checklist, task, command, notes = '') {
  const response = await authentication.request(
    `/api/v1/offboarding/${checklist.id}/tasks/${task.id}/${command}`,
    {
      access: 'protected', method: 'POST', headers: headers(branchId, true),
      json: {
        expectedChecklistUpdatedAt: checklist.updatedAt,
        expectedTaskUpdatedAt: task.updatedAt, notes,
      },
    },
  )
  return parseChecklist(response.data)
}

export async function addTask(authentication, branchId, checklist, taskName) {
  const response = await authentication.request(`/api/v1/offboarding/${checklist.id}/tasks`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { taskName, expectedChecklistUpdatedAt: checklist.updatedAt },
  })
  return parseChecklist(response.data)
}

export async function deleteTask(authentication, branchId, checklist, task) {
  const response = await authentication.request(
    `/api/v1/offboarding/${checklist.id}/tasks/${task.id}`,
    {
      access: 'protected', method: 'DELETE', headers: headers(branchId, true),
      json: {
        expectedChecklistUpdatedAt: checklist.updatedAt,
        expectedTaskUpdatedAt: task.updatedAt,
        notes: task.notes,
      },
    },
  )
  return parseChecklist(response.data)
}

export async function advanceVisa(authentication, branchId, checklist) {
  const next = { not_started: 'initiated', initiated: 'submitted_gdrfa', submitted_gdrfa: 'cancelled' }
  const status = next[checklist.visaCancellationStatus]
  if (!status) throw new Error('Visa cancellation is already complete')
  const response = await authentication.request(`/api/v1/offboarding/${checklist.id}/visa`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: { status, expectedChecklistUpdatedAt: checklist.updatedAt },
  })
  return parseChecklist(response.data)
}

export async function previewSettlement(authentication, branchId, checklist, adjustments) {
  const response = await authentication.request(
    `/api/v1/offboarding/${checklist.id}/settlement/preview`,
    {
      access: 'protected', method: 'POST', headers: headers(branchId),
      json: { expectedChecklistUpdatedAt: checklist.updatedAt, ...adjustments },
    },
  )
  return parsePreview(response.data)
}

export async function completeOffboarding(
  authentication, branchId, checklist, adjustments, preview, terminationReason,
) {
  const response = await authentication.request(`/api/v1/offboarding/${checklist.id}/complete`, {
    access: 'protected', method: 'POST', headers: headers(branchId, true),
    json: {
      expectedChecklistUpdatedAt: checklist.updatedAt, ...adjustments,
      expectedSourceDigest: preview.sourceDigest, terminationReason,
    },
  })
  return response.data
}

export const offboardingPatterns = Object.freeze({ uuid, instant, money, digest })
