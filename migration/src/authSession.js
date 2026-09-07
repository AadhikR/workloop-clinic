import { createAuthenticationSession } from './auth.js'
import { migrationPublicConfig } from './config.js'

let authentication

export function authenticationSession() {
  authentication ??= createAuthenticationSession(migrationPublicConfig)
  return authentication
}
