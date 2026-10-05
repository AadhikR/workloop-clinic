import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = (name) => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8')

test('shared controls retain readable colors and financial route headings', () => {
  const text = source('portal-ui.css')
  assert.match(text, /sidebar-signout\) \{ color: #94a3b8;/)
  assert.match(text, /tab-btn\[aria-selected='true'\] \{ color: #1d4ed8;/)
  assert.match(text, /data-theme='dark'.*aria-selected='true'.*color: #93c5fd;/)
  assert.match(text, /:has\([^\n]*\.payroll[^\n]*\) > \.portal-header \{ display: block;/)
})

test('assets retain server commands inside historical register and dialogs', () => {
  const text = source('DevelopmentAssets.jsx')
  for (const label of ['Asset Register', 'Assignment History', 'Under Repair', 'Assign asset', 'Return asset']) assert.ok(text.includes(label), label)
  assert.ok(text.includes('FormDialog'))
  assert.ok(text.includes('EmployeePicker'))
  assert.ok(!text.includes("prompt('Employee ID')"))
  for (const command of ['assignAsset', 'returnAsset', 'saveAsset', 'changeAssetStatus']) assert.ok(text.includes(command))
})

test('development areas use scoped tabs and dialog forms', () => {
  const text = source('DevelopmentAssets.jsx')
  for (const name of ['Training', 'Certifications', 'CME']) assert.ok(text.includes(name))
  assert.ok(text.includes("tab === 'cme'"))
  assert.ok(text.includes('showTrainingForm'))
  assert.ok(text.includes('showCertificationForm'))
})

test('departments expose historical views and inline editing', () => {
  const text = source('DepartmentManager.jsx')
  for (const name of ['Organization Chart', 'Staffing Rules', 'Expand all', 'Collapse all', 'New Department']) assert.ok(text.includes(name), name)
  assert.ok(text.includes('InlineEditor'))
})

test('appraisals and incidents keep action forms inside dialogs', () => {
  const text = source('AppraisalsIncidents.jsx')
  assert.ok(text.includes('FormDialog'))
  assert.ok(!text.includes('globalThis.prompt'))
  assert.ok(text.includes('cycle.status'))
  assert.ok(text.includes('StatusPill'))
})
