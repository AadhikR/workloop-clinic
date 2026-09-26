import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseAppraisal,
  parseAppraisalCycle,
  parseIncident,
} from '../src/appraisalsIncidentsApi.js'

const id = '12345678-1234-4234-8234-123456789abc'
const instant = '2026-09-23T12:00:00.000Z'

function appraisal() {
  return {
    id, cycleId: id, cycleName: 'Synthetic cycle', reviewFrom: '2026-01-01',
    reviewTo: '2026-12-31', employeeId: id, employeeName: 'Synthetic clinician',
    templateVersion: 'clinic-v1', overallRating: null, status: 'pending',
    reviewerComments: '', developmentPlan: '', reviewedAt: null,
    reviewedByAppUserId: null, createdAt: instant, updatedAt: instant,
    sections: [{
      id, sectionName: 'Clinical Competency', weight: '2.00', rating: null,
      comments: '', sortOrder: 10, updatedAt: instant,
    }],
  }
}

test('appraisal and cycle parsers enforce exact migration projections', () => {
  assert.equal(parseAppraisal(appraisal()).employeeName, 'Synthetic clinician')
  const cycle = {
    id, name: 'Synthetic cycle', reviewFrom: '2026-01-01', reviewTo: '2026-12-31',
    status: 'active', closedByAppUserId: null, closedAt: null, createdAt: instant,
    updatedAt: instant, appraisals: [appraisal()],
  }
  assert.equal(parseAppraisalCycle(cycle).appraisals.length, 1)
  assert.throws(() => parseAppraisal({ ...appraisal(), storagePath: 'forbidden' }))
})

test('incident parser requires the complete retained record projection', () => {
  const incident = {
    id, incidentDate: '2026-09-23', incidentTime: null, location: 'Synthetic ward',
    department: 'Clinical', incidentType: 'medication_error', severity: 'critical',
    description: 'Synthetic incident', reportedById: null, reportedByName: null,
    involvedEmpId: null, involvedEmployeeName: null, immediateAction: '', rootCause: '',
    correctiveAction: '', status: 'open', closedDate: null, closedByAppUserId: null,
    notes: '', createdAt: instant, updatedAt: instant,
  }
  assert.equal(parseIncident(incident).status, 'open')
  assert.throws(() => parseIncident({ ...incident, severity: 'unknown' }))
})
