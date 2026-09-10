import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const docker = process.env.DOCKER
  || (process.platform === 'win32'
    && existsSync('C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe')
    ? 'C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe'
    : 'docker')
const compose = [
  'compose',
  ...(process.env.WORKLOOP_COMPOSE_PROJECT_NAME
    ? ['--project-name', process.env.WORKLOOP_COMPOSE_PROJECT_NAME]
    : []),
  ...(process.env.WORKLOOP_COMPOSE_FILES
    ? process.env.WORKLOOP_COMPOSE_FILES.split(';').flatMap((file) => ['--file', file])
    : []),
]
const kcadmConfig = '/tmp/workloop-phase-3g-kcadm.config'
const keycloakBaseUrl = (process.env.WORKLOOP_KEYCLOAK_BASE_URL
  || 'http://127.0.0.1:8080').replace(/\/$/, '')
const apiBaseUrl = (process.env.WORKLOOP_API_BASE_URL
  || 'http://127.0.0.1:8000').replace(/\/$/, '')
const issuer = `${keycloakBaseUrl}/realms/workloop-dev`
const keycloakOrigin = new URL(keycloakBaseUrl).origin
const apiOrigin = new URL(apiBaseUrl).origin
const personas = [
  {
    appUserId: '00000000-0000-0000-0000-000000000071',
    employeeId: null,
    role: 'admin',
    userName: 'phase-3g-admin-test',
  },
  {
    appUserId: '00000000-0000-0000-0000-000000000072',
    employeeId: '00000000-0000-0000-0000-000000000072',
    role: 'manager',
    userName: 'phase-3g-manager-test',
  },
  {
    appUserId: '00000000-0000-0000-0000-000000000073',
    employeeId: '00000000-0000-0000-0000-000000000073',
    role: 'employee',
    userName: 'phase-3g-employee-test',
  },
]
const companyId = '00000000-0000-0000-0000-000000000070'
const branchId = '00000000-0000-4000-8000-000000000071'
const alternateBranchId = '00000000-0000-4000-8000-000000000074'
const createdRows = {
  appUsers: [],
  branches: [],
  company: false,
  employees: [],
  profiles: [],
}
const createdIdentityIds = []
let activeStage = 'startup'

function stage(name) {
  activeStage = name
}

function run(args, { input = undefined, output = false } = {}) {
  const result = spawnSync(docker, [...compose, ...args], {
    cwd: root,
    encoding: 'utf8',
    input,
    maxBuffer: 10 * 1024 * 1024,
    windowsHide: true,
  })
  if (result.status !== 0) {
    const detail = result.stderr.trim() || result.stdout.trim() || `exit ${result.status}`
    throw new Error(`local synthetic fixture operation failed: ${detail}`)
  }
  return output ? result.stdout.trim() : ''
}

function kcadm(args, options = {}) {
  return run([
    'exec', '-T', 'keycloak', '/opt/keycloak/bin/kcadm.sh',
    ...args, '--config', kcadmConfig,
  ], options)
}

function psql(sql, variables = {}) {
  const variableArguments = Object.entries(variables)
    .flatMap(([name, value]) => ['--set', `${name}=${value}`])
  return run([
    'exec', '-T', 'postgres', 'psql', '--username', 'postgres', '--dbname', 'workloop',
    '--tuples-only', '--no-align', '--set', 'ON_ERROR_STOP=1', ...variableArguments,
  ], { input: sql, output: true })
}

function authenticateAdministrator() {
  run([
    'exec', '-T', 'keycloak', 'sh', '-c',
    `/opt/keycloak/bin/kcadm.sh config credentials --config ${kcadmConfig} `
      + '--server http://127.0.0.1:8080 --realm master '
      + '--user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" '
      + '>/dev/null 2>&1',
  ])
}

function findUsers(userName) {
  const result = kcadm(
    ['get', 'users', '-r', 'workloop-dev', '-q', `username=${userName}`],
    { output: true },
  )
  return JSON.parse(result)
}

function setPassword(userId, password) {
  run([
    'exec', '-T', 'keycloak', 'sh', '-c',
    `IFS= read -r password; /opt/keycloak/bin/kcadm.sh set-password --config ${kcadmConfig} `
      + `-r workloop-dev --userid ${userId} --new-password "$password" --temporary=false`,
  ], { input: password })
}

function createFixtures() {
  stage('synthetic Keycloak administrator authentication')
  authenticateAdministrator()
  stage('synthetic Keycloak identity preflight')
  for (const persona of personas) {
    assert.deepEqual(findUsers(persona.userName), [])
  }
  stage('synthetic PostgreSQL identity preflight')
  assert.equal(
    psql(
      "SELECT count(*) FROM companies WHERE id = :'company_id' "
        + "OR id IN (:'app_1', :'app_2', :'app_3')",
      {
        app_1: personas[0].appUserId,
        app_2: personas[1].appUserId,
        app_3: personas[2].appUserId,
        company_id: companyId,
      },
    ),
    '0',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM app_users WHERE id IN (:'app_1', :'app_2', :'app_3')",
      {
        app_1: personas[0].appUserId,
        app_2: personas[1].appUserId,
        app_3: personas[2].appUserId,
      },
    ),
    '0',
  )
  assert.equal(
    psql(
      "SELECT count(*) FROM employees WHERE id IN (:'employee_1', :'employee_2')",
      {
        employee_1: personas[1].employeeId,
        employee_2: personas[2].employeeId,
      },
    ),
    '0',
  )

  for (const persona of personas) {
    stage(`synthetic ${persona.role} identity creation`)
    persona.password = randomBytes(32).toString('base64url')
    persona.identityId = kcadm([
      'create', 'users', '-r', 'workloop-dev',
      '-s', `username=${persona.userName}`,
      '-s', 'firstName=Phase',
      '-s', `lastName=${persona.role}`,
      '-s', `email=${persona.userName}@example.test`,
      '-s', 'enabled=true',
      '-i',
    ], { output: true })
    if (!persona.identityId) {
      const matches = findUsers(persona.userName)
      createdIdentityIds.push(...matches.map(({ id }) => id))
    }
    assert.ok(persona.identityId)
    createdIdentityIds.push(persona.identityId)
    setPassword(persona.identityId, persona.password)
  }

  stage('synthetic organization row creation')
  psql("INSERT INTO companies (id) VALUES (:'company_id')", { company_id: companyId })
  createdRows.company = true
  for (const [createdBranchId, name] of [
    [branchId, 'Phase 3G main'],
    [alternateBranchId, 'Phase 3G alternate'],
  ]) {
    psql(
      "INSERT INTO branches (id, company_id, name) VALUES (:'branch_id', :'company_id', :'name')",
      { branch_id: createdBranchId, company_id: companyId, name },
    )
    createdRows.branches.push(createdBranchId)
  }
  for (const persona of personas.filter(({ employeeId }) => employeeId)) {
    stage(`synthetic ${persona.role} employee creation`)
    psql(
      "INSERT INTO employees (id, company_id, branch_id, name, mol_id) "
        + "VALUES (:'employee_id', :'company_id', :'branch_id', :'name', :'mol_id')",
      {
        branch_id: branchId,
        company_id: companyId,
        employee_id: persona.employeeId,
        mol_id: `MOL-${persona.role}`,
        name: `Phase ${persona.role}`,
      },
    )
    createdRows.employees.push(persona.employeeId)
  }
  for (const persona of personas) {
    stage(`synthetic ${persona.role} application profile creation`)
    psql(
      "INSERT INTO app_users (id, identity_issuer, identity_subject, status) "
        + "VALUES (:'app_user_id', :'issuer', :'subject', 'active')",
      { app_user_id: persona.appUserId, issuer, subject: persona.identityId },
    )
    createdRows.appUsers.push(persona.appUserId)
    psql(
      "INSERT INTO user_profiles (app_user_id, company_id, employee_id, role) "
        + "VALUES (:'app_user_id', :'company_id', NULLIF(:'employee_id', '')::uuid, :'role')",
      {
        app_user_id: persona.appUserId,
        company_id: companyId,
        employee_id: persona.employeeId ?? '',
        role: persona.role,
      },
    )
    createdRows.profiles.push(persona.appUserId)
  }
}

function cleanupFixtures() {
  let cleanupFailed = false
  const cleanup = (operation) => {
    try {
      operation()
    } catch {}
  }
  const verifyCleanup = (operation) => {
    try {
      operation()
    } catch {
      cleanupFailed = true
    }
  }
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (createdRows.company) {
      cleanup(() => psql(
        "DELETE FROM idempotency_records WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
      cleanup(() => psql(
        "DELETE FROM audit_events WHERE company_id = :'company_id'",
        { company_id: companyId },
      ))
    }
    for (const appUserId of createdRows.profiles) {
      cleanup(() => psql(
        "DELETE FROM user_profiles WHERE app_user_id = :'app_user_id'",
        { app_user_id: appUserId },
      ))
    }
    for (const appUserId of createdRows.appUsers) {
      cleanup(() => psql("DELETE FROM app_users WHERE id = :'app_user_id'", { app_user_id: appUserId }))
    }
    for (const employeeId of createdRows.employees) {
      cleanup(() => psql("DELETE FROM employees WHERE id = :'employee_id'", { employee_id: employeeId }))
    }
    if (createdRows.company) {
      for (const createdBranchId of createdRows.branches) {
        cleanup(() => psql(
          "DELETE FROM branches WHERE id = :'branch_id'",
          { branch_id: createdBranchId },
        ))
      }
      cleanup(() => psql("DELETE FROM companies WHERE id = :'company_id'", { company_id: companyId }))
    }

    for (const persona of personas) {
      cleanup(() => {
        for (const { id } of findUsers(persona.userName)) createdIdentityIds.push(id)
      })
    }
    for (const identityId of new Set(createdIdentityIds)) {
      cleanup(() => kcadm(['delete', `users/${identityId}`, '-r', 'workloop-dev']))
    }
  }

  verifyCleanup(() => assert.deepEqual(
    JSON.parse(kcadm(['get', 'users', '-r', 'workloop-dev'], { output: true })),
    [],
  ))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM app_users'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM user_profiles'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM employees'), '0'))
  verifyCleanup(() => assert.equal(psql('SELECT count(*) FROM companies'), '0'))
  verifyCleanup(() => run(['exec', '-T', 'keycloak', 'rm', '-f', kcadmConfig]))
  verifyCleanup(() => run(['exec', '-T', 'keycloak', 'test', '!', '-e', kcadmConfig]))
  if (cleanupFailed) throw new Error('local synthetic fixture cleanup failed')
}

async function waitForStatus(page, status) {
  await page.locator(`main[data-session-status="${status}"]`).waitFor({ timeout: 20_000 })
}

async function waitForSettledStatus(page, expected, label) {
  await page.waitForFunction(
    () => {
      const status = document.querySelector('main')?.dataset.sessionStatus
      return status && status !== 'loading'
    },
    undefined,
    { timeout: 20_000 },
  )
  const status = await page.locator('main').getAttribute('data-session-status')
  stage(`${label} ${status}`)
  assert.equal(status, expected)
}

async function interactiveLogin(page, persona) {
  stage(`${persona.role} login redirect`)
  await page.getByRole('button', { name: 'Sign in' }).click()
  stage(`${persona.role} credential form`)
  await page.locator('#username').fill(persona.userName)
  await page.locator('#password').fill(persona.password)
  stage(`${persona.role} login callback`)
  await page.locator('#kc-login').click()
  await page.waitForFunction(
    () => {
      const status = document.querySelector('main')?.dataset.sessionStatus
      return status && status !== 'loading'
    },
    undefined,
    { timeout: 20_000 },
  )
  const status = await page.locator('main').getAttribute('data-session-status')
  stage(`${persona.role} login callback ${status}`)
  assert.equal(status, 'signed-in')
}

async function assertNoPersistedTokens(page) {
  const storage = await page.evaluate(async () => {
    const { authenticationSession } = await import('/src/authSession.js')
    const user = await authenticationSession().manager.getUser()
    const tokens = [user?.access_token, user?.id_token, user?.refresh_token].filter(Boolean)
    const persisted = JSON.stringify({
      cookie: document.cookie,
      local: Object.entries(localStorage),
      session: Object.entries(sessionStorage),
    })
    return {
      cacheCount: (await caches.keys()).length,
      indexedDatabaseCount: (await indexedDB.databases()).length,
      local: Object.entries(localStorage),
      session: Object.entries(sessionStorage),
      tokenPersisted: tokens.some((token) => persisted.includes(token)),
    }
  })
  stage(`storage local ${storage.local.length}`)
  assert.deepEqual(storage.local, [])
  stage(`storage session ${storage.session.length}`)
  assert.deepEqual(storage.session, [])
  stage(`storage cache ${storage.cacheCount}`)
  assert.equal(storage.cacheCount, 0)
  stage(`storage indexeddb ${storage.indexedDatabaseCount}`)
  assert.equal(storage.indexedDatabaseCount, 0)
  stage(`storage token match ${storage.tokenPersisted}`)
  assert.equal(storage.tokenPersisted, false)
}

async function assertSampleApi(page, persona) {
  await page.waitForFunction(
    () => document.querySelector('[data-public-api-status]')?.dataset.publicApiStatus === 'ready'
      && document.querySelector('[data-account-api-status]')?.dataset.accountApiStatus === 'ready',
    undefined,
    { timeout: 20_000 },
  )
  assert.equal(await page.locator('[data-public-api-status]').textContent(), 'ok')
  assert.equal(await page.locator('[data-account-api-status]').textContent(), persona.role)
  const sampleText = await page.locator('.sample-status').textContent()
  assert.ok(sampleText.includes(persona.appUserId))
  assert.ok(sampleText.includes(companyId))
  if (persona.employeeId) {
    assert.ok(sampleText.includes(persona.employeeId))
    assert.ok(sampleText.includes(branchId))
  } else {
    assert.ok(sampleText.includes('Not linked'))
    assert.ok(sampleText.includes('Not selected'))
  }
}

function businessFingerprint() {
  return psql(
    "SELECT md5(concat_ws('|', "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.id)::text, '[]') FROM companies c), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(b) ORDER BY b.id)::text, '[]') FROM branches b), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(e) ORDER BY e.id)::text, '[]') FROM employees e), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY a.id)::text, '[]') FROM app_users a), "
      + "(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.app_user_id)::text, '[]') FROM user_profiles p)))",
  )
}

async function assertOrganizationApi(page, persona) {
  await page.waitForFunction(
    (role) => role === 'admin'
      ? Boolean(document.querySelector('.branch-chooser'))
      : Boolean(document.querySelector('.organization-summary')),
    persona.role,
    { timeout: 20_000 },
  )

  const result = await page.evaluate(async ({ role, branchId, alternateBranchId }) => {
    const { authenticationSession } = await import('/src/authSession.js')
    const session = authenticationSession()
    const capture = async (operation) => {
      try {
        return { response: await operation() }
      } catch (error) {
        return { error: { code: error.code, status: error.status } }
      }
    }
    const branches = await session.request('/api/v1/branches?limit=1&sort=name', {
      access: 'protected',
    })
    const next = branches.page.nextCursor === null
      ? null
      : await session.request(`/api/v1/branches?limit=1&sort=name&cursor=${branches.page.nextCursor}`, {
        access: 'protected',
      })
    return {
      branches,
      next,
      company: await capture(() => session.request('/api/v1/company', { access: 'protected' })),
      employer: await capture(() => session.request('/api/v1/employer', { access: 'protected' })),
      detail: await capture(() => session.request(`/api/v1/branches/${branchId}`, {
        access: 'protected',
        headers: { 'X-Workloop-Branch-ID': branchId },
      })),
      mismatch: await capture(() => session.request(`/api/v1/branches/${alternateBranchId}`, {
        access: 'protected',
        headers: { 'X-Workloop-Branch-ID': branchId },
      })),
      unknown: await capture(() => session.request('/api/v1/branches?companyId=guessed', {
        access: 'protected',
      })),
      role,
    }
  }, { role: persona.role, branchId, alternateBranchId })

  stage(`${persona.role} organization API ${JSON.stringify({
    company: result.company.error ?? 'ok',
    detail: result.detail.error ?? 'ok',
    employer: result.employer.error ?? 'ok',
    mismatch: result.mismatch.error ?? 'ok',
    unknown: result.unknown.error ?? 'ok',
  })}`)

  if (persona.role === 'admin') {
    assert.deepEqual(Object.keys(result.company.response.data).sort(), [
      'createdAt', 'enableNafis', 'id', 'nafisQuotaPercent', 'name', 'sector', 'updatedAt',
    ])
    assert.equal(result.employer.error.code, 'operation_not_permitted')
    assert.equal(result.branches.data.length, 1)
    assert.equal(result.branches.page.hasMore, true)
    assert.equal(result.next.data.length, 1)
    assert.notEqual(result.branches.data[0].id, result.next.data[0].id)
    assert.deepEqual(Object.keys(result.detail.response.data).sort(), [
      'address', 'contactEmail', 'createdAt', 'defaultBankRoutingCode', 'defaultSalaryDay',
      'enableBiometricImport', 'enableStaffingRules', 'freeZoneName', 'id', 'logoUrl',
      'molEmployerId', 'name', 'updatedAt', 'workLocationType',
    ])
    assert.equal(result.mismatch.error.code, 'resource_not_found')
    assert.equal(result.mismatch.error.status, 404)
    const options = page.locator('.branch-options button')
    assert.equal(await options.count(), 2)
    const chosen = page.getByRole('button', { name: 'Phase 3G main', exact: true })
    const chosenName = (await chosen.textContent()).trim()
    await chosen.click()
    await page.locator('.organization-summary').waitFor()
    assert.equal((await page.locator('.organization-summary > p').textContent()).trim(), chosenName)
    assert.match(
      await page.evaluate(() => sessionStorage.getItem('workloop.branchId')),
      /^[0-9a-f-]{36}$/,
    )

    const selectedBranchForm = page.locator('.settings-form').filter({
      has: page.getByRole('heading', { name: 'Selected branch' }),
    })
    await selectedBranchForm.getByRole('button', { name: 'Delete branch' }).click()
    await selectedBranchForm.getByText('Select delete again to confirm.').waitFor()
    await selectedBranchForm.getByRole('button', { name: 'Confirm delete' }).click()
    const guardedDeleteStatus = selectedBranchForm.getByRole('status')
    await page.waitForFunction(
      () => {
        const text = [...document.querySelectorAll('.settings-form')]
          .find((form) => form.querySelector('h3')?.textContent === 'Selected branch')
          ?.querySelector('[role="status"]')?.textContent
        return Boolean(text) && text !== 'Select delete again to confirm.'
      },
      undefined,
      { timeout: 30_000 },
    )
    const guardedDeleteMessage = (await guardedDeleteStatus.textContent()).trim()
    stage(`admin guarded delete ${guardedDeleteMessage}`)
    assert.equal(
      guardedDeleteMessage,
      'This branch name or its retained records prevent the change.',
    )

    const createBranchForm = page.locator('.settings-form').filter({
      has: page.getByRole('heading', { name: 'Create branch' }),
    })
    await createBranchForm.getByLabel('Name').fill('Phase 7C browser branch')
    const createResponsePromise = page.waitForResponse((response) => {
      const request = response.request()
      return request.method() === 'POST' && new URL(response.url()).pathname === '/api/v1/branches'
    })
    await createBranchForm.getByRole('button', { name: 'Create branch' }).click()
    const createResponse = await createResponsePromise
    const createResponseBody = await createResponse.json()
    const createdBranchId = createResponseBody?.data?.id
    if (typeof createdBranchId === 'string' && !createdRows.branches.includes(createdBranchId)) {
      createdRows.branches.push(createdBranchId)
    }
    stage(`admin create branch response ${createResponse.status()} ${JSON.stringify(createResponseBody)}`)
    assert.equal(createResponse.status(), 201)
    const createStatus = createBranchForm.getByRole('status')
    await createStatus.waitFor()
    const createMessage = (await createStatus.textContent()).trim()
    stage(`admin create branch ${createMessage}`)
    assert.equal(createMessage, 'Branch created.')
    assert.equal(
      (await page.locator('.organization-summary > p').textContent()).trim(),
      'Phase 7C browser branch',
    )

    await selectedBranchForm.getByLabel('Name', { exact: true }).fill('Phase 7C browser branch updated')
    await selectedBranchForm.getByRole('button', { name: 'Save branch' }).click()
    await selectedBranchForm.getByText('Branch settings saved.').waitFor()
    await selectedBranchForm.getByRole('button', { name: 'Delete branch' }).click()
    await selectedBranchForm.getByRole('button', { name: 'Confirm delete' }).click()
    await page.locator('.branch-chooser').waitFor()
    assert.equal(await page.evaluate(() => sessionStorage.getItem('workloop.branchId')), null)
  } else {
    assert.equal(result.company.error.code, 'operation_not_permitted')
    assert.deepEqual(Object.keys(result.employer.response.data).sort(), [
      'branchAddress', 'branchContactEmail', 'branchName', 'companyName',
      'freeZoneName', 'logoUrl', 'workLocationType',
    ])
    assert.equal(result.branches.data.length, 1)
    assert.equal(result.branches.data[0].id, branchId)
    assert.equal(result.next, null)
    assert.equal(result.detail.error.code, 'operation_not_permitted')
    assert.equal(result.mismatch.error.code, 'operation_not_permitted')
  }
  assert.equal(result.unknown.error.code, 'validation_failed')
  assert.equal(result.unknown.error.status, 422)
}

async function browserChecks(viteServer) {
  const browser = await chromium.launch({ headless: true })
  try {
    for (const persona of personas) {
      stage(`${persona.role} initial session`)
      const context = await browser.newContext()
      const page = await context.newPage()
      let callbackUrl
      let leakedCallbackReferrer = null
      let tokenRequestCount = 0
      let accountRequestCount = 0
      let accountRequestsUsedBearer = true
      let healthRequestCount = 0
      let healthRequestUsedAuthorization = false
      let publicStatusRequestCount = 0
      let publicStatusUsedAuthorization = false
      let currentAccountRequestCount = 0
      let currentAccountRequestsUsedBearer = true
      let bearerLeftApiOrigin = false
      page.on('request', (request) => {
        const requestUrl = new URL(request.url())
        const authorization = request.headers().authorization
        if (authorization?.startsWith('Bearer ') && requestUrl.origin !== apiOrigin) {
          bearerLeftApiOrigin = true
        }
        if (
          requestUrl.origin === keycloakOrigin
          && requestUrl.pathname.endsWith('/protocol/openid-connect/token')
        ) {
          tokenRequestCount += 1
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/auth/token-check'
        ) {
          accountRequestCount += 1
          accountRequestsUsedBearer &&= authorization?.startsWith('Bearer ') === true
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/health'
        ) {
          healthRequestCount += 1
          healthRequestUsedAuthorization ||= Boolean(authorization)
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/public/status'
        ) {
          publicStatusRequestCount += 1
          publicStatusUsedAuthorization ||= Boolean(authorization)
        }
        if (
          requestUrl.origin === apiOrigin
          && requestUrl.pathname === '/api/v1/account/me'
        ) {
          currentAccountRequestCount += 1
          currentAccountRequestsUsedBearer &&= authorization?.startsWith('Bearer ') === true
        }
        if (
          requestUrl.origin === 'http://127.0.0.1:5174'
          && requestUrl.pathname === '/oidc/callback'
          && requestUrl.searchParams.has('code')
        ) {
          callbackUrl = requestUrl.toString()
        }
        const referrer = request.headers().referer
        if (
          requestUrl.origin === 'http://127.0.0.1:5174'
          && request.resourceType() !== 'document'
          && referrer
          && new URL(referrer).searchParams.has('code')
        ) {
          leakedCallbackReferrer = `${request.resourceType()}:${requestUrl.pathname}`
        }
      })

      await page.goto('http://127.0.0.1:5174/')
      await waitForSettledStatus(page, 'signed-out', `${persona.role} initial session`)
      stage(`${persona.role} interactive login`)
      await interactiveLogin(page, persona)
      await assertSampleApi(page, persona)
      const beforeOrganizationReads = businessFingerprint()
      await assertOrganizationApi(page, persona)
      assert.equal(businessFingerprint(), beforeOrganizationReads)
      assert.equal(accountRequestCount, 1)
      assert.ok(publicStatusRequestCount >= 1)
      assert.ok(currentAccountRequestCount >= 1)
      assert.equal(new URL(page.url()).pathname, '/')
      assert.equal(new URL(page.url()).search, '')
      stage(`${persona.role} callback captured ${Boolean(callbackUrl)}`)
      assert.ok(callbackUrl)
      stage(`${persona.role} callback referrer ${leakedCallbackReferrer ?? 'none'}`)
      assert.equal(leakedCallbackReferrer, null)
      await assertNoPersistedTokens(page)

      stage(`${persona.role} public health client`)
      const health = await page.evaluate(async () => {
        const { authenticationSession } = await import('/src/authSession.js')
        return authenticationSession().request('/health', { access: 'public' })
      })
      assert.deepEqual(health.data, { status: 'ok', database: 'ok' })
      assert.equal(healthRequestCount, 1)
      assert.equal(healthRequestUsedAuthorization, false)
      assert.equal(publicStatusUsedAuthorization, false)
      assert.equal(accountRequestsUsedBearer, true)
      assert.equal(currentAccountRequestsUsedBearer, true)
      assert.equal(bearerLeftApiOrigin, false)

      if (persona.role === 'admin') {
        stage('admin refresh-token renewal')
        const requestsBeforeRenewal = tokenRequestCount
        const accountRequestsBeforeRenewal = accountRequestCount
        await page.evaluate(async () => {
          const { authenticationSession } = await import('/src/authSession.js')
          await authenticationSession().renew()
        })
        await waitForStatus(page, 'signed-in')
        assert.equal(tokenRequestCount, requestsBeforeRenewal + 1)
        assert.equal(accountRequestCount, accountRequestsBeforeRenewal + 1)
        await assertNoPersistedTokens(page)
      }

      stage(`${persona.role} session restoration`)
      const accountRequestsBeforeRestoration = accountRequestCount
      const currentAccountRequestsBeforeRestoration = currentAccountRequestCount
      await page.reload()
      await waitForStatus(page, 'signed-in')
      await assertSampleApi(page, persona)
      assert.equal(accountRequestCount, accountRequestsBeforeRestoration + 1)
      assert.ok(currentAccountRequestCount > currentAccountRequestsBeforeRestoration)
      await assertNoPersistedTokens(page)

      if (persona.role === 'manager') {
        stage('manager changed email')
        kcadm([
          'update', `users/${persona.identityId}`, '-r', 'workloop-dev',
          '-s', 'email=phase-3g-manager-changed@example.test',
        ])
        await page.reload()
        await waitForStatus(page, 'signed-in')
      }

      if (persona.role === 'employee') {
        stage('employee disablement')
        psql(
          "UPDATE app_users SET status = 'disabled' WHERE id = :'app_user_id'",
          { app_user_id: persona.appUserId },
        )
        const disabledRead = await page.evaluate(async () => {
          const { authenticationSession } = await import('/src/authSession.js')
          try {
            await authenticationSession().request('/api/v1/employer', { access: 'protected' })
          } catch (error) {
            return { code: error.code, status: error.status }
          }
          return null
        })
        assert.deepEqual(disabledRead, { code: 'application_account_unavailable', status: 403 })
        await page.reload()
        await waitForStatus(page, 'account-unavailable')
      }

      stage(`${persona.role} logout`)
      await page.getByRole('button', { name: 'Sign out' }).click()
      await waitForStatus(page, 'signed-out')
      await page.reload()
      await waitForStatus(page, 'signed-out')

      if (persona.role === 'admin') {
        stage('callback replay rejection')
        await page.goto(callbackUrl)
        await waitForStatus(page, 'error')
        await assertNoPersistedTokens(page)
        stage('wrong state rejection')
        const wrongState = new URL(callbackUrl)
        wrongState.searchParams.set('state', 'invalid-state')
        await page.goto(wrongState.toString())
        await waitForStatus(page, 'error')
        await assertNoPersistedTokens(page)
      }
      assert.equal(accountRequestsUsedBearer, true)
      assert.equal(healthRequestUsedAuthorization, false)
      assert.equal(publicStatusUsedAuthorization, false)
      assert.equal(currentAccountRequestsUsedBearer, true)
      assert.equal(bearerLeftApiOrigin, false)
      await context.close()
    }

    stage('wrong nonce rejection')
    const nonceContext = await browser.newContext()
    const noncePage = await nonceContext.newPage()
    await noncePage.goto('http://127.0.0.1:5174/')
    await waitForStatus(noncePage, 'signed-out')
    await noncePage.evaluate(() => {
      const originalSetItem = Storage.prototype.setItem
      Storage.prototype.setItem = function setItem(key, value) {
        if (this === sessionStorage && key.startsWith('workloop.oidc.')) {
          const transactionState = JSON.parse(value)
          if (typeof transactionState.nonce === 'string') {
            transactionState.nonce = 'invalid-nonce'
            return originalSetItem.call(this, key, JSON.stringify(transactionState))
          }
        }
        return originalSetItem.call(this, key, value)
      }
    })
    await noncePage.getByRole('button', { name: 'Sign in' }).click()
    stage('wrong nonce login callback')
    await noncePage.locator('#username').fill(personas[0].userName)
    await noncePage.locator('#password').fill(personas[0].password)
    await noncePage.locator('#kc-login').click()
    await noncePage.waitForFunction(
      () => {
        const status = document.querySelector('main')?.dataset.sessionStatus
        return status && status !== 'loading'
      },
      undefined,
      { timeout: 20_000 },
    )
    const nonceStatus = await noncePage.locator('main').getAttribute('data-session-status')
    stage(`wrong nonce rejection ${nonceStatus}`)
    assert.equal(nonceStatus, 'error')
    await assertNoPersistedTokens(noncePage)
    await nonceContext.close()
  } finally {
    await browser.close()
    await viteServer.close()
  }
}

async function main() {
  let fixturesCreated = false
  let viteServer
  let primaryError
  try {
    stage('synthetic fixture creation')
    fixturesCreated = true
    createFixtures()
    Object.assign(process.env, {
      VITE_API_BASE_URL: apiBaseUrl,
      VITE_OIDC_AUTHORITY: issuer,
      VITE_OIDC_CLIENT_ID: 'workloop-migration-web',
      VITE_OIDC_REDIRECT_URI: 'http://127.0.0.1:5174/oidc/callback',
      VITE_OIDC_POST_LOGOUT_REDIRECT_URI: 'http://127.0.0.1:5174/',
      VITE_OIDC_AUDIENCE: 'workloop-api',
    })
    stage('migration server startup')
    viteServer = await createServer({
      configFile: path.join(root, 'migration', 'vite.migration.config.js'),
      envFile: false,
      logLevel: 'silent',
    })
    await viteServer.listen()
    stage('browser checks')
    await browserChecks(viteServer)
    viteServer = undefined
  } catch (error) {
    primaryError = error
    throw error
  } finally {
    if (viteServer) await viteServer.close()
    if (fixturesCreated) {
      try {
        cleanupFixtures()
      } catch (error) {
        if (!primaryError) throw error
        console.error(
          `Phase 3G browser cleanup failed: ${error instanceof Error ? error.message : 'unknown error'}`,
        )
      }
    }
  }

  console.log('Phase 3G browser checks passed')
}

main().catch((error) => {
  console.error(`Phase 3G browser checks failed at ${activeStage}`)
  console.error(error instanceof Error ? error.message : 'Unknown browser check failure')
  process.exitCode = 1
})
