import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('shares the historical retained-source layout across administrator, manager, and employee modules', async () => {
  const [administrator, manager, employee, css] = await Promise.all([
    readFile(new URL('../src/AdministratorPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/ManagerPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/EmployeePortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/index.css', import.meta.url), 'utf8'),
  ])

  assert.match(administrator, /className="portal-route administrator-route"/)
  assert.match(manager, /className="portal-route manager-route"/)
  assert.match(employee, /className="portal-route employee-route"/)
  assert.match(css, /Exact historical portal parity/)
  assert.match(css, /\.portal-route \.tabs/)
  assert.match(css, /\.portal-route \.expense-form/)
  assert.match(css, /\.portal-route \.table-wrap/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route \{[\s\S]*?gap: 16px;[\s\S]*?margin: 0;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal\[data-portal-role\] \.page-body \{[\s\S]*?padding: 20px 12px 28px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route \.tab-btn[\s\S]*?padding: 10px 18px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route th \{[\s\S]*?font-size: 11\.5px;/)
  assert.match(css, /Exact historical portal parity[\s\S]*?\.portal-route input,[\s\S]*?padding: 9px 13px;/)
  assert.match(css, /data-portal-role='manager'[\s\S]*height: 62px/)
})
