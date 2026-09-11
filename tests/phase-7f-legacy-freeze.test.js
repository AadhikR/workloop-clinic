import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('freezes the legacy employee administration writers', async () => {
  const source = await readFile(new URL('../src/utils/storage.js', import.meta.url), 'utf8')
  for (const name of ['saveEmployee', 'saveEmployees']) {
    assert.match(
      source,
      new RegExp(`export async function ${name}\\([^)]*\\) \\{[\\s\\S]*?throw new Error\\('Employee administration has moved to the migration employee directory\\.'\\);[\\s\\S]*?\\n\\}`),
    )
  }
  assert.doesNotMatch(source, /\.from\('employees'\)[\s\S]{0,200}\.upsert/)
})
