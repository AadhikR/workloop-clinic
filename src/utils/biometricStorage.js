/**
 * biometricStorage.js — Biometric device integration (Feature 2.2)
 *
 * Handles badge→employee mappings and CSV punch imports from
 * ZKTeco, Suprema, and generic time-attendance devices.
 */
import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ── Badge mappings ────────────────────────────────────────────────────────────

export async function getBiometricMappings() {
  const user = await getSessionUser();
  if (!user) return [];
  const { data, error } = await supabase
    .from('biometric_mappings')
    .select('*')
    .eq('user_id', user.id)
    .order('badge_no');
  if (error) { console.error('getBiometricMappings:', error); return []; }
  return (data || []).map(r => ({
    id:         r.id,
    badgeNo:    r.badge_no,
    employeeId: r.employee_id,
    deviceName: r.device_name || 'Default',
    createdAt:  r.created_at,
  }));
}

export async function saveBiometricMapping({ badgeNo, employeeId, deviceName = 'Default' }) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const { data, error } = await supabase
    .from('biometric_mappings')
    .upsert(
      { user_id: user.id, badge_no: badgeNo, employee_id: employeeId, device_name: deviceName },
      { onConflict: 'user_id,badge_no' }
    )
    .select()
    .single();
  if (error) throw error;
  return { id: data.id, badgeNo: data.badge_no, employeeId: data.employee_id, deviceName: data.device_name, createdAt: data.created_at };
}

export async function deleteBiometricMapping(id) {
  const { error } = await supabase.from('biometric_mappings').delete().eq('id', id);
  if (error) throw error;
}

// ── CSV parser ────────────────────────────────────────────────────────────────

/**
 * Auto-detects the biometric device CSV format and returns an array of
 * punch objects: { badgeNo, eventType ('CLOCK_IN'|'CLOCK_OUT'), eventTime (ISO string) }
 *
 * Supported formats:
 *   1. ZKTeco Report — headers: Name, No., Date, Time, State, In/Out
 *   2. ZKTeco Simple — headers include datetime + Verify Type
 *   3. Generic       — Badge/BadgeNo, DateTime/Timestamp, Type/PunchType (0=IN, 1=OUT)
 */
export function parseBiometricCsv(text) {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim().split('\n').filter(l => l.trim());
  if (lines.length < 2) throw new Error('File has no data rows.');

  const rawHeader = lines[0];
  const header    = rawHeader.toLowerCase();
  const dataRows  = lines.slice(1);

  // Split a CSV line respecting quoted fields
  function splitCsv(line) {
    const result = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') { inQ = !inQ; continue; }
      if (c === ',' && !inQ) { result.push(cur.trim()); cur = ''; continue; }
      cur += c;
    }
    result.push(cur.trim());
    return result;
  }

  function toEventType(raw) {
    const v = String(raw).trim().toUpperCase();
    if (v === '0' || v === 'I' || v === 'IN' || v === 'CHECK IN' || v === 'CHECKIN') return 'CLOCK_IN';
    if (v === '1' || v === 'O' || v === 'OUT' || v === 'CHECK OUT' || v === 'CHECKOUT') return 'CLOCK_OUT';
    return null;
  }

  // Parse a date/time into an ISO-8601 string (assumes UTC+4 Dubai time)
  function toIso(datePart, timePart = '') {
    // Try ISO already
    const combined = `${datePart}${timePart ? ' ' + timePart : ''}`.trim();

    // YYYY-MM-DD or YYYY/MM/DD
    const isoMatch = combined.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
    if (isoMatch) {
      const [, y, mo, d, h, mi, s = '00'] = isoMatch;
      return `${y}-${mo.padStart(2,'0')}-${d.padStart(2,'0')}T${h.padStart(2,'0')}:${mi}:${s}+04:00`;
    }

    // DD/MM/YYYY (Gulf standard)
    const gulfMatch = combined.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?/);
    if (gulfMatch) {
      const [, d, mo, y, h, mi, s = '00'] = gulfMatch;
      return `${y}-${mo.padStart(2,'0')}-${d.padStart(2,'0')}T${h.padStart(2,'0')}:${mi}:${s}+04:00`;
    }

    // Date only + separate time
    const dateOnly = datePart.trim();
    const timeOnly = timePart.trim();
    const dMatch = dateOnly.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (dMatch && timeOnly) {
      const [, d, mo, y] = dMatch;
      return `${y}-${mo.padStart(2,'0')}-${d.padStart(2,'0')}T${timeOnly.padStart(5,'0')}:00+04:00`;
    }

    throw new Error(`Unrecognised date format: "${combined}"`);
  }

  // ── Format 1: ZKTeco Report (Name, No., Date, Time, State, In/Out) ──────────
  if (header.includes('in/out') || header.includes('inout') || (header.includes('state') && header.includes('time'))) {
    const cols   = splitCsv(rawHeader);
    const iNo    = cols.findIndex(c => /^no\.?$/i.test(c.trim()));
    const iDate  = cols.findIndex(c => /date/i.test(c));
    const iTime  = cols.findIndex(c => /^time$/i.test(c.trim()));
    const iInOut = cols.findIndex(c => /in\/out|inout/i.test(c));

    if (iNo < 0 || iDate < 0 || iInOut < 0) throw new Error('ZKTeco Report format detected but required columns (No., Date, In/Out) are missing.');

    const punches = [];
    for (const row of dataRows) {
      const cells = splitCsv(row);
      if (cells.length < 3) continue;
      const badgeNo   = cells[iNo]?.trim();
      const datePart  = cells[iDate]?.trim() || '';
      const timePart  = iTime >= 0 ? cells[iTime]?.trim() : '';
      const inOut     = cells[iInOut]?.trim();
      if (!badgeNo || !inOut) continue;
      const eventType = toEventType(inOut);
      if (!eventType) continue;
      try {
        punches.push({ badgeNo, eventType, eventTime: toIso(datePart, timePart) });
      } catch { /* skip unparseable row */ }
    }
    if (punches.length === 0) throw new Error('No valid punch records found in ZKTeco Report format.');
    return punches;
  }

  // ── Format 2: Generic (Badge, DateTime, Type) ────────────────────────────────
  const cols   = splitCsv(rawHeader);
  const iBadge = cols.findIndex(c => /badge|no\.|no$|emp|id/i.test(c));
  const iDT    = cols.findIndex(c => /date.*time|datetime|timestamp|time/i.test(c));
  const iType  = cols.findIndex(c => /punch.*type|punchtype|type|in.*out|inout|direction/i.test(c));

  if (iBadge < 0) throw new Error('Could not find a Badge/ID column. Expected headers: Badge, No., EmpID, or similar.');
  if (iDT < 0)    throw new Error('Could not find a DateTime column. Expected headers: DateTime, Timestamp, Time, or similar.');
  if (iType < 0)  throw new Error('Could not find a PunchType column. Expected: PunchType, In/Out, Type, Direction, or similar.');

  const punches = [];
  for (const row of dataRows) {
    const cells    = splitCsv(row);
    if (cells.length < 3) continue;
    const badgeNo  = cells[iBadge]?.trim();
    const dtRaw    = cells[iDT]?.trim();
    const typeRaw  = cells[iType]?.trim();
    if (!badgeNo || !dtRaw || !typeRaw) continue;
    const eventType = toEventType(typeRaw);
    if (!eventType) continue;
    try {
      punches.push({ badgeNo, eventType, eventTime: toIso(dtRaw) });
    } catch { /* skip */ }
  }
  if (punches.length === 0) throw new Error('No valid punch records found. Check that the file contains Badge, DateTime, and PunchType columns.');
  return punches;
}

// ── Punch import ──────────────────────────────────────────────────────────────

/**
 * Batch-inserts matched punch records as clock_events with method='BIOMETRIC'.
 * Skips any punch already recorded at the same employee+type+minute to prevent
 * double-import when the same file is re-uploaded.
 *
 * @param {Array} punches - [{employeeId, eventType, eventTime}] (pre-matched)
 * @returns {{ imported: number, skipped: number, errors: string[] }}
 */
export async function importBiometricPunches(punches) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  if (punches.length === 0) return { imported: 0, skipped: 0, errors: [] };

  // Determine date range for deduplication query
  const times   = punches.map(p => new Date(p.eventTime).getTime());
  const minTime = new Date(Math.min(...times) - 60000).toISOString();
  const maxTime = new Date(Math.max(...times) + 60000).toISOString();

  // Fetch existing BIOMETRIC clock events in that range
  const { data: existing } = await supabase
    .from('clock_events')
    .select('employee_id, event_type, event_time')
    .eq('user_id', user.id)
    .eq('method', 'BIOMETRIC')
    .gte('event_time', minTime)
    .lte('event_time', maxTime);

  // Deduplicate at minute-level (HH:MM) to absorb minor timestamp skew
  const existingSet = new Set(
    (existing || []).map(e => `${e.employee_id}_${e.event_type}_${e.event_time.substring(0, 16)}`)
  );

  const toInsert = [];
  let skipped = 0;

  for (const p of punches) {
    const key = `${p.employeeId}_${p.eventType}_${p.eventTime.substring(0, 16)}`;
    if (existingSet.has(key)) { skipped++; continue; }
    toInsert.push({
      user_id:     user.id,
      employee_id: p.employeeId,
      event_type:  p.eventType,
      event_time:  p.eventTime,
      method:      'BIOMETRIC',
      notes:       'Imported from biometric device',
      entered_by:  user.id,
    });
  }

  if (toInsert.length === 0) return { imported: 0, skipped, errors: [] };

  const { error } = await supabase.from('clock_events').insert(toInsert);
  if (error) throw error;

  return { imported: toInsert.length, skipped, errors: [] };
}
