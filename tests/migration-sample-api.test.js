import assert from 'node:assert/strict'
import test from 'node:test'

import {
  readCurrentAccount,
  readPublicStatus,
} from '../migration/src/sampleApi.js'

const identifiers = {
  appUserId: '00f202d5-2ef0-4d6f-9553-830e5dcfb833',
  companyId: '3afbf0a0-9642-4d44-9884-e9654983eb9b',
  employeeId: '71bc11cf-1f9a-4492-8dd4-d0c1b39a6ef2',
  branchId: 'de0fb0c1-2d7a-438a-b19a-98e5bc3698c2',
}

function session(data) {
  const requests = []
  return {
    requests,
    async request(path, options) {
      requests.push([path, options])
      return { data }
    },
  }
}

test('reads public status without requesting an access token', async () => {
  const authentication = session({ status: 'ok' })

  const status = await readPublicStatus(authentication)

  assert.deepEqual(status, { status: 'ok' })
  assert.deepEqual(authentication.requests, [[
    '/api/v1/public/status',
    { access: 'public', signal: undefined },
  ]])
})

test('reads the current account through the protected client path', async () => {
  const data = { ...identifiers, role: 'manager' }
  const authentication = session(data)

  const account = await readCurrentAccount(authentication)

  assert.deepEqual(account, data)
  assert.deepEqual(authentication.requests, [[
    '/api/v1/account/me',
    { access: 'protected', signal: undefined },
  ]])
})

test('forwards cancellation and rejects malformed sample responses', async () => {
  const controller = new AbortController()
  const publicSession = session({ status: 'ok' })
  await readPublicStatus(publicSession, { signal: controller.signal })
  assert.equal(publicSession.requests[0][1].signal, controller.signal)

  for (const data of [
    { status: 'down' },
    { status: 'ok', extra: true },
    { ...identifiers, role: 'owner' },
    { ...identifiers, role: 'employee', employeeId: null, branchId: identifiers.branchId },
    { ...identifiers, role: 'admin', employeeId: identifiers.employeeId, branchId: null },
  ]) {
    const authentication = session(data)
    const operation = Object.hasOwn(data, 'status')
      ? readPublicStatus(authentication)
      : readCurrentAccount(authentication)
    await assert.rejects(operation, /invalid sample response/i)
  }
})
