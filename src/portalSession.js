import { HttpClientError } from './http.js'

export function classifyAccountFailure(error) {
  if (error instanceof HttpClientError) {
    if (error.kind === 'cancelled') return 'cancelled'
    if (error.status === 401) return 'session-expired'
    if (error.status === 403) return 'account-unavailable'
    if (
      error.status >= 500
      || error.kind === 'network'
      || error.kind === 'availability'
      || error.kind === 'timeout' && error.status === null
    ) return 'service-unavailable'
  }
  return 'account-unavailable'
}
