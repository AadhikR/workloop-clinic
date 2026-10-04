import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { changePayrollRouting } from '../src/payrollRoutingApi.js'
import { readFinancialCollection } from '../src/financialCollections.js'

test('financial summaries traverse every page and reject repeated records', async () => {
  const calls = []
  const result = await readFinancialCollection(async (query) => {
    calls.push(query)
    return { items: [{ id: query.cursor ? 'two' : 'one' }], page: { nextCursor: query.cursor ? null : 'next' } }
  })
  assert.deepEqual(result.items.map((item) => item.id), ['one', 'two'])
  assert.deepEqual(calls, [{ limit: 100 }, { limit: 100, cursor: 'next' }])
  await assert.rejects(readFinancialCollection(async () => ({ items: [{ id: 'one' }], page: { nextCursor: 'next' } })), /collection changed/)
})

test('financial summaries reject a repeated cursor even without duplicate rows', async () => {
  let count = 0
  await assert.rejects(readFinancialCollection(async () => ({ items: [{ id: String(count++) }], page: { nextCursor: 'next' } })), /pagination repeated/)
})

test('routing command rejects malformed values before a request', async () => {
  let called = false
  await assert.rejects(changePayrollRouting({ request() { called = true } }, {}, 'bad', 'bad'), /nine-digit/)
  assert.equal(called, false)
})

test('restored report, dashboard, and financial workflows keep current authority', async () => {
  const files = await Promise.all(['Reports', 'Dashboards', 'Tasks', 'NotificationBell', 'Payroll', 'WpsNafis', 'Advances', 'Expenses'].map((name) => readFile(new URL(`../src/${name}.jsx`, import.meta.url), 'utf8')))
  assert.doesNotMatch(files.join('\n'), /utils\/storage|notificationStorage|payrollCalculator/)
  assert.match(files[0], /Report family/)
  assert.match(files[1], /Setup checklist/)
  assert.match(files[2], /aria-expanded/)
  assert.match(files[3], /Dialog/)
  assert.match(files[4], /PayrollRoutingDialog/)
  assert.match(files[5], /SIF preview/)
})
