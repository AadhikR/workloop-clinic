import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = (path) => readFile(new URL(path, import.meta.url), 'utf8')

test('restores the historical Workloop shell and visual tokens', async () => {
  const [shell, css] = await Promise.all([
    source('../src/PortalShell.jsx'),
    source('../src/index.css'),
  ])

  for (const marker of [
    'app-layout',
    'sidebar',
    'sidebar-logo',
    'sidebar-nav',
    'page-header',
    'page-body',
    'welcome-banner',
  ]) assert.match(shell, new RegExp(`className="[^"]*${marker}`))

  assert.match(shell, /className=\{`main-content\$\{sidebarCollapsed/)

  for (const token of [
    '--primary: #2563eb',
    '--secondary: #38bdf8',
    '--accent: #06b6d4',
    '--sidebar-w: 240px',
    '--sidebar-gap: 12px',
    '--radius-lg: 22px',
    'background: #08122e',
    '#eef2f7',
    'linear-gradient(135deg, #2563eb 0%, #06b6d4 100%)',
    'linear-gradient(135deg, #1a56db 0%, #1e429f 100%)',
  ]) assert.ok(css.includes(token), `missing historical visual token: ${token}`)

  assert.match(css, /@media \(max-width: 48rem\)/)
  assert.match(shell, /aria-label="Primary"/)
  assert.match(shell, /aria-current=/)
  assert.match(shell, /sidebarStorageKey/)
  assert.match(shell, /className="nav-pill"/)
  assert.match(shell, /className="nav-divider"/)
  assert.match(shell, /className=\{`sidebar\$\{sidebarCollapsed/)
  assert.match(shell, /className=\{`main-content\$\{sidebarCollapsed/)
  assert.match(css, /--sidebar-w-collapsed: 64px/)
  assert.match(css, /\.portal\[data-portal-role\] \.nav-pill/)
  assert.match(css, /\.portal\[data-portal-role\] \.sidebar\.collapsed/)
})

test('keeps role routing and session actions inside the restored shell', async () => {
  const shell = await source('../src/PortalShell.jsx')
  assert.match(shell, /roleNavigation\(account\.role\)/)
  assert.match(shell, /roleHome\(account\.role\)/)
  assert.match(shell, /<AdministratorPortal/)
  assert.match(shell, /<ManagerPortal/)
  assert.match(shell, /<EmployeePortal/)
  assert.match(shell, /authentication\.logout\(\)/)
  assert.match(shell, /organization\.clearBranch/)
})
