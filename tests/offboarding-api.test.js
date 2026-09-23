import assert from 'node:assert/strict'
import test from 'node:test'

import { parseChecklist, parsePreview } from '../migration/src/offboardingApi.js'

const id = '12345678-1234-4234-8234-123456789abc'
const now = '2026-09-23T00:00:00.000Z'

test('offboarding response parsers accept exact settlement contracts', () => {
  const checklist = parseChecklist({
    id, employeeId: id, employeeName: 'Synthetic clinician', employmentStatus: 'Active',
    status: 'in_progress', visaCancellationStatus: 'not_started', visaCancellationDate: null,
    finalSettlementId: null, createdAt: now, updatedAt: now, completedAt: null,
    tasks: [{
      id, taskName: 'Return company property', completed: false, completedAt: null,
      notes: '', sortOrder: 0, source: 'template', templateId: id, updatedAt: now,
    }],
  })
  assert.equal(checklist.tasks[0].source, 'template')

  const preview = parsePreview({
    policyVersion: '1.0.0', policyDigest: `sha256:${'a'.repeat(64)}`,
    sourceDigest: `sha256:${'b'.repeat(64)}`, sourceCapturedAt: now,
    serviceDays: '2190', gratuityDays: '135.0000', leaveDays: '7.50',
    finalSalary: '12500.00', leaveEncashment: '2500.00', gratuity: '45000.00',
    noticePay: '0.00', otherEarnings: '0.00', advanceDeduction: '333.34',
    assetDeduction: '0.00', noticeDeduction: '0.00', otherDeductions: '0.00',
    grossAmount: '60000.00', totalDeductions: '333.34', netAmount: '59666.66',
  })
  assert.equal(preview.netAmount, '59666.66')
})
