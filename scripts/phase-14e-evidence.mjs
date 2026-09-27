import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const allowedFields = new Set([
  'component', 'count', 'digest', 'errorCode', 'observedAt', 'operator', 'releaseId',
  'resourceId', 'safeKeySuffix', 'signalId', 'sizeBytes', 'status',
])
const safeText = /^[A-Za-z0-9_.:-]{1,160}$/
const protectedValue = /bearer\s|password|secret|token|private[ _-]?key|postgres(?:ql)?:\/\/|https?:\/\/|x-amz-(?:signature|credential)|-----begin|[?&](?:sig|signature)=/i

export function sanitizeEvidenceRecord(record) {
  if (record === null || typeof record !== 'object' || Array.isArray(record)) throw new Error('evidence record must be an object')
  const sanitized = {}
  for (const [field, value] of Object.entries(record)) {
    if (!allowedFields.has(field)) throw new Error(`evidence field is not allowed: ${field}`)
    if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) {
      sanitized[field] = value
      continue
    }
    if (typeof value === 'string' && safeText.test(value) && !protectedValue.test(value)) {
      sanitized[field] = value
      continue
    }
    throw new Error(`evidence value is not safe: ${field}`)
  }
  if (!sanitized.observedAt || !sanitized.signalId || !sanitized.operator) throw new Error('evidence requires observedAt, signalId, and operator')
  return sanitized
}

export function sanitizeEvidence(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error('evidence input must be a nonempty array')
  return records.map(sanitizeEvidenceRecord)
}

function main() {
  const inputIndex = process.argv.indexOf('--input')
  const outputIndex = process.argv.indexOf('--output')
  if (inputIndex === -1 || outputIndex === -1 || !process.argv[inputIndex + 1] || !process.argv[outputIndex + 1]) {
    throw new Error('usage: phase-14e-evidence.mjs --input input.json --output output.json')
  }
  const input = path.resolve(process.argv[inputIndex + 1])
  const output = path.resolve(process.argv[outputIndex + 1])
  if (existsSync(output)) throw new Error('evidence output already exists')
  const records = JSON.parse(readFileSync(input, 'utf8'))
  writeFileSync(output, `${JSON.stringify(sanitizeEvidence(records), null, 2)}\n`, { encoding: 'utf8', flag: 'wx' })
  process.stdout.write(`Sanitized evidence written to ${output}.\n`)
}

if (path.resolve(process.argv[1] ?? '') === fileURLToPath(import.meta.url)) main()
