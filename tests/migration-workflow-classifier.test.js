import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import test from 'node:test'

const windowsShell = 'C:\\Program Files\\Git\\bin\\sh.exe'
const shell = process.platform === 'win32' && existsSync(windowsShell) ? windowsShell : 'sh'

function classify(...paths) {
  const result = spawnSync(
    shell,
    ['.github/scripts/classify-migration-workflow.sh'],
    {
      cwd: process.cwd(),
      encoding: 'utf8',
      env: { ...process.env, GITHUB_OUTPUT: '' },
      input: `${paths.join('\n')}\n`,
    },
  )
  assert.equal(result.status, 0, result.stderr)
  return Object.fromEntries(
    result.stdout
      .trim()
      .split('\n')
      .map((line) => line.split('=')),
  )
}

test('documentation changes use the lightweight path', () => {
  assert.deepEqual(classify('docs/migration/example.md'), {
    docs_only: 'true',
    backend: 'false',
    frontend: 'false',
    full_stack: 'false',
    database_deep: 'false',
    database_history: 'false',
    auth_deep: 'false',
  })
})

test('repository changes keep current database security checks without history replay', () => {
  const result = classify('backend/app/repositories/employees.py')
  assert.equal(result.backend, 'true')
  assert.equal(result.frontend, 'true')
  assert.equal(result.full_stack, 'true')
  assert.equal(result.database_deep, 'true')
  assert.equal(result.database_history, 'false')
})

test('append-only revisions skip the historical assertions', () => {
  const result = classify('A\tbackend/alembic/versions/example_revision.py')
  assert.equal(result.database_deep, 'true')
  assert.equal(result.database_history, 'false')
})

test('edits to existing revisions request the historical assertions', () => {
  for (const status of ['M', 'D', 'R100\tbackend/alembic/versions/old_name.py']) {
    const result = classify(`${status}\tbackend/alembic/versions/example_revision.py`)
    assert.equal(result.database_deep, 'true', status)
    assert.equal(result.database_history, 'true', status)
  }
})

test('migration controls request the historical assertions', () => {
  for (const path of [
    '.github/workflows/migration-foundation.yml',
    '.github/scripts/classify-migration-workflow.sh',
    'backend/alembic/env.py',
    'scripts/verify-phase-5g-chain.sh',
  ]) {
    const result = classify(path)
    assert.equal(result.full_stack, 'true', path)
    assert.equal(result.database_deep, 'true', path)
    assert.equal(result.database_history, 'true', path)
  }
})

test('workflow changes exercise authentication setup idempotence', () => {
  const result = classify('.github/workflows/migration-foundation.yml')
  assert.equal(result.auth_deep, 'true')
})
