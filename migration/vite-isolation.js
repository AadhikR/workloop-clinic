import path from 'node:path'
import { fileURLToPath } from 'node:url'

const migrationDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryDirectory = path.resolve(migrationDirectory, '..')
const legacySourceDirectory = path.join(repositoryDirectory, 'src')

function isWithin(directory, candidate) {
  const relativePath = path.relative(directory, candidate)
  return relativePath === '' || (!relativePath.startsWith(`..${path.sep}`) && relativePath !== '..' && !path.isAbsolute(relativePath))
}

function forbiddenMessage(source) {
  return `Migration build isolation rejected forbidden import: ${source}`
}

function assertAllowedImport(source, importer) {
  if (source === '@supabase/supabase-js' || source.startsWith('@supabase/')) {
    throw new Error(forbiddenMessage(source))
  }

  if (!importer || !source.startsWith('.') && !path.isAbsolute(source)) {
    return
  }

  const candidate = path.isAbsolute(source)
    ? source
    : path.resolve(path.dirname(importer), source)

  if (isWithin(legacySourceDirectory, candidate)) {
    throw new Error(forbiddenMessage(source))
  }
}

export function migrationIsolationPlugin() {
  return {
    name: 'workloop-migration-isolation',
    enforce: 'pre',
    resolveId(source, importer) {
      assertAllowedImport(source, importer)
      return null
    },
    transform(_code, id) {
      if (isWithin(legacySourceDirectory, id)) {
        throw new Error(forbiddenMessage(id))
      }
      return null
    },
  }
}

export const migrationIsolationPaths = {
  legacySourceDirectory,
  migrationDirectory,
  repositoryDirectory,
}
