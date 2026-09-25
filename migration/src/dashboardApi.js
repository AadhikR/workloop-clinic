const timestampPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const datePattern = /^\d{4}-\d{2}-\d{2}$/
const sourceVersionPattern = /^sha256:[0-9a-f]{64}$/
const codePattern = /^[a-z][a-zA-Z0-9]{1,63}$/
const severityValues = new Set(['info', 'success', 'warning', 'critical'])

const definitions = {
  admin: {
    cards: new Map([
      ['activeHeadcount', 'employees'], ['finalizedPayroll', 'payroll'], ['wpsStatus', 'wps'],
      ['nafisRatio', 'nafis'], ['expiryDue', 'recordsBenefits'],
    ]),
  },
  clinical: {
    cards: new Map([
      ['credentialsValid', 'developmentAssets'], ['credentialsExpiring', 'developmentAssets'],
      ['credentialsExpired', 'developmentAssets'], ['publishedRoster', 'roster'],
      ['staffingValidation', 'roster'], ['onDuty', 'attendance'],
    ]),
  },
  self: {
    cards: new Map([
      ['employmentStatus', 'profile'], ['leaveBalance', 'leave'], ['latestPayslip', 'payslips'],
      ['todayAttendance', 'attendance'], ['assignedAssets', 'developmentAssets'],
      ['todayShift', 'schedule'],
    ]),
  },
}

function exactKeys(value, expected) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function dashboardValue(value) {
  return typeof value === 'string' || (Number.isInteger(value) && value >= 0)
}

function parseComparison(value) {
  if (value === null) return null
  if (
    !exactKeys(value, ['label', 'value', 'unit'])
    || typeof value.label !== 'string'
    || !dashboardValue(value.value)
    || typeof value.unit !== 'string'
  ) throw new Error('Invalid dashboard response')
  return value
}

function parseCard(kind, value) {
  const definition = definitions[kind]
  if (
    !exactKeys(value, ['code', 'label', 'value', 'unit', 'severity', 'comparison', 'drillDown'])
    || !codePattern.test(value.code)
    || !definition.cards.has(value.code)
    || typeof value.label !== 'string'
    || !dashboardValue(value.value)
    || typeof value.unit !== 'string'
    || !severityValues.has(value.severity)
    || !exactKeys(value.drillDown, ['code', 'target'])
    || value.drillDown.code !== value.code
    || definition.cards.get(value.code) !== value.drillDown.target
  ) throw new Error('Invalid dashboard response')
  return { ...value, comparison: parseComparison(value.comparison) }
}

export function parseDashboard(kind, value) {
  if (!definitions[kind]) throw new TypeError('Invalid dashboard kind')
  if (
    !exactKeys(value, ['asOf', 'businessDate', 'sourceVersion', 'cards'])
    || !timestampPattern.test(value.asOf)
    || !datePattern.test(value.businessDate)
    || !sourceVersionPattern.test(value.sourceVersion)
    || !Array.isArray(value.cards)
    || value.cards.length !== definitions[kind].cards.size
  ) throw new Error('Invalid dashboard response')
  const cards = value.cards.map((card) => parseCard(kind, card))
  if (new Set(cards.map((card) => card.code)).size !== cards.length) {
    throw new Error('Invalid dashboard response')
  }
  return { ...value, cards }
}

function headers(kind, branchId) {
  if (kind === 'self') return {}
  if (typeof branchId !== 'string' || branchId.length !== 36) {
    throw new TypeError('Invalid branch ID')
  }
  return { 'X-Workloop-Branch-ID': branchId }
}

export async function readDashboard(authentication, kind, branchId) {
  if (!definitions[kind]) throw new TypeError('Invalid dashboard kind')
  const envelope = await authentication.request(`/api/v1/dashboards/${kind}`, {
    access: 'protected', headers: headers(kind, branchId),
  })
  return parseDashboard(kind, envelope.data)
}
