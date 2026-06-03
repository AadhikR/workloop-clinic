/**
 * notificationStorage.js — In-app notification CRUD and generation helpers.
 *
 * Notification recipients:
 *   - Admin bell  → recipient_user_id = admin uid (document/WPS/insurance expiry alerts)
 *   - Employee bell → recipient_user_id = employee auth_user_id (leave approved/rejected, payslip)
 *
 * Deduplication: UNIQUE (recipient_user_id, type, related_entity_id) with ON CONFLICT DO NOTHING.
 * Expiry alerts embed a threshold suffix (e.g. "uuid_visa_30d") so 60d and 30d alerts are distinct.
 */

import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ─── Read ─────────────────────────────────────────────────────────────────────

/**
 * Returns the caller's notifications, newest first.
 */
export async function getNotifications(limit = 30) {
  const { data, error } = await supabase
    .from('notifications')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(limit);
  if (error) { console.error('getNotifications:', error); return []; }
  return (data || []).map(dbToNotification);
}

/**
 * Returns the number of unread notifications for the caller.
 */
export async function getUnreadCount() {
  const { count, error } = await supabase
    .from('notifications')
    .select('id', { count: 'exact', head: true })
    .is('read_at', null);
  if (error) { console.error('getUnreadCount:', error); return 0; }
  return count || 0;
}

// ─── Write ────────────────────────────────────────────────────────────────────

/**
 * Marks a single notification as read.
 */
export async function markNotificationRead(id) {
  const { error } = await supabase
    .from('notifications')
    .update({ read_at: new Date().toISOString() })
    .eq('id', id);
  if (error) throw error;
}

/**
 * Marks all of the caller's unread notifications as read.
 */
export async function markAllNotificationsRead() {
  const { error } = await supabase
    .from('notifications')
    .update({ read_at: new Date().toISOString() })
    .is('read_at', null);
  if (error) throw error;
}

/**
 * Creates a single notification. Uses ON CONFLICT DO NOTHING so duplicate
 * (recipient, type, related_entity_id) combinations are silently skipped.
 *
 * @param {object} notif
 * @param {string} [notif.recipientUserId]   — defaults to caller's uid (admin-to-self)
 * @param {string} notif.type
 * @param {string} notif.title
 * @param {string} [notif.body]
 * @param {string} [notif.relatedEntityType]
 * @param {string} [notif.relatedEntityId]
 */
export async function createNotification(notif) {
  const user = await getSessionUser();
  if (!user) return;

  const row = {
    user_id:             user.id,
    recipient_user_id:   notif.recipientUserId || user.id,
    type:                notif.type,
    title:               notif.title,
    body:                notif.body || '',
    related_entity_type: notif.relatedEntityType || '',
    related_entity_id:   notif.relatedEntityId || '',
  };

  const { error } = await supabase
    .from('notifications')
    .upsert(row, { onConflict: 'recipient_user_id,type,related_entity_id', ignoreDuplicates: true });

  if (error) console.error('createNotification:', error);
}

/**
 * Batch-creates notifications. Uses ON CONFLICT DO NOTHING for all rows.
 */
export async function createNotifications(notifs) {
  if (!notifs?.length) return;
  const user = await getSessionUser();
  if (!user) return;

  const rows = notifs.map(n => ({
    user_id:             user.id,
    recipient_user_id:   n.recipientUserId || user.id,
    type:                n.type,
    title:               n.title,
    body:                n.body || '',
    related_entity_type: n.relatedEntityType || '',
    related_entity_id:   n.relatedEntityId || '',
  }));

  const { error } = await supabase
    .from('notifications')
    .upsert(rows, { onConflict: 'recipient_user_id,type,related_entity_id', ignoreDuplicates: true });

  if (error) console.error('createNotifications:', error);
}

// ─── Expiry sweep ─────────────────────────────────────────────────────────────

/**
 * Generates document / insurance / WPS expiry notifications for the admin.
 * Called from Dashboard after data loads. Uses ON CONFLICT DO NOTHING so
 * repeated Dashboard loads do not create duplicate rows.
 *
 * Threshold bands (embedded in related_entity_id for deduplication):
 *   60d → fires once when ≤60 days remain
 *   30d → fires again when ≤30 days remain
 *   14d → fires again when ≤14 days remain
 */
export async function generateExpiryNotifications(employees, _company, insurancePolicies, allEmpInsurance) {
  const today = new Date();
  const notifs = [];

  // ── Employee document expiry ──
  (employees || [])
    .filter(e => e.employmentStatus !== 'Terminated' && e.active !== false)
    .forEach(emp => {
      [
        { key: 'visa',        label: 'Visa',        date: emp.visaExpiry },
        { key: 'passport',    label: 'Passport',    date: emp.passportExpiry },
        { key: 'emirates_id', label: 'Emirates ID', date: emp.emiratesIdExpiry },
        { key: 'labour_card', label: 'Labour Card', date: emp.labourCardExpiry },
      ].forEach(({ key, label, date }) => {
        if (!date) return;
        const days = Math.ceil((new Date(date) - today) / (1000 * 60 * 60 * 24));
        if (days < 0 || days > 60) return;
        const thr = days <= 14 ? 14 : days <= 30 ? 30 : 60;
        notifs.push({
          type:               'document_expiry',
          title:              `${label} expiring — ${emp.name}`,
          body:               `${label} expires in ${days} day${days !== 1 ? 's' : ''} (${date}). Update in the employee profile.`,
          relatedEntityType:  'employee',
          relatedEntityId:    `${emp.id}_${key}_${thr}d`,
        });
      });
    });

  // ── Employee insurance coverage expiry ──
  (allEmpInsurance || []).forEach(ins => {
    if (!ins.expiryDate) return;
    const emp = (employees || []).find(e => e.id === ins.employeeId);
    if (!emp || emp.employmentStatus === 'Terminated') return;
    const days = Math.ceil((new Date(ins.expiryDate) - today) / (1000 * 60 * 60 * 24));
    if (days < 0 || days > 60) return;
    const thr = days <= 30 ? 30 : 60;
    notifs.push({
      type:               'insurance_expiry',
      title:              `Insurance expiring — ${emp.name}`,
      body:               `Health insurance coverage expires in ${days} day${days !== 1 ? 's' : ''}.`,
      relatedEntityType:  'employee_insurance',
      relatedEntityId:    `${ins.employeeId}_${thr}d`,
    });
  });

  // ── Insurance policy renewal ──
  (insurancePolicies || []).forEach(pol => {
    if (!pol.renewalDate) return;
    const days = Math.ceil((new Date(pol.renewalDate) - today) / (1000 * 60 * 60 * 24));
    if (days < 0 || days > 60) return;
    const thr = days <= 30 ? 30 : 60;
    notifs.push({
      type:               'policy_renewal',
      title:              `Policy renewal — ${pol.insurerName}`,
      body:               `${pol.insurerName}${pol.tierName ? ` (${pol.tierName})` : ''} policy renews in ${days} day${days !== 1 ? 's' : ''}.`,
      relatedEntityType:  'insurance_policy',
      relatedEntityId:    `${pol.id}_${thr}d`,
    });
  });

  if (notifs.length > 0) {
    await createNotifications(notifs);
  }
}

// ─── Shape converter ──────────────────────────────────────────────────────────

function dbToNotification(row) {
  return {
    id:                row.id,
    type:              row.type,
    title:             row.title,
    body:              row.body,
    relatedEntityType: row.related_entity_type,
    relatedEntityId:   row.related_entity_id,
    readAt:            row.read_at,
    createdAt:         row.created_at,
  };
}
