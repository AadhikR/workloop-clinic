/**
 * trainingStorage.js — Training records and certifications CRUD.
 * Feature 19: Training & Certification Records.
 *
 * Admin has full CRUD via user_id = auth.uid() RLS policy.
 * Employees self-read via employee_id IN (SELECT id FROM employees WHERE auth_user_id = auth.uid()).
 * No RPCs needed — admin manages all records; employees only read.
 *
 * NEVER use supabase.auth.getUser() — use getSessionUser() (getSession-based) to avoid
 * refresh-token rotation in Playwright tests.
 */

import { supabase } from '../lib/supabase';

// ─── Private helper ───────────────────────────────────────────────────────────

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user ?? null;
}

// ─── Shape converters ─────────────────────────────────────────────────────────

function dbToTraining(row) {
  return {
    id:             row.id,
    employeeId:     row.employee_id,
    employeeName:   row.employees?.name ?? '',
    trainingTitle:  row.training_title,
    trainingType:   row.training_type,
    provider:       row.provider,
    startDate:      row.start_date,
    endDate:        row.end_date,
    durationHours:  row.duration_hours != null ? parseFloat(row.duration_hours) : null,
    cost:           parseFloat(row.cost) || 0,
    status:         row.status,
    score:          row.score,
    passed:         row.passed,
    certificateUrl: row.certificate_url,
    notes:          row.notes,
    isCme:          row.is_cme ?? false,
    createdAt:      row.created_at,
  };
}

function dbToCertification(row) {
  return {
    id:                row.id,
    employeeId:        row.employee_id,
    employeeName:      row.employees?.name ?? '',
    certificationName: row.certification_name,
    issuingBody:       row.issuing_body,
    certificateNo:     row.certificate_no,
    issuedDate:        row.issued_date,
    expiryDate:        row.expiry_date,
    certificateUrl:    row.certificate_url,
    notes:             row.notes,
    status:            row.status || 'verified',
    createdAt:         row.created_at,
  };
}

// ─── Training Records — Admin ─────────────────────────────────────────────────

/**
 * Admin: fetch all training records, newest first.
 * Optionally filter by a single employeeId.
 */
export async function getTrainingRecords(employeeId = null) {
  let q = supabase
    .from('training_records')
    .select('*, employees(name)')
    .order('start_date', { ascending: false });
  if (employeeId) q = q.eq('employee_id', employeeId);
  const { data, error } = await q;
  if (error) { console.error('getTrainingRecords:', error); return []; }
  return (data || []).map(dbToTraining);
}

/**
 * Create or update a training record.
 * Pass { id } on the object to update; omit id to insert.
 * Returns the saved record with employeeName populated.
 */
export async function saveTrainingRecord(rec) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:         user.id,
    employee_id:     rec.employeeId,
    training_title:  rec.trainingTitle  || '',
    training_type:   rec.trainingType   || 'external',
    provider:        rec.provider       || '',
    start_date:      rec.startDate      || null,
    end_date:        rec.endDate        || null,
    duration_hours:  rec.durationHours  ? parseFloat(rec.durationHours) : null,
    cost:            parseFloat(rec.cost) || 0,
    status:          rec.status         || 'planned',
    score:           rec.score          || '',
    passed:          rec.passed         ?? null,
    certificate_url: rec.certificateUrl || '',
    notes:           rec.notes          || '',
    is_cme:          rec.isCme          ?? false,
  };

  if (rec.id) {
    const { data, error } = await supabase
      .from('training_records')
      .update(row)
      .eq('id', rec.id)
      .select('*, employees(name)')
      .single();
    if (error) throw error;
    return dbToTraining(data);
  } else {
    const { data, error } = await supabase
      .from('training_records')
      .insert(row)
      .select('*, employees(name)')
      .single();
    if (error) throw error;
    return dbToTraining(data);
  }
}

/**
 * Delete a training record by id.
 */
export async function deleteTrainingRecord(id) {
  const { error } = await supabase
    .from('training_records')
    .delete()
    .eq('id', id);
  if (error) throw error;
}

// ─── Training Records — Employee self-service ─────────────────────────────────

/**
 * Employee portal: fetch own training records.
 * Uses the training_records_employee_read RLS policy — no admin scope.
 */
export async function getEmployeeTrainingRecords(employeeId) {
  const { data, error } = await supabase
    .from('training_records')
    .select('*')
    .eq('employee_id', employeeId)
    .order('start_date', { ascending: false });
  if (error) { console.error('getEmployeeTrainingRecords:', error); return []; }
  return (data || []).map(r => dbToTraining({ ...r, employees: null }));
}

// ─── Certifications — Admin ───────────────────────────────────────────────────

/**
 * Admin: fetch certifications, ordered by expiry date (soonest first, nulls last).
 * Optionally filter by a single employeeId.
 */
export async function getCertifications(employeeId = null) {
  let q = supabase
    .from('certifications')
    .select('*, employees(name)')
    .order('expiry_date', { ascending: true, nullsFirst: false });
  if (employeeId) q = q.eq('employee_id', employeeId);
  const { data, error } = await q;
  if (error) { console.error('getCertifications:', error); return []; }
  return (data || []).map(dbToCertification);
}

/**
 * Admin: fetch all certifications for all employees (no employee filter).
 * Used by Dashboard for the cert expiry alert and generateExpiryNotifications.
 */
export async function getAllCertifications() {
  const { data, error } = await supabase
    .from('certifications')
    .select('*, employees(name)')
    .order('expiry_date', { ascending: true, nullsFirst: false });
  if (error) { console.error('getAllCertifications:', error); return []; }
  return (data || []).map(dbToCertification);
}

/**
 * Create or update a certification record.
 * Pass { id } on the object to update; omit id to insert.
 */
export async function saveCertification(cert) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');

  const row = {
    user_id:            user.id,
    employee_id:        cert.employeeId,
    certification_name: cert.certificationName || '',
    issuing_body:       cert.issuingBody        || '',
    certificate_no:     cert.certificateNo      || '',
    issued_date:        cert.issuedDate         || null,
    expiry_date:        cert.expiryDate         || null,
    certificate_url:    cert.certificateUrl     || '',
    notes:              cert.notes              || '',
    status:             cert.status             || 'verified',
  };

  if (cert.id) {
    const { data, error } = await supabase
      .from('certifications')
      .update(row)
      .eq('id', cert.id)
      .select('*, employees(name)')
      .single();
    if (error) throw error;
    return dbToCertification(data);
  } else {
    const { data, error } = await supabase
      .from('certifications')
      .insert(row)
      .select('*, employees(name)')
      .single();
    if (error) throw error;
    return dbToCertification(data);
  }
}

/**
 * Delete a certification record by id.
 */
export async function deleteCertification(id) {
  const { error } = await supabase
    .from('certifications')
    .delete()
    .eq('id', id);
  if (error) throw error;
}

// ─── Certifications — Employee self-service ───────────────────────────────────

/**
 * Employee portal: fetch own certifications, soonest-expiring first.
 * Uses the certifications_employee_read RLS policy — no admin scope.
 */
export async function getEmployeeCertifications(employeeId) {
  const { data, error } = await supabase
    .from('certifications')
    .select('*')
    .eq('employee_id', employeeId)
    .order('expiry_date', { ascending: true, nullsFirst: false });
  if (error) { console.error('getEmployeeCertifications:', error); return []; }
  return (data || []).map(r => dbToCertification({ ...r, employees: null }));
}

// ─── Manager — Training for direct reports ──────────────────────────────────

/**
 * Manager: fetch training records for direct reports.
 * Uses training_records_manager_all RLS policy (migration 040).
 */
export async function getTeamTrainingRecords() {
  const { data: selfId } = await supabase.rpc('get_manager_employee_id');
  let q = supabase
    .from('training_records')
    .select('*, employees(name)')
    .order('start_date', { ascending: false });
  if (selfId) q = q.neq('employee_id', selfId);
  const { data, error } = await q;
  if (error) { console.error('getTeamTrainingRecords:', error); return []; }
  return (data || []).map(dbToTraining);
}

/**
 * Manager: fetch certifications for direct reports.
 * Uses certifications_manager_all RLS policy (migration 040).
 */
export async function getTeamCertifications() {
  const { data: selfId } = await supabase.rpc('get_manager_employee_id');
  let q = supabase
    .from('certifications')
    .select('*, employees(name)')
    .order('expiry_date', { ascending: true, nullsFirst: false });
  if (selfId) q = q.neq('employee_id', selfId);
  const { data, error } = await q;
  if (error) { console.error('getTeamCertifications:', error); return []; }
  return (data || []).map(dbToCertification);
}

/**
 * Manager: save training record for a direct report.
 * user_id is set to the manager's auth uid (RLS allows via reporting_manager_id chain).
 */
export async function saveTeamTrainingRecord(rec) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:         user.id,
    employee_id:     rec.employeeId,
    training_title:  rec.trainingTitle  || '',
    training_type:   rec.trainingType   || 'external',
    provider:        rec.provider       || '',
    start_date:      rec.startDate      || null,
    end_date:        rec.endDate        || null,
    duration_hours:  rec.durationHours  ? parseFloat(rec.durationHours) : null,
    cost:            parseFloat(rec.cost) || 0,
    status:          rec.status         || 'planned',
    score:           rec.score          || '',
    passed:          rec.passed         ?? null,
    certificate_url: rec.certificateUrl || '',
    notes:           rec.notes          || '',
    is_cme:          rec.isCme          ?? false,
  };
  if (rec.id) {
    const { data, error } = await supabase
      .from('training_records').update(row).eq('id', rec.id)
      .select('*, employees(name)').single();
    if (error) throw error;
    return dbToTraining(data);
  }
  const { data, error } = await supabase
    .from('training_records').insert(row)
    .select('*, employees(name)').single();
  if (error) throw error;
  return dbToTraining(data);
}

/**
 * Manager: delete a training record for a direct report.
 */
export async function deleteTeamTrainingRecord(id) {
  const { error } = await supabase.from('training_records').delete().eq('id', id);
  if (error) throw error;
}

/**
 * Manager: save certification for a direct report.
 */
export async function saveTeamCertification(cert) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:            user.id,
    employee_id:        cert.employeeId,
    certification_name: cert.certificationName || '',
    issuing_body:       cert.issuingBody       || '',
    certificate_no:     cert.certificateNo     || '',
    issued_date:        cert.issuedDate        || null,
    expiry_date:        cert.expiryDate        || null,
    certificate_url:    cert.certificateUrl    || '',
    notes:              cert.notes             || '',
  };
  if (cert.id) {
    const { data, error } = await supabase
      .from('certifications').update(row).eq('id', cert.id)
      .select('*, employees(name)').single();
    if (error) throw error;
    return dbToCertification(data);
  }
  const { data, error } = await supabase
    .from('certifications').insert(row)
    .select('*, employees(name)').single();
  if (error) throw error;
  return dbToCertification(data);
}

/**
 * Manager: delete a certification for a direct report.
 */
export async function deleteTeamCertification(id) {
  const { error } = await supabase.from('certifications').delete().eq('id', id);
  if (error) throw error;
}

// ─── Employee self-service — create/update training ─────────────────────────

/**
 * Employee: create a training record for self (self-enrollment).
 * Uses training_records_employee_insert RLS policy (migration 040).
 */
export async function employeeSaveTrainingRecord(rec) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:         user.id,
    employee_id:     rec.employeeId,
    training_title:  rec.trainingTitle  || '',
    training_type:   rec.trainingType   || 'external',
    provider:        rec.provider       || '',
    start_date:      rec.startDate      || null,
    end_date:        rec.endDate        || null,
    duration_hours:  rec.durationHours  ? parseFloat(rec.durationHours) : null,
    cost:            parseFloat(rec.cost) || 0,
    status:          rec.status         || 'planned',
    score:           rec.score          || '',
    passed:          rec.passed         ?? null,
    certificate_url: rec.certificateUrl || '',
    notes:           rec.notes          || '',
    is_cme:          rec.isCme          ?? false,
  };
  if (rec.id) {
    const { data, error } = await supabase
      .from('training_records').update(row).eq('id', rec.id)
      .select('*').single();
    if (error) throw error;
    return dbToTraining({ ...data, employees: null });
  }
  const { data, error } = await supabase
    .from('training_records').insert(row)
    .select('*').single();
  if (error) throw error;
  return dbToTraining({ ...data, employees: null });
}

// ─── Employee self-service — certifications ─────────────────────────────────

/**
 * Employee: submit a certification for review (status = pending_review).
 * Uses certifications_employee_insert / certifications_employee_update RLS (migration 042).
 */
export async function employeeSaveCertification(cert) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:            user.id,
    employee_id:        cert.employeeId,
    certification_name: cert.certificationName || '',
    issuing_body:       cert.issuingBody       || '',
    certificate_no:     cert.certificateNo     || '',
    issued_date:        cert.issuedDate        || null,
    expiry_date:        cert.expiryDate        || null,
    certificate_url:    cert.certificateUrl    || '',
    notes:              cert.notes             || '',
    status:             'pending_review',
  };
  if (cert.id) {
    const { data, error } = await supabase
      .from('certifications').update(row).eq('id', cert.id)
      .select('*').single();
    if (error) throw error;
    return dbToCertification({ ...data, employees: null });
  }
  const { data, error } = await supabase
    .from('certifications').insert(row)
    .select('*').single();
  if (error) throw error;
  return dbToCertification({ ...data, employees: null });
}

// ─── CME Tracking ────────────────────────────────────────────────────────────

function dbToCmeReq(row) {
  return {
    id:            row.id,
    employeeId:    row.employee_id,
    employeeName:  row.employees?.name ?? '',
    year:          row.year,
    requiredHours: parseFloat(row.required_hours) || 25,
    notes:         row.notes || '',
  };
}

export async function getCmeRequirements(year = null) {
  let q = supabase
    .from('cme_requirements')
    .select('*, employees(name)')
    .order('year', { ascending: false });
  if (year) q = q.eq('year', year);
  const { data, error } = await q;
  if (error) { console.error('getCmeRequirements:', error); return []; }
  return (data || []).map(dbToCmeReq);
}

export async function saveCmeRequirement(req) {
  const user = await getSessionUser();
  if (!user) throw new Error('Not authenticated');
  const row = {
    user_id:        user.id,
    employee_id:    req.employeeId,
    year:           req.year,
    required_hours: parseFloat(req.requiredHours) || 25,
    notes:          req.notes || '',
  };
  if (req.id) {
    const { data, error } = await supabase
      .from('cme_requirements').update(row).eq('id', req.id)
      .select('*, employees(name)').single();
    if (error) throw error;
    return dbToCmeReq(data);
  }
  const { data, error } = await supabase
    .from('cme_requirements').insert(row)
    .select('*, employees(name)').single();
  if (error) throw error;
  return dbToCmeReq(data);
}

export async function deleteCmeRequirement(id) {
  const { error } = await supabase.from('cme_requirements').delete().eq('id', id);
  if (error) throw error;
}

export async function getCmeTrainingRecords(year = null) {
  let q = supabase
    .from('training_records')
    .select('*, employees(name)')
    .eq('is_cme', true)
    .order('start_date', { ascending: false });
  if (year) {
    q = q.gte('start_date', `${year}-01-01`).lte('start_date', `${year}-12-31`);
  }
  const { data, error } = await q;
  if (error) { console.error('getCmeTrainingRecords:', error); return []; }
  return (data || []).map(dbToTraining);
}

/**
 * Manager: fetch list of direct reports (id + name) for employee dropdown.
 */
export async function getManagerDirectReports() {
  const { data: selfId } = await supabase.rpc('get_manager_employee_id');
  if (!selfId) return [];
  const { data, error } = await supabase
    .from('employees')
    .select('id, name, job_title')
    .eq('reporting_manager_id', selfId)
    .eq('active', true)
    .order('name');
  if (error) { console.error('getManagerDirectReports:', error); return []; }
  return data || [];
}
