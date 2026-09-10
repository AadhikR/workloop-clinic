import assert from 'node:assert/strict'
import test from 'node:test'

import {
  createBranch,
  createBranchSelection,
  deleteBranch,
  readAllBranches,
  readBranch,
  readBranches,
  readCompany,
  readEmployer,
  readIdempotencyNamespaces,
  readIdempotencyStatus,
  updateBranch,
  updateCompany,
} from '../migration/src/organizationApi.js'
import { createIdempotencyRecoveryStore } from '../migration/src/idempotencyRecovery.js'

const companyId = '3afbf0a0-9642-4d44-9884-e9654983eb9b'
const dubaiId = 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2'
const sharjahId = '07186a4f-e0df-4799-916f-b524503743a4'
const idempotencyKey = '7c000000-0000-4000-8000-000000000002'
const namespace = 'rn1.1234abcd.AAAAAAAAAAAAAAAAAAAAAA'

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

test('sends exact organization mutations, concurrency guards, and cancellation', async () => {
  const controller = new AbortController()
  const companyClient = client({ data: { ...company, name: 'Updated' } })
  await updateCompany(companyClient, {
    name: 'Updated', expectedUpdatedAt: company.updatedAt,
  }, { signal: controller.signal })
  assert.deepEqual(companyClient.requests[0], ['/api/v1/company', {
    access: 'protected', method: 'PATCH',
    json: { name: 'Updated', expectedUpdatedAt: company.updatedAt },
    signal: controller.signal,
  }])

  const createClient = client({
    data: branch, status: 201, location: `/api/v1/branches/${dubaiId}`, replayed: false,
  })
  await createBranch(createClient, { name: 'Dubai' }, {
    idempotencyKey, signal: controller.signal,
  })
  assert.equal(createClient.requests[0][1].headers['Idempotency-Key'], idempotencyKey)

  const updateClient = client({ data: { ...branch, name: 'Dubai Main' } })
  await updateBranch(updateClient, dubaiId, {
    name: 'Dubai Main', expectedUpdatedAt: branch.updatedAt,
  }, { signal: controller.signal })
  assert.equal(updateClient.requests[0][1].headers['X-Workloop-Branch-ID'], dubaiId)

  const deleteClient = client({ data: null, status: 204 })
  await deleteBranch(deleteClient, dubaiId, branch.updatedAt, { signal: controller.signal })
  assert.match(deleteClient.requests[0][0], /expectedUpdatedAt=2026-09-09T12%3A30%3A45.123Z/)
  assert.equal(deleteClient.requests[0][1].signal, controller.signal)
})

test('rejects unknown or malformed organization mutations before transport', async () => {
  const authentication = client({ data: company })
  await assert.rejects(
    updateCompany(authentication, { companyId, expectedUpdatedAt: company.updatedAt }),
    /invalid organization mutation/i,
  )
  await assert.rejects(createBranch(authentication, { name: ' ' }, { idempotencyKey }), /invalid branch mutation/i)
  await assert.rejects(
    updateBranch(authentication, dubaiId, { defaultSalaryDay: 32, expectedUpdatedAt: branch.updatedAt }),
    /invalid branch mutation/i,
  )
  assert.deepEqual(authentication.requests, [])
})

test('validates recovery namespaces and status without putting keys in URLs', async () => {
  const namespacesClient = client({ data: { current: namespace, accepted: [namespace] } })
  assert.deepEqual(await readIdempotencyNamespaces(namespacesClient), {
    current: namespace, accepted: [namespace],
  })
  const statusClient = client({ data: { status: 'completed' } })
  assert.equal(await readIdempotencyStatus(statusClient, idempotencyKey), 'completed')
  assert.equal(statusClient.requests[0][0], '/api/v1/idempotency-status')
  assert.equal(statusClient.requests[0][1].headers['Idempotency-Key'], idempotencyKey)
})

test('retains unresolved idempotency keys and removes terminal or expired entries', () => {
  const values = new Map()
  let current = Date.UTC(2026, 8, 10)
  const store = createIdempotencyRecoveryStore({
    localStorage: {
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    },
    now: () => current,
    randomUUID: () => idempotencyKey,
  })
  assert.equal(store.begin(namespace), idempotencyKey)
  assert.equal(store.has(idempotencyKey), true)
  assert.equal(store.accepted([namespace]).length, 1)
  current += 7 * 24 * 60 * 60 * 1000
  assert.deepEqual(store.accepted([namespace]), [])
  assert.equal(store.has(idempotencyKey), false)
})
