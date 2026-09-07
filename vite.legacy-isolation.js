import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryDirectory = path.dirname(fileURLToPath(import.meta.url))
const migrationDirectory = path.join(repositoryDirectory, 'migration')

export const legacyPublicEnvironmentNames = [
  'VITE_SUPABASE_URL',
  'VITE_SUPABASE_ANON_KEY',
]

function isWithin(directory, candidate) {
  const relativePath = path.relative(directory, candidate)
  return relativePath === '' || (!relativePath.startsWith(`..${path.sep}`) && relativePath !== '..' && !path.isAbsolute(relativePath))
}

function forbiddenMessage(source) {
  return `Legacy build isolation rejected forbidden import: ${source}`
}

function assertAllowedImport(source, importer) {
  if (source === 'oidc-client-ts'
    || source.startsWith('oidc-client-ts/')
    || source === 'keycloak-js'
    || source.startsWith('keycloak-js/')) {
    throw new Error(forbiddenMessage(source))
  }

  if (!importer || !source.startsWith('.') && !path.isAbsolute(source)) return
  const candidate = path.isAbsolute(source) ? source : path.resolve(path.dirname(importer), source)
  if (isWithin(migrationDirectory, candidate)) throw new Error(forbiddenMessage(source))
}

export function legacyIsolationPlugin() {
  return {
    name: 'workloop-legacy-isolation',
    enforce: 'pre',
    resolveId(source, importer) {
      assertAllowedImport(source, importer)
      return null
    },
    transform(_code, id) {
      if (isWithin(migrationDirectory, id)) throw new Error(forbiddenMessage(id))
      return null
    },
  }
}

export const legacyIsolationPaths = {
  migrationDirectory,
  repositoryDirectory,
}
