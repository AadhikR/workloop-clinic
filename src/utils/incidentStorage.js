/**
 * incidentStorage.js — Feature 7.3: Clinical incident reporting.
 * CRUD for the incident_reports table.
 */
import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) throw new Error('Not authenticated');
  return session.user;
}

export const INCIDENT_TYPES = [
  { value: 'patient_safety',   label: 'Patient Safety Event' },
  { value: 'medication_error', label: 'Medication Error' },
  { value: 'injury',           label: 'Staff Injury' },
  { value: 'needlestick',      label: 'Needlestick / Sharps' },
  { value: 'infection',        label: 'Infection Control' },
  { value: 'equipment',        label: 'Equipment Failure' },
  { value: 'near_miss',        label: 'Near Miss' },
  { value: 'workplace',        label: 'Workplace Hazard' },
  { value: 'other',            label: 'Other' },
];

export const INCIDENT_SEVERITY = [
  { value: 'low',      label: 'Low',      badge: 'badge-green' },
  { value: 'moderate', label: 'Moderate', badge: 'badge-amber' },
  { value: 'high',     label: 'High',     badge: 'badge-red'   },
  { value: 'critical', label: 'Critical', badge: 'badge-red'   },
];

export const INCIDENT_STATUS = [
  { value: 'open',           label: 'Open',           badge: 'badge-blue'  },
  { value: 'investigating',  label: 'Investigating',  badge: 'badge-amber' },
  { value: 'closed',         label: 'Closed',         badge: 'badge-green' },
];

function dbToIncident(row) {
  return {
    id:               row.id,
    companyId:        row.company_id,
    incidentDate:     row.incident_date,
    incidentTime:     row.incident_time || '',
    location:         row.location || '',
    department:       row.department || '',
    incidentType:     row.incident_type,
    severity:         row.severity,
    description:      row.description || '',
    reportedById:     row.reported_by_id,
    reportedByName:   row.reported_by?.name || '',
    involvedEmpId:    row.involved_emp_id,
    involvedEmpName:  row.involved_emp?.name || '',
    immediateAction:  row.immediate_action || '',
    rootCause:        row.root_cause || '',
    correctiveAction: row.corrective_action || '',
    status:           row.status,
    closedDate:       row.closed_date,
    closedBy:         row.closed_by || '',
    notes:            row.notes || '',
    createdAt:        row.created_at,
  };
}

export async function getIncidents(companyId = null) {
  let q = supabase
    .from('incident_reports')
    .select('*, reported_by:employees!incident_reports_reported_by_id_fkey(name), involved_emp:employees!incident_reports_involved_emp_id_fkey(name)')
    .order('incident_date', { ascending: false });
  if (companyId) q = q.eq('company_id', companyId);
  const { data, error } = await q;
  if (error) { console.error('getIncidents:', error); return []; }
  return (data || []).map(dbToIncident);
}

export async function saveIncident(incident, companyId = null) {
  const user = await getSessionUser();
  const row = {
    user_id:           user.id,
    company_id:        incident.companyId ?? companyId,
    incident_date:     incident.incidentDate,
    incident_time:     incident.incidentTime || null,
    location:          incident.location || '',
    department:        incident.department || '',
    incident_type:     incident.incidentType || 'other',
    severity:          incident.severity || 'low',
    description:       incident.description || '',
    reported_by_id:    incident.reportedById || null,
    involved_emp_id:   incident.involvedEmpId || null,
    immediate_action:  incident.immediateAction || '',
    root_cause:        incident.rootCause || '',
    corrective_action: incident.correctiveAction || '',
    status:            incident.status || 'open',
    closed_date:       incident.status === 'closed' ? (incident.closedDate || new Date().toISOString().slice(0, 10)) : null,
    closed_by:         incident.closedBy || '',
    notes:             incident.notes || '',
  };
  if (incident.id) {
    const { data, error } = await supabase
      .from('incident_reports').update(row).eq('id', incident.id)
      .select('*, reported_by:employees!incident_reports_reported_by_id_fkey(name), involved_emp:employees!incident_reports_involved_emp_id_fkey(name)')
      .single();
    if (error) throw error;
    return dbToIncident(data);
  }
  const { data, error } = await supabase
    .from('incident_reports').insert(row)
    .select('*, reported_by:employees!incident_reports_reported_by_id_fkey(name), involved_emp:employees!incident_reports_involved_emp_id_fkey(name)')
    .single();
  if (error) throw error;
  return dbToIncident(data);
}

export async function deleteIncident(id) {
  const { error } = await supabase.from('incident_reports').delete().eq('id', id);
  if (error) throw error;
}
