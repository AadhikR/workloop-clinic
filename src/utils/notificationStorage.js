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

// Clinical credential document types — wider notification window (90d/30d/14d)
const CLINICAL_DOC_TYPES = new Set([
  'DHA Licence', 'DOH Licence', 'MOH Licence',
  'BLS Certificate', 'ACLS Certificate', 'PALS Certificate',
  'NRP Certificate', 'CME Certificate',
]);

/**
 * Generates document / insurance / clinical credential expiry notifications for the admin.
 * Called from Dashboard after data loads. Uses ON CONFLICT DO NOTHING so
 * repeated Dashboard loads do not create duplicate rows.
 *
 * Threshold bands for standard documents:
 *   60d / 30d / 14d
 * Threshold bands for clinical credentials (DHA/DOH Licence, BLS, ACLS, etc.):
 *   90d / 30d / 14d  — wider window because UAE healthcare licences take longer to renew
 */
export async function generateExpiryNotifications(employees, _company, insurancePolicies, allEmpInsurance, allCertifications = [], allEmployeeDocs = []) {
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

  // ── Clinical credential document expiry (DHA/DOH Licence, BLS, ACLS, etc.) ──
  // Uses a 90-day window (vs 60 for standard docs) because healthcare licences take longer to renew.
  const activeEmpIds = new Set(
    (employees || [])
      .filter(e => e.employmentStatus !== 'Terminated' && e.active !== false)
      .map(e => e.id)
  );
  const empNameMap = Object.fromEntries((employees || []).map(e => [e.id, e.name]));

  (allEmployeeDocs || [])
    .filter(doc => CLINICAL_DOC_TYPES.has(doc.documentType) && doc.expiryDate && activeEmpIds.has(doc.employeeId))
    .forEach(doc => {
      const days = Math.ceil((new Date(doc.expiryDate) - today) / (1000 * 60 * 60 * 24));
      if (days < 0 || days > 90) return;
      const thr = days <= 14 ? 14 : days <= 30 ? 30 : 90;
      const empName = empNameMap[doc.employeeId] || 'Employee';
      notifs.push({
        type:               'clinical_credential_expiry',
        title:              `${doc.documentType} expiring — ${empName}`,
        body:               `${empName}'s ${doc.documentType} expires in ${days} day${days !== 1 ? 's' : ''} (${doc.expiryDate}). Renew in the employee Documents tab.`,
        relatedEntityType:  'employee_document',
        relatedEntityId:    `${doc.id}_${thr}d`,
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

  // ── Probation ending soon (Feature 11) ──
  (employees || [])
    .filter(e => e.employmentStatus === 'Probation' && e.active !== false && e.probationEndDate)
    .forEach(emp => {
      const days = Math.ceil((new Date(emp.probationEndDate) - today) / (1000 * 60 * 60 * 24));
      if (days < 0 || days > 14) return;
      const thr = days <= 7 ? 7 : 14;
      notifs.push({
        type:               'probation_ending',
        title:              `Probation ending soon — ${emp.name}`,
        body:               `${emp.name}'s probation period ends in ${days} day${days !== 1 ? 's' : ''} (${emp.probationEndDate}). Confirm, extend, or terminate.`,
        relatedEntityType:  'employee',
        relatedEntityId:    `${emp.id}_probation_${thr}d`,
      });
    });

  // ── Contract expiry (Feature 12) ──
  (employees || [])
    .filter(e => e.contractType === 'Limited' && e.active !== false && e.contractEndDate && e.employmentStatus !== 'Terminated')
    .forEach(emp => {
      const days = Math.ceil((new Date(emp.contractEndDate) - today) / (1000 * 60 * 60 * 24));
      if (days < 0 || days > 60) return;
      const thr = days <= 7 ? 7 : days <= 14 ? 14 : days <= 30 ? 30 : 60;
      notifs.push({
        type:               'contract_expiry',
        title:              `Contract expiring — ${emp.name}`,
        body:               `${emp.name}'s limited contract expires in ${days} day${days !== 1 ? 's' : ''} (${emp.contractEndDate}). Renew, convert to unlimited, or begin offboarding.`,
        relatedEntityType:  'employee',
        relatedEntityId:    `${emp.id}_contract_${thr}d`,
      });
    });

  // ── Certification expiry (Feature 19) ──
  (allCertifications || []).forEach(cert => {
    if (!cert.expiryDate) return;
    // Only alert for employees who are active (employeeName present = admin context)
    const days = Math.ceil((new Date(cert.expiryDate) - today) / (1000 * 60 * 60 * 24));
    if (days < 0 || days > 60) return;
    const thr = days <= 14 ? 14 : days <= 30 ? 30 : 60;
    notifs.push({
      type:               'cert_expiry',
      title:              `Certification expiring — ${cert.employeeName || 'Employee'}`,
      body:               `"${cert.certificationName}" expires in ${days} day${days !== 1 ? 's' : ''} (${cert.expiryDate}).${cert.issuingBody ? ` Issued by ${cert.issuingBody}.` : ''} Renew in Training & Certifications.`,
      relatedEntityType:  'certification',
      relatedEntityId:    `${cert.id}_${thr}d`,
    });
  });

  // ── Professional licence expiry (Feature 7.1) ──
  // Direct licence_authority/licence_expiry fields on employees (separate from document uploads).
  (employees || [])
    .filter(e => e.active !== false && e.employmentStatus !== 'Terminated'
               && e.licenceAuthority && e.licenceAuthority !== 'None' && e.licenceExpiry)
    .forEach(emp => {
      const days = Math.ceil((new Date(emp.licenceExpiry) - today) / (1000 * 60 * 60 * 24));
      if (days < 0 || days > 60) return;
      const thr = days <= 14 ? 14 : days <= 30 ? 30 : 60;
      notifs.push({
        type:               'clinical_licence_expiry',
        title:              `${emp.licenceAuthority} Licence expiring — ${emp.name}`,
        body:               `${emp.name}'s ${emp.licenceAuthority} professional licence expires in ${days} day${days !== 1 ? 's' : ''} (${emp.licenceExpiry}). Renew in the employee's UAE Compliance tab.`,
        relatedEntityType:  'employee',
        relatedEntityId:    `${emp.id}_licence_${thr}d`,
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
