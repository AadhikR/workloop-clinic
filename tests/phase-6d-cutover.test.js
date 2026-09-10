import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  CutoverRecordValidationError,
  assertValidCutoverRecord,
  validateCutoverRecord,
} from '../scripts/cutover-record-validator.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const templatePath = path.join(repositoryDirectory, 'docs', 'migration', 'phase-6', 'cutover-record.template.json')
const negativeFixturePath = path.join(repositoryDirectory, 'tests', 'fixtures', 'phase-6d', 'negative-fixtures.json')

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'))
}

function mutate(record, fixture) {
  const clone = structuredClone(record)
  const parts = fixture.path.split('/').slice(1)
  const key = parts.pop()
  const parent = parts.reduce((value, part) => value[part], clone)
  if (fixture.operation === 'remove') {
    if (Array.isArray(parent)) parent.splice(Number(key), 1)
    else delete parent[key]
  } else if (fixture.operation === 'replace') {
    parent[key] = fixture.value
  } else {
    throw new Error(`Unsupported fixture operation: ${fixture.operation}`)
  }
  return clone
}

test('accepts the complete synthetic cutover declaration', async () => {
  const record = await readJson(templatePath)
  assert.deepEqual(validateCutoverRecord(record, { repositoryDirectory }), [])
  assert.equal(assertValidCutoverRecord(record, { repositoryDirectory }), record)
})

test('rejects every incomplete or ambiguous synthetic fixture', async (context) => {
  const record = await readJson(templatePath)
  const fixtures = await readJson(negativeFixturePath)

  for (const fixture of fixtures) {
    await context.test(fixture.name, () => {
      const invalidRecord = mutate(record, fixture)
      const errors = validateCutoverRecord(invalidRecord, { repositoryDirectory })
      assert.ok(
        errors.some(({ code }) => code === fixture.expectedCode),
        `Expected ${fixture.expectedCode}, received ${errors.map(({ code }) => code).join(', ')}`,
      )
      assert.throws(
        () => assertValidCutoverRecord(invalidRecord, { repositoryDirectory }),
        CutoverRecordValidationError,
      )
    })
  }
})

test('rejects a repeated application-owned identity', async () => {
  const record = await readJson(templatePath)
  record.identityMapping.mappings[1].applicationUserId = record.identityMapping.mappings[0].applicationUserId
  const errors = validateCutoverRecord(record, { repositoryDirectory })
  assert.ok(errors.some(({ code }) => code === 'identityMapping.oneToOne'))
})

test('rejects an impossible status transition', async () => {
  const record = await readJson(templatePath)
  record.status.history.push({
    state: 'completed',
    at: '2026-09-07T09:15:00Z',
    reason: 'Synthetic invalid transition.',
  })
  record.status.current = 'completed'
  record.status.changedAt = '2026-09-07T09:15:00Z'
  const errors = validateCutoverRecord(record, { repositoryDirectory })
  assert.ok(errors.some(({ code }) => code === 'status.history'))
})

test('accepts a completed read-only cutover with the legacy writer retained', async () => {
  const record = await readJson(templatePath)
  record.status.history.push({
    state: 'active-cutover',
    at: '2026-09-07T09:15:00Z',
    reason: 'Synthetic readers entered cutover.',
  })
  record.status.history.push({
    state: 'completed',
    at: '2026-09-07T09:30:00Z',
    reason: 'Synthetic reader verification passed.',
  })
  record.status.current = 'completed'
  record.status.changedAt = '2026-09-07T09:30:00Z'
  record.authority.readSystem = 'migration-fastapi'
  record.freeze.read.system = 'legacy-supabase'

  assert.deepEqual(validateCutoverRecord(record, { repositoryDirectory }), [])
})

test('rejects an active cutover that leaves both authorities on legacy', async () => {
  const record = await readJson(templatePath)
  record.status.history.push({
    state: 'active-cutover',
    at: '2026-09-07T09:15:00Z',
    reason: 'Synthetic cutover did not change authority.',
  })
  record.status.current = 'active-cutover'
  record.status.changedAt = '2026-09-07T09:15:00Z'

  const errors = validateCutoverRecord(record, { repositoryDirectory })
  assert.ok(errors.some(({ code }) => code === 'status.authority'))
})

test('enforces the complete cutover record structure', async (context) => {
  const template = await readJson(templatePath)
  const cases = [
    {
      name: 'missing required root property',
      mutate(record) { delete record.rollback },
      expectedCode: 'schema.$.required.rollback',
    },
    {
      name: 'wrong schema discriminator',
      mutate(record) { record.$schema = './another-schema.json' },
      expectedCode: 'schema.$.$schema.const',
    },
    {
      name: 'extra root property',
      mutate(record) { record.unapproved = true },
      expectedCode: 'schema.$.additionalProperties.unapproved',
    },
    {
      name: 'extra nested property',
      mutate(record) { record.authority.unapproved = true },
      expectedCode: 'schema.$.authority.additionalProperties.unapproved',
    },
  ]

  for (const item of cases) {
    await context.test(item.name, () => {
      const record = structuredClone(template)
      item.mutate(record)
      const errors = validateCutoverRecord(record, { repositoryDirectory })
      assert.ok(
        errors.some(({ code }) => code === item.expectedCode),
        `Expected ${item.expectedCode}, received ${errors.map(({ code }) => code).join(', ')}`,
      )
    })
  }
})
