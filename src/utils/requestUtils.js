export const REQUEST_KINDS = Object.freeze({
  LETTER: 'letter',
  CUSTOM: 'custom',
});

export function normalizeRequestKind(kind) {
  return kind === REQUEST_KINDS.CUSTOM ? REQUEST_KINDS.CUSTOM : REQUEST_KINDS.LETTER;
}

export function validateCustomRequest(subject, details) {
  const cleanSubject = String(subject || '').trim();
  const cleanDetails = String(details || '').trim();

  if (cleanSubject.length < 3) return 'Please enter a subject of at least 3 characters.';
  if (cleanSubject.length > 120) return 'The subject cannot exceed 120 characters.';
  if (cleanDetails.length < 5) return 'Please describe your request in at least 5 characters.';
  if (cleanDetails.length > 2000) return 'The request details cannot exceed 2000 characters.';
  return '';
}