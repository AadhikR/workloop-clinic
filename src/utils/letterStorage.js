/**
 * letterStorage.js — Letter & Certificate Request data layer (Feature 1.3)
 */

import { supabase } from '../lib/supabase';
import { normalizeRequestKind } from './requestUtils';

function dbToRequest(row) {
  return {
    id:              row.id,
    employeeId:      row.employee_id,
    employeeName:    row.employees?.name        || '',
    jobTitle:        row.employees?.job_title   || '',
    department:      row.employees?.department  || '',
    basicSalary:     parseFloat(row.employees?.basic_salary) || 0,
    allowance:       parseFloat(row.employees?.allowance)    || 0,
    joinDate:        row.employees?.join_date   || '',
    requestKind:     normalizeRequestKind(row.request_kind),
    letterType:      row.letter_type,
    purpose:         row.purpose                || '',
    status:          row.status                 || 'pending',
    notes:           row.notes                  || '',
    rejectionReason: row.rejection_reason       || '',
    requestedAt:     row.requested_at,
    completedAt:     row.completed_at           || null,
  };
}

/**
 * Admin: all letter requests for this company.
 * Pass an optional `employees` array (camelCase objects from getEmployees) to
 * enrich each request with the employee's name and job details. If omitted,
 * those fields will be blank — callers should always pass employees.
 */
export async function getLetterRequests(employees = []) {
  const { data, error } = await supabase
    .from('letter_requests')
    .select('*')
    .order('requested_at', { ascending: false });

  if (error) { console.error('getLetterRequests:', error); return []; }
  if (!data?.length) return [];

  // Build a lookup from the already-loaded employees list (avoids a second RLS-scoped query
  // that can silently fail when PostgREST's join behaviour differs across Supabase versions).
  const empMap = Object.fromEntries(employees.map(e => [e.id, e]));

  return data.map(row => {
    const emp = empMap[row.employee_id] ?? null;
    return {
      ...dbToRequest(row),
      employeeName: emp?.name        || '',
      jobTitle:     emp?.jobTitle    || '',
      department:   emp?.department  || '',
      basicSalary:  emp?.basicSalary ?? 0,
      allowance:    emp?.allowance   ?? 0,
      joinDate:     emp?.joinDate    || '',
    };
  });
}

/** Admin: count pending requests (used by Dashboard). */
export async function getPendingLetterCount() {
  const { count, error } = await supabase
    .from('letter_requests')
    .select('id', { count: 'exact', head: true })
    .eq('status', 'pending');

  if (error) { console.error('getPendingLetterCount:', error); return 0; }
  return count || 0;
}

/** Admin: mark a request complete. */
export async function completeLetterRequest(id) {
  const { error } = await supabase
    .from('letter_requests')
    .update({ status: 'completed', completed_at: new Date().toISOString() })
    .eq('id', id);
  if (error) throw error;
}

/** Admin: reject a request with a reason. */
export async function rejectLetterRequest(id, reason) {
  const { error } = await supabase
    .from('letter_requests')
    .update({ status: 'rejected', rejection_reason: reason || '' })
    .eq('id', id);
  if (error) throw error;
}

/** Employee: read own requests. */
export async function getMyLetterRequests() {
  const { data, error } = await supabase
    .from('letter_requests')
    .select('*')
    .order('requested_at', { ascending: false });

  if (error) { console.error('getMyLetterRequests:', error); return []; }
  return (data || []).map(row => ({
    id:              row.id,
    requestKind:     normalizeRequestKind(row.request_kind),
    letterType:      row.letter_type,
    purpose:         row.purpose         || '',
    status:          row.status          || 'pending',
    rejectionReason: row.rejection_reason || '',
    requestedAt:     row.requested_at,
    completedAt:     row.completed_at    || null,
  }));
}
