/**
 * uaeValidators.js — UAE-specific field validation utilities
 *
 * Covers:
 *  - IBAN (UAE format: AE + 21 digits = 23 chars total)
 *  - Emirates ID (784-YYYY-XXXXXXX-X)
 *  - Passport expiry / visa expiry (must be future date on creation)
 *  - MOL Employee ID (10-15 digits)
 */

/**
 * Validate UAE IBAN.
 * Format: AE followed by 21 digits (total 23 characters).
 * @param {string} iban
 * @returns {{ valid: boolean, message: string }}
 */
export function validateIBAN(iban) {
  if (!iban) return { valid: false, message: 'IBAN is required' };
  const clean = iban.trim().toUpperCase().replace(/\s/g, '');
  if (!clean.startsWith('AE')) return { valid: false, message: 'UAE IBAN must start with AE' };
  if (clean.length !== 23) return { valid: false, message: `UAE IBAN must be 23 characters (got ${clean.length})` };
  if (!/^AE\d{21}$/.test(clean)) return { valid: false, message: 'UAE IBAN must be AE followed by 21 digits' };
  return { valid: true, message: '' };
}

/**
 * Validate Emirates ID.
 * Format: 784-YYYY-XXXXXXX-X (15 digits with dashes, or 15 raw digits)
 * @param {string} eid
 * @returns {{ valid: boolean, message: string }}
 */
export function validateEmiratesID(eid) {
  if (!eid) return { valid: false, message: 'Emirates ID is required' };
  const clean = eid.trim().replace(/-/g, '');
  if (!/^\d{15}$/.test(clean)) return { valid: false, message: 'Emirates ID must be 15 digits (format: 784-YYYY-XXXXXXX-X)' };
  if (!clean.startsWith('784')) return { valid: false, message: 'Emirates ID must start with 784' };
  // Validate year portion (digits 4-7)
  const year = parseInt(clean.substring(3, 7));
  if (year < 1900 || year > new Date().getFullYear()) {
    return { valid: false, message: 'Emirates ID contains an invalid year' };
  }
  return { valid: true, message: '' };
}

/**
 * Format Emirates ID with dashes: 784-YYYY-XXXXXXX-X
 * @param {string} raw — 15 raw digits
 * @returns {string}
 */
export function formatEmiratesID(raw) {
  const clean = (raw || '').replace(/-/g, '').trim();
  if (clean.length !== 15) return raw;
  return `${clean.slice(0, 3)}-${clean.slice(3, 7)}-${clean.slice(7, 14)}-${clean.slice(14)}`;
}

/**
 * Validate that a date string (YYYY-MM-DD) is in the future.
 * Used for passport/visa expiry on creation.
 * @param {string} dateStr
 * @param {string} fieldName
 * @returns {{ valid: boolean, message: string }}
 */
export function validateFutureDate(dateStr, fieldName = 'Date') {
  if (!dateStr) return { valid: true, message: '' }; // optional fields
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { valid: false, message: `${fieldName} is not a valid date` };
  if (d < new Date()) return { valid: false, message: `${fieldName} must be a future date` };
  return { valid: true, message: '' };
}

/**
 * Validate MOL Employee ID (Labour Card No).
 * Must be 10-15 digits.
 * @param {string} molId
 * @returns {{ valid: boolean, message: string }}
 */
export function validateMolId(molId) {
  if (!molId) return { valid: false, message: 'MOL Employee ID is required' };
  const clean = molId.trim();
  if (!/^\d{10,15}$/.test(clean)) return { valid: false, message: 'MOL Employee ID must be 10-15 digits' };
  return { valid: true, message: '' };
}

/**
 * Format a date string (YYYY-MM-DD) to DD/MM/YYYY (UAE display standard).
 * @param {string} dateStr
 * @returns {string}
 */
export function formatDateUAE(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

/**
 * Format a number as AED currency (e.g. AED 12,500.00).
 * @param {number} amount
 * @returns {string}
 */
export function formatAED(amount) {
  const n = parseFloat(amount) || 0;
  return `AED ${n.toLocaleString('en-AE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/**
 * Calculate days remaining until a date.
 * @param {string} dateStr — YYYY-MM-DD
 * @returns {number} — negative if expired
 */
export function daysUntil(dateStr) {
  if (!dateStr) return null;
  const expiry = new Date(dateStr);
  const today  = new Date();
  today.setHours(0, 0, 0, 0);
  expiry.setHours(0, 0, 0, 0);
  return Math.ceil((expiry - today) / (1000 * 60 * 60 * 24));
}

/**
 * Get expiry badge colour class based on days remaining.
 * Red < 30, Amber 30-60, Green 60-90.
 * @param {number} daysLeft
 * @returns {string} CSS class
 */
export function expiryBadgeClass(daysLeft) {
  if (daysLeft === null) return '';
  if (daysLeft < 0)  return 'badge-red';   // expired
  if (daysLeft < 30) return 'badge-red';
  if (daysLeft < 60) return 'badge-amber';
  return 'badge-green';
}

// ─────────────────────────────────────────────────────────────────────────────
// Additive validators — safe to import anywhere. All return { valid, message }.
// Empty string / null / undefined is treated as "not provided" and returns
// { valid: true } unless the specific validator's contract says otherwise.
// This keeps them opt-in — callers add extra guards for required fields.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Validate an email address (RFC-lite).
 * Empty → valid (many fields are optional). Callers enforce required-ness separately.
 * @param {string} email
 * @returns {{ valid: boolean, message: string }}
 */
export function validateEmail(email) {
  if (email == null || email === '') return { valid: true, message: '' };
  const clean = String(email).trim();
  if (clean.length > 254) return { valid: false, message: 'Email is too long' };
  // Pragmatic RFC-lite: local@domain.tld, no spaces, at least one dot in domain.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(clean)) {
    return { valid: false, message: 'Enter a valid email address (e.g. name@example.com)' };
  }
  return { valid: true, message: '' };
}

/**
 * Validate a UAE phone number.
 * Accepts +971, 971, or leading 0. 9 digits after the country/trunk prefix.
 * Empty → valid.
 * @param {string} phone
 * @returns {{ valid: boolean, message: string }}
 */
export function validateUAEPhone(phone) {
  if (phone == null || phone === '') return { valid: true, message: '' };
  const raw = String(phone).trim();
  // Strip common separators: spaces, dashes, parentheses.
  const clean = raw.replace(/[\s\-()]/g, '');
  // Formats accepted:
  //   +9715XXXXXXXX  (mobile) or +9712XXXXXXXX–+9719XXXXXXXX (landline)
  //   9715XXXXXXXX / 05XXXXXXXX / 02XXXXXXXX etc.
  //   Total significant digits after prefix normalisation = 9.
  if (!/^(\+?971|0)\d{8,9}$/.test(clean)) {
    return { valid: false, message: 'Enter a valid UAE phone (e.g. +971 50 123 4567 or 050 123 4567)' };
  }
  return { valid: true, message: '' };
}

/**
 * Validate a monetary amount.
 * Empty and non-numeric → invalid (callers wanting optional must pre-check).
 * @param {number|string} value
 * @param {{ min?: number, max?: number, allowZero?: boolean, fieldName?: string }} [opts]
 * @returns {{ valid: boolean, message: string, value: number }}
 */
export function validateAmount(value, opts = {}) {
  const { min = 0, max = Infinity, allowZero = false, fieldName = 'Amount' } = opts;
  if (value === '' || value == null) return { valid: false, message: `${fieldName} is required`, value: 0 };
  const n = typeof value === 'number' ? value : parseFloat(value);
  if (!Number.isFinite(n)) return { valid: false, message: `${fieldName} must be a number`, value: 0 };
  if (!allowZero && n <= 0) return { valid: false, message: `${fieldName} must be greater than zero`, value: n };
  if (allowZero && n < 0)   return { valid: false, message: `${fieldName} cannot be negative`, value: n };
  if (n < min) return { valid: false, message: `${fieldName} must be at least ${min}`, value: n };
  if (n > max) return { valid: false, message: `${fieldName} cannot exceed ${max.toLocaleString('en-AE')}`, value: n };
  return { valid: true, message: '', value: n };
}

/**
 * Validate that end date is on or after start date.
 * Empty on either side → valid (the field-required check is the caller's job).
 * @param {string} start — YYYY-MM-DD
 * @param {string} end   — YYYY-MM-DD
 * @param {{ startLabel?: string, endLabel?: string, allowEqual?: boolean }} [opts]
 * @returns {{ valid: boolean, message: string }}
 */
export function validateDateRange(start, end, opts = {}) {
  const { startLabel = 'Start date', endLabel = 'End date', allowEqual = true } = opts;
  if (!start || !end) return { valid: true, message: '' };
  const s = new Date(start);
  const e = new Date(end);
  if (isNaN(s.getTime()) || isNaN(e.getTime())) {
    return { valid: false, message: 'Invalid date' };
  }
  if (allowEqual ? e < s : e <= s) {
    return { valid: false, message: `${endLabel} must be ${allowEqual ? 'on or after' : 'after'} ${startLabel.toLowerCase()}` };
  }
  return { valid: true, message: '' };
}

/**
 * Validate that a date is not in the future (today allowed).
 * Empty → valid.
 * @param {string} dateStr — YYYY-MM-DD
 * @param {string} [fieldName]
 * @returns {{ valid: boolean, message: string }}
 */
export function validatePastDate(dateStr, fieldName = 'Date') {
  if (!dateStr) return { valid: true, message: '' };
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { valid: false, message: `${fieldName} is not a valid date` };
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  d.setHours(0, 0, 0, 0);
  if (d > today) return { valid: false, message: `${fieldName} cannot be in the future` };
  return { valid: true, message: '' };
}

/**
 * Validate a UAE bank routing / SCR code — 9 numeric digits.
 * Empty → valid (fields may be optional or auto-derived).
 * @param {string} code
 * @returns {{ valid: boolean, message: string }}
 */
export function validateBankRoutingCode(code) {
  if (code == null || code === '') return { valid: true, message: '' };
  const clean = String(code).trim();
  if (!/^\d{9}$/.test(clean)) {
    return { valid: false, message: 'Bank routing code must be 9 digits' };
  }
  return { valid: true, message: '' };
}

/**
 * Validate a rejection / cancellation reason — matches SIF compliance-override
 * standard of ≥10 characters after trim.
 * @param {string} reason
 * @param {number} [minLen]
 * @returns {{ valid: boolean, message: string }}
 */
export function validateRejectionReason(reason, minLen = 10) {
  const clean = String(reason ?? '').trim();
  if (!clean) return { valid: false, message: 'A reason is required' };
  if (clean.length < minLen) {
    return { valid: false, message: `Reason must be at least ${minLen} characters (currently ${clean.length})` };
  }
  return { valid: true, message: '' };
}

/**
 * Validate a UAE residence visa file number.
 * Common formats (as issued by GDRFA):
 *   - Slash format:  XXX/YYYY/ZZZZZZZ  (3-digit emirate code / 4-digit year / 7-digit serial)
 *   - Digits-only:   14 consecutive digits (same components without separators)
 * Empty → valid (field is optional; some employees hold non-residence visas).
 * @param {string} value
 * @returns {{ valid: boolean, message: string }}
 */
export function validateUAEVisaNumber(value) {
  if (value == null || value === '') return { valid: true, message: '' };
  const clean = String(value).trim().replace(/\s+/g, '');
  // Accept the slash-separated GDRFA format or 14 digits with no separator.
  if (/^\d{3}\/\d{4}\/\d{7}$/.test(clean)) return { valid: true, message: '' };
  if (/^\d{14}$/.test(clean))              return { valid: true, message: '' };
  return {
    valid: false,
    message: 'Visa number should be XXX/YYYY/ZZZZZZZ or 14 digits',
  };
}

/**
 * Validate a passport number.
 * Passport formats are country-specific; we apply the loosest cross-country rule:
 *   - 6-20 characters
 *   - letters (A-Z, case-insensitive) and digits only
 * Empty → valid.
 * @param {string} value
 * @returns {{ valid: boolean, message: string }}
 */
export function validatePassportNumber(value) {
  if (value == null || value === '') return { valid: true, message: '' };
  const clean = String(value).trim().toUpperCase();
  if (!/^[A-Z0-9]{6,20}$/.test(clean)) {
    return { valid: false, message: 'Passport number must be 6-20 letters and digits' };
  }
  return { valid: true, message: '' };
}

/**
 * Clamp a number to a range. Non-numeric input returns the min bound.
 * Used in onChange handlers so state never holds an out-of-range number.
 * @param {number|string} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
export function clampNumber(value, min, max) {
  const n = typeof value === 'number' ? value : parseFloat(value);
  if (!Number.isFinite(n)) return min;
  if (n < min) return min;
  if (n > max) return max;
  return n;
}
