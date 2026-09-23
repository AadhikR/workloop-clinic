import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const assets = await readFile(new URL('../src/utils/assetStorage.js', import.meta.url), 'utf8')
const development = await readFile(new URL('../src/utils/trainingStorage.js', import.meta.url), 'utf8')

function functionBody(source, symbol) {
  const start = source.indexOf(`export async function ${symbol}`)
  assert.notEqual(start, -1)
  const bodyStart = source.indexOf(') {', start) + 2
  let depth = 0
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1
    if (source[index] === '}' && --depth === 0) return source.slice(start, index + 1)
  }
  throw new Error(`Could not parse ${symbol}`)
}

test('assets and professional development use migration APIs', async () => {
  for (const path of [
    '../migration/src/developmentAssetsApi.js',
    '../migration/src/DevelopmentAssets.jsx',
  ]) {
    const source = await readFile(new URL(path, import.meta.url), 'utf8')
    assert.doesNotMatch(source, /supabase|storage_path|sha256/i)
  }
})

test('legacy asset functions fail closed', () => {
  for (const symbol of [
    'getAssets', 'saveAsset', 'deleteAsset', 'getAssetAssignments', 'assignAsset',
    'returnAsset', 'getEmployeeCurrentAssets',
  ]) {
    const body = functionBody(assets, symbol)
    assert.match(body, /migration assets and professional development workspace/i)
    assert.doesNotMatch(body, /supabase/)
  }
})

test('legacy training, certification, evidence, and CME functions fail closed', () => {
  for (const symbol of [
    'uploadCertificateFile', 'getCertificateSignedUrl', 'getTrainingRecords',
    'saveTrainingRecord', 'deleteTrainingRecord', 'getEmployeeTrainingRecords',
    'getCertifications', 'getAllCertifications', 'saveCertification', 'deleteCertification',
    'getEmployeeCertifications', 'getTeamTrainingRecords', 'getTeamCertifications',
    'saveTeamTrainingRecord', 'deleteTeamTrainingRecord', 'saveTeamCertification',
    'deleteTeamCertification', 'employeeSaveTrainingRecord', 'employeeSaveCertification',
    'getCmeRequirements', 'saveCmeRequirement', 'deleteCmeRequirement',
    'getCmeTrainingRecords', 'getManagerDirectReports',
  ]) {
    const body = functionBody(development, symbol)
    assert.match(body, /migration assets and professional development workspace/i)
    assert.doesNotMatch(body, /supabase/)
  }
})
