const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const allowedExtensions = new Set(['pdf', 'png', 'jpg', 'jpeg'])
const maximumSize = 10_485_760

function branchHeaders(branchId) {
  if (typeof branchId !== 'string' || !uuidPattern.test(branchId)) {
    throw new TypeError('Invalid branch ID')
  }
  return { 'X-Workloop-Branch-ID': branchId }
}

function exactKeys(value, keys) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false
  const actual = Object.keys(value).sort()
  const expected = [...keys].sort()
  return actual.length === expected.length
    && actual.every((key, index) => key === expected[index])
}

function parseAttachment(value) {
  if (
    !exactKeys(value, [
      'id', 'fileName', 'contentType', 'sizeBytes', 'sha256', 'uploadedAt', 'expiresAt',
    ])
    || !uuidPattern.test(value.id)
    || typeof value.fileName !== 'string'
    || !['application/pdf', 'image/png', 'image/jpeg'].includes(value.contentType)
    || !Number.isInteger(value.sizeBytes)
    || !/^[0-9a-f]{64}$/.test(value.sha256)
    || !instantPattern.test(value.uploadedAt)
    || value.expiresAt !== null && !instantPattern.test(value.expiresAt)
  ) throw new Error('Invalid leave attachment response')
  return Object.freeze({ ...value })
}

export function validateAttachmentFile(file) {
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!allowedExtensions.has(extension) || file.size < 1 || file.size > maximumSize) {
    throw new TypeError('Choose one PDF, PNG, or JPEG file no larger than 10 MiB.')
  }
}

export async function uploadLeaveAttachment(
  authentication, branchId, requestId, file, { signal } = {},
) {
  validateAttachmentFile(file)
  const headers = branchId === null ? undefined : branchHeaders(branchId)
  const intent = await authentication.request('/api/v1/leave/attachment-submissions', {
    access: 'protected', method: 'POST', headers, json: { requestId }, signal,
  })
  if (
    intent === null
    || typeof intent !== 'object'
    || Array.isArray(intent)
    || !exactKeys(intent.data, ['id', 'submissionToken', 'expiresAt'])
    || !uuidPattern.test(intent.data.id)
    || typeof intent.data.submissionToken !== 'string'
    || !instantPattern.test(intent.data.expiresAt)
  ) throw new Error('Invalid leave attachment response')
  const digestBytes = await globalThis.crypto.subtle.digest('SHA-256', await file.arrayBuffer())
  const digest = Array.from(new Uint8Array(digestBytes), (byte) => (
    byte.toString(16).padStart(2, '0')
  )).join('')
  const form = new FormData()
  form.append('file', file, file.name)
  form.append('submissionToken', intent.data.submissionToken)
  form.append('sha256', digest)
  const uploaded = await authentication.request(
    `/api/v1/leave/attachment-submissions/${intent.data.id}/file`,
    { access: 'protected', method: 'POST', headers, form, signal },
  )
  if (uploaded === null || typeof uploaded !== 'object' || Array.isArray(uploaded)) {
    throw new Error('Invalid leave attachment response')
  }
  return parseAttachment(uploaded.data)
}

export async function createLeaveAttachmentDownload(
  authentication, branchId, attachmentId, { signal } = {},
) {
  if (!uuidPattern.test(attachmentId)) throw new TypeError('Invalid attachment ID')
  const response = await authentication.request(
    `/api/v1/leave/attachments/${attachmentId}/download`,
    {
      access: 'protected',
      method: 'POST',
      headers: branchId === null ? undefined : branchHeaders(branchId),
      signal,
    },
  )
  if (
    response === null
    || typeof response !== 'object'
    || Array.isArray(response)
    || !exactKeys(response.data, ['url', 'expiresAt'])
    || typeof response.data.url !== 'string'
    || !instantPattern.test(response.data.expiresAt)
  ) throw new Error('Invalid leave attachment response')
  return Object.freeze({ ...response.data })
}
