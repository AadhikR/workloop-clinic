import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

import { generateCorrectedSIF, generateSIF } from '../src/utils/sifGenerator.js'

test('legacy WPS, compliance, and Nafis writers are frozen', async () => {
  const storage = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  for (const name of ['getNafisReports', 'saveNafisReport', 'saveWpsTracking', 'saveComplianceOverride']) {
    assert.match(storage, new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?served by FastAPI`))
  }
  assert.doesNotMatch(storage, /\.from\('nafis_reports'\)|\.from\('compliance_overrides'\)/)
})

test('legacy SIF byte generation fails closed', () => {
  assert.throws(() => generateSIF({}, [], {}), /Phase 12 owns file generation/)
  assert.throws(() => generateCorrectedSIF({}, [], {}, []), /Phase 12 owns file generation/)
})

test('migration WPS and Nafis views do not call Supabase or create downloads', async () => {
  for (const path of ['../migration/src/wpsNafisApi.js', '../migration/src/WpsNafis.jsx']) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|Blob|createObjectURL|download=/i)
  }
})
