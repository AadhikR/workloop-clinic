import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeRequestKind, REQUEST_KINDS, validateCustomRequest } from '../src/utils/requestUtils.js';

test('normalizeRequestKind preserves custom and defaults legacy values to letter', () => {
  assert.equal(normalizeRequestKind('custom'), REQUEST_KINDS.CUSTOM);
  assert.equal(normalizeRequestKind('letter'), REQUEST_KINDS.LETTER);
  assert.equal(normalizeRequestKind(null), REQUEST_KINDS.LETTER);
  assert.equal(normalizeRequestKind('unknown'), REQUEST_KINDS.LETTER);
});

test('validateCustomRequest requires meaningful subject and details', () => {
  assert.match(validateCustomRequest('HR', 'Valid details'), /subject/i);
  assert.match(validateCustomRequest('Equipment', 'No'), /describe/i);
  assert.equal(validateCustomRequest('  Equipment request  ', '  Please provide a new keyboard.  '), '');
});

test('validateCustomRequest enforces database length limits', () => {
  assert.match(validateCustomRequest('a'.repeat(121), 'Valid details'), /120/);
  assert.match(validateCustomRequest('Valid subject', 'a'.repeat(2001)), /2000/);
});