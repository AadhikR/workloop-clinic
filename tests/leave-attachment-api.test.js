import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createLeaveAttachmentDownload,
  uploadStagedLeaveAttachment,
  uploadLeaveAttachment,
  validateAttachmentFile,
} from '../src/leaveAttachmentApi.js'

const branchId = '20000000-0000-4000-8000-000000000001'
const requestId = '7a2fde23-dc8c-560c-937c-4ef631aff6b2'
const attachmentId = '8d000000-0000-4000-8000-000000000001'
const timestamp = '2026-09-14T12:15:00.000Z'
const transport = (data, status = 200) => ({
  status,
  data,
  correlationId: '00000000-0000-4000-8000-000000000001',
  location: null,
  page: null,
  replayed: false,
})

test('uploads one approved file through a fresh one-use intent', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      if (calls.length === 1) {
        return transport(
          {
            id: attachmentId,
            submissionToken: `wlat1.${attachmentId}.${'A'.repeat(43)}`,
            expiresAt: timestamp,
          },
          201,
        )
      }
      return transport(
        {
          id: attachmentId,
          fileName: 'proof.pdf',
          contentType: 'application/pdf',
          sizeBytes: 16,
          sha256: '0'.repeat(64),
          uploadedAt: timestamp,
          expiresAt: null,
        },
        201,
      )
    },
  }
  const file = new File(['%PDF-1.7\n%%EOF'], 'proof.pdf', { type: 'application/pdf' })

  const result = await uploadLeaveAttachment(
    authentication, branchId, requestId, file,
  )

  assert.equal(result.id, attachmentId)
  assert.deepEqual(calls[0].options.json, { requestId })
  assert.equal(calls[0].options.headers['X-Workloop-Branch-ID'], branchId)
  assert.ok(calls[1].options.form instanceof FormData)
  assert.equal(calls[1].options.form.get('submissionToken').startsWith('wlat1.'), true)
  assert.match(calls[1].options.form.get('sha256'), /^[0-9a-f]{64}$/)
})

test('rejects disallowed extensions and oversized attachment files locally', () => {
  assert.throws(
    () => validateAttachmentFile(new File(['text'], 'proof.txt', { type: 'text/plain' })),
    /PDF, PNG, or JPEG/,
  )
  const oversized = { name: 'proof.pdf', size: 10_485_761 }
  assert.throws(() => validateAttachmentFile(oversized), /10 MiB/)
})

test('stages self and administrator attachments without a request ID', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      if (calls.length % 2 === 1) {
        return transport({
          id: attachmentId,
          submissionToken: `wlat1.${attachmentId}.${'A'.repeat(43)}`,
          expiresAt: timestamp,
        }, 201)
      }
      return transport({
        id: attachmentId,
        fileName: 'proof.pdf',
        contentType: 'application/pdf',
        sizeBytes: 16,
        sha256: '0'.repeat(64),
        uploadedAt: timestamp,
        expiresAt: timestamp,
      }, 201)
    },
  }
  const file = new File(['%PDF-1.7\n%%EOF'], 'proof.pdf', { type: 'application/pdf' })
  await uploadStagedLeaveAttachment(authentication, null, null, file)
  await uploadStagedLeaveAttachment(authentication, branchId, requestId, file)
  assert.deepEqual(calls[0].options.json, {})
  assert.equal(calls[0].options.headers, undefined)
  assert.deepEqual(calls[2].options.json, { employeeId: requestId })
  assert.deepEqual(calls[2].options.headers, { 'X-Workloop-Branch-ID': branchId })
})

test('requests an authorized download without retaining the signed URL', async () => {
  const calls = []
  const authentication = {
    async request(path, options) {
      calls.push({ path, options })
      return transport({ url: 'http://127.0.0.1:28000/signed', expiresAt: timestamp })
    },
  }

  const signed = await createLeaveAttachmentDownload(
    authentication, null, attachmentId,
  )

  assert.equal(signed.url, 'http://127.0.0.1:28000/signed')
  assert.equal(calls[0].options.headers, undefined)
  assert.equal(calls[0].options.method, 'POST')
})
