const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/
const instantPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/
const moneyPattern = /^(?:0|[1-9]\d*)\.\d{2}$/
const workLocationTypes = new Set(['mainland', 'free_zone'])
const branchStorageKey = 'workloop.branchId'

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function hasExactKeys(value, expected) {
  if (!isRecord(value)) return false
  const actual = Object.keys(value).sort()
  const required = [...expected].sort()
  return actual.length === required.length
    && actual.every((key, index) => key === required[index])
}

function isUuid(value) {
  return typeof value === 'string' && uuidPattern.test(value)
}

function isText(value) {
  return typeof value === 'string'
}

function isInstant(value) {
  return typeof value === 'string' && instantPattern.test(value)
}

function invalidOrganizationResponse() {
  return new Error('Invalid organization response')
}

function freezeExact(data) {
  return Object.freeze({ ...data })
}

function parseCompany(data) {
  if (
    !hasExactKeys(data, [
      'id', 'name', 'sector', 'nafisQuotaPercent', 'enableNafis', 'createdAt', 'updatedAt',
    ])
    || !isUuid(data.id)
    || !isText(data.name)
    || !isText(data.sector)
    || !moneyPattern.test(data.nafisQuotaPercent)
    || Number(data.nafisQuotaPercent) > 100
    || typeof data.enableNafis !== 'boolean'
    || !isInstant(data.createdAt)
    || !isInstant(data.updatedAt)
  ) throw invalidOrganizationResponse()
  return freezeExact(data)
}

function parseEmployer(data) {
  if (
    !hasExactKeys(data, [
      'companyName', 'branchName', 'branchContactEmail', 'branchAddress',
      'workLocationType', 'freeZoneName', 'logoUrl',
    ])
    || !isText(data.companyName)
    || !isText(data.branchName)
    || !isText(data.branchContactEmail)
    || !isText(data.branchAddress)
    || !workLocationTypes.has(data.workLocationType)
    || !isText(data.freeZoneName)
    || !isText(data.logoUrl)
  ) throw invalidOrganizationResponse()
  return freezeExact(data)
}

const safeBranchKeys = [
  'id', 'name', 'address', 'contactEmail', 'workLocationType', 'freeZoneName', 'logoUrl',
]
const adminBranchKeys = [
  ...safeBranchKeys,
  'molEmployerId', 'defaultBankRoutingCode', 'defaultSalaryDay',
  'enableStaffingRules', 'enableBiometricImport', 'createdAt', 'updatedAt',
]

function parseBranch(data) {
  const admin = hasExactKeys(data, adminBranchKeys)
  if (
    !admin && !hasExactKeys(data, safeBranchKeys)
    || !isUuid(data.id)
    || !isText(data.name)
    || !isText(data.address)
    || !isText(data.contactEmail)
    || !workLocationTypes.has(data.workLocationType)
    || !isText(data.freeZoneName)
    || !isText(data.logoUrl)
  ) throw invalidOrganizationResponse()
  if (
    admin
    && (
      !isText(data.molEmployerId)
      || !isText(data.defaultBankRoutingCode)
      || data.defaultSalaryDay !== null
        && (!Number.isInteger(data.defaultSalaryDay) || data.defaultSalaryDay < 1 || data.defaultSalaryDay > 31)
      || typeof data.enableStaffingRules !== 'boolean'
      || typeof data.enableBiometricImport !== 'boolean'
      || !isInstant(data.createdAt)
      || !isInstant(data.updatedAt)
    )
  ) throw invalidOrganizationResponse()
  return freezeExact(data)
}

function parsePage(page) {
  if (
    !hasExactKeys(page, ['limit', 'nextCursor', 'hasMore'])
    || !Number.isInteger(page.limit)
    || page.limit < 1
    || page.limit > 100
    || page.nextCursor !== null && typeof page.nextCursor !== 'string'
    || typeof page.hasMore !== 'boolean'
    || page.hasMore !== (page.nextCursor !== null)
  ) throw invalidOrganizationResponse()
  return freezeExact(page)
}

function queryString({ cursor, limit, search, sort }) {
  const parameters = new URLSearchParams()
  if (limit !== undefined) {
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new TypeError('Invalid branch query')
    parameters.set('limit', String(limit))
  }
  if (cursor !== undefined) {
    if (typeof cursor !== 'string' || !cursor) throw new TypeError('Invalid branch query')
    parameters.set('cursor', cursor)
  }
  if (search !== undefined) {
    if (typeof search !== 'string' || !search.trim() || search.trim().length > 100) {
      throw new TypeError('Invalid branch query')
    }
    parameters.set('search', search.normalize('NFC').trim())
  }
  if (sort !== undefined) {
    if (typeof sort !== 'string' || !sort) throw new TypeError('Invalid branch query')
    parameters.set('sort', sort)
  }
  const encoded = parameters.toString()
  return encoded ? `?${encoded}` : ''
}

export async function readCompany(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/company', {
    access: 'protected',
    signal,
  })
  return parseCompany(data)
}

export async function readEmployer(authentication, { signal } = {}) {
  const { data } = await authentication.request('/api/v1/employer', {
    access: 'protected',
    signal,
  })
  return parseEmployer(data)
}

export async function readBranches(authentication, options = {}) {
  const { signal, ...query } = options
  if (Object.keys(query).some((key) => !['cursor', 'limit', 'search', 'sort'].includes(key))) {
    throw new TypeError('Invalid branch query')
  }
  const { data, page } = await authentication.request(
    `/api/v1/branches${queryString(query)}`,
    { access: 'protected', signal },
  )
  if (!Array.isArray(data)) throw invalidOrganizationResponse()
  return Object.freeze({
    data: Object.freeze(data.map(parseBranch)),
    page: parsePage(page),
  })
}

export async function readAllBranches(authentication, options = {}) {
  if (Object.keys(options).some((key) => !['search', 'signal', 'sort'].includes(key))) {
    throw new TypeError('Invalid branch query')
  }
  const branches = []
  const identifiers = new Set()
  const cursors = new Set()
  let cursor
  do {
    const page = await readBranches(authentication, { ...options, cursor, limit: 100 })
    for (const branch of page.data) {
      if (identifiers.has(branch.id)) throw invalidOrganizationResponse()
      identifiers.add(branch.id)
      branches.push(branch)
    }
    cursor = page.page.nextCursor ?? undefined
    if (cursor !== undefined) {
      if (cursors.has(cursor)) throw invalidOrganizationResponse()
      cursors.add(cursor)
    }
  } while (cursor !== undefined)
  return Object.freeze(branches)
}

export async function readBranch(authentication, branchId, { signal } = {}) {
  if (!isUuid(branchId)) throw new TypeError('Invalid branch ID')
  const { data } = await authentication.request(`/api/v1/branches/${branchId}`, {
    access: 'protected',
    headers: { 'X-Workloop-Branch-ID': branchId },
    signal,
  })
  const branch = parseBranch(data)
  if (!hasExactKeys(branch, adminBranchKeys) || branch.id !== branchId) {
    throw invalidOrganizationResponse()
  }
  return branch
}

export function createBranchSelection({ sessionStorage }) {
  if (
    !sessionStorage
    || typeof sessionStorage.getItem !== 'function'
    || typeof sessionStorage.setItem !== 'function'
    || typeof sessionStorage.removeItem !== 'function'
  ) throw new TypeError('Invalid session storage')

  let selectedId = null
  try {
    const stored = sessionStorage.getItem(branchStorageKey)
    selectedId = isUuid(stored) ? stored : null
    if (stored !== null && selectedId === null) sessionStorage.removeItem(branchStorageKey)
  } catch {
    selectedId = null
  }

  const clear = () => {
    selectedId = null
    try {
      sessionStorage.removeItem(branchStorageKey)
    } catch {
      selectedId = null
    }
  }
  const accessible = (branches, id) => Array.isArray(branches)
    ? branches.find((branch) => branch?.id === id) ?? null
    : null

  return Object.freeze({
    currentId: () => selectedId,
    needsChooser: () => selectedId === null,
    clear,
    validate(branches) {
      if (selectedId === null) return null
      const branch = accessible(branches, selectedId)
      if (branch === null) clear()
      return branch
    },
    select(id, branches) {
      if (!isUuid(id)) {
        clear()
        return null
      }
      const branch = accessible(branches, id)
      if (branch === null) {
        clear()
        return null
      }
      selectedId = id
      try { sessionStorage.setItem(branchStorageKey, id) } catch { selectedId = null }
      return selectedId === null ? null : branch
    },
  })
}
