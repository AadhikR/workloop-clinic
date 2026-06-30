import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user ?? null;
  if (!user) throw new Error('Not authenticated');
  return user;
}

// ── Default clinic appraisal sections ────────────────────────────────────────
export const DEFAULT_SECTIONS = [
  { section_name: 'Clinical Competency',        weight: 2.0, sort_order: 0 },
  { section_name: 'Patient Care Quality',       weight: 2.0, sort_order: 1 },
  { section_name: 'Communication & Teamwork',   weight: 1.5, sort_order: 2 },
  { section_name: 'Punctuality & Attendance',   weight: 1.0, sort_order: 3 },
  { section_name: 'Professional Development',   weight: 1.0, sort_order: 4 },
];

export const RATING_LABELS = {
  1: 'Needs Improvement',
  2: 'Developing',
  3: 'Meeting Expectations',
  4: 'Exceeding Expectations',
  5: 'Outstanding',
};

// ── Shape converters ──────────────────────────────────────────────────────────
function dbToCycle(row) {
  return {
    id:         row.id,
    userId:     row.user_id,
    name:       row.name,
    reviewFrom: row.review_from,
    reviewTo:   row.review_to,
    status:     row.status,
    createdAt:  row.created_at,
  };
}

function cycleToDb(cycle, userId) {
  return {
    user_id:     userId,
    name:        cycle.name,
    review_from: cycle.reviewFrom,
    review_to:   cycle.reviewTo,
    status:      cycle.status || 'draft',
  };
}

function dbToAppraisal(row) {
  return {
    id:                row.id,
    userId:            row.user_id,
    cycleId:           row.cycle_id,
    employeeId:        row.employee_id,
    overallRating:     row.overall_rating != null ? parseFloat(row.overall_rating) : null,
    selfRating:        row.self_rating    != null ? parseFloat(row.self_rating)    : null,
    status:            row.status,
    reviewerComments:  row.reviewer_comments,
    developmentPlan:   row.development_plan,
    reviewedAt:        row.reviewed_at,
    reviewedBy:        row.reviewed_by,
    createdAt:         row.created_at,
    updatedAt:         row.updated_at,
    // joined data
    sections:          (row.appraisal_sections || []).map(dbToSection),
  };
}

function dbToSection(row) {
  return {
    id:          row.id,
    appraisalId: row.appraisal_id,
    sectionName: row.section_name,
    weight:      parseFloat(row.weight) || 1,
    rating:      row.rating     != null ? parseFloat(row.rating)      : null,
    selfRating:  row.self_rating != null ? parseFloat(row.self_rating) : null,
    comments:    row.comments,
    sortOrder:   row.sort_order ?? 0,
  };
}

// ── Cycles ────────────────────────────────────────────────────────────────────
export async function getAppraisalCycles() {
  const user = await getSessionUser();
  const { data, error } = await supabase
    .from('appraisal_cycles')
    .select('*')
    .eq('user_id', user.id)
    .order('review_from', { ascending: false });
  if (error) { console.error('getAppraisalCycles:', error); return []; }
  return (data || []).map(dbToCycle);
}

export async function saveAppraisalCycle(cycle) {
  const user  = await getSessionUser();
  const row   = cycleToDb(cycle, user.id);
  let result;
  if (cycle.id) {
    const { data, error } = await supabase
      .from('appraisal_cycles')
      .update({ ...row, updated_at: new Date().toISOString() })
      .eq('id', cycle.id).eq('user_id', user.id)
      .select().single();
    if (error) throw error;
    result = data;
  } else {
    const { data, error } = await supabase
      .from('appraisal_cycles')
      .insert(row).select().single();
    if (error) throw error;
    result = data;
  }
  return dbToCycle(result);
}

export async function deleteAppraisalCycle(id) {
  const user = await getSessionUser();
  const { error } = await supabase
    .from('appraisal_cycles')
    .delete().eq('id', id).eq('user_id', user.id);
  if (error) throw error;
}

// ── Appraisals ────────────────────────────────────────────────────────────────
export async function getAppraisalsForCycle(cycleId) {
  const { data, error } = await supabase
    .from('appraisals')
    .select('*, appraisal_sections(*)')
    .eq('cycle_id', cycleId)
    .order('created_at');
  if (error) { console.error('getAppraisalsForCycle:', error); return []; }
  return (data || []).map(dbToAppraisal);
}

export async function getMyAppraisals() {
  const { data, error } = await supabase
    .from('appraisals')
    .select('*, appraisal_sections(*), appraisal_cycles(name, review_from, review_to)')
    .order('created_at', { ascending: false });
  if (error) { console.error('getMyAppraisals:', error); return []; }
  return (data || []).map(row => ({
    ...dbToAppraisal(row),
    cycleName:  row.appraisal_cycles?.name,
    reviewFrom: row.appraisal_cycles?.review_from,
    reviewTo:   row.appraisal_cycles?.review_to,
  }));
}

/** Returns appraisals for the calling manager's direct reports (uses manager RLS policy from 033).
 *  Joins employees(name, job_title) — requires policy from 035_manager_employee_read.sql.
 *  Excludes the manager's own appraisal row, which is also visible via the employee self-read
 *  policy and would otherwise leak into "Team Appraisals". */
export async function getMyTeamAppraisals() {
  // Get own employee_id so we can exclude our own appraisal from the team view
  const { data: selfId } = await supabase.rpc('get_manager_employee_id');

  let q = supabase
    .from('appraisals')
    .select('*, appraisal_sections(*), appraisal_cycles(name, review_from, review_to), employees(name, job_title)')
    .order('created_at', { ascending: false });

  if (selfId) q = q.neq('employee_id', selfId);

  const { data, error } = await q;
  if (error) { console.error('getMyTeamAppraisals:', error); return []; }
  return (data || []).map(row => ({
    ...dbToAppraisal(row),
    cycleName:    row.appraisal_cycles?.name,
    reviewFrom:   row.appraisal_cycles?.review_from,
    reviewTo:     row.appraisal_cycles?.review_to,
    employeeName: row.employees?.name     ?? null,
    jobTitle:     row.employees?.job_title ?? null,
  }));
}

/** Manager rates a single section (uses appraisal_sections_manager_update RLS policy). */
export async function managerRateSection(sectionId, { rating, comments }) {
  const { error } = await supabase
    .from('appraisal_sections')
    .update({ rating: parseInt(rating), comments: comments || null })
    .eq('id', sectionId);
  if (error) throw error;
}

/**
 * Create appraisals for employees that don't yet have one in this cycle.
 * Seeds default sections for each new appraisal.
 */
export async function createAppraisalsForCycle(cycleId, employeeIds) {
  const user = await getSessionUser();

  // Find which employees already have an appraisal in this cycle
  const { data: existing } = await supabase
    .from('appraisals')
    .select('employee_id')
    .eq('cycle_id', cycleId);
  const existingIds = new Set((existing || []).map(r => r.employee_id));
  const toCreate = employeeIds.filter(id => !existingIds.has(id));
  if (!toCreate.length) return [];

  const { data, error } = await supabase
    .from('appraisals')
    .insert(toCreate.map(eid => ({
      user_id: user.id, cycle_id: cycleId, employee_id: eid,
    })))
    .select();
  if (error) throw error;

  // Seed default sections for each new appraisal
  const sectionRows = (data || []).flatMap(ap =>
    DEFAULT_SECTIONS.map(s => ({ ...s, appraisal_id: ap.id }))
  );
  if (sectionRows.length) {
    const { error: sErr } = await supabase.from('appraisal_sections').insert(sectionRows);
    if (sErr) throw sErr;
  }
  return (data || []).map(dbToAppraisal);
}

/**
 * Save an appraisal review: updates section ratings + computes overall rating.
 * Sections array: [{ id, rating, selfRating, comments }]
 */
export async function saveAppraisalReview(appraisalId, { sections, reviewerComments, developmentPlan, reviewedBy }) {
  const user = await getSessionUser();

  // Upsert sections
  for (const sec of sections) {
    const { error } = await supabase
      .from('appraisal_sections')
      .update({
        rating:      sec.rating      ?? null,
        self_rating: sec.selfRating  ?? null,
        comments:    sec.comments    || null,
      })
      .eq('id', sec.id);
    if (error) throw error;
  }

  // Compute weighted average of non-null ratings
  const rated = sections.filter(s => s.rating != null);
  let overallRating = null;
  if (rated.length > 0) {
    const totalWeight  = rated.reduce((s, sec) => s + (sec.weight || 1), 0);
    const weightedSum  = rated.reduce((s, sec) => s + sec.rating * (sec.weight || 1), 0);
    overallRating = Math.round((weightedSum / totalWeight) * 10) / 10;
  }

  const hasAllRatings = sections.length > 0 && sections.every(s => s.rating != null);

  const { data, error } = await supabase
    .from('appraisals')
    .update({
      overall_rating:    overallRating,
      reviewer_comments: reviewerComments || null,
      development_plan:  developmentPlan  || null,
      reviewed_by:       reviewedBy       || null,
      reviewed_at:       hasAllRatings ? new Date().toISOString() : null,
      status:            hasAllRatings ? 'reviewed' : 'pending',
      updated_at:        new Date().toISOString(),
    })
    .eq('id', appraisalId).eq('user_id', user.id)
    .select('*, appraisal_sections(*)').single();
  if (error) throw error;
  return dbToAppraisal(data);
}

export async function calibrateAppraisal(appraisalId, overallRating) {
  const user = await getSessionUser();
  const { data, error } = await supabase
    .from('appraisals')
    .update({ overall_rating: overallRating, status: 'calibrated', updated_at: new Date().toISOString() })
    .eq('id', appraisalId).eq('user_id', user.id)
    .select('*, appraisal_sections(*)').single();
  if (error) throw error;
  return dbToAppraisal(data);
}

export async function deleteAppraisal(id) {
  const user = await getSessionUser();
  const { error } = await supabase
    .from('appraisals')
    .delete().eq('id', id).eq('user_id', user.id);
  if (error) throw error;
}
