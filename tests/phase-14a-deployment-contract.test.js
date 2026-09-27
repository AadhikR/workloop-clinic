import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  cataloguePath,
  contractPath,
  externalFactsPath,
  goldenPath,
  inspectPhase14Contract,
  inventoryPath,
  validatePhase14Catalogue,
} from '../scripts/verify-phase-14a-contract.mjs'

function read(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function fixture() {
  return {
    catalogue: JSON.parse(read(cataloguePath)),
    documents: {
      inventory: read(inventoryPath),
      contract: read(contractPath),
      golden: read(goldenPath),
      external: read(externalFactsPath),
    },
  }
}

test('accepts the complete Phase 14A deployment and operations contract', () => {
  const report = inspectPhase14Contract()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 57)
  assert.equal(report.goldenCases, 38)
  assert.equal(report.externalFacts, 12)
  assert.equal(report.owners, 7)
})

test('rejects duplicate inventory IDs', () => {
  const { catalogue, documents } = fixture()
  catalogue.inventory.push(structuredClone(catalogue.inventory[0]))
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('inventory contains duplicate IDs')))
})

test('rejects a missing or invalid later-part owner', () => {
  const { catalogue, documents } = fixture()
  for (const entry of catalogue.inventory) {
    if (entry.owner === '14F') entry.owner = '14E'
  }
  catalogue.inventory[0].owner = '14Z'
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid owner 14Z')))
  assert.ok(report.errors.some((error) => error.includes('14F owns no inventory item')))
})

test('rejects an unknown action or evidence class', () => {
  const { catalogue, documents } = fixture()
  catalogue.inventory[0].action = 'guess later'
  catalogue.inventory[1].evidenceClasses = ['completion-record']
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid action guess later')))
  assert.ok(report.errors.some((error) => error.includes('invalid evidence class completion-record')))
})

test('rejects rollback order that is not the reverse part order', () => {
  const { catalogue, documents } = fixture()
  catalogue.rollbackOrder = [...catalogue.rollbackOrder].reverse()
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.includes('phase rollback order is not the exact reverse part order'))
})

test('rejects cost line items that do not equal the fixed monthly estimate', () => {
  const { catalogue, documents } = fixture()
  catalogue.contract.costBoundary.monthlyLineItems[0].unitMonthly = 12
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.includes('fixed monthly estimate does not equal its line items'))
})

test('rejects guessed external facts and prose coverage gaps', () => {
  const { catalogue, documents } = fixture()
  catalogue.externalFacts[0].status = 'assumed'
  documents.external = documents.external.replace('| `EXT-012` |', '| `EXT-999` |')
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid status assumed')))
  assert.ok(report.errors.some((error) => error.includes('external-fact record is missing: EXT-012')))
  assert.ok(report.errors.some((error) => error.includes('external-fact record has unexpected IDs: EXT-999')))
})

test('rejects a changed schema head contract', () => {
  const { catalogue, documents } = fixture()
  catalogue.contract.artifactIdentity.schemaHead = 'changed'
  const report = validatePhase14Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.includes('artifact schema head differs from catalogue head'))
})
