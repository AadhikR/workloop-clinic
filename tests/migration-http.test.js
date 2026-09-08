import assert from 'node:assert/strict'
import test from 'node:test'

import {
  HttpClientError,
  createHttpClient,
} from '../migration/src/http.js'

const correlationId = '00f202d5-2ef0-4d6f-9553-830e5dcfb833'

function jsonResponse(body, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'X-Correlation-ID': correlationId,
      ...headers,
    },
  })
}

function errorResponse(code, status, options = {}) {
  const responseCorrelationId = options.bodyCorrelationId ?? correlationId
  return jsonResponse({
    error: {
      code,
      message: options.backendMessage ?? 'backend text must not reach the user',
      correlationId: responseCorrelationId,
      details: options.details ?? [],
    },
  }, {
    status,
    headers: options.headers,
  })
}

function client(overrides = {}) {
  return createHttpClient({
    apiBaseUrl: 'http://127.0.0.1:8000',
    fetch: overrides.fetch ?? (async () => jsonResponse({ data: { ok: true } })),
    getAccessToken: overrides.getAccessToken ?? (() => 'current-memory-token'),
    timers: overrides.timers,
  })
}

async function expectClientError(promise, expected) {
  await assert.rejects(promise, (error) => {
    assert.equal(error instanceof HttpClientError, true)
    for (const [name, value] of Object.entries(expected)) {
      assert.deepEqual(error[name], value)
    }
    assert.equal(error.message.includes('backend text'), false)
    return true
  })
}

test('keeps public requests token-free and enforces transport options', async () => {
  const requests = []
  const http = client({
    getAccessToken() { throw new Error('public requests must not read the token') },
    fetch: async (...args) => {
      requests.push(args)
      return jsonResponse({ status: 'ok', database: 'ok' })
    },
  })

  const result = await http.request('/health', { access: 'public' })

  assert.deepEqual(result.data, { status: 'ok', database: 'ok' })
  assert.equal(result.correlationId, correlationId)
  assert.equal(requests[0][0].toString(), 'http://127.0.0.1:8000/health')
  assert.equal(requests[0][1].headers.has('Authorization'), false)
  assert.equal(requests[0][1].credentials, 'omit')
  assert.equal(requests[0][1].redirect, 'error')
  assert.equal(requests[0][1].cache, 'no-store')
})

test('reads the current in-memory token for each protected request', async () => {
  const seenTokens = []
  let token = 'first-memory-token'
  const http = client({
    getAccessToken: () => token,
    fetch: async (_url, options) => {
      seenTokens.push(options.headers.get('Authorization'))
      return new Response(null, {
        status: 204,
        headers: { 'X-Correlation-ID': correlationId },
      })
    },
  })

  await http.request('/api/v1/auth/token-check', { access: 'protected' })
  token = 'renewed-memory-token'
  const result = await http.request('/api/v1/auth/token-check', { access: 'protected' })

  assert.deepEqual(seenTokens, ['Bearer first-memory-token', 'Bearer renewed-memory-token'])
  assert.equal(result.status, 204)
  assert.equal(result.data, null)
})

test('rejects missing protected tokens before fetch', async () => {
  let fetched = false
  const http = client({
    getAccessToken: () => null,
    fetch: async () => { fetched = true },
  })

  await expectClientError(
    http.request('/api/v1/auth/token-check', { access: 'protected' }),
    { kind: 'authentication', code: 'client_authentication_required', status: null },
  )
  assert.equal(fetched, false)
})

test('accepts only approved relative API paths and local API origins', async () => {
  for (const path of [
    'https://example.test/api/v1/data',
    '//example.test/api/v1/data',
    'http://127.0.0.1:8000/api/v1/data',
    '/outside',
    '/api/v2/data',
    '/api/v1/../outside',
    '/api/v1/data#fragment',
    '/api/v1\\data',
  ]) {
    await expectClientError(
      client().request(path, { access: 'public' }),
      { kind: 'validation', code: 'client_invalid_request', status: null },
    )
  }

  for (const apiBaseUrl of [
    'https://supabase.example.test',
    'http://localhost:8000',
    'http://127.0.0.1:8000/api',
    'http://user:password@127.0.0.1:8000',
  ]) {
    assert.throws(
      () => createHttpClient({ apiBaseUrl, fetch: async () => {}, getAccessToken: () => null }),
      /Migration API configuration is invalid/,
    )
  }

  assert.doesNotThrow(() => createHttpClient({
    apiBaseUrl: 'http://127.0.0.1:18000',
    fetch: async () => {},
    getAccessToken: () => null,
  }))

  assert.doesNotThrow(() => createHttpClient({
    apiBaseUrl: 'https://workloop-phase-6g-example.ondigitalocean.app',
    browserOrigin: 'https://workloop-phase-6g-example.ondigitalocean.app',
    fetch: async () => {},
    getAccessToken: () => null,
  }))
  assert.throws(
    () => createHttpClient({
      apiBaseUrl: 'https://other-app.ondigitalocean.app',
      browserOrigin: 'https://workloop-phase-6g-example.ondigitalocean.app',
      fetch: async () => {},
      getAccessToken: () => null,
    }),
    /Migration API configuration is invalid/,
  )
})

test('rejects caller-controlled transport and authorization fields', async () => {
  for (const options of [
    { access: 'public', headers: { Authorization: 'Bearer leaked' } },
    { access: 'public', headers: { 'X-Correlation-ID': correlationId } },
    { access: 'public', headers: { 'X-Unapproved': 'value' } },
    { access: 'public', credentials: 'include' },
    { access: 'public', redirect: 'follow' },
  ]) {
    await expectClientError(
      client().request('/health', options),
      { kind: 'validation', code: 'client_invalid_request', status: null },
    )
  }
})

test('serializes approved JSON requests without retrying mutations', async () => {
  const requests = []
  const http = client({
    fetch: async (...args) => {
      requests.push(args)
      return jsonResponse({ data: { version: 2 } }, { status: 200 })
    },
  })

  const result = await http.request('/api/v1/example', {
    access: 'protected',
    method: 'PATCH',
    json: { version: 1 },
    headers: {
      'Idempotency-Key': '8cb9b25d-91fd-4c2b-ac6a-8aa20d9e6d6d',
      'X-Workloop-Branch-ID': '2f078aa2-fcac-4bd4-876b-d78817dd5ff1',
    },
  })

  assert.deepEqual(result.data, { version: 2 })
  assert.equal(requests.length, 1)
  assert.equal(requests[0][1].method, 'PATCH')
  assert.equal(requests[0][1].body, '{"version":1}')
  assert.equal(requests[0][1].headers.get('Content-Type'), 'application/json')
})

test('validates data and collection success envelopes', async () => {
  const responses = [
    jsonResponse({ data: { id: 'one' } }),
    jsonResponse({
      data: [],
      page: { limit: 50, nextCursor: null, hasMore: false },
    }),
  ]
  const http = client({ fetch: async () => responses.shift() })

  assert.deepEqual(
    (await http.request('/api/v1/example', { access: 'public' })).data,
    { id: 'one' },
  )
  assert.deepEqual(
    (await http.request('/api/v1/examples', { access: 'public' })).page,
    { limit: 50, nextCursor: null, hasMore: false },
  )
})

test('rejects malformed JSON, bare success values, invalid media, and bodyful 204 responses', async () => {
  const malformedResponses = [
    new Response('{', {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'X-Correlation-ID': correlationId },
    }),
    jsonResponse({ id: 'bare' }),
    new Response('<html>bad gateway</html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html', 'X-Correlation-ID': correlationId },
    }),
    new Response(null, {
      status: 204,
      headers: { 'Content-Type': 'application/json', 'X-Correlation-ID': correlationId },
    }),
  ]

  for (const response of malformedResponses) {
    await expectClientError(
      client({ fetch: async () => response }).request('/api/v1/example', { access: 'public' }),
      { kind: 'malformed-response', code: 'client_malformed_response', status: response.status },
    )
  }
})

test('rejects missing, malformed, and inconsistent correlation IDs', async () => {
  const cases = [
    jsonResponse({ data: {} }, { headers: { 'X-Correlation-ID': '' } }),
    jsonResponse({ data: {} }, { headers: { 'X-Correlation-ID': 'UPPERCASE' } }),
    errorResponse('invalid_access_token', 401, {
      bodyCorrelationId: '3afbf0a0-9642-4d44-9884-e9654983eb9b',
    }),
  ]

  for (const response of cases) {
    await expectClientError(
      client({ fetch: async () => response }).request('/api/v1/example', { access: 'public' }),
      { kind: 'malformed-response', code: 'client_malformed_response' },
    )
  }
})

test('normalizes every approved server error group without exposing backend messages', async () => {
  const cases = [
    ['invalid_access_token', 401, 'authentication'],
    ['operation_not_permitted', 403, 'authorization'],
    ['resource_not_found', 404, 'authorization'],
    ['validation_failed', 422, 'validation'],
    ['state_conflict', 409, 'conflict'],
    ['rate_limit_exceeded', 429, 'rate-limit'],
    ['service_unavailable', 503, 'availability'],
    ['request_timeout', 504, 'timeout'],
    ['internal_error', 500, 'unexpected'],
  ]

  for (const [code, status, kind] of cases) {
    const headers = code === 'rate_limit_exceeded'
      ? { 'Retry-After': '17' }
      : code === 'invalid_access_token'
        ? { 'WWW-Authenticate': 'Bearer' }
        : undefined
    await expectClientError(
      client({
        fetch: async () => errorResponse(code, status, { headers }),
      }).request('/api/v1/example', { access: 'public' }),
      {
        kind,
        code,
        status,
        correlationId,
        retryAfter: code === 'rate_limit_exceeded' ? 17 : null,
      },
    )
  }
})

test('treats valid but unknown error codes as unexpected responses', async () => {
  await expectClientError(
    client({
      fetch: async () => errorResponse('future_failure', 418),
    }).request('/api/v1/example', { access: 'public' }),
    { kind: 'unexpected', code: 'client_unexpected_response', status: 418, correlationId },
  )
})

test('treats invalid error envelopes and required headers as malformed responses', async () => {
  const cases = [
    new Response('<html>failure</html>', {
      status: 500,
      headers: { 'Content-Type': 'text/html', 'X-Correlation-ID': correlationId },
    }),
    errorResponse('rate_limit_exceeded', 429),
    errorResponse('service_unavailable', 500),
  ]

  for (const response of cases) {
    await expectClientError(
      client({ fetch: async () => response }).request('/api/v1/example', { access: 'public' }),
      { kind: 'malformed-response', code: 'client_malformed_response', status: response.status },
    )
  }
})

test('distinguishes its deadline from caller cancellation', async () => {
  let timeoutCallback
  const timers = {
    setTimeout(callback) { timeoutCallback = callback; return 1 },
    clearTimeout() {},
  }
  const waitForAbort = (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })
  })

  const timedOut = client({ fetch: waitForAbort, timers })
    .request('/api/v1/example', { access: 'public' })
  timeoutCallback()
  await expectClientError(timedOut, {
    kind: 'timeout', code: 'client_timeout', status: null,
  })

  const caller = new AbortController()
  const cancelled = client({ fetch: waitForAbort, timers })
    .request('/api/v1/example', { access: 'public', signal: caller.signal })
  caller.abort()
  await expectClientError(cancelled, {
    kind: 'cancelled', code: 'client_cancelled', status: null,
  })
})

test('uses the 10-second health and 20-second ordinary browser deadlines', async () => {
  const delays = []
  const timers = {
    setTimeout(_callback, delay) { delays.push(delay); return delays.length },
    clearTimeout() {},
  }
  const http = client({
    timers,
    fetch: async (url) => jsonResponse(
      url.pathname === '/health'
        ? { status: 'ok', database: 'ok' }
        : { data: { ok: true } },
    ),
  })

  await http.request('/health', { access: 'public' })
  await http.request('/api/v1/example', { access: 'public' })

  assert.deepEqual(delays, [10_000, 20_000])
})

test('normalizes network failures without logging or retaining the token', async () => {
  const originalToken = 'current-memory-token'
  await expectClientError(
    client({
      getAccessToken: () => originalToken,
      fetch: async () => { throw new TypeError(`failed with ${originalToken}`) },
    }).request('/api/v1/example', { access: 'protected' }),
    { kind: 'network', code: 'client_network_error', status: null, correlationId: null },
  )
})
