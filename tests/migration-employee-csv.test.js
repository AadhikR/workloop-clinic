import assert from 'node:assert/strict'
import test from 'node:test'

import { parseEmployeeCsv } from '../migration/src/employeeCsv.js'

test('parses the Phase 7F employee CSV contract for preview', () => {
  const preview = parseEmployeeCsv([
    'Emp No,Name,MOL ID,Bank Name,Bank Routing Code,IBAN,Basic Salary,Allowance',
    'E-001,Synthetic Employee,10003048635715,Synthetic Bank,123456789,AE000000000000000000001,10000,250',
  ].join('\n'))

  assert.deepEqual(preview.diagnostics, [])
  assert.deepEqual(preview.rows, [{
    rowNumber: 2,
    empNo: 'E-001',
    name: 'Synthetic Employee',
    molId: '10003048635715',
    bankName: 'Synthetic Bank',
    bankRoutingCode: '123456789',
    iban: 'AE000000000000000000001',
    basicSalary: '10000.00',
    allowance: '250.00',
  }])
})

test('returns stable row diagnostics and enforces the file limit', () => {
  const invalid = parseEmployeeCsv([
    'Emp No,Name,MOL ID,Bank Name,Bank Routing Code,IBAN,Basic Salary,Allowance',
    ',,abc,,12,GB00,not-money,0',
  ].join('\n'))
  assert.deepEqual(invalid.diagnostics.map(({ rowNumber, field }) => [rowNumber, field]), [
    [2, 'bankRoutingCode'],
    [2, 'basicSalary'],
    [2, 'empNo'],
    [2, 'iban'],
    [2, 'molId'],
    [2, 'name'],
  ])

  const oversized = parseEmployeeCsv('x'.repeat(1_048_577))
  assert.equal(oversized.diagnostics[0].message, 'CSV file exceeds 1 MiB')
  assert.deepEqual(oversized.rows, [])
})
