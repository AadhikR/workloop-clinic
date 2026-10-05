import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import {
  digestEvidence,
  digestManifest,
  evaluateAction,
  validateRetainedBoundary,
} from '../scripts/verify-phase-13g-decommission.mjs'

const repositoryDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readJson(relativePath) {
  return JSON.parse(readFileSync(path.join(repositoryDirectory, relativePath), 'utf8'))
}

function clone(value) {
  return structuredClone(value)
}

function canonicalText(value) {
  if (Array.isArray(value)) return JSON.stringify(value.map((entry) => JSON.parse(canonicalText(entry))))
  if (value && typeof value === 'object') {
    return JSON.stringify(Object.fromEntries(
      Object.keys(value).sort().map((key) => [key, JSON.parse(canonicalText(value[key]))]),
    ))
  }
  return JSON.stringify(value)
}

function targetDigest(target) {
  return createHash('sha256').update(canonicalText(target)).digest('hex')
}

function settledFixture() {
  const hashA = 'a'.repeat(64)
  const hashB = 'b'.repeat(64)
  const manifest = {
    version: 1,
    manifestId: 'synthetic-settled-manifest',
    settledAt: '2026-09-26T00:00:00Z',
    mode: 'read-only',
    discovery: {
      externalProject: {
        status: 'resolved',
        organizationId: 'org_exact_001',
        projectId: 'project_exact_001',
      },
      auth: { status: 'resolved', userCount: 12, metadataRecordCount: 12 },
      database: {
        status: 'resolved',
        schemaObjects: ['public.example'],
        tableRowCounts: { 'public.example': 12 },
        rpcNames: ['public.example_rpc'],
        exportSha256: hashA,
      },
      realtime: {
        status: 'resolved',
        publications: ['publication_exact_001'],
        channelConfigurations: [],
      },
      storage: {
        status: 'resolved',
        buckets: [{
          name: 'bucket-exact-001',
          objectCount: 2,
          byteCount: 64,
          manifestSha256: hashB,
        }],
      },
      apiKeys: { status: 'resolved', identifiers: ['key_exact_001'] },
      github: {
        status: 'resolved',
        repository: 'example/workloop',
        environmentNames: ['production'],
        secretStores: [{ scope: 'actions-repository', entries: ['ENTRY_EXACT_001'] }],
      },
      digitalOcean: {
        status: 'resolved',
        apps: [{ appId: 'app_exact_001', components: ['web'], secretEntries: ['ENTRY_EXACT_002'] }],
      },
    },
    export: {
      status: 'verified',
      externalLocation: 'custodian://encrypted-export-001',
      custodian: 'project-owner',
      encryptionOwner: 'project-owner',
      evidenceSha256: '',
      artifactDigests: [hashA, hashB],
    },
    restore: {
      status: 'passed',
      completedAt: '2026-09-26T00:00:00Z',
      sourceEvidenceSha256: '',
      restoredEvidenceSha256: '',
      countsAndDigestsMatch: true,
    },
    retention: {
      status: 'active',
      minimumCalendarDays: 30,
      startsAt: '2026-09-26T00:00:00Z',
      deadline: '2026-10-26T00:00:00Z',
    },
    destructiveTargets: {
      apiKeys: [{ organizationId: 'org_exact_001', projectId: 'project_exact_001', keyId: 'key_exact_001' }],
      githubSecrets: [{ repository: 'example/workloop', store: 'actions-repository', entry: 'ENTRY_EXACT_001' }],
      digitalOceanSecrets: [{ appId: 'app_exact_001', component: 'web', entry: 'ENTRY_EXACT_002' }],
      storageSets: [{ projectId: 'project_exact_001', bucket: 'bucket-exact-001', objectCount: 2, manifestSha256: hashB }],
      projects: [{ organizationId: 'org_exact_001', projectId: 'project_exact_001' }],
    },
    receipts: [],
  }
  const evidenceSha256 = digestEvidence(manifest)
  manifest.export.evidenceSha256 = evidenceSha256
  manifest.restore.sourceEvidenceSha256 = evidenceSha256
  manifest.restore.restoredEvidenceSha256 = evidenceSha256

  const actions = [
    ['api-key', manifest.destructiveTargets.apiKeys[0]],
    ['github-secret', manifest.destructiveTargets.githubSecrets[0]],
    ['digitalocean-secret', manifest.destructiveTargets.digitalOceanSecrets[0]],
    ['storage-set', manifest.destructiveTargets.storageSets[0]],
    ['project', manifest.destructiveTargets.projects[0]],
  ].map(([kind, target]) => ({
    kind,
    target,
    preflightTargetSha256: targetDigest(target),
    preflightObservedAt: '2026-11-01T00:00:00Z',
  }))

  const manifestSha256 = digestManifest(manifest)
  const approval = {
    version: 1,
    status: 'approved',
    targetManifestSha256: manifestSha256,
    approvals: actions.map((action) => ({
      targetKind: action.kind,
      target: action.target,
      approvedBy: 'project-owner',
      approvedAt: '2026-10-27T00:00:00Z',
      targetManifestSha256: manifestSha256,
    })),
  }
  return { manifest, approval, actions }
}

function alembicHeads() {
  const revisions = new Set()
  const predecessors = new Set()
  const directory = path.join(repositoryDirectory, 'backend', 'alembic', 'versions')
  for (const name of readdirSync(directory)) {
    if (!name.endsWith('.py')) continue
    const source = readFileSync(path.join(directory, name), 'utf8')
    revisions.add(source.match(/^revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)[1])
    const predecessor = source.match(/^down_revision:[^=]+=[ ]*['"]([^'"]+)['"]/m)
    if (predecessor) predecessors.add(predecessor[1])
  }
  return [...revisions].filter((revision) => !predecessors.has(revision)).sort()
}

test('records the owner retention decision and keeps destruction fail closed', () => {
  const targetManifest = readJson('docs/migration/phase-13/PART_13G_TARGET_MANIFEST.json')
  const approvalManifest = readJson('docs/migration/phase-13/PART_13G_APPROVAL_MANIFEST.json')
  assert.deepEqual(validateRetainedBoundary(targetManifest, approvalManifest), [])
  assert.equal(targetManifest.discovery.externalProject.repositoryCandidateAuthoritative, true)
  assert.deepEqual(targetManifest.discovery.github.environmentNames, [])
  assert.ok(targetManifest.discovery.github.secretStores.every((store) => store.entries.length === 0))
  assert.equal(targetManifest.discovery.digitalOcean.status, 'resolved')
  assert.deepEqual(targetManifest.discovery.digitalOcean.apps, [])
  assert.equal(targetManifest.export.status, 'verified')
  assert.equal(targetManifest.export.decryptionRoundTripVerified, true)
  assert.equal(targetManifest.restore.status, 'passed')
  assert.equal(targetManifest.restore.countsAndDigestsMatch, true)
  assert.deepEqual(targetManifest.restore.mismatches, [])
  assert.equal(targetManifest.restore.sourceTableCount, 91)
  assert.equal(targetManifest.restore.restoredTableCount, 91)
  assert.equal(targetManifest.restore.sourceRowCount, 1005)
  assert.equal(targetManifest.restore.restoredRowCount, 1005)
  assert.equal(targetManifest.cleanup.disposableRestoreContainerRemoved, true)
  assert.equal(targetManifest.cleanup.encryptedArtifactsRetained, true)
  assert.equal(targetManifest.retention.status, 'indefinite')
  assert.equal(targetManifest.retention.startsAt, targetManifest.restore.completedAt)
  assert.equal(targetManifest.retention.minimumDeadline, '2026-10-27T09:06:58Z')
  assert.equal(targetManifest.retention.deadline, null)
  assert.equal(targetManifest.retention.decidedBy, 'project-owner')
  assert.equal(targetManifest.retention.disposition, 'retain-external-project')
  assert.equal(targetManifest.destructiveTargets.apiKeys.length, 4)
  assert.equal(targetManifest.destructiveTargets.storageSets.length, 2)
  assert.equal(targetManifest.destructiveTargets.projects.length, 1)
  assert.equal(approvalManifest.status, 'retained')
  assert.deepEqual(approvalManifest.approvals, [])
})

test('denies every current target after the owner chooses indefinite retention', () => {
  const targetManifest = readJson('docs/migration/phase-13/PART_13G_TARGET_MANIFEST.json')
  const approvalManifest = readJson('docs/migration/phase-13/PART_13G_APPROVAL_MANIFEST.json')
  const kinds = {
    apiKeys: 'api-key',
    githubSecrets: 'github-secret',
    digitalOceanSecrets: 'digitalocean-secret',
    storageSets: 'storage-set',
    projects: 'project',
  }
  for (const [collection, kind] of Object.entries(kinds)) {
    for (const target of targetManifest.destructiveTargets[collection]) {
      const result = evaluateAction({
        targetManifest,
        approvalManifest,
        action: {
          kind,
          target,
          preflightTargetSha256: targetDigest(target),
          preflightObservedAt: '2026-11-01T00:00:00Z',
        },
        now: '2026-11-01T00:00:00Z',
      })
      assert.equal(result.allowed, false)
      assert.ok(result.reasons.includes('project owner retained target; destructive actions are prohibited'))
    }
  }
})

test('allows only independently approved exact targets after restore and retention', () => {
  const { manifest, approval, actions } = settledFixture()
  for (const action of actions) {
    assert.deepEqual(
      evaluateAction({ targetManifest: manifest, approvalManifest: approval, action, now: '2026-11-01T00:00:00Z' }),
      { allowed: true, reasons: [] },
    )
  }
})

test('denies broad, partial, stale, changed, unretained, and unverified actions', () => {
  const fixture = readJson('tests/fixtures/phase-13g/approval-cases.json')
  for (const denial of fixture.denials) {
    const { manifest, approval, actions } = settledFixture()
    const action = clone(actions.at(-1))
    let now = fixture.now
    if (denial.mutation === 'remove-exact-approvals') {
      approval.status = 'ineligible'
      approval.approvals = []
    } else if (denial.mutation === 'use-wildcard-target') {
      action.target.projectId = '*'
      action.preflightTargetSha256 = targetDigest(action.target)
    } else if (denial.mutation === 'use-partial-target') {
      delete action.target.organizationId
      action.preflightTargetSha256 = targetDigest(action.target)
    } else if (denial.mutation === 'predate-settled-manifest') {
      approval.approvals.at(-1).approvedAt = '2026-09-25T23:59:59Z'
    } else if (denial.mutation === 'predate-retention-deadline') {
      approval.approvals.at(-1).approvedAt = '2026-10-25T23:59:59Z'
    } else if (denial.mutation === 'move-now-before-deadline') {
      now = '2026-10-25T23:59:59Z'
    } else if (denial.mutation === 'fail-restore') {
      manifest.restore.status = 'failed'
    } else if (denial.mutation === 'block-project-discovery') {
      manifest.discovery.externalProject.status = 'blocked'
    } else if (denial.mutation === 'change-preflight-digest') {
      action.preflightTargetSha256 = '0'.repeat(64)
    } else if (denial.mutation === 'age-preflight-observation') {
      action.preflightObservedAt = '2026-10-31T23:00:00Z'
    } else if (denial.mutation === 'change-approval-owner') {
      approval.approvals.at(-1).approvedBy = 'unknown'
    } else {
      assert.fail(`Unknown denial mutation ${denial.mutation}`)
    }
    const result = evaluateAction({ targetManifest: manifest, approvalManifest: approval, action, now })
    assert.equal(result.allowed, false, denial.id)
    assert.ok(result.reasons.includes(denial.expectedReason), `${denial.id}: ${result.reasons.join('; ')}`)
  }
})

test('contains no external mutation or project recreation implementation', () => {
  const source = readFileSync(
    path.join(repositoryDirectory, 'scripts', 'verify-phase-13g-decommission.mjs'),
    'utf8',
  )
  assert.doesNotMatch(source, /spawn|exec|fetch|https?\.|client\.|sdk/i)
  assert.doesNotMatch(source, /createProject|restoreProject|recreateProject/i)
})

test('records the completed Part 13G retained-project closure', () => {
  const catalogue = readJson('docs/migration/phase-13/dependency-catalogue.json')
  assert.equal(catalogue.boundaries['13G'], undefined)
  assert.equal(catalogue.closures['13G'].status, 'completed')
  assert.deepEqual(catalogue.closures['13G'].dependencies, [
    'P13-EXT-001',
    'P13-EXT-002',
    'P13-EXT-003',
    'P13-EXT-004',
    'P13-EXT-005',
    'P13-EXT-006',
    'P13-EXT-007',
    'P13-EXT-008',
    'P13-APR-001',
    'P13-DEL-001',
    'P13-DEL-002',
    'P13-DEL-003',
    'P13-RET-001',
    'P13-RET-002',
  ])
  assert.ok(catalogue.closures['13G'].goldenCases.includes('13A-GC-027'))
  assert.ok(catalogue.closures['13G'].goldenCases.includes('13A-GC-028'))
  assert.ok(catalogue.closures['13G'].goldenCases.includes('13A-GC-030'))
  assert.deepEqual(alembicHeads(), ['f3a5c7e9b1d4'])
})
