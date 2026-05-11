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
