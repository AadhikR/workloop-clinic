import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('shares the polished portal layout across administrator, manager, and employee modules', async () => {
  const [administrator, manager, employee, css] = await Promise.all([
    readFile(new URL('../src/AdministratorPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/ManagerPortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/EmployeePortal.jsx', import.meta.url), 'utf8'),
    readFile(new URL('../src/index.css', import.meta.url), 'utf8'),
  ])

  assert.match(administrator, /className="portal-route administrator-route"/)
  assert.match(manager, /className="portal-route manager-route"/)
  assert.match(employee, /className="portal-route employee-route"/)
  assert.match(css, /Authenticated portal visual refinement/)
  assert.match(css, /\.portal-route \.tabs/)
  assert.match(css, /\.portal-route \.expense-form/)
  assert.match(css, /\.portal-route \.table-wrap/)
  assert.match(css, /data-portal-role='manager'[\s\S]*height: 62px/)
})
