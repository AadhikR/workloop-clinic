/**
 * staffingStorage.js — Feature 7.2: Department minimum-staffing rules
 * CRUD for the department_staffing_rules table.
 */
import { supabase } from '../lib/supabase';

async function getSessionUser() {
  const { data: { session } } = await supabase.auth.getSession();
  const user = session?.user ?? null;
  if (!user) throw new Error('Not authenticated');
  return user;
}

function dbToRule(row) {
  return {
    id:            row.id,
    department:    row.department,
    shiftCategory: row.shift_category,
    minStaff:      row.min_staff ?? 1,
    effectiveFrom: row.effective_from ?? '',
    effectiveTo:   row.effective_to ?? '',
  };
}

export async function getDeptStaffingRules() {
  const user = await getSessionUser();
  const { data, error } = await supabase
    .from('department_staffing_rules')
    .select('*')
    .eq('user_id', user.id)
    .order('department')
    .order('shift_category');
  if (error) { console.error('getDeptStaffingRules:', error); return []; }
  return (data || []).map(dbToRule);
}

export async function saveDeptStaffingRule({ id, department, shiftCategory, minStaff, effectiveFrom, effectiveTo }) {
  const user = await getSessionUser();
  const row = {
    user_id:        user.id,
    department:     department.trim(),
    shift_category: shiftCategory,
    min_staff:      parseInt(minStaff) || 1,
    effective_from: effectiveFrom || null,
    effective_to:   effectiveTo || null,
  };
  if (id) {
    const { error } = await supabase.from('department_staffing_rules').update(row).eq('id', id).eq('user_id', user.id);
    if (error) throw error;
  } else {
    const { error } = await supabase.from('department_staffing_rules')
      .upsert({ ...row }, { onConflict: 'user_id,department,shift_category', ignoreDuplicates: false });
    if (error) throw error;
  }
}

export async function deleteDeptStaffingRule(id) {
  const user = await getSessionUser();
  const { error } = await supabase.from('department_staffing_rules').delete().eq('id', id).eq('user_id', user.id);
  if (error) throw error;
}
