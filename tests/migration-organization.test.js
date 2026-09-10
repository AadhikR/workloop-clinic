import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createBranchSelection,
  readAllBranches,
  readBranch,
  readBranches,
  readCompany,
  readEmployer,
} from '../migration/src/organizationApi.js'

const companyId = '3afbf0a0-9642-4d44-9884-e9654983eb9b'
const dubaiId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const sharjahId = '07186a4f-e0df-4799-916f-b524503743a4'

const company = {
  id: companyId,
  name: 'Horizon Clinic',
  sector: 'Healthcare',
  nafisQuotaPercent: '2.00',
  enableNafis: true,
  createdAt: '2026-09-09T12:30:45.123Z',
  updatedAt: '2026-09-09T12:30:45.123Z',
}

const branch = {
  id: dubaiId,
  name: 'Dubai',
  molEmployerId: 'MOL-001',
  defaultBankRoutingCode: 'BANK-A',
  address: 'Synthetic address',
  contactEmail: 'dubai@example.test',
  defaultSalaryDay: 25,
  workLocationType: 'mainland',
  freeZoneName: '',
  logoUrl: '',
  enableStaffingRules: true,
  enableBiometricImport: false,
  createdAt: '2026-09-09T12:30:45.123Z',
  updatedAt: '2026-09-09T12:30:45.123Z',
}

function client(response) {
  const requests = []
  return {
    requests,
    async request(path, options) {
      requests.push([path, options])
      return response
    },
  }
}

test('parses exact camelCase company, employer, and branch projections', async () => {
  const companyClient = client({ data: company })
  assert.deepEqual(await readCompany(companyClient), company)

  const employer = {
    companyName: 'Horizon Clinic',
    branchName: 'Dubai',
    branchContactEmail: 'dubai@example.test',
    branchAddress: 'Synthetic address',
    workLocationType: 'mainland',
    freeZoneName: '',
    logoUrl: '',
  }
  assert.deepEqual(await readEmployer(client({ data: employer })), employer)

  const response = {
    data: [branch],
    page: { limit: 50, nextCursor: null, hasMore: false },
  }
  assert.deepEqual(await readBranches(client(response)), response)
})

test('rejects leaked, missing, snake_case, and malformed organization fields', async () => {
  const invalid = [
    { ...company, company_id: companyId },
    { ...company, nafisQuotaPercent: 2 },
    { ...company, createdAt: '2026-09-09T12:30:45Z' },
    { ...branch, companyId },
    { ...branch, workLocationType: 'Mainland' },
    { ...branch, defaultSalaryDay: 32 },
  ]
  for (const data of invalid) {
    const operation = Object.hasOwn(data, 'sector')
      ? readCompany(client({ data }))
      : readBranches(client({ data: [data], page: { limit: 50, nextCursor: null, hasMore: false } }))
    await assert.rejects(operation, /invalid organization response/i)
  }
})

test('forwards cancellation and sends a branch header only for verified detail', async () => {
  const controller = new AbortController()
  const listing = client({
    data: [branch],
    page: { limit: 50, nextCursor: null, hasMore: false },
  })
  await readBranches(listing, { signal: controller.signal, search: 'Dubai' })
  assert.deepEqual(listing.requests, [[
    '/api/v1/branches?search=Dubai',
    { access: 'protected', signal: controller.signal },
  ]])

  const detail = client({ data: branch })
  assert.deepEqual(await readBranch(detail, dubaiId, { signal: controller.signal }), branch)
  assert.deepEqual(detail.requests, [[
    `/api/v1/branches/${dubaiId}`,
    {
      access: 'protected',
      headers: { 'X-Workloop-Branch-ID': dubaiId },
      signal: controller.signal,
    },
  ]])
})

test('loads every branch page before validating a retained selection', async () => {
  const requests = []
  const authentication = {
    async request(path, options) {
      requests.push([path, options])
      if (path === '/api/v1/branches?limit=100') {
        return {
          data: [branch],
          page: { limit: 100, nextCursor: 'next-page', hasMore: true },
        }
      }
      return {
        data: [{ ...branch, id: sharjahId, name: 'Sharjah' }],
        page: { limit: 100, nextCursor: null, hasMore: false },
      }
    },
  }

  const branches = await readAllBranches(authentication)
  assert.deepEqual(branches.map(({ id }) => id), [dubaiId, sharjahId])
  assert.deepEqual(requests.map(([path]) => path), [
    '/api/v1/branches?limit=100',
    '/api/v1/branches?limit=100&cursor=next-page',
  ])
})

test('keeps a valid tab selection and never falls back to the first branch', () => {
  const storage = new Map([["workloop.branchId", sharjahId]])
  const sessionStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  }
  const selection = createBranchSelection({ sessionStorage })
  const branches = [{ ...branch }, { ...branch, id: sharjahId, name: 'Sharjah' }]

  assert.deepEqual(selection.validate(branches), branches[1])
  assert.equal(selection.currentId(), sharjahId)

  selection.clear()
  assert.equal(selection.validate(branches), null)
  assert.equal(selection.currentId(), null)
})

test('clears stale, malformed, and inaccessible selections and opens the chooser', () => {
  for (const stored of ['not-a-uuid', sharjahId, null]) {
    const storage = new Map(stored === null ? [] : [["workloop.branchId", stored]])
    const selection = createBranchSelection({
      sessionStorage: {
        getItem: (key) => storage.get(key) ?? null,
        setItem: (key, value) => storage.set(key, value),
        removeItem: (key) => storage.delete(key),
      },
    })
    assert.equal(selection.validate([branch]), null)
    assert.equal(selection.currentId(), null)
    assert.equal(selection.needsChooser(), true)
  }
})

test('accepts only an accessible explicit choice', () => {
  const storage = new Map()
  const selection = createBranchSelection({
    sessionStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    },
  })

  assert.equal(selection.select(sharjahId, [branch]), null)
  assert.equal(selection.currentId(), null)
  assert.deepEqual(selection.select(dubaiId, [branch]), branch)
  assert.equal(selection.currentId(), dubaiId)
})
