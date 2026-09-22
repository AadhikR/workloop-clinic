import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');

test('Phase 11B uses one scanner database password across generated environments', () => {
  const compose = read('docker-compose.phase11b.yml');
  const generator = read('scripts/new-local-postgres-env.ps1');
  const migrateService = compose.split('\n  backend:', 1)[0];

  assert.match(
    migrateService,
    /WORKLOOP_FILE_SCANNER_PASSWORD: \$\{PHASE11B_SCANNER_DB_PASSWORD:/,
  );
  assert.match(
    generator,
    /GetEnvironmentVariable\(\s*"PHASE11B_SCANNER_DB_PASSWORD"\s*\)/,
  );
  assert.match(
    generator,
    /"WORKLOOP_FILE_SCANNER_PASSWORD=\$fileScannerPassword"/,
  );
});
