const allowedHeaders = new Set(['badgeNo', 'eventType', 'eventTime', 'deviceName'])
const requiredHeaders = ['badgeNo', 'eventType', 'eventTime']
const timestamp = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/

function split(line) {
  const cells = []; let value = ''; let quoted = false
  for (let index = 0; index < line.length; index += 1) {
    const character = line[index]
    if (character === '"' && line[index + 1] === '"' && quoted) { value += '"'; index += 1 }
    else if (character === '"') quoted = !quoted
    else if (character === ',' && !quoted) { cells.push(value.trim()); value = '' }
    else value += character
  }
  if (quoted) throw new Error('CSV contains an unclosed quoted field.')
  cells.push(value.trim()); return cells
}
function safe(value) {
  return value && !value.includes('\0') && !['=', '+', '-', '@'].includes(value[0])
}

export function parseAttendanceCsv(text) {
  if (typeof text !== 'string') throw new TypeError('CSV text is required.')
  const sourceBytes = new TextEncoder().encode(text).byteLength
  if (sourceBytes > 2_097_152) throw new Error('CSV must not exceed 2 MiB.')
  const lines = text.replace(/\r\n?/g, '\n').split('\n').filter((line) => line.trim())
  if (lines.length < 2) throw new Error('CSV must contain a header and at least one row.')
  const headers = split(lines[0])
  if (new Set(headers).size !== headers.length || headers.some((header) => !allowedHeaders.has(header)) || requiredHeaders.some((header) => !headers.includes(header))) throw new Error('CSV headers must be badgeNo,eventType,eventTime with optional deviceName.')
  if (lines.length - 1 > 5_000) throw new Error('CSV must not exceed 5,000 data rows.')
  const candidates = lines.slice(1).map((line, offset) => {
    const values = split(line)
    if (values.length !== headers.length) throw new Error(`CSV row ${offset + 2} has the wrong number of fields.`)
    const row = Object.fromEntries(headers.map((header, index) => [header, values[index]]))
    if (!safe(row.badgeNo) || !safe(row.eventType) || !safe(row.eventTime) || row.deviceName && !safe(row.deviceName) || !['CLOCK_IN', 'CLOCK_OUT'].includes(row.eventType) || !timestamp.test(row.eventTime)) throw new Error(`CSV row ${offset + 2} is invalid.`)
    return { badgeNo: row.badgeNo, eventType: row.eventType, eventTime: row.eventTime, deviceName: row.deviceName || 'Default' }
  })
  return Object.freeze({ sourceBytes, candidates: Object.freeze(candidates), preview: Object.freeze(candidates.slice(0, 100)) })
}
