import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildAttendanceSummaryReport,
  buildEmiratizationReport,
  buildDocumentExpiryReport,
  buildEOSLiabilityReport,
  buildLeaveBalanceReport,
  buildLeaveUtilizationReport,
  buildOvertimeReport,
  buildSalaryMovementReport,
  buildTurnoverReport,
  buildWpsComplianceReport,
  headcountToRows,
} from '../src/utils/reportUtils.js';

const employee = { id: 'e1', name: 'Aisha', department: 'Clinical', active: true, employmentStatus: 'Active' };

test('headcount export is safe for an empty workforce', () => {
  assert.deepEqual(headcountToRows({ total: 0, byDept: {}, byNat: {}, byType: {}, byGend: {}, byStatus: {} }), []);
});

test('leave usage counts only final HR-approved leave', () => {
  const requests = [
    { employeeId: 'e1', status: 'Approved', startDate: '2026-01-10', daysRequested: 2, leaveTypeCode: 'ANNUAL' },
    { employeeId: 'e1', status: 'ManagerApproved', startDate: '2026-02-10', daysRequested: 5, leaveTypeCode: 'ANNUAL' },
  ];
  const [result] = buildLeaveUtilizationReport([employee], requests, 2026);
  assert.equal(result.totalDays, 2);
  assert.equal(result.requestCount, 1);
});

test('attendance treats worked exception statuses as present and unexplained absence as absent', () => {
  const records = [
    { employeeId: 'e1', date: '2026-08-01', status: 'LATE', totalHours: 8 },
    { employeeId: 'e1', date: '2026-08-02', status: 'EARLY_DEPARTURE', totalHours: 7 },
    { employeeId: 'e1', date: '2026-08-03', status: 'UNEXPLAINED_ABSENCE', totalHours: 0 },
  ];
  const [result] = buildAttendanceSummaryReport([employee], records, '2026-08');
  assert.equal(result.present, 2);
  assert.equal(result.absent, 1);
  assert.equal(result.late, 1);
  assert.equal(result.earlyDep, 1);
});

test('overtime separates approved and pending hours and approved cost', () => {
  const records = [
    { employeeId: 'e1', date: '2026-08-01', overtimeHours: 2, overtimeAmount: 100, overtimeApproved: true },
    { employeeId: 'e1', date: '2026-08-02', overtimeHours: 1.5, overtimeAmount: 75, overtimeApproved: false },
  ];
  const [result] = buildOvertimeReport([employee], records, '2026-08');
  assert.equal(result.approvedHours, 2);
  assert.equal(result.pendingHours, 1.5);
  assert.equal(result.approvedCost, 100);
});

test('document expiry includes profile compliance dates and deduplicates matching uploaded documents', () => {
  const employees = [{
    ...employee,
    visaExpiry: '2020-01-01',
    passportExpiry: '2020-02-01',
    emiratesIdExpiry: '2020-03-01',
    labourCardExpiry: '2020-04-01',
    licenceAuthority: 'DHA',
    licenceExpiry: '2020-05-01',
  }];
  const documents = [
    { employeeId: 'e1', documentType: 'Residence Visa', expiryDate: '2020-01-01' },
    { employeeId: 'e1', documentType: 'BLS Certificate', expiryDate: '2020-06-01' },
  ];
  const result = buildDocumentExpiryReport(employees, documents, 90);
  assert.equal(result.length, 6);
  assert.equal(result.filter(row => row.documentType.includes('Visa')).length, 1);
  assert.equal(result.find(row => row.documentType === 'Visa').source, 'Employee Profile');
  assert.ok(result.some(row => row.documentType === 'Passport'));
  assert.ok(result.some(row => row.documentType === 'Emirates ID'));
  assert.ok(result.some(row => row.documentType === 'Labour Card / Work Permit'));
  assert.ok(result.some(row => row.documentType === 'DHA Professional Licence'));
  assert.ok(result.some(row => row.documentType === 'BLS Certificate' && row.source === 'Uploaded Document'));
});

test('salary movement includes changes throughout the selected end date and excludes orphan rows', () => {
  const history = [
    { employeeId: 'e1', changeType: 'salary_change', changedAt: '2026-08-24T18:30:00Z', oldValue: '1000', newValue: '1200' },
    { employeeId: 'other', changeType: 'salary_change', changedAt: '2026-08-24T12:00:00Z', oldValue: '1', newValue: '2' },
  ];
  assert.equal(buildSalaryMovementReport([employee], history, '2026-08-24', '2026-08-24').length, 1);
});

test('turnover ignores invalid employment dates', () => {
  const result = buildTurnoverReport([{ ...employee, employmentStartDate: '' }], '2026-01-01', '2026-12-31');
  assert.equal(result.joiners.length, 0);
});

test('WPS report classifies failures separately from pending submissions', () => {
  const payrolls = [
    { status: 'generated', wpsStatus: 'confirmed' },
    { status: 'generated', wpsStatus: 'partial_rejection' },
    { status: 'generated', wpsStatus: 'submitted' },
  ];
  const result = buildWpsComplianceReport(payrolls);
  assert.equal(result.confirmed.length, 1);
  assert.equal(result.failed.length, 1);
  assert.equal(result.pending.length, 1);
  assert.equal(result.submitted.length, 3);
});

test('Emiratization uses 2026 headcount tiers and UAE nationality aliases', () => {
  const employees = Array.from({ length: 20 }, (_, index) => ({
    ...employee, id: `e${index}`, nationality: index < 2 ? (index ? 'UAE' : 'Emirati') : 'Other',
  }));
  const result = buildEmiratizationReport(employees, 2);
  assert.equal(result.tier, 'fixed_two');
  assert.equal(result.requiredCount, 2);
  assert.equal(result.compliant, true);
});

test('EOS liability uses canonical first-five-years gratuity calculation', () => {
  const report = buildEOSLiabilityReport([
    { ...employee, employmentStartDate: '2020-01-01', basicSalary: 3000, contractType: 'Unlimited' },
  ], new Date('2026-01-01T00:00:00Z'));
  assert.equal(report.items[0].liability, 13500);
});

test('leave balance report uses persisted accrued and remaining balances', () => {
  const balances = [{
    employeeId: 'e1', leaveYear: 2026, leaveTypeCode: 'ANNUAL', entitledDays: 30,
    accruedDays: 20, usedDays: 5, pendingDays: 2, remaining: 15,
  }];
  const [result] = buildLeaveBalanceReport([employee], balances, 2026);
  assert.equal(result.annualAccrued, 20);
  assert.equal(result.annualRemaining, 15);
  assert.equal(result.hasBalanceData, true);
});