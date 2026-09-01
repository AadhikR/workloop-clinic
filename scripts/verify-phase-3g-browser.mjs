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
const compose = ['compose']
const kcadmConfig = '/tmp/workloop-phase-3g-kcadm.config'
const issuer = 'http://127.0.0.1:8080/realms/workloop-dev'
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
const createdRows = {
  appUsers: [],
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
    throw new Error('local synthetic fixture operation failed')
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
  authenticateAdministrator()
  for (const persona of personas) {
    assert.deepEqual(findUsers(persona.userName), [])
  }
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

  psql("INSERT INTO companies (id) VALUES (:'company_id')", { company_id: companyId })
  createdRows.company = true
  for (const persona of personas.filter(({ employeeId }) => employeeId)) {
    psql(
      "INSERT INTO employees (id, company_id) VALUES (:'employee_id', :'company_id')",
      { company_id: companyId, employee_id: persona.employeeId },
    )
    createdRows.employees.push(persona.employeeId)
  }
  for (const persona of personas) {
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
    const { authenticationSession } = await import('/src/App.jsx')
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
      page.on('request', (request) => {
        const requestUrl = new URL(request.url())
        if (
          requestUrl.origin === 'http://127.0.0.1:8080'
          && requestUrl.pathname.endsWith('/protocol/openid-connect/token')
        ) {
          tokenRequestCount += 1
        }
        if (
          requestUrl.origin === 'http://127.0.0.1:8000'
          && requestUrl.pathname === '/api/v1/auth/token-check'
        ) {
          accountRequestCount += 1
        }
        if (
          requestUrl.origin === 'http://127.0.0.1:5174'
          && requestUrl.pathname === '/auth/callback'
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
      assert.equal(accountRequestCount, 1)
      assert.equal(new URL(page.url()).pathname, '/')
      assert.equal(new URL(page.url()).search, '')
      stage(`${persona.role} callback captured ${Boolean(callbackUrl)}`)
      assert.ok(callbackUrl)
      stage(`${persona.role} callback referrer ${leakedCallbackReferrer ?? 'none'}`)
      assert.equal(leakedCallbackReferrer, null)
      await assertNoPersistedTokens(page)

      if (persona.role === 'admin') {
        stage('admin refresh-token renewal')
        const requestsBeforeRenewal = tokenRequestCount
        const accountRequestsBeforeRenewal = accountRequestCount
        await page.evaluate(async () => {
          const { authenticationSession } = await import('/src/App.jsx')
          await authenticationSession().renew()
        })
        await waitForStatus(page, 'signed-in')
        assert.equal(tokenRequestCount, requestsBeforeRenewal + 1)
        assert.equal(accountRequestCount, accountRequestsBeforeRenewal + 1)
        await assertNoPersistedTokens(page)
      }

      stage(`${persona.role} session restoration`)
      const accountRequestsBeforeRestoration = accountRequestCount
      await page.reload()
      await waitForStatus(page, 'signed-in')
      assert.equal(accountRequestCount, accountRequestsBeforeRestoration + 1)
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
  try {
    stage('synthetic fixture creation')
    fixturesCreated = true
    createFixtures()
    Object.assign(process.env, {
      VITE_API_BASE_URL: 'http://127.0.0.1:8000',
      VITE_OIDC_AUTHORITY: issuer,
      VITE_OIDC_CLIENT_ID: 'workloop-migration-web',
      VITE_OIDC_REDIRECT_URI: 'http://127.0.0.1:5174/auth/callback',
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
  } finally {
    if (viteServer) await viteServer.close()
    if (fixturesCreated) cleanupFixtures()
  }

  console.log('Phase 3G browser checks passed')
}

main().catch(() => {
  console.error(`Phase 3G browser checks failed at ${activeStage}`)
  process.exitCode = 1
})
