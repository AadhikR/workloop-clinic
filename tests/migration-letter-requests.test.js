import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseLetterRequest,
  parsePrintSource,
  validateSubmission,
} from '../src/letterRequestsApi.js'

const id = '12345678-1234-4234-8234-123456789abc'
const instant = '2026-09-23T12:00:00.000Z'

function request() {
  return {
    id, employeeId: id, employeeName: 'Synthetic clinician', jobTitle: 'Clinician',
    department: 'Clinical', employmentStartDate: '2024-01-01', branchName: 'Synthetic branch',
    requestKind: 'letter', letterType: 'salary_certificate_bank', purpose: 'Emirates NBD',
    status: 'completed', notes: '', rejectionReason: '', requestedAt: instant,
    completedAt: instant, actionedAt: instant, updatedAt: instant,
  }
}

test('safe request projection rejects salary and extra fields', () => {
  assert.equal(parseLetterRequest(request()).employeeName, 'Synthetic clinician')
  assert.throws(() => parseLetterRequest({ ...request(), basicSalary: '10000.00' }))
  assert.throws(() => parseLetterRequest({ ...request(), html: '<p>forbidden</p>' }))
})

test('print source accepts only trusted source fields', () => {
  const source = {
    requestId: id, requestKind: 'letter', letterType: 'salary_certificate_bank',
    purpose: 'Emirates NBD', employeeName: 'Synthetic clinician', jobTitle: 'Clinician',
    department: 'Clinical', employmentStartDate: '2024-01-01', branchName: 'Synthetic branch',
    basicSalary: '10000.00', allowance: '2500.00', requestedAt: instant,
    completedAt: instant,
  }
  assert.equal(parsePrintSource(source).allowance, '2500.00')
  assert.throws(() => parsePrintSource({ ...source, template: 'forbidden' }))
})

test('submission validation matches the approved boundaries', () => {
  assert.equal(validateSubmission({
    requestKind: 'letter', letterType: 'salary_certificate_bank', purpose: 'Emirates NBD',
  }), '')
  assert.equal(validateSubmission({ requestKind: 'custom', subject: 'ABC', details: '12345' }), '')
  assert.match(validateSubmission({ requestKind: 'custom', subject: 'AB', details: '12345' }), /3 to 120/)
  assert.match(validateSubmission({ requestKind: 'custom', subject: 'ABC', details: '1234' }), /5 to 2000/)
})
