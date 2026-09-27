import assert from 'node:assert/strict'
import test from 'node:test'

import { sanitizeEvidence, sanitizeEvidenceRecord } from '../scripts/phase-14e-evidence.mjs'

const safeRecord = {
  observedAt: '2026-09-27T12:00:00Z',
  signalId: 'scanner-terminal',
  component: 'file-scanner',
  status: 'failed',
  count: 1,
  operator: 'synthetic-incident-operator',
}

test('keeps only explicit safe evidence fields', () => {
  assert.deepEqual(sanitizeEvidence([safeRecord]), [safeRecord])
})

for (const [field, value] of [
  ['token', 'synthetic-token'],
  ['status', 'Bearer abc'],
  ['resourceId', 'postgresql://user:password@db/workloop'],
  ['safeKeySuffix', 'https://objects.invalid/file?signature=abc'],
  ['documentContent', 'synthetic document text'],
]) {
  test(`rejects protected evidence in ${field}`, () => {
    assert.throws(() => sanitizeEvidenceRecord({ ...safeRecord, [field]: value }), /not allowed|not safe/)
  })
}

test('requires time, signal, and named operator fields', () => {
  assert.throws(() => sanitizeEvidenceRecord({ component: 'api' }), /requires/)
})
