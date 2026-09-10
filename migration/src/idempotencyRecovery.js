const storageKey = 'workloop.idempotency.v1'
const sevenDays = 7 * 24 * 60 * 60 * 1000
const uuid4Pattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
const namespacePattern = /^rn1\.[0-9a-f]{8}\.[A-Za-z0-9_-]{22}$/

function validEntry(value, now) {
  return value !== null
    && typeof value === 'object'
    && !Array.isArray(value)
    && Object.keys(value).sort().join(',') === 'createdAt,key,namespace'
    && uuid4Pattern.test(value.key)
    && namespacePattern.test(value.namespace)
    && Number.isInteger(value.createdAt)
    && value.createdAt <= now
    && now - value.createdAt < sevenDays
}

export function createIdempotencyRecoveryStore({
  localStorage,
  now = () => Date.now(),
  randomUUID = () => globalThis.crypto.randomUUID(),
}) {
  if (!localStorage || typeof now !== 'function' || typeof randomUUID !== 'function') {
    throw new TypeError('Invalid idempotency recovery storage')
  }

  const read = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey) ?? '[]')
      if (!Array.isArray(parsed)) return []
      return parsed.filter((entry) => validEntry(entry, now()))
    } catch {
      return []
    }
  }
  const write = (entries) => {
    try {
      if (entries.length) localStorage.setItem(storageKey, JSON.stringify(entries))
      else localStorage.removeItem(storageKey)
    } catch {
      return false
    }
    return true
  }

  let entries = read()
  write(entries)

  return Object.freeze({
    begin(namespace) {
      if (!namespacePattern.test(namespace)) throw new TypeError('Invalid recovery namespace')
      const key = randomUUID()
      if (!uuid4Pattern.test(key)) throw new Error('Secure UUID generation failed')
      entries = [...entries, { key, createdAt: now(), namespace }]
      if (!write(entries)) throw new Error('Idempotency recovery storage is unavailable')
      return key
    },
    complete(key) {
      entries = entries.filter((entry) => entry.key !== key)
      write(entries)
    },
    accepted(namespaces) {
      if (!Array.isArray(namespaces) || namespaces.some((value) => !namespacePattern.test(value))) {
        throw new TypeError('Invalid accepted namespaces')
      }
      entries = entries.filter((entry) => validEntry(entry, now()))
      write(entries)
      return Object.freeze(entries.filter((entry) => namespaces.includes(entry.namespace)))
    },
    has(key) {
      return entries.some((entry) => entry.key === key)
    },
  })
}
