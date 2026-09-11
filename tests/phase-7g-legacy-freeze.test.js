import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('freezes legacy employee lifecycle and portal-role access', async () => {
  const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  const profiles = await readFile(
    new URL('../src/utils/profileStorage.js', import.meta.url),
    'utf8',
  )
  const manager = await readFile(
    new URL('../src/components/EmployeeManager.jsx', import.meta.url),
    'utf8',
  )
  const modal = await readFile(
    new URL('../src/components/EmployeeModal.jsx', import.meta.url),
    'utf8',
  )

  assert.match(
    storage,
    /export async function archiveEmployee\([^)]*\) \{[\s\S]*?throw new Error\('Employee lifecycle changes have moved to the migration employee directory\.'\);[\s\S]*?\n\}/,
  )
  assert.match(
    storage,
    /export async function addJobHistoryEntry\([^)]*\) \{[\s\S]*?throw new Error\('Employee job history is written only by migration employee workflows\.'\);[\s\S]*?\n\}/,
  )
  for (const name of ['getEmployeePortalRole', 'setEmployeePortalRole']) {
    assert.match(
      profiles,
      new RegExp(`export async function ${name}\\([^)]*\\) \\{[\\s\\S]*?throw new Error\\('Employee portal roles have moved to the migration employee directory\\.'\\);[\\s\\S]*?\\n\\}`),
    )
  }
  assert.doesNotMatch(manager, /archiveEmployee\(|addJobHistoryEntry\(/)
  assert.doesNotMatch(modal, /getEmployeePortalRole\(|setEmployeePortalRole\(|addJobHistoryEntry\(/)
})
