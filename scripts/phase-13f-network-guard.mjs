import { createRequire, syncBuiltinESMExports } from 'node:module'

const require = createRequire(import.meta.url)
const retiredMarker = String.fromCharCode(115, 117, 112, 97, 98, 97, 115, 101)
const supportedProtocols = new Set([
  'dns',
  'tcp',
  'tls',
  'http',
  'https',
  'websocket',
  'postgresql',
  'object-storage',
])

function textValues(value, seen = new Set()) {
  if (typeof value === 'string') return [value]
  if (value instanceof URL) return [value.href, value.hostname, value.pathname]
  if (!value || typeof value !== 'object' || seen.has(value)) return []
  seen.add(value)
  const keys = ['address', 'headers', 'host', 'hostname', 'href', 'path', 'protocol', 'socketPath', 'target', 'url']
  return keys.flatMap((key) => textValues(value[key], seen))
}

export function inspectNetworkAttempt(protocol, ...details) {
  if (!supportedProtocols.has(protocol)) throw new TypeError(`Unsupported network protocol: ${protocol}`)
  const forbidden = details.flatMap((detail) => textValues(detail))
    .some((value) => value.toLowerCase().includes(retiredMarker))
  return { forbidden, protocol }
}

export function assertAllowedNetworkAttempt(source, protocol, ...details) {
  const result = inspectNetworkAttempt(protocol, ...details)
  if (result.forbidden) {
    throw new Error(`Phase 13F blocked a forbidden ${protocol} attempt from ${source}`)
  }
  return result
}

function wrap(object, name, source, protocol) {
  const original = object?.[name]
  if (typeof original !== 'function' || original.phase13fGuarded) return
  function guarded(...args) {
    assertAllowedNetworkAttempt(source, protocol, ...args)
    return Reflect.apply(original, this, args)
  }
  Object.defineProperty(guarded, 'phase13fGuarded', { value: true })
  object[name] = guarded
}

export function installNodeNetworkGuard(source = 'node-runtime') {
  const dns = require('node:dns')
  const http = require('node:http')
  const https = require('node:https')
  const net = require('node:net')
  const tls = require('node:tls')

  for (const name of ['lookup', 'resolve', 'resolve4', 'resolve6', 'resolveAny']) {
    wrap(dns, name, source, 'dns')
    wrap(dns.promises, name, source, 'dns')
  }
  for (const name of ['connect', 'createConnection']) wrap(net, name, source, 'tcp')
  wrap(net.Socket.prototype, 'connect', source, 'tcp')
  wrap(tls, 'connect', source, 'tls')
  for (const name of ['get', 'request']) {
    wrap(http, name, source, 'http')
    wrap(https, name, source, 'https')
  }

  if (typeof globalThis.fetch === 'function' && !globalThis.fetch.phase13fGuarded) {
    const originalFetch = globalThis.fetch
    async function guardedFetch(...args) {
      const target = args[0] instanceof Request ? args[0].url : args[0]
      const protocol = String(target).startsWith('https:') ? 'https' : 'http'
      assertAllowedNetworkAttempt(source, protocol, target, args[1])
      return Reflect.apply(originalFetch, this, args)
    }
    Object.defineProperty(guardedFetch, 'phase13fGuarded', { value: true })
    globalThis.fetch = guardedFetch
  }

  if (typeof globalThis.WebSocket === 'function' && !globalThis.WebSocket.phase13fGuarded) {
    const OriginalWebSocket = globalThis.WebSocket
    class GuardedWebSocket extends OriginalWebSocket {
      static phase13fGuarded = true

      constructor(url, protocols) {
        assertAllowedNetworkAttempt(source, 'websocket', url)
        super(url, protocols)
      }
    }
    globalThis.WebSocket = GuardedWebSocket
  }
  syncBuiltinESMExports()
}

export async function installBrowserNetworkGuard(context, source = 'browser') {
  const forbiddenAttempts = []
  await context.route('**/*', async (route) => {
    const request = route.request()
    const url = request.url()
    const protocol = url.startsWith('ws:') || url.startsWith('wss:') ? 'websocket'
      : url.startsWith('https:') ? 'https' : 'http'
    if (inspectNetworkAttempt(protocol, url, request.headers()).forbidden) {
      forbiddenAttempts.push(protocol)
      await route.abort('blockedbyclient')
      return
    }
    await route.continue()
  })
  return {
    assertClean() {
      if (forbiddenAttempts.length > 0) {
        throw new Error(`Phase 13F blocked ${forbiddenAttempts.length} forbidden browser attempt(s)`)
      }
    },
  }
}

if (process.env.WORKLOOP_PHASE13F_NETWORK_GUARD === '1') {
  installNodeNetworkGuard(process.env.WORKLOOP_PHASE13F_NETWORK_SOURCE ?? 'node-runtime')
}
