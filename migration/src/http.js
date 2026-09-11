const approvedLocalApiOrigins = new Set([
  'http://127.0.0.1:8000',
  'http://127.0.0.1:18000',
  'http://127.0.0.1:28000',
])

const allowedMethods = new Set(['GET', 'POST', 'PATCH', 'DELETE'])
const callerHeaderNames = new Set([
  'idempotency-key',
  'x-workloop-branch-id',
])
const correlationPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/

const errorContract = new Map([
  ['invalid_request', [400, 'validation']],
  ['branch_required', [400, 'validation']],
  ['invalid_cursor', [400, 'validation']],
  ['idempotency_key_required', [400, 'validation']],
  ['invalid_idempotency_key', [400, 'validation']],
  ['invalid_access_token', [401, 'authentication']],
  ['application_account_unavailable', [403, 'authorization']],
  ['operation_not_permitted', [403, 'authorization']],
  ['origin_not_allowed', [403, 'authorization']],
  ['resource_not_found', [404, 'authorization']],
  ['method_not_allowed', [405, 'validation']],
  ['not_acceptable', [406, 'validation']],
  ['state_conflict', [409, 'conflict']],
  ['branch_conflict', [409, 'conflict']],
  ['department_conflict', [409, 'conflict']],
  ['staffing_rule_conflict', [409, 'conflict']],
  ['idempotency_conflict', [409, 'conflict']],
  ['idempotency_in_progress', [409, 'conflict']],
  ['request_too_large', [413, 'validation']],
  ['unsupported_media_type', [415, 'validation']],
  ['validation_failed', [422, 'validation']],
  ['invalid_branch', [422, 'validation']],
  ['rate_limit_exceeded', [429, 'rate-limit']],
  ['internal_error', [500, 'unexpected']],
  ['application_account_lookup_unavailable', [503, 'availability']],
  ['service_unavailable', [503, 'availability']],
  ['request_timeout', [504, 'timeout']],
])

const safeMessages = Object.freeze({
  authentication: 'Authentication is required',
  authorization: 'The request is not permitted',
  cancelled: 'The request was cancelled',
  conflict: 'The request conflicts with the current state',
  malformedResponse: 'The service returned an invalid response',
  network: 'The service could not be reached',
  rateLimit: 'Too many requests. Try again shortly',
  timeout: 'The request timed out',
  unexpected: 'The request failed unexpectedly',
  validation: 'The request could not be accepted',
  availability: 'The service is temporarily unavailable',
})

export class HttpClientError extends Error {
  constructor(message, {
    kind,
    code,
    status = null,
    correlationId = null,
    retryAfter = null,
  }) {
    super(message)
    this.name = 'HttpClientError'
    this.kind = kind
    this.code = code
    this.status = status
    this.correlationId = correlationId
    this.retryAfter = retryAfter
  }
}

function clientError(kind, code, options = {}) {
  const messageName = kind.replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase())
  return new HttpClientError(safeMessages[messageName] ?? safeMessages.unexpected, {
    kind,
    code,
    ...options,
  })
}

function invalidRequest() {
  return clientError('validation', 'client_invalid_request')
}

export function assertApiBaseUrl(apiBaseUrl, browserOrigin = null) {
  let api
  try {
    api = new URL(apiBaseUrl)
  } catch {
    throw new Error('Migration API configuration is invalid')
  }

  if (
    !(
      approvedLocalApiOrigins.has(api.origin)
      || api.protocol === 'https:'
        && api.origin === browserOrigin
        && api.hostname.endsWith('.ondigitalocean.app')
    )
    || api.pathname !== '/'
    || api.search
    || api.hash
    || api.username
    || api.password
  ) {
    throw new Error('Migration API configuration is invalid')
  }
  return api
}

function resolveApiPath(path, apiBaseUrl) {
  if (
    typeof path !== 'string'
    || !path.startsWith('/')
    || path.startsWith('//')
    || path.includes('\\')
    || path.includes('#')
    || /%(?:2f|5c)/i.test(path)
  ) {
    throw invalidRequest()
  }

  const rawPath = path.split('?', 1)[0]
  try {
    if (rawPath.split('/').some((segment) => ['.', '..'].includes(decodeURIComponent(segment)))) {
      throw invalidRequest()
    }
  } catch (error) {
    if (error instanceof HttpClientError) throw error
    throw invalidRequest()
  }

  let destination
  try {
    destination = new URL(path, apiBaseUrl)
  } catch {
    throw invalidRequest()
  }
  if (
    destination.origin !== apiBaseUrl.origin
    || destination.username
    || destination.password
    || destination.hash
    || destination.pathname !== '/health'
      && !destination.pathname.startsWith('/api/v1/')
  ) {
    throw invalidRequest()
  }
  return destination
}

function isJsonContentType(value) {
  if (!value) return false
  const [mediaType, ...parameters] = value.split(';').map((part) => part.trim().toLowerCase())
  return mediaType === 'application/json'
    && parameters.every((parameter) => parameter === 'charset=utf-8')
}

function safeCorrelationId(value) {
  return typeof value === 'string' && correlationPattern.test(value) ? value : null
}

function responseCorrelationId(response) {
  return safeCorrelationId(response.headers.get('X-Correlation-ID'))
}

function malformedResponse(response, correlationId = null) {
  return clientError('malformed-response', 'client_malformed_response', {
    status: response.status,
    correlationId,
  })
}

async function parseJson(response, correlationId) {
  if (!isJsonContentType(response.headers.get('Content-Type'))) {
    throw malformedResponse(response, correlationId)
  }

  let body
  try {
    const text = await response.text()
    if (!text) throw new Error('empty response')
    body = JSON.parse(text)
  } catch {
    throw malformedResponse(response, correlationId)
  }
  return body
}

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function validPage(page) {
  return isRecord(page)
    && Number.isInteger(page.limit)
    && page.limit >= 1
    && page.limit <= 100
    && (page.nextCursor === null || typeof page.nextCursor === 'string')
    && typeof page.hasMore === 'boolean'
}

function validateRequiredErrorHeaders(response, code) {
  if (code === 'invalid_access_token') {
    return response.headers.get('WWW-Authenticate') === 'Bearer'
  }
  if (code === 'method_not_allowed') {
    return Boolean(response.headers.get('Allow'))
  }
  if (code === 'idempotency_in_progress' || code === 'rate_limit_exceeded') {
    return /^(?:0|[1-9][0-9]*)$/.test(response.headers.get('Retry-After') ?? '')
  }
  return true
}

function retryAfter(response) {
  const value = response.headers.get('Retry-After')
  return value !== null && /^(?:0|[1-9][0-9]*)$/.test(value) ? Number(value) : null
}

async function readResponse(response, destination) {
  const headerCorrelationId = responseCorrelationId(response)

  if (response.status === 204) {
    if (!headerCorrelationId || response.headers.has('Content-Type')) {
      throw malformedResponse(response, headerCorrelationId)
    }
    return {
      status: response.status,
      data: null,
      correlationId: headerCorrelationId,
      location: null,
      page: null,
      replayed: false,
    }
  }

  const body = await parseJson(response, headerCorrelationId)
  if (response.ok) {
    if (!headerCorrelationId || ![200, 201, 202].includes(response.status) || !isRecord(body)) {
      throw malformedResponse(response, headerCorrelationId)
    }

    const healthResponse = destination.pathname === '/health'
    if (healthResponse) {
      if (
        response.status !== 200
        || body.status !== 'ok'
        || body.database !== 'ok'
      ) {
        throw malformedResponse(response, headerCorrelationId)
      }
    } else if (!Object.hasOwn(body, 'data') || Object.hasOwn(body, 'page') && !validPage(body.page)) {
      throw malformedResponse(response, headerCorrelationId)
    }

    return {
      status: response.status,
      data: healthResponse ? body : body.data,
      correlationId: headerCorrelationId,
      location: response.headers.get('Location'),
      page: healthResponse ? null : body.page ?? null,
      replayed: response.headers.get('Idempotency-Replayed') === 'true',
    }
  }

  const envelope = isRecord(body) && isRecord(body.error) ? body.error : null
  const bodyCorrelationId = safeCorrelationId(envelope?.correlationId)
  const retainedCorrelationId = headerCorrelationId === bodyCorrelationId
    ? headerCorrelationId
    : headerCorrelationId ?? bodyCorrelationId
  if (
    !envelope
    || typeof envelope.code !== 'string'
    || typeof envelope.message !== 'string'
    || !Array.isArray(envelope.details)
    || !headerCorrelationId
    || !bodyCorrelationId
    || headerCorrelationId !== bodyCorrelationId
  ) {
    throw malformedResponse(
      response,
      headerCorrelationId && bodyCorrelationId && headerCorrelationId !== bodyCorrelationId
        ? null
        : retainedCorrelationId,
    )
  }

  const contract = errorContract.get(envelope.code)
  if (!contract) {
    throw clientError('unexpected', 'client_unexpected_response', {
      status: response.status,
      correlationId: headerCorrelationId,
    })
  }
  const [expectedStatus, kind] = contract
  if (response.status !== expectedStatus || !validateRequiredErrorHeaders(response, envelope.code)) {
    throw malformedResponse(response, headerCorrelationId)
  }
  throw clientError(kind, envelope.code, {
    status: response.status,
    correlationId: headerCorrelationId,
    retryAfter: retryAfter(response),
  })
}

function requestHeaders(options, accessToken) {
  let supplied
  try {
    supplied = new Headers(options.headers)
  } catch {
    throw invalidRequest()
  }
  for (const [name] of supplied) {
    if (!callerHeaderNames.has(name.toLowerCase())) throw invalidRequest()
  }

  const headers = new Headers({ Accept: 'application/json' })
  for (const [name, value] of supplied) headers.set(name, value)
  if (Object.hasOwn(options, 'json')) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  return headers
}

function requestBody(options, method) {
  if (!Object.hasOwn(options, 'json')) return undefined
  if (method === 'GET') throw invalidRequest()
  try {
    const body = JSON.stringify(options.json)
    if (body === undefined) throw new Error('value is not JSON')
    return body
  } catch {
    throw invalidRequest()
  }
}

export function createHttpClient({
  apiBaseUrl,
  browserOrigin = globalThis.location?.origin ?? null,
  fetch: fetchRequest,
  getAccessToken,
  timers = globalThis,
}) {
  const baseUrl = assertApiBaseUrl(apiBaseUrl, browserOrigin)
  if (
    typeof fetchRequest !== 'function'
    || typeof getAccessToken !== 'function'
    || typeof timers.setTimeout !== 'function'
    || typeof timers.clearTimeout !== 'function'
  ) {
    throw new Error('Migration HTTP client configuration is invalid')
  }

  return Object.freeze({
    async request(path, options = {}) {
      const allowedOptionNames = new Set(['access', 'headers', 'json', 'method', 'signal'])
      if (Object.keys(options).some((name) => !allowedOptionNames.has(name))) {
        throw invalidRequest()
      }
      if (options.access !== 'public' && options.access !== 'protected') {
        throw invalidRequest()
      }

      const destination = resolveApiPath(path, baseUrl)
      const method = (options.method ?? 'GET').toUpperCase()
      if (!allowedMethods.has(method)) throw invalidRequest()

      let accessToken = null
      if (options.access === 'protected') {
        accessToken = await getAccessToken()
        if (typeof accessToken !== 'string' || !accessToken || /\s/.test(accessToken)) {
          throw clientError('authentication', 'client_authentication_required')
        }
      }

      const headers = requestHeaders(options, accessToken)
      const body = requestBody(options, method)
      const callerSignal = options.signal
      if (callerSignal !== undefined && !(callerSignal instanceof AbortSignal)) {
        throw invalidRequest()
      }
      if (callerSignal?.aborted) {
        throw clientError('cancelled', 'client_cancelled')
      }

      const requestController = new AbortController()
      let abortOutcome = null
      const abortAs = (outcome) => {
        if (abortOutcome) return
        abortOutcome = outcome
        requestController.abort(new Error(outcome))
      }
      const callerAbort = () => abortAs('cancelled')
      callerSignal?.addEventListener('abort', callerAbort, { once: true })
      const deadline = destination.pathname === '/health' ? 10_000 : 20_000
      const timeout = timers.setTimeout(() => abortAs('timeout'), deadline)

      let response
      try {
        response = await fetchRequest(destination, {
          method,
          headers,
          body,
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'error',
          signal: requestController.signal,
        })
      } catch {
        if (abortOutcome === 'timeout') throw clientError('timeout', 'client_timeout')
        if (abortOutcome === 'cancelled') throw clientError('cancelled', 'client_cancelled')
        throw clientError('network', 'client_network_error')
      } finally {
        timers.clearTimeout(timeout)
        callerSignal?.removeEventListener('abort', callerAbort)
      }

      if (abortOutcome === 'timeout') throw clientError('timeout', 'client_timeout')
      if (abortOutcome === 'cancelled') throw clientError('cancelled', 'client_cancelled')
      if (!(response instanceof Response)) {
        throw clientError('malformed-response', 'client_malformed_response')
      }
      return readResponse(response, destination)
    },
  })
}
