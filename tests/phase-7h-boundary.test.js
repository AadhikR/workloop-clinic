import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { assertValidCutoverRecord } from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const contractPath = path.join(
  repositoryDirectory,
  'docs',
  'migration',
  'phase-7',
  'PART_7A_DOMAIN_CONTRACT.md',
)
const recordDirectory = path.join(
  repositoryDirectory,
  'docs',
  'migration',
  'phase-7',
  'cutover-records',
)
const recordNames = [
  'departments.json',
  'employee-administration.json',
  'employee-directory.json',
  'employee-lifecycle.json',
  'organization-administration.json',
  'organization-context.json',
  'staffing-rules.json',
]
const featureIds = [
  'phase7-departments',
  'phase7-employee-administration',
  'phase7-employee-directory',
  'phase7-employee-lifecycle',
  'phase7-organization-administration',
  'phase7-organization-context',
  'phase7-staffing-rules',
]
const rollbackSteps = [
  'freeze-migration-writes',
  'restore-legacy-writes',
  'restore-legacy-reads',
  'verify-authority',
  'verify-data',
]

function readRecord(name) {
  return JSON.parse(readFileSync(path.join(recordDirectory, name), 'utf8'))
}

function readText(file) {
  return readFileSync(file, 'utf8').replaceAll('\r\n', '\n')
}

function contractDependencyIds() {
  const contract = readText(contractPath)
  const section = contract
    .split('### Stable dependency IDs\n', 2)[1]
    .split('### Legacy operation inventory\n', 1)[0]
  return [...section.matchAll(/^\| `([^`]+)` \|/gm)].map((match) => match[1]).sort()
}

function locatorPaths(locator) {
  return locator
    .split(/, and |, | and /)
    .map((value) => value.trim())
    .filter(Boolean)
}

test('accounts for every Phase 7 dependency and replacement locator', () => {
  const records = recordNames.map(readRecord)
  const declaredIds = records.flatMap((record) => (
    record.dependencies.declared.map((dependency) => dependency.id)
  ))
  assert.deepEqual([...new Set(declaredIds)].sort(), contractDependencyIds())

  const replacements = records.flatMap((record) => record.dependencies.declared)
    .filter((dependency) => dependency.id.startsWith('planned-'))
  assert.equal(replacements.length, 7)
  for (const replacement of replacements) {
    assert.doesNotMatch(replacement.locator, /^synthetic:\/\//)
    for (const locator of locatorPaths(replacement.locator)) {
      assert.equal(
        existsSync(path.join(repositoryDirectory, locator)),
        true,
        `${replacement.id} names missing implementation ${locator}`,
      )
    }
  }
})

test('keeps all seven Phase 7 cutovers completed and single-writer', () => {
  const records = recordNames.map(readRecord)
  assert.deepEqual(records.map((record) => record.featureId).sort(), featureIds)

  for (const record of records) {
    assertValidCutoverRecord(record, { repositoryDirectory })
    assert.equal(record.status.current, 'completed')
    assert.deepEqual(record.authority.writableSystems, [record.authority.writeSystem])
    assert.notEqual(record.freeze.read.system, record.authority.readSystem)
    assert.notEqual(record.freeze.write.system, record.authority.writeSystem)
    assert.deepEqual(record.rollback.steps.map((step) => step.id), rollbackSteps)
  }
})
