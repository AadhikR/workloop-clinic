import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  cataloguePath,
  contractPath,
  goldenPath,
  inspectPhase15Contract,
  inventoryPath,
  planPath,
  validatePhase15Catalogue,
} from '../scripts/verify-phase-15a-contract.mjs'

function read(filePath) {
  return readFileSync(filePath, 'utf8').replaceAll('\r\n', '\n')
}

function fixture() {
  return {
    catalogue: JSON.parse(read(cataloguePath)),
    documents: {
      plan: read(planPath),
      inventory: read(inventoryPath),
      contract: read(contractPath),
      golden: read(goldenPath),
    },
  }
}

test('accepts the complete Phase 15A portal integration contract', () => {
  const report = inspectPhase15Contract()
  assert.deepEqual(report.errors, [])
  assert.equal(report.inventory, 52)
  assert.equal(report.clients, 31)
  assert.equal(report.routes, 29)
  assert.equal(report.fileFlows, 6)
  assert.equal(report.gaps, 8)
  assert.equal(report.goldenCases, 42)
  assert.equal(report.owners, 7)
})

test('rejects duplicate inventory IDs', () => {
  const { catalogue, documents } = fixture()
  catalogue.inventory.push(structuredClone(catalogue.inventory[0]))
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('inventory contains duplicate IDs')))
})

test('rejects a missing or invalid later-part owner', () => {
  const { catalogue, documents } = fixture()
  for (const entry of catalogue.inventory) if (entry.owner === '15G') entry.owner = '15F'
  catalogue.inventory[0].owner = '15Z'
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid owner 15Z')))
  assert.ok(report.errors.some((error) => error.includes('15G owns no inventory item')))
})

test('rejects an unknown action or evidence class', () => {
  const { catalogue, documents } = fixture()
  catalogue.inventory[0].action = 'invent product'
  catalogue.inventory[1].evidenceClasses = ['guess']
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid action invent product')))
  assert.ok(report.errors.some((error) => error.includes('invalid evidence class guess')))
})

test('rejects rollback order that is not reverse part order', () => {
  const { catalogue, documents } = fixture()
  catalogue.rollbackOrder = [...catalogue.rollbackOrder].reverse()
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.includes('phase rollback order is not the exact reverse part order'))
})

test('rejects an invented client endpoint', () => {
  const { catalogue, documents } = fixture()
  catalogue.clientContracts[0].sourceMarkers[0] = '/api/v1/invented'
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invented or missing endpoint marker')))
})

test('rejects an unknown role and duplicate browser path', () => {
  const { catalogue, documents } = fixture()
  catalogue.routeContracts[0].roles = ['super-admin']
  catalogue.routeContracts[1].path = catalogue.routeContracts[0].path
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid role super-admin')))
  assert.ok(report.errors.some((error) => error.includes('route paths contains duplicate IDs')))
})

test('rejects a route assigned to the wrong portal part', () => {
  const { catalogue, documents } = fixture()
  const route = catalogue.routeContracts.find((entry) => entry.path === '/manager')
  route.owner = '15C'
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('invalid route owner 15C')))
})

test('rejects a file flow without an authorized download source', () => {
  const { catalogue, documents } = fixture()
  catalogue.fileFlows[0].downloadSource = null
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('has no download source')))
})

test('rejects unowned prose inventory and golden-case drift', () => {
  const { catalogue, documents } = fixture()
  documents.inventory = documents.inventory.replace('| `P15-SHL-001` |', '| `P15-SHL-999` |')
  documents.golden = documents.golden.replace('| `15A-GC-001` |', '| `15A-GC-999` |')
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.some((error) => error.includes('prose inventory is missing: P15-SHL-001')))
  assert.ok(report.errors.some((error) => error.includes('prose golden cases is missing: 15A-GC-001')))
})

test('rejects schema and deployment boundary changes', () => {
  const { catalogue, documents } = fixture()
  catalogue.alembicHead = 'changed'
  catalogue.deploymentBoundary.automaticDeployment = true
  const report = validatePhase15Catalogue(catalogue, documents, { checkRepository: false })
  assert.ok(report.errors.includes('deployment boundary is invalid'))
})
