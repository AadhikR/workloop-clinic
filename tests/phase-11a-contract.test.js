import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

const documents = {
  inventory: 'docs/migration/phase-11/PART_11A_DEPENDENCY_INVENTORY.md',
  contract: 'docs/migration/phase-11/PART_11A_DOMAIN_AND_STORAGE_CONTRACT.md',
  golden: 'docs/migration/phase-11/PART_11A_GOLDEN_CASES.md',
  amendments: 'docs/migration/phase-11/PART_11A_AMENDMENT_PROPOSAL.md',
  completion: 'docs/migration/phase-11/PART_11A_COMPLETION.md',
};

const cutovers = [
  'common-storage-recovery',
  'employee-documents',
  'insurance',
  'employment-contracts',
  'assets',
  'training-certifications-cme',
  'appraisals',
  'clinical-incidents',
  'letter-requests',
  'offboarding-final-settlement',
];

test('Phase 11A contract documents exist and close every planned domain', () => {
  const inventory = read(documents.inventory);
  const contract = read(documents.contract);
  const golden = read(documents.golden);
  const amendments = read(documents.amendments);
  const completion = read(documents.completion);

  for (const part of ['11B', '11C', '11D', '11E', '11F', '11G', '12', '13']) {
    assert.match(inventory, new RegExp(`\\b${part}\\b`));
  }

  for (const domain of cutovers) {
    const phrase = domain.split('-').join('[\\s\\S]*');
    assert.match(`${contract}\n${golden}\n${amendments}`, new RegExp(phrase, 'i'));
  }

  for (const decision of Array.from({ length: 18 }, (_, index) => `11A-D${index + 1}`)) {
    assert.match(contract, new RegExp(`\\b${decision}\\b`));
  }

  assert.match(contract, /production-policy stop/i);
  assert.match(contract, /Phase 12 owns/i);
  assert.match(contract, /Phase 13 owns/i);
  assert.match(completion, /project owner approved decisions/i);
});

test('Phase 11 cutover records reflect only completed implementation parts', () => {
  const goldenCaseCount = read(documents.golden).match(/`11A-G-[A-Z]+-\d+`/g)?.length ?? 0;
  assert.equal(goldenCaseCount, 45);

  for (const featureId of cutovers) {
    const path = `docs/migration/phase-11/cutover/${featureId}.json`;
    const record = JSON.parse(read(path));
    const evidence = JSON.parse(read(record.refresh.lastRefresh.evidence.path));
    assert.equal(record.featureId, featureId);
    assert.equal(record.dataClassification, 'synthetic');
    const implemented = new Set([
      'common-storage-recovery',
      'employee-documents',
      'insurance',
      'employment-contracts',
      'assets',
      'training-certifications-cme',
    ]).has(featureId);
    assert.equal(record.status.current, implemented ? 'completed' : 'preparation');
    const authority = implemented ? 'migration-fastapi' : 'legacy-supabase';
    assert.deepEqual(record.authority, {
      readSystem: authority,
      writeSystem: authority,
      writableSystems: [authority],
    });
    assert.notEqual(record.freeze.read.system, record.authority.readSystem);
    assert.notEqual(record.freeze.write.system, record.authority.writeSystem);
    assert.equal(record.refresh.mode, 'synthetic-only');
    assert.equal(evidence.sourceRecordCount, goldenCaseCount);
    assert.equal(evidence.targetRecordCount, goldenCaseCount);
    assert.equal(record.rollback.targetAuthority.readSystem, 'legacy-supabase');
    assert.equal(record.rollback.targetAuthority.writeSystem, 'legacy-supabase');
  }
});
